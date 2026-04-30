# CELL 1 — Import Libraries

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import (classification_report, confusion_matrix,
                              f1_score, precision_score, recall_score,
                              roc_auc_score, roc_curve)
import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Dense
from tensorflow.keras.callbacks import EarlyStopping
import warnings
warnings.filterwarnings('ignore')

print("✅ Libraries imported")
print(f"   TensorFlow: {tf.__version__}")
print(f"   NumPy:      {np.__version__}")
print(f"   Pandas:     {pd.__version__}")
```

# CELL 2 — Load Dataset

```python
df = pd.read_csv('cicids2017_cleaned.csv')

print(f"✅ Dataset loaded")
print(f"   Shape:   {df.shape}")
print(f"   Columns: {df.shape[1]}")
print(f"\nColumn list:")
for i, col in enumerate(df.columns):
    print(f"  {i+1:3d}. {col}")
```

# CELL 3 — Data Cleaning (Remove NaN and Invalid Values)

```python
print("Before cleaning:")
print(f"  Rows:      {df.shape[0]:,}")
print(f"  NaN count: {df.isna().sum().sum()}")
print(f"  Inf count: {np.isinf(df.select_dtypes(include=np.number)).sum().sum()}")

X_raw = df.drop('Attack Type', axis=1)
y_raw = df['Attack Type']

X_clean = X_raw.dropna()
y_clean = y_raw[X_clean.index]

mask = X_clean['Flow Duration'] >= 0
X_clean = X_clean[mask]
y_clean = y_clean[mask]

print(f"\nAfter cleaning:")
print(f"  Rows removed: {df.shape[0] - X_clean.shape[0]:,}")
print(f"  Rows kept:    {X_clean.shape[0]:,}")
```

# CELL 4 — Fix Labels (Binary: Normal=0, Attack=1)

```python
nan_mask = y_clean.notna()
X_clean = X_clean[nan_mask]
y_clean = y_clean[nan_mask]

y_binary = (y_clean != 'Normal Traffic').astype(int)

print("✅ Labels fixed")
print(f"\nLabel distribution:")
print(f"  Normal Traffic (0): {(y_binary==0).sum():>7,}  ({(y_binary==0).mean()*100:.1f}%)")
print(f"  Attack         (1): {(y_binary==1).sum():>7,}  ({(y_binary==1).mean()*100:.1f}%)")
print(f"\nAttack type breakdown:")
print(y_clean.value_counts())
```

# CELL 5 — EDA: Class Distribution

```python
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

attack_counts = y_clean.value_counts()
colors = ['steelblue', 'tomato', 'orange', 'green', 'purple']
attack_counts.plot(kind='bar', ax=axes[0], color=colors[:len(attack_counts)])
axes[0].set_title('Attack Type Distribution', fontsize=13)
axes[0].set_xlabel('Attack Type')
axes[0].set_ylabel('Count')
axes[0].tick_params(axis='x', rotation=30)
for i, v in enumerate(attack_counts):
    axes[0].text(i, v + 1000, f'{v:,}', ha='center', fontsize=9)

binary_counts = pd.Series({
    'Normal (0)': (y_binary == 0).sum(),
    'Attack (1)': (y_binary == 1).sum()
})
binary_counts.plot(kind='bar', ax=axes[1], color=['steelblue', 'tomato'])
axes[1].set_title('Binary: Normal vs Attack', fontsize=13)
axes[1].set_ylabel('Count')
axes[1].tick_params(axis='x', rotation=0)
for i, v in enumerate(binary_counts):
    axes[1].text(i, v + 1000, f'{v:,}', ha='center', fontsize=9)

plt.suptitle('CICIDS2017 — Class Distribution', fontsize=15, y=1.02)
plt.tight_layout()
plt.savefig('eda_01_class_distribution.png', dpi=150, bbox_inches='tight')
plt.show()
print("✅ Saved: eda_01_class_distribution.png")
```

# CELL 6 — EDA: Summary Statistics

```python
stats = X_clean.describe().T[['mean', 'std', 'min', 'max']]
stats['cv'] = (stats['std'] / stats['mean'].abs()).round(3)

