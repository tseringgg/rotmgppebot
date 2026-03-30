"""Views for picture suggestions submenu under /manageseason."""

from __future__ import annotations

import discord

from menus.manageseason.submenus.picture_suggestions.common import (
    build_disable_picture_suggestions_confirm_embed,
    build_picture_suggestions_manage_embed,
    build_picture_suggestions_off_embed,
    build_remove_channels_confirm_embed,
)
from menus.manageseason.submenus.picture_suggestions.modals import (
    AddItemSuggestionsChannelsModal,
    RemoveItemSuggestionsChannelsModal,
)
from menus.manageseason.submenus.picture_suggestions.services import (
    disable_picture_suggestions,
    enable_picture_suggestions,
    load_picture_suggestions_state,
)
from menus.menu_utils import OwnerBoundView


async def build_picture_suggestions_panel(
    *,
    guild: discord.Guild | None,
    owner_id: int,
) -> tuple[discord.Embed, OwnerBoundView]:
    """Build the current panel payload for picture suggestions."""
    state = await load_picture_suggestions_state(guild=guild)
    enabled = bool(state["enabled"])

    if not enabled:
        view = PictureSuggestionsOffView(owner_id=owner_id)
        return view.current_embed(), view

    view = PictureSuggestionsManageView(
        owner_id=owner_id,
        enabled_channel_ids=state["enabled_channel_ids"],
        missing_channel_ids=state["missing_channel_ids"],
        non_text_channel_ids=state["non_text_channel_ids"],
    )
    return view.current_embed(guild), view


class PictureSuggestionsOffView(OwnerBoundView):
    """Pre-enable picture suggestions menu."""

    def __init__(self, *, owner_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id

    def current_embed(self) -> discord.Embed:
        return build_picture_suggestions_off_embed()

    @discord.ui.button(label="Turn Item Suggestions On", style=discord.ButtonStyle.success, row=0)
    async def turn_on(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await enable_picture_suggestions(guild=interaction.guild)
        from menus.manageseason.submenus.picture_suggestions.entry import open_picture_suggestions_menu

        await open_picture_suggestions_menu(interaction, owner_id=self.owner_id)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=0)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.home.views import ManageSeasonHomeView

        home_view = ManageSeasonHomeView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=home_view.current_embed(), view=home_view)


class PictureSuggestionsManageView(OwnerBoundView):
    """Enabled-state picture suggestions menu."""

    def __init__(
        self,
        *,
        owner_id: int,
        enabled_channel_ids: list[int],
        missing_channel_ids: list[int],
        non_text_channel_ids: list[int],
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.enabled_channel_ids = enabled_channel_ids
        self.missing_channel_ids = missing_channel_ids
        self.non_text_channel_ids = non_text_channel_ids

        if not self.enabled_channel_ids:
            self.remove_channels.disabled = True

    def current_embed(self, guild: discord.Guild | None) -> discord.Embed:
        return build_picture_suggestions_manage_embed(
            guild=guild,
            enabled_channel_ids=self.enabled_channel_ids,
            missing_channel_ids=self.missing_channel_ids,
            non_text_channel_ids=self.non_text_channel_ids,
        )

    @discord.ui.button(label="Add Channels", style=discord.ButtonStyle.success, row=0)
    async def add_channels(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(
            AddItemSuggestionsChannelsModal(owner_id=self.owner_id, source_message=interaction.message)
        )

    @discord.ui.button(label="Remove Channels", style=discord.ButtonStyle.danger, row=0)
    async def remove_channels(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        view = PictureSuggestionsRemoveChannelsConfirmView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Disable Item Suggestions", style=discord.ButtonStyle.danger, row=0)
    async def disable_item_suggestions(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        view = PictureSuggestionsDisableConfirmView(
            owner_id=self.owner_id,
            enabled_channel_count=len(self.enabled_channel_ids),
        )
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.home.views import ManageSeasonHomeView

        home_view = ManageSeasonHomeView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=home_view.current_embed(), view=home_view)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, row=1)
    async def close(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed /manageseason menu.", embed=None, view=None)


class PictureSuggestionsRemoveChannelsConfirmView(OwnerBoundView):
    """Confirmation screen before opening remove-channels modal."""

    def __init__(self, *, owner_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=300, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id

    def current_embed(self) -> discord.Embed:
        return build_remove_channels_confirm_embed()

    @discord.ui.button(label="Continue", style=discord.ButtonStyle.danger, row=0)
    async def continue_to_modal(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(
            RemoveItemSuggestionsChannelsModal(owner_id=self.owner_id, source_message=interaction.message)
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=0)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.picture_suggestions.entry import open_picture_suggestions_menu

        await open_picture_suggestions_menu(interaction, owner_id=self.owner_id)


class PictureSuggestionsDisableConfirmView(OwnerBoundView):
    """Confirmation screen for disable-all action."""

    def __init__(self, *, owner_id: int, enabled_channel_count: int) -> None:
        super().__init__(owner_id=owner_id, timeout=300, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.enabled_channel_count = enabled_channel_count

    def current_embed(self) -> discord.Embed:
        return build_disable_picture_suggestions_confirm_embed(
            enabled_channel_count=self.enabled_channel_count,
        )

    @discord.ui.button(label="Disable And Clear Channels", style=discord.ButtonStyle.danger, row=0)
    async def confirm_disable(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await disable_picture_suggestions(guild=interaction.guild)

        from menus.manageseason.submenus.picture_suggestions.entry import open_picture_suggestions_menu

        await open_picture_suggestions_menu(interaction, owner_id=self.owner_id)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=0)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.picture_suggestions.entry import open_picture_suggestions_menu

        await open_picture_suggestions_menu(interaction, owner_id=self.owner_id)


__all__ = [
    "PictureSuggestionsOffView",
    "PictureSuggestionsManageView",
    "PictureSuggestionsRemoveChannelsConfirmView",
    "PictureSuggestionsDisableConfirmView",
    "build_picture_suggestions_panel",
]
