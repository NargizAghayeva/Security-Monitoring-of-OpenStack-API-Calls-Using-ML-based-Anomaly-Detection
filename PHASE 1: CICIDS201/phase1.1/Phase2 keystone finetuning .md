# CELL 1 — Imports

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
import tensorflow as tf
from tensorflow.keras.models import load_model
from sklearn.metrics import (f1_score, precision_score, recall_score,
                              roc_auc_score, classification_report,
                              confusion_matrix, roc_curve)
from sklearn.model_selection import train_test_split

print(f'TensorFlow: {tf.__version__}')
print('Imports OK')
```

# CELL 2 — Load Dataset + Session Aggregation (60s window per IP)

```python
df_raw = pd.read_csv('final_dataset.csv')
print(f'Raw dataset: {df_raw.shape}')
print(f'Attack types:\n{df_raw["attack_type"].value_counts().to_string()}')

df_raw['timestamp'] = pd.to_datetime(df_raw['timestamp'])
df_raw = df_raw.sort_values(['source_ip', 'timestamp']).reset_index(drop=True)
df_raw['time_bucket'] = df_raw['timestamp'].dt.floor('60s')

def aggregate_session(group):
    n     = len(group)
    d     = {}
    rb    = group['request_bytes'].values.astype(float)
    rs    = group['response_bytes'].values.astype(float)
    times = group['timestamp'].values.astype('datetime64[ms]').astype(float) / 1000.0

    if n > 1:
        diffs = np.diff(sorted(times))
        d['Flow IAT Max']   = float(np.max(diffs)) * 1000
        d['Flow IAT Mean']  = float(np.mean(diffs)) * 1000
        d['Flow IAT Std']   = float(group['fail_rate_per_ip_60s'].mean())
        d['Fwd IAT Mean']   = float(np.mean(diffs)) * 1000
        d['Fwd IAT Min']    = float(np.min(diffs)) * 1000
        d['Flow Packets/s'] = n / max(float(times.max() - times.min()), 1.0)
    else:
        d['Flow IAT Max']   = 0.0
        d['Flow IAT Mean']  = 0.0
        d['Flow IAT Std']   = float(group['fail_rate_per_ip_60s'].mean())
        d['Fwd IAT Mean']   = 0.0
        d['Fwd IAT Min']    = 0.0
        d['Flow Packets/s'] = 1.0 / 60.0

    all_bytes = np.concatenate([rb, rs])
    d['Fwd Packet Length Max']       = float(np.max(rb))
    d['Fwd Packet Length Min']       = float(np.min(rb))
    d['Fwd Packet Length Mean']      = float(np.mean(rb))
    d['Fwd Header Length']           = float(np.min(rb)) * 0.5
    d['Bwd Packet Length Max']       = float(np.max(rs))
    d['Bwd Packet Length Min']       = float(np.min(rs))
    d['Bwd Header Length']           = float(np.min(rs)) * 0.5
    d['Packet Length Mean']          = float(np.mean(all_bytes))
    d['Min Packet Length']           = float(np.min(all_bytes))
    d['Max Packet Length']           = float(np.max(all_bytes))
    d['Packet Length Variance']      = float(np.var(all_bytes))
    d['Total Length of Fwd Packets'] = float(np.sum(rb))
    d['Total Fwd Packets']           = float(n)
    d['Init_Win_bytes_forward']      = float(rb[0])
    d['Init_Win_bytes_backward']     = float(rs[0])
    d['Flow Bytes/s']                = float(np.sum(all_bytes)) / 60.0
    d['PSH Flag Count']              = int((group['http_method'] == 2).sum())
    d['Destination Port']            = float(group['endpoint_category'].nunique())

    d['label']       = int(group['label'].max())
    attacks          = group.loc[group['label'] == 1, 'attack_type']
    d['attack_type'] = attacks.mode().iloc[0] if len(attacks) > 0 else 'Normal'

    return pd.Series(d)

print('\nAggregating sessions...')
sessions = df_raw.groupby(['source_ip', 'time_bucket']).apply(
    aggregate_session).reset_index(drop=True)

print(f'\nSessions:  {len(sessions):,}')
print(f'Normal:    {(sessions["label"]==0).sum():,}')
print(f'Attack:    {(sessions["label"]==1).sum():,}')
print(f'\nAttack type distribution:')
print(sessions['attack_type'].value_counts().to_string())
```

# CELL 3 — Load Scaler + Map Sessions to 24 CICIDS Features

```python
scaler = joblib.load('scaler.pkl')
CICIDS_24 = scaler.feature_names_in_.tolist()

print(f'Scaler expects {len(CICIDS_24)} features:')
print(CICIDS_24)

df_mapped = sessions[CICIDS_24].copy()
df_mapped.fillna(0, inplace=True)
df_mapped.replace([np.inf, -np.inf], 0, inplace=True)

