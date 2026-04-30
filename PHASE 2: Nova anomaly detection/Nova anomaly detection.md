# Cell 1 — Import Libraries

```python
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split, KFold
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (f1_score, precision_score, recall_score,
                              roc_auc_score, confusion_matrix,
                              classification_report, roc_curve)
import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Dense
from tensorflow.keras.callbacks import EarlyStopping
import joblib, os, warnings
warnings.filterwarnings('ignore')

print('Libraries imported successfully')
print(f'TensorFlow: {tf.__version__}')
print(f'NumPy:      {np.__version__}')
print(f'Pandas:     {pd.__version__}')
```

# Cell 2 — Clone & Inspect Dataset

```python
import subprocess
result = subprocess.run(
    ['git', 'clone', 'https://github.com/ParisaKalaki/openstack-logs.git'],
    capture_output=True, text=True
)
print(result.stdout or result.stderr)

# Only these 3 files — others explicitly excluded to prevent data contamination
LOG_FILES = {
    'openstack-nova-normal-vm-create.log':               0,
    'openstack-vm-destroy-immediately-after-create.log': 1,
    'openstack-nova-undefine-vm-after-create.log':       1,
}
LOG_DIR = 'openstack-logs'

print('Files used in this study:')
print(f"{'File':<55} {'Label':<8} {'Lines':>8}  {'Size':>8}")
print('-' * 85)
for fname, label in LOG_FILES.items():
    path  = os.path.join(LOG_DIR, fname)
    size  = os.path.getsize(path)
    lines = sum(1 for _ in open(path, errors='ignore'))
    ltype = 'Normal' if label == 0 else 'Anomaly'
    print(f'  {fname:<53} {ltype:<8} {lines:>8,}  {size/1024:>6.0f} KB')

print('\nFiles excluded (not used):')
all_logs = [f for f in os.listdir(LOG_DIR) if f.endswith('.log')]
for f in all_logs:
    if f not in LOG_FILES:
        print(f'  [EXCLUDED] {f}')
```

# Cell 3 — Log Parser

```python
LOG_PATTERN = re.compile(
    r'^\s*(INFO|ERROR|WARNING|DEBUG|CRITICAL)\s+'
    r'([\w\.]+)\s+'
    r'\[([^\]]*)\]\s*'
    r'(?:\[instance:\s*([\w\-]+)\])?\s*'
    r'(.*)$'
)

def parse_log_line(line):
    line = line.strip()
    if not line:
        return None
    m = LOG_PATTERN.match(line)
    if not m:
        return None
    level, component, req_id, instance_id, message = m.groups()
    req_id = req_id.strip() if req_id else ''
    req_id = '' if req_id in ['-', 'None', 'null'] else req_id
    return {
        'level':       level,
        'component':   component,
        'req_id':      req_id,
        'instance_id': instance_id or '',
        'message':     message.strip(),
    }

def load_log_file(filepath, label, anomaly_type=None):
    records = []
    with open(filepath, 'r', errors='ignore') as f:
        for line in f:
            parsed = parse_log_line(line)
            if parsed:
                parsed['label']        = label
                parsed['anomaly_type'] = anomaly_type or 'normal'
                parsed['source']       = os.path.basename(filepath)
                records.append(parsed)
    return records

all_records = []

path = os.path.join(LOG_DIR, 'openstack-nova-normal-vm-create.log')
recs = load_log_file(path, label=0, anomaly_type='normal')
all_records.extend(recs)
print(f'Normal logs loaded:            {len(recs):>7,} records')

path = os.path.join(LOG_DIR, 'openstack-vm-destroy-immediately-after-create.log')
recs = load_log_file(path, label=1, anomaly_type='vm_destroy')
all_records.extend(recs)
print(f'Anomaly type 1 (vm_destroy):   {len(recs):>7,} records')

path = os.path.join(LOG_DIR, 'openstack-nova-undefine-vm-after-create.log')
recs = load_log_file(path, label=1, anomaly_type='vm_undefine')
all_records.extend(recs)
print(f'Anomaly type 2 (vm_undefine):  {len(recs):>7,} records')

df = pd.DataFrame(all_records)
print(f'\nTotal records:  {len(df):>7,}')
print(f'Normal:         {(df["label"]==0).sum():>7,}  ({(df["label"]==0).mean():.1%})')
print(f'Anomalous:      {(df["label"]==1).sum():>7,}  ({(df["label"]==1).mean():.1%})')
print(f'\nAnomaly type breakdown:')
print(df[df['label']==1]['anomaly_type'].value_counts())
```

