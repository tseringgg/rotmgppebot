#!/usr/bin/env python3
"""
Migration script to normalize apostrophes in player records.

This script converts all curly/smart apostrophes (U+2019, U+2018) 
to regular apostrophes (U+0027) in stored item names.

This ensures consistency with the normalized CSV files and PNG filenames.
"""

import json
import os

PLAYER_RECORD_FILE = "./guild_loot_records.json"


def migrate_apostrophes():
    """
    Read player records and normalize apostrophes in item names.
    """
    
    if not os.path.exists(PLAYER_RECORD_FILE):
        print(f"⚠️  {PLAYER_RECORD_FILE} not found - nothing to migrate.")
        return
    
    print("=== Migrating apostrophes in player records ===\n")
    
    try:
        with open(PLAYER_RECORD_FILE, 'r', encoding='utf-8') as f:
            records = json.load(f)
        
        changes_made = {}
        total_items_fixed = 0
        
        # Process each player's records
        for user_key, player_data in records.items():
            if 'unique_items' not in player_data:
                continue
            
            original_items = player_data['unique_items']
            normalized_items = []
            player_changes = 0
            
            for item in original_items:
                item_name, shiny = item[0], item[1]
                
                # Normalize apostrophes: curly → regular
                original_name = item_name
                normalized_name = item_name.replace('\u2019', "'").replace('\u2018', "'")
                
                if original_name != normalized_name:
                    player_changes += 1
                    total_items_fixed += 1
                    if user_key not in changes_made:
                        changes_made[user_key] = []
                    changes_made[user_key].append(f"{original_name} → {normalized_name}")
                
                normalized_items.append([normalized_name, shiny])
            
            # Update the player's items
            player_data['unique_items'] = normalized_items
        
        # Save the cleaned records back
        with open(PLAYER_RECORD_FILE, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Migration complete!\n")
        print(f"Total items fixed: {total_items_fixed}")
        print(f"Players affected: {len(changes_made)}\n")
        
        if changes_made:
            print("Changes by player:")
            for user_key, items in changes_made.items():
                print(f"  {user_key}:")
                for change in items:
                    print(f"    - {change}")
        else:
            print("✅ No changes needed - all apostrophes already normalized!")
        
    except json.JSONDecodeError as e:
        print(f"❌ Error reading {PLAYER_RECORD_FILE}: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    migrate_apostrophes()
