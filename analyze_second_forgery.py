#!/usr/bin/env python3
"""Run the five-feature quantum analysis on a second known forgery."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
from dotenv import dotenv_values
from PIL import Image
from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2


IMAGE_TITLE = "File:EmmausgangersVanMeegeren1937.jpg"
IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/2/21/EmmausgangersVanMeegeren1937.jpg"
FEATURE_ORDER = (
    "mean_luminance",
    "luminance_contrast",
    "colorfulness",
    "edge_density",
    "texture_entropy",
)
RUNS = 1000
SHOTS = 1024
EXECUTION_TIMEOUT_SECONDS = 30
POLL_SECONDS = 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/second_forgery"),
    )
    parser.add_argument("--runs", type=int, default=RUNS)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def fetch_image(path: Path) -> None:
    response = requests.get(
        IMAGE_URL,
        headers={"User-Agent": "quantum-forgery-analysis/1.0"},
        timeout=20,
    )
    response.raise_for_status()
    path.write_bytes(response.content)


def normalized_entropy(gray: np.ndarray) -> float:
    histogram, _ = np.histogram(gray, bins=256, range=(0, 256), density=True)
    probabilities = histogram[histogram > 0]
    return min(1.0, float(-(probabilities * np.log2(probabilities)).sum()) / 8.0)


def extract_features(path: Path) -> dict[str, float]:
    image = Image.open(path).convert("RGB").resize((256, 256))
    rgb = np.asarray(image, dtype=np.float32) / 255.0
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    normalized_gray = gray / 255.0
    gx, gy = np.gradient(normalized_gray)
    edge_density = float(((np.abs(gx) + np.abs(gy)) / 2.0 > 0.12).mean())
    saturation = (rgb.max(axis=2) - rgb.min(axis=2)) / np.maximum(rgb.max(axis=2), 1e-8)
    values = {
        "mean_luminance": float(normalized_gray.mean()),
        "luminance_contrast": float(normalized_gray.std() * 3.0),
        "colorfulness": float(saturation.mean()),
        "edge_density": edge_density,
        "texture_entropy": normalized_entropy(gray),
    }
    return {
        name: round(min(1.0, max(0.0, values[name])), 8)
        for name in FEATURE_ORDER
    }


def build_circuit(features: dict[str, float]) -> QuantumCircuit:
    circuit = QuantumCircuit(5)
    for index, name in enumerate(FEATURE_ORDER):
        value = features[name]
        circuit.ry(math.pi * value, index)
        circuit.rz(math.pi * (1.0 - value), index)
    for index in range(4):
        circuit.cx(index, index + 1)
    circuit.measure_all()
    return circuit


def load_service(env_file: Path) -> QiskitRuntimeService:
    config = dotenv_values(env_file)
    token = config.get("IBM_QUANTUM_API_KEY")
    instance = config.get("IBM_QUANTUM_CRN")
    if not token or not instance:
        raise RuntimeError("IBM_QUANTUM_API_KEY and IBM_QUANTUM_CRN are required")
    return QiskitRuntimeService(
        channel="ibm_quantum_platform",
        token=token,
        instance=instance,
    )


def choose_backend(service: QiskitRuntimeService):
    backends = service.backends(simulator=False, operational=True, min_num_qubits=5)
    if not backends:
        raise RuntimeError("No operational IBM Quantum real backend with at least 5 qubits")
    return min(backends, key=lambda backend: backend.status().pending_jobs)


def status_name(status: object) -> str:
    return str(getattr(status, "name", status)).upper().split(".")[-1]


def run_once(sampler: SamplerV2, circuit: QuantumCircuit) -> dict:
    job = sampler.run([circuit], shots=SHOTS)
    running_started: float | None = None
    try:
        while True:
            current_status = status_name(job.status())
            if current_status == "RUNNING" and running_started is None:
                running_started = time.monotonic()
            if running_started is not None:
                execution_elapsed = time.monotonic() - running_started
                if execution_elapsed > EXECUTION_TIMEOUT_SECONDS:
                    job.cancel()
                    return {
                        "status": "error",
                        "error": "quantum execution exceeded 30 seconds; job cancelled",
                        "job_id": job.job_id(),
                        "execution_elapsed_seconds": round(execution_elapsed, 3),
                    }
            if current_status in {"DONE", "ERROR", "CANCELLED", "CANCELED"}:
                break
            time.sleep(POLL_SECONDS)

        if current_status != "DONE":
            return {
                "status": "error",
                "error": f"job ended with status {current_status}",
                "job_id": job.job_id(),
                "execution_elapsed_seconds": round(
                    time.monotonic() - running_started, 3
                )
                if running_started is not None
                else None,
            }

        result = job.result(timeout=5)
        counts = result[0].data.meas.get_counts()
        return {
            "status": "completed",
            "job_id": job.job_id(),
            "execution_elapsed_seconds": round(
                time.monotonic() - running_started, 3
            )
            if running_started is not None
            else 0.0,
            "counts": dict(sorted(counts.items())),
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "job_id": job.job_id(),
            "execution_elapsed_seconds": round(
                time.monotonic() - running_started, 3
            )
            if running_started is not None
            else None,
        }


def main() -> int:
    args = parse_args()
    if args.runs < 1 or args.workers < 1:
        raise ValueError("--runs and --workers must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    image_path = args.output / "source_forgery.jpg"
    fetch_image(image_path)
    features = extract_features(image_path)
    service = load_service(args.env_file)
    backend = choose_backend(service)
    circuit = transpile(
        build_circuit(features),
        backend=backend,
        optimization_level=1,
    )
    common = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "wikimedia_title": IMAGE_TITLE,
            "image_url": IMAGE_URL,
            "local_image": str(image_path),
        },
        "features": features,
        "feature_order": list(FEATURE_ORDER),
        "backend": backend.name,
        "shots": SHOTS,
        "execution_timeout_seconds": EXECUTION_TIMEOUT_SECONDS,
        "queue_wait_is_not_timed": True,
        "circuit_qubits": 5,
    }
    (args.output / "source_metadata.json").write_text(
        json.dumps(common, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    def run_index(index: int) -> tuple[int, dict]:
        sampler = SamplerV2(mode=backend)
        payload = {
            **common,
            "run": index,
            "quantum_result": run_once(sampler, circuit),
        }
        (args.output / f"{index}.txt").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return index, payload["quantum_result"]

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(run_index, index) for index in range(1, args.runs + 1)]
        for future in as_completed(futures):
            index, result = future.result()
            print(json.dumps({"run": index, **result}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"fatal: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
