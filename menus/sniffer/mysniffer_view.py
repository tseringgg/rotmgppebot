"""Views and embeds for the player-facing /mysniffer menu."""

from __future__ import annotations

from typing import Any

import discord

from menus.menu_utils import OwnerBoundView
from menus.sniffer.common import (
    build_realmshark_link_instructions,
    build_setup_steps,
    generate_link_token_for_user,
    iter_user_links,
    linked_character_counts,
    load_sniffer_settings,
    revoke_token,
    token_preview,
)
from slash_commands import realmshark_cmd


def build_mysniffer_home_embed(
    *,
    user: discord.abc.User,
    settings: dict[str, Any],
    user_links: list[tuple[str, dict[str, Any]]],
) -> discord.Embed:
    enabled = bool(settings.get("enabled", False))
    mapped_count, seasonal_count = linked_character_counts(user_links)

    embed = discord.Embed(
        title=f"My Sniffer - {user.display_name}",
        description="Manage your sniffer connection and character routing.",
        color=discord.Color.teal() if enabled else discord.Color.orange(),
    )

    embed.add_field(name="Sniffer Enabled", value="Yes" if enabled else "No", inline=True)
    embed.add_field(name="Linked Tokens", value=str(len(user_links)), inline=True)
    embed.add_field(name="Mapped Characters", value=str(mapped_count), inline=True)
    embed.add_field(name="Seasonal Characters", value=str(seasonal_count), inline=True)

    if enabled:
        embed.add_field(name="Setup Steps", value=build_setup_steps(), inline=False)
    else:
        embed.add_field(
            name="Status",
            value="Sniffer is currently disabled on this server. Ask a PPE Admin to enable it in `/managesniffer`.",
            inline=False,
        )

    if user_links:
        token_lines = [f"- `{token_preview(token)}`" for token, _ in user_links[:10]]
        embed.add_field(name="Your Active Tokens", value="\n".join(token_lines), inline=False)

    embed.set_footer(text="Use the buttons below to generate, unlink, or configure your sniffer.")
    return embed


class _UnlinkTokenSelect(discord.ui.Select):
    def __init__(self, owner_id: int, tokens: list[str]) -> None:
        options = [
            discord.SelectOption(label=token_preview(token), value=token, description="Revoke this token")
            for token in tokens[:25]
        ]
        super().__init__(
            placeholder="Select a token to revoke",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This picker belongs to another user.", ephemeral=True)
            return

        token = self.values[0]
        revoked = await revoke_token(interaction, token)
        if revoked:
            await interaction.response.edit_message(content="✅ Sniffer token revoked.", embed=None, view=None)
        else:
            await interaction.response.edit_message(content="Token was already removed.", embed=None, view=None)


class UnlinkTokenView(OwnerBoundView):
    def __init__(self, owner_id: int, tokens: list[str]) -> None:
        super().__init__(owner_id=owner_id, timeout=180, owner_error="This unlink menu belongs to another user.")
        self.add_item(_UnlinkTokenSelect(owner_id, tokens))


class MySnifferHomeView(OwnerBoundView):
    def __init__(self, owner_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")

    async def _refresh_home(self, interaction: discord.Interaction) -> None:
        settings, links = await load_sniffer_settings(interaction)
        user_links = iter_user_links(links, interaction.user.id)
        embed = build_mysniffer_home_embed(user=interaction.user, settings=settings, user_links=user_links)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Generate Token", style=discord.ButtonStyle.success)
    async def generate_token(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings, _links = await load_sniffer_settings(interaction)
        if not bool(settings.get("enabled", False)):
            await interaction.response.send_message(
                "Sniffer is disabled for this server. Ask an admin to enable it in `/managesniffer`.",
                ephemeral=True,
            )
            return

        token = await generate_link_token_for_user(interaction, interaction.user.id)
        await self._refresh_home(interaction)
        await interaction.followup.send(
            build_realmshark_link_instructions(interaction.guild.id if interaction.guild else None, token),
            ephemeral=True,
        )

    @discord.ui.button(label="Unlink Sniffer", style=discord.ButtonStyle.danger)
    async def unlink_sniffer(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        _settings, links = await load_sniffer_settings(interaction)
        user_links = iter_user_links(links, interaction.user.id)
        if not user_links:
            await interaction.response.send_message("You do not have any linked sniffer tokens.", ephemeral=True)
            return

        tokens = [token for token, _ in user_links]
        await interaction.response.send_message(
            "Pick which token to unlink.",
            view=UnlinkTokenView(interaction.user.id, tokens),
            ephemeral=True,
        )

    @discord.ui.button(label="Configure Characters", style=discord.ButtonStyle.primary)
    async def configure_characters(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings, _links = await load_sniffer_settings(interaction)
        if not bool(settings.get("enabled", False)):
            await interaction.response.send_message(
                "Sniffer is disabled for this server. Ask an admin to enable it in `/managesniffer`.",
                ephemeral=True,
            )
            return

        await realmshark_cmd.open_panel(interaction, "show_all")

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._refresh_home(interaction)
