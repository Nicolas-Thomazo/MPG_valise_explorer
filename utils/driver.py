import logging
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from utils.selenium import get_url


class Driver:
    chrome_options = Options()
    url = "https://mpg.football/auth/login"

    def __init__(self, docker=True) -> None:
        if docker:
            self.chrome_options.add_argument("--no-sandbox")
            self.chrome_options.add_argument("--headless=new")
            self.chrome_options.add_argument("--disable-dev-shm-usage")
            self.chrome_options.page_load_strategy = "normal"

        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=self.chrome_options,
        )

    def accept_cookies_old(self):
        """_summary_
        Accept cookies to be able to put our logging credentials
        1- Looking for every iframes, as cookies accept button is on an iframe.
        2- Try to click on this button for every iframe.
        3- Raising an error if cookies weren't accepted
        """
        time.sleep(1)
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        accepted = False
        for iframe in iframes:
            try:
                self.driver.switch_to.frame(iframe)
                button_XPATH = "//button[@class='sc-furwcr jhwOCG button button--filled button__acceptAll']"
                WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, button_XPATH))).click()
                accepted = True
                logging.info("BINGO COOKIES ACCEPTED.")
                break
            except:
                logging.info("Cookies not found in this iframe.")
        if not accepted:
            raise NameError("The button to accept cookies was not found.")

    def accept_cookies(self):
        """_summary_
        Accept cookies to be able to put our logging credentials
        1- Try to click on this button for every iframe.
        2- Raising an error if cookies weren't accepted
        """
        accept_button_id = "didomi-notice-agree-button"
        try:
            self.driver.find_element(By.ID, accept_button_id).click()
            logging.info("Bingo, cookies accepted!")
        except:
            raise NameError("Couldn't accept cookies.")

    def logging(self, user, password):
        """
        Logging user.
        1- Getting base URL
        2- Going fullscreen
        3- Accepting cookies
        4- Sending user & password keys
        5- Clicking connect button

        :param user: User mail
        :param password: User password
        """
        get_url(driver=self.driver, url=self.url)
        self.driver.fullscreen_window()

        self.accept_cookies()

        WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.ID, "login"))).send_keys(user)
        WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.ID, "password"))).send_keys(password)

        buttons = self.driver.find_elements(By.TAG_NAME, "button")
        for button in buttons:
            if button.text == "Je me connecte":
                button.click()
