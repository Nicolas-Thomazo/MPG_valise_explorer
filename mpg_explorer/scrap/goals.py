"""Goal breakdown extraction helpers for MPG match pages."""

from __future__ import annotations

import json
import re
from typing import Any, Iterator, cast

from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait

from mpg_explorer.scrap.game_info import get_all_bonus, parse_match_header

MPG_GOAL_STROKE = "#45C945"
REAL_GOAL_STROKE = "#696773"
MPG_GOAL_RGB = "69, 201, 69"
REAL_GOAL_RGB = "105, 103, 115"
HOME_GOALS_CLASS = "sc-bcXHqe fNHVxg"
HOME_SCORERS_CLASS = "sc-bcXHqe gnMozL"
AWAY_GOALS_CLASS = "sc-bcXHqe gFNZhX"
AWAY_SCORERS_CLASS = "sc-bcXHqe bIJtk"


def _count_icons_by_side(
    x_positions: list[float], viewport_width: float
) -> tuple[int, int]:
    """
    Count left and right icons based on viewport midpoint.

    Args:
        x_positions: Horizontal icon positions in pixels.
        viewport_width: Browser viewport width in pixels.

    Returns:
        tuple[int, int]: `(home_count, away_count)`.
    """
    if not x_positions:
        return 0, 0

    midpoint = viewport_width / 2
    home_count = sum(1 for x in x_positions if x < midpoint)
    away_count = len(x_positions) - home_count
    return home_count, away_count


def _find_match_summary_container(driver: Chrome) -> WebElement:
    """
    Locate the match summary container around score and goal markers.

    Args:
        driver: Selenium driver on an MPG match page.

    Returns:
        WebElement: Container element used for fallback spatial filtering.

    Raises:
        Exception: If no score element can be located.
    """
    WebDriverWait(driver, 12).until(
        lambda d: len(d.find_elements(By.XPATH, "//p[contains(normalize-space(.), ' - ')]"))
        > 0
    )

    score_candidates = driver.find_elements(
        By.XPATH, "//p[contains(normalize-space(.), ' - ')]"
    )
    score_element: WebElement | None = None
    for candidate in score_candidates:
        text = (candidate.text or "").strip()
        if re.fullmatch(r"\d+\s*-\s*\d+", text):
            score_element = candidate
            break

    if score_element is None:
        raise Exception("Could not locate score element on match page.")

    ancestors = score_element.find_elements(By.XPATH, "ancestor::div")
    for ancestor in ancestors:
        try:
            if float(ancestor.size.get("width", 0)) < 500:
                continue
            if ancestor.find_elements(By.XPATH, ".//svg"):
                return ancestor
        except Exception:
            continue

    return score_element.find_element(By.XPATH, "ancestor::div[1]")


def _extract_score_from_page(driver: Chrome) -> tuple[int, int]:
    """
    Extract home and away score from the page using multiple fallbacks.

    Args:
        driver: Selenium driver on an MPG match page.

    Returns:
        tuple[int, int]: `(home_total_goals, away_total_goals)`.

    Raises:
        Exception: If no score can be extracted.
    """
    score_pattern = re.compile(r"(\d+)\s*-\s*(\d+)")

    body_text = str(driver.execute_script("return document.body.innerText || '';"))
    score_match = score_pattern.search(body_text)
    if score_match is not None:
        return int(score_match.group(1)), int(score_match.group(2))

    score_candidates = driver.find_elements(
        By.XPATH, "//p[contains(normalize-space(.), ' - ')]"
    )
    for candidate in score_candidates:
        candidate_text = (candidate.text or "").strip()
        score_match = score_pattern.fullmatch(candidate_text)
        if score_match is not None:
            return int(score_match.group(1)), int(score_match.group(2))

    all_cards = get_all_bonus(driver, timeout=4)
    if all_cards:
        home_player, away_player = parse_match_header(all_cards[0].text)
        return home_player.score, away_player.score

    raise Exception("Could not extract score from page.")