print("Feature Summary Statistics:")
print(stats.round(3).to_string())
stats.to_csv('eda_summary_statistics.csv')
print("\n✅ Saved: eda_summary_statistics.csv")
```

# CELL 7 — EDA: Feature Distributions (Histogram)

```python
X_sample_eda = X_clean.sample(n=10000, random_state=42)

n_cols = 4
n_rows = int(np.ceil(X_clean.shape[1] / n_cols))

fig, axes = plt.subplots(n_rows, n_cols, figsize=(20, n_rows * 3))
axes = axes.flatten()

for i, col in enumerate(X_clean.columns):
    axes[i].hist(X_sample_eda[col], bins=50, color='steelblue', alpha=0.7, edgecolor='white')
    axes[i].set_title(col, fontsize=8)
    axes[i].tick_params(labelsize=7)

for j in range(i + 1, len(axes)):
    axes[j].set_visible(False)

plt.suptitle('CICIDS2017 — Feature Distributions (sample n=10,000)', fontsize=14)
plt.tight_layout()
plt.savefig('eda_02_feature_distributions.png', dpi=120, bbox_inches='tight')
plt.show()
print("✅ Saved: eda_02_feature_distributions.png")
```

# CELL 8 — EDA: Outlier Detection (Boxplot)

```python
X_log = np.log1p(X_sample_eda.clip(lower=0))

fig, axes = plt.subplots(n_rows, n_cols, figsize=(20, n_rows * 3))
axes = axes.flatten()

for i, col in enumerate(X_log.columns):
    axes[i].boxplot(X_log[col].dropna(), vert=True, patch_artist=True,
                    boxprops=dict(facecolor='steelblue', alpha=0.6))
    axes[i].set_title(col, fontsize=8)
    axes[i].tick_params(labelsize=7)

for j in range(i + 1, len(axes)):
    axes[j].set_visible(False)

plt.suptitle('CICIDS2017 — Outlier Detection (log scale, sample n=10,000)', fontsize=14)
plt.tight_layout()
plt.savefig('eda_03_outliers.png', dpi=120, bbox_inches='tight')
plt.show()
print("✅ Saved: eda_03_outliers.png")
```

# CELL 9 — Feature Selection Step 1: Variance Threshold

```python
variance = X_clean.var()
low_var_features = variance[variance < 0.01].index.tolist()

print(f"Low variance features (< 0.01):")
for f in low_var_features:
    print(f"  {f:<35} variance={variance[f]:.6f}")

print(f"\nDropping {len(low_var_features)} features: {low_var_features}")
X_var = X_clean.drop(columns=low_var_features)
print(f"Remaining: {X_var.shape[1]} features")
```

# CELL 10 — Feature Selection Step 2: Correlation Analysis

```python
corr_matrix = X_var.corr().abs()

plt.figure(figsize=(16, 14))
sns.heatmap(corr_matrix, cmap='coolwarm', center=0,
            xticklabels=True, yticklabels=True, linewidths=0.1)
plt.title('Feature Correlation Matrix (after variance filter)', fontsize=13)
plt.tight_layout()
plt.savefig('eda_04_correlation_matrix.png', dpi=150, bbox_inches='tight')
plt.show()

upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
high_corr_features = [col for col in upper.columns if any(upper[col] > 0.95)]

print(f"Highly correlated features (> 0.95) — to be dropped:")
for f in high_corr_features:
    partners = upper.index[upper[f] > 0.95].tolist()
    print(f"  DROP: {f:<35} ↔ {partners}")

X_corr = X_var.drop(columns=high_corr_features)
print(f"\nAfter correlation filter: {X_corr.shape[1]} features")
print("✅ Saved: eda_04_correlation_matrix.png")
```

# CELL 11 — Feature Selection Step 3: RF Importance

```python
y_aligned = y_binary[X_corr.index]

X_benign = X_corr[y_aligned == 0].sample(n=min(50000, (y_aligned==0).sum()), random_state=42)
X_attack = X_corr[y_aligned == 1].sample(n=min(50000, (y_aligned==1).sum()), random_state=42)
X_sample = pd.concat([X_benign, X_attack])
y_sample = pd.concat([y_aligned[X_benign.index], y_aligned[X_attack.index]])

print(f"Training RF on balanced sample: {X_sample.shape}")

rf = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
rf.fit(X_sample, y_sample)

importances = pd.Series(rf.feature_importances_, index=X_sample.columns)
importances = importances.sort_values(ascending=False)

