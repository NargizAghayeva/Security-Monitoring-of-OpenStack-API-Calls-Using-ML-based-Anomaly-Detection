# Security Monitoring of OpenStack API Calls Using ML-Based Anomaly Detection

This repository contains the full implementation of the MSc thesis project. The system detects anomalous behaviour in OpenStack API calls using unsupervised autoencoder-based anomaly detection. Two independent detection tracks are implemented: Track 1 targets Keystone authentication API sessions using transfer learning from CICIDS2017, and Track 2 targets Nova compute logs using sliding window feature engineering.

## Table of Contents

1. [Overview](#overview)
2. [Repository Structure](#repository-structure)
3. [Environment Setup](#environment-setup)
4. [Dataset Generation](#dataset-generation)
5. [Track 1: Keystone API Anomaly Detection](#track-1-keystone-api-anomaly-detection)
6. [Track 2: Nova Log Anomaly Detection](#track-2-nova-log-anomaly-detection)
7. [Results](#results)
8. [References](#references)

## Overview

### Thesis

**Title:** Security Monitoring of OpenStack API Calls Using ML-Based Anomaly Detection  
**Institution:** ELTE University Budapest — MSc in Computer Science (Cybersecurity)  
**Author:** Nargiz Aghayeva

### Problem Statement

Cloud environments generate large volumes of API activity. Traditional signature-based monitoring cannot detect novel or zero-day attack patterns. This project implements unsupervised anomaly detection — the model learns what normal behaviour looks like and flags deviations without requiring labelled attack data during training.

### Approach

Both tracks use an autoencoder trained exclusively on normal data. Anomalies are detected by measuring reconstruction error: normal inputs reconstruct with low error, anomalous inputs with high error. A threshold derived from the normal error distribution separates the two classes.

### Key Results

| Track | Dataset | F1 Score | ROC-AUC |
|-------|---------|----------|---------|
| Track 1 — Keystone | CICIDS2017 + real OpenStack Keystone logs | 0.9981 | 1.0000 |
| Track 2 — Nova | ParisaKalaki OpenStack Nova logs | 0.9900 | 0.9995 |

## Repository Structure

```
Security-Monitoring-of-OpenStack-API-Calls/
│
├── 01-devstack-setup/                   # DevStack installation and troubleshooting notes
│
├── Dataset_Generation_real/             # Scripts to generate Keystone API dataset
│   ├── config.py                        # IP addresses, credentials, endpoint config
│   ├── 1_normal_traffic.py              # Simulates normal Keystone API activity
│   ├── 2_attack_brute.py                # Simulates brute force login attacks
│   ├── 3_attack_portscan.py             # Simulates port scanning activity
│   ├── 4_attack_webattack.py            # Simulates web application attacks
│   ├── 5_attack_dos.py                  # Simulates denial of service attacks
│   ├── 6_verify_dataset.py              # Verifies and inspects the generated dataset
│   └── README.md                        # Dataset generation instructions
│
├── PHASE 1: CICIDS2017/                 # Track 1 — CICIDS2017 pretraining + Keystone fine-tuning
│   ├── phase1_cicids_pretraining.md     # EDA, feature selection, autoencoder training on CICIDS2017
│   └── phase2_keystone_finetuning.md   # Session aggregation, fine-tuning, evaluation
│
└── PHASE 2: Nova anomaly detection/     # Track 2 — Nova log anomaly detection
    └── track2_nova_anomaly_detection.md
```

## Environment Setup

### Requirements

```
Python        >= 3.9
TensorFlow    >= 2.10
scikit-learn  >= 1.2
pandas        >= 1.5
numpy         >= 1.23
matplotlib    >= 3.6
seaborn       >= 0.12
joblib        >= 1.2
```

### Installation

```bash
git clone https://github.com/NargizAghayeva/Security-Monitoring-of-OpenStack-API-Calls-Using-ML-based-Anomaly-Detection.git
cd Security-Monitoring-of-OpenStack-API-Calls-Using-ML-based-Anomaly-Detection
pip install tensorflow scikit-learn pandas numpy matplotlib seaborn joblib
```

### OpenStack (Track 1 dataset generation only)

Track 1 dataset generation requires a running OpenStack environment. A single-node DevStack setup on Ubuntu 22.04 was used. Full setup notes and troubleshooting are in `01-devstack-setup/`.

## Dataset Generation

### Track 1 — Keystone API Dataset

This step generates `final_dataset.csv` by sending real HTTP requests to a running OpenStack Keystone endpoint and recording per-request features.

#### 1. Configure connection settings

Edit `Dataset_Generation_real/config.py` and set your DevStack IP address, admin credentials, and endpoint URLs.

#### 2. Generate normal traffic

```bash
cd Dataset_Generation_real
python 1_normal_traffic.py
```

#### 3. Generate attack traffic

Run each attack script in sequence. Each script appends labelled rows to the dataset.

```bash
python 2_attack_brute.py
python 3_attack_portscan.py
python 4_attack_webattack.py
python 5_attack_dos.py
```

#### 4. Verify dataset

```bash
python 6_verify_dataset.py
```

This prints row counts, label distribution, and attack type breakdown. The output file `final_dataset.csv` is the input for Track 1 Phase 2.

### Track 2 — Nova Log Dataset

No local data collection is needed. The dataset is cloned automatically during execution in Cell 2 of the notebook:

```bash
git clone https://github.com/ParisaKalaki/openstack-logs.git
```

Three log files are used:

| File | Label |
|------|-------|
| `openstack-nova-normal-vm-create.log` | Normal (0) |
| `openstack-vm-destroy-immediately-after-create.log` | Anomaly — vm_destroy (1) |
| `openstack-nova-undefine-vm-after-create.log` | Anomaly — vm_undefine (1) |

The files `openstack-nova-sample.log` and `openstack-nova-dhcpoff.log` are excluded to prevent data contamination.

## Track 1: Keystone API Anomaly Detection

Track 1 uses transfer learning. An autoencoder is pretrained on the CICIDS2017 network intrusion dataset, then fine-tuned on real OpenStack Keystone session data collected from a DevStack environment.

### Phase 1 — CICIDS2017 Pretraining

Full step-by-step code: `PHASE 1: CICIDS2017/phase1_cicids_pretraining.md`

#### Input

Download the CICIDS2017 dataset from the [University of New Brunswick](https://www.unb.ca/cic/datasets/ids-2017.html), preprocess it into a single CSV with an `Attack Type` column, and place it as `cicids2017_cleaned.csv` in the working directory.

#### Steps

1. Load and clean dataset — remove NaN rows and records with negative Flow Duration
2. Binary label encoding: Normal Traffic = 0, any attack = 1
3. Feature selection: Variance threshold (< 0.01 dropped) → Correlation filter (> 0.95 dropped) → Random Forest importance (threshold = 0.01) → 24 final features
4. Train/test split: autoencoder trained on normal traffic only, test set contains both normal and attack
5. MinMaxScaler fitted on training data only — no data leakage
6. Autoencoder architecture: `24 → 16 → 8 → 4 → 8 → 16 → 24`
7. Threshold selection: sweep over percentiles p80–p99 of normal reconstruction error, pick best F1

#### Outputs

```
autoencoder_model.h5          — pretrained autoencoder weights
scaler.pkl                    — fitted MinMaxScaler
phase2_feature_mapping.csv    — CICIDS feature to Keystone session attribute mapping
```

### Phase 2 — Keystone Session Aggregation and Fine-tuning

Full step-by-step code: `PHASE 1: CICIDS2017/phase2_keystone_finetuning.md`

#### Input

```
final_dataset.csv             — generated in the Dataset Generation step
autoencoder_model.h5          — output of Phase 1
scaler.pkl                    — output of Phase 1
```

#### Steps

1. Load `final_dataset.csv` — raw per-request Keystone API log records
2. Aggregate into 60-second time windows per source IP → produces 24 CICIDS-equivalent session features
3. Map session features to CICIDS feature space using `phase2_feature_mapping.csv`
4. Scale using the pretrained scaler with manual override for two features (`Destination Port`, `Flow IAT Std`) that have no direct CICIDS equivalent
5. Fine-tune the pretrained autoencoder on normal Keystone sessions only (lr=1e-4, EarlyStopping patience=10, ReduceLROnPlateau)
6. Proper train/test split: fine-tune data is excluded from evaluation
7. Threshold sweep p50–p99 on held-out normal errors → best F1

#### Outputs

```
autoencoder_finetuned.h5
phase2_finetune_loss.png
track1_final_evaluation.png
```

### Track 1 Results

| Metric | Value |
|--------|-------|
| F1 Score | 0.9981 |
| Precision | 1.0000 |
| Recall | 0.9963 |
| ROC-AUC | 1.0000 |

Per-attack-type recall:

| Attack Type | Recall |
|-------------|--------|
| brute | 1.000 |
| portscan | 1.000 |
| webattack | 1.000 |
| dos | 0.987 |

## Track 2: Nova Log Anomaly Detection

Track 2 operates directly on raw OpenStack Nova log files. No pretrained model or external dataset download is required beyond the Nova logs cloned automatically in Cell 2.

Full step-by-step code: `PHASE 2: Nova anomaly detection/track2_nova_anomaly_detection.md`

### Steps

1. Clone Nova log dataset from GitHub (Cell 2 — runs automatically)
2. Parse raw log lines with regex: extract log level, component, request ID, instance ID, message
3. Sliding window feature engineering: window = 50 lines, step = 25 lines (50% overlap)
4. 14 features per window: error count, warning count, info count, error ratio, warning ratio, unique components, component diversity, and 7 keyword presence flags (failed, timeout, exception, destroy, spawn, invalid/could not, critical/fatal)
5. Train/test split: autoencoder trained on normal windows only
6. MinMaxScaler fitted on training data only
7. 5-fold cross-validation on normal data confirms stable learning across splits
8. Autoencoder architecture: `14 → 32 → 16 → 8 → 16 → 32 → 14`
9. Threshold sweep p50–p98 on normal reconstruction error → best F1
10. Baseline comparison against Isolation Forest

### Track 2 Results

| Metric | Autoencoder | Isolation Forest |
|--------|-------------|-----------------|
| F1 Score | 0.9900 | lower |
| Precision | 0.9900 | lower |
| Recall | 0.9900 | lower |
| ROC-AUC | 0.9995 | lower |

Per-anomaly-type recall:

| Anomaly Type | Recall |
|--------------|--------|
| vm_destroy | 1.000 |
| vm_undefine | 0.980 |

## Results

Both tracks demonstrate that unsupervised autoencoder-based anomaly detection is effective for OpenStack API security monitoring without requiring labelled attack data during training.

### Summary Table

| Track | Method | Features | F1 | ROC-AUC |
|-------|--------|----------|----|---------|
| Track 1 — Keystone | Transfer learning (CICIDS2017 → Keystone) | 24 session features | 0.9981 | 1.0000 |
| Track 2 — Nova | Autoencoder on sliding window log features | 14 window features | 0.9900 | 0.9995 |

### Reproducibility Note

All random seeds are fixed (`random_state=42`, TensorFlow seed not explicitly set — minor variation possible across hardware). Results should remain within ±0.002 of reported values across different machines.

## References

- [CICIDS2017 Dataset — University of New Brunswick](https://www.unb.ca/cic/datasets/ids-2017.html)
- [ParisaKalaki OpenStack Nova Logs — GitHub](https://github.com/ParisaKalaki/openstack-logs)
- [DevStack Documentation](https://docs.openstack.org/devstack/latest/)
- [TensorFlow Keras](https://www.tensorflow.org/guide/keras)
- [Scikit-learn Isolation Forest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html)

## PORTAL_METADATA

```portal
slug: security-monitoring-openstack-ml-anomaly-detection
title: Security Monitoring of OpenStack API Calls Using ML-Based Anomaly Detection
summary: Unsupervised autoencoder-based anomaly detection for OpenStack Keystone and Nova APIs. Track 1 uses transfer learning from CICIDS2017 achieving F1=0.9981 and ROC-AUC=1.0000. Track 2 detects Nova log anomalies achieving F1=0.9900 and ROC-AUC=0.9995.
startDate: 2025-02-15
endDate: 2025-04-30
repositoryUrl: https://github.com/NargizAghayeva/Security-Monitoring-of-OpenStack-API-Calls-Using-ML-based-Anomaly-Detection
logos:
```