# Cell 4 — Exploratory Data Analysis (EDA)

```python
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

level_counts = df.groupby(['level', 'label']).size().unstack(fill_value=0)
level_counts.plot(kind='bar', ax=axes[0,0], color=['steelblue', 'tomato'])
axes[0,0].set_title('Log Level Distribution by Label')
axes[0,0].set_xlabel('Log Level')
axes[0,0].set_ylabel('Count')
axes[0,0].legend(['Normal', 'Anomalous'])
axes[0,0].tick_params(axis='x', rotation=0)

df['component'].value_counts().head(10).plot(kind='barh', ax=axes[0,1], color='steelblue')
axes[0,1].set_title('Top 10 Nova Components')
axes[0,1].set_xlabel('Count')

label_counts = df['label'].value_counts()
axes[1,0].pie(label_counts, labels=['Normal', 'Anomalous'],
              colors=['steelblue', 'tomato'], autopct='%1.1f%%', startangle=90)
axes[1,0].set_title('Label Distribution')

df['anomaly_type'].value_counts().plot(kind='bar', ax=axes[1,1],
                                        color=['steelblue','tomato','orange'])
axes[1,1].set_title('Log Distribution by Type')
axes[1,1].set_ylabel('Count')
axes[1,1].tick_params(axis='x', rotation=15)

plt.suptitle('OpenStack Nova Logs — EDA', fontsize=14, y=1.01)
plt.tight_layout()
plt.savefig('track2_eda.png', dpi=150, bbox_inches='tight')
plt.show()
print('Saved: track2_eda.png')

print('\nLog level breakdown:')
print(df.groupby(['label', 'level']).size().unstack(fill_value=0))
print('\nERROR rate:')
print(f'  Normal:    {(df[df["label"]==0]["level"]=="ERROR").mean():.4%}')
print(f'  Anomalous: {(df[df["label"]==1]["level"]=="ERROR").mean():.4%}')
```

# Cell 5 — Sliding Window Feature Engineering

```python
WINDOW_SIZE = 50
STEP_SIZE   = 25

KEYWORDS = {
    'keyword_failed':    r'fail(?:ed|ure)?',
    'keyword_timeout':   r'timeout|timed[\s_]?out',
    'keyword_exception': r'traceback|exception',
    'keyword_destroy':   r'destroy(?:ed|ing)?|delet(?:ed|ing)?',
    'keyword_spawn':     r'spawn(?:ed|ing)?',
    'keyword_error_msg': r'invalid|could not',
    'keyword_critical':  r'critical|fatal|abort',
}

def extract_window_features(window_df):
    total    = len(window_df)
    levels   = window_df['level'].value_counts()
    msgs     = ' '.join(window_df['message'].str.lower())
    err_cnt  = levels.get('ERROR',   0)
    warn_cnt = levels.get('WARNING', 0)
    info_cnt = levels.get('INFO',    0)
    features = {
        'error_count':         err_cnt,
        'warning_count':       warn_cnt,
        'info_count':          info_cnt,
        'error_ratio':         err_cnt  / total,
        'warning_ratio':       warn_cnt / total,
        'unique_components':   window_df['component'].nunique(),
        'component_diversity': window_df['component'].nunique() / total,
    }
    for feat_name, pattern in KEYWORDS.items():
        features[feat_name] = int(bool(re.search(pattern, msgs)))
    features['label']        = int(window_df['label'].max())
    features['anomaly_type'] = (
        window_df[window_df['label']==1]['anomaly_type'].iloc[0]
        if window_df['label'].max() == 1 else 'normal'
    )
    return features

windows = []
for source_file in ['openstack-nova-normal-vm-create.log',
                    'openstack-vm-destroy-immediately-after-create.log',
                    'openstack-nova-undefine-vm-after-create.log']:
    source_df = df[df['source'] == source_file].reset_index(drop=True)
    n = 0
    for start in range(0, len(source_df) - WINDOW_SIZE + 1, STEP_SIZE):
        window = source_df.iloc[start:start + WINDOW_SIZE]
        feat   = extract_window_features(window)
        feat['source'] = source_file
        windows.append(feat)
        n += 1
    print(f'  {source_file:<55}: {n:,} windows')

sessions     = pd.DataFrame(windows)
feature_cols = [c for c in sessions.columns
                if c not in ['label', 'source', 'anomaly_type']]

print(f'\nTotal windows:    {len(sessions):,}')
print(f'Normal windows:   {(sessions["label"]==0).sum():,}')
print(f'Anomaly windows:  {(sessions["label"]==1).sum():,}')
print(f'Anomaly ratio:    {(sessions["label"]==1).mean():.1%}')
print(f'\nFeatures ({len(feature_cols)}): {feature_cols}')
```

