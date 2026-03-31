"""Module to handle the Selenium WebDriver for MPG website automation."""

import logging

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from mpg_explorer import LEAGUE_CONFIG


class Driver:
    chrome_options = Options()
    url = "https://mpg.football/auth/login"

    def __init__(self, docker=True) -> None:
        if docker:
            self.chrome_options.add_argument("--no-sandbox")
            self.chrome_options.add_argument("--headless")
            self.chrome_options.add_argument("--disable-dev-shm-usage")
            self.chrome_options.add_argument("--disable-gpu")
            self.chrome_options.page_load_strategy = "normal"
            self.chrome_options.add_argument("--window-size=1920,1080")
            self.chrome_options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            )

        self.driver = webdriver.Chrome(
            options=self.chrome_options,
        )

    def accept_cookies(self):
        """
        Accept cookies to be able to put our logging credentials
        1- Try to click on this button for every iframe.
        2- Raising an error if cookies weren't accepted
        """
        try:
            accept_button_id = "didomi-notice-agree-button"
            self.driver.find_element(By.ID, accept_button_id).click()
            logging.info("Bingo, cookies accepted!")
        except Exception:
            logging.info("No cookie banner detected, continuing")

    def login_mpg(
        self,
        user: str = LEAGUE_CONFIG.MPG_USERNAME,
        password: str = LEAGUE_CONFIG.MPG_PASSWORD,
    ):
        """
        Log in user.
            1- Getting base URL
            2- Going fullscreen
            3- Accepting cookies
            4- Sending user & password keys
            5- Clicking connect button

        Args:
            user (str): User email
            password (str): User password
        """
        self.driver.get(self.url)

        self.accept_cookies()

        element = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//*[text()='Se connecter']"))
        )
        element.click()

        # Send credentials
        login_input = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.ID, "username"))
        )
        login_input.clear()
        login_input.send_keys(user)

        password_input = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.ID, "password"))
        )
        password_input.clear()
        password_input.send_keys(password)

        # Click on connect button
        element = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//*[text()='Se connecter']"))
        )
        element.click()

        WebDriverWait(self.driver, 20).until(
            lambda d: "auth/login" not in d.current_url
            and not d.find_elements(By.ID, "username")
        )
