import pytest

from mpg_explorer import logger
from mpg_explorer.models.league_match_urls import LeagueMatchUrls
from mpg_explorer.scrap.league import LeagueScrapper
from mpg_explorer.utils.driver import Driver


LEAGUE_ID = "NKU1UAPG"
SEASON_NB = 10
DIVISION = 1
EXPECTED_MATCHWEEKS = list(range(1, 11))
EXPECTED_MATCH_COUNT_BY_WEEK = {week: 3 for week in EXPECTED_MATCHWEEKS}


def _extract_matchweek_from_url(url: str) -> int:
    """
    MPG URL format example:
    .../mpg_division_match_<...>_<matchweek>_<...>_<...>_<...>
    We read the 4th token from the end.
    """
    match_slug = url.rstrip("/").split("/")[-1]
    parts = match_slug.split("_")
    if len(parts) < 4:
        raise AssertionError(f"Unexpected MPG match URL format: {url}")
    return int(parts[-4])


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
def test_find_matchs_urls_all_matchweeks(logged_in_driver):
    """
    End-to-end test:
        - Logs into MPG
        - Navigates to a league result page
        - Iterates all matchweeks from the dropdown selector
        - Scrapes all match URLs for each matchweek
        - Verifies we passed through all expected matchweeks
    """

    driver = logged_in_driver.driver
    league_scrapper = LeagueScrapper(
        driver=driver,
        league_id=LEAGUE_ID,
        season_nb=SEASON_NB,
        division=DIVISION,
    )

    result = league_scrapper.find_matchs_urls_all_matchweeks()
    logger.info(f"URLs found by matchweek: {result}")

    assert isinstance(result, LeagueMatchUrls), "The output should be a LeagueMatchUrls"
    urls_by_matchweek = result.to_dict()
    assert sorted(urls_by_matchweek.keys()) == sorted(
        EXPECTED_MATCHWEEKS
    ), "The scraped matchweeks do not match expected matchweeks"

    for matchweek, urls in urls_by_matchweek.items():
        assert isinstance(urls, list), f"Week {matchweek}: expected list of URLs"
        assert all(
            isinstance(url, str) and "mpg-match" in url for url in urls
        ), f"Week {matchweek}: invalid URL found"
        for url in urls:
            assert _extract_matchweek_from_url(url) == matchweek, (
                f"Week {matchweek}: URL does not belong to this matchweek: {url}"
            )

    if EXPECTED_MATCH_COUNT_BY_WEEK:
        for week, expected_count in EXPECTED_MATCH_COUNT_BY_WEEK.items():
            assert week in urls_by_matchweek, f"Week {week} was not scraped"
            assert len(urls_by_matchweek[week]) == expected_count, (
                f"Week {week}: expected {expected_count} URLs, "
                f"got {len(urls_by_matchweek[week])}"
            )
