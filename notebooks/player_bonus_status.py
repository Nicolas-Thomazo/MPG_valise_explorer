# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mpg-explorer",
# ]
#
# [tool.uv.sources]
# mpg-explorer = { path = "../", editable = true }
# ///

# %%
from typing import Any

import polars as pl
from pathlib import Path
from mpg_explorer import LEAGUE_CONFIG, logger
from mpg_explorer.analytics.bonus_usage import get_player_bonus_status
from mpg_explorer.models.bonus import BonusName, get_bonus_name
from mpg_explorer.models.match_result import Match
from mpg_explorer.storage.league_matches_parquet import (
    get_scraped_league_matches_parquet_path,
)


def _to_bonus_list(raw_values: list[Any]) -> list[BonusName]:
    parsed: list[BonusName] = []
    for value in raw_values:
        if isinstance(value, BonusName):
            parsed.append(value)
            continue
        if isinstance(value, str):
            bonus = get_bonus_name(value)
            if bonus is not None:
                parsed.append(bonus)
    return parsed


def _row_to_match(row: dict[str, Any]) -> Match:
    home_raw = row.get("home_bonus")
    visitor_raw = row.get("visitor_bonus")
    home_bonus = _to_bonus_list(home_raw if isinstance(home_raw, list) else [])
    visitor_bonus = _to_bonus_list(visitor_raw if isinstance(visitor_raw, list) else [])

    return Match(**row)


def load_matches_from_parquet(parquet_path: Path) -> pl.DataFrame:
    df = pl.read_parquet(str(parquet_path))
    return df


# %%
# Option A: use parquet path for configured league/season/division
parquet_path = get_scraped_league_matches_parquet_path(
    league_id=LEAGUE_CONFIG.LEAGUE_ID,
    season_number=LEAGUE_CONFIG.SEASON_NUMBER,
    division=2,
    data_path=LEAGUE_CONFIG.DATA_PATH,
)

# Option B: force a specific parquet
# parquet_path = Path("data/league_NKU1UAPG_season_11_division_2.parquet")

player_name = "KABZ"

# %%
df = load_matches_from_parquet(parquet_path)
matches = [_row_to_match(row) for row in df.iter_rows(named=True)]

status = get_player_bonus_status(player_name=player_name, matches=matches)

logger.info(f"Parquet file: {parquet_path}")
logger.info(f"Player: {status.player_name}")
logger.info(f"Played bonuses: {[bonus.value for bonus in status.played]}")
logger.info(f"Remaining bonuses: {[bonus.value for bonus in status.remaining]}")

status

# %%
