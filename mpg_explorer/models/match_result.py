from pydantic import BaseModel
from mpg_explorer.models.bonus import BonusName


class Match(BaseModel):
    """
    Match model to store match information

    Args:
        BaseModel (BaseModel): Pydantic BaseModel
    """

    match_id: str
    league_id: str
    division: int
    season_number: int
    matchweek: int
    # Home
    home_team_id: str
    home_total_goals: int
    home_mpg_goals: int | None = None
    home_real_goals: int | None = None
    home_bonus: list[BonusName]
    # Visitor
    visitor_team_id: str
    visitor_total_goals: int
    visitor_mpg_goals: int | None = None
    visitor_real_goals: int | None = None
    visitor_bonus: list[BonusName]