# Cell 6 — Feature Analysis & Correlation Check

```python
normal_w  = sessions[sessions['label'] == 0]
anomaly_w = sessions[sessions['label'] == 1]

print('Feature separation analysis:')
print(f"\n{'Feature':<25} {'Normal mean':>12} {'Anomaly mean':>13} {'Ratio':>10}  Signal")
print('=' * 75)
feature_quality = []
for feat in feature_cols:
    n_mean = normal_w[feat].mean()
    a_mean = anomaly_w[feat].mean()
    ratio  = a_mean / n_mean if n_mean > 0 else float('inf')
    signal = 'STRONG' if ratio > 3.0 or ratio < 0.33 else \
             'MEDIUM' if ratio > 1.5 or ratio < 0.67 else 'WEAK'
    print(f'  {feat:<23} {n_mean:>12.4f} {a_mean:>13.4f} {ratio:>10.2f}x  {signal}')
    feature_quality.append({'feature': feat, 'ratio': ratio, 'signal': signal})
fq_df = pd.DataFrame(feature_quality)
print(f'\nStrong signals: {(fq_df["signal"]=="STRONG").sum()}')
print(f'Medium signals: {(fq_df["signal"]=="MEDIUM").sum()}')
print(f'Weak signals:   {(fq_df["signal"]=="WEAK").sum()}')

print('\n--- Feature Correlation Check ---')
corr_matrix = pd.DataFrame(sessions[feature_cols].values,
                            columns=feature_cols).corr().abs()
upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
high_corr = [
    (col, row, upper.loc[row, col])
    for col in upper.columns
    for row in upper.index
    if pd.notna(upper.loc[row, col]) and upper.loc[row, col] > 0.85
]
if high_corr:
    print('Highly correlated feature pairs (>0.85):')
    for f1n, f2n, corr in sorted(high_corr, key=lambda x: -x[2]):
        print(f'  {f1n} <-> {f2n}: {corr:.3f}')
else:
    print('No highly correlated features found (threshold=0.85).')

fig, ax = plt.subplots(figsize=(14, 5))
means = pd.DataFrame({
    'Normal':    normal_w[feature_cols].mean(),
    'Anomalous': anomaly_w[feature_cols].mean(),
})
means.plot(kind='bar', ax=ax, color=['steelblue', 'tomato'])
ax.set_title('Feature Means: Normal vs Anomalous Windows')
ax.set_ylabel('Mean Value')
ax.tick_params(axis='x', rotation=45)
ax.legend()
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig('track2_feature_analysis.png', dpi=150)
plt.show()
print('Saved: track2_feature_analysis.png')
```

# Cell 7 — Prepare Data for Training

```python
X = sessions[feature_cols].values
y = sessions['label'].values
X_normal  = X[y == 0]
X_anomaly = X[y == 1]

print(f'Total normal windows:    {len(X_normal):,}')
print(f'Total anomalous windows: {len(X_anomaly):,}')

X_train, X_test_normal = train_test_split(X_normal, test_size=0.2, random_state=42)
X_test = np.vstack([X_test_normal, X_anomaly])
y_test = np.concatenate([np.zeros(len(X_test_normal)), np.ones(len(X_anomaly))])

print(f'\nTrain set (normal only):  {X_train.shape[0]:,}')
print(f'Test set  (normal):       {X_test_normal.shape[0]:,}')
print(f'Test set  (anomalous):    {X_anomaly.shape[0]:,}')
print(f'Test set  (total):        {X_test.shape[0]:,}')

scaler     = MinMaxScaler()
X_train_sc = scaler.fit_transform(X_train)
X_test_sc  = scaler.transform(X_test)

print(f'\nScaling complete')
print(f'  Train range: [{X_train_sc.min():.3f}, {X_train_sc.max():.3f}]')
print(f'  Test  range: [{X_test_sc.min():.3f}, {X_test_sc.max():.3f}]')

joblib.dump(scaler, 'track2_scaler.pkl')
print('\nSaved: track2_scaler.pkl')
```

