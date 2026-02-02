"""End-to-end tests for MPG authentication using Selenium."""

import pytest
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from mpg_explorer import LEAGUE_CONFIG, logger
from mpg_explorer.utils.driver import Driver


@pytest.fixture
def my_driver():
    my_driver = Driver()
    yield my_driver
    my_driver.driver.quit()


@pytest.mark.end2end
def test_mpg_authentication_success(my_driver):
    """
    End-to-end test:
        - open login page
        - authenticate with credentials
        - verify user is logged in
    """

    user = LEAGUE_CONFIG.MPG_USERNAME
    password = LEAGUE_CONFIG.MPG_PASSWORD

    driver = my_driver.driver
    logger.info(f"Navigating to MPG login page: {my_driver.url}")
    try:
        my_driver.login_mpg(user=user, password=password)

        # --- 1. Assert redirect to dashboard ---
        WebDriverWait(driver, 15).until(
            lambda d: d.current_url == "https://mpg.football/dashboard"
        )

        assert driver.current_url == "https://mpg.football/dashboard"

        # --- 2. Assert login form is gone ---
        with pytest.raises(TimeoutException):
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
    finally:
        driver.quit()
