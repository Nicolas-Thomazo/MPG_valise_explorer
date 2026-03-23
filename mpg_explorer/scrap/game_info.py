"""Scraping and parsing functions for match info and bonuses from MPG game page."""

from selenium.webdriver.support.ui import WebDriverWait

import re
from typing import Optional
from selenium.webdriver.support import expected_conditions as EC

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, Field
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from mpg_explorer.models.bonus import BonusName, get_bonus_name
from mpg_explorer import logger


class PlayerResult(BaseModel):
    is_home_team: bool
    name: str
    score: int
    list_bonus: list[BonusName] = Field(default_factory=list)


BONUS_PATH = "//div[button[.//img] and div/p]"
NO_BONUS_PATH = "//*[normalize-space(text())='Pas de bonus pour cette journée']"

############################
#### Parsing functions #####
############################


def parse_match_header(header_text: str) -> tuple[PlayerResult, PlayerResult]:
    """
    Parses the match summary text to extract team names and the final score.

    Args:
        header_text: The raw text from the match summary card.

    Returns:
        A MatchResult object containing team_home, team_away, and score.
    """
    lines = [line.strip() for line in header_text.split("\n") if line.strip()]

    # We use a regex to find the score pattern "0 - 2"
    score_pattern = re.compile(r"\d+\s*-\s*\d+")
    score_match = score_pattern.search(header_text)
    if score_match:
        score = score_match.group(0)
        score_parts = score.split("-")
        team_home_score = int(score_parts[0].strip())
        team_away_score = int(score_parts[1].strip())
    else:
        team_home_score = 0
        team_away_score = 0
        logger.error("Score not found in header text, defaulting to '0 - 0'.")

    team_home = lines[0]
    if len(lines) > 6:
        team_away = lines[6]
    else:
        logger.error("Team names not found in expected positions.")
        team_away = "Unknown"

    home_player = PlayerResult(is_home_team=True, name=team_home, score=team_home_score)
    outside_player = PlayerResult(
        is_home_team=False, name=team_away, score=team_away_score
    )
    return (home_player, outside_player)


def extract_bonus_details(card: WebElement) -> BonusName:
    """
    Extracts bonus name from a bonus card WebElement.

    Args:
        card: The WebElement representing the bonus card.

    Returns:
        A dictionary with bonus details.
    """
    # The bonus is the first line of the card text
    text_bonus = card.text.split("\n")[0]
    bonus_strip = text_bonus.strip()
    bonus: BonusName | None = get_bonus_name(bonus_strip)
    if bonus is None:
        raise Exception(
            f"Found bonus name {bonus_strip}, which is not an instance of {BonusName}"
        )
    return bonus


#############################
#### Scraping functions #####
#############################


def get_all_bonus(driver: Chrome, timeout: int = 10) -> list[WebElement]:
    """
    Retrieves all bonus card WebElements from the page with explicit wait.
    """
    try:
        # Attendre que au moins 1 élément soit présent
        WebDriverWait(driver, timeout).until(
            EC.presence_of_all_elements_located((By.XPATH, BONUS_PATH))
        )
        all_cards = driver.find_elements(By.XPATH, BONUS_PATH)
        return all_cards
    except Exception as e:
        logger.error(f"Timeout waiting for bonus cards: {e}")
        return []


def check_if_no_bonus(driver: Chrome, timeout: int = 5) -> list[WebElement]:
    """
    Retrieves all bonus card WebElements from the page with explicit wait.
    """
    try:
        results: list[WebElement] = driver.find_elements(By.XPATH, NO_BONUS_PATH)
        return results
    except Exception as e:
        logger.error(f"Timeout waiting for no bonus cards: {e}")
        return []


def find_parent_x(card: WebElement) -> float:
    """
    Finds the x-coordinate of the parent element of a given WebElement.

    Args:
        card (WebElement): The WebElement for which to find the parent's x-coordinate.

    Returns:
        float: The x-coordinate of the parent element.
    """
    try:
        parent_x = card.find_element(By.XPATH, "..").location["x"]
    except Exception as e:
        msg = f"Failed to find parent x-coordinate for card {card}: {e}"
        logger.warning(msg)
        raise Exception(msg)
    return parent_x


def _get_no_bonus_label_x(driver: Chrome) -> Optional[float]:
    """Checks if the 'No bonus' label is present and returns its X position."""
    elements = check_if_no_bonus(driver)
    if elements:
        return float(elements[0].location["x"])
    return None