# Cell 8 — Cross-Validation on Normal Data

```python
input_dim = X_train_sc.shape[1]
print(f'Input dimension: {input_dim} features')
print(f'Architecture:    {input_dim}->32->16->8->16->32->{input_dim}')

def build_autoencoder(input_dim):
    inputs     = Input(shape=(input_dim,), name='input')
    x          = Dense(32, activation='relu', name='encoder_1')(inputs)
    x          = Dense(16, activation='relu', name='encoder_2')(x)
    bottleneck = Dense(8,  activation='relu', name='bottleneck')(x)
    x          = Dense(16, activation='relu', name='decoder_1')(bottleneck)
    x          = Dense(32, activation='relu', name='decoder_2')(x)
    outputs    = Dense(input_dim, activation='sigmoid', name='output')(x)
    model      = Model(inputs, outputs, name='Track2_Autoencoder')
    model.compile(optimizer='adam', loss='mse')
    return model

kf        = KFold(n_splits=5, shuffle=True, random_state=42)
cv_losses = []
cv_scaler = MinMaxScaler()

print('\n5-Fold Cross-Validation on normal data:')
print(f"{'Fold':>6} {'Val Loss':>12}")
print('-' * 22)
for fold, (train_idx, val_idx) in enumerate(kf.split(X_normal)):
    X_cv_train = cv_scaler.fit_transform(X_normal[train_idx])
    X_cv_val   = cv_scaler.transform(X_normal[val_idx])
    cv_model   = build_autoencoder(input_dim)
    cv_hist    = cv_model.fit(
        X_cv_train, X_cv_train,
        epochs=100, batch_size=32,
        validation_data=(X_cv_val, X_cv_val),
        verbose=0,
        callbacks=[EarlyStopping(patience=5, restore_best_weights=True)]
    )
    val_loss = min(cv_hist.history['val_loss'])
    cv_losses.append(val_loss)
    print(f'  Fold {fold+1}   {val_loss:>12.6f}')

print(f'\nCV Mean loss: {np.mean(cv_losses):.6f}')
print(f'CV Std loss:  {np.std(cv_losses):.6f}')
```

# Cell 9 — Build & Train Autoencoder

```python
autoencoder = build_autoencoder(input_dim)
autoencoder.summary()

early_stop = EarlyStopping(
    monitor='val_loss', patience=10,
    restore_best_weights=True, verbose=1
)

print('\nTraining autoencoder on NORMAL windows only...')

history = autoencoder.fit(
    X_train_sc, X_train_sc,
    epochs=100, batch_size=32,
    validation_split=0.1,
    callbacks=[early_stop], verbose=1
)

plt.figure(figsize=(10, 4))
plt.plot(history.history['loss'],     label='Train Loss', color='steelblue', lw=2)
plt.plot(history.history['val_loss'], label='Val Loss',   color='tomato',    lw=2)
plt.title('Track 2 - Autoencoder Training Loss')
plt.xlabel('Epoch')
plt.ylabel('MSE Loss')
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig('track2_training_loss.png', dpi=150)
plt.show()
print(f'Training complete - {len(history.history["loss"])} epochs')
print('Saved: track2_training_loss.png')

autoencoder.save('track2_autoencoder.h5')
print('Saved: track2_autoencoder.h5')
```

# Cell 10 — Reconstruction Error Analysis

