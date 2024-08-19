from kestra import Kestra

from config.config_reader import get_config
from sql.ddb_matchweek_not_scrapped import get_matchweeks_not_scrapped
from utils.log import init_logger

init_logger()
config = get_config()

matchweeks_not_scrapped = get_matchweeks_not_scrapped(
    league_id=config["LEAGUE_ID"],
    division=config["DIVISION"],
    season_nb=config["SEASON_NB"],
    nb_players=config["NB_PLAYERS"],
)


outputs = {"matchweeks_not_scrapped": matchweeks_not_scrapped}

Kestra.outputs(outputs)