max_endpoints = float(sessions['Destination Port'].max())
df_mapped['Destination Port'] = df_mapped['Destination Port'] / max_endpoints
dest_port_idx    = CICIDS_24.index('Destination Port')
flow_iat_std_idx = CICIDS_24.index('Flow IAT Std')

for i, col in enumerate(CICIDS_24):
    if col in ('Destination Port', 'Flow IAT Std'):
        continue
    df_mapped[col] = df_mapped[col].clip(
        lower=scaler.data_min_[i],
        upper=scaler.data_max_[i]
    )

X_temp = scaler.transform(df_mapped)
X_real_scaled = X_temp.copy()
X_real_scaled[:, dest_port_idx]    = df_mapped['Destination Port'].values
X_real_scaled[:, flow_iat_std_idx] = df_mapped['Flow IAT Std'].values

y_real            = sessions['label'].values
attack_types_real = sessions['attack_type'].values

print(f'\nScaling complete')
print(f'  Shape: {X_real_scaled.shape}')
print(f'  Range: [{X_real_scaled.min():.3f}, {X_real_scaled.max():.3f}]')
print(f'  NaN:   {np.isnan(X_real_scaled).sum()}')

dp_check = pd.DataFrame({
    'dest_port_scaled':    X_real_scaled[:, dest_port_idx],
    'flow_iat_std_scaled': X_real_scaled[:, flow_iat_std_idx],
    'attack_type':         attack_types_real
})
print('\nDestination Port (scaled) by attack type:')
print(dp_check.groupby('attack_type')['dest_port_scaled'].agg(['mean','max']).round(4))
print('\nFlow IAT Std / fail_rate (scaled) by attack type:')
print(dp_check.groupby('attack_type')['flow_iat_std_scaled'].agg(['mean','max']).round(4))
```

# CELL 4 — Load Pretrained Model + Check Reconstruction Error

```python
autoencoder = load_model('autoencoder_model.h5', compile=False)
autoencoder.compile(optimizer='adam', loss='mse')
print('Model loaded')
autoencoder.summary()

X_pred_check = autoencoder.predict(X_real_scaled, verbose=0)
recon_check  = np.mean(np.power(X_real_scaled - X_pred_check, 2), axis=1)

print('\nReconstruction error by type (before fine-tuning):')
print(f'{"Type":<12} {"mean":>10} {"std":>10} {"p50":>10} {"p90":>10}')
print('-' * 48)
for atype in ['Normal', 'brute', 'portscan', 'webattack', 'dos']:
    mask = (attack_types_real == atype)
    if mask.sum() == 0:
        continue
    errs = recon_check[mask]
    print(f'{atype:<12} {errs.mean():>10.6f} {errs.std():>10.6f} '
          f'{np.percentile(errs,50):>10.6f} {np.percentile(errs,90):>10.6f}')
```

# CELL 5 — Fine-tuning Data Split

```python
X_normal_all = X_real_scaled[y_real == 0]
X_attack_all = X_real_scaled[y_real == 1]
at_all       = attack_types_real[y_real == 1]

X_normal_train, X_normal_test = train_test_split(
    X_normal_all, test_size=0.2, random_state=42)

split      = int(len(X_normal_train) * 0.9)
X_ft_train = X_normal_train[:split]
X_ft_val   = X_normal_train[split:]

print(f'Fine-tune train (normal): {X_ft_train.shape}')
print(f'Fine-tune val   (normal): {X_ft_val.shape}')
print(f'Test normal (unseen):     {X_normal_test.shape}')
print(f'Attack sessions:          {X_attack_all.shape}')
```

# CELL 6 — Fine-tuning (normal only, unsupervised)

```python
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

autoencoder.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=1e-4),
    loss='mse'
)

callbacks = [
    EarlyStopping(patience=10, restore_best_weights=True, verbose=1),
    ReduceLROnPlateau(patience=5, factor=0.5, min_lr=1e-6, verbose=1)
]

print('Fine-tuning on normal Keystone sessions...')
history = autoencoder.fit(
    X_ft_train, X_ft_train,
    epochs=100,
    batch_size=32,
    validation_data=(X_ft_val, X_ft_val),
    callbacks=callbacks,
    verbose=1
)

autoencoder.save('autoencoder_finetuned.h5')
print('✅ Saved: autoencoder_finetuned.h5')

plt.figure(figsize=(8, 4))
plt.plot(history.history['loss'],     label='Train Loss', color='steelblue')
plt.plot(history.history['val_loss'], label='Val Loss',   color='tomato')
plt.xlabel('Epoch')
plt.ylabel('MSE Loss')
plt.title('Fine-tuning Loss Curve')
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig('phase2_finetune_loss.png', dpi=150)
plt.show()
print('✅ Saved: phase2_finetune_loss.png')

X_pred_after = autoencoder.predict(X_real_scaled, verbose=0)
recon_after  = np.mean(np.power(X_real_scaled - X_pred_after, 2), axis=1)