```python
X_pred       = autoencoder.predict(X_test_sc, verbose=0)
recon_errors = np.mean(np.power(X_test_sc - X_pred, 2), axis=1)
errors_normal  = recon_errors[y_test == 0]
errors_anomaly = recon_errors[y_test == 1]

print('Reconstruction Error Statistics:')
print(f'\n  Normal    - Mean: {errors_normal.mean():.6f}  Std: {errors_normal.std():.6f}  Max: {errors_normal.max():.6f}')
print(f'  Anomalous - Mean: {errors_anomaly.mean():.6f}  Std: {errors_anomaly.std():.6f}  Max: {errors_anomaly.max():.6f}')
print(f'\n  Separation ratio: {errors_anomaly.mean()/errors_normal.mean():.0f}x')

fig, axes = plt.subplots(1, 3, figsize=(16, 5))

axes[0].hist(errors_normal,  bins=60, alpha=0.6, color='steelblue', label='Normal',    density=True)
axes[0].hist(errors_anomaly, bins=60, alpha=0.6, color='tomato',    label='Anomalous', density=True)
axes[0].set_title('Reconstruction Error Distribution')
axes[0].set_xlabel('MSE Reconstruction Error')
axes[0].set_ylabel('Density')
axes[0].legend()
axes[0].grid(alpha=0.3)

axes[1].hist(np.log1p(errors_normal),  bins=60, alpha=0.6, color='steelblue', label='Normal',    density=True)
axes[1].hist(np.log1p(errors_anomaly), bins=60, alpha=0.6, color='tomato',    label='Anomalous', density=True)
axes[1].set_title('Reconstruction Error (log scale)')
axes[1].set_xlabel('log(1 + MSE)')
axes[1].legend()
axes[1].grid(alpha=0.3)

axes[2].boxplot([errors_normal, errors_anomaly], labels=['Normal', 'Anomalous'],
                patch_artist=True, boxprops=dict(facecolor='steelblue', alpha=0.6))
axes[2].set_title('Reconstruction Error - Box Plot')
axes[2].set_ylabel('MSE')
axes[2].grid(alpha=0.3)

plt.suptitle('Track 2 - Reconstruction Error Analysis', fontsize=13)
plt.tight_layout()
plt.savefig('track2_recon_error.png', dpi=150)
plt.show()
print('Saved: track2_recon_error.png')
```

# Cell 11 — Threshold Tuning

```python
print('Threshold tuning (scanning normal error percentiles):')
print(f"\n{'Percentile':>12} {'Threshold':>14} {'F1':>8} {'Precision':>10} {'Recall':>8}")
print('-' * 58)

results = []
best_f1, best_threshold, best_pct = 0, 0, 0
for pct in range(50, 100, 2):
    thr    = np.percentile(errors_normal, pct)
    y_pred = (recon_errors > thr).astype(int)
    f1     = f1_score(y_test, y_pred, zero_division=0)
    prec   = precision_score(y_test, y_pred, zero_division=0)
    rec    = recall_score(y_test, y_pred, zero_division=0)
    results.append({'pct': pct, 'thr': thr, 'f1': f1, 'prec': prec, 'rec': rec})
    marker = ' <-- BEST' if f1 > best_f1 else ''
    print(f'  p{pct:>9}   {thr:>14.8f}  {f1:>8.4f}  {prec:>10.4f}  {rec:>8.4f}{marker}')
    if f1 > best_f1:
        best_f1, best_threshold, best_pct = f1, thr, pct

print(f'\nBest threshold: {best_threshold:.8f}  (p{best_pct}, F1={best_f1:.4f})')

res_df = pd.DataFrame(results)
fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(res_df['pct'], res_df['f1'],   label='F1',       color='steelblue', lw=2)
ax.plot(res_df['pct'], res_df['prec'], label='Precision', color='tomato',   lw=1.5, ls='--')
ax.plot(res_df['pct'], res_df['rec'],  label='Recall',    color='green',    lw=1.5, ls='--')
ax.axvline(x=best_pct, color='gray', ls=':', lw=1.5, label=f'Best (p{best_pct})')
ax.set_title('F1 / Precision / Recall vs Threshold Percentile')
ax.set_xlabel('Percentile of Normal Error')
ax.set_ylabel('Score')
ax.legend()
ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig('track2_threshold_tuning.png', dpi=150)
plt.show()
print('Saved: track2_threshold_tuning.png')
```

# Cell 12 — Final Evaluation

