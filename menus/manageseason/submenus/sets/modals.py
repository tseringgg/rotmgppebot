"""Modals for managing set point bonuses."""

from __future__ import annotations

import discord

from utils.guild_config import load_guild_config, save_guild_config
from menus.manageseason.services import load_points_settings_for_menu
from utils.set_operations import load_item_sets
from menus.menu_utils import ConfirmCancelView


class ManageDefaultSetPointsModal(discord.ui.Modal, title="Manage Default Set Points"):
    """Modal for setting default points for UT and ST sets."""

    ut_default = discord.ui.TextInput(
        label="Default UT Set Points",
        placeholder="Enter default points for all UT sets (e.g., 0, 25, 50)",
        default="0",
        required=True,
        max_length=10,
    )
    
    st_default = discord.ui.TextInput(
        label="Default ST Set Points",
        placeholder="Enter default points for all ST sets (e.g., 0, 25, 50)",
        default="0",
        required=True,
        max_length=10,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        settings: dict,
        source_message: discord.Message | None,
    ) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        # Parse UT default
        try:
            ut_default_points = float(self.ut_default.value)
            if ut_default_points < 0:
                await interaction.response.send_message(
                    f"ERROR: UT default points must be non-negative. Got: `{ut_default_points}`.",
                    ephemeral=True,
                )
                return
        except ValueError:
            await interaction.response.send_message(
                f"ERROR: `{self.ut_default.value}` is not a valid number.",
                ephemeral=True,
            )
            return

        # Parse ST default
        try:
            st_default_points = float(self.st_default.value)
            if st_default_points < 0:
                await interaction.response.send_message(
                    f"ERROR: ST default points must be non-negative. Got: `{st_default_points}`.",
                    ephemeral=True,
                )
                return
        except ValueError:
            await interaction.response.send_message(
                f"ERROR: `{self.st_default.value}` is not a valid number.",
                ephemeral=True,
            )
            return

        # Confirmation
        confirm_text = (
            f"⚠️ **Apply default set point changes?**\n\n"
            f"UT Sets Default: **{ut_default_points}** pts\n"
            f"ST Sets Default: **{st_default_points}** pts\n\n"
            "Note: Individual set overrides will NOT be affected."
        )

        confirm_view = ConfirmCancelView(
            owner_id=self.owner_id,
            timeout=60,
            confirm_label="Apply Changes",
            cancel_label="Cancel",
            confirm_style=discord.ButtonStyle.danger,
            cancel_style=discord.ButtonStyle.secondary,
            owner_error="This confirmation belongs to another user.",
        )

        await interaction.response.send_message(confirm_text, view=confirm_view, ephemeral=True)
        await confirm_view.wait()

        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass

        if not confirm_view.confirmed:
            await interaction.followup.send("Default set points update cancelled.", ephemeral=True)
            return

        # Save changes - apply defaults to all sets that don't have overrides
        guild_config = await load_guild_config(interaction)
        all_sets = load_item_sets()
        
        # Get current overrides
        set_bonuses = guild_config["points_settings"].get("set_bonuses", {"UT": {}, "ST": {}})
        ut_overrides = {}
        st_overrides = {}
        
        # Preserve existing overrides, apply defaults to all others
        for set_name, data in all_sets.items():
            set_type = data["type"]
            if set_type == "UT":
                # Keep overrides, apply default to others
                if set_name in set_bonuses.get("UT", {}):
                    ut_overrides[set_name] = set_bonuses["UT"][set_name]
                else:
                    ut_overrides[set_name] = ut_default_points
            else:  # ST
                if set_name in set_bonuses.get("ST", {}):
                    st_overrides[set_name] = set_bonuses["ST"][set_name]
                else:
                    st_overrides[set_name] = st_default_points
        
        guild_config["points_settings"]["set_bonuses"] = {"UT": ut_overrides, "ST": st_overrides}
        await save_guild_config(interaction, guild_config)

        await interaction.followup.send(
            f"✅ Default set points updated:\n"
            f"  UT: **{ut_default_points}** pts\n"
            f"  ST: **{st_default_points}** pts",
            ephemeral=True,
        )

        if self.source_message:
            try:
                from menus.manageseason.submenus.sets.views import ManageSetPointsView
                settings = await load_points_settings_for_menu(interaction)
                view = ManageSetPointsView(owner_id=self.owner_id, settings=settings)
                await self.source_message.edit(embed=view.current_embed(), view=view)
            except Exception:
                pass


class AddSetOverrideModal(discord.ui.Modal, title="Add Set Override"):
    """Modal for adding a specific set override."""

    set_name = discord.ui.TextInput(
        label="Set Name",
        placeholder="Example: Golden Archer Set",
        required=True,
        max_length=100,
    )
    
    points = discord.ui.TextInput(
        label="Points for this Set",
        placeholder="Enter points (e.g., 0, 25, 50, 100)",
        required=True,
        max_length=10,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        settings: dict,
        source_message: discord.Message | None,
    ) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        set_name_input = self.set_name.value.strip()
        
        # Validate set name exists
        all_sets = load_item_sets()
        if set_name_input not in all_sets:
            await interaction.response.send_message(
                f"ERROR: `{set_name_input}` is not a valid set name.",
                ephemeral=True,
            )
            return

        set_type = all_sets[set_name_input]["type"]

        # Parse points
        try:
            points_value = float(self.points.value)
            if points_value < 0:
                await interaction.response.send_message(
                    f"ERROR: Points must be non-negative. Got: `{points_value}`.",
                    ephemeral=True,
                )
                return
        except ValueError:
            await interaction.response.send_message(
                f"ERROR: `{self.points.value}` is not a valid number.",
                ephemeral=True,
            )
            return

        # Confirmation
        confirm_text = (
            f"⚠️ **Add set override?**\n\n"
            f"Set: **{set_name_input}** ({set_type})\n"
            f"Points: **{points_value}**"
        )

        confirm_view = ConfirmCancelView(
            owner_id=self.owner_id,
            timeout=60,
            confirm_label="Add Override",
            cancel_label="Cancel",
            confirm_style=discord.ButtonStyle.success,
            cancel_style=discord.ButtonStyle.secondary,
            owner_error="This confirmation belongs to another user.",
        )

        await interaction.response.send_message(confirm_text, view=confirm_view, ephemeral=True)
        await confirm_view.wait()

        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass

        if not confirm_view.confirmed:
            await interaction.followup.send("Set override cancelled.", ephemeral=True)
            return

        # Save changes
        guild_config = await load_guild_config(interaction)
        if "set_bonuses" not in guild_config["points_settings"]:
            guild_config["points_settings"]["set_bonuses"] = {"UT": {}, "ST": {}}
        
        guild_config["points_settings"]["set_bonuses"][set_type][set_name_input] = points_value
        await save_guild_config(interaction, guild_config)

        await interaction.followup.send(
            f"✅ Set override added:\n"
            f"  **{set_name_input}** ({set_type}): **{points_value}** pts",
            ephemeral=True,
        )

        if self.source_message:
            try:
                from menus.manageseason.submenus.sets.views import ManageSetPointsView
                settings = await load_points_settings_for_menu(interaction)
                view = ManageSetPointsView(owner_id=self.owner_id, settings=settings)
                await self.source_message.edit(embed=view.current_embed(), view=view)
            except Exception:
                pass


__all__ = ["ManageDefaultSetPointsModal", "AddSetOverrideModal"]
