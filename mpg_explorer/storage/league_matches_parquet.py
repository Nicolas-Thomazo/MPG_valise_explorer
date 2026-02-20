"""Utilities to persist and resolve league parquet files with a stable naming format."""

from pathlib import Path

import polars as pl

from mpg_explorer import LEAGUE_CONFIG


def get_league_matches_parquet_filename(
    league_id: str, season_number: int, division: int
) -> str:
    """Build the canonical parquet filename from league/season/division."""
    return f"league_{league_id}_season_{season_number}_division_{division}.parquet"


def save_scraped_league_matches_to_parquet(
    df: pl.DataFrame,
    league_id: str,
    season_number: int,
    division: int,
    data_path: Path | None = None,
) -> Path:
    """
    Save scraped MPG league match rows to a deterministic Parquet filename.

    Returns:
        Path: Absolute path of the saved parquet file.
    """
    target_dir = data_path or LEAGUE_CONFIG.DATA_PATH
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = get_league_matches_parquet_filename(
        league_id=league_id,
        season_number=season_number,
        division=division,
    )

    parquet_path = target_dir / filename
    df.write_parquet(str(parquet_path))
    return parquet_path


def get_scraped_league_matches_parquet_path(
    league_id: str,
    season_number: int,
    division: int,
    data_path: Path | None = None,
) -> Path:
    """Get the exact parquet path for one league/season/division."""
    target_dir = data_path or LEAGUE_CONFIG.DATA_PATH
    filename = get_league_matches_parquet_filename(
        league_id=league_id,
        season_number=season_number,
        division=division,
    )
    parquet_path = target_dir / filename
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"No parquet file found at {parquet_path}. Run scrap_league first."
        )
    return parquet_path


def get_matchweeks_with_unplayed_matches(
    league_id: str,
    season_number: int,
    division: int,
    data_path: Path | None = None,
) -> list[int] | None:
    """
    Return matchweeks that still have incomplete match data.

    Returns:
        list[int]: Sorted unique matchweeks where `match_played` is False
            or `error_in_scrapping` is True.
        None: No parquet found or legacy parquet without required columns.
    """
    try:
        parquet_path = get_scraped_league_matches_parquet_path(
            league_id=league_id,
            season_number=season_number,
            division=division,
            data_path=data_path,
        )
    except FileNotFoundError:
        return None

    df = pl.read_parquet(str(parquet_path))
    required_columns = {"matchweek", "match_played", "error_in_scrapping"}
    if not required_columns.issubset(set(df.columns)):
        return None

    return (
        df.filter(
            (pl.col("match_played") == False) | (pl.col("error_in_scrapping") == True)
        )
        .select("matchweek")
        .unique()
        .sort("matchweek")
        .get_column("matchweek")
        .to_list()
    )
