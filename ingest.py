import requests
import json
import os
import sqlite3
import time
import traceback
from pprint import pprint
from collections import deque

API_KEY = "RGAPI-d868f483-4467-4218-8376-47448ae9d809"
CHAMPION_DATA_ENDPOINT = "https://ddragon.leagueoflegends.com/cdn/12.19.1/data/en_US/champion.json"
DELAY = 120/100 # Limit is 100 requests every 2 minutes, or 20 requests in 1 second

MATCH_FIELDS = {
    "gameVersion": str,
    "matchId": str,
    "gameCreation": int,
    "gameDuration": int,
    "gameId": int,
    # "winner": int
}

PARTICIPANT_FIELDS = {
    # "matchId": str
    "assists": str,
    "baronKills": int,
    "championId": int,
    "damageDealtToBuildings": int,
    "damageDealtToObjectives": int,
    "damageDealtToTurrets": int,
    "damageSelfMitigated": int,
    "deaths": int,
    "detectorWardsPlaced": int,
    "dragonKills": int,
    "goldEarned": int,
    "goldSpent": int,
    "kills": int,
    "magicDamageDealt": int,
    "magicDamageDealtToChampions": int,
    "magicDamageTaken": int,
    "neutralMinionsKilled": int,
    "physicalDamageDealt": int,
    "physicalDamageDealtToChampions": int,
    "physicalDamageTaken": int,
    "puuid": str,
    "sightWardsBoughtInGame": int,
    "teamId": int,
    "teamPosition": str,
    "timeCCingOthers": int,
    "totalDamageDealt": int,
    "totalDamageDealtToChampions": int,
    "totalDamageShieldedOnTeammates": int,
    "totalDamageTaken": int,
    "totalHeal": int,
    "totalHealsOnTeammates": int,
    "totalMinionsKilled": int,
    "totalTimeCCDealt": int,
    "trueDamageDealt": int,
    "trueDamageDealtToChampions": int,
    "trueDamageTaken": int,
    "turretKills": int,
    "turretTakedowns": int,
    "visionScore": int,
    "visionWardsBoughtInGame": int,
    "wardsKilled": int,
    "wardsPlaced": int,
}

def get_champion_data():
    """
    Gets relevant data about all current champions in League of Legends from
    a Riot endpoint and returns the result as a list of dictionaries.
    """
    
    r = requests.get(CHAMPION_DATA_ENDPOINT)
    result = []
    tags = set()

    # Collect all tags:
    for data in r.json()["data"].values():
        for tag in data["tags"]:
            tags.add(tag)

        champ_data = {
            "championName": data["id"],
            "championId": int(data["key"]),
            "attack": data["info"]["attack"],
            "defense": data["info"]["defense"],
            "magic": data["info"]["magic"],
            "difficulty": data["info"]["difficulty"],
            "tags": ",".join(data["tags"])
        }

        for stat, value in data["stats"].items():
            champ_data[stat] = value

        result.append(champ_data)

    # Should be {"Assassin", "Marksman", "Support", "Fighter", "Mage", "Tank"}
    assert(len(tags) == 6)
    return result


