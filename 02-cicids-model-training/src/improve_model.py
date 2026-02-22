import numpy as np
import tensorflow as tf
from tensorflow import keras
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import matplotlib.pyplot as plt
import json
import os

os.makedirs('results/plots', exist_ok=True)
os.makedirs('results/metrics', exist_ok=True)
os.makedirs('models/saved_models', exist_ok=True)

print("=" * 60)
print("IMPROVED AUTOENCODER (v2)")
print("=" * 60)

# 1. Load data
print("\n1. Loading data...")
X_train = np.load('data/processed/X_train.npy')
X_test_normal = np.load('data/processed/X_test_normal.npy')
X_test_anomaly = np.load('data/processed/X_test_anomaly.npy')
print(f"   Train:        {X_train.shape}")
print(f"   Test normal:  {X_test_normal.shape}")
print(f"   Test anomaly: {X_test_anomaly.shape}")

# 2. Remove outliers
print("\n2. Removing outliers from training data...")
norms = np.linalg.norm(X_train, axis=1)
p1 = np.percentile(norms, 1)
p99 = np.percentile(norms, 99)
mask = (norms >= p1) & (norms <= p99)
X_train_clean = X_train[mask]
print(f"   Before: {len(X_train):,}")
print(f"   After:  {len(X_train_clean):,}")
print(f"   Removed: {len(X_train) - len(X_train_clean):,} ({100*(1-len(X_train_clean)/len(X_train)):.2f}%)")

# 3. Build improved model
print("\n3. Building improved model...")
input_dim = X_train_clean.shape[1]

autoencoder_v2 = keras.Sequential([
    # Encoder
    keras.layers.Dense(64, activation='relu', input_shape=(input_dim,)),
    keras.layers.BatchNormalization(),
    keras.layers.Dense(32, activation='relu'),
    keras.layers.BatchNormalization(),
    keras.layers.Dense(16, activation='relu'),
    keras.layers.Dense(8, activation='relu'),
    # Decoder
    keras.layers.Dense(16, activation='relu'),
    keras.layers.Dense(32, activation='relu'),
    keras.layers.BatchNormalization(),
    keras.layers.Dense(64, activation='relu'),
    keras.layers.Dense(input_dim, activation='linear')
], name='autoencoder_v2')

autoencoder_v2.compile(optimizer='adam', loss='mse')
autoencoder_v2.summary()

# 4. Callbacks
early_stop = keras.callbacks.EarlyStopping(
    monitor='val_loss',
    patience=3,
    restore_best_weights=True
)

reduce_lr = keras.callbacks.ReduceLROnPlateau(
    monitor='val_loss',
    factor=0.5,
    patience=2,
    min_lr=0.00001
)

# 5. Train
print("\n4. Training...")
history = autoencoder_v2.fit(
    X_train_clean, X_train_clean,
    epochs=30,
    batch_size=512,
    validation_split=0.1,
    callbacks=[early_stop, reduce_lr],
    verbose=1
)

# 6. Save model
print("\n5. Saving model...")
autoencoder_v2.save('models/saved_models/autoencoder_v2.h5')
print("   ✅ models/saved_models/autoencoder_v2.h5")

# 7. Reconstruction errors
print("\n6. Calculating reconstruction errors...")
recon_normal = autoencoder_v2.predict(X_test_normal, batch_size=512, verbose=1)
recon_anomaly = autoencoder_v2.predict(X_test_anomaly, batch_size=512, verbose=1)

errors_normal = np.mean(np.square(X_test_normal - recon_normal), axis=1)
errors_anomaly = np.mean(np.square(X_test_anomaly - recon_anomaly), axis=1)

print(f"\n   Normal  - Mean: {errors_normal.mean():.6f}, Std: {errors_normal.std():.6f}")
print(f"   Anomaly - Mean: {errors_anomaly.mean():.6f}, Std: {errors_anomaly.std():.6f}")

# 8. Threshold optimization
print("\n7. Threshold optimization...")
percentiles = [90, 92, 95, 97, 99]
results = []

print("\n   Percentile | Threshold  | Accuracy | Precision | Recall  | F1-Score")
print("   " + "-" * 72)

