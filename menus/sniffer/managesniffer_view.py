"""Views and embeds for the admin-facing /managesniffer menu."""

from __future__ import annotations

from typing import Any

import discord

from menus.menu_utils import OwnerBoundView
from menus.sniffer.common import (
    build_realmshark_link_instructions,
    generate_link_token_for_user,
    iter_user_links,
    linked_character_counts,
    load_sniffer_settings,
    mention_for_channel,
    reset_all_sniffer_settings,
    reset_output_channel,
    revoke_all_tokens_for_user,
    revoke_token,
    set_output_channel,
    set_sniffer_enabled,
    sniffer_connected_user_count,
    token_preview,
)
from menus.sniffer.mysniffer_view import build_mysniffer_home_embed
from slash_commands import realmshark_cmd


def _resolve_member(guild: discord.Guild | None, user_id: int) -> discord.Member | None:
    if guild is None:
        return None
    return guild.get_member(int(user_id))


def build_managesniffer_home_embed(
    *,
    guild: discord.Guild | None,
    settings: dict[str, Any],
    links: dict[str, dict[str, Any]],
) -> discord.Embed:
    enabled = bool(settings.get("enabled", False))
    channel_id = int(settings.get("announce_channel_id", 0) or 0)
    connected_users = sniffer_connected_user_count(links)

    embed = discord.Embed(
        title="Manage Sniffer",
        description="Admin controls for sniffer integration and token management.",
        color=discord.Color.green() if enabled else discord.Color.orange(),
    )
    embed.add_field(name="Sniffer Enabled", value="Yes" if enabled else "No", inline=True)
    embed.add_field(name="Linked Tokens", value=str(len(links)), inline=True)
    embed.add_field(name="Connected Players", value=str(connected_users), inline=True)
    embed.add_field(name="Output Channel", value=mention_for_channel(guild, channel_id), inline=False)

    if not enabled:
        embed.add_field(
            name="Enable Sniffer",
            value="Sniffer is disabled. Use the green **Enable Sniffer** button below to turn it on.",
            inline=False,
        )
    else:
        embed.add_field(
            name="Admin Actions",
            value=(
                "Use the buttons below to manage player links, inspect and revoke tokens, "
                "set output channel, or reset all sniffer settings."
            ),
            inline=False,
        )

    embed.set_footer(text="This menu is admin-only.")
    return embed


def build_manage_player_sniffer_embed(
    *,
    target_user: discord.abc.User,
    settings: dict[str, Any],
    links: dict[str, dict[str, Any]],
) -> discord.Embed:
    user_links = iter_user_links(links, target_user.id)
    mapped_count, seasonal_count = linked_character_counts(user_links)

    embed = build_mysniffer_home_embed(user=target_user, settings=settings, user_links=user_links)
    embed.title = f"Manage Player Sniffer - {target_user.display_name}"
    embed.description = "Admin view of this player's /mysniffer dashboard."
    embed.add_field(name="Player ID", value=str(target_user.id), inline=True)
    embed.add_field(name="Player Mention", value=getattr(target_user, "mention", str(target_user.id)), inline=True)
    embed.add_field(name="Linked Tokens", value=str(len(user_links)), inline=True)
    embed.add_field(name="Mapped Characters", value=str(mapped_count), inline=True)
    embed.add_field(name="Seasonal Characters", value=str(seasonal_count), inline=True)
    embed.set_footer(text="Use these controls to manage this player's sniffer state.")
    return embed


