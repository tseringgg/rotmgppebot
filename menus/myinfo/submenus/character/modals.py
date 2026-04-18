"""Character submenu modals for /myinfo."""

from __future__ import annotations

import traceback
from uuid import uuid4

import discord

from dataclass import PPEData
from menus.myinfo.common import display_class_name, find_ppe_or_raise, format_points, penalty_input_defaults, refresh_player_data
from utils.group_ppes import set_duo_partner
from utils.ppe_types import (
    DEFAULT_PPE_TYPE,
    infer_legacy_ppe_type_from_options,
    normalize_allowed_ppe_types,
    normalize_ppe_type_options,
    ppe_type_label,
)
from utils.guild_config import load_guild_config
from utils.penalty_embed import build_penalty_infographic_embed
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.points_service import apply_penalties_to_ppe, loot_adjustment_detail_lines, parse_penalty_inputs, recompute_ppe_points
from slash_commands.newppe_cmd import create_new_ppe_for_user, send_duo_handshake_invite


def _log_legacy_duo_debug(message: str) -> None:
    print(f"[MYINFO_DUO] {message}")


def _log_legacy_duo_exception(message: str) -> None:
    print(f"[MYINFO_DUO][ERROR] {message}")
    print(traceback.format_exc())


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
            guild_config=guild_config,
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
            all_player_records = await load_player_records(interaction)
            refreshed_view = ManageCharactersView(
                owner_id=self.owner_id,
                player_data=refreshed,
                connected_ppe_ids=self.connected_ppe_ids,
                all_player_records=all_player_records,
                preferred_ppe_id=self.ppe_id,
                guild_config=guild_config,
            )
            try:
                await self.source_message.edit(embed=refreshed_view.current_embed(interaction.user, interaction.guild), view=refreshed_view)
            except discord.HTTPException:
                pass


def _matching_partner_duo_ppe(
    *,
    partner_ppes: list[PPEData],
    owner_user_id: int,
    expected_link_id: str | None,
) -> PPEData | None:
    fallback: PPEData | None = None
    for candidate in partner_ppes:
        candidate_options = normalize_ppe_type_options(
            getattr(candidate, "ppe_type_options", None),
            current_type=getattr(candidate, "ppe_type", None),
        )
        if not bool(candidate_options.get("duo_enabled", False)):
            continue
        if int(candidate_options.get("duo_partner_id") or 0) != int(owner_user_id):
            continue

        if fallback is None:
            fallback = candidate

        candidate_link_id = str(candidate_options.get("duo_link_id") or "").strip() or None
        if expected_link_id is not None and candidate_link_id == expected_link_id:
            return candidate

    return fallback