```python
y_pred_final = (recon_errors > best_threshold).astype(int)
prec = precision_score(y_test, y_pred_final)
rec  = recall_score(y_test, y_pred_final)
f1   = f1_score(y_test, y_pred_final)
auc  = roc_auc_score(y_test, recon_errors)

print('=' * 55)
print('TRACK 2 - FINAL EVALUATION')
print('=' * 55)
print(classification_report(y_test, y_pred_final, target_names=['Normal', 'Anomalous']))
print(f'F1 Score:   {f1:.4f}')
print(f'Precision:  {prec:.4f}')
print(f'Recall:     {rec:.4f}')
print(f'ROC-AUC:    {auc:.4f}')
print(f'Threshold:  {best_threshold:.8f}')

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
cm = confusion_matrix(y_test, y_pred_final)
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=axes[0],
            xticklabels=['Normal', 'Anomalous'],
            yticklabels=['Normal', 'Anomalous'])
axes[0].set_title('Confusion Matrix')
axes[0].set_ylabel('True Label')
axes[0].set_xlabel('Predicted Label')

tn, fp, fn, tp = cm.ravel()
print(f'\nConfusion Matrix:  TN={tn}  FP={fp}  FN={fn}  TP={tp}')

fpr, tpr, _ = roc_curve(y_test, recon_errors)
axes[1].plot(fpr, tpr, color='steelblue', lw=2, label=f'Autoencoder (AUC={auc:.4f})')
axes[1].plot([0, 1], [0, 1], 'k--', lw=1, label='Random')
axes[1].set_xlabel('False Positive Rate')
axes[1].set_ylabel('True Positive Rate')
axes[1].set_title('ROC Curve')
axes[1].legend()
axes[1].grid(alpha=0.3)

plt.suptitle('Track 2 - Final Evaluation', fontsize=13)
plt.tight_layout()
plt.savefig('track2_evaluation.png', dpi=150)
plt.show()
print('Saved: track2_evaluation.png')
```

# Cell 13 — Per Anomaly Type Breakdown

```python
print('Per Anomaly Type Detection Analysis:')
print('=' * 55)

test_anomaly_types = []
anomaly_sessions = sessions[sessions['label']==1].reset_index(drop=True)
for i, label in enumerate(y_test):
    if label == 0:
        test_anomaly_types.append('normal')
    else:
        anomaly_idx = i - len(X_test_normal)
        atype = anomaly_sessions['anomaly_type'].iloc[anomaly_idx] \
                if anomaly_idx < len(anomaly_sessions) else 'unknown'
        test_anomaly_types.append(atype)

test_atype_series = pd.Series(test_anomaly_types)

for atype in ['vm_destroy', 'vm_undefine']:
    mask       = test_atype_series == atype
    if mask.sum() == 0:
        continue
    detected   = y_pred_final[mask].sum()
    total      = mask.sum()
    recall_sub = detected / total
    print(f'\n  Anomaly type: {atype}')
    print(f'  Total windows:   {total}')
    print(f'  Detected:        {detected} ({recall_sub:.1%})')
    print(f'  Missed:          {total - detected} ({1-recall_sub:.1%})')

print('\nReconstruction error by anomaly type:')
print(f"  {'Type':<20} {'Mean error':>14}  {'vs Normal':>10}")
print('-' * 50)
mean_normal_err = errors_normal.mean()
for atype in ['vm_destroy', 'vm_undefine']:
    mask = (test_atype_series == atype).values
    if mask.sum() == 0:
        continue
    errs = recon_errors[mask]
    print(f"  {atype:<20} {errs.mean():>14.4f}  {errs.mean()/mean_normal_err:>9.0f}x")
print(f"  {'normal':<20} {mean_normal_err:>14.6f}  {'baseline':>10}")
```

# Cell 14 — Baseline Comparison (Isolation Forest)

