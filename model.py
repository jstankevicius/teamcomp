"""Module to create the model for predicting LoL match outcomes. Takes a list of
numpy arrays from model_inputs.py as input. Final output should be a neural
network.
"""
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense
from model_inputs import mock_model_input
from db import mock_db_matchinfo_list
'''Finish db.py, model.py and model_inputs.py
    model.py: 
        copy-paste from a Keras tutorial, change input_shape to (10, 161, 2)
    model_inputs.py: 
        copy the mock function, and switch out all random.randint() calls to be something from a matchinfo object (or a player object sitting inside the matchinfo object)
    db.py:
        iterate over all matchIds
        for each matchId, get a list of players from the Participants


'''
match = mock_db_matchinfo_list()
print(mock_model_input(match[0]))
# model = Sequential()
# model.add(Dense(10, input_shape=(10, 161, 2), activation='relu'))
# model.add(Dense(10, activation='relu'))
# model.add(Dense(10, activation='relu'))
# model.add(Dense(10, activation='relu'))
# model.add(Dense(1, activation='sigmoid'))

# model.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])
# # fit the keras model on the dataset
# model.fit(X, y, epochs=150, batch_size=10)
# # evaluate the keras model
# _, accuracy = model.evaluate(X, y)
# print('Accuracy: %.2f' % (accuracy*100))

