import polars as pl

from mpg_explorer.models.match_dataframe import MatchColumn as MDC
from mpg_explorer.storage.league_matches_parquet import (
    get_matchweeks_with_unplayed_matches,
)


def test_get_matchweeks_with_unplayed_matches_returns_pending_matchweeks(tmp_path):
    parquet_path = tmp_path / "league_L1_season_1_division_1.parquet"
    pl.DataFrame(
        {
            MDC.matchweek: [1, 2, 3, 4],
            MDC.match_played: [True, True, False, False],
            MDC.error_in_scrapping: [False, True, True, False],
        }
    ).write_parquet(str(parquet_path))

    matchweeks = get_matchweeks_with_unplayed_matches(
        league_id="L1",
        season_number=1,
        division=1,
        data_path=tmp_path,
    )

    assert matchweeks == [2, 3, 4]


def test_get_matchweeks_with_unplayed_matches_returns_none_for_legacy_schema(tmp_path):
    parquet_path = tmp_path / "league_L1_season_1_division_1.parquet"
    pl.DataFrame({MDC.matchweek: [1, 2, 3]}).write_parquet(str(parquet_path))

    matchweeks = get_matchweeks_with_unplayed_matches(
        league_id="L1",
        season_number=1,
        division=1,
        data_path=tmp_path,
    )

    assert matchweeks is None
