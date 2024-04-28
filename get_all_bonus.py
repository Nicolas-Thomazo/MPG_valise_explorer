from kestra import Kestra

from config.config_reader import get_config
from sql.ddb_bonus import get_all_players_bonus
from utils.log import init_logger

init_logger()
config = get_config()

league_id = config["LEAGUE_ID"]
season_nb = config["SEASON_NB"]
team_name = config["TEAM"]
team_id = f"{league_id}_{season_nb}_{team_name}"

all_bonus_text = get_all_players_bonus(league_id=league_id, season_nb=config["SEASON_NB"], nb_players=config["NB_PLAYERS"])

outputs = {"all_bonus_text": all_bonus_text}

Kestra.outputs(outputs)
