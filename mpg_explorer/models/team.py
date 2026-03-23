from pydantic import BaseModel


class Team(BaseModel):
    team_id: str
    mpg_manager: str
    league_id: str
    division: int
    team_name: str
