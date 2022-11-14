"""Module for interfacing with the database. Its primary goal is to return a
list of MatchInfo objects to model_inputs.py, which will then transform the list
into a numpy array.
"""
import numpy as np
import sqlite3
from tqdm import tqdm
import collections

# TEMPLATES
class MatchInfo:

    def __init__(self):
        self.winner = 0
        self.players = []

class PlayerInfo:

    def __init__(self):
        self.champion_id = 0
        self.masteries = {}
        self.team_position = None
        self.team_id = None


# TODO: kill this with fire
def db_matchinfo_list(limit=None):

    conn = sqlite3.connect("league.db")
    all_matches = conn.execute("""SELECT distinct matchId FROM
        Participants;""").fetchall()

    res = []
    all_matches = all_matches if not limit else all_matches[:limit]
    all_champ_ids = set([i[0] for i in conn.execute("SELECT distinct championId FROM Champions;").fetchall()])

    for match_id, in all_matches:
        m = MatchInfo()
        m.winner = conn.execute("""SELECT winner FROM Matches WHERE
            Matches.matchId == ?""", [match_id]).fetchone()[0]

        players = conn.execute("""SELECT summonerName, championId, teamId,
            teamPosition FROM Participants WHERE Participants.matchId == ?""",
            [match_id]).fetchall()

        for summoner_name, champion_id, team_id, team_position in players:
            p = PlayerInfo()
            p.champion_id = champion_id
            p.team_id = team_id
            p.team_position = team_position

            masteries = {champ_id: score for champ_id, score in conn.execute(
                """SELECT championId, championPoints
                   FROM ChampionMastery
                   WHERE ChampionMastery.summonerName == ?
                   ORDER BY championId ASC""",
                   [summoner_name]).fetchall()}

            all_masteries = {champ_id: 0 for champ_id in all_champ_ids}

            for champion_mastery_id, mastery_score in masteries.items():
                all_masteries[champion_mastery_id] = mastery_score

            p.masteries = sorted(list(all_masteries.items()), key=lambda x:x[0])

            m.players.append(p)

        # Sanity check:
        if len(m.players) != 10 or any([len(p.masteries) != 161 for p in m.blue]):
            continue

        res.append(m)
    return res