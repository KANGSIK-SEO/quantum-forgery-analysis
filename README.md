# Quantum Forgery Analysis / 양자 위작 분석

Exploratory analysis of one known artwork forgery using IBM Quantum real hardware.  
IBM Quantum 실기기를 사용해 알려진 미술품 위작 1점을 탐색적으로 분석했습니다.

## Experiment / 실험

- Artwork / 작품: Han van Meegeren, *The Procuress* (Wikimedia Commons)
- Features / 특징: mean luminance / 평균 밝기, luminance contrast / 밝기 대비, colorfulness / 색채도, edge density / 윤곽 밀도, texture entropy / 텍스처 엔트로피
- Circuit / 회로: 5 qubits / 큐비트 5개, 1,024 shots per run / 회당 1,024 shots
- Hardware runs / 실기기 실행: 1,000 on `ibm_kingston` / `ibm_kingston`에서 1,000회
- Total measurements / 총 측정: 1,024,000

The measurement distribution is an experimental quantum fingerprint of the encoded image features. It is **not** an art-authentication or forgery-probability model. Reliable authentication would require a representative dataset of authenticated originals and forgeries, consistent preprocessing, calibration, and statistical validation.  
측정 분포는 인코딩된 이미지 특징의 실험적 양자 지문입니다. **미술품 진위 또는 위작 확률 모델이 아닙니다.** 신뢰할 수 있는 인증에는 진품·위작의 대표 데이터셋, 일관된 전처리, 보정 및 통계 검증이 필요합니다.

## Files / 파일

- `results/1.txt` through `results/1000.txt`: individual hardware-run results / 개별 실기기 실행 결과
- `visualization/distribution.png`: aggregated measurement distribution / 집계 측정 분포도
- `visualization/distribution_summary.txt`: aggregated counts and percentages / 집계 횟수와 비율
- `results/source_metadata.json`: source and feature metadata / 출처 및 특징 메타데이터
- `analyze_forgery.py`: execution script / 실행 스크립트

Source artwork / 작품 출처: [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:The_Procuress_forgery_by_Han_van_Meegeren_from_the_Courtauld_Gallery.jpg)
