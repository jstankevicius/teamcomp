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
import random
import sqlite3
import threading
import time
import traceback

import requests


CHAMPION_DATA_URL = "https://ddragon.leagueoflegends.com/cdn/12.19.1/data/en_US/champion.json"
DELAY = 120 / 100 # Limit is 100 requests every 2 minutes, or 20 requests in 1
                  # second
REQUEST_RETRY_COUNT = 5 # How many times we will re-send a request before giving
                        # up

class SummonerNotFoundException(Exception):
    pass


def get_keys_from_file(file_name):
    """
    Returns a list of all Riot API keys from a text file.
    """

    with open(file_name, encoding="utf-8") as file:
        return [key.strip() for key in file.readlines() if key[:5] == "RGAPI"]


def get_with_retry(url):
    retry_attempts = 0
    req = requests.get(url)
    time.sleep(DELAY)

    if req.status_code == 403:
        logging.error("Request for %s received status code 403, shutting down", url)
        exit(1)

    while req.status_code in (429, 500, 503) and retry_attempts < REQUEST_RETRY_COUNT:
        logging.warning("Received status code %d for %s, retrying",
            req.status_code, url)
        time.sleep(5)
        req = requests.get(url)
        retry_attempts += 1

    return req


def get_player_info_by_summoner_name(summoner_name, api_key):
    """
    Returns a player's account information given a summoner name.

    Reference:
    https://developer.riotgames.com/apis#summoner-v4/GET_getBySummonerName
    """

    url = "https://na1.api.riotgames.com"
    endpoint = "lol/summoner/v4/summoners/by-name"
    full_url = f"{url}/{endpoint}/{summoner_name}?api_key={api_key}"
    req = get_with_retry(full_url)

    if req.status_code == 404 and "summoner not found" in req.json()["status"]["message"]:
        raise SummonerNotFoundException(summoner_name);

    req.raise_for_status()

    return req.json()


def get_matches_by_puuid(puuid, api_key):
    """
    Returns a player's most recent 100 matches given the player's PUUID.

    Reference:
    https://developer.riotgames.com/apis#match-v5/GET_getMatchIdsByPUUID
    """

    url = "https://americas.api.riotgames.com"
    endpoint = "lol/match/v5/matches/by-puuid"
    req = get_with_retry(f"{url}/{endpoint}/{puuid}/ids?start=0&count=100&api_key={api_key}")
    req.raise_for_status()

    return req.json()


def get_match_by_match_id(match_id, api_key):
    """
    Returns detailed information about a match given a match ID.

    Reference:
    https://developer.riotgames.com/apis#match-v5/GET_getMatch
    """

    url = "https://americas.api.riotgames.com"
    endpoint = "lol/match/v5/matches"
    req = get_with_retry(f"{url}/{endpoint}/{match_id}?api_key={api_key}")
    req.raise_for_status()

    return req.json()


def get_champion_mastery(encrypted_summoner_id, api_key):
    """
    Returns champion mastery information for a summoner given an encrypted
    summoner ID.

    Reference:
    https://developer.riotgames.com/apis#champion-mastery-v4/GET_getAllChampionMasteries
    """

    url = "https://na1.api.riotgames.com"
    endpoint = "lol/champion-mastery/v4/champion-masteries/by-summoner"
    req = get_with_retry(f"{url}/{endpoint}/{encrypted_summoner_id}?api_key={api_key}")
    req.raise_for_status()

    return req.json()


def get_champion_data():
    """
    Gets relevant data about all current champions in League of Legends from a
    Riot endpoint and returns the result as a list of dictionaries, one dict per
    champion.
    """

    req = requests.get(CHAMPION_DATA_URL)
    result = []
    tags = set()

    # Collect all tags:
    for data in req.json()["data"].values():
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


