from __future__ import annotations

from typing import Iterable

import discord

from utils.pagination import LootPaginationView


LEADERBOARD_PAGE_SIZE = 20


def medal_or_rank(rank: int) -> str:
    if rank == 1:
        return "🥇"
    if rank == 2:
        return "🥈"
    if rank == 3:
        return "🥉"
    return f"{rank}."


def build_ranked_entry_lines(rows: Iterable[str], *, start_rank: int = 1) -> list[str]:
    lines: list[str] = []
    for offset, row in enumerate(rows):
        rank = start_rank + offset
        lines.append(f"{medal_or_rank(rank)} {row}")
    return lines


def build_leaderboard_embeds(
    *,
    title: str,
    entries: list[str],
    color: discord.Color,
    header_lines: list[str] | None = None,
    empty_message: str = "No data available yet.",
    per_page: int = LEADERBOARD_PAGE_SIZE,
) -> list[discord.Embed]:
    if not entries:
        return [
            discord.Embed(
                title=title,
                description=empty_message,
                color=color,
            )
        ]

    pages: list[list[str]] = []
    for index in range(0, len(entries), per_page):
        pages.append(entries[index:index + per_page])

    embeds: list[discord.Embed] = []
    page_total = len(pages)
    header = header_lines or []
    for page_number, page_entries in enumerate(pages, start=1):
        description_lines: list[str] = []
        if header:
            description_lines.extend(header)
            description_lines.append("")
        description_lines.extend(page_entries)

        embed = discord.Embed(
            title=title,
            description="\n".join(description_lines),
            color=color,
        )
        if page_total > 1:
            embed.set_footer(text=f"Page {page_number}/{page_total}")
        embeds.append(embed)

    return embeds


async def send_leaderboard(
    interaction: discord.Interaction,
    *,
    title: str,
    entries: list[str],
    color: discord.Color,
    header_lines: list[str] | None = None,
    empty_message: str = "No data available yet.",
    per_page: int = LEADERBOARD_PAGE_SIZE,
) -> None:
    if not entries:
        empty_embed = discord.Embed(
            title=title,
            description=empty_message,
            color=color,
        )
        if interaction.response.is_done():
            await interaction.followup.send(embed=empty_embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=empty_embed, ephemeral=True)
        return

    embeds = build_leaderboard_embeds(
        title=title,
        entries=entries,
        color=color,
        header_lines=header_lines,
        empty_message=empty_message,
        per_page=per_page,
    )
    if len(embeds) == 1:
        await interaction.response.send_message(embed=embeds[0])
        return

    view = LootPaginationView(embeds=embeds, user_id=interaction.user.id)
    await interaction.response.send_message(embed=embeds[0], view=view)


async def send_error_response(interaction: discord.Interaction, message: str) -> None:
    """Safely send an ephemeral error regardless of response state."""
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
        return
    await interaction.response.send_message(message, ephemeral=True)
