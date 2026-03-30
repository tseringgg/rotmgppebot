"""Character submenu modals for /myinfo."""

from __future__ import annotations

import discord

from dataclass import PPEData
from menus.myinfo.common import (
    display_class_name,
    find_ppe_or_raise,
    format_points,
    penalty_input_defaults,
    refresh_player_data,
)
from utils.guild_config import load_guild_config
from utils.penalty_embed import build_penalty_infographic_embed
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.points_service import apply_penalties_to_ppe, parse_penalty_inputs, recompute_ppe_points
from slash_commands.newppe_cmd import create_new_ppe_for_user


class ManagePPEPenaltiesModal(discord.ui.Modal, title="Manage PPE Penalties"):
    """Modal form used by the myinfo character view to edit penalty inputs."""

    pet_level = discord.ui.TextInput(label="Pet Level (0-100)", required=True, max_length=3)
    num_exalts = discord.ui.TextInput(label="Exalts (0-40)", required=True, max_length=3)
    percent_loot = discord.ui.TextInput(label="Loot Boost % (0-25)", required=True, max_length=5)
    incombat_reduction = discord.ui.TextInput(
        label="In-Combat Reduction (0/0.2/0.4/0.6/0.8/1.0)",
        placeholder="Enter one of: 0, 0.2, 0.4, 0.6, 0.8, 1.0",
        required=True,
        max_length=3,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        ppe_id: int,
        defaults: dict[str, float],
        source_message: discord.Message | None,
        connected_ppe_ids: set[int],
    ) -> None:
        super().__init__()
        self.owner_id = owner_id
        self.ppe_id = ppe_id
        self.source_message = source_message
        self.connected_ppe_ids = connected_ppe_ids
        self.pet_level.default = str(int(defaults["pet_level"]))
        self.num_exalts.default = str(int(defaults["num_exalts"]))
        self.percent_loot.default = f"{float(defaults['percent_loot']):g}"
        self.incombat_reduction.default = f"{float(defaults['incombat_reduction']):g}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Validate modal values, persist penalties, and refresh the open character panel."""

        parsed_inputs, error = parse_penalty_inputs(
            self.pet_level.value,
            self.num_exalts.value,
            self.percent_loot.value,
            self.incombat_reduction.value,
        )
        if error:
            await interaction.response.send_message(error, ephemeral=False)
            return

        assert parsed_inputs is not None
        pet_level = int(parsed_inputs["pet_level"])
        num_exalts = int(parsed_inputs["num_exalts"])
        percent_loot = float(parsed_inputs["percent_loot"])
        incombat_reduction = float(parsed_inputs["incombat_reduction"])

        # Re-load records at submit time to avoid writing stale menu state.
        records = await load_player_records(interaction)
        key = ensure_player_exists(records, self.owner_id)
        player_data = records[key]
        ppe = find_ppe_or_raise(player_data, self.ppe_id)

        guild_config = await load_guild_config(interaction)

        penalty_result = apply_penalties_to_ppe(
            ppe,
            pet_level=pet_level,
            num_exalts=num_exalts,
            percent_loot=percent_loot,
            incombat_reduction=incombat_reduction,
            guild_config=guild_config,
        )
        points_breakdown = recompute_ppe_points(ppe, guild_config)
        await save_player_records(interaction=interaction, records=records)

        components = penalty_result["components"]
        embed = build_penalty_infographic_embed(
            pet_level=pet_level,
            num_exalts=num_exalts,
            percent_loot=percent_loot,
            incombat_reduction=incombat_reduction,
            pet_penalty=components["Pet Level Penalty"],
            exalt_penalty=components["Exalts Penalty"],
            loot_penalty=components["Loot Boost Penalty"],
            incombat_penalty=components["In-Combat Reduction Penalty"],
            total_points=points_breakdown["total"],
        )

        await interaction.response.send_message(
            f"✅ Updated penalties for PPE #{ppe.id} ({display_class_name(ppe)}). "
            f"New total: **{format_points(points_breakdown['total'])}** points.",
            embed=embed,
            ephemeral=False,
        )

        # Refresh the character panel message so penalty stats and points are immediately visible.
        if self.source_message is not None:
            from menus.myinfo.submenus.character.views import ManageCharactersView

            refreshed = await refresh_player_data(interaction, self.owner_id)
            refreshed_view = ManageCharactersView(
                owner_id=self.owner_id,
                player_data=refreshed,
                connected_ppe_ids=self.connected_ppe_ids,
                preferred_ppe_id=self.ppe_id,
                guild_config=guild_config,
            )
            try:
                await self.source_message.edit(embed=refreshed_view.current_embed(interaction.user), view=refreshed_view)
            except discord.HTTPException:
                pass


class NewPPEFromMyInfoModal(discord.ui.Modal, title="Create New PPE"):
    """Modal that mirrors /newppe inputs directly from the Manage Characters panel."""

    class_name = discord.ui.TextInput(
        label="Class Name",
        placeholder="Example: Wizard",
        required=True,
        max_length=32,
    )
    pet_level = discord.ui.TextInput(label="Pet Level (0-100)", required=True, max_length=3)
    num_exalts = discord.ui.TextInput(label="Exalts (0-40)", required=True, max_length=3)
    percent_loot = discord.ui.TextInput(label="Loot Boost % (0-25)", required=True, max_length=5)
    incombat_reduction = discord.ui.TextInput(
        label="In-Combat Reduction (0/0.2/0.4/0.6/0.8/1.0)",
        placeholder="Enter one of: 0, 0.2, 0.4, 0.6, 0.8, 1.0",
        required=True,
        max_length=3,
    )

    def __init__(self, *, owner_id: int, source_message: discord.Message | None, connected_ppe_ids: set[int]) -> None:
        super().__init__()
        self.owner_id = owner_id
        self.source_message = source_message
        self.connected_ppe_ids = connected_ppe_ids

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        try:
            result = await create_new_ppe_for_user(
                interaction,
                class_name=str(self.class_name.value).strip(),
                pet_level=int(str(self.pet_level.value).strip()),
                num_exalts=int(str(self.num_exalts.value).strip()),
                percent_loot=float(str(self.percent_loot.value).strip()),
                incombat_reduction=float(str(self.incombat_reduction.value).strip()),
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=False)
            return

        await interaction.response.send_message(
            f"✅ Created `PPE #{result['next_id']}` for your `{result['class_name']}` "
            f"and set it as your active PPE.\n"
            f"You now have {result['ppe_count']}/{result['max_ppes']} PPEs.",
            embed=result["embed"],
            ephemeral=False,
        )

        if self.source_message is not None:
            from menus.myinfo.submenus.character.views import ManageCharactersView

            refreshed = await refresh_player_data(interaction, self.owner_id)
            guild_config = await load_guild_config(interaction)
            refreshed_view = ManageCharactersView(
                owner_id=self.owner_id,
                player_data=refreshed,
                connected_ppe_ids=self.connected_ppe_ids,
                preferred_ppe_id=int(result["next_id"]),
                guild_config=guild_config,
            )
            try:
                await self.source_message.edit(embed=refreshed_view.current_embed(interaction.user), view=refreshed_view)
            except discord.HTTPException:
                pass


__all__ = ["ManagePPEPenaltiesModal", "NewPPEFromMyInfoModal"]
