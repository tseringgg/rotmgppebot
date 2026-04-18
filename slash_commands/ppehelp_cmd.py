

import discord

from menus.menu_utils.base_views import OwnerBoundView
from utils.guild_config import load_guild_config
from utils.pagination import chunk_lines_to_pages
from utils.ppe_types import (
    all_ppe_types,
    get_ppe_type_multiplier_details_from_options,
    legacy_ppe_type_to_options,
    normalize_combo_signature,
    normalize_iterative_combo_overrides,
    normalize_ppe_combo_label_overrides,
    options_from_signature,
    PPE_TYPE_DIVINE_ONLY,
    PPE_TYPE_DIVINE_SHINY,
    PPE_TYPE_DIVINE_NO_PET,
    PPE_TYPE_DIVINE_SHINY_NO_PET,
    PPE_TYPE_DUO,
    PPE_TYPE_DUO_NO_PET,
    PPE_TYPE_LEGENDARY_OR_SHINY,
    PPE_TYPE_LEGENDARY_OR_SHINY_NO_PET,
    PPE_TYPE_NO_PET,
    PPE_TYPE_REGULAR,
    PPE_TYPE_SHINY_ONLY,
    PPE_TYPE_SHINY_NO_PET,
    PPE_TYPE_UT_ONLY,
    PPE_TYPE_UT_NO_PET,
    normalize_iterative_option_multipliers,
    ppe_type_display_from_options,
    ppe_type_label,
    ppe_type_option_signature,
    ppe_type_short_label,
    resolve_legacy_ppe_type_from_options,
)


SECTIONS: list[str] = [
    "home",
    "types",
    "loot_bonuses",
    "quests",
    "sets",
    "teams",
    "sniffer",
    "season_setup",
]

BUTTON_LABELS: dict[str, str] = {
    "home": "Home",
    "types": "Types of PPEs",
    "loot_bonuses": "Loot & Bonuses",
    "quests": "Quests",
    "sets": "Set Completion",
    "teams": "Teams",
    "sniffer": "Sniffer",
    "season_setup": "Season Setup",
}


class HelpSectionButton(discord.ui.Button):
    def __init__(self, section_key: str, row: int):
        super().__init__(
            label=BUTTON_LABELS[section_key],
            style=discord.ButtonStyle.primary,
            row=row,
        )
        self.section_key = section_key

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, PPEHelpView):
            return
        await view.show_section(interaction, self.section_key)


