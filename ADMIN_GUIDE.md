# 👨‍💼 Administrator Guide

This guide is for server admins who need to manage contests, configure the bot, and handle complex tasks. If you're looking for general help, check the [FAQ](FAQ.md) instead.

---

## Table of Contents

1. [Command Overview](#command-overview)
2. [/manageseason - Master Control](#manageseason---master-control)
3. [/manageplayer - Individual Player Management](#manageplayer---individual-player-management)
4. [/managequests - Quest Configuration](#managequests---quest-configuration)
5. [/manageteams - Team Management](#manageteams---team-management)
6. [/managesniffer - Sniffer Setup](#managesniffer---sniffer-setup)
7. [Points System Deep Dive](#points-system-deep-dive)
8. [CSV File Editing Guide](#csv-file-editing-guide)
9. [Best Practices](#best-practices)

---

## Admin Command Overview

| Command | Purpose | Who Can Use | Complexity |
|---------|---------|-------------|-----------|
| `/manageseason` | Master control panel for contests | Admins only | High |
| `/manageplayer` | Manage individual players | Admins only | Medium |
| `/managequests` | Configure and reset quests | Admins only | Medium |
| `/manageteams` | Create and manage teams | Admins only | Low |
| `/managesniffer` | Enable/configure sniffer | Admins only | Medium |
| `/ppehelp` | View feature documentation | Everyone | Low |

---

## /manageseason - Master Control

`/manageseason` is the most powerful command. It opens a menu with four main sections:

### 1. Reset Season

**What it does:** Clears old contest data and starts fresh for a new season. You can choose exactly what to reset.

**When to use it:** At the start of each contest season.

**Available reset options:**

- **Reset All (Full Wipe)** - Clears everything: PPEs, items, quests, teams, sniffer links. Start completely fresh.
- **Reset PPEs & Items Only** - Clears all player PPEs and loot history, but keeps teams and sniffer configuration.
- **Reset Teams** - Deletes all teams (players stay in the system).
- **Reset All Sniffer Links** - Disconnects all in-game character links. Players must re-link with `/mysniffer`.
- **Clear Pending Sniffer Data** - Deletes items waiting to be processed by sniffer (rarely needed).

**Example workflow:**
1. Type `/manageseason`
2. Click "Reset Season"
3. Scroll through menu and choose "Reset PPEs & Items Only" (assuming you want to keep your teams)
4. Confirm (it will ask for confirmation)
5. Wait for the reset to complete. You'll see how many items and PPEs were cleared.

**Warning:** Resets are permanent! There's no undo. Make sure you really want to reset before confirming and backup data if needed.

---

### 2. Manage Point Settings

**What it does:** Configure how points are calculated globally. This is where most of your customization happens.

**Sub-sections:**

#### A. Manage Global Points

Sets percentage modifiers that apply to ALL items in your contest.

**What you can configure:**
- **Loot Modifier %** - Applies to regular item drops (e.g., 110% = all items worth 10% more)
- **Bonus Modifier %** - Applies to set completion bonuses (e.g., completing a set usually gives bonus points)
- **Penalty Modifier %** - Applies to starting penalties based on pet level and stats

**Example:** If you set Loot Modifier to 150%, all T14 weapons go from 1 point to 1.5 points.

**Real-world use case:** Mid-contest, your players say items are too easy to get. You raise Loot Modifier to 200% (2x points). Now drops feel more valuable!

---

#### B. Manage Rarity Multipliers

Sets multipliers based on item rarity/color.

**Rarity types:**
- **Common** - Normal items (usually 1.0x)
- **Uncommon** - Slightly rarer (you can set the multiplier)
- **Rare** - Rarer still (you can set the multiplier)
- **Legendary** - Very rare (you can set the multiplier)
- **Divine** - Extremely rare (usually 2.0x)


**Shiny** - Shiny variants of UTs (usually 2.0x, stacks with other multipliers)

**How to edit:**
1. Click "Manage Rarity Multipliers"
2. A form appears showing current values
3. Change any rarity's multiplier (e.g., change Divine from 2.0 to 3.0)
4. Click Submit
5. Changes apply immediately!

**Important:** If an item is both Divine AND Shiny, both multipliers apply! (e.g., 2.0 divine × 2.0 shiny = 4.0x total)

---

#### C. Manage Class Modifiers

Sets multipliers for different character classes (Warrior, Wizard, Knight, etc.).

**What you can do:**
- Set a different multiplier for each class
- This multiplier applies to ALL items that class drops

**Example setup:**
```
Warrior: 1.0x (normal)
Wizard: 1.2x (20% bonus - harder to play)
Knight: 1.1x (10% bonus)
Paladin: 0.9x (10% penalty - too easy)
```

Now when a Wizard drops a T14 weapon (normally 1 point), it's worth 1.2 points!

**How to edit:**
1. Click "Manage Class Modifiers"
2. Select which class to modify from the dropdown
3. Click "Edit Modifier"
4. Enter the new multiplier (e.g., 1.25)
5. Confirm

---

#### D. Manage Set Completion Points

Sets bonus points players get for completing item sets.

**Default set types:**
- **UT Sets** - Untiered equipment sets (e.g., "Golden Archer Set")
- **ST Sets** - Special Tiered equipment sets (e.g., "Assassin's Creed Set")

**How it works:**
1. You set a default point value for all UT sets (e.g., 50 points)
2. You set a default point value for all ST sets (e.g., 75 points)
3. When a player collects all items in a set, they get that bonus
4. You can also override specific sets (e.g., "Golden Archer Set = 75 points" instead of default)

**How to configure:**
1. Click "Manage Set Completion Points"
2. Click "Manage Set Points"
3. Enter the default values:
   - **UT Default:** (number of points for each UT set completion)
   - **ST Default:** (number of points for each ST set completion)
4. Click Submit

**Adding set overrides:**
1. From the same menu, click "Add Set Override"
2. Enter the set name (must match exactly, like "Golden Archer Set")
3. Enter the bonus points for that specific set
4. Submit

**Removing overrides:**
1. Click "Remove Set Override"
2. Enter the set name
3. Confirm (it will fall back to the default)

**Adding sets:**
1. Go to GitHub
2. Open up `rotmg_item_sets.csv`.
3. Populate it with valid items in the correct fields.
4. Save and merge it into your main branch.

---

### 3. Manage Contests

**What it does:** Configure leaderboards, scoring modes, and the "join" page.

**Sub-sections:**

#### A. Set Default Leaderboard

Choose which leaderboard appears when players use `/leaderboard` without specifying one.

**Available leaderboards:**
- **Individual Points** - Shows each player's total points
- **Top 10 Items** - Shows the 10 most common items dropped
- **Divine Count** - Shows how many divine items each player has
- **Shiny Count** - Shows how many shinies each player has
- **Set Completion** - Shows which sets players have completed
- And more...

**How to set:**
1. Click "Manage Contests"
2. Click "Set Default Leaderboard"
3. Select from the dropdown
4. Confirm

---

#### B. Configure Leaderboard Scoring

Choose how points are calculated on leaderboards (affects `/leaderboard` displays).

**Scoring modes:**
- **Total Points** - Sum of all item points (default)
- **Weighted Points** - Different rarities count differently
- **Distinct Items** - Count how many unique items (not total loot)
- **Custom** - Advanced scoring (requires configuration knowledge)

---

#### C. Configure Join Embed

This sets up a nice Discord embed message that tells people how to join the contest.

**How to configure:**
1. Click "Configure Join Page"
2. Set up the title, description, and instructions
3. Choose a role that new players must have to join
4. Confirm
5. The bot will post an embed in a channel with a "Join" button for new players

---

### 4. Picture Suggestions

**What it does:** Enable/disable automatic item recognition from screenshots.

**How it works:**
1. Players upload a screenshot of an item (with mouse hovering over it)
2. The bot uses image recognition to identify the item
3. If it recognizes it, it suggests adding it to the player's loot
4. The player confirms or rejects the suggestion

**How to enable:**
1. Click "Manage Contests"
2. Click "Picture Suggestions"
3. Toggle "Enable" or "Disable"
4. Confirm

**Note:** This is optional! Many contests use sniffer instead, which is more reliable.

---

## /manageplayer - Individual Player Management

Use `/manageplayer` to manage a specific player's records and permissions.

**Available actions:**

### 1. View Player Profile

Shows:
- Total points
- Number of items
- Active PPEs
- Team assignments
- Role (admin, player, etc.)

### 2. View Loot History

Shows all items the player has logged, including:
- Item name
- Points earned
- Rarity (common, divine, etc.)
- Date logged
- Sort by date or points

### 3. Manage PPEs

Create, edit, or delete PPEs for this player.

**When creating a PPE:**
- Set the class (Warrior, Wizard, etc.)
- Set the name (e.g., "Warrior PPE #1")
- Set the starting penalties (pet level, exalts, etc.)
- Choose PPE type (Regular, Hardcore, etc.)

**When editing:**
- Change name or class
- Adjust penalties
- Reassign to a different player

### 4. Add Item

Manually add an item to the player's log (useful if sniffer missed something).

**Steps:**
1. Click "Add Item"
2. Enter the item name (must match CSV exactly)
3. Enter the rarity (common, divine, shiny, etc.)
4. Confirm

The bot automatically calculates correct points based on rarity and all modifiers!

### 5. Remove Item

Remove an item from the player's log (useful if there was a mistake).

**Steps:**
1. Click "Remove Item"
2. Select which item to remove (shows most recent first)
3. Confirm

The points are automatically recalculated.

### 6. Adjust Points

Add or subtract points manually (useful for penalties, bonuses, or corrections).

**Steps:**
1. Click "Adjust Points"
2. Enter the amount (positive to add, negative to subtract)
3. Enter a reason (shows in audit log)
4. Confirm

### 7. Assign to Team

Add the player to a team (or remove from a team).

**Steps:**
1. Click "Assign to Team"
2. Select the team from the dropdown
3. Confirm

Players on the same team have their points combined on team leaderboards!

### 8. Change Role

Give the player admin permissions or remove them.

**Roles:**
- **Player** - Can see leaderboards, manage their own PPEs, submit loot
- **Admin** - Can use all `/manage*` commands, reset data, configure points

**How to promote to admin:**
1. Click "Change Role"
2. Select "Admin"
3. Confirm

**Important:** Only promote players you trust! Admins can delete all data!

---

## /managequests - Quest Configuration

Manage the quest system (daily challenges for points).

**How to use:**
```
/managequests
```

### Main Actions:

#### 1. View Active Quests

Shows all current quests and which players are working on them.

Quests are organized by:
- **Global quests** - Everyone works on the same quests
- **Team quests** - Each team has different quests

#### 2. Reset Player Quests

Clear a specific player's quest progress.

**When to use:** Player wants to re-do quests, or you want to give them new quests mid-season.

**Steps:**
1. Click "Reset Player Quests"
2. Select the player
3. Confirm

The player gets new random quests immediately!

#### 3. Configure Quest Mode

Choose between Global or Team-based quests.

**Global Mode:** Everyone gets the same random quests. Best for mixed-up competitions.

**Team Mode:** Each team gets their own separate quest pool. Best for team vs team competitions.

**How to change:**
1. Click "Manage Quest Mode"
2. Select "Global" or "Team"
3. Confirm

**Note:** Changing the mode doesn't affect active quests—you'd need to reset them separately.

#### 4. Reset All Quests

Clear all quest progress for all players and generate new ones.

**When to use:** Weekly quest refresh, mid-season shakeup, or if there's a bug.

**Steps:**
1. Click "Reset All Quests"
2. Confirm (there's no undo!)

---

## /manageteams - Team Management

Create and manage competing teams.

**How to use:**
```
/manageteams
```

### Main Actions:

#### 1. Create Team

Set up a new team.

**Steps:**
1. Click "Create Team"
2. Enter team name (e.g., "Fire Guild")
3. Choose a color (affects how the team appears)
4. Confirm

The team is created! Now assign players to it using `/manageplayer`.

#### 2. View Teams

See all teams and their members.

**Shows:**
- Team name
- Member list
- Total points

#### 3. Edit Team

Change a team's name.

**Steps:**
1. Click "Edit Team"
2. Select the team
3. Change name
4. Confirm

#### 4. Delete Team

Remove a team (members stay in the system, just not on the team).

**Steps:**
1. Click "Delete Team"
2. Select the team
3. Confirm

**Note:** This doesn't delete the players, just removes the team grouping!

### Adding Players to Teams:

Teams are empty until you assign players! To add someone to a team:

1. Use `/manageplayer @PlayerName`
2. Click "Assign to Team"
3. Select the team
4. Confirm

Their points will now be counted toward the team's total on leaderboards!

---

## /managesniffer - Sniffer Setup

Enable and configure automatic loot logging.

**How to use:**
```
/managesniffer
```

### Main Actions:

#### 1. Enable/Disable Sniffer

Toggle whether sniffer is active for your guild.

**When to use:**
- Enable: You have sniffer files set up and want automatic logging
- Disable: You're using manual loot submission instead

#### 2. Set Endpoint

Tell the sniffer where to send loot data.

**Steps:**
1. Click "Set Endpoint" (or "Edit Endpoint" if already set)
2. Paste your Railway domain: `https://<your-railway-domain>/realmshark/ingest`
3. Confirm

**Example:**
```
https://rotmg-ppe-bot-production.up.railway.app/realmshark/ingest
```

Find your domain in Railway's Networking settings!

#### 3. View Sniffer Status

See if the sniffer connection is working.

**Status indicators:**
- ✅ **Connected** - Sniffer is working, items will be logged
- ❌ **Disconnected** - Something's wrong, check the endpoint URL
- ⏳ **Pending** - Sniffer is processing items, check back soon

#### 4. View Pending Items

See items that sniffer has received but haven't been added to players yet.

(Technical detail: sniffer sometimes needs to verify items before adding them.)

---

## Points System Deep Dive

### How Points Are Calculated

When a player logs an item, the bot goes through these steps:

1. **Get base points from CSV** 
   - Example: Kusanagi = 1.0 point

2. **Apply rarity multiplier**
   - If divine: × 2.0
   - If shiny: × 2.0 (stacks!)
   - If common: × 1.0
   - Example: Divine Kusanagi = 1.0 × 2.0 = 2.0 points

3. **Apply class multiplier**
   - If from Wizard (set to 1.2x): × 1.2
   - Example: 2.0 × 1.2 = 2.4 points

4. **Apply global loot modifier**
   - If you set it to 150%: × 1.5
   - Example: 2.4 × 1.5 = 3.6 points

5. **Apply pet modifier**
   - Based on pet level and stats
   - Example: High-level pet adds 1.2x
   - Example: 3.6 × 1.2 = 4.32 points

6. **Check for duplicates**
   - Is this the second Kusanagi? If so: × 0.5 (50% reduction)
   - Example: 4.32 × 0.5 = 2.16 points

7. **Set bonus** (if item completes a set)
   - Add fixed bonus (e.g., +50 points)
   - Example: 2.16 + 50 = 52.16 points (for the set bonus)

**Final result: 52.16 points awarded!**

### Point Multiplier Cheat Sheet

| Setting | Where to Configure | Effect | Example |
|---------|-------------------|--------|---------|
| CSV Item Points | Edit CSV file | Base value for all items | Kusanagi: 1.0 point |
| Rarity Multiplier | `/manageseason` → Point Settings → Rarity | Boost by item color | Divine = 2.0x |
| Class Multiplier | `/manageseason` → Point Settings → Class | Boost by class | Wizard = 1.2x |
| Global Modifier | `/manageseason` → Point Settings → Global | Boost all items | 150% = 1.5x |
| Duplicate Reduction | `/manageseason` → Point Settings → Duplicate | Reduce 2nd copy | 50% = 0.5x |
| Set Bonus | `/manageseason` → Point Settings → Sets | Bonus when set complete | +50 points |

### Duplicate Point Reduction

**What it does:** The second copy of an item is worth less than the first.

**How to configure:**
1. `/manageseason` → Manage Point Settings
2. Click "Manage Duplicate Items"
3. Set the reduction multiplier (default is 0.5 = 50% of normal points)
4. Set the duplicate mode (how to decide if items match):
   - **Different rarities are separate** - Knife (common) ≠ Knife (divine)
   - **Any rarity of same item is duplicate** - Knife (common) = Knife (divine)
   - **Divines are exempt** - Knife (divine) never loses points; others do
   - **All variants group** - All versions of "Knife" are duplicates, ignoring rarity/shiny

**Example:**
- First Kusanagi (divine): 2.0 points
- Second Kusanagi (common): 1.0 point (50% reduction)
- Third Kusanagi (shiny): 1.0 point (50% reduction)

---

## CSV File Editing Guide

### File Location

`rotmg_loot_drops_updated.csv` in your GitHub repository root.

### File Format

```
Loot Type,Item Name,Points,Dungeon
Tier 14 Weapon,Sword of Majesty,1.0,Tops
Tier 14 Weapon,Kusanagi,1.0,Tops
Tier 7 Ability,Cloak of Nightmares,1.0,Tops
UT,Bramble Bow,5.0,Forest Maze
Skin,Scallywag Slurp Pet Skin,0,Pirate Cave
```

**Columns:**
- **Loot Type** - Category (Tier 14 Weapon, UT, ST, Skin, etc.)
- **Item Name** - Exact in-game name (case-sensitive!)
- **Points** - Base point value (0 = don't count)
- **Dungeon** - Where it drops (informational, not used by bot)

### Editing on GitHub

**Step 1: Navigate to the file**
1. Go to your forked repository
2. Click `rotmg_loot_drops_updated.csv`
3. Click the pencil icon to edit

**Step 2: Make changes**

**Example 1: Change point value**
Find:
```
Tier 14 Weapon,Kusanagi,1.0,Tops
```

Change to:
```
Tier 14 Weapon,Kusanagi,3.0,Tops
```

**Example 2: Add new item**
Go to the end of the file and add:
```
UT,New Sword Name,2.5,Void
```

**Example 3: Remove item**
Delete the entire line for that item.

**Example 4: Disable item (don't count it)**
Change points to 0:
```
Tier 14 Weapon,Sword of Majesty,0,Tops
```

**Step 3: Commit**
1. Scroll to the bottom
2. Click "Commit Changes"
3. (Optional) Add a message like "Buffed Kusanagi from 1 to 3 points"
4. Click "Commit"

**Step 4: Deploy**
1. Go to Railway
2. Click "Deploy" on your bot service
3. Wait for the build to finish
4. Changes are live!

### Common Mistakes & Fixes

**Mistake 1: Changed item name casing**
```
Kusanagi → kusanagi  ❌ Wrong! Sniffer won't recognize it
```
**Fix:** Match exact in-game casing: `Kusanagi` ✅

**Mistake 2: Added a space or special character wrong**
```
Sword of Majesty → Sword ofMajesty  ❌ No space between words!
```
**Fix:** Check in-game name exactly. Use copy-paste if possible.

**Mistake 3: Forgot to commit**
You edited the file but didn't click "Commit Changes."
**Fix:** Click the pencil icon again, make any change (even add a space and remove it), and commit for real this time.

**Mistake 4: Comma or quotation mark broke the format**
If you add an item with a comma in the name, you might break CSV formatting.
```
UT,Soul's Bound Blade,2.5,Void  ❌ The apostrophe might break things
```
**Fix:** Wrap the name in quotes:
```
UT,"Soul's Bound Blade",2.5,Void  ✅
```

### What If the Bot Can't Read the CSV?

If you get an error like "cannot parse CSV," the file is corrupted. Here's how to fix it:

**Option 1: Revert to last working version**
1. Click "History" on the CSV file
2. Find the last version that worked
3. Click "..." and "View file" to see it
4. Copy all the text
5. Go back to edit the current file
6. Replace everything with the copied text
7. Commit

**Option 2: Sync your fork**
1. Go to your repository
2. Click "Sync fork"
3. Click "Update branch"
4. The CSV is restored to the official version!

---

## Best Practices

### Seasonal Management

**Start of Season:**
1. `/manageseason` → "Reset Season" → Choose what to reset
2. `/manageteams` → Create teams
3. `/manageplayer` → Assign players to teams
4. `/manageseason` → "Manage Point Settings" → Set multipliers
5. `/managesniffer` → Ensure endpoint is set and sniffer enabled

**Mid-Season:**
1. Monitor `/leaderboard` regularly
2. Adjust point multipliers if items are too easy/hard
3. Check `/managesniffer` status to ensure items are being logged
4. Use `/manageplayer` → "Adjust Points" to handle special cases

**End of Season:**
1. Run `/leaderboard` to see final standings
2. Export final leaderboard (screenshot or copy)
3. `/manageseason` → "Reset Season" to prepare for next season

### Point Balancing Tips

**If items are too easy (too many points):**
- Lower the CSV base points (edit CSV)
- Lower the Global Loot Modifier (set to 80-90%)
- Lower rarity multipliers
- Increase duplicate reduction

**If items are too hard (not enough points):**
- Raise the CSV base points (edit CSV)
- Raise the Global Loot Modifier (set to 120-150%)
- Raise rarity multipliers
- Decrease duplicate reduction

**If certain classes are overpowered:**
- Lower that class's multiplier (e.g., Wizard 1.2x → 1.0x)
- Or raise other classes

**If sets are too valuable:**
- Lower the set bonus points
- Or keep them high to encourage set collecting!

### Troubleshooting Common Issues

**Problem: Item logged with wrong points**
- Check the CSV - item value might be wrong
- Check if modifiers were changed recently
- Use `/manageplayer` → "Adjust Points" to manually fix

**Problem: Item not recognized by sniffer**
- Item might be missing from CSV
- Check exact spelling (case-sensitive!)
- Use `/manageplayer` → "Add Item" to manually log it

**Problem: Players got 0 points for an item**
- Item is probably set to 0 points in CSV
- Check if duplicate reduction removed all points
- Use `/manageplayer` to view the item and see actual points

**Problem: Sniffer stopped working**
- Check endpoint URL in `/managesniffer`
- Make sure Railway domain is correct (check Railway's Networking settings)
- Check Railway logs for errors
- Try redeploying

**Problem: Can't access `/manageseason`**
- Make sure you're an admin (check your roles in Discord)
- Make sure the bot has permissions to see the channel
- Try using the command in different channel

### Recommended Multiplier Starting Points

For a balanced contest:

```
Global Loot Modifier: 100% (default)
Global Bonus Modifier: 100% (default)
Global Penalty Modifier: 100% (default)

Rarity Multipliers:
  Common: 1.0x
  Uncommon: 1.0x
  Rare: 1.2x
  Legendary: 1.5x
  Divine: 2.0x
  Shiny: 2.0x

Duplicate Reduction: 0.5x (50% of normal)

Class Multipliers (optional):
  All classes: 1.0x (no difference)
  OR adjust based on difficulty:
    Hard classes: 1.2x
    Medium classes: 1.0x
    Easy classes: 0.8x

Set Bonuses:
  UT Sets: 50 points each
  ST Sets: 75 points each
```

Adjust from this baseline based on your contest's difficulty!

---

## FAQ for Admins

**Q: Can I change multipliers mid-contest?**
A: Yes! Changes apply immediately to all items.

**Q: What's the maximum points I can set?**
A: No hard limit! You can set a T14 weapon to 100 points if you want. But very high points can make the game unbalanced.

**Q: Can I prevent certain items from being logged?**
A: Yes! Set their points to 0 in the CSV. They'll still appear in the loot list but award no points.

**Q: What happens if I reset the season accidentally?**
A: The reset is immediate and permanent. Your data is lost unless you have a backup. Always make sure before confirming a reset!

**Q: How do I back up player data?**
A: The bot stores everything in `/data` on your Railway volume. You can:
1. Go to Railway and look at the Volume details
2. Download the files to your computer (instructions are available online)
3. Keep them as a backup

**Q: Can multiple people be admins?**
A: Yes! Use `/manageplayer` to promote multiple players to admin. Admins can all use `/manage*` commands.

**Q: Can I change an item's name in the CSV?**
A: Yes, but be careful:
- Old logs with the old name won't update
- Sniffer won't recognize items with the old name anymore
- Better approach: add a new item and set the old one to 0 points

**Q: How often should I sync the fork?**
A: Weekly or monthly. We release bug fixes and features regularly. Syncing takes 5 minutes!

---

## Getting Help

If you encounter an issue not covered here:

1. **Check the [FAQ](FAQ.md)** for general questions
2. **Check the README** for setup help
3. **Review Railway logs** for technical errors
4. **Open a GitHub Issue** with detailed info:
   - What you were trying to do
   - What error or unexpected behavior occurred
   - Your current settings (if relevant)
   - Steps to reproduce

Good luck managing your contest! 🎉