class ManageCharacterDuoPartnerModal(discord.ui.Modal, title="Set Duo Partner Discord ID"):
    partner_id = discord.ui.TextInput(
        label="Discord User ID",
        placeholder="Example: 123456789012345678",
        required=True,
        max_length=24,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        ppe_id: int,
        class_name: str,
        source_message: discord.Message | None = None,
        connected_ppe_ids: set[int] | None = None,
    ) -> None:
        super().__init__(timeout=180)
        self.owner_id = int(owner_id)
        self.ppe_id = int(ppe_id)
        self.class_name = str(class_name)
        self.source_message = source_message
        self.connected_ppe_ids = connected_ppe_ids or set()

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            _log_legacy_duo_debug(
                f"submit owner_id={self.owner_id} ppe_id={self.ppe_id} guild_id={getattr(interaction.guild, 'id', None)} channel_id={getattr(interaction.channel, 'id', None)}"
            )

            if interaction.user.id != self.owner_id:
                await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
                return
            if interaction.guild is None:
                await interaction.response.send_message("This action can only be used in a server.", ephemeral=True)
                return

            partner_text = str(self.partner_id.value or "").strip()
            _log_legacy_duo_debug(f"raw partner_text={partner_text!r}")
            if not partner_text.isdigit() or int(partner_text) <= 0:
                await interaction.response.send_message("Please enter a valid numeric Discord ID.", ephemeral=True)
                return

            partner_user_id = int(partner_text)
            if partner_user_id == self.owner_id:
                await interaction.response.send_message("You cannot set yourself as your duo partner.", ephemeral=True)
                return

            if interaction.guild.get_member(partner_user_id) is None:
                await interaction.response.send_message(f"❌ User <@{partner_user_id}> is not in this server.", ephemeral=True)
                return

            records = await load_player_records(interaction)
            key = ensure_player_exists(records, self.owner_id)
            player_data = records[key]
            ppe = find_ppe_or_raise(player_data, self.ppe_id)
            current_options = normalize_ppe_type_options(
                getattr(ppe, "ppe_type_options", None),
                current_type=getattr(ppe, "ppe_type", None),
            )

            partner_player = records.get(partner_user_id)
            partner_ppe = None
            if partner_player is not None:
                partner_ppe = _matching_partner_duo_ppe(
                    partner_ppes=getattr(partner_player, "ppes", []),
                    owner_user_id=self.owner_id,
                    expected_link_id=str(current_options.get("duo_link_id") or "").strip() or None,
                )
            _log_legacy_duo_debug(
                f"existing partner_ppe={'yes' if partner_ppe is not None else 'no'} current_duo_link_id={str(current_options.get('duo_link_id') or '').strip() or None}"
            )

            duo_link_id = str(current_options.get("duo_link_id") or "").strip() or None
            if duo_link_id is None and partner_ppe is not None:
                partner_options = normalize_ppe_type_options(
                    getattr(partner_ppe, "ppe_type_options", None),
                    current_type=getattr(partner_ppe, "ppe_type", None),
                )
                duo_link_id = str(partner_options.get("duo_link_id") or "").strip() or None
            if duo_link_id is None:
                duo_link_id = f"legacy-duo-{self.owner_id}-{self.ppe_id}-{uuid4().hex}"

            context = {
                "requester_ppe_id": int(self.ppe_id),
                "duo_link_id": duo_link_id,
            }
            _log_legacy_duo_debug(
                f"sending handshake partner_user_id={partner_user_id} duo_link_id={duo_link_id} context={context}"
            )
            await send_duo_handshake_invite(
                interaction,
                requester_user_id=self.owner_id,
                partner_user_id=partner_user_id,
                class_name=self.class_name,
                request_channel_id=interaction.channel.id if interaction.channel is not None else None,
                context=context,
            )

            current_options["duo_enabled"] = True
            current_options["duo_partner_id"] = partner_user_id
            current_options["duo_link_id"] = duo_link_id
            ppe.ppe_type_options = normalize_ppe_type_options(current_options, current_type=getattr(ppe, "ppe_type", None))
            ppe.ppe_type = infer_legacy_ppe_type_from_options(ppe.ppe_type_options)

            if partner_ppe is not None:
                partner_options = normalize_ppe_type_options(
                    getattr(partner_ppe, "ppe_type_options", None),
                    current_type=getattr(partner_ppe, "ppe_type", None),
                )
                partner_options["duo_enabled"] = True
                partner_options["duo_partner_id"] = self.owner_id
                partner_options["duo_link_id"] = duo_link_id
                partner_ppe.ppe_type_options = normalize_ppe_type_options(partner_options, current_type=getattr(partner_ppe, "ppe_type", None))
                partner_ppe.ppe_type = infer_legacy_ppe_type_from_options(partner_ppe.ppe_type_options)

            await set_duo_partner(interaction, self.owner_id, partner_user_id)
            await save_player_records(interaction, records)

            message = f"✅ Sent a duo link request for PPE #{self.ppe_id} to <@{partner_user_id}>."
            if partner_ppe is not None:
                message += f" Found a matching partner PPE #{partner_ppe.id}; it can be linked when they accept."
            else:
                message += " If they do not already have a duo PPE, they will be prompted to create one when they accept."

            await interaction.response.send_message(message, ephemeral=True)

            if self.source_message is not None:
                from menus.myinfo.submenus.character.views import ManageCharactersView

                refreshed = await refresh_player_data(interaction, self.owner_id)
                guild_config = await load_guild_config(interaction)
                refreshed_view = ManageCharactersView(
                    owner_id=self.owner_id,
                    player_data=refreshed,
                    connected_ppe_ids=self.connected_ppe_ids,
                    all_player_records=records,
                    preferred_ppe_id=self.ppe_id,
                    guild_config=guild_config,
                )
                try:
                    await self.source_message.edit(
                        embed=refreshed_view.current_embed(interaction.user, interaction.guild),
                        view=refreshed_view,
                    )
                except discord.HTTPException as exc:
                    _log_legacy_duo_debug(f"source_message refresh failed: {exc}")
        except Exception:
            _log_legacy_duo_exception(
                f"submit failed owner_id={self.owner_id} ppe_id={self.ppe_id} partner_field={getattr(self, 'partner_id', None)!r}"
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Failed to set the duo partner. Check the Railway logs for the traceback.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "Failed to set the duo partner. Check the Railway logs for the traceback.",
                    ephemeral=True,
                )


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

    def __init__(
        self,
        *,
        owner_id: int,
        source_message: discord.Message | None,
        connected_ppe_ids: set[int],
        ppe_type: str = DEFAULT_PPE_TYPE,
    ) -> None:
        super().__init__()
        self.owner_id = owner_id
        self.source_message = source_message
        self.connected_ppe_ids = connected_ppe_ids
        self.ppe_type = ppe_type

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
                ppe_type=self.ppe_type,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=False)
            return

        await interaction.response.send_message(
            f"✅ Created `PPE #{result['next_id']}` for your `{result['class_name']}` ({result['ppe_type_label']}) "
            f"and set it as your active PPE.\n"
            f"You now have {result['ppe_count']}/{result['max_ppes']} PPEs.\n\n"
            f"**Loot Adjustments**\n"
            f"{chr(10).join(loot_adjustment_detail_lines(result['loot_adjustments']))}\n",
            embed=result["embed"],
            ephemeral=False,
        )

        if self.source_message is not None:
            from menus.myinfo.submenus.character.views import ManageCharactersView

            refreshed = await refresh_player_data(interaction, self.owner_id)
            all_player_records = await load_player_records(interaction)
            guild_config = await load_guild_config(interaction)
            refreshed_view = ManageCharactersView(
                owner_id=self.owner_id,
                player_data=refreshed,
                connected_ppe_ids=self.connected_ppe_ids,
                all_player_records=all_player_records,
                preferred_ppe_id=int(result["next_id"]),
                guild_config=guild_config,
            )
            try:
                await self.source_message.edit(embed=refreshed_view.current_embed(interaction.user, interaction.guild), view=refreshed_view)
            except discord.HTTPException:
                pass


