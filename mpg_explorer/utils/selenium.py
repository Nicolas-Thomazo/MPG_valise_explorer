import time


def get_url(driver, url, wait_time=2):
    driver.implicitly_wait(wait_time)
    time.sleep(0.5)
    driver.get(url)
    driver.implicitly_wait(wait_time)
    time.sleep(1)
    driver.fullscreen_window()
