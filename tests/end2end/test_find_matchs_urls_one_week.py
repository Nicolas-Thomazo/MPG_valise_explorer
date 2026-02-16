import pytest
from mpg_explorer.utils.driver import Driver
from mpg_explorer.scrap.league import LeagueScrapper
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
    "league_url, division,list_expected_url",
    [
        (
            "https://mpg.football/league/mpg_league_NKU1UAPG/mpg_division_NKU1UAPG_10_1/results",
            1,
            [
                "https://mpg.football/mpg-match/league/mpg_division_NKU1UAPG_10_1/mpg_division_match_NKU1UAPG_10_1_10_1_1_5",
                "https://mpg.football/mpg-match/league/mpg_division_NKU1UAPG_10_1/mpg_division_match_NKU1UAPG_10_1_10_2_0_4",
                "https://mpg.football/mpg-match/league/mpg_division_NKU1UAPG_10_1/mpg_division_match_NKU1UAPG_10_1_10_3_2_3",
            ],
        ),
        (
            "https://mpg.football/league/mpg_league_NKU1UAPG/mpg_division_NKU1UAPG_10_2/results",
            2,
            [
                "https://mpg.football/mpg-match/league/mpg_division_NKU1UAPG_10_2/mpg_division_match_NKU1UAPG_10_2_10_1_5_4",
                "https://mpg.football/mpg-match/league/mpg_division_NKU1UAPG_10_2/mpg_division_match_NKU1UAPG_10_2_10_2_0_2",
                "https://mpg.football/mpg-match/league/mpg_division_NKU1UAPG_10_2/mpg_division_match_NKU1UAPG_10_2_10_3_1_3",
            ],
        ),
    ],
)
def test_find_matchs_urls_one_week(
    logged_in_driver, league_url, division, list_expected_url
):
    """
    End-to-end test:
        - Logs into MPG
        - Navigates to a league calendar page
        - Scrapes all match URLs on the page
        - Verifies that we got a list of URLs
    """
    driver = logged_in_driver.driver

    logger.info(f"Navigating to league page: {league_url}")
    league_scrapper = LeagueScrapper(driver=driver, season_nb=10, division=division)
    found_urls = league_scrapper.find_matchs_urls_one_week()
    logger.info(f"URLs found: {found_urls}")

    assert isinstance(found_urls, list), "The output should be a list"
    assert found_urls == list_expected_url
