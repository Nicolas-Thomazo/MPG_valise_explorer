# %%
from mpg_explorer.scrap.league import LeagueScrapper
from mpg_explorer.utils.driver import Driver
from mpg_explorer import logger, LEAGUE_CONFIG
from mpg_explorer.scrap.game import Game

logger.info("Starting scraping process")
# %%
my_driver = Driver(docker=False)
# %%
# Define your credentials
my_driver.login_mpg(
    user=LEAGUE_CONFIG.MPG_USERNAME, password=LEAGUE_CONFIG.MPG_PASSWORD
)
# %%
matchweeks = [1]
league = LeagueScrapper(driver=my_driver.driver)
list_matchs_urls = league.scrap_league(matchweeks=matchweeks)

# %%
# scrap match
game = Game(driver=my_driver.driver, game_url=list_matchs_urls[0], matchweek=1)

# %%