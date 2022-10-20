"""
The ingest module, responsible for fetching data from the Riot Games API and
adding it to the database.

This module utilizes multiple threads of execution (concurrent, not parallel) to
maximize request throughput. It will instantiate a separate thread for each API
key. Each thread performs a breadth-first search over the player graph by adding 
each player's past match IDs to a queue. Only matched games on Summoner's Rift
are considered, and the rest are skipped. 

An important goal of this module is to continue running each thread for as long
as possible. Because of this, many exceptions, like KeyErrors, IndexErrors, and
certain kinds of HTTPErrors are ignored (or recovered from) where they can be.
"""

import collections
import logging
import os
import sqlite3
import threading
import time
import traceback

import requests


CHAMPION_DATA_URL = "https://ddragon.leagueoflegends.com/cdn/12.19.1/data/en_US/champion.json"
DELAY = 120 / 100 # Limit is 100 requests every 2 minutes, or 20 requests in 1 
                  # second

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
    """
    Decorator that pauses for `DELAY` seconds after `func` is executed. This is
    used to avoid being ratelimited by the RG API.
    """

    def inner(*args, **kwargs):
        result = func(*args, **kwargs)
        time.sleep(DELAY)
        return result
    
    return inner


@delay
def get_player_info_by_summoner_name(summoner_name, api_key):
    """
    Returns a player's account information given a summoner name.
    
    Reference: 
    https://developer.riotgames.com/apis#summoner-v4/GET_getBySummonerName
    """

    url = "https://na1.api.riotgames.com"
    r = requests.get(f"{url}/lol/summoner/v4/summoners/by-name/{summoner_name}?api_key={api_key}")
    r.raise_for_status()
    return r.json()


@delay
def get_matches_by_puuid(puuid, api_key):
    """
    Returns a player's most recent 100 matches given the player's PUUID.

    Reference:
    https://developer.riotgames.com/apis#match-v5/GET_getMatchIdsByPUUID
    """

    url = "https://americas.api.riotgames.com"
    r = requests.get(f"{url}/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=100&api_key={api_key}")
    r.raise_for_status()
    return r.json()


@delay
def get_match_by_match_id(match_id, api_key):
    """
    Returns detailed information about a match given a match ID.

    Reference:
    https://developer.riotgames.com/apis#match-v5/GET_getMatch
    """

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
    
    r = requests.get(CHAMPION_DATA_URL)
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
    assert len(tags) == 6
    return result