def maybe_init_db(db_name="league.db"):
    """
    Initializes the database if it does not exist and returns the connection.
    """

    if not os.path.exists(db_name):
        try:
            print(f"{db_name} does not exist, initializing schema")
            conn = sqlite3.connect(db_name)
            
            # Create tables.
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS Matches (
                    matchId TEXT PRIMARY KEY,
                    gameVersion TEXT,
                    gameCreation INTEGER,
                    gameDuration INTEGER,
                    gameId INTEGER,
                    winner INTEGER
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS SeenMatches (
                    matchId TEXT PRIMARY KEY
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS SeenPlayers (
                    puuid TEXT PRIMARY KEY
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS Champions (
                    armor INTEGER,
                    armorperlevel REAL,
                    attack INTEGER,
                    attackdamage INTEGER,
                    attackdamageperlevel REAL,
                    attackrange INTEGER,
                    attackspeed REAL,
                    attackspeedperlevel REAL,
                    championId INTEGER PRIMARY KEY,
                    championName TEXT,
                    crit INTEGER,
                    critperlevel INTEGER,
                    defense INTEGER,
                    difficulty INTEGER,
                    hp INTEGER,
                    hpperlevel INTEGER,
                    hpregen REAL,
                    hpregenperlevel REAL,
                    magic INTEGER,
                    movespeed INTEGER,
                    mp INTEGER,
                    mpperlevel INTEGER,
                    mpregen INTEGER,
                    mpregenperlevel REAL,
                    spellblock INTEGER,
                    spellblockperlevel REAL,
                    tags TEXT
                )
                """
            )

            for champ_data in get_champion_data():
                # values in champ_data in alphabetical order
                values = [champ_data[name] for name in sorted(list(champ_data.keys()))]

                conn.execute(
                    f"""
                    INSERT INTO Champions VALUES ({",".join(["?"] * len(champ_data))})
                    """,
                    tuple(values)
                )

            fields = []
            for fieldName, fieldType in PARTICIPANT_FIELDS.items():
                if fieldType == int:
                    fields.append(f"{fieldName} INTEGER")
                elif fieldType == str:
                    fields.append(f"{fieldName} TEXT")
                else:
                    print("unknown type:", fieldName, fieldType)

            joined_fields = ",\n".join(fields)
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS Participants (
                    {joined_fields},
                    matchId TEXT
                )
                """
            )

            conn.commit()
            return conn

        except Exception as ex:
            traceback.print_exception(type(ex), ex, ex.__traceback__)
            print("Something failed! Aborting...")
            os.remove(db_name)
            return None
    
    else:
        print(f"{db_name} already exists, won't initialize")
        return sqlite3.connect(db_name)    

def delay(func):
    def inner(*args, **kwargs):
        result = func(*args, **kwargs)
        time.sleep(DELAY)
        return result
    
    return inner


@delay
def get_player_info_by_summoner_name(summoner_name):
    url = "https://na1.api.riotgames.com"
    r = requests.get(f"{url}/lol/summoner/v4/summoners/by-name/{summoner_name}?api_key={API_KEY}")
    return r.json()


@delay
def get_matches_by_puuid(puuid):
    url = "https://americas.api.riotgames.com"
    r = requests.get(f"{url}/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=100&api_key={API_KEY}")
    return r.json()


@delay
def get_match_by_match_id(match_id):
    url = "https://americas.api.riotgames.com"
    r = requests.get(f"{url}/lol/match/v5/matches/{match_id}?api_key={API_KEY}")
    return r.json()


def process_match(data, conn):

    info = data["info"]
    meta = data["metadata"]
    winner = 100 if info["teams"][0]["win"] else 200

    # Insert information about the match:
    conn.execute("""
    INSERT INTO Matches 
    (gameVersion, matchId, gameCreation, gameDuration, gameId, winner) 
    VALUES(?, ?, ?, ?, ?, ?)
    """, 
    [info["gameVersion"], meta["matchId"], info["gameCreation"], info["gameDuration"], info["gameId"], winner])

    # Now insert information about each of the participants:
    for participant in info["participants"]:
        values = []

        for name in sorted(list(PARTICIPANT_FIELDS.keys())):
            values.append(participant[name])
        values.append(meta["matchId"])

        conn.execute(
            f"""
            INSERT INTO Participants VALUES({",".join(["?"] * (len(PARTICIPANT_FIELDS) + 1))})
            """,
            values
        )

    conn.commit()


def listen_and_commit(conn):
    match_ids = deque()
    seen_players = set()
    seen_matches = set()

    seed_player = "badgary"
    seed_info = get_player_info_by_summoner_name(seed_player)
    seen_players.add(seed_info["puuid"])

    seed_matches = get_matches_by_puuid(seed_info["puuid"])

    for match in seed_matches:
        match_ids.append(match)

    while match_ids:
        match = match_ids.popleft()

        # TODO: this is actually a hacky fix for some kind of logic
        # flaw where we try to process a match twice. I think it may
        # have something to do with how `seed_matches` gets handled.
        if match in seen_matches or match["info"]["gameMode"] != "CLASSIC":
            continue

        print(f"processing {match}, # players: {len(seen_players)}, # matches processed: {len(seen_matches)}, # matches enqueued: {len(match_ids)}")

        # Grab match information
        seen_matches.add(match)
        data = get_match_by_match_id(match)

        # Do some processing
        process_match(data, conn)

        # Get list of all players in the match and add their recent
        # match IDs to the queue:
        if len(match_ids) == 0:
            for puuid in data["metadata"]["participants"]:
                if puuid not in seen_players:
                    seen_players.add(puuid)
                    match_data = get_matches_by_puuid(puuid)
                    for match in match_data:
                        if match not in seen_matches:
                            match_ids.append(match)

if __name__ == "__main__":
    conn = maybe_init_db()
    listen_and_commit(conn)
