"""Compatibility exports for /managesniffer views.

Canonical implementations live in `menus.managesniffer.submenus.*`.
"""

from menus.managesniffer.submenus.danger_confirm.views import SnifferDangerConfirmView
from menus.managesniffer.submenus.home.views import ManageSnifferHomeView, render_managesniffer_home, send_managesniffer_home
from menus.managesniffer.submenus.output_channel.views import ManageSnifferOutputChannelView, render_output_channel_view
from menus.managesniffer.submenus.player_manage.views import ManagePlayerSnifferView, render_manage_player_sniffer_home
from menus.managesniffer.submenus.tokens.views import ManageSnifferTokensView, TokenDeletePickerView

__all__ = [
    "ManagePlayerSnifferView",
    "ManageSnifferHomeView",
    "ManageSnifferOutputChannelView",
    "ManageSnifferTokensView",
    "SnifferDangerConfirmView",
    "TokenDeletePickerView",
    "render_manage_player_sniffer_home",
    "render_managesniffer_home",
    "render_output_channel_view",
    "send_managesniffer_home",
]
