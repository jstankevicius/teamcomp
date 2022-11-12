"""Module for interfacing with the database. Its primary goal is to return a
list of MatchInfo objects to model_inputs.py, which will then transform the list
into a numpy array.
"""
import numpy as np

# TEMPLATES
class MatchInfo:

    def __init__(self):
        self.winner = 0
        self.players = []


class PlayerInfo:

    def __init__(self):
        self.champion_id = 0
        self.masteries = np.zeros(161)


def db_matchinfo_list():
    res = []
    cnx = sqlite3.connect("league.db")
    all_matches = cnx.execute("SELECT matchId FROM Matches;").fetchall()

    for match_id in all_matches:
        m = MatchInfo()
        m.winner = cnx.execute("SELECT winner FROM Matches WHERE Matches.matchId == ?", [match_id]).fetchone()[0]
        players = cnx.execute("SELECT summonerName, championID FROM Participants WHERE Participants.matchId == ?", [maych_id]).fetchall()

        for player in players:
            p = PlayerInfo()
            summoner_name = player[0]
            champion_id = player[1]
  
            p.champion_id = champion_id
            p.masteries = cnx.execute("SELECT championID, ChampionMastery FROM championPoints WHERE ChampionMastery.summonerName == ?" [summoner_name]).fetchall()
            m.players.append(p)

        res.append(m)

    return res