def _extract_real_goals_from_scorers(driver: Chrome) -> tuple[int, int] | None:
    """
    Count real goals from scorer rows when scorer panels are available.

    Args:
        driver: Selenium driver on an MPG match page.

    Returns:
        tuple[int, int] | None: `(home_real_goals, away_real_goals)` or `None`
        when scorer rows cannot be found.
    """
    home_xpath = (
        "//*[@class='sc-bcXHqe drrRfn'][1]"
        f"//*[@class='{HOME_GOALS_CLASS}']"
        f"//*[@class='{HOME_SCORERS_CLASS}']"
    )
    away_xpath = (
        "//*[@class='sc-bcXHqe drrRfn'][1]"
        f"//*[@class='{AWAY_GOALS_CLASS}']"
        f"//*[@class='{AWAY_SCORERS_CLASS}']"
    )

    try:
        WebDriverWait(driver, 8).until(
            lambda d: (
                len(d.find_elements(By.XPATH, home_xpath))
                + len(d.find_elements(By.XPATH, away_xpath))
            )
            > 0
        )
    except Exception:
        return None

    home_scorers = driver.find_elements(By.XPATH, home_xpath)
    away_scorers = driver.find_elements(By.XPATH, away_xpath)
    home_real = sum(
        len(scorer.find_elements(By.TAG_NAME, "svg")) for scorer in home_scorers
    )
    away_real = sum(
        len(scorer.find_elements(By.TAG_NAME, "svg")) for scorer in away_scorers
    )
    return home_real, away_real


