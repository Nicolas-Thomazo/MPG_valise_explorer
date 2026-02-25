"""Dataframe refresh helpers for league scraping."""

from __future__ import annotations

from logging import Logger
from uuid import uuid4

import polars as pl

from mpg_explorer.models.match_dataframe import MatchColumn as MDC
from mpg_explorer.models.league_match_urls import MatchweekUrls
from mpg_explorer.models.match_result import Match


def matches_per_matchweek(nb_players: int) -> int:
    """Return expected matches count per matchweek."""
    return max(1, nb_players // 2)


def extend_refresh_matchweeks_with_missing_weeks(
    df_existing: pl.DataFrame,
    matchweeks_to_refresh: list[int],
    nb_players: int,
    league_id: str,
    logger: Logger,
) -> list[int]:
    """Add completely missing matchweeks to the refresh scope."""
    expected_matchweeks = set(range(1, (nb_players - 1) * 2 + 1))
    if MDC.matchweek not in df_existing.columns:
        missing_matchweeks = sorted(expected_matchweeks)
    else:
        existing_matchweeks = set(
            df_existing.select(MDC.matchweek)
            .drop_nulls()
            .unique()
            .get_column(MDC.matchweek)
            .to_list()
        )
        missing_matchweeks = sorted(expected_matchweeks - existing_matchweeks)

    combined = sorted(set(matchweeks_to_refresh) | set(missing_matchweeks))
    if missing_matchweeks:
        logger.warning(
            f"[league_id={league_id}] Missing matchweeks in parquet: {missing_matchweeks}. "
            f"Final refresh set: {combined}"
        )
    return combined


def ensure_match_url_column(df: pl.DataFrame) -> pl.DataFrame:
    """Ensure dataframe contains `match_url` column."""
    if MDC.match_url in df.columns:
        return df
    return df.with_columns(pl.lit(None).cast(pl.String).alias(MDC.match_url))


def get_pending_rows(df_existing: pl.DataFrame) -> pl.DataFrame:
    """Return rows that still require scraping."""
    required_cols = {MDC.match_played, MDC.error_in_scrapping}
    if not required_cols.issubset(set(df_existing.columns)):
        return df_existing.head(0)

    has_score_cols = {MDC.home_total_goals, MDC.visitor_total_goals}.issubset(
        set(df_existing.columns)
    )
    if has_score_cols:
        pending_expr = (pl.col(MDC.error_in_scrapping) == True) | (
            (pl.col(MDC.match_played) == False)
            & (
                pl.col(MDC.home_total_goals).is_null()
                | pl.col(MDC.visitor_total_goals).is_null()
            )
        )
    else:
        pending_expr = (pl.col(MDC.match_played) == False) | (
            pl.col(MDC.error_in_scrapping) == True
        )
    return df_existing.filter(pending_expr)


def team_pair_key(home_name: str, visitor_name: str) -> str:
    """Create a stable pair key for one match independent of home/away."""
    normalized = sorted([home_name.strip().casefold(), visitor_name.strip().casefold()])
    return "||".join(normalized)


def build_pending_index_by_week(
    pending_rows: pl.DataFrame,
) -> dict[int, dict[str, set[str]]]:
    """Build lookup index for pending matches keyed by matchweek."""
    index: dict[int, dict[str, set[str]]] = {}
    for row in pending_rows.iter_rows(named=True):
        matchweek = row.get(MDC.matchweek)
        if matchweek is None:
            continue
        week = int(matchweek)
        bucket = index.setdefault(week, {"urls": set(), "pairs": set()})

        match_url = row.get(MDC.match_url)
        if isinstance(match_url, str) and match_url.strip():
            bucket["urls"].add(match_url.strip())

        home_name = row.get(MDC.home_team_name)
        visitor_name = row.get(MDC.visitor_team_name)
        if isinstance(home_name, str) and isinstance(visitor_name, str):
            bucket["pairs"].add(
                team_pair_key(home_name=home_name, visitor_name=visitor_name)
            )
    return index


def filter_matchweek_urls_to_pending(
    matchweek_data: MatchweekUrls,
    pending_index_by_week: dict[int, dict[str, set[str]]],
    league_id: str,
    logger: Logger,
) -> MatchweekUrls:
    """Keep only pending matches for a given matchweek when possible."""
    pending_bucket = pending_index_by_week.get(matchweek_data.matchweek)
    if pending_bucket is None:
        return matchweek_data

    pending_urls = pending_bucket["urls"]
    pending_pairs = pending_bucket["pairs"]
    if not pending_urls and not pending_pairs:
        return matchweek_data

    filtered_urls: list[str] = []
    filtered_played: list[bool] = []
    filtered_home_names: list[str | None] = []
    filtered_visitor_names: list[str | None] = []

    for idx, url in enumerate(matchweek_data.urls):
        played = (
            matchweek_data.matches_played[idx]
            if idx < len(matchweek_data.matches_played)
            else False
        )
        home_name = (
            matchweek_data.home_team_names[idx]
            if idx < len(matchweek_data.home_team_names)
            else None
        )
        visitor_name = (
            matchweek_data.visitor_team_names[idx]
            if idx < len(matchweek_data.visitor_team_names)
            else None
        )
        keep = False
        if url in pending_urls:
            keep = True
        elif isinstance(home_name, str) and isinstance(visitor_name, str):
            keep = (
                team_pair_key(home_name=home_name, visitor_name=visitor_name)
                in pending_pairs
            )
        if keep:
            filtered_urls.append(url)
            filtered_played.append(played)
            filtered_home_names.append(home_name)
            filtered_visitor_names.append(visitor_name)

    if filtered_urls:
        return MatchweekUrls(
            matchweek=matchweek_data.matchweek,
            urls=filtered_urls,
            matches_played=filtered_played,
            home_team_names=filtered_home_names,
            visitor_team_names=filtered_visitor_names,
        )

    logger.warning(
        f"[league_id={league_id}][matchweek={matchweek_data.matchweek}] "
        "No URL matched pending rows; keeping full matchweek to avoid missing updates."
    )
    return matchweek_data


def align_dataframe_schema(df: pl.DataFrame, target_columns: list[str]) -> pl.DataFrame:
    """Align dataframe to target columns by adding missing null columns."""
    result = df
    for column in target_columns:
        if column not in result.columns:
            result = result.with_columns(pl.lit(None).alias(column))
    return result.select(target_columns)


def cleanup_legacy_error_rows(
    df_existing: pl.DataFrame, nb_players: int, league_id: str, logger: Logger
) -> pl.DataFrame:
    """Drop legacy null-team error rows when a week is already complete."""
    required = {
        MDC.matchweek,
        MDC.home_team_name,
        MDC.visitor_team_name,
        MDC.error_in_scrapping,
    }
    if not required.issubset(set(df_existing.columns)):
        return df_existing

    expected_per_week = matches_per_matchweek(nb_players)
    complete_weeks = (
        df_existing.filter(
            pl.col(MDC.home_team_name).is_not_null()
            & pl.col(MDC.visitor_team_name).is_not_null()
        )
        .group_by(MDC.matchweek)
        .len()
        .filter(pl.col("len") >= expected_per_week)
        .select(MDC.matchweek)
        .get_column(MDC.matchweek)
        .to_list()
    )
    if not complete_weeks:
        return df_existing

    cleaned = df_existing.filter(
        ~(
            pl.col(MDC.matchweek).is_in(complete_weeks)
            & (pl.col(MDC.error_in_scrapping) == True)
            & pl.col(MDC.home_team_name).is_null()
            & pl.col(MDC.visitor_team_name).is_null()
        )
    )
    dropped = df_existing.height - cleaned.height
    if dropped > 0:
        logger.warning(
            f"[league_id={league_id}] Dropped {dropped} legacy error rows with null teams "
            f"on already-complete matchweeks: {sorted(complete_weeks)}"
        )
    return cleaned


def _row_identity_key(row: dict) -> tuple[str, int | None, str]:
    """Build a stable identity key for one match row."""
    matchweek = row.get(MDC.matchweek)
    match_url = row.get(MDC.match_url)
    if isinstance(match_url, str) and match_url.strip():
        return (
            "url",
            int(matchweek) if matchweek is not None else None,
            match_url.strip(),
        )

    home_name = row.get(MDC.home_team_name)
    visitor_name = row.get(MDC.visitor_team_name)
    if isinstance(home_name, str) and isinstance(visitor_name, str):
        pair_key = team_pair_key(home_name=home_name, visitor_name=visitor_name)
        return ("pair", int(matchweek) if matchweek is not None else None, pair_key)

    match_id = str(row.get(MDC.match_id, ""))
    return ("id", int(matchweek) if matchweek is not None else None, match_id)


def merge_refreshed_rows(
    df_existing: pl.DataFrame, df_refresh: pl.DataFrame
) -> pl.DataFrame:
    """Merge refreshed rows into existing dataframe without dropping whole matchweeks."""
    if df_refresh.is_empty():
        return df_existing

    refresh_rows = list(df_refresh.iter_rows(named=True))
    refresh_keys = {_row_identity_key(row) for row in refresh_rows}
    kept_rows = [
        row
        for row in df_existing.iter_rows(named=True)
        if _row_identity_key(row) not in refresh_keys
    ]
    merged_rows = kept_rows + refresh_rows
    merged = pl.DataFrame(merged_rows)
    return align_dataframe_schema(merged, df_existing.columns)


def build_inferred_unplayed_rows(
    df_existing: pl.DataFrame,
    target_matchweeks: list[int],
    league_id: str,
    division: int,
    season_nb: int,
    nb_players: int,
    logger: Logger,
) -> pl.DataFrame:
    """Build fallback unplayed rows when MPG does not expose match URLs."""
    if not target_matchweeks:
        return pl.DataFrame()

    first_leg_weeks = nb_players - 1
    rows: list[dict] = []
    expected_matches = matches_per_matchweek(nb_players)

    for week in sorted(set(target_matchweeks)):
        source_week = (
            week - first_leg_weeks if week > first_leg_weeks else week + first_leg_weeks
        )
        source = df_existing.filter(
            (pl.col(MDC.matchweek) == source_week)
            & pl.col(MDC.home_team_name).is_not_null()
            & pl.col(MDC.visitor_team_name).is_not_null()
        )
        if source.height != expected_matches:
            logger.warning(
                f"[league_id={league_id}] Could not infer matchweek {week}: "
                f"source week {source_week} has {source.height}/{expected_matches} complete rows."
            )
            continue

        for source_row in source.iter_rows(named=True):
            rows.append(
                Match(
                    match_id=str(uuid4()),
                    match_url=None,
                    league_id=league_id,
                    division=division,
                    season_number=season_nb,
                    matchweek=week,
                    match_played=False,
                    error_in_scrapping=False,
                    home_team_name=source_row.get(MDC.visitor_team_name),
                    visitor_team_name=source_row.get(MDC.home_team_name),
                ).model_dump(mode="json")
            )

    if not rows:
        return pl.DataFrame()
    return pl.DataFrame(rows)
