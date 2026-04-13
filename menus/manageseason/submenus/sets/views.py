"""Set Points submenu views and modals for /manageseason."""

from __future__ import annotations

import discord

from menus.menu_utils import OwnerBoundView
from menus.manageseason.services import load_points_settings_for_menu
from utils.set_operations import load_item_sets


def _build_manage_set_points_embed(settings: dict) -> discord.Embed:
    """Build the main set completion points management embed."""
    embed = discord.Embed(
        title="Manage Set Completion Points",
        description="Configure default points for all sets and manage individual set overrides.",
        color=discord.Color.gold(),
    )

    set_bonuses = settings.get("points_settings", {}).get("set_bonuses", {})
    
    # Get default points for UT and ST
    all_sets = load_item_sets()
    ut_sets = {name: data for name, data in all_sets.items() if data["type"] == "UT"}
    st_sets = {name: data for name, data in all_sets.items() if data["type"] == "ST"}
    
    ut_bonuses = set_bonuses.get("UT", {})
    st_bonuses = set_bonuses.get("ST", {})
    
    # Calculate default points (sets that have the same points are considered "default")
    ut_default_point_counts = {}
    st_default_point_counts = {}
    ut_overrides = []
    st_overrides = []
    
    for set_name in ut_sets.keys():
        points = ut_bonuses.get(set_name, 0.0)
        if points == 0.0:
            ut_default_point_counts[0.0] = ut_default_point_counts.get(0.0, 0) + 1
        else:
            ut_overrides.append((set_name, points))
    
    for set_name in st_sets.keys():
        points = st_bonuses.get(set_name, 0.0)
        if points == 0.0:
            st_default_point_counts[0.0] = st_default_point_counts.get(0.0, 0) + 1
        else:
            st_overrides.append((set_name, points))
    
    # Add default points section
    embed.add_field(
        name="Default Set Points",
        value=(
            f"UT Default: **0 pts** (applies to {len(ut_sets)} sets)\n"
            f"ST Default: **0 pts** (applies to {len(st_sets)} sets)"
        ),
        inline=False,
    )
    
    # Add overrides section if any exist
    if ut_overrides or st_overrides:
        override_lines = []
        for set_name, points in sorted(ut_overrides):
            override_lines.append(f"- {set_name}: **{points}** pts")
        for set_name, points in sorted(st_overrides):
            override_lines.append(f"- {set_name}: **{points}** pts")
        
        if override_lines:
            embed.add_field(
                name=f"Set Overrides ({len(override_lines)})",
                value="\n".join(override_lines) if override_lines else "None",
                inline=False,
            )
    
    embed.set_footer(text="Use buttons below to manage default points or add/edit set overrides.")
    return embed


class ManageSetPointsView(OwnerBoundView):
    """View for managing set completion point values."""

    def __init__(self, *, owner_id: int, settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings

    def current_embed(self) -> discord.Embed:
        return _build_manage_set_points_embed(self.settings)

    @discord.ui.button(label="Manage Set Points", style=discord.ButtonStyle.success, row=0)
    async def manage_set_points(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.sets.modals import ManageDefaultSetPointsModal

        self.settings = await load_points_settings_for_menu(interaction)
        await interaction.response.send_modal(
            ManageDefaultSetPointsModal(
                owner_id=self.owner_id,
                settings=self.settings,
                source_message=interaction.message,
            )
        )

    @discord.ui.button(label="Add Set Override", style=discord.ButtonStyle.success, row=0)
    async def add_set_override(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.sets.modals import AddSetOverrideModal

        self.settings = await load_points_settings_for_menu(interaction)
        await interaction.response.send_modal(
            AddSetOverrideModal(
                owner_id=self.owner_id,
                settings=self.settings,
                source_message=interaction.message,
            )
        )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.points.views import ManagePointSettingsView

        settings = await load_points_settings_for_menu(interaction)
        view = ManagePointSettingsView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


__all__ = ["ManageSetPointsView"]
