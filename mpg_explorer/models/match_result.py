from pydantic import BaseModel, Field
from mpg_explorer.models.bonus import BonusName


class Match(BaseModel):
    """
    Match model to store match information

    Args:
        BaseModel (BaseModel): Pydantic BaseModel
    """

    match_id: str
    match_url: str | None = None
    league_id: str
    division: int
    season_number: int
    matchweek: int
    match_played: bool = True
    error_in_scrapping: bool = False
    # Home
    home_team_name: str | None = None
    home_total_goals: int | None = None
    home_mpg_goals: int | None = None
    home_real_goals: int | None = None
    home_bonus: list[BonusName] = Field(default_factory=list)
    # Visitor
    visitor_team_name: str | None = None
    visitor_total_goals: int | None = None
    visitor_mpg_goals: int | None = None
    visitor_real_goals: int | None = None
    visitor_bonus: list[BonusName] = Field(default_factory=list)
