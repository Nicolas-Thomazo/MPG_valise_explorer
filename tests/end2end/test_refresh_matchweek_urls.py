import pytest

from mpg_explorer import logger
from mpg_explorer.models.league_match_urls import LeagueMatchUrls
from mpg_explorer.scrap.league import LeagueScrapper
from mpg_explorer.utils.driver import Driver


@pytest.fixture(scope="module")
def logged_in_driver():
    """Fixture that initializes the driver and performs login once."""
    logger.info("Initializing driver and performing one-time login...")
    my_driver = Driver()
    try:
        my_driver.login_mpg()
        yield my_driver
    finally:
        logger.info("Closing driver after module tests.")
        my_driver.driver.quit()


@pytest.mark.end2end
def test_find_matchs_urls_all_matchweeks_refresh_one_week(logged_in_driver):
    """
    Regression test for refresh flows that re-open an already selected matchweek.

    The season 11 / division 1 / matchweek 10 page is the path exercised by the
    notebook refresh flow and previously returned zero URLs after repeated
    re-selection attempts.
    """
    league_scrapper = LeagueScrapper(
        driver=logged_in_driver.driver,
        league_id="NKU1UAPG",
        season_nb=11,
        division=1,
    )

    result = league_scrapper.find_matchs_urls_all_matchweeks(
        matchweeks=[10],
        use_storage_verification=False,
    )

    assert isinstance(result, LeagueMatchUrls)
    assert [matchweek.matchweek for matchweek in result.matchweeks] == [10]

    matchweek_10 = result.matchweeks[0]
    assert len(matchweek_10.urls) == 3
    assert len(matchweek_10.matches_played) == 3
    assert all("mpg-match" in url for url in matchweek_10.urls)
    assert all(matchweek_10.matches_played)
