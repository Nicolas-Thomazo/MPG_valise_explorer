import duckdb

from utils import duckdb_helper
from utils.bonus import bonus
from utils.duckdb_helper import azure_secret


def get_json_bonus():
    return bonus


def get_total_team_bonus_played(team_id: str) -> dict:
    results = []
    team_id = team_id.replace("'", "''")
    for prefix in ["h_", "v_"]:
        results.append(
            duckdb.query(
                f"""
        SELECT
            SUM({prefix}valise) AS valise, 
            SUM({prefix}ubereats) AS ubereats,
            SUM({prefix}suarez) AS suarez,
            SUM({prefix}zahia) AS zahia,
            SUM({prefix}miroir) AS miroir,
            SUM({prefix}chapron) AS chapron,
            SUM({prefix}tontonpat) AS tontonpat,
            SUM({prefix}decat) AS decat
        FROM 'azure://scrapping-exports/exports/games.parquet' G
        INNER JOIN 'azure://scrapping-exports/exports/bonus.parquet' B ON G.match_id = B.match_id
        WHERE {prefix}teamid = '{team_id}'
        GROUP BY {prefix}teamid
        """
            ).fetchnumpy()
        )
    return {k: int((results[0].get(k, 0) or 0) + (results[1].get(k, 0) or 0)) for k in results[0]}


def get_all_team_ids(league_id, season_nb):
    """
    Retourne tout les ids des joueurs d'une saison en particulier

    :param league_id: _description_
    :param season_nb: _description_
    """
    query = f"""
    SELECT 
        DISTINCT(h_teamid)
    FROM 'azure://scrapping-exports/exports/games.parquet' G
    WHERE G.league_id = '{league_id}'
    AND G.season_nb = '{season_nb}'
    """
    return duckdb.query(query).fetchnumpy()


def get_remaining_bonus_player(team_id: str, nb_players: int):
    """
    Returns the number of bonuses remaining for the team in a particular league

    1- Retrieves the number of starting bonuses according to league size
    2- Returns the number of bonuses played since the start of the season
    3- Return the difference between the two

    :param team_id: team id (unique for each league, division, season_nb)
    :param nb_players: number players in the league, to know how much bonus the player had in the beginning
    :raises ValueError: Raise an error if nb players in not possible
    :return: dict with number of remaining bonus
    """
    if nb_players not in [4, 6, 8, 10]:
        raise ValueError("Number of players must be one of : [4, 6, 8, 10]")

    duckdb_helper.azure_secret()
    bonus = get_json_bonus()
    start_bonus = bonus[f"{nb_players}_players"]

    bonus_played = get_total_team_bonus_played(team_id)

    return {k: start_bonus.get(k, 0) - bonus_played.get(k, 0) for k in bonus_played}


def get_all_players_bonus(league_id, season_nb, nb_players: int):
    """
    Returns the number of bonuses remaining for the team in a particular league

    1- Retrieves the number of starting bonuses according to league size
    2- Returns the number of bonuses played since the start of the season
    3- Return the difference between the two

    :param team_id: team id (unique for each league, division, season_nb)
    :param nb_players: number players in the league, to know how much bonus the player had in the beginning
    :raises ValueError: Raise an error if nb players in not possible
    :return: dict with number of remaining bonus
    """
    if nb_players not in [4, 6, 8, 10]:
        raise ValueError("Number of players must be one of : [4, 6, 8, 10]")

    azure_secret()
    bonus = get_json_bonus()
    start_bonus = bonus[f"{nb_players}_players"]

    team_ids = get_all_team_ids(league_id=league_id, season_nb=season_nb)["h_teamid"]

    full_text = ""
    for team_id in team_ids:
        bonus_played = get_total_team_bonus_played(team_id)
        remaining_bonus = {k: start_bonus.get(k, 0) - bonus_played.get(k, 0) for k in bonus_played}
        # print(f"Remaining bonuses of {team_id.split('_')[2:]} are:")
        full_text = full_text + f"<p>Remaining bonuses of {'_'.join(team_id.split('_')[2:])} are:"
        for bonus in remaining_bonus:
            full_text = full_text + f"{bonus} : {remaining_bonus[bonus]}<br>"
        full_text = full_text + "</p>"
    return full_text
