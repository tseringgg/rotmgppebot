"""Reusable interactive menu entrypoints for slash commands and views."""

from menus.leaderboard import open_leaderboard_menu
from menus.manageplayer import open_manageplayer_menu
from menus.managequests import open_managequests_menu
from menus.manageseason import open_manageseason_menu
from menus.managesniffer import open_managesniffer_menu
from menus.manageteams import open_manage_teams_menu
from menus.myinfo import open_myinfo_menu
from menus.myquests import open_myquests_menu
from menus.mysniffer import open_mysniffer_menu

__all__ = [
	"open_leaderboard_menu",
	"open_manageplayer_menu",
	"open_managequests_menu",
	"open_manageseason_menu",
	"open_managesniffer_menu",
	"open_manage_teams_menu",
	"open_myinfo_menu",
	"open_myquests_menu",
	"open_mysniffer_menu",
]