threshold_val = 0.01
plt.figure(figsize=(10, 8))
importances[importances >= threshold_val].sort_values().plot(
    kind='barh', color='steelblue')
plt.axvline(x=threshold_val, color='red', linestyle='--', label=f'Threshold={threshold_val}')
plt.title('Feature Importance (Random Forest)', fontsize=13)
plt.xlabel('Importance Score')
plt.legend()
plt.tight_layout()
plt.savefig('eda_05_feature_importance.png', dpi=150, bbox_inches='tight')
plt.show()

selected_features = importances[importances >= threshold_val].index.tolist()
print(f"\nSelected features ({len(selected_features)}):")
for i, f in enumerate(selected_features):
    bar = '█' * int(importances[f] * 300)
    print(f"  {i+1:2d}. {f:<35} {importances[f]:.4f} {bar}")

X_final = X_corr[selected_features]
y_final = y_binary[X_final.index]
print(f"\n✅ Final dataset: {X_final.shape}")
print("✅ Saved: eda_05_feature_importance.png")
```

# CELL 12 — Train/Test Split

```python
X_normal = X_final[y_final == 0]
X_attack = X_final[y_final == 1]

print(f"Normal samples: {X_normal.shape[0]:,}")
print(f"Attack samples: {X_attack.shape[0]:,}")

X_train, X_test_normal = train_test_split(X_normal, test_size=0.2, random_state=42)

X_test = pd.concat([X_test_normal, X_attack])
y_test = pd.concat([
    pd.Series(np.zeros(len(X_test_normal)), index=X_test_normal.index),
    pd.Series(np.ones(len(X_attack)),       index=X_attack.index)
])

print(f"\nTrain set (normal only): {X_train.shape[0]:,}")
print(f"Test set  (normal):      {X_test_normal.shape[0]:,}")
print(f"Test set  (attack):      {X_attack.shape[0]:,}")
print(f"Test set  (total):       {X_test.shape[0]:,}")
```

# CELL 13 — Normalization (MinMax Scaling)

```python
scaler = MinMaxScaler()

X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled  = scaler.transform(X_test)

print("✅ Scaling complete")
print(f"   Train range: [{X_train_scaled.min():.3f}, {X_train_scaled.max():.3f}]")
print(f"   Test  range: [{X_test_scaled.min():.3f},  {X_test_scaled.max():.3f}]")

import joblib
joblib.dump(scaler, 'scaler.pkl')
print("✅ Saved: scaler.pkl")
```

# CELL 14 — Build Autoencoder Model

```python
input_dim = X_train_scaled.shape[1]
print(f"Input dimension: {input_dim} features")

inputs     = Input(shape=(input_dim,), name='input')
x          = Dense(16, activation='relu', name='encoder_1')(inputs)
x          = Dense(8,  activation='relu', name='encoder_2')(x)
bottleneck = Dense(4,  activation='relu', name='bottleneck')(x)
x          = Dense(8,  activation='relu', name='decoder_1')(bottleneck)
x          = Dense(16, activation='relu', name='decoder_2')(x)
outputs    = Dense(input_dim, activation='sigmoid', name='output')(x)

autoencoder = Model(inputs, outputs, name='Autoencoder')
autoencoder.compile(optimizer='adam', loss='mse')
autoencoder.summary()
```

# CELL 15 — Train Autoencoder

```python
early_stop = EarlyStopping(
    monitor='val_loss',
    patience=5,
    restore_best_weights=True,
    verbose=1
)

print("Training autoencoder on normal traffic only...")
history = autoencoder.fit(
    X_train_scaled, X_train_scaled,
    epochs=50,
    batch_size=256,
    validation_split=0.1,
    callbacks=[early_stop],
    verbose=1
)

plt.figure(figsize=(10, 4))
plt.plot(history.history['loss'],     label='Train Loss', color='steelblue')
plt.plot(history.history['val_loss'], label='Val Loss',   color='tomato')
plt.title('Autoencoder Training Loss', fontsize=13)
plt.xlabel('Epoch')
plt.ylabel('MSE Loss')
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig('training_loss.png', dpi=150)
plt.show()
print("✅ Saved: training_loss.png")

