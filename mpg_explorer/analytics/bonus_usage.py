"""Compute bonus usage for a specific MPG player from scraped matches."""

from mpg_explorer.models.bonus import BonusName
from mpg_explorer.models.match_result import Match
from mpg_explorer.models.player_bonus_status import PlayerBonusStatus


def get_player_bonus_status(player_name: str, matches: list[Match]) -> PlayerBonusStatus:
    """
    Return bonus usage for one player across a list of league matches.

    Args:
        player_name: Team/player name as it appears in match data.
        matches: Scraped match rows.

    Returns:
        PlayerBonusStatus containing already-played bonuses and remaining bonuses.
    """
    normalized_player = player_name.strip().casefold()
    played_set: set[BonusName] = set()

    for match in matches:
        if not match.match_played:
            continue

        if (
            match.home_team_name is not None
            and match.home_team_name.strip().casefold() == normalized_player
        ):
            played_set.update(match.home_bonus)
        if (
            match.visitor_team_name is not None
            and match.visitor_team_name.strip().casefold() == normalized_player
        ):
            played_set.update(match.visitor_bonus)

    played = [bonus for bonus in BonusName if bonus in played_set]
    remaining = [bonus for bonus in BonusName if bonus not in played_set]

    return PlayerBonusStatus(
        player_name=player_name,
        played=played,
        remaining=remaining,
    )
