from pydantic import Field
from pydantic_settings import BaseSettings


class LeagueConfig(BaseSettings):
    USE_VAR_ENV: bool | None = Field(default=False, env="USE_VAR_ENV")
    MAIL: str | None = Field(default=None, env="MAIL")
    PASSWORD: str | None = Field(default=None, env="PASSWORD")
    IS_DOCKER: bool = Field(default=True, env="IS_DOCKER")
    LEAGUE_ID: str | None = Field(default=None, env="LEAGUE_ID")
    RESULTS_LINK: str | None = Field(default=None, env="RESULTS_LINK")
    SEASON_NB: int | None = Field(default=None, env="SEASON_NB")
    DIVISION: int | None = Field(default=None, env="DIVISION")
    NB_PLAYERS: int | None = Field(default=None, env="NB_PLAYERS")
    MATCHWEEK: list | None = Field(default=None, env="MATCHWEEK")
    TEAM: str | None = Field(default=None, env="TEAM")
    AZURE_STORAGE_CONNECTION_STRING: str | None = Field(default=None, env="AZURE_STORAGE_CONNECTION_STRING")


def get_config():
    league_config = LeagueConfig()
    return league_config.model_dump()