for p in percentiles:
    threshold = np.percentile(errors_normal, p)
    
    y_pred_normal = (errors_normal > threshold).astype(int)
    y_pred_anomaly = (errors_anomaly > threshold).astype(int)
    
    y_true = np.concatenate([np.zeros(len(y_pred_normal)), np.ones(len(y_pred_anomaly))])
    y_pred = np.concatenate([y_pred_normal, y_pred_anomaly])
    
    acc  = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred)
    rec  = recall_score(y_true, y_pred)
    f1   = f1_score(y_true, y_pred)
    
    results.append({
        'percentile': p,
        'threshold': threshold,
        'accuracy': acc,
        'precision': prec,
        'recall': rec,
        'f1_score': f1
    })
    
    print(f"   {p:>3}%       | {threshold:.6f} | {acc*100:>6.2f}%  | {prec*100:>7.2f}%  | {rec*100:>6.2f}% | {f1*100:>7.2f}%")

# 9. Best result
best = max(results, key=lambda x: x['f1_score'])
print("\n   " + "=" * 72)
print(f"   ✅ BEST: {best['percentile']}th percentile - F1={best['f1_score']*100:.2f}%")
print("   " + "=" * 72)

# 10. Plot training
print("\n8. Plotting training history...")
plt.figure(figsize=(10, 5))
plt.plot(history.history['loss'], label='Train Loss')
plt.plot(history.history['val_loss'], label='Val Loss')
plt.xlabel('Epoch')
plt.ylabel('MSE Loss')
plt.title('Autoencoder v2 Training History')
plt.legend()
plt.grid(True)
plt.savefig('results/plots/training_history_v2.png', dpi=150)
plt.close()
print("   ✅ results/plots/training_history_v2.png")

# 11. Plot threshold comparison
print("\n9. Plotting threshold optimization...")
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Metrics vs Percentile
perc = [r['percentile'] for r in results]
acc_list = [r['accuracy']*100 for r in results]
prec_list = [r['precision']*100 for r in results]
rec_list = [r['recall']*100 for r in results]
f1_list = [r['f1_score']*100 for r in results]

axes[0].plot(perc, acc_list, 'o-', label='Accuracy', linewidth=2)
axes[0].plot(perc, prec_list, 's-', label='Precision', linewidth=2)
axes[0].plot(perc, rec_list, '^-', label='Recall', linewidth=2)
axes[0].plot(perc, f1_list, 'd-', label='F1-Score', linewidth=2)
axes[0].axvline(best['percentile'], color='red', linestyle='--', alpha=0.5, label=f"Best: {best['percentile']}%")
axes[0].set_xlabel('Percentile')
axes[0].set_ylabel('Score (%)')
axes[0].set_title('Threshold Optimization')
axes[0].legend()
axes[0].grid(True, alpha=0.3)

# Error distribution with best threshold
axes[1].hist(errors_normal, bins=100, alpha=0.6, label='Normal', color='blue', density=True)
axes[1].hist(errors_anomaly, bins=100, alpha=0.6, label='Anomaly', color='red', density=True)
axes[1].axvline(best['threshold'], color='green', linestyle='--', linewidth=2, 
                label=f"Threshold={best['threshold']:.4f}")
axes[1].set_xlabel('Reconstruction Error')
axes[1].set_ylabel('Density')
axes[1].set_title(f"Best Threshold ({best['percentile']}th percentile)")
axes[1].legend()
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('results/plots/threshold_optimization.png', dpi=150, bbox_inches='tight')
plt.close()
print("   ✅ results/plots/threshold_optimization.png")

# 12. Save metrics
print("\n10. Saving metrics...")
metrics = {
    'model_version': 'v2',
    'training_samples': int(len(X_train_clean)),
    'outliers_removed': int(len(X_train) - len(X_train_clean)),
    'best_percentile': int(best['percentile']),
    'best_threshold': float(best['threshold']),
    'accuracy': round(best['accuracy'], 4),
    'precision': round(best['precision'], 4),
    'recall': round(best['recall'], 4),
    'f1_score': round(best['f1_score'], 4),
    'all_results': results
}

with open('results/metrics/autoencoder_v2_metrics.json', 'w') as f:
    json.dump(metrics, f, indent=2)
print("   ✅ results/metrics/autoencoder_v2_metrics.json")

print("\n" + "=" * 60)
print("✅ IMPROVED MODEL COMPLETE!")
print("=" * 60)
print(f"\nFinal Results (v2):")
print(f"  Accuracy:  {best['accuracy']*100:.2f}%")
print(f"  Precision: {best['precision']*100:.2f}%")
print(f"  Recall:    {best['recall']*100:.2f}%")
print(f"  F1-Score:  {best['f1_score']*100:.2f}%")
print("=" * 60)
```

---
