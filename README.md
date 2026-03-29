# 🧙 ROTMG PPE Discord Bot

A comprehensive Discord bot for managing **Petless Player Experience (PPE)** competitions in Realm of the Mad God communities. Track loot, manage bonuses, calculate points, and maintain leaderboards with automated precision.

## ✨ Features

### 🎮 Player Features
- **Create & Manage PPEs**: Start new PPE runs with automatic penalty calculations
- **Loot Tracking**: Add/remove items with divine and shiny variants
- **Bonus System**: Apply achievement bonuses with quantity tracking
- **Point Management**: Automated point calculations with duplicate handling
- **Personal Statistics**: View your PPE progress and loot collections
- **Separate Seasonal Tracking**: View your overall season progress and loot
- **Account Quests**: Get randomized regular, shiny, and skin quests tied to your account with completion tracking
- **Team System**: Join teams with team leaders who can manage team members

### 🔧 Admin Features
- **Player Management**: Add/remove contest participants
- **Advanced Moderation**: Manage any player's PPE data
- **Point Corrections**: Refresh and fix point totals automatically
- **Bulk Operations**: Mass point recalculation for server-wide fixes
- **Inspection Tools**: View detailed loot and bonus information
- **Quest Administration**: View and reset quest progress for any contest player, including global resets and per-server target tuning
- **Team Management**: Create teams, manage members, and delete teams

### 📊 Advanced Systems
- **Smart Autocomplete**: Context-aware suggestions for items, bonuses, and PPE IDs
- **Role-Based Permissions**: Separate player and admin command access
- **Data Integrity**: Atomic transactions prevent data corruption
- **Penalty Calculations**: Automatic penalties for pets, exalts, and boosts
- **Leaderboard System**: Real-time rankings with best PPE tracking
- **Seasonal Tracking**: Separate seasonal and overall loot tracking with dedicated leaderboards
- **Team Management**: Collaborative competition with team-based leaderboards

## 🚀 Quick Start