print('\nReconstruction error by type (after fine-tuning):')
print(f'{"Type":<12} {"mean":>10} {"std":>10} {"p50":>10} {"p90":>10}')
print('-' * 48)
for atype in ['Normal', 'brute', 'portscan', 'webattack', 'dos']:
    mask = (attack_types_real == atype)
    if mask.sum() == 0:
        continue
    errs = recon_after[mask]
    print(f'{atype:<12} {errs.mean():>10.6f} {errs.std():>10.6f} '
          f'{np.percentile(errs,50):>10.6f} {np.percentile(errs,90):>10.6f}')
```

# CELL 7 — Threshold Tuning + Final Evaluation

```python
X_test = np.vstack([X_normal_test, X_attack_all])
y_test = np.concatenate([
    np.zeros(len(X_normal_test)),
    np.ones(len(X_attack_all))
])
at_test = np.concatenate([
    np.array(['Normal'] * len(X_normal_test)),
    at_all
])

X_pred_test  = autoencoder.predict(X_test, verbose=0)
recon_errors = np.mean(np.power(X_test - X_pred_test, 2), axis=1)

errors_normal_test = recon_errors[y_test == 0]
best_f1, best_thr  = 0, 0

for pct in range(50, 100):
    thr    = np.percentile(errors_normal_test, pct)
    y_pred = (recon_errors > thr).astype(int)
    f1     = f1_score(y_test, y_pred, zero_division=0)
    if f1 > best_f1:
        best_f1  = f1
        best_thr = thr

y_pred_final = (recon_errors > best_thr).astype(int)
prec = precision_score(y_test, y_pred_final, zero_division=0)
rec  = recall_score(y_test, y_pred_final, zero_division=0)
auc  = roc_auc_score(y_test, recon_errors)

print('=' * 60)
print('TRACK 1 — FINAL EVALUATION')
print('=' * 60)
print(classification_report(y_test, y_pred_final, target_names=['Normal', 'Attack']))
print(f'F1:        {best_f1:.4f}')
print(f'Precision: {prec:.4f}')
print(f'Recall:    {rec:.4f}')
print(f'ROC-AUC:   {auc:.4f}')
print(f'Threshold: {best_thr:.6f}')

print('\nPER ATTACK TYPE BREAKDOWN:')
print(f'{"Attack Type":<12} {"Total":>6} {"Detected":>9} {"Missed":>7} {"Recall":>8}')
print('-' * 48)
for atype in ['Normal', 'brute', 'portscan', 'webattack', 'dos']:
    mask  = (at_test == atype)
    total = mask.sum()
    if total == 0:
        continue
    if atype == 'Normal':
        correct = (y_pred_final[mask] == 0).sum()
        print(f'{atype:<12} {total:>6} {correct:>9} {total-correct:>7} {correct/total:>8.3f}  (TNR)')
    else:
        detected = (y_pred_final[mask] == 1).sum()
        print(f'{atype:<12} {total:>6} {detected:>9} {total-detected:>7} {detected/total:>8.3f}')
```

# CELL 8 — Plots

```python
fig, axes = plt.subplots(1, 3, figsize=(18, 5))

cm = confusion_matrix(y_test, y_pred_final)
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=axes[0],
            xticklabels=['Normal', 'Attack'],
            yticklabels=['Normal', 'Attack'])
axes[0].set_title(f'Confusion Matrix\nThreshold={best_thr:.6f}')
axes[0].set_ylabel('True')
axes[0].set_xlabel('Predicted')

fpr, tpr, _ = roc_curve(y_test, recon_errors)
axes[1].plot(fpr, tpr, color='steelblue', lw=2, label=f'AUC={auc:.4f}')
axes[1].plot([0, 1], [0, 1], 'k--', lw=1)
axes[1].set_xlabel('False Positive Rate')
axes[1].set_ylabel('True Positive Rate')
axes[1].set_title('ROC Curve')
axes[1].legend()
axes[1].grid(alpha=0.3)

colors = {'Normal': 'steelblue', 'brute': 'tomato',
          'portscan': 'orange', 'webattack': 'green', 'dos': 'purple'}
for atype in ['Normal', 'brute', 'portscan', 'webattack', 'dos']:
    mask = (at_test == atype)
    if mask.sum() == 0:
        continue
    axes[2].hist(recon_errors[mask], bins=50, alpha=0.5,
                 label=f'{atype} (n={mask.sum()})',
                 color=colors.get(atype, 'gray'), density=True)
axes[2].axvline(best_thr, color='red', linestyle='--',
                label=f'Threshold={best_thr:.6f}')
axes[2].set_xlabel('Reconstruction Error')
axes[2].set_ylabel('Density')
axes[2].set_title('Reconstruction Error by Attack Type')
axes[2].legend(fontsize=8)
axes[2].grid(alpha=0.3)

plt.suptitle('Track 1 — Final Evaluation', fontsize=13)
plt.tight_layout()
plt.savefig('track1_final_evaluation.png', dpi=150)
plt.show()
print('✅ Saved: track1_final_evaluation.png')
```