autoencoder.save('autoencoder_model.h5')
print("✅ Saved: autoencoder_model.h5")
```

# CELL 16 — Reconstruction Error Analysis

```python
X_test_pred = autoencoder.predict(X_test_scaled, verbose=0)
recon_errors = np.mean(np.power(X_test_scaled - X_test_pred, 2), axis=1)

errors_normal = recon_errors[y_test.values == 0]
errors_attack = recon_errors[y_test.values == 1]

print(f"Reconstruction Error — Normal Traffic:")
print(f"  Mean:   {errors_normal.mean():.6f}")
print(f"  Std:    {errors_normal.std():.6f}")
print(f"  Max:    {errors_normal.max():.6f}")
print(f"\nReconstruction Error — Attack Traffic:")
print(f"  Mean:   {errors_attack.mean():.6f}")
print(f"  Std:    {errors_attack.std():.6f}")
print(f"  Max:    {errors_attack.max():.6f}")

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

axes[0].hist(errors_normal, bins=100, alpha=0.6, color='steelblue', label='Normal', density=True)
axes[0].hist(errors_attack, bins=100, alpha=0.6, color='tomato',    label='Attack', density=True)
axes[0].set_title('Reconstruction Error Distribution', fontsize=13)
axes[0].set_xlabel('MSE')
axes[0].set_ylabel('Density')
axes[0].legend()
axes[0].set_yscale('log')

axes[1].boxplot([errors_normal, errors_attack],
                labels=['Normal', 'Attack'], patch_artist=True,
                boxprops=dict(facecolor='steelblue', alpha=0.6))
axes[1].set_title('Error Comparison (Boxplot)', fontsize=13)
axes[1].set_ylabel('Reconstruction Error (MSE)')
axes[1].set_yscale('log')

plt.tight_layout()
plt.savefig('reconstruction_error.png', dpi=150)
plt.show()
print("✅ Saved: reconstruction_error.png")
```

# CELL 17 — Threshold Selection

```python
thresholds = np.percentile(errors_normal, np.arange(80, 100, 1))
best_f1, best_threshold = 0, np.percentile(errors_normal, 95)

print("Threshold tuning:")
print(f"{'Percentile':>12} {'Threshold':>12} {'F1':>8} {'Precision':>10} {'Recall':>8}")
print("-" * 55)

for pct, thr in zip(np.arange(80, 100, 1), thresholds):
    y_pred = (recon_errors > thr).astype(int)
    f1   = f1_score(y_test, y_pred, zero_division=0)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec  = recall_score(y_test, y_pred, zero_division=0)
    print(f"  p{int(pct):>9} {thr:>12.6f} {f1:>8.4f} {prec:>10.4f} {rec:>8.4f}")
    if f1 > best_f1:
        best_f1 = f1
        best_threshold = thr

print(f"\n✅ Best threshold: {best_threshold:.6f}  (F1={best_f1:.4f})")
```

# CELL 18 — Final Evaluation

```python
y_pred_final = (recon_errors > best_threshold).astype(int)

print("=" * 55)
print("FINAL EVALUATION RESULTS")
print("=" * 55)
print(classification_report(y_test, y_pred_final, target_names=['Normal', 'Attack']))

f1   = f1_score(y_test, y_pred_final)
prec = precision_score(y_test, y_pred_final)
rec  = recall_score(y_test, y_pred_final)
auc  = roc_auc_score(y_test, recon_errors)

print(f"F1 Score:   {f1:.4f}")
print(f"Precision:  {prec:.4f}")
print(f"Recall:     {rec:.4f}")
print(f"ROC-AUC:    {auc:.4f}")

cm = confusion_matrix(y_test, y_pred_final)
plt.figure(figsize=(7, 5))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=['Normal', 'Attack'],
            yticklabels=['Normal', 'Attack'])
plt.title(f'Confusion Matrix (threshold={best_threshold:.4f})', fontsize=13)
plt.ylabel('True Label')
plt.xlabel('Predicted Label')
plt.tight_layout()
plt.savefig('confusion_matrix.png', dpi=150)
plt.show()

fpr, tpr, _ = roc_curve(y_test, recon_errors)
plt.figure(figsize=(7, 5))
plt.plot(fpr, tpr, color='steelblue', lw=2, label=f'ROC AUC = {auc:.4f}')
plt.plot([0, 1], [0, 1], color='gray', linestyle='--')
plt.title('ROC Curve — Autoencoder Anomaly Detection', fontsize=13)
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig('roc_curve.png', dpi=150)
plt.show()

