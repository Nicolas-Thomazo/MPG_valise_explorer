from pydantic import BaseModel, Field


class MatchweekUrls(BaseModel):
    matchweek: int
    urls: list[str] = Field(default_factory=list)


class LeagueMatchUrls(BaseModel):
    league_id: str
    division: int
    season_number: int
    matchweeks: list[MatchweekUrls] = Field(default_factory=list)

    def to_dict(self) -> dict[int, list[str]]:
        return {item.matchweek: item.urls for item in self.matchweeks}

