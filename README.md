# 🧙 ROTMG PPE Discord Bot

A comprehensive Discord bot for managing competitions and more in Realm of the Mad God. You can track loot, complete quests, set points for items, and maintain a variety of leaderboards.

## Features

### Player Features
- **Create & Manage PPEs**: Create PPEs with automatic penalty calculations.
- **Season Management**: Track whole season loot, beyond individual characters. Auto-updated with character loot.
- **Account Quests**: Get item, shiny, and skin quests with automated completion tracking via `/myquests`.
- **Team Functionality**: You can be added to a team and be assigned a team-specific role with points automatically counted together.
- **Loot Tracking**: Track and graphically view regular, shiny, and divine items and skins automatically or manually.
- **Sniffer Integration**: Automatically connect in-game characters to your bot account via sniffer for automated logging.
- **Bonus System**: Add character bonuses such as fame and maxed stats.
- **Point Management**: Automated and adjustable point calculations with duplicate handling.
- **Personal Dashboard**: Use `/myinfo` as a central menu for all player actions.

### Admin Features
- **Player Management**: One central dashboard for managing any player via `/manageplayer`.
- **Quest Management**: View and reset quest progress for any contest player, including setting up global, shared quests via `/managequests`.
- **Team Management**: Use `/manageteams` to create, update, and delete teams; assign members through `/manageplayer`
- **Global Season Management**: Manage the overall season and the nitty gritty details of how the bot works with `/manageseason`. *Note: this board is still a work in-progress.*


---

## Bot Setup

> **Note:** These are instructions for self-hosting the bot. The bot typically costs less than a dollar a month to run, and you can try self-hosting it with Railway for free. If you have a large community, you may eventually need to pay for their Hobby plan ($5/month). Make sure to set up monetary limits on your hosting account if you decide to upgrade!

### Prerequisites