class _PPETypeSelect(discord.ui.Select):
    def __init__(self, *, allowed_types: list[str], selected_type: str) -> None:
        options = [
            discord.SelectOption(label=ppe_type_label(ppe_type), value=ppe_type, default=(ppe_type == selected_type))
            for ppe_type in allowed_types
        ]
        super().__init__(
            placeholder="Choose a PPE type",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, NewPPETypeChoiceView):
            await interaction.response.send_message("Invalid selector state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This selector belongs to another user.", ephemeral=True)
            return

        view.selected_type = self.values[0]
        for option in self.options:
            option.default = option.value == view.selected_type
        await interaction.response.edit_message(view=view)


class NewPPETypeChoiceView(discord.ui.View):
    def __init__(
        self,
        *,
        owner_id: int,
        source_message: discord.Message | None,
        connected_ppe_ids: set[int],
        allowed_types: list[str],
    ) -> None:
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.source_message = source_message
        self.connected_ppe_ids = connected_ppe_ids
        self.allowed_types = allowed_types
        self.selected_type = allowed_types[0]
        self.add_item(_PPETypeSelect(allowed_types=allowed_types, selected_type=self.selected_type))

    @discord.ui.button(label="Continue", style=discord.ButtonStyle.success, row=1)
    async def continue_to_modal(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        await interaction.response.send_modal(
            NewPPEFromMyInfoModal(
                owner_id=self.owner_id,
                source_message=self.source_message,
                connected_ppe_ids=self.connected_ppe_ids,
                ppe_type=self.selected_type,
            )
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=1)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        await interaction.response.edit_message(content="Cancelled new PPE creation.", view=None)


async def launch_new_ppe_modal_flow(
    interaction: discord.Interaction,
    *,
    owner_id: int,
    source_message: discord.Message | None,
    connected_ppe_ids: set[int],
) -> None:
    guild_config = await load_guild_config(interaction)
    ppe_settings = guild_config.get("ppe_settings", {}) if isinstance(guild_config.get("ppe_settings", {}), dict) else {}
    enabled = bool(ppe_settings.get("enable_ppe_types", True))
    allowed_types = normalize_allowed_ppe_types(ppe_settings.get("allowed_ppe_types"))

    if not enabled or len(allowed_types) == 1:
        forced_type = allowed_types[0] if enabled else DEFAULT_PPE_TYPE
        await interaction.response.send_modal(
            NewPPEFromMyInfoModal(
                owner_id=owner_id,
                source_message=source_message,
                connected_ppe_ids=connected_ppe_ids,
                ppe_type=forced_type,
            )
        )
        return

    chooser = NewPPETypeChoiceView(
        owner_id=owner_id,
        source_message=source_message,
        connected_ppe_ids=connected_ppe_ids,
        allowed_types=allowed_types,
    )
    await interaction.response.send_message(
        "Choose the PPE type for your new character.",
        view=chooser,
        ephemeral=True,
    )


__all__ = [
    "ManagePPEPenaltiesModal",
    "ManageCharacterDuoPartnerModal",
    "NewPPEFromMyInfoModal",
    "NewPPETypeChoiceView",
    "launch_new_ppe_modal_flow",
]
