"""Module to scrap league data from MPG website."""

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By

from mpg_explorer.scrap.game import Game
from selenium.webdriver.support import expected_conditions as EC

from mpg_explorer import logger, LEAGUE_CONFIG
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver import Chrome


class LeagueScrapper:
    def __init__(
        self,
        driver: Chrome,
        league_id: str = LEAGUE_CONFIG.LEAGUE_ID,
        result_link: str = LEAGUE_CONFIG.RESULT_LINK,
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
        self.results_link = result_link
        self.season_nb = season_nb
        self.division = division
        self.nb_players = nb_players

        self.driver.get(self.results_link)

    def scrap_league(self, matchweeks: list = []):
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
        logger.info(f"Starting league scraping for league id {self.league_id}")
        matchweeks_scrapped = []
        for matchweek in matchweeks:
            list_matchs_urls: list[str] = self.iterate_on_matchs(matchweek=matchweek)
            matchweeks_scrapped.append(matchweek)
        logger.info(f"matchweek scrapped : {matchweeks_scrapped} {list_matchs_urls}")
        return list_matchs_urls

    def iterate_on_matchs(self, matchweek: int) -> list[str]:
        """
        Iterate on every matchs of a given matchweek and scrap them.

        Args:
            driver (Chrome): selenium driver
            matchweek (int): matchweek number to scrap

        Returns:
            list[str]: List of URLs of the scrapped matches
        """
        list_matchs_urls: list[str] = []
        scores = wait_for_scores(self.driver)
        logger.info(f"Found {len(scores)} scores")

        for index in range(len(scores)):
            try:
                score = scores[index]
                logger.info("Going back to previous page")
                match_url = self.scrape_matchweek(matchweek=matchweek, score=score)
                list_matchs_urls.append(match_url)
            except (StaleElementReferenceException, TimeoutException) as exc:
                logger.warning(f"Score {index} ignore: {exc}")
                continue

        logger.info(f"Scrapped {len(list_matchs_urls)} matchs")
        return list_matchs_urls

    def scrape_matchweek(self, matchweek: int, score):
        """
        Scrape a match from a given matchweek.

        Args:
            driver (Chrome): selenium driver
            matchweek (int): matchweek number to scrap
        """
        WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(score))
        score.click()
        match_url = self.driver.current_url
        try:
            Game(driver=self.driver, game_url=match_url, matchweek=matchweek)
        except Exception as exc:
            logger.error(f"Error while scraping match {match_url} : {exc}")
        finally:
            self.driver.back()

        score_xpath = get_button_score_balise()
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, score_xpath))
        )
        return match_url


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
