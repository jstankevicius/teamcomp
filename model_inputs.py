"""Module for transforming database MatchInfo objects into numpy arrays that are
then passed to model.py.
"""

import numpy as np
import random

POSITION_OFFSET = {
    "TOP": 0,
    "JUNGLE": 1,
    "MIDDLE": 2,
    "BOTTOM": 3,
    "UTILITY": 4
}

def match_info_to_nparray(match_info):
    """
    Returns a mock version of the model's input as a numpy array.
    """

    model_input = np.zeros(shape=(10, 161, 2))

    for p in match_info.players:
        team_offset = 0 if p.team_id == 100 else 5
        pos_offset = POSITION_OFFSET[p.team_position]
        player_idx = team_offset + pos_offset

        player = match_info.players[player_idx]
        champ_id = player.champion_id

        # TODO: avoid this for loop, do it in constant time
        for i in range(len(player.masteries)):
            if player.masteries[i][0] == champ_id:
                model_input[player_idx][i][0] = 1
                break

        for i in range(161):
            model_input[player_idx][i][1] = player.masteries[i][1]

    return model_input

