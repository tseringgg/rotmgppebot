"""Compatibility exports for RealmShark sniffer core modules.

Canonical implementations now live in:
- menus.menu_utils.sniffer_core.panel_services
- menus.menu_utils.sniffer_core.mapping_actions
- menus.menu_utils.sniffer_core.panel_views
- menus.menu_utils.sniffer_core.admin_panel
"""

from menus.menu_utils.sniffer_core.admin_panel import RealmSharkAdminPanelView, admin_panel
from menus.menu_utils.sniffer_core.mapping_actions import admin_view, bindings, configure, reset_all
from menus.menu_utils.sniffer_core.panel_services import (
    generate_link_token,
    set_announce_channel,
    set_enabled,
    status,
    unlink_token,
)
from menus.menu_utils.sniffer_core.panel_views import (
    RealmSharkConfigurePanelView,
    RealmSharkMapToPPEView,
    open_panel,
    render_panel_embed,
)

__all__ = [
    "RealmSharkAdminPanelView",
    "RealmSharkConfigurePanelView",
    "RealmSharkMapToPPEView",
    "admin_panel",
    "admin_view",
    "bindings",
    "configure",
    "generate_link_token",
    "open_panel",
    "render_panel_embed",
    "reset_all",
    "set_announce_channel",
    "set_enabled",
    "status",
    "unlink_token",
]
