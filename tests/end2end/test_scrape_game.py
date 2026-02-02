"""End-to-end tests for MPG authentication using Selenium."""

import pytest
from mpg_explorer.utils.driver import Driver
from mpg_explorer.scrap.game_info import get_match_data, PlayerResult
from mpg_explorer import logger


@pytest.fixture
def my_driver():
    my_driver = Driver()
    yield my_driver
    my_driver.driver.quit()


@pytest.mark.end2end
def test_mpg_authentication_success(my_driver):
    """
    End-to-end test:
        - Logs into MPG website
        - Navigates to a specific match page
        - Extracts match data including team names, scores, and bonuses
        - Validates the extracted data against expected values
    """
    driver = my_driver.driver

    expected_home_player = PlayerResult(
        is_home_team=True,
        name="FC Rouen Métropole",
        score=0,
        list_bonus=["Capitaine", "4 défenseurs"],
    )
    expected_outside_player = PlayerResult(
        is_home_team=False,
        name="NIKEU",
        score=2,
        list_bonus=["Capitaine", "4 défenseurs", "Zahia"],
    )
    try:
        my_driver.login_mpg()
        my_driver.driver.get(
            "https://mpg.football/mpg-match/league/mpg_division_NKU1UAPG_11_1/mpg_division_match_NKU1UAPG_11_1_6_3_3_2"
        )
        home_player, outside_player = get_match_data(my_driver.driver)
        assert isinstance(home_player, PlayerResult), (
            "home_player is not a PlayerResult"
        )
        assert isinstance(outside_player, PlayerResult), (
            "outside_player is not a PlayerResult"
        )

        assert home_player == expected_home_player, (
            f"home_player data does not match expected values. Expected: {expected_home_player}, Got: {home_player}"
        )
        assert outside_player == expected_outside_player, (
            f"outside_player data does not match expected values. Expected: {expected_outside_player}, Got: {outside_player}"
        )

    except Exception as e:
        logger.error(f"Error while extracting match data: {e}")
        assert False, f"Test failed due to error: {e}"

    finally:
        driver.quit()
