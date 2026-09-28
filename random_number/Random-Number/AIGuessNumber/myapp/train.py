import os
import numpy as np
import pandas as pd
from keras.models import Sequential
from keras.layers import LSTM, Dense, Dropout, Bidirectional
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import pickle

# Example: load your data from DB or file
# sequence = [...]

df = pd.DataFrame(sequence, columns=[f'seq_{i}' for i in range(1, 11)])

scaler = StandardScaler()
scaled_data = scaler.fit_transform(df.values)

# Save scaler
os.makedirs("saved_model", exist_ok=True)
with open("saved_model/scaler.pkl", "wb") as f:
    pickle.dump(scaler, f)

window_length = 4
n_feature = 10

X, y = [], []

for i in range(len(df) - window_length):
    X.append(scaled_data[i:i+window_length])
    y.append(scaled_data[i+window_length])

X = np.array(X)
y = np.array(y)

train_x, test_x, train_y, test_y = train_test_split(X, y, test_size=0.25)

model = Sequential()
model.add(Bidirectional(LSTM(64, return_sequences=True), input_shape=(window_length, n_feature)))
model.add(Dropout(0.2))
model.add(Bidirectional(LSTM(64)))
model.add(Dense(n_feature))

model.compile(optimizer='adam', loss='mse')
model.fit(train_x, train_y, epochs=50, batch_size=32)

# Save model
model.save("saved_model/model.h5")

print(" Model trained and saved!")