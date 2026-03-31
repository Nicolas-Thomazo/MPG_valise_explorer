import pytest

from mpg_explorer import logger
from mpg_explorer.models.league_match_urls import MatchweekUrls
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
def test_find_matchs_urls_one_week_returns_unplayed_placeholders(logged_in_driver):
    """Upcoming matchweek cards should still produce placeholder rows."""
    league_scrapper = LeagueScrapper(
        driver=logged_in_driver.driver,
        league_id="NKU1UAPG",
        season_nb=12,
        division=2,
    )

    result = league_scrapper.find_matchs_urls_one_week(matchweek=4)

    assert isinstance(result, MatchweekUrls)
    assert len(result.urls) == 4
    assert all(url is None or "mpg-match" in url for url in result.urls)
    assert result.matches_played == [False, False, False, False]
    assert all(name is not None for name in result.home_team_names)
    assert all(name is not None for name in result.visitor_team_names)
