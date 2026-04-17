from pathlib import Path

import polars as pl

from mpg_explorer.models.match_dataframe import MatchColumn as MDC
from mpg_explorer.reports.scrape_summary import (
    build_scrape_summary_dict,
    export_scrape_summary_html,
    get_newly_added_matches,
)


def test_build_scrape_summary_dict_uses_first_unplayed_matchweek():
    df = pl.DataFrame(
        {
            MDC.matchweek: [1, 1, 2, 2, 3, 3],
            MDC.match_played: [True, True, True, True, False, False],
        }
    )

    summary = build_scrape_summary_dict(
        df=df,
        division=2,
        season_number=12,
    )

    assert summary["matches_scraped"] == 6
    assert summary["division"] == 2
    assert summary["season_number"] == 12
    assert summary["matches_played"] == 4
    assert summary["current_matchweek"] == 3
    assert summary["new_matches_added"] == 6


def test_get_newly_added_matches_ignores_existing_rows_with_same_identity():
    previous_df = pl.DataFrame(
        {
            MDC.matchweek: [1, 2],
            MDC.match_url: ["u1", None],
            MDC.home_team_name: ["Team A", "Team C"],
            MDC.visitor_team_name: ["Team B", "Team D"],
            MDC.match_played: [True, False],
        }
    )
    df = pl.DataFrame(
        {
            MDC.matchweek: [1, 2, 3],
            MDC.match_url: ["u1", "u2", "u3"],
            MDC.home_team_name: ["Team A", "Team C", "Team E"],
            MDC.visitor_team_name: ["Team B", "Team D", "Team F"],
            MDC.match_played: [True, True, False],
        }
    )

    new_rows = get_newly_added_matches(df=df, previous_df=previous_df)

    assert len(new_rows) == 1
    assert new_rows[0][MDC.matchweek] == 3
    assert new_rows[0][MDC.home_team_name] == "Team E"
    assert new_rows[0][MDC.visitor_team_name] == "Team F"


def test_export_scrape_summary_html_writes_file(tmp_path: Path):
    df = pl.DataFrame(
        {
            MDC.matchweek: [1, 2],
            MDC.match_played: [True, False],
        }
    )
    output_path = tmp_path / "reports" / "scrape_summary.html"

    written_path = export_scrape_summary_html(
        df=df,
        division=1,
        season_number=11,
        output_path=output_path,
    )

    html = written_path.read_text(encoding="utf-8")
    assert written_path == output_path
    assert "Rapport de scraping MPG" in html
    assert "Nombre de matchs scrappes" in html
    assert ">2<" in html
    assert "Journee actuelle" in html
    assert "Nouveaux matchs ajoutes" in html
    assert "J1 - ? vs ? (joue)" in html
    assert "J2 - ? vs ? (a venir)" in html
