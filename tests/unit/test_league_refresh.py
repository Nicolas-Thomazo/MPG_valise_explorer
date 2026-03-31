import logging

import polars as pl

from mpg_explorer.analytics.league_refresh import (
    build_inferred_unplayed_rows,
    build_pending_index_by_week,
    ensure_match_url_column,
    extend_refresh_matchweeks_with_missing_weeks,
    filter_matchweek_urls_to_pending,
    get_pending_rows,
    merge_refreshed_rows,
)
from mpg_explorer.models.match_dataframe import MatchColumn as MDC
from mpg_explorer.models.league_match_urls import MatchweekUrls


def test_extend_refresh_matchweeks_with_missing_weeks_adds_absent_week():
    df_existing = pl.DataFrame({MDC.matchweek: [1, 2, 3, 4, 5, 6, 7, 8, 9]})
    result = extend_refresh_matchweeks_with_missing_weeks(
        df_existing=df_existing,
        matchweeks_to_refresh=[],
        nb_players=6,
        league_id="L1",
        logger=logging.getLogger("test"),
    )
    assert result == [10]


def test_get_pending_rows_ignores_false_match_played_when_scores_present():
    df = pl.DataFrame(
        {
            MDC.matchweek: [1, 2, 3],
            MDC.match_played: [False, False, True],
            MDC.error_in_scrapping: [False, False, False],
            MDC.home_total_goals: [2, None, 1],
            MDC.visitor_total_goals: [1, None, 0],
        }
    )
    pending = get_pending_rows(df)
    assert pending.get_column(MDC.matchweek).to_list() == [2]


def test_filter_matchweek_urls_to_pending_by_pair():
    pending_rows = pl.DataFrame(
        {
            MDC.matchweek: [9],
            MDC.match_url: [None],
            MDC.home_team_name: ["KABZ"],
            MDC.visitor_team_name: ["NIKEU"],
        }
    )
    pending_index = build_pending_index_by_week(pending_rows)
    week = MatchweekUrls(
        matchweek=9,
        urls=["u1", "u2"],
        matches_played=[True, True],
        home_team_names=["KABZ", "FC Roro"],
        visitor_team_names=["NIKEU", "Baptoz"],
    )
    filtered = filter_matchweek_urls_to_pending(
        matchweek_data=week,
        pending_index_by_week=pending_index,
        league_id="L1",
        logger=logging.getLogger("test"),
    )
    assert filtered.urls == ["u1"]


def test_merge_refreshed_rows_replaces_only_matching_row():
    df_existing = ensure_match_url_column(
        pl.DataFrame(
            {
                MDC.match_id: ["a", "b"],
                MDC.matchweek: [9, 9],
                MDC.match_url: ["u1", "u2"],
                MDC.home_team_name: ["KABZ", "FC Roro"],
                MDC.visitor_team_name: ["NIKEU", "Baptoz"],
                MDC.match_played: [False, True],
                MDC.error_in_scrapping: [True, False],
            }
        )
    )
    df_refresh = pl.DataFrame(
        {
            MDC.match_id: ["new-a"],
            MDC.matchweek: [9],
            MDC.match_url: ["u1"],
            MDC.home_team_name: ["KABZ"],
            MDC.visitor_team_name: ["NIKEU"],
            MDC.match_played: [True],
            MDC.error_in_scrapping: [False],
        }
    )
    merged = merge_refreshed_rows(df_existing=df_existing, df_refresh=df_refresh)
    assert merged.height == 2
    assert merged.filter(pl.col(MDC.match_url) == "u2").height == 1
    updated = merged.filter(pl.col(MDC.match_url) == "u1")
    assert updated.select(MDC.match_played).item() is True


def test_merge_refreshed_rows_replaces_pending_pair_without_url():
    df_existing = ensure_match_url_column(
        pl.DataFrame(
            {
                MDC.match_id: ["pending-a", "pending-b", "done-c"],
                MDC.matchweek: [10, 10, 9],
                MDC.match_url: [None, None, "u9"],
                MDC.home_team_name: ["NIKEU", "KABZ", "FC Roro"],
                MDC.visitor_team_name: ["FC Roro", "Baptoz", "NIKEU"],
                MDC.match_played: [False, False, True],
                MDC.error_in_scrapping: [False, False, False],
            }
        )
    )
    df_refresh = pl.DataFrame(
        {
            MDC.match_id: ["played-a"],
            MDC.matchweek: [10],
            MDC.match_url: ["u10-a"],
            MDC.home_team_name: ["NIKEU"],
            MDC.visitor_team_name: ["FC Roro"],
            MDC.match_played: [True],
            MDC.error_in_scrapping: [False],
        }
    )

    merged = merge_refreshed_rows(df_existing=df_existing, df_refresh=df_refresh)

    assert merged.height == 3
    assert merged.filter(pl.col(MDC.match_id) == "pending-a").height == 0
    assert merged.filter(pl.col(MDC.match_id) == "pending-b").height == 1
    refreshed = merged.filter(pl.col(MDC.match_url) == "u10-a")
    assert refreshed.height == 1
    assert refreshed.select(MDC.match_played).item() is True


def test_build_inferred_unplayed_rows_mirrors_home_away():
    df_existing = pl.DataFrame(
        {
            MDC.matchweek: [1, 1, 1],
            MDC.home_team_name: ["A", "B", "C"],
            MDC.visitor_team_name: ["D", "E", "F"],
        }
    )
    inferred = build_inferred_unplayed_rows(
        df_existing=df_existing,
        target_matchweeks=[6],
        league_id="L1",
        division=1,
        season_nb=1,
        nb_players=6,
        logger=logging.getLogger("test"),
    )
    assert inferred.height == 3
    assert {
        MDC.home_team_name,
        MDC.visitor_team_name,
        MDC.match_played,
        MDC.match_url,
    }.issubset(set(inferred.columns))
    assert inferred.select(MDC.match_played).to_series().to_list() == [
        False,
        False,
        False,
    ]
