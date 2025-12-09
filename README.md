# 🧙 Discord PPE Bot

A comprehensive Discord bot for managing **Player Progression Enhancement (PPE)** competitions in Realm of the Mad God communities. Track loot, manage bonuses, calculate points, and maintain leaderboards with automated precision.

## ✨ Features

### 🎮 Player Features
- **Create & Manage PPEs**: Start new PPE runs with automatic penalty calculations
- **Loot Tracking**: Add/remove items with divine and shiny variants
- **Bonus System**: Apply achievement bonuses with quantity tracking
- **Point Management**: Automated point calculations with duplicate handling
- **Personal Statistics**: View your PPE progress and loot collections

### 🔧 Admin Features
- **Player Management**: Add/remove contest participants
- **Advanced Moderation**: Manage any player's PPE data
- **Point Corrections**: Refresh and fix point totals automatically
- **Bulk Operations**: Mass point recalculation for server-wide fixes
- **Inspection Tools**: View detailed loot and bonus information

### 📊 Advanced Systems
- **Smart Autocomplete**: Context-aware suggestions for items, bonuses, and PPE IDs
- **Role-Based Permissions**: Separate player and admin command access
- **Data Integrity**: Atomic transactions prevent data corruption
- **Penalty Calculations**: Automatic penalties for pets, exalts, and boosts
- **Leaderboard System**: Real-time rankings with best PPE tracking

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

### Admin Commands
| Command | Description |
|---------|-------------|
| `/addplayer` | Register a player for the contest |
| `/removeplayer` | Remove a player and all their data |
| `/listplayers` | View all contest participants |
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

### Utility Commands
| Command | Description |
|---------|-------------|
| `/leaderboard` | Show top PPE rankings |
| `/ppehelp` | Display all available commands |
| `/listadmins` | View all PPE admins |
| `/listroles` | Show server role information |

## 🏗️ Architecture

### Data Structure
```
PlayerData
├── is_member: bool
├── active_ppe: int
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
```

### Key Components

- **Player Manager**: Atomic transactions for data safety
- **Point Calculator**: Handles duplicates and special modifiers
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
- `guild_loot_records.json`: Player data storage

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

## 🛠️ Development

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