

class MPG():
    def create_game_id(self):
        """
        Create a unique id for each game
        """
        h_team_reduced = self.tab_info["h_team"][:4].strip()
        v_team_reduced = self.tab_info["v_team"][:4].strip()
        return f"{self.league_id}_{self.season_nb}_{self.division}_{h_team_reduced}_{v_team_reduced}"

    def get_team_id(self, home: bool):
        """
        Get unique id for each team
        :param home: Is the team home or visitor ?
        :return: _description_
        """
        if home:
            team = "h_team"
        else:
            team = "v_team"
        return f"{self.league_id}_{self.season_nb}_{self.tab_info[team]}"