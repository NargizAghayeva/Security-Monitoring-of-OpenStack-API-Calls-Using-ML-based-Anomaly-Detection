import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib
import os

os.makedirs('data/processed', exist_ok=True)
os.makedirs('models/saved_models', exist_ok=True)

print("=" * 50)
print("PREPROCESSING")
print("=" * 50)

# 1. Load
print("\n1. Loading data...")
df = pd.read_csv('data/raw/cicids2017_cleaned.csv')
print(f"   Total: {len(df):,}")

# 2. Separate
print("\n2. Separating normal/anomaly...")
normal = df[df['Attack Type'] == 'Normal Traffic'].drop(columns=['Attack Type'])
anomaly = df[df['Attack Type'] != 'Normal Traffic'].drop(columns=['Attack Type'])
print(f"   Normal: {len(normal):,}")
print(f"   Anomaly: {len(anomaly):,}")

# 3. Train/test split
print("\n3. Splitting...")
X_train, X_test_normal = train_test_split(normal, test_size=0.2, random_state=42)
print(f"   Train: {len(X_train):,}")
print(f"   Test normal: {len(X_test_normal):,}")
print(f"   Test anomaly: {len(anomaly):,}")

# 4. Scale
print("\n4. Scaling...")
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_normal_scaled = scaler.transform(X_test_normal)
X_test_anomaly_scaled = scaler.transform(anomaly)

# 5. Save
print("\n5. Saving...")
np.save('data/processed/X_train.npy', X_train_scaled)
np.save('data/processed/X_test_normal.npy', X_test_normal_scaled)
np.save('data/processed/X_test_anomaly.npy', X_test_anomaly_scaled)
joblib.dump(scaler, 'models/saved_models/scaler.pkl')
joblib.dump(normal.columns.tolist(), 'models/saved_models/feature_names.pkl')

print("\n" + "=" * 50)
print("✅ DONE!")
print("=" * 50)
print(f"   Train shape:        {X_train_scaled.shape}")
print(f"   Test normal shape:  {X_test_normal_scaled.shape}")
print(f"   Test anomaly shape: {X_test_anomaly_scaled.shape}")
