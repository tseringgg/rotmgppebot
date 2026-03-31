

import discord

from menus.menu_utils.base_views import OwnerBoundView


SECTIONS: list[str] = [
    "home",
    "loot_bonuses",
    "quests",
    "teams",
    "sniffer",
    "season_setup",
]

BUTTON_LABELS: dict[str, str] = {
    "home": "Home",
    "loot_bonuses": "Loot & Bonuses",
    "quests": "Quests",
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
    def __init__(self, owner_id: int):
        super().__init__(owner_id=owner_id, timeout=600)
        self.current_section = "home"

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

    async def show_section(self, interaction: discord.Interaction, section_key: str) -> None:
        self.current_section = section_key
        self._sync_button_styles()
        embed = build_help_embed(section_key)
        await interaction.response.edit_message(embed=embed, view=self)


def _divider() -> str:
    return "----------------------------------------"


def _common_footer() -> str:
    return "Use /ppehelp anytime."


def build_help_embed(section_key: str) -> discord.Embed:
    if section_key == "home":
        embed = discord.Embed(
            title="PPE Bot Help - Home",
            description=(
                "Welcome to the RotMG PPE Discord Bot. This menu is your navigation hub for logging loot, "
                "tracking progress, managing quests, and handling contest tools."
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Season Loot (Global Account Progress)",
            value=(
                "Season loot tracks unique loot across your whole account, not just one PPE.\n" 
                "You can log season loot with /addseasonloot even if you do not have a PPE character yet.\n"
                f"{_divider()}\n"
            ),
            inline=False,
        )
        embed.add_field(
            name="PPE Characters (Per Character Progress)",
            value=(
                "PPEs track your per-character run, loot, points, and penalties.\n"
                "Start with /newppe, then use /myinfo to view and manage your account's PPE + season data."
            ),
            inline=False,
        )
        embed.set_footer(text=_common_footer())
        return embed

    if section_key == "loot_bonuses":
        embed = discord.Embed(
            title="PPE Bot Help - Loot & Bonuses",
            description=(
                "Use this section to understand how loot and bonus points are added, adjusted, and recalculated "
                "for PPE characters and season collections."
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Normal Player",
            value=(
                "- /addloot and /removeloot to update active PPE loot\n"
                "- /addbonus and /removebonus to manage active PPE bonuses\n"
                "- /myinfo -> Manage Characters -> Show Loot for a graphic of all loot earned on that specific PPE.\n"
                "- /myinfo -> Manage Characters to manage characters\n"
                "- /myinfo -> Show Season Loot for a graphic of all loot earned over the season. Note that season"
                 " loot is account-wide and not tied to specific PPE characters, so it can be logged separately as well as through a specific PPE."
            ),
            inline=False,
        )
        embed.add_field(name=_divider(), value="\u200b", inline=False)
        embed.add_field(
            name="Admin",
            value=(
                "- /addlootfor and /removelootfrom for targeted PPE loot edits\n"
                "- /addbonusfor and /removebonusfrom for admin bonus edits\n"
                "- /addpointsfor for manual point adjustments\n"
                "- /refreshpointsfor or /refreshallpoints to repair/recompute point totals after adjusting the rotmg_loot_drops_updated.csv\n"
                "- You can adjust points for items by manually editing and saving the rotmg_loot_drops_updated.csv file in the bot's data folder."
                 " If you do this, make sure to use /refreshpointsfor or /refreshallpoints to apply the changes to player accounts. "
                 "Note that changing point values for items will affect all PPEs with those items, so be cautious when making adjustments."
                 " Additionally, if you are using the sniffer integration, you will need to ensure everyone has the updated CSV locally."
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
                "- /myquests or /myinfo -> Show Quests opens your shared quest menu\n"
                "- Use quest menu actions to view graphics of your progress and reset"
                 " a selection of your own quests up to a specified number of times per season\n"
            ),
            inline=False,
        )
        embed.add_field(name=_divider(), value="\u200b", inline=False)
        embed.add_field(
            name="Admin",
            value=(
                "- /removeseasonlootfrom if targetted to an item which completed a quest will remove"
                 " the quest from the player's completed list\n"
                "- /managequests to edit targets, enable global quest pools, and point settings\n"
                "- /managequests -> Reset All Quests for server-wide resets\n"
                "- /manageplayer -> Show Quests to view/reset a specific player's quests"
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
                "- /myteam to view your team's members and rankings\n"
                "- /leaderboard includes team rankings\n"
            ),
            inline=False,
        )
        embed.add_field(name=_divider(), value="\u200b", inline=False)
        embed.add_field(
            name="Admin",
            value=(
                "- /manageteams to create, rename, delete, and set leaders\n"
                "- /manageteams to open team leaderboard and team member controls\n"
                "- /manageplayer -> Team actions to add/remove players from teams"
                "- /manageseason -> Manage Contests -> Manage Leaderboard to allow"
                 " quests to count for team scores."
            ),
            inline=False,
        )
        embed.set_footer(text=_common_footer())
        return embed

    if section_key == "sniffer":
        embed = discord.Embed(
            title="PPE Bot Help - Sniffer",
            description=(
                "Sniffer integration lets your in-game drops auto-log to PPE or season loot with character-aware "
                 "routing and pending review tools for unmapped characters. Note that you must download the specific"
                 " sniffer client built for this bot. You also must have a CSV of the loot drops in the same folder"
                 " so that the sniffer knows which items to send to the bot."
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Normal Player",
            value=(
                "- /mysniffer opens your sniffer dashboard\n"
                "- Generate/unlink token and open Configure Characters panel\n"
                "- Map character IDs to PPEs or seasonal routing and resolve pending loot"
            ),
            inline=False,
        )
        embed.add_field(name=_divider(), value="\u200b", inline=False)
        embed.add_field(
            name="Admin",
            value=(
                "- /managesniffer to enable/disable sniffer support\n"
                "- Manage tokens, output channel, and player sniffer state\n"
                "- Use reset/revoke actions from admin sniffer panel when needed\n"
                "- Refer to the README.md in the repository for sniffer setup instructions."
            ),
            inline=False,
        )
        embed.set_footer(text=_common_footer())
        return embed

    embed = discord.Embed(
        title="PPE Bot Help - Season Setup",
        description=(
            "Season setup controls global contest configuration including season reset actions, point settings, "
            "and optional screenshot suggestion channels."
        ),
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="Normal Player",
        value=(
            "- /addseasonloot and /removeseasonloot for your global account season collection\n"
            "- /myinfo -> Show Season Loot for list/image views\n"
            "- You can use season tracking without creating a PPE"
        ),
        inline=False,
    )
    embed.add_field(name=_divider(), value="\u200b", inline=False)
    embed.add_field(
        name="Admin",
        value=(
            
            "- /addseasonlootfor and /removeseasonlootfrom for admin season adjustments\n"
            "- /manageseason can adjust the core functionalities and values of the season.\n"
            "- /manageseason -> Picture Suggestions to configure automatic image detection of loot in specified channels.\n"
            "- /manageseason -> Manage Contests to set up and choose default leaderboard."
            "- /manageseason -> Manage Point Settings to adjust point values at scale."
        ),
        inline=False,
    )
    embed.set_footer(text=_common_footer())
    return embed


async def command(interaction: discord.Interaction):
    view = PPEHelpView(owner_id=interaction.user.id)
    embed = build_help_embed("home")
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
