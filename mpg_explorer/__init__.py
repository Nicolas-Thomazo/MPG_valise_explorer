from logging import basicConfig, getLogger
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LeagueConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # CREDENTIALS
    MPG_USERNAME: str | None = Field(default=None, env="MPG_USERNAME")
    PASSWORD: str | None = Field(default=None, env="MPG_PASSWORD")

    # LEAGUE CONFIG
    LEAGUE_ID: str | None = Field(default=None, env="LEAGUE_ID")
    TEAM_NAME: str | None = Field(default=None, env="TEAM_NAME")
    RESULTS_LINK: str | None = Field(default=None, env="RESULT_LINK")
    SEASON_NUMBER: int | None = Field(default=None, env="SEASON_NUMBER")
    DIVISION: int | None = Field(default=None, env="DIVISION")
    NUMBER_PLAYERS: int | None = Field(default=None, env="NUMBER_PLAYERS")

    # CONFIG
    IS_DOCKER: bool = Field(default=True, env="IS_DOCKER")
    MATCHWEEK: list | None = Field(default=None, env="MATCHWEEK")
    AZURE_STORAGE_CONNECTION_STRING: str | None = Field(
        default=None, env="AZURE_STORAGE_CONNECTION_STRING"
    )


LEAGUE_CONFIG = LeagueConfig()


basicConfig(
    level="INFO",
    format="%(levelname)s - %(message)s",  # %(asctime)s
)
logger = getLogger("mpg-explorer")
