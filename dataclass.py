from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from enum import Enum

ROTMG_CLASSES = [
    "Wizard", "Priest", "Archer", "Rogue", "Warrior", "Knight", "Paladin",
    "Assassin", "Necromancer", "Huntress", "Mystic", "Trickster",
    "Sorcerer", "Ninja", "Samurai", "Bard", "Summoner", "Kensei", "Druid"
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
    DRUID = "Druid"


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
class TeamData:
    """Represents a team in the PPE contest."""
    name: str
    leader_id: int  # Discord user ID of the team leader
    members: List[int] = field(default_factory=list)  # Discord user IDs of all members

@dataclass
class PlayerData:
    ppes: List[PPEData] = field(default_factory=list)
    active_ppe: Optional[int] = None
    is_member: bool = False
    unique_items: Set[tuple] = field(default_factory=set)  # (item_name, shiny)
    team_name: Optional[str] = None  # Name of the team this player is on (None if not on a team)
    
    def get_unique_item_count(self) -> int:
        """Get the count of unique items across all PPEs."""
        return len(self.unique_items)

