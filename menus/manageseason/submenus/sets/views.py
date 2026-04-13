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

    # `settings` is already the points_settings payload.
    set_overrides = settings.get("set_overrides", {}) if isinstance(settings.get("set_overrides", {}), dict) else {}
    default_ut_points = float(settings.get("default_ut_points", 0.0))
    default_st_points = float(settings.get("default_st_points", 0.0))

    
    # Get default points for UT and ST
    all_sets = load_item_sets()
    ut_sets = {name: data for name, data in all_sets.items() if data["type"] == "UT"}
    st_sets = {name: data for name, data in all_sets.items() if data["type"] == "ST"}
    
    ut_overrides_map = set_overrides.get("UT", {}) if isinstance(set_overrides.get("UT", {}), dict) else {}
    st_overrides_map = set_overrides.get("ST", {}) if isinstance(set_overrides.get("ST", {}), dict) else {}
    
    ut_overrides = []
    st_overrides = []
    
    for set_name in ut_sets.keys():
        if set_name in ut_overrides_map:
            points = float(ut_overrides_map.get(set_name, default_ut_points))
            ut_overrides.append((set_name, points))
    
    for set_name in st_sets.keys():
        if set_name in st_overrides_map:
            points = float(st_overrides_map.get(set_name, default_st_points))
            st_overrides.append((set_name, points))
    
    # Add default points section
    embed.add_field(
        name="Default Set Points",
        value=(
            f"UT Default: **{default_ut_points:.1f} pts** (applies to {len(ut_sets)} sets)\n"
            f"ST Default: **{default_st_points:.1f} pts** (applies to {len(st_sets)} sets)"
        ),
        inline=False,
    )
    
    # Add overrides section if any exist
    if ut_overrides or st_overrides:
        override_lines = []
        for set_name, points in sorted(ut_overrides):
            override_lines.append(f"- {set_name}: **{points:g}** pts (Manually Overriden)")
        for set_name, points in sorted(st_overrides):
            override_lines.append(f"- {set_name}: **{points:g}** pts (Manually Overriden)")
        
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

    @discord.ui.button(label="Remove Set Override", style=discord.ButtonStyle.danger, row=0)
    async def remove_set_override(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.sets.modals import RemoveSetOverrideModal

        self.settings = await load_points_settings_for_menu(interaction)
        await interaction.response.send_modal(
            RemoveSetOverrideModal(
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
