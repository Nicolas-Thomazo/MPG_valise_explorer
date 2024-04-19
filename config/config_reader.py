from pydantic import Field
from pydantic_settings import BaseSettings


class LeagueConfig(BaseSettings):
    USE_VAR_ENV: bool = Field(default=False, env="USE_VAR_ENV")
    MAIL: str = Field(..., env="MAIL")
    PASSWORD: str = Field(..., env="PASSWORD")
    IS_DOCKER: bool = Field(default=True, env="IS_DOCKER")
    LEAGUE_ID: str = Field(..., env="LEAGUE_ID")
    RESULTS_LINK: str = Field(..., env="RESULTS_LINK")
    SEASON_NB: int = Field(..., env="SEASON_NB")
    DIVISION: int = Field(..., env="DIVISION")
    NB_PLAYERS: int = Field(..., env="NB_PLAYERS")
    MATCHWEEK: int = Field(..., env="MATCHWEEK")
    TEAM: str | None = Field(default=None, env="TEAM")
    AZURE_STORAGE_CONNECTION_STRING: str = Field(..., env="AZURE_STORAGE_CONNECTION_STRING")


def get_config():
    league_config = LeagueConfig()
    return league_config.model_dump()
