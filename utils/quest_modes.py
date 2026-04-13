"""Quest mode payload and context builders."""

from __future__ import annotations

from dataclass import PlayerData, TeamData


def normalize_team_key(team_name: str | None) -> str:
    if not isinstance(team_name, str):
        return ""
    return team_name.strip().lower()


def ensure_team_quests_state(settings: dict) -> dict[str, dict[str, list[str]]]:
    raw = settings.get("team_quests_state")
    if not isinstance(raw, dict):
        raw = {}
        settings["team_quests_state"] = raw
    return raw


def build_global_quests_payload(settings: dict) -> dict:
    return {
        "enabled": bool(settings.get("use_global_quests", False)),
        "regular": list(settings.get("global_regular_quests", [])),
        "shiny": list(settings.get("global_shiny_quests", [])),
        "skin": list(settings.get("global_skin_quests", [])),
    }


def build_quest_mode_payload(settings: dict) -> dict:
    return {
        "global": build_global_quests_payload(settings),
        "team": {
            "enabled": bool(settings.get("enable_team_quests", False)),
            "state": ensure_team_quests_state(settings),
        },
    }


def resolve_player_team(
    player_data: PlayerData,
    teams: dict[str, TeamData],
) -> tuple[str | None, TeamData | None]:
    team_name = getattr(player_data, "team_name", None)
    if not isinstance(team_name, str) or not team_name.strip():
        return None, None

    normalized_target = normalize_team_key(team_name)
    for candidate_name, team_data in teams.items():
        if normalize_team_key(candidate_name) == normalized_target:
            return candidate_name, team_data
    return None, None


def build_team_quests_context(
    *,
    settings: dict,
    player_data: PlayerData,
    records: dict[int, PlayerData],
    teams: dict[str, TeamData],
) -> dict | None:
    if bool(settings.get("use_global_quests", False)):
        return None
    if not bool(settings.get("enable_team_quests", False)):
        return None

    actual_team_name, team_data = resolve_player_team(player_data, teams)
    if actual_team_name is None or team_data is None:
        return None

    state_map = ensure_team_quests_state(settings)
    key = normalize_team_key(actual_team_name)

    member_records: list[PlayerData] = []
    for member_id in getattr(team_data, "members", []):
        member_data = records.get(int(member_id))
        if member_data is None or not member_data.is_member:
            continue
        member_records.append(member_data)

    if not member_records:
        member_records = [player_data]

    return {
        "enabled": True,
        "team_name": actual_team_name,
        "team_key": key,
        "team_state_map": state_map,
        "member_records": member_records,
    }
