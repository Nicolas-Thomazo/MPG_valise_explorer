"""HTML export utilities for scrape summary reports."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import TypedDict, cast

import polars as pl

from mpg_explorer.models.match_dataframe import MatchColumn as MDC


class MatchSummaryDetail(TypedDict):
    """Serializable summary for one newly added match."""

    matchweek: int | None
    home_team_name: str | None
    visitor_team_name: str | None
    match_played: bool | None


class ScrapeSummary(TypedDict):
    """Serializable payload rendered in the scrape summary HTML."""

    matches_scraped: int
    division: int
    season_number: int
    matches_played: int
    current_matchweek: int | None
    new_matches_added: int
    new_matches_details: list[MatchSummaryDetail]


def _team_pair_key(home_name: str, visitor_name: str) -> str:
    """Create a stable pair key for one match independent of home/away."""
    normalized = sorted([home_name.strip().casefold(), visitor_name.strip().casefold()])
    return "||".join(normalized)


def _row_identity_keys(row: dict[str, object]) -> set[tuple[str, int | None, str]]:
    """Build stable identity keys for one match row."""
    keys: set[tuple[str, int | None, str]] = set()
    matchweek = row.get(MDC.matchweek)
    week = int(matchweek) if isinstance(matchweek, int) else None

    match_url = row.get(MDC.match_url)
    if isinstance(match_url, str) and match_url.strip():
        keys.add(("url", week, match_url.strip()))

    home_name = row.get(MDC.home_team_name)
    visitor_name = row.get(MDC.visitor_team_name)
    if isinstance(home_name, str) and isinstance(visitor_name, str):
        keys.add(("pair", week, _team_pair_key(home_name, visitor_name)))

    if keys:
        return keys

    match_id = row.get(MDC.match_id)
    if isinstance(match_id, str) and match_id.strip():
        return {("id", week, match_id.strip())}

    return set()


def get_newly_added_matches(
    df: pl.DataFrame, previous_df: pl.DataFrame | None = None
) -> list[dict[str, object]]:
    """Return rows present in `df` but not in `previous_df`."""
    sort_columns = [
        column for column in [MDC.matchweek, MDC.home_team_name] if column in df.columns
    ]
    if previous_df is None or previous_df.is_empty():
        return (df.sort(sort_columns) if sort_columns else df).to_dicts()

    previous_keys: set[tuple[str, int | None, str]] = set()
    for raw_row in previous_df.iter_rows(named=True):
        row = cast(dict[str, object], raw_row)
        previous_keys.update(_row_identity_keys(row))

    new_rows: list[dict[str, object]] = []
    for raw_row in df.iter_rows(named=True):
        row = cast(dict[str, object], raw_row)
        row_keys = _row_identity_keys(row)
        if row_keys and row_keys & previous_keys:
            continue
        new_rows.append(row)

    return sorted(
        new_rows,
        key=lambda row: (
            row.get(MDC.matchweek) is None,
            row.get(MDC.matchweek) or 0,
            str(row.get(MDC.home_team_name) or ""),
            str(row.get(MDC.visitor_team_name) or ""),
        ),
    )


def build_scrape_summary_dict(
    df: pl.DataFrame,
    division: int,
    season_number: int,
    previous_df: pl.DataFrame | None = None,
) -> ScrapeSummary:
    """Build a one-row summary payload for a league scrape."""
    played_matches = df.filter(pl.col(MDC.match_played)).height
    newly_added_matches = get_newly_added_matches(df=df, previous_df=previous_df)
    unplayed_weeks = (
        df.filter(~pl.col(MDC.match_played))
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
        df.filter(pl.col(MDC.match_played))
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
        "new_matches_added": len(newly_added_matches),
        "new_matches_details": cast(
            list[MatchSummaryDetail],
            [
            {
                "matchweek": row.get(MDC.matchweek),
                "home_team_name": row.get(MDC.home_team_name),
                "visitor_team_name": row.get(MDC.visitor_team_name),
                "match_played": row.get(MDC.match_played),
            }
            for row in newly_added_matches
            ],
        ),
    }


def build_scrape_summary_html(summary: ScrapeSummary) -> str:
    """Render a simple HTML summary report."""
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_matches_details = summary["new_matches_details"]
    details_html = (
        "".join(
            f"<li>J{escape(str(match.get('matchweek') or '-'))} - "
            f"{escape(str(match.get('home_team_name') or '?'))} vs "
            f"{escape(str(match.get('visitor_team_name') or '?'))}"
            f"{' (joue)' if match.get('match_played') else ' (a venir)'}"
            "</li>"
            for match in new_matches_details
        )
        if new_matches_details
        else "<li>Aucun nouveau match ajoute depuis le dernier scraping.</li>"
    )
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
    ul {{ margin: 18px 0 0; padding-left: 20px; }}
    li {{ margin: 6px 0; }}
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
    <div class="row"><span class="label">Nouveaux matchs ajoutes</span><span class="value">{summary["new_matches_added"]}</span></div>
    <ul>{details_html}</ul>
  </div>
</body>
</html>
"""


def export_scrape_summary_html(
    df: pl.DataFrame,
    division: int,
    season_number: int,
    output_path: Path,
    previous_df: pl.DataFrame | None = None,
) -> Path:
    """Write the scrape summary HTML report to disk."""
    summary = build_scrape_summary_dict(
        df=df,
        division=division,
        season_number=season_number,
        previous_df=previous_df,
    )
    html = build_scrape_summary_html(summary)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
