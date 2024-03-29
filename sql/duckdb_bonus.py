import json

import duckdb
import polars

bonus_json_path = "utils/bonus.json"


def get_json_bonus():
    with open("utils/bonus.json") as js:
        return json.load(js)


def get_total_team_bonus_played(team_id: str) -> dict:
    results = []
    team_id = team_id.replace("'","''")
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
            SUM({prefix}tonton) AS tonton,
            SUM({prefix}decat) AS decat
        FROM 'exports/games.parquet' G
        INNER JOIN 'exports/bonus.parquet' B ON G.match_id = B.match_id
        WHERE {prefix}teamid = '{team_id}'
        GROUP BY {prefix}teamid
        """
            ).fetchnumpy()
        )
    return {k: int((results[0].get(k, 0) or 0) + (results[1].get(k, 0) or 0)) for k in results[0]}


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

    bonus = get_json_bonus()
    start_bonus = bonus[f"{nb_players}_players"]

    bonus_played = get_total_team_bonus_played(team_id)

    return {k: start_bonus.get(k, 0) - bonus_played.get(k, 0) for k in bonus_played}
