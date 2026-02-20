"""Module to scrap league data from MPG website."""

import re
from pathlib import Path
from uuid import uuid4

import polars as pl
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import Chrome
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from mpg_explorer import LEAGUE_CONFIG, logger
from mpg_explorer.models.league_match_urls import LeagueMatchUrls, MatchweekUrls
from mpg_explorer.models.match_result import Match
from mpg_explorer.scrap.game_info import get_match_data
from mpg_explorer.storage.league_matches_parquet import (
    get_matchweeks_with_unplayed_matches,
    get_scraped_league_matches_parquet_path,
    save_scraped_league_matches_to_parquet,
)


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
        self.matchweeks = matchweeks
        self.results_link = self.get_result_link()

        self.driver.get(self.results_link)

    def get_result_link(self) -> str:
        """URL to the results page of the configured league."""
        return (
            f"https://mpg.football/league/mpg_league_{self.league_id}"
            f"/mpg_division_{self.league_id}_"
            f"{self.season_nb}_{self.division}/results"
        )

    def find_matchs_urls_one_week(self, matchweek: int | None = None) -> MatchweekUrls:
        """
        Iterate on every match of a given matchweek and retrieve their URLs.

        This method handles Single Page Applications (SPA) where clicking a match
        changes the page context. It uses an index-based approach to avoid
        StaleElementReferenceException by re-fetching the list at each iteration.

        Args:
            matchweek (int): The matchweek number (currently unused in logic but
                            reserved for navigation logic).

        Returns:
            MatchweekUrls: Matchweek payload with URLs and played status list.
        """
        list_matchs_urls: list[str] = []
        list_matches_played: list[bool] = []

        # 1. Get total count of matches
        try:
            total_matches = self._get_matches_count()
            logger.info(
                f"[league_id={self.league_id}] Found {total_matches} matches to scrape."
            )
        except TimeoutException:
            logger.warning(f"[league_id={self.league_id}] No matches found or timeout.")
            return MatchweekUrls(
                matchweek=matchweek or 0,
                urls=[],
                matches_played=[],
            )

        # 2. Iterate by index
        for index in range(total_matches):
            done = False
            for _ in range(3):
                try:
                    if matchweek is not None:
                        self._select_matchweek(matchweek)

                    logger.info(f"Processing match {index + 1}/{total_matches}...")
                    match_url, is_match_played = self._extract_url_from_match_index(index)

                    if match_url and match_url not in list_matchs_urls:
                        list_matchs_urls.append(match_url)
                        list_matches_played.append(is_match_played)
                    done = True
                    break
                except Exception as exc:
                    logger.error(f"Failed to scrape match at index {index}: {exc}")
                    # Try to recover navigation if we are stuck on a sub-page
                    if "mpg-match" in self.driver.current_url:
                        self.driver.back()
                    self._wait_for_list_to_reload()
                    continue
            if not done:
                logger.warning(
                    f"[league_id={self.league_id}] Could not scrape match at index {index} after retries."
                )

        logger.info(
            f"[league_id={self.league_id}] Successfully scrapped {len(list_matchs_urls)} match URLs."
        )
        return MatchweekUrls(
            matchweek=matchweek or 0,
            urls=list_matchs_urls,
            matches_played=list_matches_played,
        )

    def find_matchs_urls_all_matchweeks(
        self,
        matchweeks: list[int] | None = None,
        use_storage_verification: bool = True,
        data_path: Path | None = None,
    ) -> LeagueMatchUrls:
        """
        Iterates on available matchweeks and returns all match URLs grouped by matchweek.

        If `matchweeks` is not provided and `use_storage_verification` is True,
        it checks the parquet export and only keeps matchweeks containing
        at least one pending match (`match_played = False` or
        `error_in_scrapping = True`).

        Returns:
            LeagueMatchUrls: Structured URLs grouped by matchweek.
        """
        results: dict[int, MatchweekUrls] = {}
        target_matchweeks = matchweeks
        if target_matchweeks is None and use_storage_verification:
            target_matchweeks = get_matchweeks_with_unplayed_matches(
                league_id=self.league_id,
                season_number=self.season_nb,
                division=self.division,
                data_path=data_path or LEAGUE_CONFIG.DATA_PATH,
            )
            if target_matchweeks is None:
                logger.info(
                    f"[league_id={self.league_id}] No compatible parquet verification found. Scraping all matchweeks."
                )
            else:
                logger.info(
                    f"[league_id={self.league_id}] Parquet verification selected matchweeks: {target_matchweeks}"
                )

        if target_matchweeks == []:
            logger.info(
                f"[league_id={self.league_id}] No matchweek to scrape after parquet verification."
            )
            return LeagueMatchUrls(
                league_id=self.league_id,
                division=self.division,
                season_number=self.season_nb,
                matchweeks=[],
            )

        target_matchweeks_set = set(target_matchweeks) if target_matchweeks else None
        total_matchweeks = self._get_matchweeks_count()
        logger.info(
            f"[league_id={self.league_id}] Found {total_matchweeks} matchweeks in selector."
        )

        for index in range(total_matchweeks):
            self._open_matchweek_dropdown()
            options = self._wait_for_matchweek_options()
            if index >= len(options):
                logger.warning(
                    f"[league_id={self.league_id}] Matchweek option index {index} out of range."
                )
                break

            option = options[index]
            option_label = option.text
            matchweek = self._extract_matchweek_from_label(option_label)
            if matchweek is None:
                logger.warning(
                    f"[league_id={self.league_id}] Could not parse matchweek number from option '{option_label}'. Skipping."
                )
                continue
            if (
                target_matchweeks_set is not None
                and matchweek not in target_matchweeks_set
            ):
                continue

            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", option
            )
            try:
                option.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", option)
            try:
                self._wait_for_matchweek_applied(matchweek, timeout=5)
            except TimeoutException:
                logger.warning(
                    f"[league_id={self.league_id}] Could not confirm selected matchweek {matchweek} from button label; continuing."
                )

            logger.info(
                f"[league_id={self.league_id}][matchweek={matchweek}] Scrapping match URLs."
            )
            results[matchweek] = self.find_matchs_urls_one_week(matchweek=matchweek)

        logger.info(
            f"[league_id={self.league_id}] Finished scraping all matchweeks: {sorted(results.keys())}"
        )
        ordered_matchweeks = [
            MatchweekUrls(
                matchweek=week,
                urls=results[week].urls,
                matches_played=results[week].matches_played,
            )
            for week in sorted(results.keys())
        ]
        return LeagueMatchUrls(
            league_id=self.league_id,
            division=self.division,
            season_number=self.season_nb,
            matchweeks=ordered_matchweeks,
        )

    def scrape_matches_dataframe(
        self, league_urls: LeagueMatchUrls | None = None
    ) -> pl.DataFrame:
        """
        Scrape match rows for the provided URLs and return them as a dataframe.

        Args:
            league_urls: Optional pre-fetched match URLs grouped by matchweek.

        Returns:
            pl.DataFrame: One row per match, including `match_played`.
        """
        if league_urls is None:
            league_urls = self.find_matchs_urls_all_matchweeks(
                use_storage_verification=False
            )

        rows: list[dict] = []
        for matchweek_data in league_urls.matchweeks:
            matchweek = matchweek_data.matchweek
            logger.info(
                f"[matchweek={matchweek}] Scraping {len(matchweek_data.urls)} matches."
            )

            for match_url, match_played in zip(
                matchweek_data.urls, matchweek_data.matches_played, strict=True
            ):
                row = Match(
                    match_id=str(uuid4()),
                    league_id=self.league_id,
                    division=self.division,
                    season_number=self.season_nb,
                    matchweek=matchweek,
                    match_played=match_played,
                    error_in_scrapping=False,
                ).model_dump(mode="json")

                if match_played:
                    try:
                        self.driver.get(match_url)
                        home_player, away_player = get_match_data(driver=self.driver)
                        row.update(
                            {
                                "home_team_name": home_player.name,
                                "home_total_goals": home_player.score,
                                "home_bonus": [bonus.value for bonus in home_player.list_bonus],
                                "visitor_team_name": away_player.name,
                                "visitor_total_goals": away_player.score,
                                "visitor_bonus": [
                                    bonus.value for bonus in away_player.list_bonus
                                ],
                            }
                        )
                    except Exception as exc:
                        logger.warning(
                            f"[league_id={self.league_id}][matchweek={matchweek}] Failed to scrape match '{match_url}': {exc}"
                        )
                        row["error_in_scrapping"] = True
                        row["match_played"] = False
                rows.append(row)

        if not rows:
            return self._empty_matches_dataframe()
        return pl.DataFrame(rows)

    def scrape_league_with_verification(
        self, data_path: Path | None = None
    ) -> pl.DataFrame:
        """
        Scrape league data incrementally by reusing existing parquet exports.

        Behavior:
            - If no parquet exists, scrape all matchweeks.
            - If parquet lacks `match_played`, scrape all matchweeks.
            - If no unplayed matches exist, reuse current parquet rows.
            - Otherwise, scrape only matchweeks that still contain unplayed matches.

        Args:
            data_path: Optional storage directory overriding configured data path.

        Returns:
            pl.DataFrame: Refreshed dataframe ready to be saved.
        """
        target_data_path = data_path or LEAGUE_CONFIG.DATA_PATH
        try:
            parquet_path = get_scraped_league_matches_parquet_path(
                league_id=self.league_id,
                season_number=self.season_nb,
                division=self.division,
                data_path=target_data_path,
            )
        except FileNotFoundError:
            logger.info(
                f"[league_id={self.league_id}] No parquet found. Scraping all matchweeks."
            )
            league_urls = self.find_matchs_urls_all_matchweeks(
                use_storage_verification=False, data_path=target_data_path
            )
            return self.scrape_matches_dataframe(league_urls=league_urls)

        df_existing = pl.read_parquet(str(parquet_path))
        matchweeks_to_refresh = get_matchweeks_with_unplayed_matches(
            league_id=self.league_id,
            season_number=self.season_nb,
            division=self.division,
            data_path=target_data_path,
        )

        if matchweeks_to_refresh is None:
            logger.info(
                f"[league_id={self.league_id}] Legacy parquet schema. Scraping all matchweeks."
            )
            league_urls = self.find_matchs_urls_all_matchweeks(
                use_storage_verification=False, data_path=target_data_path
            )
            return self.scrape_matches_dataframe(league_urls=league_urls)

        if not matchweeks_to_refresh:
            logger.info(
                f"[league_id={self.league_id}] No unplayed matches found in parquet. Reusing current data."
            )
            return df_existing

        logger.info(
            f"[league_id={self.league_id}] Refreshing matchweeks: {matchweeks_to_refresh}"
        )
        league_urls = self.find_matchs_urls_all_matchweeks(
            matchweeks=matchweeks_to_refresh,
            use_storage_verification=False,
            data_path=target_data_path,
        )
        matchweeks_with_urls = [
            matchweek_data for matchweek_data in league_urls.matchweeks if matchweek_data.urls
        ]
        if not matchweeks_with_urls:
            logger.info(
                f"[league_id={self.league_id}] No match URLs found for pending matchweeks. Keeping current parquet rows."
            )
            return df_existing

        if len(matchweeks_with_urls) != len(league_urls.matchweeks):
            missing_matchweeks = sorted(
                {
                    matchweek_data.matchweek
                    for matchweek_data in league_urls.matchweeks
                    if not matchweek_data.urls
                }
            )
            logger.warning(
                f"[league_id={self.league_id}] Skipping matchweeks with no URLs: {missing_matchweeks}"
            )

        filtered_league_urls = LeagueMatchUrls(
            league_id=league_urls.league_id,
            division=league_urls.division,
            season_number=league_urls.season_number,
            matchweeks=matchweeks_with_urls,
        )
        refreshed_matchweeks = [item.matchweek for item in matchweeks_with_urls]
        df_refresh = self.scrape_matches_dataframe(league_urls=filtered_league_urls)

        return pl.concat(
            [
                df_existing.filter(~pl.col("matchweek").is_in(refreshed_matchweeks)),
                df_refresh,
            ],
            how="vertical_relaxed",
        )

    def scrape_and_save_league(
        self, data_path: Path | None = None
    ) -> tuple[pl.DataFrame, Path]:
        """
        Scrape league data with parquet verification and persist the result.

        Args:
            data_path: Optional storage directory overriding configured data path.

        Returns:
            tuple[pl.DataFrame, Path]: Scraped dataframe and written parquet path.
        """
        target_data_path = data_path or LEAGUE_CONFIG.DATA_PATH
        df = self.scrape_league_with_verification(data_path=target_data_path)
        parquet_path = save_scraped_league_matches_to_parquet(
            df=df,
            league_id=self.league_id,
            season_number=self.season_nb,
            division=self.division,
            data_path=target_data_path,
        )
        return df, parquet_path

    ##########################
    #### Utils scrapping ####
    ##########################
    def _empty_matches_dataframe(self) -> pl.DataFrame:
        """Build an empty match dataframe with a stable schema."""
        return pl.DataFrame(
            schema={
                "match_id": pl.String,
                "league_id": pl.String,
                "division": pl.Int64,
                "season_number": pl.Int64,
                "matchweek": pl.Int64,
                "match_played": pl.Boolean,
                "error_in_scrapping": pl.Boolean,
                "home_team_name": pl.String,
                "home_total_goals": pl.Int64,
                "home_mpg_goals": pl.Int64,
                "home_real_goals": pl.Int64,
                "home_bonus": pl.List(pl.String),
                "visitor_team_name": pl.String,
                "visitor_total_goals": pl.Int64,
                "visitor_mpg_goals": pl.Int64,
                "visitor_real_goals": pl.Int64,
                "visitor_bonus": pl.List(pl.String),
            }
        )

    def _open_matchweek_dropdown(self):
        """Opens the matchweek dropdown selector."""
        dropdown_button_xpath_candidates = [
            "//button[@aria-haspopup='listbox' and @type='button']",
            "//button[@aria-haspopup='listbox']",
        ]

        button = None
        for attempt in range(2):
            if "results" not in self.driver.current_url:
                self.driver.get(self.results_link)

            for xpath in dropdown_button_xpath_candidates:
                try:
                    WebDriverWait(self.driver, 8).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
                    elements = self.driver.find_elements(By.XPATH, xpath)
                    button = next(
                        (element for element in elements if element.is_displayed()), None
                    )
                    if button is not None:
                        break
                except TimeoutException:
                    continue

            if button is not None:
                break
            self.driver.get(self.results_link)

        if button is None:
            raise TimeoutException(
                f"Could not find matchweek dropdown button on {self.driver.current_url}."
            )

        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", button
        )
        try:
            WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable(button))
            button.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", button)
        self._wait_for_matchweek_options()

    def _wait_for_matchweek_options(self) -> list:
        """Waits for matchweek dropdown options to be present."""
        options_xpath = "//ul[@role='listbox']//li[@role='option']"
        return WebDriverWait(self.driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, options_xpath))
        )

    def _get_matchweeks_count(self) -> int:
        """Returns the number of available matchweeks in the dropdown."""
        self._open_matchweek_dropdown()
        options = self._wait_for_matchweek_options()
        count = len(options)
        # Close the dropdown to avoid overlapping with next interactions.
        ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
        return count

    def _extract_matchweek_from_label(self, label: str) -> int | None:
        """
        Extracts numeric matchweek from labels like 'Journée 8'.
        """
        match = re.search(r"Journ[ée]e?\s+(\d+)", label, flags=re.IGNORECASE)
        if not match:
            return None
        return int(match.group(1))

    def _select_matchweek(self, matchweek: int):
        """Selects a specific matchweek from the dropdown."""
        self._open_matchweek_dropdown()
        option_xpath = f"//ul[@role='listbox']//li[@role='option' and .//*[contains(normalize-space(.), 'Journée {matchweek}')]]"
        option = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, option_xpath))
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", option
        )
        try:
            option.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", option)
        self._wait_for_matchweek_applied(matchweek)

    def _wait_for_matchweek_applied(self, matchweek: int, timeout: int = 15):
        """
        Waits until the selected matchweek label appears on the dropdown button.
        This is more robust than waiting for score cards because some matchweeks
        can legitimately have no displayed matches yet.
        """
        dropdown_button_xpath = "//button[@aria-haspopup='listbox' and @type='button']"
        WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, dropdown_button_xpath))
        )

        def _matchweek_visible_on_button(driver):
            buttons = driver.find_elements(By.XPATH, dropdown_button_xpath)
            button = next(
                (element for element in buttons if element.is_displayed()), None
            )
            if button is None:
                return False
            text = button.text or ""
            parsed = self._extract_matchweek_from_label(text)
            # Fallback for layouts like "Journée : 9 / 10"
            if parsed is None:
                numbers = re.findall(r"\d+", text)
                if numbers:
                    parsed = int(numbers[0])
            return parsed == matchweek

        WebDriverWait(self.driver, timeout).until(_matchweek_visible_on_button)

    def _get_matches_count(self) -> int:
        """
        Waits for the score elements to appear and returns the count.

        Returns:
            int: Number of match elements visible.
        """
        elements = self._wait_for_scores_elements()
        return len(elements)

    def _extract_url_from_match_index(self, index: int) -> tuple[str, bool]:
        """
        Performs the navigation sequence: Find List -> Click Item(i) -> Get URL -> Back.

        Args:
            index (int): The index of the match in the list.

        Returns:
            tuple[str, bool]: The match URL and whether the match has already been played.
        """
        # A. Re-fetch the fresh list of elements
        scores = self._wait_for_scores_elements()

        if index >= len(scores):
            raise IndexError("Match index out of range (DOM might have changed).")

        target_score = scores[index]
        is_match_played = _is_played_match(target_score.text or "")

        current_list_url = self.driver.current_url

        # B. Ensure clickable and click
        self._click_score_element(target_score)

        # C. Capture URL after navigation to match page
        WebDriverWait(self.driver, 8).until(
            lambda d: "mpg-match" in d.current_url and d.current_url != current_list_url
        )
        match_url = self.driver.current_url

        # D. Go Back to the list
        self.driver.back()

        # E. Wait for the list to reappear before returning control
        self._wait_for_list_to_reload()

        return match_url, is_match_played

    def _wait_for_scores_elements(self) -> list:
        """
        Wraps the wait logic to retrieve score elements.
        Replaces the standalone 'wait_for_scores' function.
        """
        # Remplacez ceci par votre appel existant: return wait_for_scores(self.driver)
        # Voici une implémentation standard basée sur votre xpath:
        xpath = get_button_score_balise()  # Supposé importé
        return WebDriverWait(self.driver, 12).until(
            EC.visibility_of_all_elements_located((By.XPATH, xpath))
        )

    def _click_score_element(self, element):
        """Scrolls to element and clicks it."""
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", element
        )
        try:
            WebDriverWait(self.driver, 6).until(EC.element_to_be_clickable(element))
            element.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", element)

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
    IS_VS_LABEL = (
        "translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz') = 'vs'"
    )
    SCORE_P_XPATH: str = (
        f"//p[({HAS_DASH_SEPARATOR} and {ONLY_ALLOWED_CHARS}) or {IS_VS_LABEL}]"
    )
    return SCORE_P_XPATH


def _is_played_match(match_text: str) -> bool:
    """
    Returns True when text looks like a played score (e.g. "2 - 1").
    """
    return bool(re.search(r"^\s*\d+\s*-\s*\d+\s*$", match_text))


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
