#!/usr/bin/env python3
"""Analyze one Wikimedia Commons forgery sample on IBM Quantum hardware."""

from __future__ import annotations

import json
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import numpy as np
import requests
from dotenv import dotenv_values
from PIL import Image, ImageFilter
from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2


ENV_FILE = Path("/Users/kangsikseo/.copilot/attachments/edc499c4-8686-4280-9983-643a6c347986-.env")
OUTPUT_DIR = Path.home() / "Desktop" / "위작분포"
IMAGE_PATH = OUTPUT_DIR / "source_forgery.jpg"
IMAGE_TITLE = "File:The Procuress forgery by Han van Meegeren from the Courtauld Gallery.jpg"
IMAGE_URL = (
    "https://upload.wikimedia.org/wikipedia/commons/2/20/"
    "The_Procuress_forgery_by_Han_van_Meegeren_from_the_Courtauld_Gallery.jpg"
)
RUNS = 1000
OPERATION_TIMEOUT_SECONDS = 60


def fetch_image() -> None:
    response = requests.get(
        IMAGE_URL,
        headers={"User-Agent": "forgery-quantum-analysis/1.0"},
        timeout=20,
    )
    response.raise_for_status()
    IMAGE_PATH.write_bytes(response.content)


def normalized_entropy(gray: np.ndarray) -> float:
    histogram, _ = np.histogram(gray, bins=256, range=(0, 256), density=True)
    probabilities = histogram[histogram > 0]
    entropy = float(-(probabilities * np.log2(probabilities)).sum())
    return min(1.0, entropy / 8.0)


def extract_features() -> dict[str, float]:
    image = Image.open(IMAGE_PATH).convert("RGB").resize((256, 256))
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
    return {name: round(min(1.0, max(0.0, value)), 8) for name, value in values.items()}


def build_circuit(features: dict[str, float]) -> QuantumCircuit:
    values = list(features.values())
    circuit = QuantumCircuit(5)
    for index, value in enumerate(values):
        circuit.ry(math.pi * value, index)
        circuit.rz(math.pi * (1.0 - value), index)
    for index in range(4):
        circuit.cx(index, index + 1)
    circuit.measure_all()
    return circuit


def load_service() -> QiskitRuntimeService:
    config = dotenv_values(ENV_FILE)
    token = config.get("IBM_QUANTUM_API_KEY")
    instance = config.get("IBM_QUANTUM_CRN")
    if not token or not instance:
        raise RuntimeError("IBM_QUANTUM_API_KEY and IBM_QUANTUM_CRN must be set in the attached .env file")
    return QiskitRuntimeService(channel="ibm_quantum_platform", token=token, instance=instance)


def choose_backend(service: QiskitRuntimeService):
    backends = service.backends(simulator=False, operational=True, min_num_qubits=5)
    if not backends:
        raise RuntimeError("No operational IBM Quantum real backend with at least 5 qubits is available")
    return min(backends, key=lambda backend: backend.status().pending_jobs)


def run_once(sampler: SamplerV2, circuit: QuantumCircuit) -> dict:
    started = time.monotonic()
    job = sampler.run([circuit], shots=1024)
    try:
        result = job.result(timeout=OPERATION_TIMEOUT_SECONDS)
        counts = result[0].data.meas.get_counts()
        elapsed = time.monotonic() - started
        return {
            "status": "completed",
            "elapsed_seconds": round(elapsed, 3),
            "job_id": job.job_id(),
            "counts": dict(sorted(counts.items())),
        }
    except TimeoutError:
        job.cancel()
        return {
            "status": "error",
            "error": f"operation exceeded {OPERATION_TIMEOUT_SECONDS} seconds; job cancelled",
            "job_id": job.job_id(),
            "elapsed_seconds": OPERATION_TIMEOUT_SECONDS,
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "job_id": job.job_id(),
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }


def write_result(index: int, payload: dict) -> None:
    (OUTPUT_DIR / f"{index}.txt").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fetch_image()
    features = extract_features()
    circuit = build_circuit(features)
    service = load_service()
    backend = choose_backend(service)
    isa_circuit = transpile(circuit, backend=backend, optimization_level=1)
    common = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "wikimedia_title": IMAGE_TITLE,
            "image_url": IMAGE_URL,
            "local_image": str(IMAGE_PATH),
        },
        "features": features,
        "feature_order": list(features),
        "backend": backend.name,
        "shots": 1024,
        "operation_timeout_seconds": OPERATION_TIMEOUT_SECONDS,
        "circuit_qubits": 5,
    }
    (OUTPUT_DIR / "source_metadata.json").write_text(
        json.dumps(common, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    def run_index(index: int) -> tuple[int, dict]:
        sampler = SamplerV2(mode=backend)
        result = {**common, "run": index, "quantum_result": run_once(sampler, isa_circuit)}
        write_result(index, result)
        return index, result["quantum_result"]

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(run_index, index) for index in range(1, RUNS + 1)]
        for future in as_completed(futures):
            index, quantum_result = future.result()
            print(json.dumps({"run": index, **quantum_result}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"fatal: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