def maybe_init_db(db_name="league.db"):
    """
    Initializes the database if it does not exist.
    """
    if os.path.exists(db_name):
        logging.info("%s already exists, won't initialize", db_name)
        return

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
            values = [champ_data[name] 
                for name in sorted(list(champ_data.keys()))]

            conn.execute(
                f"""
                INSERT INTO Champions VALUES ({
                    ",".join(["?"] * len(champ_data))
                })
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
                logging.error("Unknown type '%s' for field '%s'", 
                    str(field_type), field_name)

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
        logging.error("Caught a %s while initializing database, aborting", 
            ex.__class__.__qualname__)
        os.remove(db_name)


def process_match(data, conn):
    """
    Given match data as retrieved by `get_match_by_id()`, extracts relevant data
    fields and commits them to the database using `conn` (a sqlite3 connection).
    """

    now = time.time()

    info = data["info"]
    meta = data["metadata"]
    winner = 100 if info["teams"][0]["win"] else 200

    # Insert information about the match:
    conn.execute(
        """
        INSERT INTO Matches 
        (gameVersion, matchId, gameCreation, gameDuration, gameId, winner) 
        VALUES(?, ?, ?, ?, ?, ?)
        """, 
        [info["gameVersion"], meta["matchId"], info["gameCreation"], 
        info["gameDuration"], info["gameId"], winner])

    # Now insert information about each of the participants:
    for participant in info["participants"]:
        values = []

        for name in sorted(list(PARTICIPANT_FIELDS.keys())):
            values.append(participant[name])
        values.append(meta["matchId"])

        conn.execute(
            f"""
            INSERT INTO Participants VALUES({
                ",".join(["?"] * (len(PARTICIPANT_FIELDS) + 1))
            })
            """,
            values)

    conn.commit()
    logging.debug("Processed match data for %s in %f seconds", meta["matchId"], 
        time.time() - now)


def add_player_match_history(puuid, match_ids, seen_players, seen_matches, 
                             api_key):
    """
    Given `seed_player` (a PUUID), gets the most recent 100 matches played by
    the player, adds the player to `seen_players`, and queues their matches in
    `match_ids`.
    """

    logging.info("Adding match history for PUUID %s", puuid)

    seen_players.add(puuid)
    match_data = get_matches_by_puuid(puuid, api_key)

    for match in match_data:
        if match not in seen_matches:
            match_ids.append(match)


def listen_and_commit(seed_player, seen_players, seen_matches, lock, api_key):
    """
    Per-thread method that performs a breadth-first search over the player
    graph. `seen_players` consists of players whose match history has already
    been fetched, and `seen_matches` consists of matches that have already been
    processed; both are protected by `lock`.

    For now, each thread runs until it encounters an exception, after which it
    will shut down.
    """

    last_valid_match = None

    conn = sqlite3.connect("league.db")
    match_ids = collections.deque()
    seed_puuid = get_player_info_by_summoner_name(seed_player, api_key)["puuid"]

    lock.acquire()
    add_player_match_history(seed_puuid, match_ids, seen_players, seen_matches, 
        api_key);
    lock.release()

    while True:

        try:
            match = match_ids.popleft()
            
            # TODO: I'm pretty sure this being necessary is the result of a bug.
            lock.acquire()
            if match in seen_matches:
                lock.release()

                # TODO: This can cause us to skip the `finally` branch when 
                # we need to repopulate the queue. If len(match_ids) == 0 but
                # we go here, the queue will be empty the next time around. For
                # now, we'll catch an IndexError so we can repopulate the queue
                # in this scenario.
                continue

            seen_matches.add(match)
            lock.release()

            data = get_match_by_match_id(match, api_key)

            lock.acquire()
            if len(seen_matches) % 10 == 0:
                logging.info("Processed %d matches", len(seen_matches))
            lock.release()

            if not (data["info"]["gameMode"] == "CLASSIC" 
                and data["info"]["gameType"] == "MATCHED_GAME"):
                logging.debug("Match %s gamemode: %s; gametype: %s, skipping", 
                    match, data["info"]["gameMode"], data["info"]["gameType"])
            else:
                last_valid_match = data
                process_match(data, conn)

        except requests.HTTPError as err:

            if lock.locked():
                lock.release()

            # TODO: Hacky way to check for 503. Could probably pass around the
            # returned status code.
            if "503" in str(err):
                logging.warning("Received status 503; pausing for 30s")
                time.sleep(30)
            else:            
                traceback.print_exception(type(err), err, err.__traceback__)
                logging.error("Received non-503 HTTPError, shutting down")
                exit(1)

        except IndexError as err:
            if lock.locked():
                lock.release()
            
            traceback.print_exception(type(err), err, err.__traceback__)

            if len(match_ids) == 0:
                logging.warning("Popped from an empty queue. Continuing")
            else:
                logging.error("Received an IndexError, but don't know why. Shutting down")
                exit(1)

        except KeyError as err:
            # KeyErrors can (generally) be ignored. If the data does not fit the
            # format we expect it to fit (i.e. a key is missing), we won't 
            # bother processing it and will skip.
            if lock.locked():
                lock.release()
            
            traceback.print_exception(type(err), err, err.__traceback__)
            logging.warning("Encountered a KeyError while parsing data, skipping")

        finally:
            # Get list of all players in the match and add their recent match 
            # IDs to the queue.

            if len(match_ids) == 0:
                lock.acquire()
                logging.info("Match queue is empty, enqueuing more")

                # It may be the case that `data` is not a valid gamemode or game
                # type (for example, we could have a custom game with only 1
                # player). To account for this, we keep track of "valid" matches
                # in `last_valid_match`, so that when we need to get a valid
                # player list we have one available.
                data = last_valid_match
                for puuid in data["metadata"]["participants"]:
                    if puuid not in seen_players:
                        add_player_match_history(puuid, match_ids, seen_players,
                            seen_matches, api_key)
                
                logging.info("Added %d new matches to queue", len(match_ids))
                lock.release()


def main():
    logging.getLogger().setLevel(logging.INFO)
    logging.basicConfig(
        format="[%(asctime)s][%(levelname)s][tid %(thread)d] %(message)s", 
        datefmt="%H:%M:%S")

    maybe_init_db()

    keys = get_keys_from_file("keys.txt");
    seen_players = set()
    seen_matches = set()
    lock = threading.Lock()

    if len(keys) == 0:
        logging.error("Could not find any keys!")
        exit(1);
    
    threads = []

    # NOTE: Edit this list! There should be one player for each key in keys.txt.
    players = ["badgary"]

    assert len(players) == len(keys)

    for key, player in zip(keys, players):
        thread = threading.Thread(target=listen_and_commit, 
            args=(player, seen_players, seen_matches, lock, key))
        
        threads.append(thread)
        logging.info("Starting thread for key %s", key)
        thread.start()

    for t in threads:
        t.join()


if __name__ == "__main__":
    main()