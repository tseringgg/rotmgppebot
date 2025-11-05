import discord
from discord.ext import commands
from dotenv import load_dotenv
import aiosqlite
import os

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    async with aiosqlite.connect("data.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS points (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                points INTEGER DEFAULT 0
            )
        """)
        await db.commit()

@bot.command()
@commands.has_permissions(administrator=True)
async def removeplayer(ctx, member: discord.Member):
    """Removes a player completely from the points list."""
    async with aiosqlite.connect("data.db") as db:
        await db.execute("DELETE FROM points WHERE user_id = ?", (member.id,))
        await db.commit()
    await ctx.send(f"🗑️ Removed {member.display_name} from the leaderboard.")
    
@bot.command()
async def addpointsfor(ctx, member: discord.Member, amount: int):
    """Adds points to the specified member."""
    user = member
    display_name = user.display_name  # use server display name
    async with aiosqlite.connect("data.db") as db:
        await db.execute("""
            INSERT INTO points (user_id, username, points)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET 
                username = excluded.username,
                points = points + excluded.points;
        """, (user.id, display_name, amount))
        await db.commit()
    await ctx.send(f"✅ {user.mention} gained **{amount} points!**")

@bot.command()
async def addpoints(ctx, amount: int):
    """Adds points to whoever called the command."""
    user = ctx.author
    display_name = user.display_name  # use server display name
    async with aiosqlite.connect("data.db") as db:
        await db.execute("""
            INSERT INTO points (user_id, username, points)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET 
                username = excluded.username,
                points = points + excluded.points;
        """, (user.id, display_name, amount))
        await db.commit()
    await ctx.send(f"✅ {user.mention} gained **{amount} points!**")

@bot.command()
async def leaderboard(ctx):
    """Shows the top 10 players by display name."""
    async with aiosqlite.connect("data.db") as db:
        async with db.execute("SELECT username, points FROM points ORDER BY points DESC LIMIT 10") as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await ctx.send("No points have been added yet!")
        return

    leaderboard_text = "\n".join([
        f"{i+1}. **{name}** — {pts} pts"
        for i, (name, pts) in enumerate(rows)
    ])
    await ctx.send(f"🏆 **Leaderboard** 🏆\n{leaderboard_text}")
bot.run(DISCORD_TOKEN)
