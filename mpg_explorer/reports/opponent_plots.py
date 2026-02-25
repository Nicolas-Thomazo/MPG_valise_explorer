"""Plot generation utilities for the next-opponent report."""

from __future__ import annotations

from html import escape

import polars as pl

from mpg_explorer.models.match_dataframe import MatchColumn as MDC


def _extract_team_goals(df: pl.DataFrame, team_name: str) -> list[dict[str, object]]:
    """Extract real and MPG goals for one team on every played matchweek.

    Args:
        df: League matches dataframe using canonical `MatchColumn` fields.
        team_name: Team name to extract (case-insensitive, whitespace-tolerant).

    Returns:
        A list of dictionaries sorted by matchweek. Each dictionary contains:
        `matchweek`, `team_name`, `opponent_name`, `real_goals`, and `mpg_goals`.
    """
    normalized_team = team_name.strip().casefold()
    is_home = (
        pl.col(MDC.home_team_name).str.strip_chars().str.to_lowercase()
        == pl.lit(normalized_team)
    )
    is_visitor = (
        pl.col(MDC.visitor_team_name).str.strip_chars().str.to_lowercase()
        == pl.lit(normalized_team)
    )
    rows = (
        df.filter(pl.col(MDC.match_played) == True)
        .filter(is_home | is_visitor)
        .with_columns(
            [
                pl.when(is_home)
                .then(pl.col(MDC.visitor_team_name))
                .otherwise(pl.col(MDC.home_team_name))
                .alias("opponent_name"),
                pl.when(is_home)
                .then(pl.col(MDC.home_real_goals))
                .otherwise(pl.col(MDC.visitor_real_goals))
                .fill_null(0)
                .cast(pl.Int64)
                .alias("real_goals"),
                pl.when(is_home)
                .then(pl.col(MDC.home_mpg_goals))
                .otherwise(pl.col(MDC.visitor_mpg_goals))
                .fill_null(0)
                .cast(pl.Int64)
                .alias("mpg_goals"),
            ]
        )
        .select(
            [
                pl.col(MDC.matchweek).cast(pl.Int64).alias("matchweek"),
                pl.lit(team_name).alias("team_name"),
                pl.col("opponent_name"),
                pl.col("real_goals"),
                pl.col("mpg_goals"),
            ]
        )
        .sort("matchweek")
    )
    return rows.to_dicts()