def maybe_init_db_from_schema(db_name="league.db", schema="schema.sql"):
    """
    Initializes the database if it does not exist.
    """
    if os.path.exists(db_name):
        logging.info("%s already exists, won't initialize", db_name)
        return

    try:
        logging.info("%s does not exist, initializing schema", db_name)
        conn = sqlite3.connect(db_name)

        with open(schema, encoding="utf-8") as file:
            lines = file.read()
            conn.executescript(lines)

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

        conn.commit()

    except Exception as ex:
        traceback.print_exception(type(ex), ex, ex.__traceback__)
        logging.error("Caught a %s while initializing database, aborting",
            ex.__class__.__qualname__)
        os.remove(db_name)


def process_match(data, conn, seen_masteries, api_key):
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
    conn.commit()

    # This returns a list of tuples that looks something like this:
    # [(0, 'assists', 'INTEGER', 0, None, 0),
    #  (1, 'baronKills', 'INTEGER', 0, None, 0),
    #  (2, 'championId', 'INTEGER', 0, None, 0),
    #  ... ]
    # NOTE: Hacky! But allows us to use the schema to *mostly* determine which
    # fields we want to grab from the JSON.
    fields = [field for field in
        conn.execute("PRAGMA table_info('Participants')").fetchall()
        if field [1] != "matchId"]

    for participant in info["participants"]:
        values = []

        for field in sorted(fields, key=lambda x: x[1]):
            values.append(participant[field[1]])
        values.append(meta["matchId"])

        conn.execute(
            f"""
            INSERT INTO Participants VALUES({
                ",".join(["?"] * (len(fields) + 1))
            })
            """,
            values)
        conn.commit()

        # Get each participant's champion mastery info (if we don't have it
        # already)
        if participant["summonerName"] not in seen_masteries:
            mastery_list = get_champion_mastery(participant["summonerId"],
                api_key)

            for mastery in mastery_list:
                conn.execute("INSERT INTO ChampionMastery VALUES(?,?,?,?)",
                    (mastery["championId"], mastery["championLevel"],
                    mastery["championPoints"], participant["summonerName"]))
            seen_masteries.add(participant["summonerName"])

            conn.commit()

    logging.debug("Processed match data for %s in %f seconds", meta["matchId"],
        time.time() - now)


def add_player_match_history(conn, name, match_ids, seen_players, seen_matches,
                             api_key):
    """
    Given `seed_player` (a PUUID), gets the most recent 100 matches played by
    the player, adds the player to `seen_players`, and queues their matches in
    `match_ids`.
    """
    logging.info("Adding match history for %s", name)
    seen_players.add(name)

    try:
        puuid = get_player_info_by_summoner_name(name, api_key)["puuid"]
    except SummonerNotFoundException as err:
        raise err


    conn.execute("INSERT INTO SeenPlayers VALUES(?);", [name])
    conn.commit()

    match_data = get_matches_by_puuid(puuid, api_key)

    for match in match_data:
        if match not in seen_matches:
            match_ids.append(match)


