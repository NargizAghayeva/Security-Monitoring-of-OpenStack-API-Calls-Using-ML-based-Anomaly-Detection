import numpy as np
import tensorflow as tf
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
import matplotlib.pyplot as plt
import os
import json

os.makedirs('results/plots', exist_ok=True)
os.makedirs('results/metrics', exist_ok=True)

print("=" * 50)
print("EVALUATION")
print("=" * 50)

# 1. Load
print("\n1. Loading model and data...")
autoencoder = tf.keras.models.load_model('models/saved_models/autoencoder.h5')
X_test_normal = np.load('data/processed/X_test_normal.npy')
X_test_anomaly = np.load('data/processed/X_test_anomaly.npy')
print(f"   Test normal:  {X_test_normal.shape}")
print(f"   Test anomaly: {X_test_anomaly.shape}")

# 2. Reconstruction errors
print("\n2. Calculating reconstruction errors...")
recon_normal = autoencoder.predict(X_test_normal, batch_size=512, verbose=1)
recon_anomaly = autoencoder.predict(X_test_anomaly, batch_size=512, verbose=1)

errors_normal = np.mean(np.square(X_test_normal - recon_normal), axis=1)
errors_anomaly = np.mean(np.square(X_test_anomaly - recon_anomaly), axis=1)

print(f"\n   Normal  - Mean: {errors_normal.mean():.6f}, Std: {errors_normal.std():.6f}")
print(f"   Anomaly - Mean: {errors_anomaly.mean():.6f}, Std: {errors_anomaly.std():.6f}")

# 3. Threshold
threshold = np.percentile(errors_normal, 95)
print(f"\n3. Threshold (95th percentile): {threshold:.6f}")

# 4. Predictions
y_pred_normal = (errors_normal > threshold).astype(int)
y_pred_anomaly = (errors_anomaly > threshold).astype(int)

y_true = np.concatenate([np.zeros(len(y_pred_normal)), np.ones(len(y_pred_anomaly))])
y_pred = np.concatenate([y_pred_normal, y_pred_anomaly])

# 5. Metrics
print("\n4. Performance Metrics:")
print("-" * 40)
acc  = accuracy_score(y_true, y_pred)
prec = precision_score(y_true, y_pred)
rec  = recall_score(y_true, y_pred)
f1   = f1_score(y_true, y_pred)

print(f"   Accuracy:  {acc*100:.2f}%")
print(f"   Precision: {prec*100:.2f}%")
print(f"   Recall:    {rec*100:.2f}%")
print(f"   F1-Score:  {f1*100:.2f}%")
print("-" * 40)

# 6. Plot
print("\n5. Plotting...")
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Distribution
axes[0].hist(errors_normal, bins=100, alpha=0.6, label='Normal', color='blue', density=True)
axes[0].hist(errors_anomaly, bins=100, alpha=0.6, label='Anomaly', color='red', density=True)
axes[0].axvline(threshold, color='green', linestyle='--', linewidth=2, label=f'Threshold={threshold:.4f}')
axes[0].set_xlabel('Reconstruction Error')
axes[0].set_ylabel('Density')
axes[0].set_title('Reconstruction Error Distribution')
axes[0].legend()
axes[0].grid(True, alpha=0.3)

# Confusion matrix
cm = confusion_matrix(y_true, y_pred)
im = axes[1].imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
axes[1].set_title('Confusion Matrix')
plt.colorbar(im, ax=axes[1])
axes[1].set_xlabel('Predicted')
axes[1].set_ylabel('Actual')
axes[1].set_xticks([0, 1])
axes[1].set_yticks([0, 1])
axes[1].set_xticklabels(['Normal', 'Anomaly'])
axes[1].set_yticklabels(['Normal', 'Anomaly'])
for i in range(2):
    for j in range(2):
        axes[1].text(j, i, format(cm[i, j], 'd'),
                    ha='center', va='center', fontsize=12,
                    color='white' if cm[i, j] > cm.max()/2 else 'black')

plt.tight_layout()
plt.savefig('results/plots/evaluation.png', dpi=150, bbox_inches='tight')
plt.close()
print("   ✅ results/plots/evaluation.png")

# 7. Save metrics
metrics = {
    'accuracy': round(acc, 4),
    'precision': round(prec, 4),
    'recall': round(rec, 4),
    'f1_score': round(f1, 4),
    'threshold': round(float(threshold), 6)
}
with open('results/metrics/autoencoder_metrics.json', 'w') as f:
    json.dump(metrics, f, indent=2)
print("   ✅ results/metrics/autoencoder_metrics.json")

print("\n" + "=" * 50)
print("✅ EVALUATION COMPLETE!")
print("=" * 50)
