import pytest
from mpg_explorer.utils.driver import Driver
from mpg_explorer.scrap.game_info import PlayerResult, get_match_data
from mpg_explorer.scrap.goals import get_goal_breakdown
from mpg_explorer.models.bonus import BonusName
from mpg_explorer import logger


@pytest.fixture(scope="module")
def logged_in_driver():
    """
    Fixture that initializes the driver and performs login ONLY ONCE
    for all tests in this module.
    """
    logger.info("Initializing driver and performing one-time login...")
    my_driver = Driver()
    try:
        my_driver.login_mpg()
        yield my_driver
    finally:
        logger.info("Closing driver after module tests.")
        my_driver.driver.quit()


@pytest.mark.end2end
@pytest.mark.parametrize(
    "match_url, expected_home, expected_outside",
    [
        # Case 1: Rouen vs NIKEU
        (
            "https://mpg.football/mpg-match/league/mpg_division_NKU1UAPG_11_1/mpg_division_match_NKU1UAPG_11_1_6_3_3_2",
            PlayerResult(
                is_home_team=True,
                name="FC Rouen Métropole",
                score=0,
                list_bonus=[
                    BonusName.capitaine,
                    BonusName.four_defense,
                    BonusName.cheat_code,
                ],
            ),
            PlayerResult(
                is_home_team=False,
                name="NIKEU",
                score=2,
                list_bonus=[
                    BonusName.capitaine,
                    BonusName.four_defense,
                    BonusName.zahia,
                ],
            ),
        ),
        # Case 2: Baptoz vs KABZ (No bonus for away team)
        (
            "https://mpg.football/mpg-match/league/mpg_division_NKU1UAPG_11_1/mpg_division_match_NKU1UAPG_11_1_6_1_0_5",
            PlayerResult(
                is_home_team=True,
                name="Baptoz",
                score=4,
                list_bonus=[
                    BonusName.capitaine,
                    BonusName.four_defense,
                    BonusName.zahia,
                ],
            ),
            PlayerResult(
                is_home_team=False,
                name="KABZ",
                score=1,
                list_bonus=[],
            ),
        ),
        # Case 3: No bonus for home and away team
        (
            "https://mpg.football/mpg-match/league/mpg_division_NKU1UAPG_11_3/mpg_division_match_NKU1UAPG_11_3_6_1_4_5",
            PlayerResult(
                is_home_team=True,
                name="aymericn10",
                score=2,
                list_bonus=[],
            ),
            PlayerResult(
                is_home_team=False,
                name="Tchouinamax",
                score=5,
                list_bonus=[],
            ),
        ),
    ],
)
def test_mpg_match_data_extraction(
    logged_in_driver, match_url, expected_home, expected_outside
):
    """
    End-to-end test:
        - Logs into MPG
        - Navigates to a parametrized match URL
        - Validates extracted PlayerResult (Home & Outside) against expected data
    """
    driver = logged_in_driver.driver

    logger.info(f"Navigating to match: {match_url}")
    driver.get(match_url)

    # Execution
    home_player, outside_player = get_match_data(driver)
    # Assertions for Home Player
    assert home_player.name == expected_home.name
    assert home_player.score == expected_home.score
    assert home_player.list_bonus == expected_home.list_bonus
    assert home_player.is_home_team is True

    # Assertions for Outside Player
    assert outside_player.name == expected_outside.name
    assert outside_player.score == expected_outside.score
    assert outside_player.list_bonus == expected_outside.list_bonus
    assert outside_player.is_home_team is False

    logger.info(
        f"Validation successful for {home_player.name} vs {outside_player.name}"
    )


@pytest.mark.end2end
def test_goal_breakdown_extraction(logged_in_driver):
    """
    End-to-end test:
        - Logs into MPG
        - Navigates to a known match URL
        - Validates MPG vs real goal counts for both teams
    """
    driver = logged_in_driver.driver
    match_url = "https://mpg.football/mpg-match/league/mpg_division_NKU1UAPG_11_2/mpg_division_match_NKU1UAPG_11_2_8_2_5_3"

    logger.info(f"Navigating to match for goal breakdown: {match_url}")
    driver.get(match_url)

    home_mpg, home_real, away_mpg, away_real = get_goal_breakdown(driver)

    assert home_mpg == 0
    assert home_real == 2
    assert away_mpg == 1
    assert away_real == 6
