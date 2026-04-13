"""Modals for managing set point bonuses."""

from __future__ import annotations

import discord

from utils.guild_config import load_guild_config, save_guild_config
from menus.manageseason.services import load_points_settings_for_menu
from utils.set_operations import load_item_sets
from menus.menu_utils import ConfirmCancelView


class EditSetPointsModal(discord.ui.Modal, title="Edit Set Completion Points"):
    """Modal for editing set point values for a specific set type."""

    sets_input = discord.ui.TextInput(
        label="Set Point Values (one per line: SetName=points)",
        placeholder="Example:\nGolden Archer Set=50\nPriest of Geb Set=75",
        style=discord.TextStyle.paragraph,
        required=False,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        settings: dict,
        set_type: str,
        source_message: discord.Message | None,
    ) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message
        self.set_type = set_type.upper()

        # Build default text showing current values
        set_bonuses = settings.get("points_settings", {}).get("set_bonuses", {}).get(self.set_type, {})
        all_sets = load_item_sets()
        sets_of_type = {name: data for name, data in all_sets.items() if data["type"] == self.set_type}

        default_lines = []
        for set_name in sorted(sets_of_type.keys()):
            points = set_bonuses.get(set_name, 0.0)
            default_lines.append(f"{set_name}={points}")

        self.sets_input.default = "\n".join(default_lines) if default_lines else ""

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        # Parse input
        input_text = self.sets_input.value.strip()
        parsed_bonuses: dict[str, float] = {}

        if input_text:
            for line in input_text.split("\n"):
                line = line.strip()
                if not line:
                    continue

                if "=" not in line:
                    await interaction.response.send_message(
                        f"ERROR: Invalid format: `{line}`. Use `SetName=points`.",
                        ephemeral=True,
                    )
                    return

                parts = line.split("=", 1)
                if len(parts) != 2:
                    await interaction.response.send_message(
                        f"ERROR: Invalid format: `{line}`. Use `SetName=points`.",
                        ephemeral=True,
                    )
                    return

                set_name = parts[0].strip()
                points_str = parts[1].strip()

                # Validate set name exists
                all_sets = load_item_sets()
                if set_name not in all_sets or all_sets[set_name]["type"] != self.set_type:
                    await interaction.response.send_message(
                        f"ERROR: `{set_name}` is not a valid {self.set_type} set name.",
                        ephemeral=True,
                    )
                    return

                # Parse points
                try:
                    points = float(points_str)
                    if points < 0:
                        await interaction.response.send_message(
                            f"ERROR: Points must be non-negative. Got: `{points}`.",
                            ephemeral=True,
                        )
                        return
                    parsed_bonuses[set_name] = points
                except ValueError:
                    await interaction.response.send_message(
                        f"ERROR: `{points_str}` is not a valid number.",
                        ephemeral=True,
                    )
                    return

        # Confirmation
        if parsed_bonuses:
            changes_text = "\n".join(f"  {name}: {points} points" for name, points in sorted(parsed_bonuses.items()))
            confirm_text = (
                f"⚠️ **Apply {self.set_type} set completion point changes?**\n\n"
                f"Changes:\n{changes_text}"
            )
        else:
            confirm_text = (
                f"⚠️ **Clear all {self.set_type} set completion point values to 0?**\n\n"
                "This will reset all bonuses for this set type."
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
            await interaction.followup.send("Set completion point update cancelled.", ephemeral=True)
            return

        # Save changes
        guild_config = await load_guild_config(interaction)
        guild_config["points_settings"]["set_bonuses"][self.set_type] = parsed_bonuses
        await save_guild_config(interaction, guild_config)

        # Notify user
        if parsed_bonuses:
            changes_text = "\n".join(f"  {name}: {points} points" for name, points in sorted(parsed_bonuses.items()))
            await interaction.followup.send(
                f"✅ Updated {self.set_type} set completion points:\n{changes_text}",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"✅ Cleared all {self.set_type} set completion points.",
                ephemeral=True,
            )

        # Refresh the source message if available
        if self.source_message:
            from menus.manageseason.submenus.sets.views import ManageSetTypePointsView

            settings = await load_guild_config(interaction)
            view = ManageSetTypePointsView(owner_id=self.owner_id, settings=settings, set_type=self.set_type)
            try:
                await self.source_message.edit(embed=view.current_embed(), view=view)
            except discord.HTTPException:
                pass


__all__ = ["EditSetPointsModal"]
