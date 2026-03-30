"""Typed payload models for /managesniffer flows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SnifferTokenRow:
    token: str
    user_id: int | None
    created_at: str
    last_used_at: str

    @classmethod
    def from_link(cls, token: str, link_data: dict[str, Any]) -> "SnifferTokenRow":
        raw_user_id = link_data.get("user_id")
        user_id: int | None = None
        try:
            if raw_user_id is not None:
                user_id = int(raw_user_id)
        except (TypeError, ValueError):
            user_id = None

        return cls(
            token=token,
            user_id=user_id,
            created_at=str(link_data.get("created_at", "")),
            last_used_at=str(link_data.get("last_used_at", "")),
        )


__all__ = ["SnifferTokenRow"]