def _build_goals_plot_html(my_team_name: str, opponent_name: str, df: pl.DataFrame) -> str:
    """Build one Plotly bar chart comparing both teams for every matchweek.

    For each matchweek, the chart displays two adjacent bars:
    one bar for `my_team_name` and one bar for `opponent_name`.
    Each bar is stacked with two colored segments: real goals and MPG goals.
    A line trace is also added for each team to connect the top of stacked bars
    (team total goals per matchweek).

    Args:
        my_team_name: Team configured as the user's team.
        opponent_name: Upcoming opponent team.
        df: League matches dataframe using canonical `MatchColumn` fields.

    Returns:
        Plotly HTML fragment (no full document) or a text fallback when no played
        match exists for both teams.

    Raises:
        RuntimeError: If `plotly` is not installed and a chart must be rendered.
    """
    my_rows = _extract_team_goals(df=df, team_name=my_team_name)
    opponent_rows = _extract_team_goals(df=df, team_name=opponent_name)
    if not my_rows and not opponent_rows:
        return "<p>Aucun match joue pour tracer les buts.</p>"

    try:
        import plotly.graph_objects as go
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Le package `plotly` est requis pour generer le report."
        ) from exc

    my_by_week = {int(row["matchweek"]): row for row in my_rows}
    opponent_by_week = {int(row["matchweek"]): row for row in opponent_rows}
    weeks = sorted(set(my_by_week) | set(opponent_by_week))

    my_real = [int(my_by_week.get(week, {}).get("real_goals", 0)) for week in weeks]
    my_mpg = [int(my_by_week.get(week, {}).get("mpg_goals", 0)) for week in weeks]
    opp_real = [
        int(opponent_by_week.get(week, {}).get("real_goals", 0)) for week in weeks
    ]
    opp_mpg = [
        int(opponent_by_week.get(week, {}).get("mpg_goals", 0)) for week in weeks
    ]
    x_my = [week - 0.2 for week in weeks]
    x_opp = [week + 0.2 for week in weeks]
    tick_text = [f"J{week}" for week in weeks]

    fig = go.Figure()
    my_real_color = "#1d4ed8"
    my_mpg_color = "#93c5fd"
    opp_real_color = "#b91c1c"
    opp_mpg_color = "#fca5a5"
    my_line_color = "#1e3a8a"
    opponent_line_color = "#7f1d1d"

    fig.add_bar(
        name=f"{my_team_name} - Buts reels",
        x=x_my,
        y=my_real,
        marker_color=my_real_color,
        width=0.36,
        offsetgroup="my_team",
        legendgroup="my_team",
        hovertemplate=(
            f"Equipe: {escape(my_team_name)}<br>Journee: J%{{customdata}}"
            "<br>Buts reels: %{y}<extra></extra>"
        ),
        customdata=weeks,
    )
    fig.add_bar(
        name=f"{my_team_name} - Buts MPG",
        x=x_my,
        y=my_mpg,
        marker_color=my_mpg_color,
        width=0.36,
        offsetgroup="my_team",
        legendgroup="my_team",
        hovertemplate=(
            f"Equipe: {escape(my_team_name)}<br>Journee: J%{{customdata}}"
            "<br>Buts MPG: %{y}<extra></extra>"
        ),
        customdata=weeks,
    )
    fig.add_bar(
        name=f"{opponent_name} - Buts reels",
        x=x_opp,
        y=opp_real,
        marker_color=opp_real_color,
        width=0.36,
        offsetgroup="opponent_team",
        legendgroup="opponent_team",
        hovertemplate=(
            f"Equipe: {escape(opponent_name)}<br>Journee: J%{{customdata}}"
            "<br>Buts reels: %{y}<extra></extra>"
        ),
        customdata=weeks,
    )
    fig.add_bar(
        name=f"{opponent_name} - Buts MPG",
        x=x_opp,
        y=opp_mpg,
        marker_color=opp_mpg_color,
        width=0.36,
        offsetgroup="opponent_team",
        legendgroup="opponent_team",
        hovertemplate=(
            f"Equipe: {escape(opponent_name)}<br>Journee: J%{{customdata}}"
            "<br>Buts MPG: %{y}<extra></extra>"
        ),
        customdata=weeks,
    )

    my_total = [real + mpg for real, mpg in zip(my_real, my_mpg, strict=False)]
    opp_total = [real + mpg for real, mpg in zip(opp_real, opp_mpg, strict=False)]
    fig.add_scatter(
        name=f"{my_team_name} - Total",
        x=x_my,
        y=my_total,
        mode="lines+markers",
        line={"color": my_line_color, "width": 2},
        marker={"size": 7},
        legendgroup="my_team_total",
        hovertemplate=(
            f"Equipe: {escape(my_team_name)}<br>Journee: J%{{customdata}}"
            "<br>Total buts: %{y}<extra></extra>"
        ),
        customdata=weeks,
    )
    fig.add_scatter(
        name=f"{opponent_name} - Total",
        x=x_opp,
        y=opp_total,
        mode="lines+markers",
        line={"color": opponent_line_color, "width": 2},
        marker={"size": 7},
        legendgroup="opponent_team_total",
        hovertemplate=(
            f"Equipe: {escape(opponent_name)}<br>Journee: J%{{customdata}}"
            "<br>Total buts: %{y}<extra></extra>"
        ),
        customdata=weeks,
    )
    fig.update_layout(
        barmode="stack",
        bargap=0.2,
        bargroupgap=0.05,
        title=f"Buts par journee - {my_team_name} vs {opponent_name}",
        xaxis_title="Journee",
        yaxis_title="Nombre de buts",
        legend_title="Equipe et type de but",
        height=560,
    )
    fig.update_xaxes(tickmode="array", tickvals=weeks, ticktext=tick_text)
    return fig.to_html(full_html=False, include_plotlyjs="cdn")
