"""Module to scrap league data from MPG website."""

import re
from pathlib import Path
from urllib.parse import urljoin
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
from mpg_explorer.analytics.league_refresh import (
    align_dataframe_schema,
    build_inferred_unplayed_rows,
    build_pending_index_by_week,
    cleanup_legacy_error_rows,
    ensure_match_url_column,
    extend_refresh_matchweeks_with_missing_weeks,
    filter_matchweek_urls_to_pending,
    get_pending_rows,
    merge_refreshed_rows,
)
from mpg_explorer.models.league_match_urls import LeagueMatchUrls, MatchweekUrls
from mpg_explorer.models.match_dataframe import MatchColumn as MDC
from mpg_explorer.models.match_result import Match
from mpg_explorer.scrap.game_info import get_match_data
from mpg_explorer.scrap.goals import get_goal_breakdown
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
        list_home_team_names: list[str | None] = []
        list_visitor_team_names: list[str | None] = []

        # 1. Get total count of matches
        try:
            total_matches = self._get_matches_count()
            logger.info(
                f"[league_id={self.league_id}] Found {total_matches} matches to scrape."
            )
        except TimeoutException:
            logger.warning(
                f"[league_id={self.league_id}] No visible matches found. Falling back to page source URL extraction."
            )
            extracted_urls = self._extract_match_urls_from_page_source()
            if not extracted_urls:
                logger.warning(
                    f"[league_id={self.league_id}] No matches found or timeout."
                )
                return MatchweekUrls(
                    matchweek=matchweek or 0,
                    urls=[],
                    matches_played=[],
                    home_team_names=[],
                    visitor_team_names=[],
                )
            return MatchweekUrls(
                matchweek=matchweek or 0,
                urls=extracted_urls,
                matches_played=[False] * len(extracted_urls),
                home_team_names=[None] * len(extracted_urls),
                visitor_team_names=[None] * len(extracted_urls),
            )

        # 2. Iterate by index
        for index in range(total_matches):
            done = False
            for _ in range(3):
                try:
                    if matchweek is not None:
                        self._select_matchweek(matchweek)

                    logger.info(f"Processing match {index + 1}/{total_matches}...")
                    (
                        match_url,
                        is_match_played,
                        home_team_name,
                        visitor_team_name,
                    ) = self._extract_url_from_match_index(index)

                    if match_url and match_url not in list_matchs_urls:
                        list_matchs_urls.append(match_url)
                        list_matches_played.append(is_match_played)
                        list_home_team_names.append(home_team_name)
                        list_visitor_team_names.append(visitor_team_name)
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
            home_team_names=list_home_team_names,
            visitor_team_names=list_visitor_team_names,
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
                home_team_names=results[week].home_team_names,
                visitor_team_names=results[week].visitor_team_names,
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

            for i, (match_url, match_played) in enumerate(
                zip(matchweek_data.urls, matchweek_data.matches_played, strict=True)
            ):
                home_team_name = (
                    matchweek_data.home_team_names[i]
                    if i < len(matchweek_data.home_team_names)
                    else None
                )
                visitor_team_name = (
                    matchweek_data.visitor_team_names[i]
                    if i < len(matchweek_data.visitor_team_names)
                    else None
                )
                row = Match(
                    match_id=str(uuid4()),
                    match_url=match_url,
                    league_id=self.league_id,
                    division=self.division,
                    season_number=self.season_nb,
                    matchweek=matchweek,
                    match_played=match_played,
                    error_in_scrapping=False,
                    home_team_name=home_team_name,
                    visitor_team_name=visitor_team_name,
                ).model_dump(mode="json")

                if (
                    row.get(MDC.home_team_name) is None
                    or row.get(MDC.visitor_team_name) is None
                ):
                    (
                        fallback_home_name,
                        fallback_visitor_name,
                    ) = self._extract_team_names_from_match_url(match_url)
                    row[MDC.home_team_name] = (
                        row.get(MDC.home_team_name) or fallback_home_name
                    )
                    row[MDC.visitor_team_name] = (
                        row.get(MDC.visitor_team_name) or fallback_visitor_name
                    )

                if match_played:
                    try:
                        self.driver.get(match_url)
                        home_player, away_player = get_match_data(driver=self.driver)
                        (
                            home_mpg_goals,
                            home_real_goals,
                            away_mpg_goals,
                            away_real_goals,
                        ) = get_goal_breakdown(driver=self.driver)
                        row.update(
                            {
                                "home_team_name": home_player.name,
                                "home_total_goals": home_player.score,
                                "home_mpg_goals": home_mpg_goals,
                                "home_real_goals": home_real_goals,
                                "home_bonus": [
                                    bonus.value for bonus in home_player.list_bonus
                                ],
                                "visitor_team_name": away_player.name,
                                "visitor_total_goals": away_player.score,
                                "visitor_mpg_goals": away_mpg_goals,
                                "visitor_real_goals": away_real_goals,
                                "visitor_bonus": [
                                    bonus.value for bonus in away_player.list_bonus
                                ],
                            }
                        )
                    except Exception as exc:
                        logger.warning(
                            f"[league_id={self.league_id}][matchweek={matchweek}] Failed to scrape match '{match_url}': {exc}"
                        )
                        row[MDC.error_in_scrapping] = True
                        row[MDC.match_played] = False
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
            - If total scraped rows is lower than the expected season total,
              refresh only the latest matchweeks needed to close the gap.
            - If no unplayed matches and row count is complete, reuse current parquet rows.
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
        df_existing = ensure_match_url_column(df_existing)
        df_existing = cleanup_legacy_error_rows(
            df_existing=df_existing,
            nb_players=self.nb_players,
            league_id=self.league_id,
            logger=logger,
        )
        pending_rows = get_pending_rows(df_existing)
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

        matchweeks_to_refresh = extend_refresh_matchweeks_with_missing_weeks(
            df_existing=df_existing,
            matchweeks_to_refresh=matchweeks_to_refresh,
            nb_players=self.nb_players,
            league_id=self.league_id,
            logger=logger,
        )

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
        pending_index_by_week = build_pending_index_by_week(pending_rows)
        matchweeks_with_urls = [
            matchweek_data
            for matchweek_data in league_urls.matchweeks
            if matchweek_data.urls
        ]
        if not matchweeks_with_urls:
            logger.info(
                f"[league_id={self.league_id}] No match URLs found for pending matchweeks. "
                "Trying inferred placeholders for unplayed matchweeks."
            )
            inferred_rows = build_inferred_unplayed_rows(
                df_existing=df_existing,
                target_matchweeks=matchweeks_to_refresh,
                league_id=self.league_id,
                division=self.division,
                season_nb=self.season_nb,
                nb_players=self.nb_players,
                logger=logger,
            )
            if inferred_rows.is_empty():
                logger.info(
                    f"[league_id={self.league_id}] No inferred placeholders available. Keeping current parquet rows."
                )
                return df_existing

            inferred_rows = align_dataframe_schema(
                df=inferred_rows,
                target_columns=df_existing.columns,
            )
            merged = merge_refreshed_rows(
                df_existing=df_existing,
                df_refresh=inferred_rows,
            )
            return ensure_match_url_column(merged)

        matchweeks_with_urls = [
            filter_matchweek_urls_to_pending(
                matchweek_data=matchweek_data,
                pending_index_by_week=pending_index_by_week,
                league_id=self.league_id,
                logger=logger,
            )
            for matchweek_data in matchweeks_with_urls
        ]
        matchweeks_with_urls = [
            matchweek_data
            for matchweek_data in matchweeks_with_urls
            if matchweek_data.urls
        ]
        if not matchweeks_with_urls:
            logger.info(
                f"[league_id={self.league_id}] No pending matches left after row-level filtering. Keeping current parquet rows."
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
        df_refresh = self.scrape_matches_dataframe(league_urls=filtered_league_urls)

        merged = merge_refreshed_rows(
            df_existing=df_existing,
            df_refresh=df_refresh,
        )
        return ensure_match_url_column(merged)

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
                MDC.match_id: pl.String,
                MDC.match_url: pl.String,
                MDC.league_id: pl.String,
                MDC.division: pl.Int64,
                MDC.season_number: pl.Int64,
                MDC.matchweek: pl.Int64,
                MDC.match_played: pl.Boolean,
                MDC.error_in_scrapping: pl.Boolean,
                MDC.home_team_name: pl.String,
                MDC.home_total_goals: pl.Int64,
                MDC.home_mpg_goals: pl.Int64,
                MDC.home_real_goals: pl.Int64,
                MDC.home_bonus: pl.List(pl.String),
                MDC.visitor_team_name: pl.String,
                MDC.visitor_total_goals: pl.Int64,
                MDC.visitor_mpg_goals: pl.Int64,
                MDC.visitor_real_goals: pl.Int64,
                MDC.visitor_bonus: pl.List(pl.String),
            }
        )

    def _open_matchweek_dropdown(self):
        """Opens the matchweek dropdown selector."""
        dropdown_button_xpath_candidates = [
            "//button[@aria-haspopup='listbox' and @type='button']",
            "//button[@aria-haspopup='listbox']",
        ]

        button = None
        for attempt in range(3):
            if "results" not in self.driver.current_url:
                self.driver.get(self.results_link)

            # Close potential stale overlays before opening the dropdown.
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()

            for xpath in dropdown_button_xpath_candidates:
                try:
                    WebDriverWait(self.driver, 8).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
                    elements = self.driver.find_elements(By.XPATH, xpath)
                    button = next(
                        (element for element in elements if element.is_displayed()),
                        None,
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

        open_last_error: Exception | None = None
        for _ in range(3):
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", button
            )
            try:
                WebDriverWait(self.driver, 5).until(
                    lambda d: button.is_displayed() and button.is_enabled()
                )
                try:
                    button.click()
                except Exception:
                    # Fallbacks for flaky react/styled buttons.
                    self.driver.execute_script("arguments[0].click();", button)

                # If the menu does not open, try keyboard activation.
                if not self._wait_for_matchweek_options(
                    timeout=4, raise_on_timeout=False
                ):
                    button.send_keys(Keys.ENTER)
                    if not self._wait_for_matchweek_options(
                        timeout=3, raise_on_timeout=False
                    ):
                        button.send_keys(Keys.SPACE)

                self._wait_for_matchweek_options(timeout=6)
                return
            except Exception as exc:
                open_last_error = exc
                # Re-acquire button if DOM re-rendered.
                for xpath in dropdown_button_xpath_candidates:
                    elements = self.driver.find_elements(By.XPATH, xpath)
                    button = next(
                        (element for element in elements if element.is_displayed()),
                        button,
                    )
                    if button is not None:
                        break

        raise TimeoutException(
            f"Could not open matchweek dropdown on {self.driver.current_url}. "
            f"Last error: {open_last_error}"
        )

    def _wait_for_matchweek_options(
        self, timeout: int = 10, raise_on_timeout: bool = True
    ) -> list:
        """Wait for visible matchweek options in the dropdown.

        Supports both strict listbox semantics and more permissive role-based options
        to handle minor MPG frontend changes.
        """
        options_xpaths = [
            "//ul[@role='listbox']//li[@role='option']",
            "//*[@role='listbox']//*[@role='option']",
            "//*[@role='option']",
        ]

        def _find_visible_options(driver):
            for xpath in options_xpaths:
                options = driver.find_elements(By.XPATH, xpath)
                visible_options = [opt for opt in options if opt.is_displayed()]
                if visible_options:
                    return visible_options
            return False

        try:
            return WebDriverWait(self.driver, timeout).until(_find_visible_options)
        except TimeoutException:
            if raise_on_timeout:
                raise
            return []

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
        Waits for match entries to appear and returns the count.

        Returns:
            int: Number of match elements visible.
        """
        elements = self._wait_for_match_entries_elements()
        return len(elements)

    def _extract_url_from_match_index(
        self, index: int
    ) -> tuple[str, bool, str | None, str | None]:
        """
        Resolve one match URL and metadata from the list page.

        Args:
            index (int): The index of the match in the list.

        Returns:
            tuple[str, bool, str | None, str | None]:
                match URL, played flag, home team name, visitor team name.
        """
        entries = self._wait_for_match_entries_elements()

        if index >= len(entries):
            raise IndexError("Match index out of range (DOM might have changed).")

        target_entry = entries[index]
        entry_text = target_entry.text or ""
        is_match_played = _is_played_match(entry_text)
        home_team_name, visitor_team_name = _extract_team_names_from_text(entry_text)

        href = target_entry.get_attribute("href")
        if href and "mpg-match" in href:
            return href, is_match_played, home_team_name, visitor_team_name

        current_list_url = self.driver.current_url

        self._click_score_element(target_entry)

        WebDriverWait(self.driver, 8).until(
            lambda d: "mpg-match" in d.current_url and d.current_url != current_list_url
        )
        match_url = self.driver.current_url
        if home_team_name is None or visitor_team_name is None:
            home_from_title, visitor_from_title = _extract_team_names_from_text(
                self.driver.title or ""
            )
            home_team_name = home_team_name or home_from_title
            visitor_team_name = visitor_team_name or visitor_from_title

        self.driver.back()
        self._wait_for_list_to_reload()

        return match_url, is_match_played, home_team_name, visitor_team_name

    def _wait_for_match_entries_elements(self) -> list:
        """
        Return visible match entry elements.

        It first searches score/`vs` labels and then falls back to direct match links
        to support unplayed matchweeks where score cards may be absent.
        """
        score_xpath = get_button_score_balise()
        link_xpath = get_match_link_balise()

        def _find_visible_entries(driver):
            score_elements = driver.find_elements(By.XPATH, score_xpath)
            visible_scores = [elem for elem in score_elements if elem.is_displayed()]
            if visible_scores:
                return visible_scores

            link_elements = driver.find_elements(By.XPATH, link_xpath)
            visible_links = [elem for elem in link_elements if elem.is_displayed()]
            if visible_links:
                return visible_links

            return False

        return WebDriverWait(self.driver, 12).until(_find_visible_entries)

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
        self._wait_for_match_entries_elements()

    def _extract_match_urls_from_page_source(self) -> list[str]:
        """Extract direct match URLs from current page source as a fallback."""
        html = self.driver.page_source or ""
        found = re.findall(r"/mpg-match/league/[a-zA-Z0-9_/-]+", html)
        if not found:
            return []
        unique_urls: list[str] = []
        seen: set[str] = set()
        for raw_url in found:
            normalized = urljoin("https://mpg.football", raw_url)
            if normalized in seen:
                continue
            seen.add(normalized)
            unique_urls.append(normalized)
        return unique_urls

    def _extract_team_names_from_match_url(
        self, match_url: str
    ) -> tuple[str | None, str | None]:
        """Open one match URL and try to extract home/visitor names."""
        try:
            self.driver.get(match_url)
        except Exception:
            return None, None

        text_candidates = [self.driver.title or ""]
        for xpath in ("//h1", "//h2", "//p"):
            elements = self.driver.find_elements(By.XPATH, xpath)
            text_candidates.extend((elem.text or "") for elem in elements[:6])

        for text in text_candidates:
            home, visitor = _extract_team_names_from_text(text)
            if home and visitor:
                return home, visitor
        return None, None


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
    IS_VS_LABEL = "translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz') = 'vs'"
    SCORE_P_XPATH: str = (
        f"//p[({HAS_DASH_SEPARATOR} and {ONLY_ALLOWED_CHARS}) or {IS_VS_LABEL}]"
    )
    return SCORE_P_XPATH


def _is_played_match(match_text: str) -> bool:
    """
    Returns True when text contains a played score (e.g. "2 - 1").
    """
    return bool(re.search(r"\b\d+\s*-\s*\d+\b", match_text))


def _extract_team_names_from_text(raw_text: str) -> tuple[str | None, str | None]:
    """Extract home and visitor names from a text block containing 'vs' or score."""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if len(lines) < 3:
        return None, None

    marker_index = None
    for idx, line in enumerate(lines):
        if line.casefold() == "vs" or _is_played_match(line):
            marker_index = idx
            break

    if marker_index is None or marker_index == 0 or marker_index >= len(lines) - 1:
        return None, None

    return lines[marker_index - 1], lines[marker_index + 1]


def get_match_link_balise() -> str:
    """Get XPath selecting direct match links from the results page."""
    return "//a[contains(@href, '/mpg-match/')]"


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
