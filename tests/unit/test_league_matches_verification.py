import polars as pl

from mpg_explorer.models.match_dataframe import MatchColumn as MDC
from mpg_explorer.storage.utils import (
    get_matchweeks_with_unplayed_matches,
    save_scraped_league_matches_to_parquet,
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


def test_save_scraped_league_matches_to_parquet_sorts_by_matchweek(tmp_path):
    df = pl.DataFrame(
        {
            MDC.match_id: ["c", "a", "b"],
            MDC.matchweek: [3, 1, 2],
            MDC.match_played: [False, True, False],
            MDC.home_team_name: ["Team C", "Team A", "Team B"],
            MDC.visitor_team_name: ["Opp C", "Opp A", "Opp B"],
        }
    )

    parquet_path = save_scraped_league_matches_to_parquet(
        df=df,
        league_id="L1",
        season_number=1,
        division=1,
        data_path=tmp_path,
    )

    saved = pl.read_parquet(str(parquet_path))
    assert saved.get_column(MDC.matchweek).to_list() == [1, 2, 3]
