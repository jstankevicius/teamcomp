"""Module for interfacing with the database. Its primary goal is to return a
list of MatchInfo objects to model_inputs.py, which will then transform the list
into a numpy array.
"""
import numpy as np
import sqlite3
from tqdm import tqdm
import collections
import pandas as pd
db_conn = sqlite3.connect("league.db")
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
        self.win_rate = []
def win_rate():
    sql3 = ("SELECT ch.championName, ch.difficulty, COUNT(m.winner) as games_won_by_champ FROM Champions as ch JOIN Participants as p on ch.championId = p.championId JOIN Matches as m on p.matchId = m.matchId WHERE m.winner = p.teamId GROUP BY ch.championName ORDER BY championName ASC")
    df1 = pd.read_sql(sql3, con = db_conn)
    # print(df)
    sql4 = "select Champions.championName, count(*) as total from Participants join Champions on Participants.championId == Champions.championId join Matches on Matches.matchId == Participants.matchId group by championName Order BY championName"
    df2 = pd.read_sql(sql4, con = db_conn)
    # print(df2)
    dataframe = pd.DataFrame().assign(ChampionName=df1['championName'], gamesWon=df1['games_won_by_champ'], difficulty=df1["difficulty"], total=df2['total'])
    dataframe['percentage'] = np.nan
    dataframe['percentage'] = dataframe['gamesWon']/dataframe['total'] * 100
    dataframe['percentage'] = dataframe['percentage'].apply(lambda x: round(x, 2))
    return dataframe
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
        # m.winner = conn.execute("""SELECT winner FROM Matches WHERE
        #     Matches.matchId == ?""", [match_id]).fetchone()[0]

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
            p.win_rate = win_rate()["percentage"]
            m.players.append(p)

        # Sanity check:
        if len(m.players) != 10 or any([len(p.masteries) != 161 for p in m.players]):
            continue
        
        res.append(m)
    return res