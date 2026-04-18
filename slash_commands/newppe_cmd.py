

import discord
from types import SimpleNamespace
from uuid import uuid4

from dataclass import PPEData, ROTMGClass
from utils.ppe_types import (
    build_ppe_type_options,
    get_ppe_type_multiplier_details_from_options,
    infer_legacy_ppe_type_from_options,
    normalize_ppe_type_options,
    ppe_type_compact_summary,
    ppe_type_label,
    ppe_type_option_signature,
    resolve_creation_ppe_type,
)
from utils.penalty_embed import build_penalty_infographic_embed
from utils.guild_config import get_max_ppes, load_guild_config, load_guild_config_by_id
from utils.group_ppes import clear_duo_partner, get_duo_link_id_for_user, get_duo_partner, set_duo_partner
from utils.points_service import (
    apply_penalties_to_ppe,
    loot_adjustment_detail_lines,
    loot_adjustments_for_ppe,
    parse_penalty_inputs,
    recompute_ppe_points,
)
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.wizard_components import (
    MinimumRarityContinueButton,
    MinimumRaritySelect,
    build_minimum_rarity_handlers,
    get_minimum_rarity_options,
)


async def create_new_ppe_for_user(
    interaction: discord.Interaction,
    *,
    class_name: str,
    pet_level: int,
    num_exalts: int,
    percent_loot: float,
    incombat_reduction: float,
    ppe_type: str | None = None,
    ppe_type_options: dict | None = None,
    target_user_id: int | None = None,
    set_active: bool = True,
    force_ppe_id: int | None = None,
    guild_override: discord.Guild | None = None,
) -> dict:
    """Create a new PPE for a user.

    Args:
        interaction: The discord interaction.
        class_name: The ROTMG class name.
        pet_level: Pet level (0-100).
        num_exalts: Number of exalts (0-40).
        percent_loot: Loot boost percentage (0-25).
        incombat_reduction: In-combat reduction value.
        target_user_id: Optional. The user ID to create the PPE for. Defaults to interaction.user.id.
    """
    guild = interaction.guild if interaction.guild is not None else guild_override
    if guild is None:
        raise ValueError("❌ This command can only be used in a server.")

    # --- Validate class name ---
    class_enum = next((c for c in ROTMGClass if c.value == class_name), None)
    if not class_enum:
        raise ValueError(
            f"❌ `{class_name}` is not a valid RotMG class.\n"
            f"Use the autocomplete list to choose one.",
        )

    parsed_inputs, error = parse_penalty_inputs(pet_level, num_exalts, percent_loot, incombat_reduction)
    if error:
        raise ValueError(error)

    assert parsed_inputs is not None
    pet_level = int(parsed_inputs["pet_level"])
    num_exalts = int(parsed_inputs["num_exalts"])
    percent_loot = float(parsed_inputs["percent_loot"])
    incombat_reduction = float(parsed_inputs["incombat_reduction"])

    proxy_interaction = SimpleNamespace(guild=guild, user=interaction.user)

    records = await load_player_records(proxy_interaction)
    user_id = target_user_id if target_user_id is not None else interaction.user.id
    key = ensure_player_exists(records, user_id)

    player_data = records[key]

    max_ppes = await get_max_ppes(proxy_interaction)

    # --- PPE limit check ---
    ppe_count = len(player_data.ppes)
    if ppe_count >= max_ppes:
        raise ValueError(
            f"⚠️ You’ve reached the limit of `{max_ppes} PPEs`. "
            "Delete or reuse an existing one before making a new one."
        )


    # --- Create new PPE ---
    suggested_next_id = max((ppe.id for ppe in player_data.ppes), default=0) + 1
    next_id = suggested_next_id
    if isinstance(force_ppe_id, int) and force_ppe_id > 0:
        used_ids = {int(ppe.id) for ppe in player_data.ppes}
        if int(force_ppe_id) not in used_ids:
            next_id = int(force_ppe_id)

    new_ppe = PPEData(
        id=next_id,
        name=class_enum,
        points=0.0,
        loot=[],
        bonuses=[],
    )

    guild_config = await load_guild_config(proxy_interaction)
    ppe_settings = guild_config.get("ppe_settings", {}) if isinstance(guild_config.get("ppe_settings", {}), dict) else {}
    resolved_type, type_error = resolve_creation_ppe_type(
        ppe_type,
        enabled=bool(ppe_settings.get("enable_ppe_types", True)),
        allowed_types=ppe_settings.get("allowed_ppe_types", []),
    )
    if type_error:
        raise ValueError(type_error)
    new_ppe.ppe_type = resolved_type
    if isinstance(ppe_type_options, dict):
        new_ppe.ppe_type_options = normalize_ppe_type_options(ppe_type_options, current_type=resolved_type)
        new_ppe.ppe_type = infer_legacy_ppe_type_from_options(new_ppe.ppe_type_options)
    else:
        new_ppe.ppe_type_options = normalize_ppe_type_options(None, current_type=resolved_type)

    penalty_result = apply_penalties_to_ppe(
        new_ppe,
        pet_level=pet_level,
        num_exalts=num_exalts,
        percent_loot=percent_loot,
        incombat_reduction=incombat_reduction,
        guild_config=guild_config,
    )
    components = penalty_result["components"]
    pet_penalty = components["Pet Level Penalty"]
    exalt_penalty = components["Exalts Penalty"]
    loot_penalty = components["Loot Boost Penalty"]
    incombat_penalty = components["In-Combat Reduction Penalty"]

    points_breakdown = recompute_ppe_points(new_ppe, guild_config)
    points = points_breakdown["total"]
    loot_adjustments = loot_adjustments_for_ppe(new_ppe, guild_config)

    player_data.ppes.append(new_ppe)
    if set_active:
        player_data.active_ppe = next_id

    await save_player_records(interaction=proxy_interaction, records=records)

    embed = build_penalty_infographic_embed(
        pet_level=pet_level,
        num_exalts=num_exalts,
        percent_loot=percent_loot,
        incombat_reduction=incombat_reduction,
        pet_penalty=pet_penalty,
        exalt_penalty=exalt_penalty,
        loot_penalty=loot_penalty,
        incombat_penalty=incombat_penalty,
        total_points=points,
        guild_config=guild_config,
    )

    return {
        "next_id": next_id,
        "class_name": class_enum.value,
        "ppe_type": new_ppe.ppe_type,
        "ppe_type_label": ppe_type_label(new_ppe.ppe_type),
        "ppe_type_summary": ppe_type_compact_summary(
            new_ppe.ppe_type_options,
            fallback_type=new_ppe.ppe_type,
            ppe_settings=ppe_settings,
        ),
        "ppe_count": ppe_count + 1,
        "max_ppes": max_ppes,
        "loot_adjustments": loot_adjustments,
        "embed": embed,
    }