def build_tokens_embed(
    *,
    guild: discord.Guild | None,
    page: int,
    per_page: int,
    token_entries: list[tuple[str, dict[str, Any]]],
) -> discord.Embed:
    total = len(token_entries)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))

    start = page * per_page
    end = start + per_page
    window = token_entries[start:end]

    embed = discord.Embed(
        title="Manage Sniffer Tokens",
        description="Review and revoke active sniffer link tokens.",
        color=discord.Color.blurple(),
    )

    if not window:
        embed.add_field(name="Tokens", value="No linked tokens found.", inline=False)
    else:
        lines: list[str] = []
        for token, link_data in window:
            user_id = link_data.get("user_id", "unknown")
            owner_text = str(user_id)
            try:
                parsed_user_id = int(user_id)
                member = _resolve_member(guild, parsed_user_id)
                if member is not None:
                    owner_text = f"{member.display_name} ({member.mention})"
            except (TypeError, ValueError):
                pass

            lines.append(
                f"- `{token_preview(token)}` | owner: {owner_text} | "
                f"created: `{link_data.get('created_at', '')}` | last_used: `{link_data.get('last_used_at', '')}`"
            )

        embed.add_field(name="Active Tokens", value="\n".join(lines), inline=False)

    embed.set_footer(text=f"Page {page + 1}/{total_pages} - total tokens: {total}")
    return embed


class _DeleteTokenSelect(discord.ui.Select):
    def __init__(self, owner_id: int, token_window: list[tuple[str, dict[str, Any]]]) -> None:
        options = [
            discord.SelectOption(label=token_preview(token), value=token, description="Delete token")
            for token, _ in token_window[:25]
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
            await interaction.response.send_message("This picker belongs to another admin.", ephemeral=True)
            return

        token = self.values[0]
        deleted = await revoke_token(interaction, token)
        if deleted:
            await interaction.response.edit_message(content="✅ Token revoked.", embed=None, view=None)
        else:
            await interaction.response.edit_message(content="Token was already removed.", embed=None, view=None)


class TokenDeletePickerView(OwnerBoundView):
    def __init__(self, owner_id: int, token_window: list[tuple[str, dict[str, Any]]]) -> None:
        super().__init__(owner_id=owner_id, timeout=180, owner_error="This picker belongs to another admin.")
        self.add_item(_DeleteTokenSelect(owner_id, token_window))


class _ManageSnifferPlayerPicker(discord.ui.UserSelect):
    def __init__(self, owner_id: int) -> None:
        super().__init__(
            placeholder="Select a player to manage",
            min_values=1,
            max_values=1,
        )
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This picker belongs to another admin.", ephemeral=True)
            return

        if not self.values:
            await interaction.response.send_message("Please select a user.", ephemeral=True)
            return

        target_user = self.values[0]
        await render_manage_player_sniffer_home(
            interaction,
            owner_id=self.owner_id,
            target_user_id=int(target_user.id),
        )


class ManageSnifferPlayerPickerView(OwnerBoundView):
    def __init__(self, owner_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=300, owner_error="This picker belongs to another admin.")
        self.add_item(_ManageSnifferPlayerPicker(owner_id))

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await render_managesniffer_home(interaction, owner_id=self.owner_id)


class _OutputChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, owner_id: int) -> None:
        super().__init__(
            placeholder="Select output channel",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
        )
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This picker belongs to another admin.", ephemeral=True)
            return

        if not self.values:
            await interaction.response.send_message("Please select a text channel.", ephemeral=True)
            return

        selected = self.values[0]
        channel_id = int(getattr(selected, "id", 0) or 0)
        if channel_id <= 0:
            await interaction.response.send_message("Invalid channel selection.", ephemeral=True)
            return

        await set_output_channel(interaction, channel_id)
        await render_output_channel_view(interaction, owner_id=self.owner_id)


