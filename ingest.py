import requests
import logging
import os
import sqlite3
import threading
import time
import traceback
from collections import deque


logging.getLogger().setLevel(logging.INFO)
logging.basicConfig(format="[%(asctime)s][%(levelname)s][tid %(thread)d] %(message)s", datefmt="%H:%M:%S")


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


def get_keys_from_file(file_name):
    """
    Returns a list of all Riot API keys from a text file.
    """
    with open(file_name) as f:
        return [key.strip() for key in f.readlines() if key[:5] == "RGAPI"]


def delay(func):

    def inner(*args, **kwargs):
        result = func(*args, **kwargs)
        time.sleep(DELAY)
        return result
    
    return inner


@delay
def get_player_info_by_summoner_name(summoner_name, api_key):
    url = "https://na1.api.riotgames.com"
    r = requests.get(f"{url}/lol/summoner/v4/summoners/by-name/{summoner_name}?api_key={api_key}")
    r.raise_for_status()
    return r.json()


@delay
def get_matches_by_puuid(puuid, api_key):
    url = "https://americas.api.riotgames.com"
    r = requests.get(f"{url}/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=100&api_key={api_key}")
    r.raise_for_status()
    return r.json()


@delay
def get_match_by_match_id(match_id, api_key):
    url = "https://americas.api.riotgames.com"
    r = requests.get(f"{url}/lol/match/v5/matches/{match_id}?api_key={api_key}")
    r.raise_for_status()
    return r.json()


def get_champion_data():
    """
    Gets relevant data about all current champions in League of Legends from a 
    Riot endpoint and returns the result as a list of dictionaries, one dict per
    champion.
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
            logging.info("%s does not exist, initializing schema", db_name)
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
            for field_name, field_type in PARTICIPANT_FIELDS.items():
                if field_type == int:
                    fields.append(f"{field_name} INTEGER")
                elif field_type == str:
                    fields.append(f"{field_name} TEXT")
                else:
                    logging.error("Unknown type '%s' for field '%s'", str(field_type), field_name)

            joined_fields = ",\n".join(fields)
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS Participants (
                    {joined_fields},
                    matchId TEXT
                )
                """
            )

            conn.commit()

        except Exception as ex:
            traceback.print_exception(type(ex), ex, ex.__traceback__)
            logging.error("Caught a %s while initializing database, aborting", ex.__class__.__qualname__)
            os.remove(db_name)
    
    else:
        logging.info("%s already exists, won't initialize", db_name)


def process_match(data, conn):
    now = time.time()

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
    logging.debug("Processed match data for %s in %f seconds", meta["matchId"], time.time() - now)


def init_seed_data(seed_player, match_ids, seen_players, seen_matches, api_key):
    seed_player = seed_player
    seed_info = get_player_info_by_summoner_name(seed_player, api_key)
    seen_players.add(seed_info["puuid"])

    seed_matches = get_matches_by_puuid(seed_info["puuid"], api_key)

    for match in seed_matches:
        match_ids.append(match)


def listen_and_commit(match_ids, seen_players, seen_matches, api_key):
    conn = sqlite3.connect("league.db")

    while True:
        try:
            match = match_ids.popleft()
            
            # TODO: I'm pretty sure this being necessary is the result of a bug.
            if match in seen_matches:
                continue

            # Grab match information
            seen_matches.add(match)
            data = get_match_by_match_id(match, api_key)

            if len(seen_matches) % 10 == 0:
                logging.info("Processed %d matches", len(seen_matches))

            if data["info"]["gameMode"] != "CLASSIC":
                logging.debug("Match %s gamemode is %s, skipping", match, data["info"]["gameMode"])
                continue
                
            # Do some processing
            process_match(data, conn)

            # Get list of all players in the match and add their recent
            # match IDs to the queue. This might be seen by multiple threads
            # simultaneously, but that's OK - we just care that the queue gets
            # refilled, and if threads add more matches than necessary, all the
            # better for us.
            # TODO: Make this threadsafe; there's a small chance for a race
            # condition that leads to a DB error.
            if len(match_ids) == 0:
                logging.info("Match queue is empty, enqueuing more")
                queue_length = len(match_ids)

                for puuid in data["metadata"]["participants"]:
                    if puuid not in seen_players:
                        seen_players.add(puuid)
                        match_data = get_matches_by_puuid(puuid, api_key)
                        for match in match_data:
                            if match not in seen_matches:
                                match_ids.append(match)
                
                logging.info("Added %d new matches to queue", len(match_ids) - queue_length)

        except requests.HTTPError as error:
            logging.error("Received HTTPError, shutting down")
            exit(1)
        
        except Exception as ex:
            traceback.print_exception(type(ex), ex, ex.__traceback__)
            logging.error("Caught a %s while fetching data, shutting down", ex.__class__.__qualname__)
            exit(1)


def main():
    maybe_init_db()

    keys = get_keys_from_file("keys.txt");
    match_ids = deque()
    seen_players = set()
    seen_matches = set()

    if len(keys) == 0:
        logging.error("Could not find any keys!")
        exit(1);

    init_seed_data("badgary", match_ids, seen_players, seen_matches, keys[0])
    
    threads = []

    for key in keys:
        thread = threading.Thread(target=listen_and_commit, args=(match_ids, seen_players, seen_matches, key))
        threads.append(thread)
        logging.info("Starting thread for key %s", key)
        thread.start()

    for t in threads:
        t.join()


if __name__ == "__main__":
    main()