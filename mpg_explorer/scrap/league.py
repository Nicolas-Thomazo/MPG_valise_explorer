"""Module to scrap league data from MPG website."""

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By

from mpg_explorer.scrap.game import Game
from selenium.webdriver.support import expected_conditions as EC

from mpg_explorer import logger, LEAGUE_CONFIG
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver import Chrome
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains


class LeagueScrapper:
    def __init__(
        self,
        driver: Chrome,
        league_id: str = LEAGUE_CONFIG.LEAGUE_ID,
        # result_link: str = LEAGUE_CONFIG.RESULT_LINK,
        season_nb: int = LEAGUE_CONFIG.SEASON_NUMBER,
        division: int = LEAGUE_CONFIG.DIVISION,
        nb_players: int = LEAGUE_CONFIG.NUMBER_PLAYERS,
        matchweeks: list = LEAGUE_CONFIG.MATCHWEEK,
    ):
        """
        Initialise League scrapper class

        Args:
            driver (Chrome): Chrome driver
            league_id (str): Id of the mpg league
            results_link (str): Link of the results page of one week of the league
            season_nb (str): Number of the season in the league
            division (int): Division of the league
            nb_players (int): Number of players in the league
            matchweeks (list): List of matchweeks to scrap
        """
        self.driver = driver
        self.league_id = league_id
        self.season_nb = season_nb
        self.division = division
        self.nb_players = nb_players
        self.results_link = self.get_result_link()

        self.driver.get(self.results_link)

    def get_result_link(self) -> str:
        """URL to the results page of the configured league."""
        return (
            f"https://mpg.football/league/mpg_league_{self.league_id}"
            f"/mpg_division_{self.league_id}_"
            f"{self.season_nb}_{self.division}/results"
        )

    def scrap_league_games_urls(self):
        """
        Scrap games from a specific league. By default all matches of the season
        otherwise only the matches in 'matchweeks' list

        1- Set 'matchweek_start' to the current matchweek (to know when you've made a loop)
        2- While as matchweek + 1 is not equal to matchweek_start, we continue scrapping.
            If it is, this means we'll start again from the first matchweek we traversed.
            3- If the current matchweek is in the list,
                or if matchweek is empty (meaning we want to scrap all games), we scrap it.

        Args:
            matchweeks (list, optional): list of int of matchweeks to scrap, defaults to []
        """
        logger.info(f"[{self.league_id=}] Starting league scraping for league")
        matchweeks_scrapped = []
        for matchweek in matchweeks:
            logger.info(f"[{self.league_id=}][{matchweek}] scrapping one week")
            list_matchs_urls: list[str] = self.find_matchs_urls_one_week(
                matchweek=matchweek
            )
            matchweeks_scrapped.append(matchweek)
        logger.info(
            f"[{self.league_id=}] matchweek scrapped : {matchweeks_scrapped} {list_matchs_urls}"
        )
        if len(list_matchs_urls) != len(matchweeks_scrapped):
            raise ValueError(
                f"The length of the urls scrapped should be the same as matchweeks asked. Got {len(list_matchs_urls)} urls for {len(matchweeks_scrapped)} matchs asked."
            )
        return list_matchs_urls

    def find_matchs_urls_one_week(self) -> list[str]:
        """
        Iterate on every match of a given matchweek and retrieve their URLs.

        This method handles Single Page Applications (SPA) where clicking a match
        changes the page context. It uses an index-based approach to avoid
        StaleElementReferenceException by re-fetching the list at each iteration.

        Args:
            matchweek (int): The matchweek number (currently unused in logic but
                            reserved for navigation logic).

        Returns:
            list[str]: A list of absolute URLs for each match found.
        """
        list_matchs_urls: list[str] = []

        # 1. Get total count of matches
        try:
            total_matches = self._get_matches_count()
            logger.info(
                f"[league_id={self.league_id}] Found {total_matches} matches to scrape."
            )
        except TimeoutException:
            logger.warning(f"[league_id={self.league_id}] No matches found or timeout.")
            return []

        # 2. Iterate by index
        for index in range(total_matches):
            try:
                logger.info(f"Processing match {index + 1}/{total_matches}...")
                match_url = self._extract_url_from_match_index(index)

                if match_url:
                    list_matchs_urls.append(match_url)

            except Exception as exc:
                logger.error(f"Failed to scrape match at index {index}: {exc}")
                # Try to recover navigation if we are stuck on a sub-page
                if "mpg-match" in self.driver.current_url:
                    self.driver.back()
                continue

        logger.info(
            f"[league_id={self.league_id}] Successfully scrapped {len(list_matchs_urls)} match URLs."
        )
        return list_matchs_urls

    def _get_matches_count(self) -> int:
        """
        Waits for the score elements to appear and returns the count.

        Returns:
            int: Number of match elements visible.
        """
        elements = self._wait_for_scores_elements()
        return len(elements)

    def _extract_url_from_match_index(self, index: int) -> str:
        """
        Performs the navigation sequence: Find List -> Click Item(i) -> Get URL -> Back.

        Args:
            index (int): The index of the match in the list.

        Returns:
            str: The URL of the match.
        """
        # A. Re-fetch the fresh list of elements
        scores = self._wait_for_scores_elements()

        if index >= len(scores):
            raise IndexError("Match index out of range (DOM might have changed).")

        target_score = scores[index]

        # B. Ensure clickable and Click
        self._click_score_element(target_score)

        # C. Capture URL
        # Optional: Wait briefly for URL update if strictly necessary
        # WebDriverWait(self.driver, 5).until(lambda d: "mpg-match" in d.current_url)
        match_url = self.driver.current_url

        # D. Go Back to the list
        self.driver.back()

        # E. Wait for the list to reappear before returning control
        self._wait_for_list_to_reload()

        return match_url

    def _wait_for_scores_elements(self) -> list:
        """
        Wraps the wait logic to retrieve score elements.
        Replaces the standalone 'wait_for_scores' function.
        """
        # Remplacez ceci par votre appel existant: return wait_for_scores(self.driver)
        # Voici une implémentation standard basée sur votre xpath:
        xpath = get_button_score_balise()  # Supposé importé
        return WebDriverWait(self.driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, xpath))
        )

    def _click_score_element(self, element):
        """Scrolls to element and clicks it."""
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", element
        )
        WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(element))
        element.click()

    def _wait_for_list_to_reload(self):
        """Waits for the main list container to be present again after navigation."""
        xpath = get_button_score_balise()
        WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )


##########################
#### Helper functions ####
##########################


def get_button_score_balise():
    """
    Get balise of score inside the result page.

    Returns:
        str: The XPath of the score element
    """
    DIGITS = "0123456789"
    ALLOWED_SCORE_CHARS = f"{DIGITS} -"

    HAS_DASH_SEPARATOR = "contains(normalize-space(.), ' - ')"
    ONLY_ALLOWED_CHARS = (
        f"string-length(translate(normalize-space(.), '{ALLOWED_SCORE_CHARS}', '')) = 0"
    )
    SCORE_P_XPATH: str = f"//p[{HAS_DASH_SEPARATOR} and {ONLY_ALLOWED_CHARS}]"
    return SCORE_P_XPATH


def wait_for_scores(driver: Chrome, timeout: int = 10) -> list:
    """
    Wait until score elements are present in the DOM.

    Args:
        driver (Chrome): selenium driver
        timeout (int, optional): Maximum time to wait. Defaults to 10.

    Returns:
        list: List of score elements found in the DOM
    """
    score_xpath = get_button_score_balise()
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_all_elements_located((By.XPATH, score_xpath))
    )