def listen_and_commit(seed_name, seen_players, seen_matches, seen_masteries,
                      lock, api_key):
    """
    Per-thread method that performs a breadth-first search over the player
    graph. `seen_players` consists of players whose match history has already
    been fetched, and `seen_matches` consists of matches that have already been
    processed; both are protected by `lock`.

    For now, each thread runs until it encounters an exception, after which it
    will shut down.
    """
    last_valid_match = None

    conn = sqlite3.connect("league.db", timeout=60)
    match_ids = collections.deque()

    lock.acquire()
    add_player_match_history(conn, seed_name, match_ids, seen_players,
        seen_matches, api_key)
    lock.release()

    while True:

        try:
            match = match_ids.popleft()

            # NOTE: I'm pretty sure this being necessary is the result of a bug.
            lock.acquire()
            if match in seen_matches:
                lock.release()
                continue

            seen_matches.add(match)

            num_matches = conn.execute("SELECT COUNT(*) FROM Matches;").fetchone()[0]

            if len(seen_matches) % 100 == 0:
                logging.info("Processed %d matches (%d committed)",
                    len(seen_matches), num_matches)

            lock.release()

            data = get_match_by_match_id(match, api_key)

            if not (data["info"]["gameMode"] == "CLASSIC"
                and data["info"]["gameType"] == "MATCHED_GAME"
                and all([p["summonerId"] != "BOT" for p in data["info"]["participants"]])):
                logging.debug("Match %s gamemode: %s; gametype: %s, skipping",
                    match, data["info"]["gameMode"], data["info"]["gameType"])
            else:
                last_valid_match = data if data else last_valid_match
                process_match(data, conn, seen_masteries, api_key)

        except requests.HTTPError as err:
            traceback.print_exception(type(err), err, err.__traceback__)
            logging.error("Received some other HTTPError: %s", str(err))

        except requests.ConnectionError as err:
            traceback.print_exception(type(err), err, err.__traceback__)
            logging.error("Received a ConnectionError: %s", str(err))

        except IndexError as err:
            traceback.print_exception(type(err), err, err.__traceback__)

            if len(match_ids) == 0:
                logging.error("Popped from an empty queue. Continuing")

        except KeyError as err:
            # KeyErrors can (generally) be ignored. If the data does not fit the
            # format we expect it to fit (i.e. a key is missing), we won't
            # bother processing it and will skip.
            traceback.print_exception(type(err), err, err.__traceback__)
            logging.error("KeyError: %s", str(err))

        except Exception as err:
            traceback.print_exception(type(err), err, err.__traceback__)
            logging.error("Some other exception: %s", str(err))

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
                for participant in data["info"]["participants"]:
                    name = participant["summonerName"]
                    if name not in seen_players:
                        try:
                            add_player_match_history(conn, name, match_ids,
                                seen_players, seen_matches, api_key)
                        except SummonerNotFoundException as err:
                            traceback.print_exception(type(err), err, err.__traceback__)
                            logging.error("Could not find summoner %s, skipping", str(err))

                logging.info("Added %d new matches to queue", len(match_ids))
                lock.release()


def main():
    logging.basicConfig(
        format="[%(asctime)s][%(levelname)s][tid %(thread)d] %(message)s",
        datefmt="%H:%M:%S",
        filename="ingest.log",
        filemode="w+",
        level=logging.INFO)

    maybe_init_db_from_schema()

    keys = get_keys_from_file("keys.txt")

    # Re-populate seen_players, seen_matches, and seen_masteries if we can
    conn = sqlite3.connect("league.db")

    seen_players = set([p[0]
        for p in conn.execute("SELECT summonerName from SeenPlayers;").fetchall()])

    seen_matches = set([m[0]
        for m in conn.execute("SELECT matchId FROM Matches;").fetchall()])

    seen_masteries = set(m[0]
        for m in conn.execute("SELECT DISTINCT summonerName from ChampionMastery;").fetchall())

    logging.info("Seen players (match history): %d", len(seen_players))
    logging.info("Seen matches: %d", len(seen_matches))
    logging.info("Seen players (mastery): %d", len(seen_masteries))

    lock = threading.Lock()

    if len(keys) == 0:
        logging.error("Could not find any keys!")
        exit(1)

    threads = []

    # NOTE: Edit this list! There should be one player for each key in keys.txt.
    players = [
        "Murik",
        "TwTv Secillia",
        "BelliB0lt",
        "i play sova alot",
        "Yuumbee"
    ]

    # If this isn't our first time populating this DB, pick a player at random
    # to be the seed player.
    if len(seen_matches) > 0:
        pool = [p[0] for p in
            conn.execute("SELECT DISTINCT summonerName from Participants;").fetchall()]

        players = random.sample(pool, len(keys))
        while any([p in seen_players for p in players]):
            players = random.sample(pool, len(keys))

    assert len(players) == len(keys)

    for key, player in zip(keys, players):
        thread = threading.Thread(target=listen_and_commit,
            args=(player, seen_players, seen_matches, seen_masteries, lock,
                  key))

        threads.append(thread)
        logging.info("Starting thread for key %s", key)
        thread.start()

    for thread in threads:
        thread.join()


if __name__ == "__main__":
    while True:
        try:
            main()
            time.sleep(30)
        except Exception as err:
            logging.error("Exception escaped main loop: %s", str(err))
            logging.error("RESTARTING")

