import polars as pl

from config.config_reader import get_config
from scrap.league import League
from utils.azure import AzureUtils
from utils.driver import Driver
from utils.log import init_logger

init_logger()
config = get_config()
Driver = Driver(docker=config["IS_DOCKER"])

# Define your credentials
user = config["MAIL"]
password = config["PASSWORD"]
Driver.logging(user, password)


league = League(
    driver=Driver.driver,
    league_id=config["LEAGUE_ID"],
    results_link=config["RESULTS_LINK"],
    season_nb=config["SEASON_NB"],
    division=config["DIVISION"],
    nb_players=config["NB_PLAYERS"],
    matchweeks=[config["MATCHWEEK"]],
)
