"""Column names for league match dataframes."""

from enum import StrEnum


class MatchColumn(StrEnum):
    """Canonical dataframe columns used for league match rows."""

    match_id = "match_id"
    match_url = "match_url"
    league_id = "league_id"
    division = "division"
    season_number = "season_number"
    matchweek = "matchweek"
    match_played = "match_played"
    error_in_scrapping = "error_in_scrapping"
    home_team_name = "home_team_name"
    home_total_goals = "home_total_goals"
    home_mpg_goals = "home_mpg_goals"
    home_real_goals = "home_real_goals"
    home_bonus = "home_bonus"
    visitor_team_name = "visitor_team_name"
    visitor_total_goals = "visitor_total_goals"
    visitor_mpg_goals = "visitor_mpg_goals"
    visitor_real_goals = "visitor_real_goals"
    visitor_bonus = "visitor_bonus"
