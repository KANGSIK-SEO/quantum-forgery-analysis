# Second forgery report

## Source artwork

**Han van Meegeren, *Emmausgangers* (1937), known forgery**

- Wikimedia Commons: [File:EmmausgangersVanMeegeren1937.jpg](https://commons.wikimedia.org/wiki/File:EmmausgangersVanMeegeren1937.jpg)
- Image URL: `https://upload.wikimedia.org/wikipedia/commons/2/21/EmmausgangersVanMeegeren1937.jpg`
- Local copy: [`source_forgery.jpg`](source_forgery.jpg)

## Quantum experiment

- Backend: `ibm_fez`
- Runs: 1,000
- Shots per run: 1,024
- Qubits: 5
- Completed runs: 994
- Error runs: 6
- Execution limit: 30 seconds after the job enters `RUNNING`
- Queue wait: not included in the execution timeout

## Extracted features

| Feature | Value |
|---|---:|
| `mean_luminance` | 0.20231941 |
| `luminance_contrast` | 0.48003030 |
| `colorfulness` | 0.31518573 |
| `edge_density` | 0.01748657 |
| `texture_entropy` | 0.85298327 |

## Report files

- [`dashboard.html`](dashboard.html): self-contained browser dashboard
- [`report_overview.png`](report_overview.png): combined experiment overview
- [`distribution.png`](distribution.png): aggregate measured bitstring distribution
- [`feature_profile.png`](feature_profile.png): five encoded image features
- [`runtime_profile.png`](runtime_profile.png): execution-time distribution
- [`report_summary.txt`](report_summary.txt): aggregate statistics

These artifacts visualize an experimental quantum fingerprint. They are not an
art-authentication model or a forgery-probability estimate.
