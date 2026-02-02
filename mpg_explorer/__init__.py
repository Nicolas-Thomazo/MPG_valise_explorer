from logging import basicConfig, getLogger
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LeagueConfig(BaseSettings):
    """Configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- CREDENTIALS ---
    MPG_USERNAME: str
    MPG_PASSWORD: str

    # --- LEAGUE CONFIG ---
    LEAGUE_ID: str
    TEAM_NAME: str
    SEASON_NUMBER: int
    DIVISION: int
    NUMBER_PLAYERS: int

    # --- CONFIG ---
    IS_DOCKER: bool = True
    MATCHWEEK: list[int] = [1]

    AZURE_STORAGE_CONNECTION_STRING: str | None = None

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
