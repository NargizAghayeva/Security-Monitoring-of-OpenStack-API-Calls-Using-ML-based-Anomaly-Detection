import numpy as np
import tensorflow as tf
from tensorflow import keras
import matplotlib.pyplot as plt
import os

os.makedirs('results/plots', exist_ok=True)
os.makedirs('models/saved_models', exist_ok=True)

print("=" * 50)
print("AUTOENCODER TRAINING")
print("=" * 50)

# 1. Load data
print("\n1. Loading data...")
X_train = np.load('data/processed/X_train.npy')
print(f"   Train shape: {X_train.shape}")

# 2. Build autoencoder
print("\n2. Building model...")
input_dim = X_train.shape[1]  # 52

autoencoder = keras.Sequential([
    # Encoder
    keras.layers.Dense(32, activation='relu', input_shape=(input_dim,)),
    keras.layers.Dense(16, activation='relu'),
    keras.layers.Dense(8, activation='relu'),
    # Decoder
    keras.layers.Dense(16, activation='relu'),
    keras.layers.Dense(32, activation='relu'),
    keras.layers.Dense(input_dim, activation='linear')
])

autoencoder.compile(optimizer='adam', loss='mse')
autoencoder.summary()

# 3. Train
print("\n3. Training...")
history = autoencoder.fit(
    X_train, X_train,
    epochs=20,
    batch_size=512,
    validation_split=0.1,
    verbose=1
)

# 4. Save model
print("\n4. Saving model...")
autoencoder.save('models/saved_models/autoencoder.h5')
print("   ✅ models/saved_models/autoencoder.h5")

# 5. Plot
print("\n5. Plotting training history...")
plt.figure(figsize=(10, 5))
plt.plot(history.history['loss'], label='Train Loss')
plt.plot(history.history['val_loss'], label='Val Loss')
plt.xlabel('Epoch')
plt.ylabel('MSE Loss')
plt.title('Autoencoder Training History')
plt.legend()
plt.grid(True)
plt.savefig('results/plots/training_history.png', dpi=150)
plt.close()
print("   ✅ results/plots/training_history.png")

print("\n" + "=" * 50)
print("✅ TRAINING COMPLETE!")
print("=" * 50)
