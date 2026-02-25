from pathlib import Path

import polars as pl
import pytest

from mpg_explorer.models.match_dataframe import MatchColumn as MDC
from mpg_explorer.reports import opponent_report


def _matches_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "match_id": ["m1", "m2", "m3", "m4"],
            "matchweek": [1, 2, 3, 4],
            "match_played": [True, True, False, True],
            "home_team_name": ["Team A", "Team C", "Team A", "Team B"],
            "visitor_team_name": ["Team C", "Team A", "Team B", "Team C"],
            "home_bonus": [["Zahia"], [], [], ["Miroir"]],
            "visitor_bonus": [[], ["McDo+"], [], []],
            "home_real_goals": [1, 0, 0, 2],
            "home_mpg_goals": [1, 0, 0, 0],
            "visitor_real_goals": [0, 2, 0, 1],
            "visitor_mpg_goals": [0, 1, 0, 1],
            "home_total_goals": [2, 0, 0, 2],
            "visitor_total_goals": [0, 3, 0, 2],
        }
    )


def test_get_next_match_and_opponent_returns_first_upcoming_for_team():
    df = _matches_df()
    next_match = opponent_report.get_next_match_and_opponent(df=df, team_name="Team A")
    assert next_match[MDC.match_id] == "m3"
    assert next_match[MDC.matchweek] == 3


def test_get_next_match_and_opponent_raises_when_no_upcoming_match():
    df = _matches_df().with_columns(pl.lit(True).alias(MDC.match_played))
    with pytest.raises(ValueError, match="Aucun prochain match non joue"):
        opponent_report.get_next_match_and_opponent(df=df, team_name="Team A")


def test_collect_bonus_usage_for_one_team():
    df = _matches_df()
    usage = opponent_report.collect_bonus_usage(df=df, team_name="Team A")
    assert set(usage) == {"McDo+", "Zahia"}
    assert usage["Zahia"][0]["matchweek"] == 1
    assert usage["Zahia"][0]["opponent"] == "Team C"
    assert usage["McDo+"][0]["matchweek"] == 2
    assert usage["McDo+"][0]["opponent"] == "Team C"


def test_extract_team_goals_handles_home_and_away_rows():
    df = _matches_df()
    rows = opponent_report._extract_team_goals(df=df, team_name="Team A")
    assert len(rows) == 2
    assert rows[0]["matchweek"] == 1
    assert rows[0]["real_goals"] == 1
    assert rows[0]["mpg_goals"] == 1
    assert rows[1]["matchweek"] == 2
    assert rows[1]["real_goals"] == 2
    assert rows[1]["mpg_goals"] == 1


def test_export_opponent_report_html_writes_html_without_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    df = _matches_df()
    output_path = tmp_path / "next_opponent_report.html"
    monkeypatch.setattr(
        opponent_report,
        "_build_goals_plot_html",
        lambda my_team_name, opponent_name, df: "<div>mock plotly chart</div>",
    )

    report_path, opponent_name = opponent_report.export_opponent_report_html(
        df=df,
        my_team_name="Team A",
        output_path=output_path,
    )

    html = report_path.read_text(encoding="utf-8")
    assert opponent_name == "Team B"
    assert "Bonus restants de l'adversaire" in html
    assert "mock plotly chart" in html
    assert "<table" not in html.lower()


def test_build_goals_plot_html_returns_empty_text_when_no_played_match():
    df = _matches_df().with_columns(pl.lit(False).alias(MDC.match_played))
    html = opponent_report._build_goals_plot_html(
        my_team_name="Team A",
        opponent_name="Team B",
        df=df,
    )
    assert "Aucun match joue pour tracer les buts." in html


def test_build_goals_plot_html_contains_stack_and_team_colors():
    pytest.importorskip("plotly")
    df = _matches_df()
    html = opponent_report._build_goals_plot_html(
        my_team_name="Team A",
        opponent_name="Team B",
        df=df,
    )
    assert '"barmode":"stack"' in html
    assert "#1d4ed8" in html
    assert "#93c5fd" in html
    assert "#b91c1c" in html
    assert "#fca5a5" in html
