"""Compatibility wrapper for legacy imports.

New code should import from `menus.myinfo`.
"""

from menus.myinfo import open_myinfo_menu

__all__ = ["open_myinfo_menu"]
