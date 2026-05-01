# Frequently Asked Questions (FAQ)

Welcome! If you're having trouble with the PPE bot, you're likely not alone. This FAQ covers the most common questions and issues non-technical users encounter. Note that this FAQ is a work in progress and the bot has a lot of features that may need to be expanded on. Please run `/ppehelp` for a summary of each command as well.

---

## Most Common Questions

- [Updating Point Values](#editing-the-csv-file)
- [Seasonal vs PPE Character](#seasonal-vs-ppe-character)
- [Security Concerns](#security-concerns)

--- 

## How to Sync Your Fork with the Latest Version

### "How do I update my bot to the latest version?"

This is the most important thing to know about maintaining your bot! Follow these steps:

1. Go to your forked repository on GitHub (e.g., `github.com/yourusername/rotmgppebot`)
2. Look for the **"Sync fork"** button near the top of the page (if you don't see it, your fork is already up to date)
3. Click **"Update branch"** (this merges the latest changes from the original repository into yours)
4. Railway will automatically redeploy your bot. This typically takes a minute or two (during which your bot may be down).
5. Wait for the build to finish. Your bot will automatically restart with the latest version!

That's it! You don't need to touch any code or settings. Everything you configured will stay the same.

### "When should I sync my fork?"

We recommend checking for updates:
- **Weekly or monthly** if you're running an active contest
- **Before important events** to get the latest bug fixes
- **When we announce a new feature** you want to use

**Important:** Always sync during a time when your bot being down for 5 minutes won't disrupt gameplay (like late night or between contest seasons).

### "What if syncing breaks something?"

This is very rare, but if it does happen:
1. Check the Railway logs to see what went wrong
2. Go back to GitHub and try syncing again—sometimes it's just a temporary issue
3. If it keeps failing, open a GitHub Issue describing what happened

You can also **manually rollback** by going to GitHub, clicking "Revert" on the last commit, and deploying again (though this is a last resort).

### "Will syncing delete my configuration and player data?"

**No.** Syncing only updates the bot's code. All your:
- Player records
- Points settings
- Guild configurations
- Team setups
- Everything else

...stays exactly the same. You don't lose anything if you have properly setup a Railway Volume. Note that you should review code if you can in case it updates how data is managed (very rare).

---

## Setup & Deployment

### "What's the difference between forking and cloning? Do I need to do both?"

**You only need to fork.** When you fork on GitHub, it creates your own personal copy of the code under your account. You don't need to clone it to your computer—Railway will handle pulling the code directly from your forked repository. Think of forking as creating your own version of the project that you control.

### "I got an error during deployment. What went wrong?"

Check these things in order:
1. **Did you commit your changes to GitHub?** If you edited `main.py` with your Server ID but didn't click "Commit Changes," Railway won't see your updates.
2. **Is your `DISCORD_TOKEN` set in Railway?** Go to Variables and check that it's there and has the correct token (should be a long string of characters).
3. **Did you set a Volume with Mount Path `/data`?** Without this, all player data disappears when the bot restarts. This is critical.
4. **Check the build logs** in Railway. Click on the build (the box in the middle) and click on logs to see what actually failed.

### "How long does deployment take?"

Usually 2-5 minutes. Railway will show you live logs as it builds. A successful deployment will show a message like "Build successful" or similar. The bot should automatically start after that. Note if it takes longer you can check for [outages](https://status.railway.com/).

### "My bot keeps restarting or crashing. Why?"

Your data may be corrupted, or you may have set it up incorrectly. Carefully verify your bot was setup correctly. If the issue persists, open an issue with as many details and the logs as possible. Note that I make no guarantees that I can look at, nor fix all bugs.

---

## Tokens & Security

### "What's a Discord Token? Why do I need to keep it secret?"

A Discord Token is like a password for your bot. Anyone with this token can control your bot and access your server's data. **Never share it publicly, put it in GitHub, or post it anywhere.** Only put it in Railway's Variables section where it's private. If you accidentally share it, go back to Discord Developer Portal and click "Reset Token" to create a new one.

### "What if I accidentally put my token in GitHub?"

Immediately go to the Discord Developer Portal and click "Reset Token" to create a new one. The old token will stop working. Then go back to Railway and update the `DISCORD_TOKEN` variable with the new token and deploy again.

### "Is the Sniffer Token important to keep secret?"

When linking your Sniffer to the bot, it will ask you to generate a token. It is best to keep this token secret as it is how the bot recognizes a request is coming from you. Note that if it does leak, the only risk is that other people will be able to log loot to your bot under your name. Tokens can be deleted with `/managesniffer`.

---

## Server & Role Setup

### "What does 'Developer Mode' mean? How do I enable it?"

Developer Mode is a Discord feature that shows you technical IDs for servers, users, channels, etc. To enable it:
1. Open Discord Settings
2. Go to **Advanced** (usually at the bottom of the left menu)
3. Toggle **Developer Mode** on
4. Close settings. You should now see "Copy Server ID" when you right-click your server

### "I can't find my Server ID. What am I doing wrong?"

Make sure:
1. **Developer Mode is enabled** (see above)
2. **You're right-clicking on the server name/icon**, not a channel
3. You should see a context menu with "Copy Server ID" option

### "What are roles? Why do I need to create them?"

Roles are like permission levels in Discord. The bot needs specific roles to function properly. When you type `/setuproles`, it automatically creates these roles for you. You can then assign these roles to players to control what they can see and do in the bot. Don't delete or rename these roles unless you know what you're doing!

### "My players can't use `/addplayer`. How do I fix this?"

Only admins can use `/addplayer`. Make sure:
1. The user has an admin/moderator role in Discord
2. They have the role the bot designated as admin (usually created by `/setuproles`)
3. Their role is positioned **above** the bot's role in the server's role list

---

## Bot Not Responding

### "I typed a slash command but nothing happened. Why?"

Try these steps:
1. **Is the bot online?** Check your server member list—the bot should show as "Online" (green dot)
2. **Try `/ppehelp`** in the channel to test if the bot responds at all
3. **Check permissions:** Make sure the channel allows the bot to send messages
4. **Restart the bot:** Go to Railway, find your bot service, and click the restart button
5. **Wait a moment:** Sometimes it takes 5-10 seconds for the bot to process commands

### "The bot shows as offline. What do I do?"

1. Go to your Railway dashboard
2. Find your bot service
3. Check the logs for errors (scroll down to read them)
4. Click the restart button
5. If it stays offline, there's likely an error in the code or configuration. Check:
   - Your `DISCORD_TOKEN` is correct
   - Your `SERVER1_ID` is correct
   - The Volume is attached with Mount Path `/data`

### "I deleted the bot from my server. How do I add it back?"

Use your invite link (the one from Step 2 of setup). You saved it somewhere, right? If you can't find it, go back to the Discord Developer Portal, find your application, get your Application ID, and replace it in this link:

`https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID_HERE&permissions=8&integration_type=0&scope=bot+applications.commands`

---

## Features & Gameplay

### "What's a PPE? Why is this bot for PPE players?"

PPE stands for "Player Pet Experience." It's a Realm of the Mad God (RotMG) challenge where players play on a fresh character, using loot only earned by the character. Note that this bot supports more than just PPEs and can track season loot as well as enable other types of contests.

### "What are 'sets'? Why should I complete them?"

Item sets are themed groups of items that go together (like a full armor set). When you collect all items in a set, the bot can automatically mark it as complete and give bonus points. You configure the bonus points amount as an admin. Information regarding valid sets can be found in `rotmg_item_sets.csv`.

### "What's Sniffer?"

A sniffer is optional software that connects your in-game character to the bot. It automatically logs every item you get when you drop it, so you don't have to type them manually. If you don't use a sniffer, you can manually report items with `/addloot`, `/addseasonloot`, or use image recognition.

### "I enabled Sniffer but it's not logging items. Why?"

Common reasons:
0. **Network Intercept Isn't Working:** Make sure you can get regular sniffer to work. Also make sure you are running sniffer (should say Network Monitor: RUNNING in bottom left). If this is all occurring and its not logging, try reinstalling the sniffer and restarting it.
1. **The item isn't in the CSV file:** If an item exists in the game but not in `rotmg_loot_drops_updated.csv`, sniffer won't recognize it. Information on this can be found in Bridge Review and Bridge Logs.
2. **Sniffer isn't actually connected:** Check `/mysniffer` to see if it says "Connected"
4. **The endpoint URL is wrong:** Make sure it matches your Railway domain exactly. When you click save it should ping you.

---

## Seasonal vs PPE Character

### "What is the 'season' in the bot?"

Within the bot, there is a concept of a season (i.e. `/addseasonloot`). This is just *all* the loot you got across the season. Any loot added to a specific PPE Character will also be added as seasonloot automatically. You can view your season loot by going to `/myinfo -> Show Season Stats`. Admins can reset the season in `/manageseason`.

### "What is a seasonal character in the bot?"

A seasonal character is something you will only see with `/mysniffer` and is a way of labelling a character so that the bot knows that it should send any loot earned on that character directly to your seasonal loot list, instead of putting it under one specific character.

---

## Data & Backups

### "Will my data be saved if the bot restarts?"

**Only if you created a Volume in Railway with Mount Path `/data`.** This is critical! Without it, all player records, points, and history disappear on every restart. If you forgot to create the Volume, do it now in Railway, then deploy again.

### "Can I back up my player data?"

Yes! The data is stored in the `/data` folder on your Railway volume. You can:
1. Download it from Railway's file explorer
2. Save it to your computer as a backup
3. If something goes wrong, you can re-upload it

Check Railway's documentation for detailed instructions on how to download data on a volume.

### "What happens if I delete the bot or stop hosting it?"

All data on the `/data` volume will be deleted if you remove the volume or delete the project. **Make sure to back up your data first** if you think you might need it later!

---

## Updates & Changes

### "How do I update the bot to a newer version?"

1. Go to your GitHub fork of the repository
2. Click the **Sync** button (or **Fetch Upstream** then **Merge**)
3. Go to Railway
4. Click the deploy button
5. The bot will restart with the latest code

It's that simple! You don't need to change anything else.

### "I made changes to the bot myself. Will syncing overwrite them?"

Yes, there may be some risk of losing them. If you made custom changes, **save them somewhere** before syncing, or commit them to your own branch in GitHub to keep them separate.

### "What if the update breaks something?"

Rollbacks are tricky without Git knowledge. Your best bet:
1. Check the GitHub repository for known issues
2. If there's a bug, report it (or wait for a fix)
3. As a last resort, you could re-deploy an older version, but this requires GitHub knowledge

---

## Costs

### "How much does this cost to run?"

Railway charges based on resource usage:
- **Small bot with few players:** Usually $0.50–$2 per month
- **Larger bot with 200+ players:** $3–$10 per month.

You get a small free allowance (~$5) per month, so very small setups might be free!

### "How can I prevent unexpected charges?"

1. **Set a spending limit** in Railway's billing settings
2. **Monitor your usage** on the dashboard regularly. The bot also has information in `/manageseason -> Manage Bot Costs`.
3. **Consider turning off optional features** (like picture suggestions) if you don't need them

### "Can I run this on my personal computer instead of Railway?"

Yes, but:
- You'll need Python installed
- Your computer must stay on 24/7
- It's more complicated to set up
- If your internet goes down, so does the bot

Railway is much easier and more reliable for non-technical users.

---

## Troubleshooting

### "Something is broken and I don't know what. Where do I start?"

1. **Check the Railway logs** - Go to your project, find the service, click "View logs." Look for red error messages.
2. **Restart the bot** - Sometimes it's just being weird. Click the restart button.
3. **Check your variables** - Make sure `DISCORD_TOKEN` is set correctly
4. **Make sure the Volume exists** - The `/data` volume is required
5. **Try the `/ppehelp` command** - If the bot responds, it's mostly working

### "I see a red error in the Railway logs. What does it mean?"

Take a screenshot of the error and share it! Error messages are cryptic, but there are a few common ones:
- **"Token is invalid"** → You have the wrong token. Check Discord Developer Portal.
- **"Cannot find module"** → This usually means a failed deployment. Try redeploying.
- **"Permission denied"** → The bot doesn't have permission to perform an action in Discord

### "Can I get help if my problem isn't listed here?"

Check the GitHub Issues page for your problem. If no one has reported it, you can open a new issue describing what's happening. Include:
- What you were trying to do
- What error you got (or what happened instead)
- Your Railway and Discord setup steps
- As many logs and pictures as possible.

The more details, the better!

### "The bot is doing something weird but isn't showing an error. What now?"

Try:
1. **Restart the bot** in Railway
2. **Redeploy** the bot (click Deploy again)
3. **Check recent changes** - Did you update the bot code recently? 
4. **Check player data** - Is the issue affecting one player or everyone?
5. If still broken, describe it in a GitHub Issue with as much detail as possible. You may have to roll back the bot to an earlier version.

---

## Admin Commands & Management

### "What is `/manageseason`? What can I do with it?"

`/manageseason` is the master admin control panel for managing your entire contest. It has four main sections:

1. **Reset Season** - Clear player data, teams, items, quests, and sniffer links for a new contest
2. **Manage Point Settings** - Configure how points are calculated globally
3. **Manage Contests** - Set up leaderboards and contest configurations
4. **Picture Suggestions** - Enable/disable automatic item recognition from screenshots

We have a detailed [Admin Guide](ADMIN_GUIDE.md) that explains each of these in depth!

### "What is `/manageplayer`? How do I use it?"

`/manageplayer` lets you manage individual players. You can:
- View a player's points and loot history
- Manually add or remove items from their record
- Adjust their points manually
- Assign them to teams
- Change their roles (admin, player, etc.)
- View their quest progress

To use it:
1. Type `/manageplayer @username` (mention the player) or `/manageplayer user_id: [id]` (paste their ID)
2. A menu opens with buttons for different actions
3. Click the action you want, follow the prompts

### "What is `/managequests`? How does it work?"

`/managequests` controls the quest system for your contest. You can:
- **View active quests** - See what quests all players are working on
- **Reset individual player quests** - Clear a specific player's quest progress
- **Configure quest mode** - Choose between "Global" (everyone gets same quests) or "Team Shared" (each team has different quests)
- **Manage quest pools** - Add custom quests or modify existing ones (requires code knowledge for advanced customization)

For most users, you just need to occasionally reset quests when you want a fresh set.

### "What is `/manageteams`? How do I create teams?"

`/manageteams` lets you organize players into competing teams. You can:
- **Create teams** - Give them a name and assign a color
- **View teams** - See all teams and their members
- **Delete teams** - Remove a team (members aren't deleted, just the team)
- **Edit team names/colors** - Customize how they appear in Discord

To add players to teams, use `/manageplayer` on each player and assign them to a team. Team points are automatically combined on leaderboards.

### "What is `/managesniffer`? How do I set it up?"

`/managesniffer` controls automatic loot logging from the sniffer. You can:
- **Enable/Disable Sniffer** - Turn the feature on or off for your guild
- **Set the Endpoint** - Paste your Railway domain so the sniffer knows where to send data
- **View status** - Check if the sniffer connection is working

Detailed sniffer setup is in the main README, but the basic setup is:
1. Type `/managesniffer`
2. Click "Enable Sniffer"
3. Click "Set Endpoint" and paste: `https://<your-railway-domain>/realmshark/ingest`
4. Players can then use `/mysniffer` to link their in-game characters

---

## Points & Scoring System

### "How are points calculated? What affects them?"

Points go through several calculations:

1. **Base Points** - The starting point value from the `rotmg_loot_drops_updated.csv` file (e.g., 1.0 for a T14 weapon)
2. **Rarity Multiplier** - If set in `/manageseason`, different rarities get different multipliers (e.g., divine = 2x, shiny = 2x)
3. **Global Multiplier** - An overall percentage increase/decrease you can set in `/manageseason`
4. **Class Multiplier** - If you set class-specific multipliers (like "Warrior gets 1.5x"), they apply here.
5. **Pet Multiplier** - Additional decay multipliers based on pet level.
6. **Duplicate Reduction** - If the player already has this item, it can get reduced points.
7. **Set Bonus** - If the item completes a set, bonus points are added. The default is 0.

### "How do I change point values for items?"

There are two ways:

**Option 1: CSV (for base point values)**
Edit `rotmg_loot_drops_updated.csv` in your GitHub repository and change the "Points" column. See our "Editing the CSV" section below.

**Option 2: Discord (for wider changes only)**
Use `/manageseason → Manage Point Settings` to configure overarching point settings for all players.

**You cannot configure individual item point changes in Discord** (like making "T14 Sword" worth 5 instead of 1). You must edit the CSV for that.

### "What are 'modifiers' and how do I change them?"

Modifiers are percentage multipliers applied to all loot. In `/manageseason → Manage Point Settings → Manage Global Points`, you can set:

- **Loot Modifier** - Percentage increase/decrease for all loot points (e.g., 110% = 10% bonus)
- **Bonus Modifier** - Percentage increase/decrease for set completion bonuses
- **Penalty Modifier** - Percentage increase/decrease for character penalties (like bad pet rolls)

Example: If you set Loot Modifier to 150%, all items are worth 1.5x their normal points.

**Important:** Shiny and divine can stack! A shiny divine item gets both multipliers (2x × 2x = 4x).

### "What are 'class modifiers'? Can I give certain classes more points?"

Yes! In `/manageseason → Manage Point Settings → Manage Class Modifiers`, you can set different multipliers for each class. For example:
- Warrior: 1.0x (normal)
- Wizard: 1.2x (20% bonus)
- Paladin: 0.8x (20% penalty)

All items dropped by those characters get the multiplier. This is useful for making harder classes reward more points.


---

## Editing the CSV File

---

### "What is the CSV file and why do I need it?"

`rotmg_loot_drops_updated.csv` is a spreadsheet that tells the bot:
1. What items exist in the game
2. How many base points each item is worth
3. Which dungeon each item drops from

If an item isn't in this CSV, the bot won't recognize it when players log it. You can customize this file to match your contest rules.

### "How do I edit the CSV file? It looks complicated..."

Don't worry! It's actually simple. The CSV looks like this:

```
Loot Type,Item Name,Points,Dungeon
Tier 14 Weapon,Sword of Majesty,1.0,Tops
Tier 14 Weapon,Kusanagi,1.0,Tops
Tier 7 Ability,Cloak of Nightmares,1.0,Tops
UT,Bramble Bow,5.0,Forest Maze
Skin,Scallywag Slurp Pet Skin,0,Pirate Cave
```

Each line is one item. The columns are:
- **Loot Type** - Category like "Tier 14 Weapon", "UT", "Skin", etc.
- **Item Name** - Exact name of the item (must match the in-game name!)
- **Points** - Base point value (e.g., 1.0 means 1 point)
- **Dungeon** - Where the item drops from

### "How do I edit the CSV on GitHub?"

1. Go to your forked repository on GitHub
2. Click on `rotmg_loot_drops_updated.csv` to open it
3. Click the **pencil icon** (Edit) in the top right
4. Make your changes:
   - **To change a point value:** Find the item in the list and change the "Points" column
   - **To add a new item:** Add a new line at the end with the format: `Loot Type,Item Name,Points,Dungeon`
   - **To remove an item:** Delete the entire line
5. Scroll to the bottom and click **Commit Changes**
6. Go to Railway and click **Deploy** to reload the CSV

**Important:** Item names must EXACTLY match the in-game name, including capitalization and spaces! "Sword of Majesty" is different from "sword of majesty".

### "Can you give me an example of editing the CSV?"

Sure! Let's say you want to:
1. Change "Kusanagi" from 1.0 points to 3.0 points
2. Add a new item "Ancient Robe of Wisdom" worth 2.5 points

**Step 1:** Find the Kusanagi line. It looks like:
```
Tier 14 Weapon,Kusanagi,1.0,Tops
```

Change it to:
```
Tier 14 Weapon,Kusanagi,3.0,Tops
```

**Step 2:** Go to the end of the file and add a new line:
```
Tier 14 Armor,Ancient Robe of Wisdom,2.5,Void
```

**Step 3:** Click Commit, then redeploy in Railway.

That's it! The changes are live.

### "I messed up the CSV and the bot can't read it. What do I do?"

Don't panic! GitHub has a **Revert** feature:

1. Go to your repository
2. Click on `rotmg_loot_drops_updated.csv`
3. Click **History** (or the clock icon) to see past versions
4. Find the version before you messed up
5. Click **View file** on that version
6. Copy all the text
7. Go back to the current version, click Edit, replace everything with the text you copied, and commit

Or, more simply, you can just sync your fork with the original repository to reset the CSV to the default.

### "Why are some items marked as 0 points?"

Items with 0 points are either:
1. **Skins** - Cosmetic items that shouldn't award points
2. **Items we don't want to count** - You can set any item to 0 if you don't want it tracked
3. **Placeholder items** - Items that exist in the game but we don't have point values for yet

You can change any item to 0 or add new items with 0 points if you want to track them without awarding points.

---

## Security Concerns

### "Do I need to worry about my information being stolen?"

Yes, this is a very valid concern and its good to be proactive about this. There are a few things to address, so I appreciate you taking the time to read through these:

**Hosting the bot:** If you use **the free tier** on Railway, this is completely safe. Since you don't ever need to download any of my code onto your computer, there's no way for you to be at risk to any vulnerabilities. The largest potential security risk for doing this is that I could potentially have the bot forward me all of the information that is stored/sent to the bot to myself. I do not do this and never will, but even if I did, the only information that would be leaked is RotMG PPE data, which isn't a privacy concern. If you get **the paid tier** on Railway, the primary risk is that the bot may run into some error, be spammed, or DDOSed. These are real and valid concerns and something you should address by **setting up spending limits** on Railway. This is very important to set up and will protect you from large charges.

**Sniffer/RealmShark:** This is much more of a security concern, as RealmShark intercepts network packets and could potentially be used as Malware. As such, downloading the original Sniffer, or my extension to it inherently come with security risks. The only way to truly prevent these risks is to read through the code (which is public) and compile it yourself, otherwise you inherently take on the risk of me or the RealmShark team including malware within the downloadable file. I obviously did not do this, but **it is important to be cautious.** If you have technical people in your discord, I would suggest that you have them show people how to generate your own jar file by running the code at `https://github.com/LastEternity/RealmShark/tree/tomato_integration`. I have not included instructions for doing this, however, as it is much more involved and difficult to setup. I also will not answer instruction about how to compile it yourself, as I expect people who are trying to do so will have the technical knowledge to do it themselves.


### "What is risky?"

As mentioned above, using this bot has two potential risks. The first is usage costs and the second is potential Sniffer Malware. Unfortunately, I do not have much control over the first, but it can be addressed with spending limits. For the latter, I *strongly recommend* people review the code and compile it themselves if they wish to use Sniffer, but I provide a precompiled version along with the necessary CSV (`rotmg_loot_drops_updated.csv`) for people's convenience [here](https://drive.google.com/drive/u/2/folders/1d8pT1B3D73gULcJQkVT9WoArDMIzFulG).

---

## Advanced Topics

### "What's an 'environment variable'? Why do I need to set them?"

Environment variables are like settings the bot reads when it starts. In Railway, you set them in the Variables tab. The bot knows to look there for things like your Discord token. You don't need to understand how they work—just make sure you set them correctly!

### "What's a 'Mount Path'? Why is `/data` important?"

A Mount Path tells Railway where to store files on the volume. `/data` is where the bot stores all player records, points, and settings. **Without this Mount Path set correctly, the bot will lose all data on restart.** Don't skip this step!

### "What's the difference between 'Global' and 'Team' quests?"

- **Global:** All players complete quests from the same pool
- **Team:** Each team has their own separate quest pool

You can change this with `/managequests`.

### "What's a 'Sniffer Integration'?"

Sniffer Integration means your bot can connect to in-game sniffer software to automatically log item drops. It's optional but makes tracking much easier. You enable it with `/managesniffer` in Discord.

### "What does 'Duplicate Point Reduction' mean?"

If a player gets the same item twice, the bot treats the second copy as a "duplicate." By default, duplicates get 50% of the normal points. You can configure this in `/manageseason → Manage Point Settings → Manage Duplicate Items`.

For example:
- First Kusanagi: 3 points
- Second Kusanagi (duplicate): 1.5 points (50% reduction)

Different duplicate modes let you decide what counts as a duplicate (same rarity? any rarity? shinies don't count?).

### "What's a 'CSV file'? Why do I need one for loot?"

CSV stands for "comma-separated values." It's a simple spreadsheet format. The `rotmg_loot_drops_updated.csv` file tells the sniffer which items exist and how many points each is worth. Both sniffer files must be in the same folder on your computer. A CSV file is just a spreadsheet!

### "What's the difference between 'Permitted PPE Types' and multipliers?"

**Permitted PPE Types** - Which challenge types are allowed in your contest (e.g., only allow "Regular" PPEs, or allow "Regular", "D+SPE", "NPEs", etc.)

**Multipliers** - How many times the normal points each type is worth. For example, "Ironman" might be worth 1.5x normal points because it's harder.

You configure these in `/manageseason → Manage Contest`

---

## Pro Tips

1. **Save your important links** - Write down your Railway domain, Discord bot invite link, and bot token location (Discord Developer Portal) in case you forget them later.

2. **Test commands as a regular player** - Have a friend without admin permissions test slash commands. Permission bugs are common!

3. **Check the README** - The main README has detailed setup instructions. If you're confused, re-read the relevant section.

4. **Use `/ppehelp`** - This is the bot's built-in help command. It explains all commands and features right in Discord.

5. **Keep GitHub updated** - Use the Sync button regularly to get bug fixes and new features.

6. **Monitor Railway** - Check your usage and spending monthly so you're not surprised by costs.

7. **Back up your data** - Make backups of your `/data` folder regularly, especially before major updates.

---

## Still Stuck?

If your question isn't answered here:

1. **Check the [Admin Guide](ADMIN_GUIDE.md)** - For detailed admin command explanations
2. **Check the full README** - It has comprehensive setup instructions
3. **Review Railway's documentation** - For hosting-specific questions
4. **Check Discord's documentation** - For bot permissions, roles, etc.
5. **Open a GitHub Issue** - Describe your problem with as much detail as possible, and maintainers will help!

Good luck, and have fun with your PPE competition! 🚀
