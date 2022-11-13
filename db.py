"""Module for interfacing with the database. Its primary goal is to return a
list of MatchInfo objects to model_inputs.py, which will then transform the list
into a numpy array.
"""
import numpy as np
import sqlite3
from tqdm import tqdm

# TEMPLATES
class MatchInfo:

    def __init__(self):
        self.winner = 0
        self.players = []


class PlayerInfo:

    def __init__(self):
        self.champion_id = 0
        self.masteries = []


def db_matchinfo_list():

    conn = sqlite3.connect("league.db")
    all_matches = conn.execute("""SELECT distinct matchId FROM
        Participants;""").fetchall()
    res = []

    for match_id, in all_matches:
        m = MatchInfo()
        m.winner = conn.execute("""SELECT winner FROM Matches WHERE
            Matches.matchId == ?""", [match_id]).fetchone()[0]

        players = conn.execute("""SELECT summonerName, championId FROM
            Participants WHERE Participants.matchId == ?""",
            [match_id]).fetchall()

        for summoner_name, champion_id in players:
            p = PlayerInfo()

            p.champion_id = champion_id
            p.masteries = conn.execute(
                """SELECT championId, championPoints
                   FROM ChampionMastery
                   WHERE ChampionMastery.summonerName == ?
                   ORDER BY championId ASC""",
                   [summoner_name]).fetchall()

            m.players.append(p)

        # Sanity check:
        if len(m.players) != 10 or any([len(p.masteries) != 161 for p in m.players]):
            continue

        res.append(m)
    return res