import json
import os

import duckdb

from utils import duckdb_helper

bonus_json_path = "utils/bonus.json"


def get_matchweeks_scrapped(league_id, division, season_nb, nb_players):
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
    duckdb_helper.azure_secret()

    query = f"""
    SELECT
        matchweek,
        COUNT(DISTINCT match_id) AS nb_games
    FROM 'azure://scrapping-exports/exports/games.parquet'
    WHERE league_id = '{league_id}'
        AND division = '{division}'
        AND season_nb = '{season_nb}'
    GROUP BY matchweek
    HAVING nb_games >= {nb_players/2}
    """
    full_matchweek_results = duckdb.query(query).fetchnumpy()
    return sorted(list(full_matchweek_results["matchweek"]))


def get_matchweeks_not_scrapped(league_id: str, division: int, season_nb: int, nb_players: int) -> list:
    """
    On récupère la liste des matchweeks déjà entièrement scrappés.
    On soustraie à la liste des matchweeks complet, pour avoir la liste des
    matchweeks par encore scrappés.

    :param league_id: _description_
    :param division_id: _description_
    :param season_number: _description_
    :param nb_players: _description_
    """
    if nb_players not in [4, 6, 8, 10]:
        raise ValueError(f"Number of players must be one of : [4, 6, 8, 10]. Received value '{nb_players}'.")

    matchweeks_scrapped = get_matchweeks_scrapped(league_id, division, season_nb, nb_players)
    all_matchweeks_not = list(range(1, (nb_players * 2) - 1))
    return list(set(all_matchweeks_not) - set(matchweeks_scrapped))