def _extract_bonuses_with_positions(
    cards: list[WebElement],
) -> tuple[list[BonusName], list[float]]:
    """
    Iterates through cards to extract text details and their horizontal positions.

    Args:
        cards: List of WebElement representing bonus cards.

    Returns:
        A tuple containing:
            - A list of bonus detail strings.
            - A list of corresponding x-coordinates.
    """
    bonus_details: list[BonusName] = []
    x_coords: list[float] = []

    for card in cards:
        try:
            x_pos = find_parent_x(card)
            details: BonusName = extract_bonus_details(card)

            bonus_details.append(details)
            x_coords.append(x_pos)
            logger.debug(f"Found bonus: {details.name} at x={x_pos}")
        except Exception as e:
            logger.warning(f"Failed to process a bonus card: {e}")

    return bonus_details, x_coords


##########################
#### Logic functions #####
##########################


def find_index_split_bonuses(position_array: NDArray) -> np.integer:
    """
    Find the index to split bonuses between two teams based on position array.

    Args:
        position_array (NDArray): Array of x-coordinates of bonus cards.

    Returns:
        np.integer: The index of the last bonus card for the first team.
    """
    diff_position = np.diff(position_array)
    index_split = np.argmax(diff_position)
    return index_split


def _assign_by_no_bonus_label(
    home: PlayerResult,
    away: PlayerResult,
    bonuses: list[BonusName],
    x_coords: list[float],
    no_bonus_x: float,
) -> tuple[PlayerResult, PlayerResult]:
    """Assigns all bonuses to one team if the 'No Bonus' label is detected for the other."""
    if not x_coords:
        return home, away

    # If the 'No bonus' label is to the right of all existing bonuses
    if no_bonus_x > max(x_coords):
        logger.info(f"No bonuses detected for away team: {away.name}")
        home.list_bonus = bonuses
        away.list_bonus = []
    # If the 'No bonus' label is to the left of all existing bonuses
    elif no_bonus_x < min(x_coords):
        logger.info(f"No bonuses detected for home team: {home.name}")
        home.list_bonus = []
        away.list_bonus = bonuses
    return home, away


def _assign_by_splitting(
    home: PlayerResult,
    away: PlayerResult,
    bonuses: list[BonusName],
    x_coords: list[float],
) -> tuple[PlayerResult, PlayerResult]:
    """Splits the bonus list in two based on the largest gap in X coordinates."""
    if not x_coords:
        return home, away

    split_index = find_index_split_bonuses(np.array(x_coords))
    logger.debug(
        f"Splitting bonuses at index {split_index} for {home.name}/{away.name}"
    )

    # Standard slicing: home gets up to split_index, away gets the rest
    home.list_bonus = bonuses[: split_index + 1]
    away.list_bonus = bonuses[split_index + 1 :]
    return home, away


###############
#### Main #####
###############


def get_match_data(driver: Chrome) -> tuple[PlayerResult, PlayerResult]:
    """
    Orchestrates the scraping of match information and player bonuses.
    Uses horizontal positioning (X-axis) to attribute bonuses to the correct team.

    Args:
        driver: The Chrome WebDriver instance.

    Returns:
        A tuple containing PlayerResult for home and away players.
    """
    logger.info("Starting match data extraction...")

    # 1. Data Collection
    all_cards = get_all_bonus(driver)
    if not all_cards:
        msg = "No bonus cards found. Page structure might have changed."
        logger.error(msg)
        raise Exception(msg)

    # 2. Header Parsing (First card)
    home_player, away_player = parse_match_header(all_cards[0].text)
    logger.info(
        f"Match: {home_player.name} vs {away_player.name} | Score: {home_player.score}-{away_player.score}"
    )

    # 3. Bonus & Position Extraction (Remaining cards)
    bonus_list, x_coords = _extract_bonuses_with_positions(all_cards[1:])

    # 4. Attribution Logic
    no_bonus_x = _get_no_bonus_label_x(driver)

    if no_bonus_x is not None:
        # Case A: One team has explicitly "No bonus"
        home_player, away_player = _assign_by_no_bonus_label(
            home_player, away_player, bonus_list, x_coords, no_bonus_x
        )
    else:
        # Case B: Both teams might have bonuses, split the list based on X gap
        home_player, away_player = _assign_by_splitting(
            home_player, away_player, bonus_list, x_coords
        )
    return home_player, away_player
