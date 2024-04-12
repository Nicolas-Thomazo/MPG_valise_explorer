import duckdb

from config.config_reader import get_config
from sql.duckdb_bonus import get_remaining_bonus_player
from utils.log import init_logger

init_logger()
config = get_config()

league_id = config["LEAGUE_ID"]
season_nb = config["SEASON_NB"]
team_name = config["TEAM"]
team_id = f"{league_id}_{season_nb}_{team_name}"

remaining_bonus = get_remaining_bonus_player(team_id=team_id, nb_players=config["NB_PLAYERS"])

print(f"Remaining bonuses of {team_name} are:")
for bonus in remaining_bonus:
    print(f"{bonus} : {remaining_bonus[bonus]}")
