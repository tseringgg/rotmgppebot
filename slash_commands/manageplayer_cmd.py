import discord

from menus.manageplayer import open_manageplayer_menu


async def command(
    interaction: discord.Interaction,
    member: discord.Member | None = None,
    user_id: str | None = None,
) -> None:
    await open_manageplayer_menu(interaction, member=member, user_id=user_id)
