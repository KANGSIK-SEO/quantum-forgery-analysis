#!/usr/bin/env python3
"""Generate reproducible static charts from the quantum run results."""

from __future__ import annotations

import argparse
import json
import math
from html import escape
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


FEATURE_ORDER = (
    "mean_luminance",
    "luminance_contrast",
    "colorfulness",
    "edge_density",
    "texture_entropy",
)
COLORS = {
    "blue": "#5069d9",
    "orange": "#e28b45",
    "green": "#4c9f70",
    "red": "#c95c5c",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create static visualizations from results/*.txt."
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=Path(__file__).parents[1] / "results",
        help="Directory containing numbered JSON result files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent,
        help="Directory for generated charts and summary.",
    )
    return parser.parse_args()


def load_results(results_dir: Path) -> list[dict[str, Any]]:
    paths = sorted(
        results_dir.glob("[0-9]*.txt"),
        key=lambda path: int(path.stem),
    )
    if not paths:
        raise FileNotFoundError(f"No numbered result files found in {results_dir}")

    records: list[dict[str, Any]] = []
    for path in paths:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not read {path}: {exc}") from exc
        if not isinstance(record, dict) or "quantum_result" not in record:
            raise ValueError(f"Invalid result shape in {path}")
        records.append(record)
    return records


def aggregate(records: list[dict[str, Any]]) -> tuple[Counter[str], Counter[str], list[float]]:
    counts: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    elapsed: list[float] = []
    for record in records:
        result = record["quantum_result"]
        status = result.get("status", "unknown")
        statuses[status] += 1
        if status == "completed":
            counts.update(result.get("counts", {}))
        duration = result.get("elapsed_seconds", result.get("execution_elapsed_seconds"))
        if isinstance(duration, (int, float)):
            elapsed.append(float(duration))
    return counts, statuses, elapsed


def style_axes(ax: plt.Axes) -> None:
    ax.grid(axis="y", alpha=0.22)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def save_distribution(counts: Counter[str], output: Path, total_shots: int) -> None:
    states = [state for state, _ in counts.most_common()]
    values = [counts[state] / total_shots * 100 for state in states]
    fig, ax = plt.subplots(figsize=(16, 8))
    ax.bar(states, values, color=COLORS["blue"], width=0.82)
    ax.set_title("IBM Quantum measurement distribution")
    ax.set_xlabel("5-qubit measured bitstring")
    ax.set_ylabel("Probability (%)")
    ax.tick_params(axis="x", rotation=65)
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(output / "distribution.png", dpi=160)
    plt.close(fig)


def save_feature_profile(record: dict[str, Any], output: Path) -> None:
    features = record.get("features", {})
    names = [name for name in FEATURE_ORDER if name in features]
    values = [float(features[name]) for name in names]
    labels = [name.replace("_", "\n") for name in names]
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(labels, values, color=COLORS["orange"])
    ax.set_title("Encoded image feature profile")
    ax.set_ylabel("Normalized value")
    ax.set_ylim(0, 1)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.025,
            f"{value:.3f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(output / "feature_profile.png", dpi=160)
    plt.close(fig)


def save_runtime_profile(elapsed: list[float], output: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(elapsed, bins=min(30, max(8, len(elapsed) // 25)), color=COLORS["green"])
    ax.axvline(np.mean(elapsed), color=COLORS["red"], linestyle="--", label=f"Mean: {np.mean(elapsed):.2f}s")
    ax.set_title("Hardware run duration")
    ax.set_xlabel("Elapsed time (seconds)")
    ax.set_ylabel("Runs")
    ax.legend()
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(output / "runtime_profile.png", dpi=160)
    plt.close(fig)


def save_overview(
    counts: Counter[str],
    statuses: Counter[str],
    elapsed: list[float],
    record: dict[str, Any],
    output: Path,
    total_shots: int,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    ax = axes[0, 0]
    states = [state for state, _ in counts.most_common()]
    percentages = [counts[state] / total_shots * 100 for state in states]
    ax.bar(states, percentages, color=COLORS["blue"])
    ax.set_title("Measurement distribution")
    ax.set_ylabel("Probability (%)")
    ax.tick_params(axis="x", rotation=70, labelsize=8)
    style_axes(ax)

    ax = axes[0, 1]
    names = [name for name in FEATURE_ORDER if name in record.get("features", {})]
    values = [float(record["features"][name]) for name in names]
    ax.bar([name.replace("_", "\n") for name in names], values, color=COLORS["orange"])
    ax.set_title("Encoded image features")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Normalized value")
    style_axes(ax)

    ax = axes[1, 0]
    ax.hist(elapsed, bins=min(30, max(8, len(elapsed) // 25)), color=COLORS["green"])
    ax.axvline(np.mean(elapsed), color=COLORS["red"], linestyle="--")
    ax.set_title("Run duration")
    ax.set_xlabel("Seconds")
    ax.set_ylabel("Runs")
    style_axes(ax)

    ax = axes[1, 1]
    status_names = list(statuses)
    status_values = [statuses[name] for name in status_names]
    ax.bar(status_names, status_values, color=COLORS["red"])
    ax.set_title("Run status")
    ax.set_ylabel("Runs")
    style_axes(ax)

    backend = record.get("backend", "unknown")
    fig.suptitle(f"Quantum forgery analysis overview | backend: {backend}", fontsize=16)
    fig.tight_layout()
    fig.savefig(output / "report_overview.png", dpi=160)
    plt.close(fig)


def write_summary(
    records: list[dict[str, Any]],
    counts: Counter[str],
    statuses: Counter[str],
    elapsed: list[float],
    output: Path,
    total_shots: int,
) -> None:
    first = records[0]
    entropy = -sum(
        (count / total_shots) * math.log2(count / total_shots)
        for count in counts.values()
        if count
    )
    lines = [
        "Quantum forgery analysis static report",
        "=======================================",
        f"Runs: {len(records)}",
        f"Backend: {first.get('backend', 'unknown')}",
        f"Shots per run: {first.get('shots', 'unknown')}",
        f"Total completed shots: {total_shots:,}",
        f"Statuses: {dict(statuses)}",
        f"Average elapsed seconds: {np.mean(elapsed):.3f}",
        f"Median elapsed seconds: {np.median(elapsed):.3f}",
        f"Measurement entropy (bits): {entropy:.6f}",
        "",
        "Generated files:",
        "- report_overview.png",
        "- distribution.png",
        "- feature_profile.png",
        "- runtime_profile.png",
        "- dashboard.html",
    ]
    (output / "report_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_dashboard(
    records: list[dict[str, Any]],
    counts: Counter[str],
    statuses: Counter[str],
    elapsed: list[float],
    output: Path,
    total_shots: int,
) -> None:
    first = records[0]
    payload = {
        "backend": first.get("backend", "unknown"),
        "runs": len(records),
        "shotsPerRun": first.get("shots", 0),
        "totalShots": total_shots,
        "features": first.get("features", {}),
        "counts": dict(counts.most_common()),
        "statuses": dict(statuses),
        "elapsed": elapsed,
    }
    data = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    title = escape("Quantum forgery analysis dashboard")
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ color-scheme: light; --ink:#182033; --muted:#68738a; --line:#dce1eb; --blue:#5069d9; --orange:#e28b45; --green:#4c9f70; --red:#c95c5c; --surface:#fff; --background:#f4f6fb; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font:15px/1.45 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:var(--background); }}
main {{ max-width:1400px; margin:0 auto; padding:32px; }}
header {{ display:flex; justify-content:space-between; gap:24px; align-items:flex-end; margin-bottom:24px; }}
h1 {{ margin:0 0 6px; font-size:clamp(1.7rem,3vw,2.5rem); }}
h2 {{ margin:0 0 16px; font-size:1.05rem; }}
p {{ margin:0; color:var(--muted); }}
.grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:18px; }}
.card,.panel {{ background:var(--surface); border:1px solid var(--line); border-radius:14px; box-shadow:0 4px 18px #1820330b; }}
.card {{ padding:18px; }} .label {{ color:var(--muted); font-size:.8rem; }} .value {{ display:block; margin-top:5px; font-size:1.45rem; font-weight:700; }}
.panels {{ display:grid; grid-template-columns:1.5fr 1fr; gap:18px; }} .panel {{ padding:20px; margin-bottom:18px; }}
.bar {{ display:flex; align-items:center; gap:10px; margin:9px 0; }} .bar-label {{ width:48px; font-family:ui-monospace,monospace; font-size:.82rem; }} .bar-track {{ flex:1; height:19px; background:#edf0f7; border-radius:5px; overflow:hidden; }} .bar-fill {{ height:100%; background:var(--blue); border-radius:5px; }} .bar-value {{ width:75px; color:var(--muted); text-align:right; font-size:.82rem; }}
.feature {{ display:grid; grid-template-columns:155px 1fr 55px; align-items:center; gap:10px; margin:14px 0; }} .feature-name {{ font-family:ui-monospace,monospace; font-size:.82rem; }} .feature .bar-fill {{ background:var(--orange); }}
table {{ width:100%; border-collapse:collapse; font-size:.87rem; }} th,td {{ padding:9px 6px; border-bottom:1px solid var(--line); text-align:left; }} th {{ color:var(--muted); font-weight:600; }} td:last-child,th:last-child {{ text-align:right; }}
.status-list {{ display:flex; flex-wrap:wrap; gap:10px; }} .status {{ padding:10px 14px; border-radius:9px; background:#eef1f8; }} .status strong {{ display:block; font-size:1.2rem; }} .note {{ margin-top:18px; padding:12px 14px; background:#fff8ed; border-left:3px solid var(--orange); color:#725021; }}
@media (max-width:900px) {{ main {{ padding:20px; }} .grid {{ grid-template-columns:repeat(2,1fr); }} .panels {{ grid-template-columns:1fr; }} header {{ display:block; }} }}
@media (max-width:520px) {{ .grid {{ grid-template-columns:1fr; }} .feature {{ grid-template-columns:125px 1fr 48px; }} }}
</style>
</head>
<body>
<main>
<header><div><h1>{title}</h1><p>Static, reproducible view of the tracked IBM Quantum run results.</p></div><p id="backend"></p></header>
<section class="grid" id="cards"></section>
<section class="panels">
<div>
<article class="panel"><h2>Measurement distribution</h2><div id="distribution"></div></article>
<article class="panel"><h2>Top measured states</h2><table><thead><tr><th>Bitstring</th><th>Count</th><th>Probability</th></tr></thead><tbody id="states"></tbody></table></article>
</div>
<div>
<article class="panel"><h2>Encoded image features</h2><div id="features"></div></article>
<article class="panel"><h2>Run status</h2><div class="status-list" id="statuses"></div><div class="note">This dashboard visualizes an experimental quantum fingerprint. It is not an authenticity classifier or forgery probability model.</div></article>
</div>
</section>
</main>
<script>
const report = {data};
const total = report.totalShots;
const fmt = new Intl.NumberFormat();
const pct = value => `${{(value / total * 100).toFixed(4)}}%`;
document.querySelector("#backend").textContent = `Backend: ${{report.backend}}`;
document.querySelector("#cards").innerHTML = [
  ["Runs", fmt.format(report.runs)],
  ["Shots per run", fmt.format(report.shotsPerRun)],
  ["Total measurements", fmt.format(total)],
  ["Mean runtime", `${{(report.elapsed.reduce((a,b) => a+b, 0) / report.elapsed.length).toFixed(2)}} s`]
].map(([label,value]) => `<div class="card"><span class="label">${{label}}</span><span class="value">${{value}}</span></div>`).join("");
const maxCount = Math.max(...Object.values(report.counts));
document.querySelector("#distribution").innerHTML = Object.entries(report.counts).map(([state,count]) =>
  `<div class="bar"><span class="bar-label">${{state}}</span><span class="bar-track"><span class="bar-fill" style="width:${{count / maxCount * 100}}%"></span></span><span class="bar-value">${{pct(count)}}</span></div>`).join("");
document.querySelector("#states").innerHTML = Object.entries(report.counts).slice(0,12).map(([state,count]) =>
  `<tr><td><code>${{state}}</code></td><td>${{fmt.format(count)}}</td><td>${{pct(count)}}</td></tr>`).join("");
document.querySelector("#features").innerHTML = Object.entries(report.features).map(([name,value]) =>
  `<div class="feature"><span class="feature-name">${{name}}</span><span class="bar-track"><span class="bar-fill" style="width:${{value * 100}}%"></span></span><span>${{Number(value).toFixed(3)}}</span></div>`).join("");
document.querySelector("#statuses").innerHTML = Object.entries(report.statuses).map(([name,count]) =>
  `<div class="status"><span class="label">${{name}}</span><strong>${{fmt.format(count)}}</strong></div>`).join("");
</script>
</body>
</html>
"""
    (output / "dashboard.html").write_text(html, encoding="utf-8")


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    records = load_results(args.results)
    counts, statuses, elapsed = aggregate(records)
    if not elapsed:
        raise ValueError("No elapsed run durations found")
    total_shots = sum(counts.values())
    if total_shots == 0:
        raise ValueError("No completed measurement counts found")

    save_distribution(counts, args.output, total_shots)
    save_feature_profile(records[0], args.output)
    save_runtime_profile(elapsed, args.output)
    save_overview(counts, statuses, elapsed, records[0], args.output, total_shots)
    write_summary(records, counts, statuses, elapsed, args.output, total_shots)
    save_dashboard(records, counts, statuses, elapsed, args.output, total_shots)
    print(f"Generated static report in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
