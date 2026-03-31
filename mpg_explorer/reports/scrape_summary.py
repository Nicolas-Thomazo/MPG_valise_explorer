"""HTML export utilities for scrape summary reports."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

import polars as pl

from mpg_explorer.models.match_dataframe import MatchColumn as MDC


def build_scrape_summary_dict(
    df: pl.DataFrame,
    division: int,
    season_number: int,
) -> dict[str, int | None]:
    """Build a one-row summary payload for a league scrape."""
    played_matches = df.filter(pl.col(MDC.match_played) == True).height
    unplayed_weeks = (
        df.filter(pl.col(MDC.match_played) == False)
        .select(MDC.matchweek)
        .drop_nulls()
        .unique()
        .sort(MDC.matchweek)
        .get_column(MDC.matchweek)
        .to_list()
        if MDC.matchweek in df.columns
        else []
    )
    played_weeks = (
        df.filter(pl.col(MDC.match_played) == True)
        .select(MDC.matchweek)
        .drop_nulls()
        .unique()
        .sort(MDC.matchweek)
        .get_column(MDC.matchweek)
        .to_list()
        if MDC.matchweek in df.columns
        else []
    )
    current_matchweek = (
        min(unplayed_weeks)
        if unplayed_weeks
        else (max(played_weeks) if played_weeks else None)
    )
    return {
        "matches_scraped": df.height,
        "division": division,
        "season_number": season_number,
        "matches_played": played_matches,
        "current_matchweek": current_matchweek,
    }


def build_scrape_summary_html(summary: dict[str, int | None]) -> str:
    """Render a simple HTML summary report."""
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Rapport de scraping MPG</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2937; }}
    h1 {{ margin-bottom: 12px; }}
    .muted {{ color: #6b7280; }}
    .card {{ max-width: 560px; border: 1px solid #e5e7eb; border-radius: 12px; padding: 18px; background: #ffffff; }}
    .row {{ display: flex; justify-content: space-between; gap: 16px; padding: 10px 0; border-bottom: 1px solid #f3f4f6; }}
    .row:last-child {{ border-bottom: none; }}
    .label {{ font-weight: 600; }}
    .value {{ color: #111827; }}
  </style>
</head>
<body>
  <h1>Rapport de scraping MPG</h1>
  <p class="muted">Genere le {escape(generated_at)}</p>
  <div class="card">
    <div class="row"><span class="label">Nombre de matchs scrappes</span><span class="value">{summary["matches_scraped"]}</span></div>
    <div class="row"><span class="label">Division</span><span class="value">{summary["division"]}</span></div>
    <div class="row"><span class="label">Saison</span><span class="value">{summary["season_number"]}</span></div>
    <div class="row"><span class="label">Matchs joues</span><span class="value">{summary["matches_played"]}</span></div>
    <div class="row"><span class="label">Journee actuelle</span><span class="value">{summary["current_matchweek"] if summary["current_matchweek"] is not None else "-"}</span></div>
  </div>
</body>
</html>
"""


def export_scrape_summary_html(
    df: pl.DataFrame,
    division: int,
    season_number: int,
    output_path: Path,
) -> Path:
    """Write the scrape summary HTML report to disk."""
    summary = build_scrape_summary_dict(
        df=df,
        division=division,
        season_number=season_number,
    )
    html = build_scrape_summary_html(summary)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
