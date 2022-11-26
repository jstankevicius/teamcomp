"""Module to create the model for predicting LoL match outcomes. Takes a list of
numpy arrays from model_inputs.py as input. Final output should be a neural
network.
"""
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense
from model_inputs import match_info_to_nparray
from db import db_matchinfo_list
import numpy as np
import tensorflow as tf


matches = db_matchinfo_list(limit=10000)
print(matches)
for m in matches:
    assert len(m.players) == 10

converted = [match_info_to_nparray(m) for m in matches]

x = np.zeros(shape=(len(matches), 10, 161, 2))

for i in range(len(converted)):
    x[i] = converted[i]

y = np.array([1 if m.winner == 100 else 0 for m in matches])
print(x.shape)
print(y.shape)
model = Sequential()
model.add(Dense(161, input_shape=(10, 161, 2), activation='relu'))
for i in range(20):
    model.add(Dense(40, activation='relu'))
model.add(Dense(1, activation='sigmoid'))

model.compile(loss="mse", optimizer='adam', metrics=['accuracy'])
# fit the keras model on the dataset
model.fit(x[:-100], y[:-100], epochs=50, batch_size=100)

# evaluate the keras model
_, accuracy = model.evaluate(x[-100:], y[-100:])
print('Accuracy: %.2f' % (accuracy*100))

