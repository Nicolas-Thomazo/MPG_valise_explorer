"""Plot generation utilities for the next-opponent report."""

from __future__ import annotations

import base64
from io import BytesIO

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
    """Build one PNG chart comparing both teams for every matchweek.

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
        HTML fragment containing an embedded PNG image, or a text fallback when
        no played match exists for both teams.

    Raises:
        RuntimeError: If `matplotlib` is not installed and a chart must be
            rendered.
    """
    my_rows = _extract_team_goals(df=df, team_name=my_team_name)
    opponent_rows = _extract_team_goals(df=df, team_name=opponent_name)
    if not my_rows and not opponent_rows:
        return "<p>Aucun match joue pour tracer les buts.</p>"

    try:
        import matplotlib.pyplot as plt
        from matplotlib.lines import Line2D
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Le package `matplotlib` est requis pour generer le report."
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
    x_positions = list(range(len(weeks)))
    bar_width = 0.36
    x_my = [pos - (bar_width / 2) for pos in x_positions]
    x_opp = [pos + (bar_width / 2) for pos in x_positions]
    tick_text = [f"J{week}" for week in weeks]
    my_real_color = "#1d4ed8"
    my_mpg_color = "#93c5fd"
    opp_real_color = "#b91c1c"
    opp_mpg_color = "#fca5a5"
    my_line_color = "#1e3a8a"
    opponent_line_color = "#7f1d1d"
    my_total = [real + mpg for real, mpg in zip(my_real, my_mpg, strict=False)]
    opp_total = [real + mpg for real, mpg in zip(opp_real, opp_mpg, strict=False)]

    fig, ax = plt.subplots(figsize=(11, 6))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    ax.bar(
        x_my,
        my_real,
        width=bar_width,
        color=my_real_color,
        label=f"{my_team_name} - Buts reels",
    )
    ax.bar(
        x_my,
        my_mpg,
        width=bar_width,
        bottom=my_real,
        color=my_mpg_color,
        label=f"{my_team_name} - Buts MPG",
    )
    ax.bar(
        x_opp,
        opp_real,
        width=bar_width,
        color=opp_real_color,
        label=f"{opponent_name} - Buts reels",
    )
    ax.bar(
        x_opp,
        opp_mpg,
        width=bar_width,
        bottom=opp_real,
        color=opp_mpg_color,
        label=f"{opponent_name} - Buts MPG",
    )

    ax.plot(
        x_my,
        my_total,
        color=my_line_color,
        marker="o",
        linewidth=2,
        label=f"{my_team_name} - Total",
    )
    ax.plot(
        x_opp,
        opp_total,
        color=opponent_line_color,
        marker="o",
        linewidth=2,
        label=f"{opponent_name} - Total",
    )

    ax.set_title(f"Buts par journee - {my_team_name} vs {opponent_name}")
    ax.set_xlabel("Journee")
    ax.set_ylabel("Nombre de buts")
    ax.set_xticks(x_positions)
    ax.set_xticklabels(tick_text)
    ax.grid(axis="y", linestyle="--", linewidth=0.8, alpha=0.35)
    ax.set_axisbelow(True)

    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, color=my_real_color, label=f"{my_team_name} - Buts reels"),
        plt.Rectangle((0, 0), 1, 1, color=my_mpg_color, label=f"{my_team_name} - Buts MPG"),
        Line2D([0], [0], color=my_line_color, marker="o", linewidth=2, label=f"{my_team_name} - Total"),
        plt.Rectangle((0, 0), 1, 1, color=opp_real_color, label=f"{opponent_name} - Buts reels"),
        plt.Rectangle((0, 0), 1, 1, color=opp_mpg_color, label=f"{opponent_name} - Buts MPG"),
        Line2D([0], [0], color=opponent_line_color, marker="o", linewidth=2, label=f"{opponent_name} - Total"),
    ]
    ax.legend(
        handles=legend_handles,
        title="Equipe et type de but",
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=2,
        frameon=False,
    )

    buffer = BytesIO()
    fig.tight_layout()
    fig.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    encoded_image = base64.b64encode(buffer.getvalue()).decode("ascii")
    return (
        "<img "
        f"src=\"data:image/png;base64,{encoded_image}\" "
        "alt=\"Graphique des buts reels et MPG\" "
        "style=\"max-width:100%;height:auto;display:block\" />"
    )