def _duo_partner_id_from_options(options: dict | None) -> int | None:
    if not isinstance(options, dict):
        return None
    raw = options.get("duo_partner_id")
    if isinstance(raw, int) and raw > 0:
        return raw
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _is_duo_enabled(options: dict | None) -> bool:
    if not isinstance(options, dict):
        return False
    return bool(options.get("duo_enabled", False))


class DuoPpeConfirmationView(discord.ui.View):
    def __init__(
        self,
        *,
        guild_id: int,
        guild_name: str,
        requester_user_id: int,
        partner_user_id: int,
        requester_display: str,
        requester_ppe_id: int,
        class_name: str,
        pet_level: int,
        num_exalts: int,
        percent_loot: float,
        incombat_reduction: float,
        duo_link_id: str,
        requester_options: dict,
        timeout_seconds: int = 86400,
    ) -> None:
        super().__init__(timeout=timeout_seconds)
        self.guild_id = int(guild_id)
        self.guild_name = str(guild_name)
        self.requester_user_id = int(requester_user_id)
        self.partner_user_id = int(partner_user_id)
        self.requester_display = str(requester_display)
        self.requester_ppe_id = int(requester_ppe_id)
        self.class_name = str(class_name)
        self.pet_level = int(pet_level)
        self.num_exalts = int(num_exalts)
        self.percent_loot = float(percent_loot)
        self.incombat_reduction = float(incombat_reduction)
        self.duo_link_id = str(duo_link_id)
        self.requester_options = dict(requester_options)
        self.completed = False

    async def _notify_requester(self, interaction: discord.Interaction, message: str) -> None:
        requester = interaction.client.get_user(self.requester_user_id)
        if requester is None:
            try:
                requester = await interaction.client.fetch_user(self.requester_user_id)
            except discord.HTTPException:
                requester = None
        if requester is not None:
            try:
                await requester.send(message)
            except discord.HTTPException:
                return

    async def _resolve_guild(self, interaction: discord.Interaction) -> discord.Guild | None:
        guild = interaction.client.get_guild(self.guild_id)
        if guild is not None:
            return guild
        try:
            fetched = await interaction.client.fetch_guild(self.guild_id)
        except discord.HTTPException:
            return None
        return interaction.client.get_guild(int(fetched.id))

    async def _finalize(self, interaction: discord.Interaction, content: str) -> None:
        self.completed = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content=content, view=self)
        self.stop()

    async def _convert_requester_to_regular(self, interaction: discord.Interaction) -> bool:
        guild = await self._resolve_guild(interaction)
        if guild is None:
            return False

        proxy_interaction = SimpleNamespace(guild=guild, user=interaction.user)
        try:
            records = await load_player_records(proxy_interaction)
        except Exception:
            return False

        requester_data = records.get(self.requester_user_id)
        if requester_data is None:
            return False

        requester_ppe = next((ppe for ppe in requester_data.ppes if int(getattr(ppe, "id", 0)) == self.requester_ppe_id), None)
        if requester_ppe is None:
            return False

        requester_ppe.ppe_type_options = normalize_ppe_type_options({"regular": True}, current_type="regular")
        requester_ppe.ppe_type = infer_legacy_ppe_type_from_options(requester_ppe.ppe_type_options)
        try:
            await save_player_records(proxy_interaction, records)
        except Exception:
            return False
        return True

    @discord.ui.button(label="Confirm Duo PPE", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if self.completed:
            await interaction.response.send_message("This duo request was already handled.", ephemeral=True)
            return
        if interaction.user.id != self.partner_user_id:
            await interaction.response.send_message("This confirmation request is for a different user.", ephemeral=True)
            return

        guild = await self._resolve_guild(interaction)
        if guild is None:
            await interaction.response.send_message("Unable to access the original server for this request.", ephemeral=True)
            return

        proxy_interaction = SimpleNamespace(guild=guild, user=interaction.user)
        try:
            await set_duo_partner(proxy_interaction, self.requester_user_id, self.partner_user_id)
        except ValueError as exc:
            await interaction.response.send_message(f"Could not confirm your duo partner: {exc}", ephemeral=True)
            return

        await self._finalize(
            interaction,
            (
                f"✅ Duo request accepted for **{self.guild_name}**. "
                "You can now create your own PPE with `/newppe` in that server and it will auto-bind as duo."
            ),
        )
        await self._notify_requester(
            interaction,
            (
                f"✅ <@{self.partner_user_id}> confirmed your duo request in **{self.guild_name}**. "
                "Their next `/newppe` in that server will automatically create a duo PPE and link to yours."
            ),
        )

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if self.completed:
            await interaction.response.send_message("This duo request was already handled.", ephemeral=True)
            return
        if interaction.user.id != self.partner_user_id:
            await interaction.response.send_message("This confirmation request is for a different user.", ephemeral=True)
            return

        converted = await self._convert_requester_to_regular(interaction)
        await self._finalize(interaction, "Declined duo request. No paired PPE was created.")
        await self._notify_requester(
            interaction,
            (
                f"❌ <@{self.partner_user_id}> declined your duo request. "
                + (
                    f"Your PPE #{self.requester_ppe_id} was converted to a regular PPE. "
                    if converted
                    else "Your PPE could not be auto-converted to regular. "
                )
                + "You can keep it, or delete it from `/myinfo`."
            ),
        )


class DuoSetupInviteView(discord.ui.View):
    def __init__(
        self,
        *,
        guild_id: int,
        guild_name: str,
        requester_user_id: int,
        partner_user_id: int,
        class_name: str,
        timeout_seconds: int = 86400,
    ) -> None:
        super().__init__(timeout=timeout_seconds)
        self.guild_id = int(guild_id)
        self.guild_name = str(guild_name)
        self.requester_user_id = int(requester_user_id)
        self.partner_user_id = int(partner_user_id)
        self.class_name = str(class_name)
        self.completed = False

    async def _resolve_guild(self, interaction: discord.Interaction) -> discord.Guild | None:
        guild = interaction.client.get_guild(self.guild_id)
        if guild is not None:
            return guild
        try:
            fetched = await interaction.client.fetch_guild(self.guild_id)
        except discord.HTTPException:
            return None
        return interaction.client.get_guild(int(fetched.id))

    async def _notify_requester(self, interaction: discord.Interaction, message: str) -> None:
        requester = interaction.client.get_user(self.requester_user_id)
        if requester is None:
            try:
                requester = await interaction.client.fetch_user(self.requester_user_id)
            except discord.HTTPException:
                requester = None
        if requester is None:
            return
        try:
            await requester.send(message)
        except discord.HTTPException:
            return

    async def _finalize(self, interaction: discord.Interaction, content: str) -> None:
        self.completed = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content=content, view=self)
        self.stop()

    @discord.ui.button(label="Accept Duo Request", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if self.completed:
            await interaction.response.send_message("This duo invite was already handled.", ephemeral=True)
            return
        if interaction.user.id != self.partner_user_id:
            await interaction.response.send_message("This duo invite is for a different user.", ephemeral=True)
            return

        guild = await self._resolve_guild(interaction)
        if guild is None:
            await interaction.response.send_message("Unable to access the original server for this request.", ephemeral=True)
            return

        proxy_interaction = SimpleNamespace(guild=guild, user=interaction.user)
        try:
            await set_duo_partner(proxy_interaction, self.requester_user_id, self.partner_user_id)
        except ValueError as exc:
            await interaction.response.send_message(f"Could not accept duo request: {exc}", ephemeral=True)
            return

        await self._finalize(
            interaction,
            (
                f"✅ Accepted duo request for **{self.guild_name}** ({self.class_name}).\n"
                "The requester can now finish creating their PPE.\n"
                "After they do, run `/newppe` in that server to create your linked duo PPE."
            ),
        )
        await self._notify_requester(
            interaction,
            (
                f"✅ <@{self.partner_user_id}> accepted your duo request in **{self.guild_name}**. "
                "You can now click **Create PPE** to finish your duo character."
            ),
        )
        launcher_view = DuoPartnerCreateLauncherView(
            owner_id=self.partner_user_id,
            guild_id=self.guild_id,
            guild_name=self.guild_name,
            partner_user_id=self.requester_user_id,
            default_class_name=self.class_name,
        )
        launcher_embed = discord.Embed(
            title="Create Linked Duo PPE",
            description="Use the button below to start your guided partner PPE creation.",
            color=discord.Color.blue(),
        )
        launcher_embed.add_field(name="This Creates In", value=f"**{self.guild_name}**", inline=True)
        launcher_embed.add_field(name="Duo Partner", value=f"<@{self.requester_user_id}>", inline=True)
        launcher_embed.add_field(name="Suggested Class", value=f"**{self.class_name}**", inline=True)
        await interaction.followup.send(
            "Ready when you are.",
            embed=launcher_embed,
            view=launcher_view,
        )

    @discord.ui.button(label="Reject Duo Request", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if self.completed:
            await interaction.response.send_message("This duo invite was already handled.", ephemeral=True)
            return
        if interaction.user.id != self.partner_user_id:
            await interaction.response.send_message("This duo invite is for a different user.", ephemeral=True)
            return

        guild = await self._resolve_guild(interaction)
        if guild is not None:
            proxy_interaction = SimpleNamespace(guild=guild, user=interaction.user)
            try:
                await clear_duo_partner(proxy_interaction, self.partner_user_id)
            except Exception:
                pass

        await self._finalize(
            interaction,
            (
                f"❌ Rejected duo request for **{self.guild_name}** ({self.class_name}).\n"
                "No duo link was created."
            ),
        )
        await self._notify_requester(
            interaction,
            (
                f"❌ <@{self.partner_user_id}> rejected your duo request in **{self.guild_name}**. "
                "You can pick a different partner or create a non-duo PPE."
            ),
        )


class DuoPartnerCreateLauncherView(discord.ui.View):
    def __init__(
        self,
        *,
        owner_id: int,
        guild_id: int,
        guild_name: str,
        partner_user_id: int,
        default_class_name: str,
        timeout_seconds: int = 86400,
    ) -> None:
        super().__init__(timeout=timeout_seconds)
        self.owner_id = int(owner_id)
        self.guild_id = int(guild_id)
        self.guild_name = str(guild_name)
        self.partner_user_id = int(partner_user_id)
        self.default_class_name = str(default_class_name)

    @discord.ui.button(label="Create Partner PPE", style=discord.ButtonStyle.success, row=0)
    async def create_partner_ppe(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This duo setup belongs to another user.", ephemeral=True)
            return

        await interaction.response.send_modal(
            DuoPartnerCreateStartModal(
                owner_id=self.owner_id,
                guild_id=self.guild_id,
                guild_name=self.guild_name,
                partner_user_id=self.partner_user_id,
                default_class_name=self.default_class_name,
            )
        )


class DuoPartnerCreateStartModal(discord.ui.Modal, title="Create Partner PPE"):
    class_name = discord.ui.TextInput(
        label="Class Name",
        placeholder="Example: Priest",
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
        guild_id: int,
        guild_name: str,
        partner_user_id: int,
        default_class_name: str,
    ) -> None:
        super().__init__(timeout=600)
        self.owner_id = int(owner_id)
        self.guild_id = int(guild_id)
        self.guild_name = str(guild_name)
        self.partner_user_id = int(partner_user_id)
        self.class_name.default = str(default_class_name or "")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This duo setup belongs to another user.", ephemeral=True)
            return

        guild = interaction.client.get_guild(self.guild_id)
        if guild is None:
            try:
                fetched = await interaction.client.fetch_guild(self.guild_id)
            except discord.HTTPException:
                await interaction.response.send_message(
                    f"Unable to access **{self.guild_name}**. Please run `/newppe` in that server instead.",
                    ephemeral=True,
                )
                return
            guild = interaction.client.get_guild(int(fetched.id))

        if guild is None:
            await interaction.response.send_message(
                f"Unable to access **{self.guild_name}**. Please run `/newppe` in that server instead.",
                ephemeral=True,
            )
            return

        parsed_inputs, error = parse_penalty_inputs(
            str(self.pet_level.value).strip(),
            str(self.num_exalts.value).strip(),
            str(self.percent_loot.value).strip(),
            str(self.incombat_reduction.value).strip(),
        )
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        assert parsed_inputs is not None
        ppe_settings = (await load_guild_config_by_id(int(guild.id))).get("ppe_settings", {})
        if not isinstance(ppe_settings, dict):
            ppe_settings = {}

        proxy_interaction = SimpleNamespace(guild=guild, user=interaction.user)
        duo_link_id = await get_duo_link_id_for_user(proxy_interaction, interaction.user.id)

        wizard = NewPpeIterativeWizardView(
            owner_id=interaction.user.id,
            class_name=str(self.class_name.value).strip(),
            pet_level=int(parsed_inputs["pet_level"]),
            num_exalts=int(parsed_inputs["num_exalts"]),
            percent_loot=float(parsed_inputs["percent_loot"]),
            incombat_reduction=float(parsed_inputs["incombat_reduction"]),
            ppe_settings=ppe_settings,
            duo_partner_id=self.partner_user_id,
            duo_link_id=duo_link_id,
            skip_duo_selection=True,
            guild_override=guild,
        )

        await interaction.response.send_message(
            (
                f"Starting duo PPE setup for **{self.guild_name}**.\n"
                f"Duo partner: <@{self.partner_user_id}>"
            )
            + "\n\n"
            + wizard.prompt_text(),
            view=wizard,
        )
        wizard.message = await interaction.original_response()


async def command(
    interaction: discord.Interaction,
    class_name: str,
    pet_level: int,
    num_exalts: int,
    percent_loot: float,
    incombat_reduction: float,
    ppe_type: str | None = None,
):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")

    if ppe_type is None:
        guild_config = await load_guild_config(interaction)
        ppe_settings = guild_config.get("ppe_settings", {}) if isinstance(guild_config.get("ppe_settings", {}), dict) else {}
        duo_partner_id = None
        duo_link_id = None
        try:
            duo_partner_id = await get_duo_partner(interaction, interaction.user.id)
        except Exception:
            duo_partner_id = None
        if duo_partner_id is not None:
            try:
                duo_link_id = await get_duo_link_id_for_user(interaction, interaction.user.id)
            except Exception:
                duo_link_id = None
        wizard = NewPpeIterativeWizardView(
            owner_id=interaction.user.id,
            class_name=class_name,
            pet_level=pet_level,
            num_exalts=num_exalts,
            percent_loot=percent_loot,
            incombat_reduction=incombat_reduction,
            ppe_settings=ppe_settings,
            duo_partner_id=duo_partner_id,
            duo_link_id=duo_link_id,
            skip_duo_selection=duo_partner_id is not None,
        )
        await interaction.response.send_message(
            wizard.prompt_text(),
            view=wizard,
            ephemeral=True,
        )
        wizard.message = await interaction.original_response()
        return

    guild_config = await load_guild_config(interaction)
    ppe_settings = guild_config.get("ppe_settings", {}) if isinstance(guild_config.get("ppe_settings", {}), dict) else {}
    resolved_type, type_error = resolve_creation_ppe_type(
        ppe_type,
        enabled=bool(ppe_settings.get("enable_ppe_types", True)),
        allowed_types=ppe_settings.get("allowed_ppe_types", []),
    )
    if type_error:
        return await interaction.response.send_message(type_error, ephemeral=True)

    selected_options = normalize_ppe_type_options(None, current_type=resolved_type)
    if _is_duo_enabled(selected_options):
        await interaction.response.send_modal(
            DuoPpeTypePartnerModal(
                class_name=class_name,
                pet_level=pet_level,
                num_exalts=num_exalts,
                percent_loot=percent_loot,
                incombat_reduction=incombat_reduction,
                resolved_ppe_type=resolved_type,
            )
        )
        return

    try:
        result = await create_new_ppe_for_user(
            interaction,
            class_name=class_name,
            pet_level=pet_level,
            num_exalts=num_exalts,
            percent_loot=percent_loot,
            incombat_reduction=incombat_reduction,
            ppe_type=resolved_type,
        )
    except ValueError as exc:
        return await interaction.response.send_message(str(exc), ephemeral=True)

    loot_adjustment_lines = "\n".join(loot_adjustment_detail_lines(result["loot_adjustments"]))

    await interaction.response.send_message(
        f"✅ Created `PPE #{result['next_id']}` for your `{result['class_name']}` "
        f"({result['ppe_type_label']}) "
        f"[{result['ppe_type_summary']}] "
        f"and set it as your active PPE.\n"
        f"You now have {result['ppe_count']}/{result['max_ppes']} PPEs.\n\n"
        f"**Loot Adjustments**\n"
        f"{loot_adjustment_lines}\n",
        embed=result["embed"],
    )


class DuoPpeTypePartnerModal(discord.ui.Modal, title="Set Duo Partner Discord ID"):
    partner_id = discord.ui.TextInput(
        label="Discord User ID",
        placeholder="Example: 123456789012345678",
        required=True,
        max_length=24,
    )

    def __init__(
        self,
        *,
        class_name: str,
        pet_level: int,
        num_exalts: int,
        percent_loot: float,
        incombat_reduction: float,
        resolved_ppe_type: str,
    ) -> None:
        super().__init__(timeout=180)
        self.class_name = class_name
        self.pet_level = pet_level
        self.num_exalts = num_exalts
        self.percent_loot = percent_loot
        self.incombat_reduction = incombat_reduction
        self.resolved_ppe_type = resolved_ppe_type

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        partner_text = str(self.partner_id.value or "").strip()
        if not partner_text.isdigit() or int(partner_text) <= 0:
            await interaction.response.send_message("Please enter a valid numeric Discord ID.", ephemeral=True)
            return

        partner_id = int(partner_text)
        if partner_id == interaction.user.id:
            await interaction.response.send_message("You cannot set yourself as your duo partner.", ephemeral=True)
            return

        guild_member = interaction.guild.get_member(partner_id)
        if guild_member is None:
            await interaction.response.send_message("❌ That user is not in this server.", ephemeral=True)
            return

        options = normalize_ppe_type_options(None, current_type=self.resolved_ppe_type)
        options["duo_enabled"] = True
        options["duo_partner_id"] = partner_id
        duo_link_id = uuid4().hex
        options["duo_link_id"] = duo_link_id

        try:
            result = await create_new_ppe_for_user(
                interaction,
                class_name=self.class_name,
                pet_level=self.pet_level,
                num_exalts=self.num_exalts,
                percent_loot=self.percent_loot,
                incombat_reduction=self.incombat_reduction,
                ppe_type=self.resolved_ppe_type,
                ppe_type_options=options,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        confirmation_view = DuoPpeConfirmationView(
            guild_id=interaction.guild.id,
            guild_name=interaction.guild.name,
            requester_user_id=interaction.user.id,
            partner_user_id=partner_id,
            requester_display=interaction.user.display_name,
            requester_ppe_id=int(result["next_id"]),
            class_name=self.class_name,
            pet_level=self.pet_level,
            num_exalts=self.num_exalts,
            percent_loot=self.percent_loot,
            incombat_reduction=self.incombat_reduction,
            duo_link_id=duo_link_id,
            requester_options=options,
        )

        dm_sent = False
        try:
            await guild_member.send(
                (
                    f"{interaction.user.mention} requested a Duo PPE with you in **{interaction.guild.name}**.\n"
                    f"Confirm that this is the server you want to use: **{interaction.guild.name}**.\n"
                    f"Character: **{self.class_name}**\n"
                    f"Their PPE ID: **#{int(result['next_id'])}**\n"
                    "If you confirm, you can create your own PPE there and it will auto-link as a duo."
                ),
                view=confirmation_view,
            )
            dm_sent = True
        except discord.HTTPException:
            dm_sent = False

        loot_adjustment_lines = "\n".join(loot_adjustment_detail_lines(result["loot_adjustments"]))
        status_suffix = (
            f"\n\n📩 Sent a duo confirmation DM to <@{partner_id}>."
            if dm_sent
            else f"\n\n⚠️ Could not DM <@{partner_id}>. Ask them to enable DMs and try again."
        )
        await interaction.response.send_message(
            f"✅ Created `PPE #{result['next_id']}` for your `{result['class_name']}` "
            f"({result['ppe_type_label']}) [{result['ppe_type_summary']}] and set it as your active PPE.\n"
            f"You now have {result['ppe_count']}/{result['max_ppes']} PPEs.\n\n"
            f"**Loot Adjustments**\n"
            f"{loot_adjustment_lines}"
            f"{status_suffix}",
            embed=result["embed"],
            ephemeral=False,
        )


class DuoPartnerIdModal(discord.ui.Modal, title="Set Duo Partner Discord ID"):
    partner_id = discord.ui.TextInput(
        label="Discord User ID",
        placeholder="Example: 123456789012345678",
        required=True,
        max_length=24,
    )

    def __init__(self, *, wizard: "NewPpeIterativeWizardView") -> None:
        super().__init__(timeout=180)
        self.wizard = wizard

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.wizard.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        partner_text = str(self.partner_id.value or "").strip()
        if not partner_text.isdigit() or int(partner_text) <= 0:
            await interaction.response.send_message("Please enter a valid numeric Discord ID.", ephemeral=True)
            return

        partner_id = int(partner_text)
        
        # Validate that partner exists in guild
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        guild_member = interaction.guild.get_member(partner_id)
        if guild_member is None:
            await interaction.response.send_message(
                f"❌ User <@{partner_id}> is not in this server.",
                ephemeral=True,
            )
            return

        try:
            await clear_duo_partner(interaction, interaction.user.id)
        except Exception:
            pass
        
        self.wizard.state["duo_partner_id"] = partner_id
        invite_view = DuoSetupInviteView(
            guild_id=interaction.guild.id,
            guild_name=interaction.guild.name,
            requester_user_id=interaction.user.id,
            partner_user_id=partner_id,
            class_name=self.wizard.class_name,
        )
        try:
            await guild_member.send(
                (
                    f"{interaction.user.mention} selected you as a Duo PPE partner in **{interaction.guild.name}**.\n"
                    f"Character: **{self.wizard.class_name}**\n"
                    "Use the buttons below to accept or reject this duo request."
                ),
                view=invite_view,
            )
        except discord.HTTPException:
            pass
        await interaction.response.send_message(
            (
                f"✅ Duo partner set to <@{partner_id}>. "
                "They were sent an Accept/Reject DM. You can create your PPE once they accept."
            ),
            ephemeral=True,
        )

        await self.wizard.advance_from_modal()


class NewPpeIterativeWizardView(discord.ui.View):
    def __init__(
        self,
        *,
        owner_id: int,
        class_name: str,
        pet_level: int,
        num_exalts: int,
        percent_loot: float,
        incombat_reduction: float,
        ppe_settings: dict,
        duo_partner_id: int | None = None,
        duo_link_id: str | None = None,
        skip_duo_selection: bool = False,
        guild_override: discord.Guild | None = None,
    ) -> None:
        super().__init__(timeout=600)
        self.owner_id = owner_id
        self.class_name = class_name
        self.pet_level = pet_level
        self.num_exalts = num_exalts
        self.percent_loot = percent_loot
        self.incombat_reduction = incombat_reduction
        self.ppe_settings = ppe_settings
        self.guild_override = guild_override
        self.skip_duo_selection = bool(skip_duo_selection or duo_partner_id is not None)
        self.base_multipliers = ppe_settings.get("iterative_base_multipliers", {}) if isinstance(ppe_settings.get("iterative_base_multipliers", {}), dict) else {}
        self.state: dict[str, object] = {
            "regular": None,
            "uses_pet": True,
            "allows_tiered": True,
            "minimum_rarity": "common",
            "shiny_only": False,
            "enforce_rarity_on_shiny": False,
            "duo_enabled": bool(duo_partner_id is not None),
            "duo_partner_id": duo_partner_id,
            "duo_link_id": duo_link_id,
        }
        self.history: list[str] = []
        self.step = "regular"
        self.message: discord.Message | None = None

        async def _refresh_minimum_rarity(interaction: discord.Interaction) -> None:
            await interaction.response.edit_message(content=self.prompt_text(), view=self)

        (
            self._minimum_rarity_on_selected,
            self._minimum_rarity_on_continue,
        ) = build_minimum_rarity_handlers(
            state=self.state,
            refresh=_refresh_minimum_rarity,
            advance=self.advance,
        )

        self._rebuild_items()

    def _multiplier_hint(self, key: str, fallback: float) -> str:
        try:
            value = float(self.base_multipliers.get(key, fallback))
        except (TypeError, ValueError):
            value = fallback
        return f"x{value:.2f}"

    def _rarity_hint(self) -> str:
        bucket = self.base_multipliers.get("minimum_rarity", {}) if isinstance(self.base_multipliers.get("minimum_rarity", {}), dict) else {}
        
        shiny_only = bool(self.state.get("shiny_only", False))
        available_options = get_minimum_rarity_options(shiny_only)

        fallback_map = {
            "all_shinies_allowed": 1.0,
            "common": 1.0,
            "uncommon": 1.1,
            "rare": 1.2,
            "legendary": 1.4,
            "divine": 1.5,
        }
        
        def _value(name: str, fallback: float) -> str:
            try:
                parsed = float(bucket.get(name, fallback))
            except (TypeError, ValueError):
                parsed = fallback
            if name == "all_shinies_allowed":
                return f"All Shinies Allowed {parsed:.2f}x"
            return f"{name.title()} {parsed:.2f}x"
        
        return ", ".join([_value(opt, fallback_map.get(opt, 1.0)) for opt in available_options])

    def prompt_text(self) -> str:
        if self.step == "regular":
            return "Are you going to do a regular PPE?"
        if self.step == "uses_pet":
            return f"Are you gonna use a pet? (No pet: {self._multiplier_hint('no_pet', 1.3)})"
        if self.step == "allows_tiered":
            return f"Do you allow yourself to use tiered items? (No tiered: {self._multiplier_hint('no_tiered', 1.3)})"
        if self.step == "shiny_only":
            return f"Is this character shiny only? (Yes: {self._multiplier_hint('shiny_only', 1.5)})"
        if self.step == "minimum_rarity":
            return f"What is the minimum rarity for this character? ({self._rarity_hint()})"
        if self.step == "enforce_shiny":
            return "Will your rarity requirement be enforced on shiny items?"
        if self.step == "duo":
            if self.skip_duo_selection:
                return "Continue setup."
            return f"Would you like to do a duo PPE? (Yes: {self._multiplier_hint('duo', 0.6)})"
        if self.step == "duo_partner":
            partner_id = self.state.get("duo_partner_id")
            partner_line = f"Current duo partner: <@{partner_id}>" if isinstance(partner_id, int) else "Current duo partner: not set"
            return (
                "Enter your duo partner Discord ID.\n"
                "How to find it: User Settings -> Advanced -> Developer Mode ON, then right click your partner and Copy User ID.\n"
                f"{partner_line}"
            )
        if self.step == "summary":
            options = build_ppe_type_options(
                regular=self.state.get("regular", True),
                uses_pet=self.state.get("uses_pet", True),
                allows_tiered=self.state.get("allows_tiered", True),
                minimum_rarity=self.state.get("minimum_rarity", "common"),
                shiny_only=self.state.get("shiny_only", False),
                enforce_rarity_on_shiny=self.state.get("enforce_rarity_on_shiny", False),
                duo_enabled=self.state.get("duo_enabled", False),
                duo_partner_id=self.state.get("duo_partner_id"),
            )
            breakdown = get_ppe_type_multiplier_details_from_options(options, self.ppe_settings)
            component_lines = [
                f"- {str(line).strip()}"
                for line in breakdown.get("component_lines", [])
                if str(line).strip()
            ]
            if not component_lines:
                component_lines = ["- No extra combo multipliers apply."]
            partner_line = "None"
            if options.get("duo_enabled"):
                partner_id = options.get("duo_partner_id")
                partner_line = f"<@{partner_id}>" if partner_id else "Missing"
            summary_lines = [
                f"Review new PPE setup for {self.class_name}.",
                f"Selected: {ppe_type_compact_summary(options, ppe_settings=self.ppe_settings)}",
                f"Signature: `{breakdown.get('signature', ppe_type_option_signature(options))}`",
                f"Duo Partner: {partner_line}",
                "",
                "Multipliers:",
                *component_lines,
                f"Final Multiplier: x{float(breakdown.get('multiplier', 1.0)):.2f}",
                "Click Create PPE to finish.",
            ]
            return "\n".join(summary_lines)
        return "Continue setup."

    def _set_yes_no(self, value: bool) -> None:
        if self.step == "regular":
            self.state["regular"] = value
        elif self.step == "uses_pet":
            self.state["uses_pet"] = value
        elif self.step == "allows_tiered":
            self.state["allows_tiered"] = value
        elif self.step == "shiny_only":
            self.state["shiny_only"] = value
        elif self.step == "enforce_shiny":
            self.state["enforce_rarity_on_shiny"] = value
        elif self.step == "duo":
            self.state["duo_enabled"] = value
            if not value:
                self.state["duo_partner_id"] = None

    def _next_step(self) -> str:
        if self.step == "regular":
            if bool(self.state.get("regular")):
                return "summary" if self.skip_duo_selection else "duo"
            return "uses_pet"
        if self.step == "uses_pet":
            return "allows_tiered"
        if self.step == "allows_tiered":
            return "shiny_only"
        if self.step == "shiny_only":
            return "minimum_rarity"
        if self.step == "minimum_rarity":
            if bool(self.state.get("shiny_only")):
                return "enforce_shiny"
            return "summary" if self.skip_duo_selection else "duo"
        if self.step == "enforce_shiny":
            return "summary" if self.skip_duo_selection else "duo"
        if self.step == "duo":
            return "duo_partner" if bool(self.state.get("duo_enabled")) else "summary"
        if self.step == "duo_partner":
            return "summary"
        return "summary"

    async def advance(self, interaction: discord.Interaction) -> None:
        self.history.append(self.step)
        self.step = self._next_step()
        self._rebuild_items()
        await interaction.response.edit_message(content=self.prompt_text(), view=self)

    async def go_back(self, interaction: discord.Interaction) -> None:
        if not self.history:
            await interaction.response.send_message("Already at the first step.", ephemeral=True)
            return

        self.step = self.history.pop()
        self._rebuild_items()
        await interaction.response.edit_message(content=self.prompt_text(), view=self)

    async def advance_from_modal(self) -> None:
        self.history.append(self.step)
        self.step = self._next_step()
        self._rebuild_items()
        if self.message is not None:
            await self.message.edit(content=self.prompt_text(), view=self)

    def _rebuild_items(self) -> None:
        self.clear_items()
        if self.step in {"regular", "uses_pet", "allows_tiered", "shiny_only", "enforce_shiny", "duo"}:
            if self.step == "duo" and self.skip_duo_selection:
                self.step = "summary"
                self._rebuild_items()
                return
            self.add_item(_WizardYesButton())
            self.add_item(_WizardNoButton())
            self.add_item(_WizardBackButton(disabled=not bool(self.history)))
            self.add_item(_WizardCancelButton())
            return
        if self.step == "minimum_rarity":
            self.add_item(
                MinimumRaritySelect(
                    selected=str(self.state.get("minimum_rarity", "common")),
                    owner_id=self.owner_id,
                    view_type=NewPpeIterativeWizardView,
                    on_selected=self._minimum_rarity_on_selected,
                    shiny_only=bool(self.state.get("shiny_only", False)),
                )
            )
            self.add_item(
                MinimumRarityContinueButton(
                    owner_id=self.owner_id,
                    view_type=NewPpeIterativeWizardView,
                    on_continue=self._minimum_rarity_on_continue,
                    row=1,
                )
            )
            self.add_item(_WizardBackButton(disabled=not bool(self.history)))
            self.add_item(_WizardCancelButton())
            return
        if self.step == "duo_partner":
            self.add_item(_WizardSetDuoIdButton())
            self.add_item(_WizardBackButton(disabled=not bool(self.history)))
            self.add_item(_WizardContinueButton())
            self.add_item(_WizardCancelButton())
            return
        if self.step == "summary":
            self.add_item(_WizardCreatePpeButton())
            self.add_item(_WizardBackButton(disabled=not bool(self.history)))
            self.add_item(_WizardCancelButton())


class _WizardYesButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Yes", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, NewPpeIterativeWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        view._set_yes_no(True)
        await view.advance(interaction)


class _WizardNoButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="No", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, NewPpeIterativeWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        view._set_yes_no(False)
        await view.advance(interaction)


class _WizardBackButton(discord.ui.Button):
    def __init__(self, *, disabled: bool) -> None:
        super().__init__(label="Back", style=discord.ButtonStyle.secondary, row=1, disabled=disabled)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, NewPpeIterativeWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        await view.go_back(interaction)


class _WizardSetDuoIdButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Set Duo Partner ID", style=discord.ButtonStyle.primary, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, NewPpeIterativeWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        await interaction.response.send_modal(DuoPartnerIdModal(wizard=view))


class _WizardContinueButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Continue", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, NewPpeIterativeWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        if bool(view.state.get("duo_enabled")) and not isinstance(view.state.get("duo_partner_id"), int):
            await interaction.response.send_message("Please set a valid duo partner Discord ID first.", ephemeral=True)
            return
        await view.advance(interaction)


class _WizardCreatePpeButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Create PPE", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, NewPpeIterativeWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        options = build_ppe_type_options(
            regular=view.state.get("regular", True),
            uses_pet=view.state.get("uses_pet", True),
            allows_tiered=view.state.get("allows_tiered", True),
            minimum_rarity=view.state.get("minimum_rarity", "common"),
            shiny_only=view.state.get("shiny_only", False),
            enforce_rarity_on_shiny=view.state.get("enforce_rarity_on_shiny", False),
            duo_enabled=view.state.get("duo_enabled", False),
            duo_partner_id=view.state.get("duo_partner_id"),
        )

        duo_enabled = _is_duo_enabled(options)
        duo_partner_id = _duo_partner_id_from_options(options)
        if duo_enabled and duo_partner_id is None:
            await interaction.response.send_message("Duo PPE requires a valid duo partner Discord ID.", ephemeral=True)
            return
        if duo_enabled and duo_partner_id == interaction.user.id:
            await interaction.response.send_message("You cannot set yourself as your duo partner.", ephemeral=True)
            return

        duo_link_id: str | None = None
        if duo_enabled:
            duo_interaction = interaction
            if interaction.guild is None and view.guild_override is not None:
                duo_interaction = SimpleNamespace(guild=view.guild_override, user=interaction.user)
            try:
                accepted_partner_id = await get_duo_partner(duo_interaction, interaction.user.id)
            except Exception:
                accepted_partner_id = None
            if int(accepted_partner_id or 0) != int(duo_partner_id):
                await interaction.response.send_message(
                    "Your duo partner has not accepted yet. Ask them to use the Accept button from the DM invite first.",
                    ephemeral=True,
                )
                return
            duo_link_id = str(view.state.get("duo_link_id") or "").strip() or None
            if duo_link_id is None:
                try:
                    duo_link_id = await get_duo_link_id_for_user(duo_interaction, interaction.user.id)
                except Exception:
                    duo_link_id = None
            if duo_link_id is None:
                duo_link_id = uuid4().hex
            options["duo_link_id"] = duo_link_id

        try:
            result = await create_new_ppe_for_user(
                interaction,
                class_name=view.class_name,
                pet_level=view.pet_level,
                num_exalts=view.num_exalts,
                percent_loot=view.percent_loot,
                incombat_reduction=view.incombat_reduction,
                ppe_type_options=options,
                guild_override=view.guild_override,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await interaction.response.edit_message(content="PPE created.", view=None)
        base_message = (
            f"✅ Created `PPE #{result['next_id']}` for your `{result['class_name']}` "
            f"({result['ppe_type_label']}) [{result['ppe_type_summary']}] and set it as your active PPE.\n"
            f"You now have {result['ppe_count']}/{result['max_ppes']} PPEs.\n\n"
            f"**Loot Adjustments**\n"
            f"Stat Reduction: **-{float(result['loot_adjustments']['total_reduction_percent']):.2f}%** "
            f"({float(result['loot_adjustments']['reduction_multiplier']):.2f}x)\n"
            f"Type Multiplier: **{float(result['loot_adjustments']['type_multiplier']):.2f}"
            f"{' (overridden)' if str(result['loot_adjustments'].get('type_multiplier_source', '')).strip().lower() == 'preset' else 'x'}**\n"
            f"Combined Multiplier: **{float(result['loot_adjustments']['combined_item_multiplier']):.2f}x**"
        )

        if not duo_enabled or duo_partner_id is None or duo_link_id is None or interaction.guild is None:
            await interaction.followup.send(base_message, embed=result["embed"], ephemeral=False)
            return

        await interaction.followup.send(
            base_message
            + f"\n\n🤝 Duo link confirmed with <@{duo_partner_id}>. "
            "They can now run `/newppe` to create their linked duo PPE.",
            embed=result["embed"],
            ephemeral=False,
        )


class _WizardCancelButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Cancel", style=discord.ButtonStyle.danger, row=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, NewPpeIterativeWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        await interaction.response.edit_message(content="Cancelled new PPE setup.", view=None)