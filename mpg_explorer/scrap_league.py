# %%
from mpg_explorer.scrap.league import LeagueScrapper
from mpg_explorer.utils.driver import Driver
from mpg_explorer import logger, LEAGUE_CONFIG

logger.info("Starting scraping process")
# %%
my_driver = Driver(docker=False)
# %%
# Define your credentials
my_driver.login_mpg(
    user=LEAGUE_CONFIG.MPG_USERNAME, password=LEAGUE_CONFIG.MPG_PASSWORD
)
# %%
league = LeagueScrapper(driver=my_driver.driver)

# %%
