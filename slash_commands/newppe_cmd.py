

import discord

from dataclass import PPEData, ROTMGClass
from utils.ppe_types import (
    build_ppe_type_options,
    infer_legacy_ppe_type_from_options,
    normalize_ppe_type_options,
    ppe_type_compact_summary,
    ppe_type_label,
    ppe_type_option_signature,
    resolve_creation_ppe_type,
)
from utils.penalty_embed import build_penalty_infographic_embed
from utils.guild_config import get_max_ppes, load_guild_config
from utils.points_service import (
    apply_penalties_to_ppe,
    loot_adjustment_detail_lines,
    loot_adjustments_for_ppe,
    parse_penalty_inputs,
    recompute_ppe_points,
)
from utils.player_records import ensure_player_exists, load_player_records, save_player_records


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
    if not interaction.guild:
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

    records = await load_player_records(interaction)
    user_id = target_user_id if target_user_id is not None else interaction.user.id
    key = ensure_player_exists(records, user_id)

    player_data = records[key]

    max_ppes = await get_max_ppes(interaction)

    # --- PPE limit check ---
    ppe_count = len(player_data.ppes)
    if ppe_count >= max_ppes:
        raise ValueError(
            f"⚠️ You’ve reached the limit of `{max_ppes} PPEs`. "
            "Delete or reuse an existing one before making a new one."
        )


    # --- Create new PPE ---
    next_id = max((ppe.id for ppe in player_data.ppes), default=0) + 1

    new_ppe = PPEData(
        id=next_id,
        name=class_enum,
        points=0.0,
        loot=[],
        bonuses=[],
    )

    guild_config = await load_guild_config(interaction)
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
    player_data.active_ppe = next_id

    await save_player_records(interaction=interaction, records=records)

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
        wizard = NewPpeIterativeWizardView(
            owner_id=interaction.user.id,
            class_name=class_name,
            pet_level=pet_level,
            num_exalts=num_exalts,
            percent_loot=percent_loot,
            incombat_reduction=incombat_reduction,
            ppe_settings=ppe_settings,
        )
        await interaction.response.send_message(
            wizard.prompt_text(),
            view=wizard,
            ephemeral=True,
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
            ppe_type=ppe_type,
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

        self.wizard.state["duo_partner_id"] = int(partner_text)
        await interaction.response.send_message(
            f"Saved duo partner as <@{partner_text}>. Click Continue in the wizard to finish.",
            ephemeral=True,
        )


class _RaritySelect(discord.ui.Select):
    def __init__(self, *, selected: str) -> None:
        options = [
            discord.SelectOption(label="Common", value="common", default=selected == "common"),
            discord.SelectOption(label="Uncommon", value="uncommon", default=selected == "uncommon"),
            discord.SelectOption(label="Rare", value="rare", default=selected == "rare"),
            discord.SelectOption(label="Legendary", value="legendary", default=selected == "legendary"),
            discord.SelectOption(label="Divine", value="divine", default=selected == "divine"),
        ]
        super().__init__(
            placeholder="Select minimum rarity",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, NewPpeIterativeWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        view.state["minimum_rarity"] = self.values[0]
        await view.advance(interaction)


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
    ) -> None:
        super().__init__(timeout=600)
        self.owner_id = owner_id
        self.class_name = class_name
        self.pet_level = pet_level
        self.num_exalts = num_exalts
        self.percent_loot = percent_loot
        self.incombat_reduction = incombat_reduction
        self.ppe_settings = ppe_settings
        self.base_multipliers = ppe_settings.get("iterative_base_multipliers", {}) if isinstance(ppe_settings.get("iterative_base_multipliers", {}), dict) else {}
        self.state: dict[str, object] = {
            "regular": None,
            "uses_pet": True,
            "allows_tiered": True,
            "minimum_rarity": "common",
            "shiny_only": False,
            "enforce_rarity_on_shiny": False,
            "duo_enabled": False,
            "duo_partner_id": None,
        }
        self.step = "regular"
        self._rebuild_items()

    def _multiplier_hint(self, key: str, fallback: float) -> str:
        try:
            value = float(self.base_multipliers.get(key, fallback))
        except (TypeError, ValueError):
            value = fallback
        return f"x{value:.2f}"

    def _rarity_hint(self) -> str:
        bucket = self.base_multipliers.get("minimum_rarity", {}) if isinstance(self.base_multipliers.get("minimum_rarity", {}), dict) else {}
        def _value(name: str, fallback: float) -> str:
            try:
                parsed = float(bucket.get(name, fallback))
            except (TypeError, ValueError):
                parsed = fallback
            return f"{name.title()} {parsed:.2f}x"
        return ", ".join([
            _value("common", 1.0),
            _value("uncommon", 1.1),
            _value("rare", 1.2),
            _value("legendary", 1.4),
            _value("divine", 1.5),
        ])

    def prompt_text(self) -> str:
        if self.step == "regular":
            return "Are you going to do a regular PPE?"
        if self.step == "uses_pet":
            return f"Are you gonna use a pet? (No pet: {self._multiplier_hint('no_pet', 1.3)})"
        if self.step == "allows_tiered":
            return f"Do you allow yourself to use tiered items? (No tiered: {self._multiplier_hint('no_tiered', 1.3)})"
        if self.step == "minimum_rarity":
            return f"What is the minimum rarity for this PPE? ({self._rarity_hint()})"
        if self.step == "shiny_only":
            return f"Are you shiny only? (Yes: {self._multiplier_hint('shiny_only', 1.5)})"
        if self.step == "enforce_shiny":
            return "Will your rarity requirement be enforced on shiny items?"
        if self.step == "duo":
            return f"Would you like to do a duo PPE? (Yes: {self._multiplier_hint('duo', 0.6)})"
        if self.step == "duo_partner":
            partner_id = self.state.get("duo_partner_id")
            partner_line = f"Current duo partner: <@{partner_id}>" if isinstance(partner_id, int) else "Current duo partner: not set"
            return (
                "Enter your duo partner Discord ID.\n"
                "How to find it: User Settings -> Advanced -> Developer Mode ON, then right click your partner and Copy User ID.\n"
                f"{partner_line}"
            )
        if self.step == "confirm":
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
            signature = ppe_type_option_signature(options)
            summary = ppe_type_compact_summary(options, ppe_settings=self.ppe_settings)
            partner_line = "None"
            if options.get("duo_enabled"):
                partner_id = options.get("duo_partner_id")
                partner_line = f"<@{partner_id}>" if partner_id else "Missing"
            return (
                f"Confirm new PPE setup for {self.class_name}.\n"
                f"Summary: {summary}\n"
                f"Signature: `{signature}`\n"
                f"Duo Partner: {partner_line}\n"
                "Click Confirm to create the PPE."
            )
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
            return "duo" if bool(self.state.get("regular")) else "uses_pet"
        if self.step == "uses_pet":
            return "allows_tiered"
        if self.step == "allows_tiered":
            return "minimum_rarity"
        if self.step == "minimum_rarity":
            return "shiny_only"
        if self.step == "shiny_only":
            return "enforce_shiny" if bool(self.state.get("shiny_only")) else "duo"
        if self.step == "enforce_shiny":
            return "duo"
        if self.step == "duo":
            return "duo_partner" if bool(self.state.get("duo_enabled")) else "confirm"
        if self.step == "duo_partner":
            return "confirm"
        return "confirm"

    async def advance(self, interaction: discord.Interaction) -> None:
        self.step = self._next_step()
        self._rebuild_items()
        await interaction.response.edit_message(content=self.prompt_text(), view=self)

    def _rebuild_items(self) -> None:
        self.clear_items()
        if self.step in {"regular", "uses_pet", "allows_tiered", "shiny_only", "enforce_shiny", "duo"}:
            self.add_item(_WizardYesButton())
            self.add_item(_WizardNoButton())
            self.add_item(_WizardCancelButton())
            return
        if self.step == "minimum_rarity":
            self.add_item(_RaritySelect(selected=str(self.state.get("minimum_rarity", "common"))))
            self.add_item(_WizardCancelButton())
            return
        if self.step == "duo_partner":
            self.add_item(_WizardSetDuoIdButton())
            self.add_item(_WizardContinueButton())
            self.add_item(_WizardCancelButton())
            return
        if self.step == "confirm":
            self.add_item(_WizardConfirmCreateButton())
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


class _WizardConfirmCreateButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Confirm Create", style=discord.ButtonStyle.success, row=0)

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

        try:
            result = await create_new_ppe_for_user(
                interaction,
                class_name=view.class_name,
                pet_level=view.pet_level,
                num_exalts=view.num_exalts,
                percent_loot=view.percent_loot,
                incombat_reduction=view.incombat_reduction,
                ppe_type_options=options,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await interaction.response.edit_message(content="PPE created.", view=None)
        await interaction.followup.send(
            f"✅ Created `PPE #{result['next_id']}` for your `{result['class_name']}` "
            f"({result['ppe_type_label']}) [{result['ppe_type_summary']}] and set it as your active PPE.\n"
            f"You now have {result['ppe_count']}/{result['max_ppes']} PPEs.\n\n"
            f"**Loot Adjustments**\n"
            f"Stat Reduction: **-{float(result['loot_adjustments']['total_reduction_percent']):.2f}%** "
            f"({float(result['loot_adjustments']['reduction_multiplier']):.2f}x)\n"
            f"Type Multiplier: **{float(result['loot_adjustments']['type_multiplier']):.2f}x**\n"
            f"Combined Multiplier: **{float(result['loot_adjustments']['combined_item_multiplier']):.2f}x**",
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