def _walk_json_nodes(payload: Any) -> Iterator[dict[str, Any]]:
    """
    Yield all dictionary nodes from a nested JSON-like payload.

    Args:
        payload: Parsed JSON object (dict/list/scalar).

    Yields:
        dict[str, Any]: Every nested dictionary node.
    """
    if isinstance(payload, dict):
        yield cast(dict[str, Any], payload)
        for value in payload.values():
            yield from _walk_json_nodes(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _walk_json_nodes(item)


def _extract_goal_breakdown_from_next_data(
    driver: Chrome,
) -> tuple[int, int, int, int] | None:
    """
    Extract goal breakdown directly from `__NEXT_DATA__` when available.

    Args:
        driver: Selenium driver on an MPG match page.

    Returns:
        tuple[int, int, int, int] | None:
            `(home_mpg_goals, home_real_goals, away_mpg_goals, away_real_goals)`
            or `None` when fields are unavailable.
    """
    scripts = driver.find_elements(By.XPATH, "//script[@id='__NEXT_DATA__']")
    if not scripts:
        return None

    raw_payload = scripts[0].get_attribute("textContent") or ""
    if not raw_payload.strip():
        return None

    try:
        payload = json.loads(raw_payload)
    except Exception:
        return None

    home_mpg_keys = ["home_mpg_goals", "homempggoals", "homempggoals"]
    home_real_keys = ["home_real_goals", "homerealgoals", "homerealgoalscount"]
    away_mpg_keys = ["away_mpg_goals", "visitormpggoals", "awaympggoals"]
    away_real_keys = ["away_real_goals", "visitorrealgoals", "awayrealgoals"]

    for node in _walk_json_nodes(payload):
        lowered = {str(key).lower().replace("-", "_"): value for key, value in node.items()}

        def _pick(keys: list[str]) -> int | None:
            for key in keys:
                if key in lowered and isinstance(lowered[key], (int, float)):
                    return int(lowered[key])
            return None

        home_mpg = _pick(home_mpg_keys)
        home_real = _pick(home_real_keys)
        away_mpg = _pick(away_mpg_keys)
        away_real = _pick(away_real_keys)
        if None not in (home_mpg, home_real, away_mpg, away_real):
            return cast(
                tuple[int, int, int, int],
                (home_mpg, home_real, away_mpg, away_real),
            )

    return None


def _get_goal_icon_positions_from_dom(
    driver: Chrome, stroke_color: str, rgb_color: str
) -> list[tuple[float, float]]:
    """
    Extract SVG icon center positions matching one target color.

    Args:
        driver: Selenium driver on an MPG match page.
        stroke_color: Target hex color (e.g. `#696773`).
        rgb_color: Target RGB value without wrapper (e.g. `105, 103, 115`).

    Returns:
        list[tuple[float, float]]: Raw icon center positions `(x, y)`.
    """
    return driver.execute_script(
        """
const hex = arguments[0].toLowerCase();
const rgb = arguments[1].toLowerCase();
const nodes = Array.from(
  document.querySelectorAll('svg, path, circle, line, polyline, polygon, rect, g')
);
const seen = new Set();
const icons = [];
for (const node of nodes) {
  const stroke = (node.getAttribute('stroke') || '').toLowerCase();
  const fill = (node.getAttribute('fill') || '').toLowerCase();
  const style = (node.getAttribute('style') || '').toLowerCase();
  const matches =
    stroke === hex ||
    fill === hex ||
    style.includes(`stroke: ${hex}`) ||
    style.includes(`fill: ${hex}`) ||
    style.includes(`stroke: rgb(${rgb})`) ||
    style.includes(`fill: rgb(${rgb})`);
  if (!matches) continue;
  const svg = node.closest('svg') || node;
  if (seen.has(svg)) continue;
  seen.add(svg);
  const rect = svg.getBoundingClientRect();
  icons.push({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
}
return icons;
""",
        stroke_color,
        rgb_color,
    )


def get_goal_breakdown(driver: Chrome) -> tuple[int, int, int, int]:
    """
    Return MPG and real goals for both teams.

    The function tries progressively:
    1) Parse values from `__NEXT_DATA__`.
    2) Parse scorer rows (real goals) then infer MPG goals from score.
    3) Fallback to icon-color heuristics for real goals then infer MPG goals.

    Args:
        driver: Selenium driver on an MPG match page.

    Returns:
        tuple[int, int, int, int]:
            `(home_mpg_goals, home_real_goals, away_mpg_goals, away_real_goals)`.
    """
    next_data_values = _extract_goal_breakdown_from_next_data(driver)
    if next_data_values is not None:
        return next_data_values

    home_total_goals, away_total_goals = _extract_score_from_page(driver)
    real_goals_from_scorers = _extract_real_goals_from_scorers(driver)
    if real_goals_from_scorers is not None:
        home_real_goals, away_real_goals = real_goals_from_scorers
        home_mpg_goals = max(home_total_goals - home_real_goals, 0)
        away_mpg_goals = max(away_total_goals - away_real_goals, 0)
        return home_mpg_goals, home_real_goals, away_mpg_goals, away_real_goals

    summary_card = _find_match_summary_container(driver)
    viewport_width = float(
        driver.execute_script(
            "return window.innerWidth || document.documentElement.clientWidth || 1200;"
        )
    )
    raw_real_positions = _get_goal_icon_positions_from_dom(
        driver=driver,
        stroke_color=REAL_GOAL_STROKE,
        rgb_color=REAL_GOAL_RGB,
    )
    real_positions = [
        (float(item["x"]), float(item["y"]))
        for item in raw_real_positions
        if isinstance(item, dict) and "x" in item and "y" in item
    ]
    total_real_goals = len(real_positions)

    top = float(summary_card.location["y"]) - 120.0
    bottom = top + float(summary_card.size["height"]) + 260.0
    summary_real_x_positions = [x for x, y in real_positions if top <= y <= bottom]
    summary_home_real, summary_away_real = _count_icons_by_side(
        summary_real_x_positions, viewport_width
    )

    if summary_home_real + summary_away_real >= total_real_goals:
        home_real_goals = summary_home_real
        away_real_goals = summary_away_real
    else:
        remainder = total_real_goals - (summary_home_real + summary_away_real)
        home_real_goals = summary_home_real
        away_real_goals = summary_away_real
        home_capacity = max(home_total_goals - home_real_goals, 0)
        away_capacity = max(away_total_goals - away_real_goals, 0)
        if away_capacity >= home_capacity:
            add_away = min(remainder, away_capacity)
            away_real_goals += add_away
            remainder -= add_away
            add_home = min(remainder, home_capacity)
            home_real_goals += add_home
        else:
            add_home = min(remainder, home_capacity)
            home_real_goals += add_home
            remainder -= add_home
            add_away = min(remainder, away_capacity)
            away_real_goals += add_away

    home_mpg_goals = max(home_total_goals - home_real_goals, 0)
    away_mpg_goals = max(away_total_goals - away_real_goals, 0)
    return home_mpg_goals, home_real_goals, away_mpg_goals, away_real_goals
