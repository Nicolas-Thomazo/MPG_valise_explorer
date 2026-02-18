"""Utilities to persist scraped MPG league match data as Parquet files."""

from datetime import datetime
from pathlib import Path

import polars as pl

from mpg_explorer import LEAGUE_CONFIG


def save_scraped_league_matches_to_parquet(
    df: pl.DataFrame,
    league_id: str,
    season_number: int,
    division: int,
    data_path: Path | None = None,
    add_timestamp: bool = True,
) -> Path:
    """
    Save scraped MPG league match rows to a timestamped Parquet file in DATA_PATH.

    Returns:
        Path: Absolute path of the saved parquet file.
    """
    target_dir = data_path or LEAGUE_CONFIG.DATA_PATH
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = (
        f"scraped_league_matches_league_{league_id}"
        f"_season_{season_number}_division_{division}"
    )
    if add_timestamp:
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename}_{now}"

    parquet_path = target_dir / f"{filename}.parquet"
    df.write_parquet(str(parquet_path))
    return parquet_path

