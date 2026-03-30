"""Compatibility re-exports for /manageplayer team submenu views."""

from menus.manageplayer.submenus.team.views import (
    ManagePlayerAddToTeamView,
    ManagePlayerRemoveFromTeamConfirmView,
    ManagePlayerTeamOverviewView,
)

__all__ = [
    "ManagePlayerAddToTeamView",
    "ManagePlayerRemoveFromTeamConfirmView",
    "ManagePlayerTeamOverviewView",
]
