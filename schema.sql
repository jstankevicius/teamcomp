CREATE TABLE IF NOT EXISTS Matches (
    matchId TEXT PRIMARY KEY,
    gameVersion TEXT,
    gameCreation INTEGER,
    gameDuration INTEGER,
    gameId INTEGER,
    winner INTEGER
);


CREATE TABLE IF NOT EXISTS SeenPlayers (
    summonerName TEXT PRIMARY KEY
);


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
);

CREATE TABLE IF NOT EXISTS ChampionMastery (
    championId INTEGER,
    championLevel INTEGER,
    championPoints INTEGER,
    summonerId TEXT
);

CREATE TABLE IF NOT EXISTS Participants (
    assists INTEGER,
    baronKills INTEGER,
    championId INTEGER,
    damageDealtToBuildings INTEGER,
    damageDealtToObjectives INTEGER,
    damageDealtToTurrets INTEGER,
    damageSelfMitigated INTEGER,
    deaths INTEGER,
    detectorWardsPlaced INTEGER,
    dragonKills INTEGER,
    goldEarned INTEGER,
    goldSpent INTEGER,
    kills INTEGER,
    magicDamageDealt INTEGER,
    magicDamageDealtToChampions INTEGER,
    magicDamageTaken INTEGER,
    neutralMinionsKilled INTEGER,
    physicalDamageDealt INTEGER,
    physicalDamageDealtToChampions INTEGER,
    physicalDamageTaken INTEGER,
    sightWardsBoughtInGame INTEGER,
    summonerId TEXT,
    summonerName TEXT,
    teamId INTEGER,
    teamPosition TEXT,
    timeCCingOthers INTEGER,
    totalDamageDealt INTEGER,
    totalDamageDealtToChampions INTEGER,
    totalDamageShieldedOnTeammates INTEGER,
    totalDamageTaken INTEGER,
    totalHeal INTEGER,
    totalHealsOnTeammates INTEGER,
    totalMinionsKilled INTEGER,
    totalTimeCCDealt INTEGER,
    trueDamageDealt INTEGER,
    trueDamageDealtToChampions INTEGER,
    trueDamageTaken INTEGER,
    turretKills INTEGER,
    turretTakedowns INTEGER,
    visionScore INTEGER,
    visionWardsBoughtInGame INTEGER,
    wardsKilled INTEGER,
    wardsPlaced INTEGER,
    matchId TEXT
);

