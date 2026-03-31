from pathlib import Path

import polars as pl

from mpg_explorer.models.match_dataframe import MatchColumn as MDC
from mpg_explorer.reports.scrape_summary import (
    build_scrape_summary_dict,
    export_scrape_summary_html,
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
