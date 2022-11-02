"""Module for interfacing with the database. Its primary goal is to return a
list of MatchInfo objects to model_inputs.py, which will then transform the list
into a numpy array.
"""
import numpy as np
import random

# TEMPLATES
class MatchInfo:

    def __init__(self):
        self.winner = 0
        self.players = []


class PlayerInfo:

    def __init__(self):
        self.champion_id = 0
        self.masteries = np.zeros(161)


def mock_db_matchinfo_list(list_len=10):
    """
    Returns a mock version of a list of MatchInfo objects.
    """
    res = []

    for _ in range(list_len):
        m = MatchInfo()
        m.winner = random.choice([0, 1])

        for _ in range(10):
            p = PlayerInfo()

            # This allows for duplicate champions, so this is not completely
            # correct input
            p.champion_id = random.randint(0, 160)
            p.masteries = np.random.randint(50000, size=161)
            m.players.append(p)

        res.append(m)

    return res