class ManageSnifferOutputChannelView(OwnerBoundView):
    def __init__(self, owner_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=300, owner_error="This menu belongs to another admin.")
        self.add_item(_OutputChannelSelect(owner_id))

    @discord.ui.button(label="Reset To Default", style=discord.ButtonStyle.secondary)
    async def reset_default(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await reset_output_channel(interaction)
        await render_output_channel_view(interaction, owner_id=self.owner_id)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await render_managesniffer_home(interaction, owner_id=self.owner_id)


class ManagePlayerSnifferView(OwnerBoundView):
    def __init__(self, owner_id: int, target_user_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This panel belongs to another admin.")
        self.target_user_id = int(target_user_id)

    async def _target_user(self, interaction: discord.Interaction) -> discord.abc.User | None:
        if interaction.guild is None:
            return None
        return interaction.guild.get_member(self.target_user_id)

    @discord.ui.button(label="Generate Token", style=discord.ButtonStyle.success)
    async def generate_token(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        target_user = await self._target_user(interaction)
        if target_user is None:
            await interaction.response.send_message("Player is no longer in this server.", ephemeral=True)
            return

        token = await generate_link_token_for_user(interaction, self.target_user_id)
        await render_manage_player_sniffer_home(
            interaction,
            owner_id=self.owner_id,
            target_user_id=self.target_user_id,
        )
        await interaction.followup.send(
            "Generated token for selected player:\n"
            + build_realmshark_link_instructions(interaction.guild.id if interaction.guild else None, token),
            ephemeral=True,
        )

    @discord.ui.button(label="Unlink Sniffer", style=discord.ButtonStyle.danger)
    async def unlink(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        revoked = await revoke_all_tokens_for_user(interaction, self.target_user_id)
        await render_manage_player_sniffer_home(
            interaction,
            owner_id=self.owner_id,
            target_user_id=self.target_user_id,
        )
        await interaction.followup.send(f"Revoked `{revoked}` token(s) for this player.", ephemeral=True)

    @discord.ui.button(label="Configure Characters", style=discord.ButtonStyle.primary)
    async def configure(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        target_member = _resolve_member(interaction.guild, self.target_user_id)
        if target_member is None:
            await interaction.response.send_message("Player is no longer in this server.", ephemeral=True)
            return
        await realmshark_cmd.admin_panel(interaction, target_member, "show_all")

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await render_managesniffer_home(interaction, owner_id=self.owner_id)


class ManageSnifferTokensView(OwnerBoundView):
    def __init__(self, owner_id: int, page: int = 0) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another admin.")
        self.page = page
        self.per_page = 8

    async def _entries(self, interaction: discord.Interaction) -> list[tuple[str, dict[str, Any]]]:
        _settings, links = await load_sniffer_settings(interaction)
        return sorted(links.items(), key=lambda pair: pair[0])

    async def _render(self, interaction: discord.Interaction) -> None:
        entries = await self._entries(interaction)
        total_pages = max(1, (len(entries) + self.per_page - 1) // self.per_page)
        self.page = max(0, min(self.page, total_pages - 1))
        embed = build_tokens_embed(
            guild=interaction.guild,
            page=self.page,
            per_page=self.per_page,
            token_entries=entries,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        entries = await self._entries(interaction)
        total_pages = max(1, (len(entries) + self.per_page - 1) // self.per_page)
        self.page = (self.page - 1) % total_pages
        await self._render(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        entries = await self._entries(interaction)
        total_pages = max(1, (len(entries) + self.per_page - 1) // self.per_page)
        self.page = (self.page + 1) % total_pages
        await self._render(interaction)

    @discord.ui.button(label="Delete Token", style=discord.ButtonStyle.danger)
    async def delete_token_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        entries = await self._entries(interaction)
        if not entries:
            await interaction.response.send_message("No tokens to delete.", ephemeral=True)
            return

        start = self.page * self.per_page
        window = entries[start:start + self.per_page]
        await interaction.response.send_message(
            "Select a token to revoke from this page.",
            view=TokenDeletePickerView(self.owner_id, window),
            ephemeral=True,
        )

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.primary)
    async def refresh(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._render(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await render_managesniffer_home(interaction, owner_id=self.owner_id)


class ManageSnifferHomeView(OwnerBoundView):
    def __init__(self, owner_id: int, *, enabled: bool) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another admin.")
        self.enabled = enabled

        if enabled:
            self.remove_item(self.enable_sniffer)
        else:
            self.remove_item(self.disable_sniffer)

    @discord.ui.button(label="Enable Sniffer", style=discord.ButtonStyle.success, row=0)
    async def enable_sniffer(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await set_sniffer_enabled(interaction, True)
        await render_managesniffer_home(interaction, owner_id=self.owner_id)

    @discord.ui.button(label="Manage Player's Sniffer", style=discord.ButtonStyle.primary, row=0)
    async def manage_player(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        embed = discord.Embed(
            title="Select Player",
            description="Pick a player to open their sniffer management panel.",
            color=discord.Color.blurple(),
        )
        await interaction.response.edit_message(embed=embed, view=ManageSnifferPlayerPickerView(self.owner_id))

    @discord.ui.button(label="Manage Tokens", style=discord.ButtonStyle.primary, row=1)
    async def manage_tokens(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings, links = await load_sniffer_settings(interaction)
        view = ManageSnifferTokensView(self.owner_id, page=0)
        embed = build_tokens_embed(
            guild=interaction.guild,
            page=0,
            per_page=view.per_page,
            token_entries=sorted(links.items(), key=lambda pair: pair[0]),
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Change Output Channel", style=discord.ButtonStyle.primary, row=1)
    async def change_output_channel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await render_output_channel_view(interaction, owner_id=self.owner_id)

    @discord.ui.button(label="Reset All Sniffer Settings", style=discord.ButtonStyle.danger, row=2)
    async def reset_all(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        summary = await reset_all_sniffer_settings(interaction)
        await render_managesniffer_home(interaction, owner_id=self.owner_id)
        await interaction.followup.send(
            "Reset all sniffer data for this guild.\n"
            f"enabled: `{summary['enabled']}`\n"
            f"mode: `{summary['mode']}`\n"
            f"announce_channel_id: `{summary['announce_channel_id']}`\n"
            f"link_count: `{summary['link_count']}`\n"
            f"revoked_links: `{summary['revoked_links']}`\n"
            f"pending_files_removed: `{summary['pending_files_removed']}`",
            ephemeral=True,
        )

    @discord.ui.button(label="Disable Sniffer", style=discord.ButtonStyle.danger, row=2)
    async def disable_sniffer(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await set_sniffer_enabled(interaction, False)
        await render_managesniffer_home(interaction, owner_id=self.owner_id)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, row=3)
    async def refresh(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await render_managesniffer_home(interaction, owner_id=self.owner_id)


async def render_managesniffer_home(interaction: discord.Interaction, *, owner_id: int) -> None:
    settings, links = await load_sniffer_settings(interaction)
    enabled = bool(settings.get("enabled", False))

    embed = build_managesniffer_home_embed(guild=interaction.guild, settings=settings, links=links)
    view = ManageSnifferHomeView(owner_id=owner_id, enabled=enabled)
    await interaction.response.edit_message(embed=embed, view=view)


async def send_managesniffer_home(interaction: discord.Interaction) -> None:
    settings, links = await load_sniffer_settings(interaction)
    enabled = bool(settings.get("enabled", False))

    embed = build_managesniffer_home_embed(guild=interaction.guild, settings=settings, links=links)
    view = ManageSnifferHomeView(owner_id=interaction.user.id, enabled=enabled)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def render_manage_player_sniffer_home(
    interaction: discord.Interaction,
    *,
    owner_id: int,
    target_user_id: int,
) -> None:
    target_user = _resolve_member(interaction.guild, target_user_id)
    if target_user is None:
        await interaction.response.edit_message(
            content="Player is no longer in this server.",
            embed=None,
            view=ManageSnifferPlayerPickerView(owner_id),
        )
        return

    settings, links = await load_sniffer_settings(interaction)
    embed = build_manage_player_sniffer_embed(target_user=target_user, settings=settings, links=links)
    view = ManagePlayerSnifferView(owner_id=owner_id, target_user_id=target_user_id)
    await interaction.response.edit_message(embed=embed, view=view)


async def render_output_channel_view(interaction: discord.Interaction, *, owner_id: int) -> None:
    settings, _links = await load_sniffer_settings(interaction)
    channel_id = int(settings.get("announce_channel_id", 0) or 0)

    embed = discord.Embed(
        title="Sniffer Output Channel",
        description="Choose a text channel for sniffer announcements, or reset to default.",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Current Channel", value=mention_for_channel(interaction.guild, channel_id), inline=False)

    view = ManageSnifferOutputChannelView(owner_id=owner_id)
    await interaction.response.edit_message(embed=embed, view=view)
