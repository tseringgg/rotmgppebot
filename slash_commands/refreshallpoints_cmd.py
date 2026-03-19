import discord
from utils.player_records import load_player_records, save_player_records
from utils.embed_builders import calculate_item_points
from utils.calc_points import load_loot_points, normalize_item_name
from utils.pagination import chunk_lines_to_pages

async def command(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")

    # This command can take longer than Discord's initial interaction timeout.
    await interaction.response.defer(thinking=True)
    
    # Load player records and loot data
    records = await load_player_records(interaction)
    loot_points = load_loot_points()
    
    total_ppes_processed = 0
    total_corrections = 0
    correction_summary = []
    # Track invalid removals as: {player_name: {item_label: {"total_quantity": int, "characters": [str]}}}
    removed_items_by_player = {}
    # Track invalid unique-item removals as: {player_name: [item_label, ...]}
    removed_unique_items_by_player = {}
    
    # Iterate through all players
    for player_key, player_data in records.items():
        if not player_data.ppes:
            # Still clean invalid season cache entries even if player has no PPEs.
            invalid_unique_items = []
            for item_name, shiny in list(player_data.unique_items):
                lookup_name = f"{normalize_item_name(item_name)} (shiny)" if shiny else normalize_item_name(item_name)
                if lookup_name not in loot_points:
                    invalid_unique_items.append((item_name, shiny))

            if invalid_unique_items:
                try:
                    member = interaction.guild.get_member(int(player_key))
                    player_name = member.display_name if member else f"User {player_key}"
                except:
                    player_name = f"User {player_key}"

                removed_unique_items_by_player.setdefault(player_name, [])
                for item_name, shiny in invalid_unique_items:
                    player_data.unique_items.discard((item_name, shiny))
                    item_label = f"{item_name}{' (shiny)' if shiny else ''}"
                    removed_unique_items_by_player[player_name].append(item_label)
            continue
            
        # Process each PPE for this player
        for ppe in player_data.ppes:
            total_ppes_processed += 1
            
            # Store old points for comparison
            old_points = ppe.points
            
            # Validate and remove invalid items
            valid_loot = []
            for loot_item in ppe.loot:
                # Check if item exists in loot_points
                if loot_item.shiny:
                    lookup_name = f"{normalize_item_name(loot_item.item_name)} (shiny)"
                else:
                    lookup_name = normalize_item_name(loot_item.item_name)
                
                if lookup_name not in loot_points:
                    # Item is invalid, flag it for removal
                    try:
                        member = interaction.guild.get_member(int(player_key))
                        player_name = member.display_name if member else f"User {player_key}"
                    except:
                        player_name = f"User {player_key}"

                    item_label = f"{loot_item.item_name}{' (shiny)' if loot_item.shiny else ''}{' (divine)' if loot_item.divine else ''}"
                    player_summary = removed_items_by_player.setdefault(player_name, {})
                    item_summary = player_summary.setdefault(
                        item_label,
                        {"total_quantity": 0, "characters": []}
                    )

                    item_summary["total_quantity"] += loot_item.quantity
                    item_summary["characters"].append(
                        f"PPE #{ppe.id} ({ppe.name}) x{loot_item.quantity}"
                    )
                else:
                    valid_loot.append(loot_item)
            
            # Update the loot list with only valid items
            ppe.loot = valid_loot
            
            # Recalculate points from loot
            total_loot_points = 0.0
            for loot_item in ppe.loot:
                item_points = calculate_item_points(
                    loot_item.item_name, 
                    loot_item.divine, 
                    loot_item.shiny, 
                    loot_item.quantity
                )
                total_loot_points += item_points
            
            # Recalculate points from bonuses
            total_bonus_points = 0.0
            for bonus in ppe.bonuses:
                bonus_points = bonus.points * bonus.quantity
                total_bonus_points += bonus_points
            
            # Set the corrected total
            corrected_total = total_loot_points + total_bonus_points
            ppe.points = corrected_total
            
            # Track corrections
            point_difference = corrected_total - old_points
            if abs(point_difference) > 0.01:  # Only count meaningful differences
                total_corrections += 1
                # Try to get player name from Discord
                try:
                    member = interaction.guild.get_member(int(player_key))
                    player_name = member.display_name if member else f"User {player_key}"
                except:
                    player_name = f"User {player_key}"
                
                correction_summary.append(
                    f"• {player_name} - PPE #{ppe.id} ({ppe.name}): "
                    f"{old_points:.1f} → {corrected_total:.1f} "
                    f"({point_difference:+.1f})"
                )

        # Clean invalid season cache entries for this player as well.
        invalid_unique_items = []
        for item_name, shiny in list(player_data.unique_items):
            lookup_name = f"{normalize_item_name(item_name)} (shiny)" if shiny else normalize_item_name(item_name)
            if lookup_name not in loot_points:
                invalid_unique_items.append((item_name, shiny))

        if invalid_unique_items:
            try:
                member = interaction.guild.get_member(int(player_key))
                player_name = member.display_name if member else f"User {player_key}"
            except:
                player_name = f"User {player_key}"

            removed_unique_items_by_player.setdefault(player_name, [])
            for item_name, shiny in invalid_unique_items:
                player_data.unique_items.discard((item_name, shiny))
                item_label = f"{item_name}{' (shiny)' if shiny else ''}"
                removed_unique_items_by_player[player_name].append(item_label)
    
    # Save all records
    await save_player_records(interaction=interaction, records=records)
    
    # Build response message with pagination
    response_lines = [f"✅ **Refresh Complete!**", ""]
    response_lines.append(f"Processed **{total_ppes_processed} PPEs**")
    response_lines.append(f"Made **{total_corrections} corrections**")
    
    if removed_items_by_player:
        response_lines.append("")
        total_removed_quantity = sum(
            item_data["total_quantity"]
            for player_data in removed_items_by_player.values()
            for item_data in player_data.values()
        )
        response_lines.append(f"**Removed Invalid Items ({total_removed_quantity} total):**")

        for player_name in sorted(removed_items_by_player.keys()):
            player_data = removed_items_by_player[player_name]
            player_total = sum(item_data["total_quantity"] for item_data in player_data.values())
            response_lines.append(f"• **{player_name}** - removed **{player_total}** invalid item(s):")

            for item_label in sorted(player_data.keys()):
                item_data = player_data[item_label]
                character_breakdown = "; ".join(item_data["characters"])
                response_lines.append(
                    f"  - **{item_label}** x{item_data['total_quantity']} from: {character_breakdown}"
                )
    
    if correction_summary:
        response_lines.append("")
        response_lines.append(f"**Point Corrections Made:**")
        response_lines.extend(correction_summary)

    if removed_unique_items_by_player:
        response_lines.append("")
        total_removed_unique = sum(len(items) for items in removed_unique_items_by_player.values())
        response_lines.append(f"**Removed Invalid Season Items ({total_removed_unique} total):**")

        for player_name in sorted(removed_unique_items_by_player.keys()):
            items = sorted(removed_unique_items_by_player[player_name])
            preview = ", ".join(items[:5])
            if len(items) > 5:
                preview += f" (+{len(items) - 5} more)"
            response_lines.append(f"• **{player_name}**: {preview}")
    
    # Split into pages if necessary
    pages = chunk_lines_to_pages(response_lines, 1900)
    
    if len(pages) == 1:
        await interaction.followup.send("\n".join(pages[0]))
    else:
        # Send first page with footer, then additional pages
        first_message = "\n".join(pages[0]) + f"\n\n*[Part 1 of {len(pages)}]*"
        await interaction.followup.send(first_message)
        
        for i, page in enumerate(pages[1:], start=2):
            page_text = "\n".join(page) + f"\n\n*[Part {i} of {len(pages)}]*"
            await interaction.followup.send(page_text)