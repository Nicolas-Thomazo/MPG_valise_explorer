from pydantic import BaseModel, Field


class MatchweekUrls(BaseModel):
    matchweek: int
    urls: list[str | None] = Field(default_factory=list)
    matches_played: list[bool] = Field(default_factory=list)
    home_team_names: list[str | None] = Field(default_factory=list)
    visitor_team_names: list[str | None] = Field(default_factory=list)


class LeagueMatchUrls(BaseModel):
    league_id: str
    division: int
    season_number: int
    matchweeks: list[MatchweekUrls] = Field(default_factory=list)

    def to_dict(self) -> dict[int, list[str | None]]:
        return {item.matchweek: item.urls for item in self.matchweeks}
