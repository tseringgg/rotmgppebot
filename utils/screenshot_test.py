

from find_items import find_items_in_image

# file_path = "./downloads/merlot2.png"
# dungeon = "Wine Cellar"

# dungeon = "Oryx's Chamber"

file_path = "./downloads/broken.png"
dungeon = "Mountain Temple"


# file_path = "./downloads/screenshot.png"
# dungeon = "Ice Citadel"


# file_path = "./downloads/doublewhite.png"
# dungeon = "Oryx's Sanctuary"

# file_path = "./downloads/bone.png"
# dungeon = "Manor of the Immortals"

found_items = find_items_in_image(file_path, templates_folder=f"./helper_pics/dungeon_pics/{dungeon}")
if found_items:
    # player_name = str(interaction.user.display_name)
    # loot_results, total = await calculate_loot_points(interaction.guild.id, player_name, found_items)

    msg_lines = [f"`LogicVoid's` Loot Summary:"]
    for item in found_items:
        msg_lines.append(f"- {item['item']}")

    # print("\n".join(msg_lines))