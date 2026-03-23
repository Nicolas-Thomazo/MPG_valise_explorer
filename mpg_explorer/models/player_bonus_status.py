from pydantic import BaseModel, Field

from mpg_explorer.models.bonus import BonusName


class PlayerBonusStatus(BaseModel):
    player_name: str
    played: list[BonusName] = Field(default_factory=list)
    remaining: list[BonusName] = Field(default_factory=list)

