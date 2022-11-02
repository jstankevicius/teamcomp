"""Module for transforming database MatchInfo objects into numpy arrays that are
then passed to model.py.
"""

import numpy as np
import random


def mock_model_input():
    """
    Returns a mock version of the model's input as a numpy array.
    """

    model_input = np.zeros(shape=(10, 161, 2))

    for player_idx in range(10):
        champ_idx = random.randint(0, 160)
        model_input[player_idx][champ_idx][0] = 1

        for i in range(161):
            model_input[player_idx][i][1] = random.randint(0, 50000)

    return model_input