* A [GitHub](https://github.com/) Account
* A Discord Account

---

### Step 1: GitHub Setup

1. **Fork the Repository**
* Click on the **Fork** button at the top right of this repository's webpage.
* Click **Create Fork**.
* This builds a personal copy of the project under your own GitHub account.


2. **Update `main.py`**
* In your newly created fork, click on the `main.py` file.
* Click the pencil icon (labeled `Edit this file`) in the top right corner of the file view.
* Locate the following lines of code:

```python
# In main.py, update these IDs to your discord server's ID:
SERVER1_ID = 000000000000000000  # Replace with your server ID
SERVER2_ID = 00000000000000000000  # Add more servers as needed
SERVER3_ID = 00000000000000000000  # Add more servers as needed
```
* Update the value of `SERVER1_ID` to match your Discord server's ID. *(To find this, enable Developer Mode in your Discord advanced settings, then right-click your server icon and select "Copy Server ID".)*
* If you intend to only have the bot in **one** Discord server, you can delete the lines for `SERVER2_ID` and `SERVER3_ID`.
* If you delete them, be sure to update the very next line of code to look exactly like this:

```python
guilds = [discord.Object(id=SERVER1_ID)]
```

* Click on **Commit Changes** at the top right, and then click **Commit Changes** again without changing any settings.



> **Tip:** Whenever you want to update your bot to the latest version in the future, just go to your GitHub repository and click the **Sync** button!

---

### Step 2: Getting a Discord Token & Invite Link

Before we can host the bot, we need to create it on Discord and get its "password" (the token).

1. **Create the Application**
* Head over to the [Discord Developer Portal](https://discord.com/developers/applications).
* Log in, click **New Application** in the top right, give your bot a name, and click **Create**.


2. **Get Your Bot Token**
* On the left-hand menu, click on the **Bot** tab.
* Under the bot's username, click the **Reset Token** button, then click **Yes, do it!**.
* Click **Copy** to save your token. **Keep this secret and save it somewhere safe!** You will need it for the next section. *(If you lose it, you'll have to come back and reset it again).*
* *Optional but recommended:* While on this page, scroll down to **Privileged Gateway Intents** and toggle on **Message Content Intent**, **Server Members Intent**, and **Presence Intent**, then save your changes.


3. **Generate Your Invite Link**
* On the left-hand menu, click on **General Information** (or **OAuth2**).
* Find your **Application ID** (also called Client ID) and click **Copy**.
* Take the link below and replace `YOUR_CLIENT_ID_HERE` with the number you just copied:


`https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID_HERE&permissions=8&integration_type=0&scope=bot+applications.commands`
* **Save this customized link!** You will use it to invite the bot to your server after we finish hosting it in the next step.



---

### Step 3: Hosting on Railway

*For those unfamiliar with programming, [Railway](https://railway.app/) offers a simple way to host this bot 24/7 in the cloud with minimal setup. This is perfect if you don't want to run the bot on your personal computer.*

**Why Railway?**

* **Affordable**: Costs approximately **$1–$2 per month** (often less).
* **Reliable**: 24/7 uptime for your bot.
* **Simple**: No command-line experience needed.
* **Easy Deployment**: Connect your GitHub account and deploy in minutes.

#### Railway Setup Instructions

1. **Create a Railway Account**
* Go to [railway.app](https://railway.app/) and sign up using your GitHub account.


2. **Create a New Project**
* Click **Create New Project**.
* Select **Deploy from GitHub repo**.
* Authorize Railway to access your GitHub account.
* Select your forked `rotmgppebot` repository.


3. **Configure Environment Variables**
* In your Railway dashboard, click on your project, go to the **Variables** tab.
* Add a new variable: Name it `DISCORD_TOKEN` and paste the bot token you saved earlier in the value box.
* Add a new variable: Name it `REALMSHARK_INGEST_HOST` and set the value to `0.0.0.0`.
* *(Optional)* If you want the Sniffer integration to be allowed, add a third variable: Name it `REALMSHARK_INGEST_ENABLED` and set the value to `true`.


4. **Configure Settings**
* Navigate to the **Settings** tab. Keep all settings default except for the following:
* **Networking (For Sniffer Integration):** If you enabled Sniffer, scroll to the `Networking` section. Type `8080` into the Port box and click **Generate Domain**. This creates your public web link (Endpoint) that you will give people later.
* **Build:** Scroll to the `Build` section. Set the `Builder` to `Dockerfile` and set the `Dockerfile Path` to `/Dockerfile`.
* Click the purple **Deploy** button.


5. **Create the Data Volume**
* **This is critical:** The bot stores all player records in a `/data` directory. If you skip this, player data will delete itself every time the bot restarts!
* In the Railway project view, right-click on empty space (or click the 'New' button) and select **Volume**.
* Attach it to your `rotmgppebot` service.
* Go to your service settings, find the Volume section, and set the **Mount Path** to `/data`.
* You will likely need to click **Deploy** again to apply these changes.


6. **Deploy**
* Railway will automatically deploy the bot. You can watch the build logs in the dashboard.
* Once deployment completes successfully, your bot will start running!


7. **Add the Bot to Your Server**
* Paste the **Invite Link** you created in Step 2 into your web browser. *(Note: You must have "Manage Server" permissions or be the owner of the Discord server to do this).*
* Select your server and authorize the bot.
* Check your Discord server to make sure the bot is online.
* Type `/ppehelp` in a channel to confirm it's responding!



---

### Step 4: Initial Discord Setup

Now that the bot is in your server, you need to set up its basic functions:

1. **Create roles**: Type `/setuproles` in your server to automatically create the required roles.
2. **Assign permissions**: Give users access to the bot by using the `/addplayer` command to register contest members. You can use `/manageplayer` to give specific people access to management menus.

---

### Step 5: Sniffer Setup (Optional)

**Please note that this step assumes you've followed the regular Sniffer setup and can successfully use regular Sniffer. If you haven't, you can find the RealmShark sniffer [here](https://github.com/X-com/RealmShark).**

*Note: The link to the custom sniffer extension for the bot can be found [here](https://github.com/LastEternity/RealmShark/tree/tomato_integration). The original sniffer file will not work with it, so you will need to download the one attached below. You can also generate the file yourself.*

1. **Verify Your Endpoint:** Check if your bot's sniffer setup is working by opening a web browser and going to `https://<your-railway-domain>/realmshark/health`.
* *Make sure to replace `<your-railway-domain>` with the exact Networking Domain URL you generated in Railway Step 4!* * If it works, the webpage should display: `{"ok": true, "service": "realmshark-ingest"}`.


2. **Enable in Discord:** Go to your Discord server, type `/managesniffer`, and select `Enable Sniffer`.
3. **Set the Endpoint:** Select `Set Endpoint` / `Edit Endpoint` and paste your ingest URL: `https://<your-railway-domain>/realmshark/ingest`. *(Again, remember to replace the placeholder with your actual Railway domain).*
4. **Download Required Files:** Download the Sniffer File and the Loot CSV file [here](https://drive.google.com/drive/folders/1d8pT1B3D73gULcJQkVT9WoArDMIzFulG?usp=sharing). **Keep both of these files in the exact same folder on your computer.** 
* You can review and generate your own version of this extended Sniffer File by going to this link: https://github.com/LastEternity/RealmShark/tree/tomato_integration.
* *Note: If you rename `rotmg_loot_drops_updated.csv` to something else, you will have to update the filename field in the Bridge Review.*
5. Use /mysniffer to see instructions on how to link your sniffer to the bot. Once you save the settings, you should be pinged by the bot!
6. **Customize Loot (Optional):** You can edit your own version of `rotmg_loot_drops_updated.csv` by editing the file in your GitHub repository, saving it, and downloading it. This file determines the base point values of items and tells Sniffer which items to send to the bot. If an item drops but isn't being logged by the bot, it's likely missing from this CSV file!

---

### Step 6: Image Recognition Setup (Optional)

If you don't want to set up the Sniffer, you can easily enable text-based image recognition instead.

*Note: For the bot to recognize an item in a screenshot, the user must be actively hovering their mouse over the item in-game.*

1. Type `/manageseason` in your Discord server and click on `Picture Suggestions`.
2. Enable it and select `Add Channels`. You can select any channel IDs where you want the bot to automatically scan images.
3. Test it out! Post an in-game picture of an item in the designated channel, and the bot will reply with an option for you to accept the suggested item.


## 📋 Command Reference

### Player Commands
| Command | Description |
|---------|-------------|
| `/newppe` | Create a new PPE with class and penalty setup |
| `/myinfo` | Open the reusable My Info menu (season loot, quests, character management, bonus editing) |
| `/setactiveppe` | Switch between your PPE characters |
| `/addloot` | Add items to your active PPE |
| `/removeloot` | Remove items from your active PPE |
| `/addbonus` | Add a bonus to your active PPE |
| `/removebonus` | Remove a bonus from your active PPE |
| `/addseasonloot` | Add a unique item to your season collection |
| `/removeseasonloot` | Remove a unique item from your season collection |
| `/myquests` | Open the same reusable quest menu available from My Info -> Show Quests |

### Admin Commands
| Command | Description |
|---------|-------------|
| `/addplayer` | Register a player for the contest |
| `/listplayers` | View all contest participants |
| `/manageplayer` | Open the admin menu to manage a player's PPE, season loot, quests, team state, and roles (owner-only buttons for Make/Remove Admin) |
| `/addlootfor` | Add items to any player's specific PPE |
| `/removelootfrom` | Remove items from any player's PPE |
| `/addbonusfor` | Add bonuses to any player's PPE |
| `/removebonusfrom` | Remove bonuses from any player's PPE |
| `/addpointsfor` | Manually add points to a specific PPE |
| `/refreshpointsfor` | Recalculate points for a specific PPE |
| `/refreshallpoints` | Fix all PPE point totals server-wide |
| `/managequests` | View or update per-server quest targets (regular/shiny/skin), global quest pools, and run Reset All Quests from the menu |
| `/manageseason` | Open season admin controls: Reset Season and Manage Point Settings |
| `/addseasonlootfor` | Add a unique item to another player's season collection |
| `/removeseasonlootfrom` | Remove a unique item from another player's season collection |

Legacy standalone commands for `/myloot`, `/myppes`, and `/showseasonloot` were retired in favor of `/myinfo`.
The `/myquests` command and the My Info -> Show Quests button now use the same shared menu view implementation.
Quest reset actions are now menu-integrated:
- Use `/myquests` -> `Reset Quests` for self resets.
- Use `/manageplayer` -> `Show Quests` -> `Reset Quests` for admin resets.
- Use `/managequests` -> `Reset All Quests` for server-wide quest resets.

### Team Commands
| Command | Description |
|---------|-------------|
| `/manageteams` | Open admin team management menu (create team, add/remove members, set leader, rename, delete, and view team leaderboard) |
| `/myteam` | View your team members and their rankings (optional: specify team name) |

Player team assignment/removal is now handled through `/manageplayer` in the Team actions panel. Standalone `/removeppeadminrole` was retired; use `/manageplayer` for admin-role toggles.

### Utility Commands
| Command | Description |
|---------|-------------|
| `/leaderboard` | Open interactive leaderboard menu (PPE, Quest, Character by class, Season Loot, Team), all with paged embeds |
| `/ppehelp` | Display all available commands |
| `/listadmins` | View all PPE admins |
| `/listroles` | Show server role information |

### Sniffer Commands
| Command | Description |
|---------|-------------|
| `/mysniffer` | Player sniffer dashboard: setup steps, generate token, unlink token, and open character configure panel |
| `/managesniffer` | Admin sniffer dashboard: enable/disable, manage player sniffer view, manage/revoke tokens, change output channel, and reset all sniffer settings |

## RealmShark Character-Aware Routing

When Tomato sends loot with `character_id`, routing is policy-driven:

1. If `character_id` is mapped to one of your PPEs, the bot logs through `/addloot` behavior on that mapped PPE.
2. If `character_id` is mapped as seasonal, the bot logs through `/addseasonloot` behavior.
3. If `character_id` is unseen/unmapped, the bot logs through `/addseasonloot`, pings the player, and stores a pending loot log (item + rarity + flags) for review.

Use `/mysniffer` and click `Configure Characters` to manage all character mappings and pending loot through an interactive panel. Start in `Show All` (all known characters) or `Show Pending` (only pending unmapped characters), then use the panel buttons to map characters to PPEs (which automatically applies pending loot), set characters as seasonal, clear pending logs, and navigate between entries.
The panel is intuitive with `Prev` / `Next` buttons to cycle through characters, and all destructive actions require explicit confirmation.
The panel/config view shows detected in-game character name/class when available, and mapping is class-validated: a character cannot be mapped to a PPE of a different class.

Pending unmapped character events are stored in per-player files so main guild config files stay compact.

### Important Notes
- **Never commit your `.env` file** with the bot token to GitHub
- The `/data` volume is where all player records, loot tracking, and season data are stored—**never delete it**
- If you need to update the code, simply push changes to your GitHub repo and Railway will redeploy automatically
- Check Railway's [documentation](https://docs.railway.app/) for additional help

## 🏗️ Architecture

### Data Structure
```
PlayerData
├── is_member: bool
├── active_ppe: int
├── team_name: str (optional)  # Name of team player is on
├── unique_items: Set[tuple]  # (item_name, shiny) - Seasonal
├── quests: QuestData
│   ├── current_items: List[str]
│   ├── current_shinies: List[str]
│   ├── current_skins: List[str]
│   ├── completed_items: List[str]
│   ├── completed_shinies: List[str]
│   └── completed_skins: List[str]
└── ppes: List[PPEData]
    ├── id: int
    ├── name: ROTMGClass
    ├── points: float
    ├── loot: List[Loot]
    │   ├── item_name: str
    │   ├── quantity: int
    │   ├── divine: bool
    │   └── shiny: bool
    └── bonuses: List[Bonus]
        ├── name: str
        ├── points: float
        ├── repeatable: bool
        └── quantity: int

TeamData
├── name: str          # Team name
├── leader_id: int     # Discord user ID of leader
└── members: List[int] # Discord user IDs of all members
```

## 🔧 Configuration

### Data Files
- `rotmg_loot_drops_updated.csv`: Item point values
- `bonuses.csv`: Available achievement bonuses
- `{guild_id}_loot_records.json`: Player data storage (per guild)
- `{guild_id}_teams.json`: Team data storage (per guild)
- `{guild_id}_config.json`: Per-server settings storage (quest target counts and future config)
- `{guild_id}_{user_id}_realmshark_pending.json`: Pending unmapped character logs for each player

### Role Requirements
- **PPE Player**: Can create PPEs and manage own data
- **PPE Admin**: Full administrative access to all features

## 🎯 Point System

### Base Points
- Items have base point values from `rotmg_loot_drops_updated.csv`.
- **Divine items**: 2x multiplier
- **Shiny items**: Special point values from separate entries

### Duplicate Handling
- **First item**: Full point value
- **Additional copies**: Half points (except 1-point items)
- **Removal**: Correctly calculates which points to subtract

### Penalties
- **Pet Level**: -0.25 points per level
- **Exalts**: -0.5 points per exalt
- **Loot Boost**: -2 points per 1% boost
- **In-Combat Reduction**: -10 points per 0.2 seconds

## � Team System

### Overview
Teams enable collaborative PPE competition where multiple players combine their efforts for group rankings.

### Key Features
- **Team Creation**: Admins create empty teams from `/manageteams` and assign leader/member later
- **Member Management**: Admins can add/remove players through `/manageplayer`
- **One Team Per Player**: Players cannot be on multiple teams simultaneously
- **Team Leaderboard**: Teams ranked by combined points (using each member's best PPE)
- **Team Viewer**: `/myteam` shows all team members ranked by their best PPE points
- **Automatic Roles**: Discord roles created automatically for each team
- **Team Renaming**: Admins can rename teams from `/manageteams`
- **Season Reset**: All teams are deleted when season resets
- **Robust Removal**: Team removal works even for players no longer in contest records when handled from `/manageplayer`

### Team Point Calculation
- Each team member's **highest-scoring PPE** is counted toward the team total
- Team points = Sum of all members' best PPE points
- Members added/removed update totals automatically
- Team leader can be viewed on the team leaderboard

### Viewing Teams
- **`/manageteams`**: Admin-only menu includes a Team Leaderboard button with paged rankings
- **`/myteam`**: View your team members and their individual rankings (or specify a team name to view any team)

### Player Removal Behavior
- **`/manageplayer`**: Removes players from teams and/or contest data from a single admin panel, and exposes owner-only PPE Admin add/remove actions

### Permissions
- **Admin Only**: Create teams, delete teams, set leaders, rename teams, force remove players from teams
- **All Players**: View team leaderboard, view own team with `/myteam`

## �🛠️ Development

### Project Structure
```
rotmgppebot/
├── main.py                    # Bot entry point
├── dataclass.py              # Data structures
├── requirements.txt          # Dependencies
├── menus/                    # Shared menu/view architecture
│   ├── myinfo/               # My Info menu package (home/season/character/common)
│   ├── myquests/             # My Quests menu package (view/common)
│   ├── myinfo_menu.py        # Compatibility wrapper for older imports
│   ├── myquests_menu.py      # Compatibility wrapper for older imports
│   └── menu_utils/           # Reusable owner/confirm menu components
├── slash_commands/           # Command implementations
├── utils/                   # Utility modules
│   ├── player_records.py    # Data persistence
│   ├── calc_points.py       # Point calculations
│   ├── autocomplete.py      # Dynamic suggestions
│   ├── embed_builders.py    # Discord embeds
│   └── role_checks.py       # Permission validation
└── data/                    # CSV and JSON files
```

### Menu Reuse Design
- Slash commands stay thin and delegate to reusable menu modules in `menus/`.
- The same `MyQuestsView` is used by both `/myquests` and `/myinfo` -> Show Quests.
- My Info and My Quests are split into focused submodules so each button path maps to a dedicated menu/view class instead of one bloated file.

### Adding New Commands
1. Create command file in `slash_commands/`
2. Import in `main.py`
3. Register with Discord using decorators
4. Add to help system in `ppehelp_cmd.py`

### Database Schema Updates
Use the migration system in `player_records.py` to safely update data structures without losing existing player data.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with proper error handling
4. Test thoroughly with edge cases
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Realm of the Mad God community** for inspiration and feedback
- **Discord.py developers** for the excellent library
- **Contributors** who help improve the bot

## 📞 Support

- **Issues**: Report bugs on [GitHub Issues](https://github.com/tseringgg/rotmgppebot/issues)
- **Discord**: Join our community server for help and updates
- **Documentation**: Check the `/ppehelp` command for in-bot guidance

---

*Made with ❤️ for the RotMG PPE community*
