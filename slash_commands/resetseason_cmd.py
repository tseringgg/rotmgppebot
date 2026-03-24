import discord
from utils.guild_config import get_realmshark_settings, set_realmshark_settings
from utils.player_records import load_player_records, save_player_records, load_teams, save_teams
from utils.realmshark_pending_store import clear_all_pending_for_guild
from utils.guild_config import load_guild_config


class ConfirmView(discord.ui.View):
    def __init__(self, timeout=60):
        super().__init__(timeout=timeout)
        self.confirmed = False
    
    @discord.ui.button(label="Confirm Reset", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        await interaction.response.defer()
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        await interaction.response.defer()
        self.stop()


async def command(interaction: discord.Interaction, clear_realmshark_links: bool = False):
    """
    Reset the season by clearing all unique items and quest data for all players,
    deleting all teams, and resetting RealmShark integration state.
    Retains player member status and PPE roles.
    Admin only.
    """
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
    
    try:
        # Ask for confirmation
        view = ConfirmView()
        reset_mode_line = (
            "WARNING: This will unlink all RealmShark integrations and clear all character mappings."
            if clear_realmshark_links
            else "RealmShark links will be kept. Existing PPE character mappings will be converted to seasonal mappings."
        )
        await interaction.response.send_message(
            "⚠️ **Are you sure you want to reset the season?**\n"
            "This will clear all unique items and quest data for all players, delete all teams, and reset RealmShark season state.\n"
            f"{reset_mode_line}\n"
            "Member status and PPE roles will be preserved.",
            view=view,
            ephemeral=True
        )
        
        # Wait for user response
        await view.wait()
        
        if not view.confirmed:
            await interaction.followup.send("❌ Season reset cancelled.", ephemeral=True)
            return
        
        records = await load_player_records(interaction)
        config = await load_guild_config(interaction)
        default_reset_limit = config["quest_settings"]["num_resets"]
        teams = await load_teams(interaction)
        
        # Get team role names before clearing teams
        team_names = set(teams.keys())
        
        # Clear all PPE characters and unique items for all players
        items_cleared = 0
        ppes_cleared = 0
        quest_entries_cleared = 0
        for player_data in records.values():
            # Clear all PPE characters
            ppes_cleared += len(player_data.ppes)
            player_data.ppes.clear()
            player_data.active_ppe = None
            
            # Clear unique items
            if len(player_data.unique_items) > 0:
                items_cleared += len(player_data.unique_items)
                player_data.unique_items.clear()

            # Clear all quest data
            quest_entries_cleared += len(player_data.quests.current_items)
            quest_entries_cleared += len(player_data.quests.current_shinies)
            quest_entries_cleared += len(player_data.quests.current_skins)
            quest_entries_cleared += len(player_data.quests.completed_items)
            quest_entries_cleared += len(player_data.quests.completed_shinies)
            quest_entries_cleared += len(player_data.quests.completed_skins)
            player_data.quests.current_items.clear()
            player_data.quests.current_shinies.clear()
            player_data.quests.current_skins.clear()
            player_data.quests.completed_items.clear()
            player_data.quests.completed_shinies.clear()
            player_data.quests.completed_skins.clear()
            player_data.quest_resets_remaining = default_reset_limit
            
            # Clear team associations
            player_data.team_name = None
        
        # Save the updated records
        await save_player_records(interaction, records)
        
        # Delete all teams from data
        teams_deleted = len(teams)
        teams.clear()
        await save_teams(interaction, teams)

        # Reset RealmShark pending state for new season.
        pending_files_cleared = await clear_all_pending_for_guild(interaction.guild.id)

        # Reset RealmShark state according to selected mode.
        realmshark_settings = await get_realmshark_settings(interaction)
        realmshark_links = realmshark_settings.get("links", {}) if isinstance(realmshark_settings.get("links"), dict) else {}
        realmshark_links_cleared = len(realmshark_links)

        realmshark_summary = ""
        if clear_realmshark_links:
            await set_realmshark_settings(
                interaction,
                {
                    "enabled": False,
                    "mode": "addloot",
                    "links": {},
                    "announce_channel_id": 0,
                },
            )
            realmshark_summary = (
                f"**RealmShark:** Fully reset, revoked {realmshark_links_cleared} link tokens, "
                f"and removed {pending_files_cleared} pending file(s)"
            )
        else:
            converted_bindings = 0
            tokens_updated = 0

            migrated_links = {}
            for token, link_data in realmshark_links.items():
                if not isinstance(link_data, dict):
                    continue

                raw_bindings = link_data.get("character_bindings", {})
                bindings = raw_bindings if isinstance(raw_bindings, dict) else {}
                seasonal_raw = link_data.get("seasonal_character_ids", [])
                seasonal_ids: set[str] = set()
                if isinstance(seasonal_raw, list):
                    for value in seasonal_raw:
                        try:
                            parsed = int(value)
                        except (TypeError, ValueError):
                            continue
                        if parsed > 0:
                            seasonal_ids.add(str(parsed))

                binding_ids: list[str] = []
                for character_id in bindings.keys():
                    try:
                        parsed = int(character_id)
                    except (TypeError, ValueError):
                        continue
                    if parsed > 0:
                        binding_ids.append(str(parsed))

                if binding_ids:
                    converted_bindings += len(binding_ids)
                    seasonal_ids.update(binding_ids)
                    link_data["character_bindings"] = {}
                    link_data["seasonal_character_ids"] = sorted(seasonal_ids, key=int)
                    tokens_updated += 1

                migrated_links[token] = link_data

            await set_realmshark_settings(
                interaction,
                {
                    "enabled": bool(realmshark_settings.get("enabled", False)),
                    "mode": "addloot",
                    "links": migrated_links,
                    "announce_channel_id": (
                        int(realmshark_settings.get("announce_channel_id", 0) or 0)
                        if str(realmshark_settings.get("announce_channel_id", 0) or "0").lstrip("-").isdigit()
                        else 0
                    ),
                },
            )

            realmshark_summary = (
                f"**RealmShark:** Kept {realmshark_links_cleared} link token(s), converted {converted_bindings} PPE mapping(s) "
                f"to seasonal across {tokens_updated} token(s), and removed {pending_files_cleared} pending file(s)"
            )
        
        # Delete team roles using the actual team names we had
        for team_name in team_names:
            try:
                team_role = discord.utils.get(interaction.guild.roles, name=team_name)
                if team_role and not team_role.managed:
                    await team_role.delete(reason="Season reset - team cleanup")
            except Exception:
                print(f"Failed to delete role for team '{team_name}'. It may have already been deleted or does not exist.")
                pass  # Silently ignore any role deletion errors
        
        await interaction.followup.send(
            f"✅ Season reset complete!\n"
            f"**Cleared:** {ppes_cleared} PPE characters, {items_cleared} unique items, {quest_entries_cleared} quest entries\n"
            f"**Deleted:** {teams_deleted} teams and their roles\n"
            f"{realmshark_summary}\n"
            f"**Reset quest attempts to:** {default_reset_limit}\n"
            f"**Preserved:** Player member status and PPE roles",
            ephemeral=False
        )
        
    except (ValueError, KeyError) as e:
        return await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
