from __future__ import annotations

import re

import discord

from dataclass import TeamData

TEAM_LIST_PAGE_SIZE = 12


def resolve_team_name(teams: dict[str, TeamData], requested_name: str) -> str | None:
    for team_name in teams:
        if team_name.lower() == requested_name.lower():
            return team_name
    return None


def display_name(guild: discord.Guild, user_id: int) -> str:
    member = guild.get_member(user_id)
    if member is None:
        return f"Unknown User ({user_id})"
    return member.display_name


def parse_id_token(raw_value: str) -> int | None:
    token = str(raw_value).strip()
    if not token:
        return None

    mention_match = re.fullmatch(r"<@!?(\d+)>", token)
    if mention_match:
        return int(mention_match.group(1))

    if token.isdigit():
        return int(token)
    return None


def resolve_single_name_query(
    candidates: list[tuple[int, str]],
    query: str,
    *,
    context_label: str,
) -> tuple[int | None, str | None]:
    token = str(query).strip()
    if not token:
        return None, f"❌ Please provide a {context_label} name, mention, or user ID."

    parsed_id = parse_id_token(token)
    if parsed_id is not None:
        for candidate_id, _candidate_name in candidates:
            if candidate_id == parsed_id:
                return candidate_id, None
        return None, f"❌ No {context_label} matched that user ID."

    lowered = token.lower()
    exact_matches = [entry for entry in candidates if entry[1].lower() == lowered]
    if len(exact_matches) == 1:
        return exact_matches[0][0], None
    if len(exact_matches) > 1:
        names = ", ".join(name for _id, name in exact_matches[:5])
        return None, f"❌ Multiple exact matches found: {names}. Please use a mention or user ID."

    startswith_matches = [entry for entry in candidates if entry[1].lower().startswith(lowered)]
    if len(startswith_matches) == 1:
        return startswith_matches[0][0], None

    contains_matches = [entry for entry in candidates if lowered in entry[1].lower()]
    if len(contains_matches) == 1:
        return contains_matches[0][0], None

    matches = startswith_matches or contains_matches
    if matches:
        preview = ", ".join(name for _id, name in matches[:8])
        return None, f"❌ Multiple matches found. Be more specific: {preview}"

    return None, f"❌ No {context_label} matched '{token}'."


def resolve_team_name_query(team_names: list[str], query: str) -> tuple[str | None, str | None]:
    token = str(query).strip()
    if not token:
        return None, "❌ Team name cannot be empty."

    lowered = token.lower()
    exact = [name for name in team_names if name.lower() == lowered]
    if len(exact) == 1:
        return exact[0], None
    if len(exact) > 1:
        return None, "❌ Multiple teams have the same exact name. Please use a more specific query."

    startswith = [name for name in team_names if name.lower().startswith(lowered)]
    if len(startswith) == 1:
        return startswith[0], None

    contains = [name for name in team_names if lowered in name.lower()]
    if len(contains) == 1:
        return contains[0], None

    matches = startswith or contains
    if matches:
        return None, f"❌ Multiple team matches found: {', '.join(matches[:8])}. Please refine your input."

    return None, f"❌ No team matched '{token}'."