class PPEHelpView(OwnerBoundView):
    def __init__(self, owner_id: int, *, ppe_settings: dict | None = None):
        super().__init__(owner_id=owner_id, timeout=600)
        self.current_section = "home"
        self.types_overrides_page_index = 0
        self.ppe_settings = ppe_settings if isinstance(ppe_settings, dict) else {}

        for index, section_key in enumerate(SECTIONS):
            row = 0 if index < 5 else 1
            self.add_item(HelpSectionButton(section_key=section_key, row=row))

        self.add_item(
            discord.ui.Button(
                label="Close",
                style=discord.ButtonStyle.danger,
                row=1,
                custom_id="ppehelp_close",
            )
        )
        self._sync_button_styles()
        self._sync_types_pagination_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not await super().interaction_check(interaction):
            return False
        if interaction.data and interaction.data.get("custom_id") == "ppehelp_close":
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            await interaction.response.edit_message(content="Closed /ppehelp menu.", embed=None, view=self)
            self.stop()
            return False
        return True

    def _sync_button_styles(self) -> None:
        for item in self.children:
            if not isinstance(item, HelpSectionButton):
                continue
            item.style = (
                discord.ButtonStyle.success
                if item.section_key == self.current_section
                else discord.ButtonStyle.primary
            )

    def _sync_types_pagination_buttons(self) -> None:
        total_pages = get_types_override_page_count(self.ppe_settings)
        is_types_section = self.current_section == "types"
        show_controls = is_types_section
        has_prev = self.prev_types_overrides_page in self.children
        has_next = self.next_types_overrides_page in self.children

        if show_controls:
            if not has_prev:
                self.add_item(self.prev_types_overrides_page)
            if not has_next:
                self.add_item(self.next_types_overrides_page)
        else:
            if has_prev:
                self.remove_item(self.prev_types_overrides_page)
            if has_next:
                self.remove_item(self.next_types_overrides_page)

        controls_disabled = total_pages <= 1
        self.prev_types_overrides_page.disabled = controls_disabled
        self.next_types_overrides_page.disabled = controls_disabled
        if total_pages > 0 and self.types_overrides_page_index >= total_pages:
            self.types_overrides_page_index = total_pages - 1

    async def show_section(self, interaction: discord.Interaction, section_key: str) -> None:
        self.current_section = section_key
        if section_key != "types":
            self.types_overrides_page_index = 0
        self._sync_button_styles()
        self._sync_types_pagination_buttons()
        embed = build_help_embed(
            section_key,
            ppe_settings=self.ppe_settings,
            types_overrides_page_index=self.types_overrides_page_index,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Prev Overrides", style=discord.ButtonStyle.secondary, row=2)
    async def prev_types_overrides_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if self.current_section != "types":
            await interaction.response.edit_message(
                embed=build_help_embed(
                    self.current_section,
                    ppe_settings=self.ppe_settings,
                    types_overrides_page_index=self.types_overrides_page_index,
                ),
                view=self,
            )
            return
        total_pages = get_types_override_page_count(self.ppe_settings)
        if total_pages <= 1:
            self._sync_types_pagination_buttons()
            await interaction.response.edit_message(
                embed=build_help_embed(
                    self.current_section,
                    ppe_settings=self.ppe_settings,
                    types_overrides_page_index=self.types_overrides_page_index,
                ),
                view=self,
            )
            return
        self.types_overrides_page_index = (self.types_overrides_page_index - 1) % total_pages
        self._sync_types_pagination_buttons()
        await interaction.response.edit_message(
            embed=build_help_embed(
                self.current_section,
                ppe_settings=self.ppe_settings,
                types_overrides_page_index=self.types_overrides_page_index,
            ),
            view=self,
        )

    @discord.ui.button(label="Next Overrides", style=discord.ButtonStyle.secondary, row=2)
    async def next_types_overrides_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if self.current_section != "types":
            await interaction.response.edit_message(
                embed=build_help_embed(
                    self.current_section,
                    ppe_settings=self.ppe_settings,
                    types_overrides_page_index=self.types_overrides_page_index,
                ),
                view=self,
            )
            return
        total_pages = get_types_override_page_count(self.ppe_settings)
        if total_pages <= 1:
            self._sync_types_pagination_buttons()
            await interaction.response.edit_message(
                embed=build_help_embed(
                    self.current_section,
                    ppe_settings=self.ppe_settings,
                    types_overrides_page_index=self.types_overrides_page_index,
                ),
                view=self,
            )
            return
        self.types_overrides_page_index = (self.types_overrides_page_index + 1) % total_pages
        self._sync_types_pagination_buttons()
        await interaction.response.edit_message(
            embed=build_help_embed(
                self.current_section,
                ppe_settings=self.ppe_settings,
                types_overrides_page_index=self.types_overrides_page_index,
            ),
            view=self,
        )


def _divider() -> str:
    return "----------------------------------------"


def _common_footer() -> str:
    return "Use /ppehelp anytime."


def _build_iterative_defaults_lines(ppe_settings: dict | None) -> list[str]:
    base = (
        ppe_settings.get("iterative_base_multipliers", {})
        if isinstance(ppe_settings, dict) and isinstance(ppe_settings.get("iterative_base_multipliers"), dict)
        else {}
    )
    multipliers = normalize_iterative_option_multipliers(base)
    rarity = multipliers.get("minimum_rarity", {}) if isinstance(multipliers.get("minimum_rarity"), dict) else {}
    return [
        f"- No Pet: x{float(multipliers.get('no_pet', 1.3)):.2f}",
        f"- No Tiered: x{float(multipliers.get('no_tiered', 1.3)):.2f}",
        f"- Minimum rarity: Common x{float(rarity.get('common', 1.0)):.2f}, Uncommon x{float(rarity.get('uncommon', 1.1)):.2f}, Rare x{float(rarity.get('rare', 1.2)):.2f}, Legendary x{float(rarity.get('legendary', 1.4)):.2f}, Divine x{float(rarity.get('divine', 1.5)):.2f}",
        f"- Shiny Only: x{float(multipliers.get('shiny_only', 1.5)):.2f}",
        f"- Enforce Shiny Rarity: x{float(multipliers.get('enforce_shiny_rarity', 0.9)):.2f}",
        f"- Duo: x{float(multipliers.get('duo', 0.6)):.2f}",
    ]


def _build_types_override_lines(ppe_settings: dict | None) -> list[str]:
    settings = ppe_settings if isinstance(ppe_settings, dict) else {}
    lines: list[str] = []

    for ppe_type in all_ppe_types():
        options = legacy_ppe_type_to_options(ppe_type)
        details = get_ppe_type_multiplier_details_from_options(options, settings, current_type=ppe_type)
        value = float(details.get("multiplier", 1.0))
        source = str(details.get("source", "base")).strip().lower()
        source_suffix = ""
        if source == "override":
            source_suffix = " (combo override)"
        elif source == "preset":
            source_suffix = " (default override)"
        lines.append(
            f"- {ppe_type_label(ppe_type, ppe_settings=settings)} [{ppe_type_short_label(ppe_type, ppe_settings=settings)}]: x{value:.2f}{source_suffix}"
        )

    combo_overrides = normalize_iterative_combo_overrides(settings.get("iterative_combo_overrides"))
    combo_labels = normalize_ppe_combo_label_overrides(settings.get("combo_label_overrides"))
    candidate_signatures: set[str] = set()
    for raw_signature in list(combo_overrides.keys()) + list(combo_labels.keys()):
        signature = normalize_combo_signature(raw_signature)
        if signature and signature != "regular":
            candidate_signatures.add(signature)

    for signature in sorted(candidate_signatures):
        options = options_from_signature(signature)
        if not isinstance(options, dict):
            continue

        legacy_type = resolve_legacy_ppe_type_from_options(options)
        if legacy_type is not None:
            legacy_signature = ppe_type_option_signature(legacy_ppe_type_to_options(legacy_type))
            if signature == legacy_signature:
                continue

        details = get_ppe_type_multiplier_details_from_options(options, settings)
        value = float(details.get("multiplier", 1.0))
        source = str(details.get("source", "base")).strip().lower()
        source_suffix = ""
        if source == "override":
            source_suffix = " (combo override)"
        elif source == "preset":
            source_suffix = " (default override)"
        lines.append(
            f"- {ppe_type_display_from_options(options, ppe_settings=settings, compact=False)} [{ppe_type_display_from_options(options, ppe_settings=settings, compact=True)}]: x{value:.2f}{source_suffix}"
        )

    return lines


def _types_override_pages(ppe_settings: dict | None) -> list[list[str]]:
    lines = _build_types_override_lines(ppe_settings)
    pages = chunk_lines_to_pages(lines, 950)
    return pages if pages else [["- No overrides configured."]]


def get_types_override_page_count(ppe_settings: dict | None) -> int:
    return len(_types_override_pages(ppe_settings))


def build_help_embed(
    section_key: str,
    *,
    ppe_settings: dict | None = None,
    types_overrides_page_index: int = 0,
) -> discord.Embed:
    if section_key == "home":
        embed = discord.Embed(
            title="PPE Bot Help - Home",
            description=(
                "Welcome to the RotMG PPE Discord Bot. Use this menu to navigate loot logging, quest tracking, "
                "contest tools, and season management."
            ),
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="General Bot Information",
            value=(
                "This bot tracks PPE characters, season-wide loot, quests, and competition settings.\n"
                "It also supports teams, reaction-based contest joins, and dynamic point scoring.\n"
                "**Normal players** will mostly use `/myinfo` and other `/my...` commands.\n"
                "**Admins** also get `/manage...` commands for season and server controls.\n"
                f"{_divider()}\n"
            ),
            inline=False,
        )

        embed.add_field(
            name="Season Loot (Global Account Progress)",
            value=(
                "Season loot tracks unique loot across your whole account, not just one PPE.\n"
                "You can log season loot with `/addseasonloot` even before creating a PPE.\n"
                "All PPE loot is also logged to season loot automatically.\n"
                f"{_divider()}\n"
            ),
            inline=False,
        )
        embed.add_field(
            name="PPE Characters (Per Character Progress)",
            value=(
                "PPEs track your per-character run, loot, points, and penalties.\n"
                "Start with `/newppe`, then use `/addloot` to add items to your PPE."
            ),
            inline=False,
        )
        embed.set_footer(text=_common_footer())
        return embed

    if section_key == "types":
        embed = discord.Embed(
            title="PPE Bot Help - Types of PPEs",
            description=(
                "PPE type scoring is now option-based. You choose rules, and the bot builds your type summary and multiplier."
            ),
            color=discord.Color.blurple(),
        )
        lines = [
            "- Regular PPE: skips most option questions and keeps baseline type rules.",
            "- Duo PPE: applies the Duo factor and needs a duo partner ID to stay duo-enabled.",
            "- Custom PPE: any option combination that does not match a legacy preset type is shown as Custom PPE.",
        ]
        lines.extend(_build_iterative_defaults_lines(ppe_settings))
        lines.append("- Enforce rarity on shiny: if enabled with high rarity, extra stacking can apply.")
        lines.append("- Duo: uses the configured duo multiplier and requires your partner Discord ID.")
        embed.add_field(name="Option Multipliers (Defaults)", value="\n".join(lines), inline=False)
        embed.add_field(
            name="Shorthand Tokens",
            value=(
                "- `NPE`: no pet\n"
                "- `UT0`: no tiered\n"
                "- `MINU/MINR/MINL/MIND`: minimum rarity\n"
                "- `SH`: shiny only\n"
                "- `ERS`: enforce rarity on shiny\n"
                "- `DUO`: duo enabled"
            ),
            inline=False,
        )
        embed.add_field(
            name="Custom Names and Shorthands",
            value=(
                "Admins can customize labels in `/manageseason -> Manage Point Settings -> Edit PPE Type`.\n"
                "Use combo overrides to set custom names/shorthands for specific option-combination signatures."
            ),
            inline=False,
        )
        override_pages = _types_override_pages(ppe_settings)
        total_pages = len(override_pages)
        page_index = max(0, min(int(types_overrides_page_index), total_pages - 1)) if total_pages > 0 else 0
        override_lines = override_pages[page_index] if total_pages > 0 else ["- No overrides configured."]
        page_suffix = f" (Page {page_index + 1}/{total_pages})" if total_pages > 1 else ""
        embed.add_field(
            name=f"Current Type/Combo Overrides{page_suffix}",
            value="\n".join(override_lines) if override_lines else "- No overrides configured.",
            inline=False,
        )
        embed.set_footer(text=_common_footer())
        return embed

    if section_key == "loot_bonuses":
        embed = discord.Embed(
            title="PPE Bot Help - Loot & Bonuses",
            description=(
                "Use this section to understand how loot and bonus points are added, removed, and recalculated "
                "for PPE characters and season collections."
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Normal Player",
            value=(
                "- `/addloot` and `/removeloot` update active PPE loot, including timestamp history\n"
                "- `/addbonus` and `/removebonus` manage active PPE bonuses\n"
                "- `/myinfo -> Manage Characters -> Statistics` shows loot and stats tools for that PPE\n"
                "- `/myinfo -> Manage Characters` opens character management\n"
                "- `/myinfo -> Show Season Stats` shows a wrapped recap and graphic for season-wide progress\n"
                "- Season loot is account-wide, so it can be logged separately or through a specific PPE"
            ),
            inline=False,
        )
        embed.add_field(name=_divider(), value="\u200b", inline=False)
        embed.add_field(
            name="Admin",
            value=(
                "- `/addlootfor` and `/removelootfrom` edit targeted PPE loot\n"
                "- `/addbonusfor` and `/removebonusfrom` handle admin bonus edits\n"
                "- `/addpointsfor` applies manual point adjustments\n"
                "- `/refreshpointsfor` or `/refreshallpoints` recomputes totals after CSV point changes\n"
                "- If you edit `rotmg_loot_drops_updated.csv`, refresh points so player totals match the new values\n"
                "- Sniffer users also need the updated CSV locally when item points change"
            ),
            inline=False,
        )
        embed.set_footer(text=_common_footer())
        return embed

    if section_key == "quests":
        embed = discord.Embed(
            title="PPE Bot Help - Quests",
            description=(
                "Quests provide rotating account goals for items, shinies, and skins with tracked completion "
                "and leaderboard integration. If global quests are enabled, everyone will share the same starting quests."
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Normal Player",
            value=(
                "- `/myquests` or `/myinfo -> Show Quests` opens your shared quest menu\n"
                "- Quest menu actions let you review progress and reset a limited number of your own quests each season\n"
            ),
            inline=False,
        )
        embed.add_field(name=_divider(), value="\u200b", inline=False)
        embed.add_field(
            name="Admin",
            value=(
                "- `/removeseasonlootfrom` removes matching completed quest entries when it targets a quest item\n"
                "- `/managequests` edits targets, global quest pools, and point settings\n"
                "- `/managequests -> Reset All Quests` performs a server-wide quest reset\n"
                "- `/manageplayer -> Show Quests` lets you view or reset a specific player's quests"
            ),
            inline=False,
        )
        embed.set_footer(text=_common_footer())
        return embed

    if section_key == "teams":
        embed = discord.Embed(
            title="PPE Bot Help - Teams",
            description=(
                "Teams combine member scores using each member's best PPE and support collaborative rankings "
                "through dedicated team menus."
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Normal Player",
            value=(
                "- `/myteam` shows your team's members and rankings\n"
                "- `/leaderboard` includes team rankings\n"
            ),
            inline=False,
        )
        embed.add_field(name=_divider(), value="\u200b", inline=False)
        embed.add_field(
            name="Admin",
            value=(
                "- `/manageteams` creates, renames, deletes, and sets team leaders\n"
                "- `/manageteams` also opens team leaderboard and member controls\n"
                "- `/manageplayer -> Team actions` adds or removes players from teams\n"
                "- `/manageseason -> Manage Contests -> Manage Leaderboard` controls whether quests count for team scores"
            ),
            inline=False,
        )
        embed.set_footer(text=_common_footer())
        return embed

    if section_key == "sniffer":
        embed = discord.Embed(
            title="PPE Bot Help - Sniffer",
            description=(
                "Sniffer integration auto-logs in-game drops to PPE or season loot with character-aware routing and "
                "pending-review tools for unmapped characters. You must use the sniffer client built for this bot, "
                "and it needs the loot CSV in the same folder."
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Normal Player",
            value=(
                "- `/mysniffer` opens your sniffer dashboard\n"
                "- Generate or unlink a token, then open Configure Characters\n"
                "- Map character IDs to PPEs or seasonal routing and resolve pending loot"
            ),
            inline=False,
        )
        embed.add_field(name=_divider(), value="\u200b", inline=False)
        embed.add_field(
            name="Admin",
            value=(
                "- `/managesniffer` enables or disables sniffer support\n"
                "- Manage tokens, output channel, and player sniffer state\n"
                "- Use reset and revoke actions from the admin sniffer panel when needed\n"
                "- Refer to the repository README for setup instructions"
            ),
            inline=False,
        )
        embed.set_footer(text=_common_footer())
        return embed

    if section_key == "sets":
        embed = discord.Embed(
            title="PPE Bot Help - Set Completion",
            description=(
                "Item sets are collections of 4 special items that can be completed for bonus points. "
                "When you log all items in a set, you receive a congratulations message and bonus points."
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="How Sets Work",
            value=(
                "- Item sets consist of 4 pieces: Weapon, Ability, Armor, and Ring\n"
                "- When you log all 4 items from a set (via `/addloot`, sniffer, or `/submitloot`), the bot automatically detects completion\n"
                "- You receive a public congratulations message announcing your set completion\n"
                "- Each set is completed **once per PPE** - completing the same set on different PPEs gives points each time\n"
                "- Set completion bonus points are configurable by server admins (default: 0 points)\n"
                "- Standard (ST) and Unique (UT) sets are tracked separately"
            ),
            inline=False,
        )
        embed.add_field(name=_divider(), value="\u200b", inline=False)
        embed.add_field(
            name="Admin",
            value=(
                "- `/manageseason -> Manage Point Settings -> Manage Set Completion Points` opens the set points menu\n"
                "- Choose \"Manage ST Set Points\" or \"Manage UT Set Points\" to configure bonus points for each set\n"
                "- Use the form to enter one set per line as `SetName=points` (e.g., `Golden Archer Set=50`)\n"
                "- Set points are added as bonuses when a set is completed and count toward the PPE's total\n"
                "- Use \"Reset to Zero\" to clear all set bonuses for a type"
            ),
            inline=False,
        )
        embed.set_footer(text=_common_footer())
        return embed

    embed = discord.Embed(
        title="PPE Bot Help - Season Setup",
        description=(
            "Season setup controls global contest configuration, including the step-by-step season reset flow, "
            "point settings, and optional screenshot suggestion channels."
        ),
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="Normal Player",
        value=(
            "- `/addseasonloot` and `/removeseasonloot` manage your global season collection\n"
            "- `/myinfo -> Show Season Stats` shows list, image, and wrapped views\n"
            "- Season tracking works even if you never create a PPE"
        ),
        inline=False,
    )
    embed.add_field(name=_divider(), value="\u200b", inline=False)
    embed.add_field(
        name="Admin",
        value=(
            "- `/addseasonlootfor` and `/removeseasonlootfrom` handle admin season adjustments\n"
            "- `/manageseason` adjusts the season's core behavior and values\n"
            "- `/manageseason -> Reset Season` is a guided reset flow with confirmations for each step\n"
            "- The PPE Player / Join Embed reset step also removes contest reactions from the join embed when players are removed\n"
            "- `/manageseason -> Reset Season -> Reset Sniffer Information` lets you choose exactly what sniffer data to clear\n"
            "- `/manageseason -> Manage Point Settings -> Edit Duplicate Item Points` controls duplicate scoring; set Point Reduction to 0 to disable it\n"
            "- `/manageseason -> Picture Suggestions` configures automatic image detection of loot in selected channels\n"
            "- `/manageseason -> Manage Contests` sets contest defaults and leaderboard behavior\n"
            "- `/forcereset` is a server-owner-only full data wipe and should only be used for a complete restart"
        ),
        inline=False,
    )
    embed.set_footer(text=_common_footer())
    return embed


async def command(interaction: discord.Interaction):
    guild_config = await load_guild_config(interaction)
    ppe_settings = guild_config.get("ppe_settings", {}) if isinstance(guild_config.get("ppe_settings"), dict) else {}
    view = PPEHelpView(owner_id=interaction.user.id, ppe_settings=ppe_settings)
    embed = build_help_embed("home", ppe_settings=ppe_settings, types_overrides_page_index=0)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
