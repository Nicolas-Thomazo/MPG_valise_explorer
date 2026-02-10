from enum import Enum


class BonusName(Enum):
    zahia: str = "Zahia"
    mcdo: str = "McDo+"
    valise: str = "Valise à Nanard"
    suarez: str = "Suarez"
    miroir: str = "Miroir"
    cheat_code: str = "Cheat Code 18-26"
    tonton_pat: str = "Tonton Pat'"
    decathlon: str = "Decathlon"
    four_defense: str = "4 défenseurs"
    five_defense: str = "5 défenseurs"
    capitaine: str = "Capitaine"


def get_bonus_name(potential_bonus: str) -> BonusName | None:
    for bonus in BonusName:
        if potential_bonus == bonus.value:
            return BonusName[bonus.name]
    return None
