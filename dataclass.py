from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from enum import Enum

from utils.ppe_types import DEFAULT_PPE_TYPE

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
    rarity: str = "common"
    first_logged_at: int | None = None
    last_logged_at: int | None = None
    logged_times: List[int] = field(default_factory=list)

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
    ppe_type: str = DEFAULT_PPE_TYPE

@dataclass
class TeamData:
    """Represents a team in the PPE contest."""
    name: str
    leader_id: int  # Discord user ID of the team leader
    members: List[int] = field(default_factory=list)  # Discord user IDs of all members


@dataclass
class QuestData:
    current_items: List[str] = field(default_factory=list)
    current_shinies: List[str] = field(default_factory=list)
    current_skins: List[str] = field(default_factory=list)
    completed_items: List[str] = field(default_factory=list)
    completed_shinies: List[str] = field(default_factory=list)
    completed_skins: List[str] = field(default_factory=list)

@dataclass
class PlayerData:
    ppes: List[PPEData] = field(default_factory=list)
    active_ppe: Optional[int] = None
    is_member: bool = False
    unique_items: Set[tuple] = field(default_factory=set)  # (item_name, shiny)
    season_item_rarities: Dict[str, str] = field(default_factory=dict)  # seasonal item key -> highest rarity seen
    item_log_timestamps: Dict[str, int] = field(default_factory=dict)  # seasonal item key -> unix timestamp
    season_item_history: Dict[str, List[int]] = field(default_factory=dict)  # seasonal item variant key -> sorted unix timestamps
    team_name: Optional[str] = None  # Name of the team this player is on (None if not on a team)
    quests: QuestData = field(default_factory=QuestData)
    quest_resets_remaining: Optional[int] = None
    
    def get_unique_item_count(self) -> int:
        """Get the count of unique items across all PPEs."""
        if isinstance(self.season_item_history, dict) and self.season_item_history:
            unique_base_items: Set[tuple[str, bool]] = set()
            for key in self.season_item_history.keys():
                parts = str(key).split("|")
                if len(parts) < 2:
                    continue
                item_name = parts[0]
                shiny = parts[1] == "1"
                if item_name:
                    unique_base_items.add((item_name, shiny))
            if unique_base_items:
                return len(unique_base_items)
        return len(self.unique_items)

