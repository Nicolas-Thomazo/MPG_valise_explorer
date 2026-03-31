"""Orchestration layer for next-opponent report generation."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from mpg_explorer.models.bonus import BonusName, get_bonus_name
from mpg_explorer.models.match_dataframe import MatchColumn as MDC
from mpg_explorer.reports.opponent_html import (
    build_error_html_report,
    build_html_report,
)
from mpg_explorer.reports.opponent_plots import (
    _build_goals_plot_html,
    _extract_team_goals,
)


def load_matches_from_parquet(parquet_path: Path) -> pl.DataFrame:
    """Load match data from parquet and validate minimal required schema.

    Args:
        parquet_path: Path to the parquet file containing league matches.

    Returns:
        A Polars dataframe with match rows.

    Raises:
        ValueError: If the `match_played` column is missing.
    """
    df = pl.read_parquet(str(parquet_path))
    if MDC.match_played not in df.columns:
        raise ValueError(
            "Colonne obligatoire manquante: `match_played`. "
            "Le parquet semble legacy, relance probablement le scrapper."
        )
    return df


def _normalize_team_name(team_name: str) -> str:
    """Normalize one team name for case-insensitive comparisons.

    Args:
        team_name: Raw team label from configuration or dataframe.

    Returns:
        Trimmed and casefolded team label.
    """
    return team_name.strip().casefold()


def _is_team_match(row: dict[str, object], team_name: str) -> bool:
    """Check whether a match row involves a given team.

    Args:
        row: Match row represented as a dictionary.
        team_name: Team name to match.

    Returns:
        True if `team_name` is either home or visitor team in the row.
    """
    normalized_team = _normalize_team_name(team_name)
    home_name = str(row.get(MDC.home_team_name, "")).strip().casefold()
    visitor_name = str(row.get(MDC.visitor_team_name, "")).strip().casefold()
    return normalized_team in {home_name, visitor_name}


def _get_opponent_name(row: dict[str, object], team_name: str) -> str:
    """Return opponent team name for `team_name` in a given row.

    Args:
        row: Match row represented as a dictionary.
        team_name: Team for which opponent must be derived.

    Returns:
        Opponent team name as found in the row.
    """
    normalized_team = _normalize_team_name(team_name)
    home_name = str(row.get(MDC.home_team_name, "")).strip()
    visitor_name = str(row.get(MDC.visitor_team_name, "")).strip()
    if _normalize_team_name(home_name) == normalized_team:
        return visitor_name
    return home_name


def get_next_match_and_opponent(df: pl.DataFrame, team_name: str) -> dict[str, object]:
    """Find the first upcoming (unplayed) match for one team.

    Args:
        df: League matches dataframe containing canonical `MatchColumn` fields.
        team_name: Team for which the upcoming match should be found.

    Returns:
        Match row dictionary for the nearest unplayed match.

    Raises:
        ValueError: If no unplayed match exists for `team_name`.
    """
    upcoming = (
        df.filter(pl.col(MDC.match_played) == False)
        .sort([MDC.matchweek, MDC.match_id])
        .iter_rows(named=True)
    )
    for row in upcoming:
        if _is_team_match(row, team_name):
            return row
    raise ValueError(
        f"Aucun prochain match non joue trouve pour '{team_name}'. "
        "Verifie TEAM_NAME ou mets a jour le parquet."
    )


def _team_bonus_for_row(row: dict[str, object], team_name: str) -> list[str]:
    """Extract bonuses used by one team in one match row.

    Args:
        row: Match row represented as a dictionary.
        team_name: Team whose bonus list must be returned.

    Returns:
        List of bonus labels used by the team in this row.
    """
    normalized_team = _normalize_team_name(team_name)
    home_name = str(row.get(MDC.home_team_name, "")).strip().casefold()
    visitor_name = str(row.get(MDC.visitor_team_name, "")).strip().casefold()
    if home_name == normalized_team:
        values = row.get(MDC.home_bonus, [])
    elif visitor_name == normalized_team:
        values = row.get(MDC.visitor_bonus, [])
    else:
        return []
    if not isinstance(values, list):
        return []
    return [str(v) for v in values]


def collect_bonus_usage(
    df: pl.DataFrame, team_name: str
) -> dict[str, list[dict[str, object]]]:
    """Aggregate used bonuses for one team over played matches.

    Args:
        df: League matches dataframe containing canonical `MatchColumn` fields.
        team_name: Team for which bonus usage is computed.

    Returns:
        Dictionary keyed by bonus label, with one list of usage events per bonus.
        Each usage event contains `matchweek` and `opponent`.
    """
    played_rows = (
        df.filter(pl.col(MDC.match_played) == True)
        .sort(MDC.matchweek)
        .iter_rows(named=True)
    )
    usage: dict[str, list[dict[str, object]]] = {}
    for row in played_rows:
        if not _is_team_match(row, team_name):
            continue
        for bonus in _team_bonus_for_row(row, team_name):
            usage.setdefault(bonus, []).append(
                {
                    "matchweek": row.get(MDC.matchweek),
                    "opponent": _get_opponent_name(row, team_name),
                }
            )
    return usage


def _remaining_limited_bonus(
    used_bonus: dict[str, list[dict[str, object]]],
) -> list[str]:
    """Return remaining single-use bonuses, excluding reusable defense bonuses."""
    excluded_bonus = {
        BonusName.four_defense.value,
        BonusName.five_defense.value,
    }
    all_bonus = [
        bonus.value for bonus in BonusName if bonus.value not in excluded_bonus
    ]
    return [bonus for bonus in all_bonus if bonus not in used_bonus]


def _count_defense_bonus_usage(df: pl.DataFrame, team_name: str) -> dict[str, int]:
    """Count opponent usage of `4 défenseurs` and `5 défenseurs`.

    Args:
        df: League matches dataframe containing canonical `MatchColumn` fields.
        team_name: Team for which tactical defense bonuses must be counted.

    Returns:
        Dictionary with keys `4 défenseurs` and `5 défenseurs`.
    """
    counts = {
        BonusName.four_defense.value: 0,
        BonusName.five_defense.value: 0,
    }
    played_rows = (
        df.filter(pl.col(MDC.match_played) == True)
        .sort(MDC.matchweek)
        .iter_rows(named=True)
    )
    for row in played_rows:
        if not _is_team_match(row, team_name):
            continue
        for raw_bonus in _team_bonus_for_row(row, team_name):
            bonus = get_bonus_name(raw_bonus)
            if bonus == BonusName.four_defense:
                counts[BonusName.four_defense.value] += 1
            elif bonus == BonusName.five_defense:
                counts[BonusName.five_defense.value] += 1
    return counts


def export_opponent_report_html(
    df: pl.DataFrame,
    my_team_name: str,
    output_path: Path,
) -> tuple[Path, str]:
    """Compute and write the next-opponent report as HTML.

    Args:
        df: League matches dataframe containing canonical `MatchColumn` fields.
        my_team_name: Team configured as the user's team.
        output_path: Destination HTML path.

    Returns:
        Tuple `(written_path, opponent_name)`.

    Raises:
        ValueError: If no upcoming match exists for `my_team_name`.
        RuntimeError: If Plotly is missing while a chart must be rendered.
    """
    next_match = get_next_match_and_opponent(df=df, team_name=my_team_name)
    opponent_name = _get_opponent_name(next_match, my_team_name)

    used_bonus = collect_bonus_usage(df=df, team_name=opponent_name)
    my_used_bonus = collect_bonus_usage(df=df, team_name=my_team_name)
    my_remaining_bonus = _remaining_limited_bonus(my_used_bonus)
    remaining_bonus = _remaining_limited_bonus(used_bonus)
    opponent_defense_bonus_usage = _count_defense_bonus_usage(
        df=df, team_name=opponent_name
    )
    goals_plot_html = _build_goals_plot_html(
        my_team_name=my_team_name,
        opponent_name=opponent_name,
        df=df,
    )

    html = build_html_report(
        my_team_name=my_team_name,
        opponent_name=opponent_name,
        next_match=next_match,
        my_remaining_bonus=my_remaining_bonus,
        remaining_bonus=remaining_bonus,
        opponent_defense_bonus_usage=opponent_defense_bonus_usage,
        goals_plot_html=goals_plot_html,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path, opponent_name


def export_error_report_html(
    my_team_name: str,
    output_path: Path,
    error_message: str,
) -> Path:
    """Write fallback report when generation cannot proceed.

    Args:
        my_team_name: Team configured as the user's team.
        output_path: Destination HTML path.
        error_message: Error text to display in the report.

    Returns:
        Path to the generated HTML file.
    """
    html = build_error_html_report(
        my_team_name=my_team_name, error_message=error_message
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