print("✅ Saved: confusion_matrix.png")
print("✅ Saved: roc_curve.png")
```

# CELL 19 — Save Feature List for Phase 2 (Keystone Mapping)

```python
print(f"selected_features count: {len(selected_features)}")
print(f"Features: {selected_features}")
```

```python
keystone_mapping = {
    'Packet Length Mean':           'avg_packet_bytes',
    'Destination Port':             'endpoint_category',
    'Bwd Packet Length Max':        'response_bytes_max',
    'Packet Length Variance':       'packet_bytes_variance',
    'Max Packet Length':            'response_bytes_max2',
    'Fwd Packet Length Max':        'request_bytes_max',
    'Init_Win_bytes_forward':       'first_request_bytes',
    'Init_Win_bytes_backward':      'first_response_bytes',
    'Min Packet Length':            'min_packet_bytes',
    'Total Length of Fwd Packets':  'request_bytes_total',
    'Fwd Packet Length Min':        'request_bytes_min',
    'Fwd Header Length':            'request_header_size',
    'Bwd Packet Length Min':        'response_bytes_min',
    'Fwd Packet Length Mean':       'request_bytes_mean',
    'Total Fwd Packets':            'total_requests_session',
    'Flow IAT Std':                 'inter_request_time_std',
    'Bwd Header Length':            'response_header_size',
    'Flow IAT Mean':                'inter_request_time_mean',
    'Fwd IAT Mean':                 'fwd_inter_request_time_mean',
    'Flow Bytes/s':                 'bytes_per_sec',
    'PSH Flag Count':               'post_method_count',
    'Flow Packets/s':               'req_rate_per_sec',
    'Flow IAT Max':                 'max_time_between_requests',
    'Fwd IAT Min':                  'min_inter_request_time',
    'Flow Duration':                'session_duration_ms',
    'Bwd Packets/s':                'response_rate_per_sec',
    'ACK Flag Count':               'success_count',
    'Bwd Packet Length Mean':       'response_bytes_mean',
}

feature_export = pd.DataFrame({
    'feature_name':     selected_features,
    'importance':       [round(importances[f], 4) for f in selected_features],
    'keystone_mapping': [keystone_mapping[f] for f in selected_features],
})

feature_export.to_csv('phase2_feature_mapping.csv', index=False)
print("✅ Saved: phase2_feature_mapping.csv")
print(f"\nTotal features: {len(selected_features)}")
print(feature_export.to_string(index=False))
```

# CELL 20 — Phase 1 Summary

```python
print("\n" + "=" * 55)
print("PHASE 1 COMPLETE — SUMMARY")
print("=" * 55)
print(f"Dataset:          CICIDS2017 Cleaned & Preprocessed")
print(f"Original features:{52}")
print(f"After var filter: {52 - len(low_var_features)}")
print(f"After corr filter:{52 - len(low_var_features) - len(high_corr_features)}")
print(f"After RF filter:  {len(selected_features)}  ← final")
print(f"Train samples:    {X_train.shape[0]:,}  (normal only)")
print(f"Test samples:     {X_test.shape[0]:,}  (normal + attack)")
print(f"")
print(f"Model:            Autoencoder ({input_dim}→16→8→4→8→16→{input_dim})")
print(f"Threshold:        {best_threshold:.6f}")
print(f"F1 Score:         {f1:.4f}")
print(f"Precision:        {prec:.4f}")
print(f"Recall:           {rec:.4f}")
print(f"ROC-AUC:          {auc:.4f}")
print(f"")
print(f"Saved files:")
print(f"  autoencoder_model.h5")
print(f"  scaler.pkl")
print(f"  phase2_feature_mapping.csv")
print(f"  eda_01_class_distribution.png")
print(f"  eda_02_feature_distributions.png")
print(f"  eda_03_outliers.png")
print(f"  eda_04_correlation_matrix.png")
print(f"  eda_05_feature_importance.png")
print(f"  training_loss.png")
print(f"  reconstruction_error.png")
print(f"  confusion_matrix.png")
print(f"  roc_curve.png")
print("=" * 55)
print("→ Next: Phase 2 — Keystone Feature Mapping & Fine-tuning")
```
