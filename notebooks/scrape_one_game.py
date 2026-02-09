# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mpg-explorer",
# ]
#
# [tool.uv.sources]
# mpg-explorer = { path = "../", editable = true }
# ///

# %%
from mpg_explorer import LEAGUE_CONFIG, logger
from mpg_explorer.scrap.game_info import get_match_data
from mpg_explorer.utils.driver import Driver

match_url = "https://mpg.football/mpg-match/league/mpg_division_NKU1UAPG_11_1/mpg_division_match_NKU1UAPG_11_1_6_3_3_2"

logger.info(f"Scrapping data from match url {match_url}")
my_driver = Driver(docker=False)
my_driver.login_mpg(
    user=LEAGUE_CONFIG.MPG_USERNAME, password=LEAGUE_CONFIG.MPG_PASSWORD
)
my_driver.driver.get(match_url)
home_player, outside_player = get_match_data(driver=my_driver.driver)
logger.info(f"Home player: {home_player}, Outside player: {outside_player}")
# %%
