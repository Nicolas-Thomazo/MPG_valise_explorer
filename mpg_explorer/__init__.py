from logging import basicConfig, getLogger
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LeagueConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # CREDENTIALS
    MPG_USERNAME: str = Field(env="MPG_USERNAME")
    MPG_PASSWORD: str = Field(env="MPG_PASSWORD")

    # LEAGUE CONFIG
    LEAGUE_ID: str = Field(env="LEAGUE_ID")
    TEAM_NAME: str = Field(env="TEAM_NAME")
    SEASON_NUMBER: int = Field(env="SEASON_NUMBER")
    DIVISION: int = Field(env="DIVISION")
    NUMBER_PLAYERS: int = Field(env="NUMBER_PLAYERS")

    # CONFIG
    IS_DOCKER: bool = Field(default=True, env="IS_DOCKER")
    MATCHWEEK: list = Field(default=[1], env="MATCHWEEK")
    AZURE_STORAGE_CONNECTION_STRING: str | None = Field(
        default=None, env="AZURE_STORAGE_CONNECTION_STRING"
    )

    @computed_field
    @property
    def RESULT_LINK(self) -> str:
        """URL to the results page of the configured league."""
        return (
            f"https://mpg.football/league/mpg_league_{self.LEAGUE_ID}"
            f"/mpg_division_{self.LEAGUE_ID}_"
            f"{self.SEASON_NUMBER}_{self.DIVISION}/results"
        )


LEAGUE_CONFIG = LeagueConfig()


basicConfig(
    level="INFO",
    format="%(levelname)s - %(message)s",  # %(asctime)s
)
logger = getLogger("mpg-explorer")
