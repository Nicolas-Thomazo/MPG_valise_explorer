from pydantic import BaseModel


class Match(BaseModel):
    """
    Match model to store match information

    Args:
        BaseModel (BaseModel): Pydantic BaseModel
    """

    match_id: str
    league_id: str
    division: int
    season_nb: int
    h_teamid: str
    v_teamid: str
    h_total_goals: int
    h_mpg_goals: int
    h_real_goals: int
    h_own_goals: int
    h_red_cards: int
    v_total_goals: int
    v_mpg_goals: int
    v_real_goals: int
    v_own_goals: int
    v_red_cards: int
    matchweek: int
