from typing import cast

from mpg_explorer.analytics.bonus_usage import get_player_bonus_status
from mpg_explorer.models.bonus import BonusName
from mpg_explorer.models.match_result import Match


def test_get_player_bonus_status():
    matches: list[Match] = [
        Match(
            match_id="m1",
            league_id="L",
            division=1,
            season_number=1,
            matchweek=1,
            home_team_name="Alice",
            home_total_goals=2,
            home_bonus=cast(list[BonusName], [BonusName.zahia, BonusName.suarez]),
            visitor_team_name="Bob",
            visitor_total_goals=1,
            visitor_bonus=cast(list[BonusName], [BonusName.mcdo]),
        ),
        Match(
            match_id="m2",
            league_id="L",
            division=1,
            season_number=1,
            matchweek=2,
            home_team_name="Charlie",
            home_total_goals=0,
            home_bonus=cast(list[BonusName], []),
            visitor_team_name="Alice",
            visitor_total_goals=3,
            visitor_bonus=cast(list[BonusName], [BonusName.capitaine]),
        ),
    ]

    status = get_player_bonus_status("alice", matches)

    assert status.player_name == "alice"
    assert status.played == [BonusName.zahia, BonusName.suarez, BonusName.capitaine]
    assert BonusName.mcdo in status.remaining
    assert BonusName.zahia not in status.remaining
