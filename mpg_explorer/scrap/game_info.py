"""Scraping and parsing functions for match info and bonuses from MPG game page."""

from selenium.webdriver.support.ui import WebDriverWait

import re
from typing import Optional
from selenium.webdriver.support import expected_conditions as EC

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from mpg_explorer import logger


class PlayerResult(BaseModel):
    is_home_team: bool
    name: str
    score: int
    list_bonus: list[str] = []


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


def extract_bonus_details(card: WebElement) -> str:
    """
    Extracts bonus name from a bonus card WebElement.

    Args:
        card: The WebElement representing the bonus card.

    Returns:
        A dictionary with bonus details.
    """
    # The bonus is the first line of the card text
    text_bonus = card.text.split("\n")[0]
    return text_bonus.strip()


#############################
#### Scraping functions #####
#############################


def get_all_bonus(driver: Chrome, timeout: int = 5) -> list[WebElement]:
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


def get_match_data(driver: Chrome) -> tuple[PlayerResult, PlayerResult]:
    """
    Main orchestrator to scrape match info and bonuses using location strategy.

    Returns:
        A tuple of PlayerResult objects (home_player, outside_player) or None if failed.
    """
    logger.info("Starting match data extraction...")
    all_cards: list[WebElement] = get_all_bonus(driver)
    no_bonus_selector = check_if_no_bonus(driver)
    if no_bonus_selector:
        position_no_bonus = no_bonus_selector[0].location["x"]

    if not all_cards:
        msg = "No html found with the actuel selector, maybe the page structure has changed. Cannot proceed to extract match data."
        logger.error(msg)
        raise Exception(msg)

    # 1. Process Header (The first card contains match info)
    header_card = all_cards[0]
    home_player, outside_player = parse_match_header(header_card.text)
    logger.info(
        f"Match: {home_player.name} vs {outside_player.name} | Score: {home_player.score} - {outside_player.score}"
    )

    # 3. Process Bonus Cards (Skipping the first card which is the header)
    bonus_cards = all_cards[1:]
    list_bonuses: list[str] = []
    list_positions_bonuses: list[float] = []
    for card in bonus_cards:
        try:
            parent_x = find_parent_x(card)
            bonus_text = extract_bonus_details(card)
            list_bonuses.append(bonus_text)
            list_positions_bonuses.append(parent_x)
            logger.info(f"Found bonus {bonus_text}")
        except Exception as e:
            logger.warning(f"Failed to process a bonus card: {e}")

    if no_bonus_selector:
        if position_no_bonus > max(list_positions_bonuses):
            logger.info(f"No bonuses for outside team {outside_player.name}")
            home_player.list_bonus = list_bonuses
        elif position_no_bonus < min(list_positions_bonuses):
            logger.info(f"No bonuses for home team {home_player.name}")
            outside_player.list_bonus = list_bonuses
    else:
        index_split = find_index_split_bonuses(np.array(list_positions_bonuses))
        logger.debug(
            f"Index to split bonuses between teams: {index_split}, bonuses found: {list_bonuses}"
        )
        home_player.list_bonus = list_bonuses[:index_split]
        outside_player.list_bonus = list_bonuses[index_split + 1 :]

    return (home_player, outside_player)
