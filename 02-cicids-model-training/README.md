# CICIDS2017 Autoencoder Training

Autoencoder-based anomaly detection model trained on CICIDS2017 dataset for network intrusion detection.

## Overview

This repository contains the implementation of Phase 1 of the thesis: developing and validating an autoencoder neural network for anomaly detection using the CICIDS2017 dataset.

### Key Results

- **F1-Score:** 80.34%
- **Accuracy:** 81.81%
- **Precision:** 88.22%
- **Recall:** 73.75%
- **Dataset:** CICIDS2017 (2,520,751 records)

## Project Structure
```
02-cicids-model-training/
├── data/
│   ├── raw/                    # CICIDS2017 CSV files
│   └── processed/              # Preprocessed numpy arrays
├── models/
│   └── saved_models/           # Trained models
├── results/
│   ├── metrics/                # Performance metrics
│   └── plots/                  # Visualizations
├── src/
│   ├── preprocess.py
│   ├── train_autoencoder.py
│   ├── evaluate.py
│   └── improve_model.py
└── requirements.txt
```

## Installation

### 1. Clone Repository
```bash
git clone https://github.com/YOUR_USERNAME/02-cicids-model-training.git
cd 02-cicids-model-training
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## Dataset Acquisition

### Download CICIDS2017 from Kaggle
```bash
# Install Kaggle CLI
pip install kaggle

# Setup API token
mkdir -p ~/.kaggle
# Download kaggle.json from https://www.kaggle.com/settings
mv ~/Downloads/kaggle.json ~/.kaggle/
chmod 600 ~/.kaggle/kaggle.json

# Download dataset
kaggle datasets download -d ericanacletoribeiro/cicids2017-cleaned-and-preprocessed -p data/raw/
cd data/raw/
unzip cicids2017-cleaned-and-preprocessed.zip
rm cicids2017-cleaned-and-preprocessed.zip
```

## Usage

### Step 1: Preprocess Data
```bash
python src/preprocess.py
```

Outputs:
- `data/processed/X_train.npy` (1,676,045 samples)
- `data/processed/X_test_normal.npy` (419,012 samples)
- `data/processed/X_test_anomaly.npy` (425,694 samples)

### Step 2: Train Initial Model
```bash
python src/train_autoencoder.py
```

Outputs:
- `models/saved_models/autoencoder.h5`
- `results/plots/training_history.png`

### Step 3: Evaluate Model
```bash
python src/evaluate.py
```

Outputs:
- `results/metrics/autoencoder_metrics.json`
- `results/plots/evaluation.png`

### Step 4: Train Optimized Model (v2)
```bash
python src/improve_model.py
```

Outputs:
- `models/saved_models/autoencoder_v2.h5`
- `results/metrics/autoencoder_v2_metrics.json`

## Model Architecture
```
Autoencoder v2 (Optimized):

Encoder:
  Input(52) → Dense(64, relu) → BatchNorm →
  Dense(32, relu) → BatchNorm →
  Dense(16, relu) → Dense(8, relu)

Decoder:
  Dense(16, relu) → Dense(32, relu) → BatchNorm →
  Dense(64, relu) → Dense(52, linear)

Parameters: ~6,000
```

## Results

### Model v1 (Baseline)

| Metric    | Value  |
|-----------|--------|
| Accuracy  | 78.25% |
| Precision | 92.62% |
| Recall    | 61.77% |
| F1-Score  | 74.11% |

### Model v2 (Optimized)

| Metric    | Value  | Change  |
|-----------|--------|---------|
| Accuracy  | 81.81% | +3.56%  |
| Precision | 88.22% | -4.40%  |
| Recall    | 73.75% | +11.98% |
| F1-Score  | 80.34% | +6.23%  |

**Key Improvements:**
- Outlier removal (2% of training data)
- BatchNormalization layers
- Threshold optimization (90th percentile)

## Dataset Details

- **Source:** CICIDS2017 (Kaggle cleaned version)
- **Total Records:** 2,520,751
- **Normal Traffic:** 2,095,057 (83.1%)
- **Attacks:** 425,694 (16.9%)
  - DoS/DDoS: 321,759
  - Port Scanning: 90,694
  - Brute Force: 9,150
  - Web Attacks: 2,143
  - Botnets: 1,948
- **Features:** 52


## License

MIT License