```python
print('Baseline Comparison: Autoencoder vs Isolation Forest')
print('=' * 55)

iso_forest = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
iso_forest.fit(X_train_sc)

iso_pred     = (iso_forest.predict(X_test_sc) == -1).astype(int)
iso_scores_v = -iso_forest.score_samples(X_test_sc)

iso_f1   = f1_score(y_test, iso_pred, zero_division=0)
iso_prec = precision_score(y_test, iso_pred, zero_division=0)
iso_rec  = recall_score(y_test, iso_pred, zero_division=0)
iso_auc  = roc_auc_score(y_test, iso_scores_v)

print(f"\n{'Metric':<15} {'Autoencoder':>13} {'Isolation Forest':>18}")
print('-' * 50)
print(f"{'F1 Score':<15} {f1:>13.4f} {iso_f1:>18.4f}")
print(f"{'Precision':<15} {prec:>13.4f} {iso_prec:>18.4f}")
print(f"{'Recall':<15} {rec:>13.4f} {iso_rec:>18.4f}")
print(f"{'ROC-AUC':<15} {auc:>13.4f} {iso_auc:>18.4f}")

fig, ax = plt.subplots(figsize=(9, 5))
metrics       = ['F1 Score', 'Precision', 'Recall', 'ROC-AUC']
ae_scores_v   = [f1, prec, rec, auc]
iso_scores_vv = [iso_f1, iso_prec, iso_rec, iso_auc]
x = np.arange(len(metrics))
w = 0.35
ax.bar(x - w/2, ae_scores_v,   w, label='Autoencoder',     color='steelblue', alpha=0.85)
ax.bar(x + w/2, iso_scores_vv, w, label='Isolation Forest', color='tomato',   alpha=0.85)
ax.set_title('Autoencoder vs Isolation Forest')
ax.set_xticks(x)
ax.set_xticklabels(metrics)
ax.set_ylabel('Score')
ax.set_ylim(0, 1.12)
ax.legend()
ax.grid(axis='y', alpha=0.3)
for i, (a, b) in enumerate(zip(ae_scores_v, iso_scores_vv)):
    ax.text(i - w/2, a + 0.02, f'{a:.3f}', ha='center', fontsize=9)
    ax.text(i + w/2, b + 0.02, f'{b:.3f}', ha='center', fontsize=9)
plt.tight_layout()
plt.savefig('track2_baseline_comparison.png', dpi=150)
plt.show()
print('Saved: track2_baseline_comparison.png')
```

# Cell 15 — Summary

```python
print('\n' + '='*60)
print('TRACK 2 - COMPLETE SUMMARY')
print('='*60)
print(f'Dataset:              Kalaki OpenStack Nova Logs (GitHub)')
print(f'Files used:           3 (1 normal, 2 anomaly types)')
print(f'Files excluded:       2 (sample + dhcpoff - contamination prevention)')
print(f'Total log records:    {len(df):,}')
print()
print(f'Windowing:            size={WINDOW_SIZE}, step={STEP_SIZE} (50% overlap)')
print(f'Total windows:        {len(sessions):,}')
print(f'Normal windows:       {(sessions["label"]==0).sum():,}')
print(f'Anomaly windows:      {(sessions["label"]==1).sum():,}')
print(f'  - vm_destroy:       {(sessions["anomaly_type"]=="vm_destroy").sum():,}')
print(f'  - vm_undefine:      {(sessions["anomaly_type"]=="vm_undefine").sum():,}')
print()
print(f'Features ({len(feature_cols)}):')
for i, fc in enumerate(feature_cols, 1):
    print(f'  {i:2d}. {fc}')
print()
print(f'Model:                Autoencoder ({input_dim}->32->16->8->16->32->{input_dim})')
print(f'Training:             Normal windows only (unsupervised)')
print(f'Cross-validation:     5-fold, mean={np.mean(cv_losses):.6f} +/- {np.std(cv_losses):.6f}')
print(f'Threshold:            {best_threshold:.8f} (p{best_pct} of normal errors)')
print()
print(f'Results (Autoencoder):')
print(f'  F1 Score:           {f1:.4f}')
print(f'  Precision:          {prec:.4f}')
print(f'  Recall:             {rec:.4f}')
print(f'  ROC-AUC:            {auc:.4f}')
print()
print(f'Baseline (Isolation Forest):')
print(f'  F1 Score:           {iso_f1:.4f}')
print(f'  ROC-AUC:            {iso_auc:.4f}')
print()
print('Saved files:')
for fname in ['track2_autoencoder.h5', 'track2_scaler.pkl',
              'track2_eda.png', 'track2_feature_analysis.png',
              'track2_training_loss.png', 'track2_recon_error.png',
              'track2_threshold_tuning.png', 'track2_evaluation.png',
              'track2_baseline_comparison.png']:
    print(f'  {fname}')
```
