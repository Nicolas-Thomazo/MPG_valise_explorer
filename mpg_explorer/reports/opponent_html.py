"""HTML rendering utilities for the next-opponent report."""

from __future__ import annotations

from datetime import datetime
from html import escape

from mpg_explorer.models.match_dataframe import MatchColumn as MDC


def _render_remaining_bonus_badges(remaining_bonus: list[str]) -> str:
    """Render remaining opponent bonuses as badges.

    Args:
        remaining_bonus: Bonus labels that have not been used yet.

    Returns:
        HTML fragment containing one badge per remaining bonus, or a fallback
        message if no bonus remains.
    """
    if not remaining_bonus:
        return "<p>Tous les bonus ont deja ete utilises.</p>"
    badges = "".join(
        f"<span class='badge bonus'>{escape(bonus)}</span>"
        for bonus in sorted(remaining_bonus)
    )
    return f"<div class='bonus-wrap'>{badges}</div>"


def build_html_report(
    my_team_name: str,
    opponent_name: str,
    next_match: dict[str, object],
    my_remaining_bonus: list[str],
    remaining_bonus: list[str],
    opponent_defense_bonus_usage: dict[str, int],
    goals_plot_html: str,
) -> str:
    """Build the full HTML document for next-opponent analysis.

    Args:
        my_team_name: Team configured as the user's team.
        opponent_name: Name of the upcoming opponent.
        next_match: Next match row with canonical `MatchColumn` keys.
        my_remaining_bonus: User team bonuses not yet used in played matches.
        remaining_bonus: Opponent bonuses not yet used in played matches.
        opponent_defense_bonus_usage: Number of uses for opponent tactical
            bonuses (`4 défenseurs`, `5 défenseurs`).
        goals_plot_html: Plotly HTML fragment already generated for goals.

    Returns:
        Complete HTML report as a string.
    """
    match_line = (
        f"Prochain match: J{next_match.get(MDC.matchweek, '-')}, "
        f"{next_match.get(MDC.home_team_name, '-')}"
        f" vs {next_match.get(MDC.visitor_team_name, '-')}"
    )
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    my_remaining_bonus_html = _render_remaining_bonus_badges(my_remaining_bonus)
    remaining_bonus_html = _render_remaining_bonus_badges(remaining_bonus)
    four_def_count = int(opponent_defense_bonus_usage.get("4 défenseurs", 0))
    five_def_count = int(opponent_defense_bonus_usage.get("5 défenseurs", 0))
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Recap adversaire MPG - {escape(opponent_name)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2937; }}
    h1, h2 {{ margin-bottom: 8px; }}
    p {{ margin-top: 0; }}
    .muted {{ color: #6b7280; }}
    .badge {{ display: inline-block; padding: 4px 10px; background: #e5e7eb; border-radius: 999px; margin-right: 8px; }}
    .bonus-wrap {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 18px; }}
    .bonus {{ background: #dcfce7; color: #166534; font-weight: 600; }}
    .plot {{ margin-top: 12px; }}
  </style>
</head>
<body>
  <h1>Recap adversaire MPG</h1>
  <p><span class="badge">Mon equipe: {escape(my_team_name)}</span><span class="badge">Adversaire: {escape(opponent_name)}</span></p>
  <p><strong>{escape(match_line)}</strong></p>
  <p class="muted">Genere le {escape(generated_at)}</p>

  <h2>Mes bonus restants</h2>
  {my_remaining_bonus_html}

  <h2>Bonus restants de l'adversaire</h2>
  {remaining_bonus_html}
  <p><strong>Utilisations adverses de 4 défenseurs:</strong> {four_def_count}</p>
  <p><strong>Utilisations adverses de 5 défenseurs:</strong> {five_def_count}</p>

  <h2>Buts (reels vs MPG) sur toutes les journees</h2>
  <div class="plot">{goals_plot_html}</div>
</body>
</html>
"""


def build_error_html_report(my_team_name: str, error_message: str) -> str:
    """Build fallback HTML when source data is missing or unusable.

    Args:
        my_team_name: Team configured as the user's team.
        error_message: Human-readable error message to include in the page.

    Returns:
        Complete HTML error page as a string.
    """
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Recap adversaire MPG - Erreur</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2937; }}
    h1 {{ margin-bottom: 8px; }}
    .muted {{ color: #6b7280; }}
    .error {{ background: #fef2f2; border: 1px solid #ef4444; padding: 12px; border-radius: 8px; }}
  </style>
</head>
<body>
  <h1>Recap adversaire MPG - indisponible</h1>
  <p><strong>Equipe:</strong> {escape(my_team_name)}</p>
  <div class="error">
    <p><strong>Erreur:</strong> {escape(error_message)}</p>
    <p>Action recommandee: relancer le scrapper pour regenerer un parquet a jour.</p>
  </div>
  <p class="muted">Genere le {escape(generated_at)}</p>
</body>
</html>
"""
