# Quantum Forgery Analysis

Exploratory analysis of one known artwork forgery using IBM Quantum real hardware.

## Experiment

- Artwork: Han van Meegeren, *The Procuress* (Wikimedia Commons)
- Features: mean luminance, luminance contrast, colorfulness, edge density, texture entropy
- Circuit: 5 qubits, 1,024 shots per run
- Hardware runs: 1,000 on `ibm_kingston`
- Total measurements: 1,024,000

The measurement distribution is an experimental quantum fingerprint of the encoded image features. It is **not** an art-authentication or forgery-probability model. Reliable authentication would require a representative dataset of authenticated originals and forgeries, consistent preprocessing, calibration, and statistical validation.

## Files

- `results/1.txt` through `results/1000.txt`: individual hardware-run results
- `visualization/distribution.png`: aggregated measurement distribution
- `visualization/distribution_summary.txt`: aggregated counts and percentages
- `results/source_metadata.json`: source and feature metadata
- `results/analyze_forgery.py`: execution script

Source artwork: [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:The_Procuress_forgery_by_Han_van_Meegeren_from_the_Courtauld_Gallery.jpg)
