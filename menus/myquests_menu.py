"""Compatibility wrapper for legacy imports.

New code should import from `menus.myquests`.
"""

from menus.myquests import open_myquests_menu

__all__ = ["open_myquests_menu"]