### Prerequisites
- Python 3.13+
- Discord Bot Token
- Discord server with appropriate permissions

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/tseringgg/rotmgppebot.git
   cd rotmgppebot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   # Create .env file
   echo "DISCORD_TOKEN=your_bot_token_here" > .env
   ```

4. **Update server configuration**
   ```python
   # In main.py, update these IDs to your servers:
   SERVER1_ID = 000000000000000000  # Replace with your server ID
   SERVER2_ID = 00000000000000000000  # Add more servers as needed
   ```

5. **Run the bot**
   ```bash
   python main.py
   ```

### Initial Setup

1. **Create roles**: Run `/setuproles` to create required roles
2. **Assign permissions**: Give users "PPE Player" or "PPE Admin" roles
3. **Add participants**: Use `/addplayer` to register contest members

## 📋 Command Reference

### Player Commands
| Command | Description |
|---------|-------------|
| `/newppe` | Create a new PPE with class and penalty setup |
| `/setactiveppe` | Switch between your PPE characters |
| `/addloot` | Add items to your active PPE |
| `/removeloot` | Remove items from your active PPE |
| `/addbonus` | Apply achievement bonuses (stackable) |
| `/removebonus` | Remove bonuses (decrements quantity) |
| `/addpenalties` | Apply retroactive penalties to your PPE |
| `/myloot` | View your current PPE's loot and stats |
| `/myppes` | See all your PPEs and which is active |
| `/myquests` | View your current and completed account quests |

### Admin Commands
| Command | Description |
|---------|-------------|
| `/addplayer` | Register a player for the contest |
| `/removeplayer` | Remove a player and all their data |
| `/listplayers` | View all contest participants |
| `/listcharactersfor` | Show all characters and IDs for a specific player |
| `/addlootfor` | Add items to any player's specific PPE |
| `/removelootfrom` | Remove items from any player's PPE |
| `/addbonusfor` | Add bonuses to any player's PPE |
| `/removebonusfrom` | Remove bonuses from any player's PPE |
| `/addpenaltiesfor` | Apply penalties to any player's PPE |
| `/inspectloot` | View any player's PPE loot details |
| `/refreshpointsfor` | Recalculate points for a specific PPE |
| `/refreshallpoints` | Fix all PPE point totals server-wide |
| `/deleteallppes` | Delete all PPEs for a player |
| `/deleteppe` | Delete a specific PPE by ID |
| `/viewquestsfor` | View quest state for any player |
| `/resetquestfor` | Open an interactive menu to reset quest sections for any player |
| `/resetallquests` | Reset quest data for all players (with confirmation) |
| `/managequests` | View or update per-server quest targets (regular/shiny/skin) |

### Team Commands (Leaders & Admins)
| Command | Description |
|---------|-------------|
| `/addteam` | Create a new team with a leader (Admin only) |
| `/addplayer_team` | Add a player to a team (Team leader or Admin) |
| `/leaveteam` | Remove a player from their team (Admin only); works even if player was removed from contest |
| `/updateteam` | Rename a team (Team leader or Admin) |
| `/deleteteam` | Delete a team and remove all members (Admin only) |
| `/teamleaderboard` | View team rankings by total points |
| `/myteam` | View your team members and their rankings (optional: specify team name) |

### Utility Commands
| Command | Description |
|---------|-------------|
| `/leaderboard` | Show top PPE rankings |
| `/characterleaderboard` | Show highest point characters of a specific class |
| `/ppehelp` | Display all available commands |
| `/listadmins` | View all PPE admins |
| `/listroles` | Show server role information |

## 🚂 Hosting on Railway (No Coding Required)

For those unfamiliar with programming, [Railway](https://railway.app/) offers a simple way to host this bot 24/7 in the cloud with minimal setup. This is perfect if you don't want to run the bot on your personal computer.

### Why Railway?
- **Affordable**: Costs approximately **$1-2 per month** (often less)
- **Reliable**: 24/7 uptime for your bot
- **Simple**: No command line experience needed
- **Easy Deployment**: Connect your GitHub account and deploy in minutes

### Railway Setup Instructions

1. **Create a Railway Account**
   - Go to [railway.app](https://railway.app/) and sign up with your GitHub account

2. **Create a New Project**
   - Click "Create New Project"
   - Select "Deploy from GitHub repo"
   - Authorize Railway to access your GitHub account
   - Select the `rotmgppebot` repository

3. **Configure Environment Variables**
   - In the Railway dashboard, go to your project settings
   - Add a new variable: `DISCORD_TOKEN` and set it to your bot token

4. **Create the Data Volume**
   - **This is critical**: The bot stores all player records in a `/data` directory
   - In the Railway dashboard, go to the "Storage" tab
   - Create a new volume called `/data` and mount it by dragging onto the `rotmgppebot` instance.
   - This ensures your player data persists between bot restarts

5. **Deploy**
   - Railway will automatically detect the `requirements.txt` and deploy the bot
   - You'll see build logs in the dashboard
   - Once deployment completes, your bot will start running

6. **Verify It's Running**
   - Check the bot is online in your Discord server
   - Run `/ppehelp` to confirm it's responding

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

### Key Components

- **Player Manager**: Atomic transactions for data safety
- **Team Manager**: Manages team creation, member assignments, and leaderboard calculations
- **Point Calculator**: Handles duplicates and special modifiers
- **Seasonal Tracker**: Maintains unique item collections across seasons with dedicated leaderboards
- **Quest Manager**: Generates randomized regular/shiny/skin quests and rotates replacements on completion
- **Autocomplete System**: Dynamic suggestions based on context
- **Embed Builder**: Rich Discord embed formatting
- **Role Checker**: Permission validation and error handling

## 🔧 Configuration

### Server IDs
Update `main.py` with your Discord server IDs:
```python
SERVER1_ID = your_server_id_here
SERVER2_ID = another_server_id_here
```

### Data Files
- `rotmg_loot_drops_updated.csv`: Item point values
- `bonuses.csv`: Available achievement bonuses
- `{guild_id}_loot_records.json`: Player data storage (per guild)
- `{guild_id}_teams.json`: Team data storage (per guild)
- `{guild_id}_config.json`: Per-server settings storage (quest target counts and future config)

### Role Requirements
- **PPE Player**: Can create PPEs and manage own data
- **PPE Admin**: Full administrative access to all features

## 🎯 Point System

### Base Points
- Items have base point values from the CSV database
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
- **Team Creation**: Admins create teams with a designated leader
- **Member Management**: Team leaders and admins can add/remove players
- **One Team Per Player**: Players cannot be on multiple teams simultaneously
- **Team Leaderboard**: Teams ranked by combined points (using each member's best PPE)
- **Team Viewer**: `/myteam` shows all team members ranked by their best PPE points
- **Automatic Roles**: Discord roles created automatically for each team
- **Team Renaming**: Leaders and admins can update team names
- **Season Reset**: All teams are deleted when season resets
- **Robust Removal**: `/leaveteam` works even for players no longer in the contest

### Team Point Calculation
- Each team member's **highest-scoring PPE** is counted toward the team total
- Team points = Sum of all members' best PPE points
- Members added/removed update totals automatically
- Team leader can be viewed on the team leaderboard

### Viewing Teams
- **`/teamleaderboard`**: See all teams ranked by total points
- **`/myteam`**: View your team members and their individual rankings (or specify a team name to view any team)

### Player Removal Behavior
- **`/removeplayer`**: Removes players by member or raw Discord user ID, clears contest data, and removes team associations
- **`/leaveteam`**: Can remove players from teams even if they were previously removed from the contest system

### Permissions
- **Admin Only**: Create teams, delete teams, force remove players from teams
- **Team Leader + Admin**: Add players to team, update team name
- **All Players**: View team leaderboard, view own team with `/myteam`

## �🛠️ Development

### Project Structure
```
rotmgppebot/
├── main.py                    # Bot entry point
├── dataclass.py              # Data structures
├── requirements.txt          # Dependencies
├── slash_commands/           # Command implementations
├── utils/                   # Utility modules
│   ├── player_records.py    # Data persistence
│   ├── calc_points.py       # Point calculations
│   ├── autocomplete.py      # Dynamic suggestions
│   ├── embed_builders.py    # Discord embeds
│   └── role_checks.py       # Permission validation
└── data/                    # CSV and JSON files
```

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
