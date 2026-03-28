"""Shared building blocks used by interactive menu modules."""

from menus.menu_utils.base_views import OwnerBoundView
from menus.menu_utils.confirm_views import ConfirmCancelView

__all__ = ["OwnerBoundView", "ConfirmCancelView"]
