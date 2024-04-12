import polars as pl

from scrap.mpg import MPG
from utils.azure import AzureUtils

pl.Config(tbl_cols=22)
from selenium.webdriver.common.by import By

from utils.selenium import get_url


class Game(MPG):
    # Tab info
    tab_info_class = "sc-bcXHqe euGzhE"
    tab_info_class = "sc-bcXHqe sc-dmctIk gmwvWu jMJMOc"  ### Permet d'avoir toutes les infos dans le panneau (dont le numéro de la journée et les buteurs)
    h_goals_class = "sc-bcXHqe fNHVxg"
    h_scorers_class = "sc-bcXHqe gnMozL"
    v_goals_class = "sc-bcXHqe gFNZhX"
    v_scorers_class = "sc-bcXHqe bIJtk"

    # Bonus
    h_bonus_class = "sc-bcXHqe fhMvyb"
    v_bonus_class = "sc-bcXHqe jSNkIw"
    all_bonus_list = [
        "valise",
        "ubereats",
        "suarez",
        "zahia",
        "miroir",
        "chapron",
        "tonton",
        "decat",
        "5défenseurs",
        "4défenseurs",
        "capitaine",
        "4decat",
    ]

    export_game_path = "exports/games.parquet"
    export_bonus_path = "exports/bonus.parquet"

    def get_players_info_df(self, scores_tab_element):
        """
        Receiving the game scores tab element, this function retrieves all players informations displayed there as a pd df.
        1- 'team_goals_element' is either the full element for home team, either the full element for away team
        2- We get each 'scorer' in the 'team_goals_element' = one element by scorer (one scorer can have multiple goals)
        3- For each of scorer, we get both "p" elements:
            As of 10/02/2024, there are two elements, one looks always empty but might be kept for particularly long names
            We read them both and join them.
            JUST FOUND OUT : it's the minutes of the goals, in case it's a real game and not mpg game
        4- We count the number of 'svg' elemnts = number of things displayed close to his names
        TODO: Find a way to classify those elements (real goals, mpg goals, goals saved etc.), in an other function ?
            For that, I recommend using 'print(scorer.get_attribute("innerHTML"))' and checking in an other window
            to understund each differences.

        Infos are saved as a list of dicts with one element per players in the scores tab element, structured as :
        {name:,nb_goals:,team:}
        Then, returned in a pandas dataframe

        Notes : not working for real games because of the "Dernières confrontation" at the end of the page. We retrieved both tabs
        both goal scorers etc. I didn't find a way to catch only the first tab easily, but should be doable

        :param scores_tab_element: Scores tab selenium element
        """
        players_info = []
        for team in ["home", "visitor"]:
            if team == "home":
                goals_class = self.h_goals_class
                scorers_class = self.h_scorers_class
            else:
                goals_class = self.v_goals_class
                scorers_class = self.v_scorers_class

            for scorer in scores_tab_element.find_elements(
                By.XPATH, f"//*[@class='sc-bcXHqe drrRfn'][1]//*[@class='{goals_class}']//*[@class='{scorers_class}']"
            ):
                scorer_infos = {}
                scorer_infos["name"] = scorer.find_elements(By.TAG_NAME, "p")[1].text
                scorer_infos["real_goals"] = len(scorer.find_elements(By.TAG_NAME, "svg"))
                scorer_infos["team"] = team
                players_info.append(scorer_infos)

        df_players_info = pl.DataFrame(players_info, schema=["name", "real_goals", "mpg_goals", "own_goals", "team"])
        # Fill null, might be a better way to do that
        df_players_info = df_players_info.with_columns(pl.col("real_goals", "mpg_goals", "own_goals").fill_null(0))
        return df_players_info.filter(pl.col("team") == "home"), df_players_info.filter(pl.col("team") == "visitor")

    def get_score_tab_info(self):
        """
        Taking all infos in the score table of a game
        1- Finding the tab element by class
        2- Taking all "p" tag elements
        3- Returning a dictionnary with all informations
        """
        tableau_scores = self.driver.find_element(By.XPATH, f"//*[@class='{self.tab_info_class}']")
        df_h_players_info, df_v_players_info = self.get_players_info_df(tableau_scores)

        tab_info = {}
        teams = tableau_scores.find_elements(By.XPATH, f"//*[@class='sc-dkrFOg sc-hbqYmb gappF ePpVLH']")
        tab_info["h_team"] = teams[0].text.replace(" ", "_")
        tab_info["v_team"] = teams[1].text.replace(" ", "_")

        players = tableau_scores.find_elements(By.XPATH, f"//*[@class='sc-dkrFOg dciwac']")
        tab_info["h_player"] = players[0].text.replace(" ", "_")
        tab_info["v_player"] = players[3].text.replace(" ", "_")

        score = tableau_scores.find_element(By.XPATH, f"//*[@class='sc-dkrFOg sc-jTjUTQ dfVVDa ibfwxi']").text
        tab_info["h_score"] = int(score.split(" ")[0])
        tab_info["v_score"] = int(score.split(" ")[2])

        tab_info["h_real_goals"] = df_h_players_info.select(pl.sum("real_goals"))[0, 0]
        tab_info["v_real_goals"] = df_v_players_info.select(pl.sum("real_goals"))[0, 0]

        tab_info["h_mpg_goals"] = df_h_players_info.select(pl.sum("mpg_goals"))[0, 0]
        tab_info["v_mpg_goals"] = df_v_players_info.select(pl.sum("mpg_goals"))[0, 0]

        tab_info["h_own_goals"] = df_h_players_info.select(pl.sum("own_goals"))[0, 0]
        tab_info["v_own_goals"] = df_v_players_info.select(pl.sum("own_goals"))[0, 0]

        return tab_info

    def extract_bonus_from_class(self, bonus_class: str, bonus_dict: dict, home: bool):
        """
        Extracting all tag from a given class and incrementing the dictionnary if this bonus is known
        If bonus is unknown, raising an error.

        Returns bonus dictionnary updated with team bonuses.

        :param bonus_class: Lowest bonus class level => Giving the name of the bonus directly
        :param bonus_class: Dictionary to update if bonuses are found
        :param home: Is the team home or visitor ?
        """
        if home:
            prefix = "h_"
        else:
            prefix = "v_"

        all_bonus = self.driver.find_elements(By.XPATH, f"//*[@class='{bonus_class}']")
        for bonus in all_bonus:
            bonus_name = bonus.find_element(By.TAG_NAME, "p").text.lower().replace(" ", "")
            bonus_name = bonus_name.replace("chapronrouge", "chapron")
            bonus_name = bonus_name.replace("lavaliseànanard", "valise")
            bonus_name = bonus_name.replace("4-decat'", "4decat")
            print(self.all_bonus_list)
            if bonus_name in self.all_bonus_list:
                bonus_dict[f"{prefix}{bonus_name}"] += 1
            else:
                raise ValueError(f"Found an unknown bonus name : {bonus_name}")
        return bonus_dict

    def get_bonus_info(self):
        """
        The bonus section has the same class as the "Replacements" and "Badges obtained" modules.
        The aim is to retrieve these three elements, then select the second, which should be the bonuses.

        1- Create a default dict with all bonuses for both teams set to 0
        2- Add all bonus for the 'home' team
        3- Add all bonus for the 'visitor' team
        """
        bonus_dict = {}
        for t in ["h", "v"]:
            for bonus in self.all_bonus_list:
                bonus_dict[f"{t}_{bonus.replace(' ', '')}"] = 0

        bonus_dict = self.extract_bonus_from_class(bonus_class=self.h_bonus_class, bonus_dict=bonus_dict, home=True)
        bonus_dict = self.extract_bonus_from_class(bonus_class=self.v_bonus_class, bonus_dict=bonus_dict, home=False)
        return bonus_dict

    def db_game_insert(self):
        """
        Saving game informations in file.
        Reading the existing file and appending the current game information.
        If the file doesn't exist, creating it.
        """
        df = pl.DataFrame(
            {
                "match_id": self.game_id,
                "league_id": self.league_id,
                "division": self.division,
                "season_nb": self.season_nb,
                "h_teamid": self.h_team_id,
                "v_teamid": self.v_team_id,
                "h_total_goals": self.h_total_goals,
                "h_mpg_goals": self.h_mpg_goals,
                "h_real_goals": self.h_real_goals,
                "h_own_goals": self.h_own_goals,
                "h_red_cards": self.h_red_cards,
                "v_total_goals": self.v_total_goals,
                "v_mpg_goals": self.v_mpg_goals,
                "v_real_goals": self.v_real_goals,
                "v_own_goals": self.v_own_goals,
                "v_red_cards": self.v_red_cards,
                "matchweek": self.matchweek,
            }
        )
        try:
            historical_df = pl.read_parquet(self.AzureUtils.read_file(self.export_game_path))
            df = historical_df.vstack(df)
        except TypeError:
            print("No history file found.")
        self.AzureUtils.write_file(data=df, path=self.export_game_path)
        print(f"Games file now has a lenght of {df.select(pl.count())[0,0]} rows.")

    def db_bonus_insert(self):
        """
        Saving bonus informations in file.
        Reading the existing file and appending the current game information.
        If the file doesn't exist, creating it.
        """
        df = pl.DataFrame(
            {
                "match_id": self.game_id,
                "h_valise": self.bonus["h_valise"],
                "h_ubereats": self.bonus["h_ubereats"],
                "h_suarez": self.bonus["h_suarez"],
                "h_zahia": self.bonus["h_zahia"],
                "h_miroir": self.bonus["h_miroir"],
                "h_chapron": self.bonus["h_chapron"],
                "h_tonton": self.bonus["h_tonton"],
                "h_decat": self.bonus["h_decat"],
                "h_5défenseurs": self.bonus["h_5défenseurs"],
                "h_4défenseurs": self.bonus["h_4défenseurs"],
                "v_valise": self.bonus["v_valise"],
                "v_ubereats": self.bonus["v_ubereats"],
                "v_suarez": self.bonus["v_suarez"],
                "v_zahia": self.bonus["v_zahia"],
                "v_miroir": self.bonus["v_miroir"],
                "v_chapron": self.bonus["v_chapron"],
                "v_tonton": self.bonus["v_tonton"],
                "v_decat": self.bonus["v_decat"],
                "v_5défenseurs": self.bonus["v_5défenseurs"],
                "v_4défenseurs": self.bonus["v_4défenseurs"],
            }
        )
        try:
            historical_df = pl.read_parquet(self.AzureUtils.read_file(self.export_bonus_path))
            df = historical_df.vstack(df)
        except TypeError:
            print("No history file found.")
        self.AzureUtils.write_file(data=df, path=self.export_bonus_path)
        print(f"Bonus file now has a lenght of {df.select(pl.count())[0,0]} rows.")

    def __init__(
        self,
        driver,
        league_id: str,
        season_nb: int,
        division: int,
        matchweek: int,
        game_link: str,
    ):
        """

        TODO: Add a check on game id, if game is already in base, stop processing.

        :param driver: Selenium driver
        :param league_id: MPG league unique ID (eg: 'KWGFGJUM')
        :param season_nb: Season number
        :param division: Division
        :param matchweek: How many matches has it been th
        is season?
        :param game_link: mpg full link
        """
        self.driver = driver
        self.game_link = game_link
        self.league_id = league_id
        self.season_nb = season_nb
        self.division = division
        self.matchweek = matchweek
        self.AzureUtils = AzureUtils()

        get_url(driver=self.driver, url=game_link)

        self.tab_info = self.get_score_tab_info()

        self.game_id = self.create_game_id()
        self.h_team_id = self.get_team_id(home=True)
        self.v_team_id = self.get_team_id(home=False)
        self.h_total_goals = self.tab_info["h_mpg_goals"] + self.tab_info["h_real_goals"]
        self.h_mpg_goals = self.tab_info["h_mpg_goals"]
        self.h_real_goals = self.tab_info["h_real_goals"]
        self.h_own_goals = 0
        self.h_red_cards = 0
        self.v_total_goals = self.tab_info["v_mpg_goals"] + self.tab_info["v_real_goals"]
        self.v_mpg_goals = self.tab_info["v_mpg_goals"]
        self.v_real_goals = self.tab_info["v_real_goals"]
        self.v_own_goals = 0
        self.v_red_cards = 0
        self.db_game_insert()

        self.bonus = self.get_bonus_info()
        self.db_bonus_insert()
