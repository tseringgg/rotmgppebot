from dataclasses import dataclass, field
from typing import Dict, List, Optional

from enum import Enum

ROTMG_CLASSES = [
    "Wizard", "Priest", "Archer", "Rogue", "Warrior", "Knight", "Paladin",
    "Assassin", "Necromancer", "Huntress", "Mystic", "Trickster",
    "Sorcerer", "Ninja", "Samurai", "Bard", "Summoner", "Kensei"
]

class ROTMGClass(str, Enum):
    WIZARD = "Wizard"
    PRIEST = "Priest"
    ARCHER = "Archer"
    ROGUE = "Rogue"
    WARRIOR = "Warrior"
    KNIGHT = "Knight"
    PALADIN = "Paladin"
    ASSASSIN = "Assassin"
    NECROMANCER = "Necromancer"
    HUNTRESS = "Huntress"
    MYSTIC = "Mystic"
    TRICKSTER = "Trickster"
    SORCERER = "Sorcerer"
    NINJA = "Ninja"
    SAMURAI = "Samurai"
    BARD = "Bard"
    SUMMONER = "Summoner"
    KENSEI = "Kensei"


@dataclass
class Loot:
    item_name: str
    quantity: int
    divine: bool = False
    shiny: bool = False

@dataclass
class Bonus:
    name: str
    points: float
    repeatable: bool
    quantity: int = 1

@dataclass
class PPEData:
    id: int
    name: ROTMGClass
    points: float = 0.0
    loot: List[Loot] = field(default_factory=list)
    bonuses: List[Bonus] = field(default_factory=list)
@dataclass
class PlayerData:
    ppes: List[PPEData] = field(default_factory=list)
    active_ppe: Optional[int] = None
    is_member: bool = False

