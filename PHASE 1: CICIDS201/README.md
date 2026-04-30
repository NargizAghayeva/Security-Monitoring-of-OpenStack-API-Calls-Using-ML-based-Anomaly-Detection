# Security Monitoring of OpenStack API Calls Using ML-Based Anomaly Detection

**MSc Thesis — ELTE University Budapest**  
**Track 1: Keystone API Anomaly Detector (CICIDS2017 Pretraining + Fine-tuning)**

---

## Overview

This repository contains the full ML pipeline for Track 1 of the thesis. The approach uses an **unsupervised autoencoder** pretrained on the CICIDS2017 network intrusion dataset, then fine-tuned on real OpenStack Keystone session data. Anomaly detection is based on **reconstruction error** — normal traffic reconstructs with low error, attacks with high error.

### Results

| Metric    | Value  |
|-----------|--------|
| F1 Score  | 0.9981 |
| ROC-AUC   | 1.0000 |
| Precision | ~1.000 |
| Recall    | ~0.997 |

---

## Repository Structure

```
openstack-anomaly-detection/
│
├── README.md
│
├── phase1/
│   └── phase1_cicids_pretraining.py      # EDA, feature selection, autoencoder training on CICIDS2017
│
├── phase2/
│   └── phase2_keystone_finetuning.py     # Session aggregation, fine-tuning, evaluation
│
└── requirements.txt
```

---

## Pipeline

### Phase 1 — CICIDS2017 Pretraining

1. Load and clean CICIDS2017 dataset
2. Binary label encoding (Normal=0, Attack=1)
3. EDA: distributions, outliers, correlation matrix
4. Feature selection: Variance threshold → Correlation filter → Random Forest importance
5. Train/test split (autoencoder trains on **normal traffic only**)
6. MinMax scaling (fit on train only — no data leakage)
7. Autoencoder training: `input_dim → 16 → 8 → 4 → 8 → 16 → input_dim`
8. Threshold selection via percentile sweep on normal reconstruction errors
9. Export: `autoencoder_model.h5`, `scaler.pkl`, `phase2_feature_mapping.csv`

### Phase 2 — Keystone Session Aggregation + Fine-tuning

1. Load `final_dataset.csv` (real OpenStack Keystone API logs)
2. Session aggregation: 60-second time windows per source IP → 24 CICIDS-equivalent features
3. Map session features to CICIDS feature space using `phase2_feature_mapping.csv`
4. Scale using pretrained scaler (manual override for `Destination Port` and `Flow IAT Std`)
5. Fine-tune autoencoder on **normal Keystone sessions only** (lr=1e-4, EarlyStopping, ReduceLROnPlateau)
6. Proper train/test split: fine-tune data excluded from evaluation
7. Threshold sweep (p50–p99) → best F1 threshold
8. Evaluation: per-attack-type recall breakdown, confusion matrix, ROC curve

---

## Attack Types Detected

- `brute` — Brute force login attempts
- `portscan` — Port scanning activity
- `webattack` — Web application attacks
- `dos` — Denial of Service

---

## Input Data

| File | Description |
|------|-------------|
| `cicids2017_cleaned.csv` | Preprocessed CICIDS2017 dataset (52 features + `Attack Type` label) |
| `final_dataset.csv` | Real OpenStack Keystone API logs with columns: `timestamp`, `source_ip`, `request_bytes`, `response_bytes`, `http_method`, `endpoint_category`, `fail_rate_per_ip_60s`, `label`, `attack_type` |

---

## Output Files

| File | Description |
|------|-------------|
| `autoencoder_model.h5` | Pretrained autoencoder weights |
| `autoencoder_finetuned.h5` | Fine-tuned weights on Keystone data |
| `scaler.pkl` | MinMaxScaler fitted on CICIDS normal traffic |
| `phase2_feature_mapping.csv` | CICIDS feature → Keystone session attribute mapping |
| `eda_01_class_distribution.png` | Class balance visualization |
| `eda_02_feature_distributions.png` | Feature histograms |
| `eda_03_outliers.png` | Boxplots (log scale) |
| `eda_04_correlation_matrix.png` | Feature correlation heatmap |
| `eda_05_feature_importance.png` | Random Forest feature importances |
| `training_loss.png` | Autoencoder pretraining loss curve |
| `phase2_finetune_loss.png` | Fine-tuning loss curve |
| `reconstruction_error.png` | Error distribution: normal vs attack |
| `confusion_matrix.png` | Final confusion matrix |
| `roc_curve.png` | ROC curve |
| `track1_final_evaluation.png` | Combined evaluation plots |

---

## Requirements

```
tensorflow>=2.10
scikit-learn>=1.2
pandas>=1.5
numpy>=1.23
matplotlib
seaborn
joblib
```

Install:
```bash
pip install -r requirements.txt
```

---

## Usage

```bash
# Phase 1: Pretrain on CICIDS2017
python phase1/phase1_cicids_pretraining.py

# Phase 2: Fine-tune on Keystone sessions
python phase2/phase2_keystone_finetuning.py
```

Both scripts assume the input CSVs are in the working directory.

---

## Architecture

```
Input (24) → Dense(16, ReLU) → Dense(8, ReLU) → Dense(4, ReLU) [bottleneck]
           → Dense(8, ReLU)  → Dense(16, ReLU) → Dense(24, Sigmoid) → Output
```

Anomaly score = per-sample MSE reconstruction error.  
Classification: `error > threshold → Attack`, else `Normal`.

---

## Thesis Context

This track implements the **transfer learning** component of the thesis:  
pretraining on a large labeled network dataset (CICIDS2017) and adapting to  
the OpenStack domain via unsupervised fine-tuning on real Keystone API traffic.

The 24-feature session aggregation maps CICIDS2017 flow-level features to  
Keystone API session-level attributes, enabling cross-domain anomaly detection  
without requiring labeled attack data from the target environment.
