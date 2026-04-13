"""Set Points submenu views and modals for /manageseason."""

from __future__ import annotations

import discord

from menus.menu_utils import OwnerBoundView
from menus.manageseason.services import load_points_settings_for_menu
from utils.set_operations import load_item_sets


def _build_set_points_embed(set_type: str, settings: dict) -> discord.Embed:
    """Build an embed showing current set point settings for a given type."""
    embed = discord.Embed(
        title=f"Set Completion Points - {set_type} Sets",
        description=f"Configure points awarded for completing {set_type} item sets.",
        color=discord.Color.gold(),
    )

    set_bonuses = settings.get("points_settings", {}).get("set_bonuses", {}).get(set_type, {})
    all_sets = load_item_sets()

    # Filter sets by type
    sets_of_type = {name: data for name, data in all_sets.items() if data["type"] == set_type}

    if not sets_of_type:
        embed.add_field(name="No sets found", value=f"No {set_type} sets found in the item sets database.", inline=False)
        return embed

    # Show all sets with their current point values
    for set_name in sorted(sets_of_type.keys()):
        points = set_bonuses.get(set_name, 0.0)
        embed.add_field(name=set_name, value=f"**{points}** points", inline=False)

    return embed


class ManageSetPointsView(OwnerBoundView):
    """View for managing set completion point values."""

    def __init__(self, *, owner_id: int, settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings

    def current_embed(self) -> discord.Embed:
        return discord.Embed(
            title="Manage Set Completion Points",
            description="Choose a set type to manage point values for completed sets.",
            color=discord.Color.gold(),
        )

    @discord.ui.button(label="Manage ST Set Points", style=discord.ButtonStyle.success, row=0)
    async def manage_st_sets(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_points_settings_for_menu(interaction)
        view = ManageSetTypePointsView(owner_id=self.owner_id, settings=self.settings, set_type="ST")
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Manage UT Set Points", style=discord.ButtonStyle.success, row=0)
    async def manage_ut_sets(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_points_settings_for_menu(interaction)
        view = ManageSetTypePointsView(owner_id=self.owner_id, settings=self.settings, set_type="UT")
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.points.views import ManagePointSettingsView

        settings = await load_points_settings_for_menu(interaction)
        view = ManagePointSettingsView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class ManageSetTypePointsView(OwnerBoundView):
    """View for managing points for a specific set type (ST or UT)."""

    def __init__(self, *, owner_id: int, settings: dict, set_type: str) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings
        self.set_type = set_type.upper()

    def current_embed(self) -> discord.Embed:
        return _build_set_points_embed(self.set_type, self.settings)

    @discord.ui.button(label="Edit Set Points", style=discord.ButtonStyle.success, row=0)
    async def edit_set_points(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.sets.modals import EditSetPointsModal

        self.settings = await load_points_settings_for_menu(interaction)
        await interaction.response.send_modal(
            EditSetPointsModal(
                owner_id=self.owner_id,
                settings=self.settings,
                set_type=self.set_type,
                source_message=interaction.message,
            )
        )

    @discord.ui.button(label="Reset to Zero", style=discord.ButtonStyle.danger, row=0)
    async def reset_to_zero(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from utils.guild_config import load_guild_config, save_guild_config

        if not interaction.guild:
            await interaction.response.send_message("ERROR: Could not access guild settings.", ephemeral=True)
            return

        guild_config = await load_guild_config(interaction)
        guild_config["points_settings"]["set_bonuses"][self.set_type] = {}
        await save_guild_config(interaction, guild_config)

        self.settings = await load_points_settings_for_menu(interaction)
        await interaction.response.edit_message(embed=self.current_embed(), view=self)
        await interaction.followup.send(
            f"✅ All {self.set_type} set bonuses have been reset to 0 points.",
            ephemeral=True,
        )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_points_settings_for_menu(interaction)
        view = ManageSetPointsView(owner_id=self.owner_id, settings=self.settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


__all__ = ["ManageSetPointsView", "ManageSetTypePointsView"]
