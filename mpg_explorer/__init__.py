import sys
from logging import basicConfig, getLogger
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
    DATA_PATH: Path = PROJECT_ROOT / "data"

    AZURE_STORAGE_CONNECTION_STRING: str | None = None


LEAGUE_CONFIG = LeagueConfig()  # type: ignore

# Root-level folder for local data exports (configurable via LeagueConfig).
DATA_PATH = LEAGUE_CONFIG.DATA_PATH
DATA_PATH.mkdir(parents=True, exist_ok=True)


basicConfig(
    level="INFO",
    stream=sys.stdout,
    format="%(levelname)s - %(message)s",  # %(asctime)s
)
logger = getLogger("mpg-explorer")
