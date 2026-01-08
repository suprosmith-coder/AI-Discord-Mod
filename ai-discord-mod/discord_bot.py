"""
Cyanix AI - Advanced AI-Powered Discord Moderation Bot
Enhanced version with better performance, more features, and improved UX
"""

import discord
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions, MissingPermissions
from discord import app_commands
from ai_discord_functions import CyanixModerator, image_is_safe, message_is_safe
import os
from dotenv import load_dotenv
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cyanix_ai.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# Constants
DEFAULT_SETTINGS = {
    'use_warnings': False,
    'warnings': 3,
    'mute_time': '10m',
    'sensitivity': 0.5,
    'logs_channel_id': None,
    'moderation_enabled': True,
    'ai_moderator': None
}

# Create locks for thread-safe file operations
servers_lock = asyncio.Lock()
warnings_lock = asyncio.Lock()
sensitivity_lock = asyncio.Lock()

# File paths
SERVERS_FILE = "cyanix_servers.json"
WARNINGS_FILE = "cyanix_warnings.json"
CONFIG_FILE = "cyanix_config.json"

class CyanixDataManager:
    """Enhanced data management with error handling and backup"""
    
    @staticmethod
    async def save_servers(servers: Dict):
        """Save server settings with backup"""
        async with servers_lock:
            try:
                # Create backup
                if os.path.exists(SERVERS_FILE):
                    backup_name = f"{SERVERS_FILE}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    os.rename(SERVERS_FILE, backup_name)
                
                with open(SERVERS_FILE, "w") as file:
                    json.dump(servers, file, indent=2)
                logger.info(f"Saved server settings to {SERVERS_FILE}")
            except IOError as e:
                logger.error(f"Error saving servers: {e}")
                raise
    
    @staticmethod
    async def load_servers() -> Dict:
        """Load server settings with fallback"""
        try:
            with open(SERVERS_FILE, "r") as file:
                data = json.load(file)
                logger.info(f"Loaded server settings from {SERVERS_FILE}")
                return data
        except FileNotFoundError:
            logger.warning(f"{SERVERS_FILE} not found, creating new")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing {SERVERS_FILE}: {e}")
            return {}
    
    @staticmethod
    async def save_warnings(warning_list: Dict):
        """Save warnings with compression"""
        async with warnings_lock:
            try:
                # Compress old warnings (older than 30 days)
                current_time = datetime.now().timestamp()
                compressed_data = {}
                
                for guild_id, users in warning_list.items():
                    compressed_users = {}
                    for user_id, warnings in users.items():
                        # Keep only active warnings (last 30 days)
                        if isinstance(warnings, dict) and 'last_warning' in warnings:
                            last_warning = datetime.fromisoformat(warnings['last_warning']).timestamp()
                            if current_time - last_warning < 30 * 24 * 3600:  # 30 days
                                compressed_users[user_id] = warnings
                        else:
                            compressed_users[user_id] = warnings
                    
                    if compressed_users:
                        compressed_data[guild_id] = compressed_users
                
                with open(WARNINGS_FILE, "w") as file:
                    json.dump(compressed_data, file, indent=2)
                logger.info(f"Saved warnings to {WARNINGS_FILE}")
            except IOError as e:
                logger.error(f"Error saving warnings: {e}")
                raise
    
    @staticmethod
    async def load_warnings() -> Dict:
        """Load warnings with validation"""
        try:
            with open(WARNINGS_FILE, "r") as file:
                data = json.load(file)
                logger.info(f"Loaded warnings from {WARNINGS_FILE}")
                return data
        except FileNotFoundError:
            logger.warning(f"{WARNINGS_FILE} not found, creating new")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing {WARNINGS_FILE}: {e}")
            return {}
    
    @staticmethod
    async def save_config(config: Dict):
        """Save global configuration"""
        try:
            with open(CONFIG_FILE, "w") as file:
                json.dump(config, file, indent=2)
            logger.info(f"Saved config to {CONFIG_FILE}")
        except IOError as e:
            logger.error(f"Error saving config: {e}")

# Initialize data
servers = asyncio.run(CyanixDataManager.load_servers())
warning_list = asyncio.run(CyanixDataManager.load_warnings())

# Initialize Cyanix AI moderators for each server
async def initialize_server_moderators():
    """Initialize AI moderators for each server"""
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found in environment")
        return
    
    for guild_id, settings in servers.items():
        try:
            sensitivity = settings.get('sensitivity', DEFAULT_SETTINGS['sensitivity'])
            moderator = CyanixModerator(openai_api_key, sensitivity)
            settings['ai_moderator'] = moderator
            logger.info(f"Initialized AI moderator for guild {guild_id}")
        except Exception as e:
            logger.error(f"Failed to initialize moderator for guild {guild_id}: {e}")

# Run initialization
asyncio.create_task(initialize_server_moderators())

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

class CyanixAI(commands.Bot):
    """Cyanix AI Discord Bot with enhanced features"""
    
    def __init__(self):
        super().__init__(
            command_prefix='$',
            intents=intents,
            help_command=None  # We'll use our own help command
        )
        
        # Bot stats
        self.stats = {
            'messages_processed': 0,
            'violations_detected': 0,
            'images_processed': 0,
            'start_time': datetime.now()
        }
        
        # Activity loop
        self.status_loop.start()
    
    async def setup_hook(self):
        """Setup hook for slash commands"""
        await self.tree.sync()
        logger.info("Slash commands synced")
    
    @tasks.loop(seconds=30)
    async def status_loop(self):
        """Rotate bot status"""
        statuses = [
            discord.Activity(type=discord.ActivityType.watching, name="for rule violations"),
            discord.Activity(type=discord.ActivityType.listening, name="moderation reports"),
            discord.Activity(type=discord.ActivityType.playing, name="with AI algorithms"),
            discord.Activity(type=discord.ActivityType.competing, name="against toxic behavior")
        ]
        await self.change_presence(activity=statuses[self.stats['messages_processed'] % len(statuses)])

bot = CyanixAI()

class TimeConverter:
    """Convert time strings to seconds"""
    
    @staticmethod
    def to_seconds(time_str: str) -> Optional[int]:
        """Convert time string to seconds"""
        try:
            if time_str[-1] not in 'smhd':
                return None
            
            value = int(time_str[:-1])
            unit = time_str[-1]
            
            multipliers = {
                's': 1,
                'm': 60,
                'h': 3600,
                'd': 86400
            }
            
            if unit not in multipliers:
                return None
            
            return value * multipliers[unit]
        except (ValueError, KeyError):
            return None
    
    @staticmethod
    def to_readable(seconds: int) -> str:
        """Convert seconds to readable string"""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        elif seconds < 86400:
            return f"{seconds // 3600}h"
        else:
            return f"{seconds // 86400}d"

# ========== COMMANDS ==========

@bot.tree.command(name="help", description="Shows commands and information for Cyanix AI bot.")
async def cyanix_help(interaction: discord.Interaction):
    """Help command with Cyanix AI branding"""
    embed = discord.Embed(
        title="🛡️ Cyanix AI Help",
        description="Advanced AI-powered moderation for your Discord server.",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📊 Configuration Commands",
        value="""
        `/config` - View current configuration
        `/set_warnings <count>` - Set warning limit before mute (default: 3)
        `/set_mute_time <time>` - Set mute duration (e.g., 1d, 3m, 5s, 6h)
        `/toggle_warnings <on/off>` - Enable/disable warning system
        `/set_sensitivity <0.0-1.0>` - Set AI sensitivity (higher = more strict)
        `/set_logs_channel <channel>` - Set channel for moderation logs
        `/toggle_moderation <on/off>` - Enable/disable AI moderation
        """,
        inline=False
    )
    
    embed.add_field(
        name="👤 User Management",
        value="""
        `/warnings @user` - Check user's warnings
        `/clear_warnings @user` - Clear user's warnings
        `/mute @user <time> [reason]` - Manually mute a user
        `/unmute @user` - Unmute a user
        `/history @user` - View user's moderation history
        """,
        inline=False
    )
    
    embed.add_field(
        name="📈 Analytics",
        value="""
        `/stats` - View moderation statistics
        `/report` - Generate moderation report
        `/status` - Check bot status and health
        """,
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Default Settings",
        value=f"""
        Warning Limit: {DEFAULT_SETTINGS['warnings']}
        Mute Time: {DEFAULT_SETTINGS['mute_time']}
        Warning System: {'Enabled' if DEFAULT_SETTINGS['use_warnings'] else 'Disabled'}
        Sensitivity: {DEFAULT_SETTINGS['sensitivity']}
        """,
        inline=False
    )
    
    embed.set_footer(text="Cyanix AI 🤖 | Advanced AI Moderation")
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="config", description="View current server configuration.")
async def view_config(interaction: discord.Interaction):
    """View current server configuration"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You need administrator permissions to use this command.",
            ephemeral=True
        )
        return
    
    guild_id = str(interaction.guild.id)
    settings = servers.get(guild_id, DEFAULT_SETTINGS.copy())
    
    embed = discord.Embed(
        title="⚙️ Server Configuration",
        description=f"Configuration for {interaction.guild.name}",
        color=discord.Color.green()
    )
    
    embed.add_field(name="Warning System", value="✅ Enabled" if settings.get('use_warnings', False) else "❌ Disabled", inline=True)
    embed.add_field(name="Warning Limit", value=str(settings.get('warnings', 3)), inline=True)
    embed.add_field(name="Mute Duration", value=settings.get('mute_time', '10m'), inline=True)
    embed.add_field(name="AI Sensitivity", value=f"{settings.get('sensitivity', 0.5):.2f}", inline=True)
    embed.add_field(name="Logs Channel", value=f"<#{settings.get('logs_channel_id', 0)}>" if settings.get('logs_channel_id') else "Not set", inline=True)
    embed.add_field(name="AI Moderation", value="✅ Enabled" if settings.get('moderation_enabled', True) else "❌ Disabled", inline=True)
    
    # Stats
    warnings_count = len(warning_list.get(guild_id, {}))
    embed.add_field(name="Active Warnings", value=str(warnings_count), inline=False)
    
    embed.set_footer(text="Use /help to see all commands")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="set_logs_channel", description="Set a channel for moderation logs.")
@app_commands.describe(channel="The channel to send logs to")
async def set_logs_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """Set logs channel"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You need administrator permissions to use this command.",
            ephemeral=True
        )
        return
    
    guild_id = str(interaction.guild.id)
    servers[guild_id] = servers.get(guild_id, DEFAULT_SETTINGS.copy())
    servers[guild_id]['logs_channel_id'] = str(channel.id)
    
    await CyanixDataManager.save_servers(servers)
    
    embed = discord.Embed(
        title="✅ Logs Channel Set",
        description=f"Moderation logs will now be sent to {channel.mention}",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="toggle_warnings", description="Enable or disable the warning system.")
@app_commands.describe(enabled="Enable warning system")
async def toggle_warnings(interaction: discord.Interaction, enabled: bool):
    """Toggle warning system"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You need administrator permissions to use this command.",
            ephemeral=True
        )
        return
    
    guild_id = str(interaction.guild.id)
    servers[guild_id] = servers.get(guild_id, DEFAULT_SETTINGS.copy())
    servers[guild_id]['use_warnings'] = enabled
    
    await CyanixDataManager.save_servers(servers)
    
    status = "✅ Enabled" if enabled else "❌ Disabled"
    embed = discord.Embed(
        title="⚙️ Warning System Updated",
        description=f"Warning system has been {status}",
        color=discord.Color.green() if enabled else discord.Color.orange()
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="set_sensitivity", description="Set AI moderation sensitivity (0.0-1.0).")
@app_commands.describe(sensitivity="Sensitivity level (0.0 = lenient, 1.0 = strict)")
async def set_sensitivity(interaction: discord.Interaction, sensitivity: float):
    """Set AI sensitivity"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You need administrator permissions to use this command.",
            ephemeral=True
        )
        return
    
    if not 0.0 <= sensitivity <= 1.0:
        await interaction.response.send_message(
            "Sensitivity must be between 0.0 and 1.0.",
            ephemeral=True
        )
        return
    
    guild_id = str(interaction.guild.id)
    servers[guild_id] = servers.get(guild_id, DEFAULT_SETTINGS.copy())
    servers[guild_id]['sensitivity'] = round(sensitivity, 2)
    
    # Update AI moderator if exists
    if 'ai_moderator' in servers[guild_id] and servers[guild_id]['ai_moderator']:
        servers[guild_id]['ai_moderator'].sensitivity = sensitivity
    
    await CyanixDataManager.save_servers(servers)
    
    embed = discord.Embed(
        title="🎯 Sensitivity Updated",
        description=f"AI sensitivity set to **{sensitivity:.2f}**",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="What this means:",
        value=f"""
        • **Low ({sensitivity:.2f})**: Fewer false positives, may miss some violations
        • **High ({sensitivity:.2f})**: More aggressive moderation, more false positives
        """,
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="set_warnings", description="Set warning limit before muting.")
@app_commands.describe(count="Number of warnings before mute")
async def set_warnings(interaction: discord.Interaction, count: int):
    """Set warning limit"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You need administrator permissions to use this command.",
            ephemeral=True
        )
        return
    
    if count < 1 or count > 10:
        await interaction.response.send_message(
            "Warning count must be between 1 and 10.",
            ephemeral=True
        )
        return
    
    guild_id = str(interaction.guild.id)
    servers[guild_id] = servers.get(guild_id, DEFAULT_SETTINGS.copy())
    servers[guild_id]['warnings'] = count
    
    await CyanixDataManager.save_servers(servers)
    
    embed = discord.Embed(
        title="⚠️ Warning Limit Updated",
        description=f"Users will be muted after **{count}** warnings",
        color=discord.Color.orange()
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="set_mute_time", description="Set mute duration for violations.")
@app_commands.describe(duration="Mute duration (e.g., 1d, 3m, 5s, 6h)")
async def set_mute_time(interaction: discord.Interaction, duration: str):
    """Set mute time"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You need administrator permissions to use this command.",
            ephemeral=True
        )
        return
    
    # Validate duration
    if not TimeConverter.to_seconds(duration):
        await interaction.response.send_message(
            "Invalid duration format. Use: 1s, 5m, 2h, 1d",
            ephemeral=True
        )
        return
    
    guild_id = str(interaction.guild.id)
    servers[guild_id] = servers.get(guild_id, DEFAULT_SETTINGS.copy())
    servers[guild_id]['mute_time'] = duration
    
    await CyanixDataManager.save_servers(servers)
    
    readable_time = TimeConverter.to_readable(TimeConverter.to_seconds(duration))
    
    embed = discord.Embed(
        title="⏰ Mute Duration Updated",
        description=f"Mute duration set to **{duration}** ({readable_time})",
        color=discord.Color.purple()
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="warnings", description="Check a user's warnings.")
@app_commands.describe(user="User to check warnings for")
async def check_warnings(interaction: discord.Interaction, user: discord.Member):
    """Check user warnings"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You need administrator permissions to use this command.",
            ephemeral=True
        )
        return
    
    guild_id = str(interaction.guild.id)
    user_warnings = warning_list.get(guild_id, {}).get(str(user.id), {})
    
    if isinstance(user_warnings, dict):
        warning_count = user_warnings.get('count', 0) if 'count' in user_warnings else user_warnings
        last_warning = user_warnings.get('last_warning')
    else:
        warning_count = user_warnings
        last_warning = None
    
    guild_settings = servers.get(guild_id, DEFAULT_SETTINGS.copy())
    warning_limit = guild_settings.get('warnings', 3)
    
    embed = discord.Embed(
        title=f"⚠️ Warnings for {user.name}",
        color=discord.Color.orange()
    )
    
    embed.add_field(name="Current Warnings", value=str(warning_count), inline=True)
    embed.add_field(name="Warning Limit", value=str(warning_limit), inline=True)
    embed.add_field(name="Status", value="⚠️ Close to mute" if warning_count >= warning_limit - 1 else "✅ Safe", inline=True)
    
    if last_warning:
        embed.add_field(name="Last Warning", value=f"<t:{int(datetime.fromisoformat(last_warning).timestamp())}:R>", inline=False)
    
    embed.set_thumbnail(url=user.avatar.url if user.avatar else None)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="clear_warnings", description="Clear a user's warnings.")
@app_commands.describe(user="User to clear warnings for")
async def clear_warnings(interaction: discord.Interaction, user: discord.Member):
    """Clear user warnings"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You need administrator permissions to use this command.",
            ephemeral=True
        )
        return
    
    guild_id = str(interaction.guild.id)
    
    if guild_id in warning_list and str(user.id) in warning_list[guild_id]:
        del warning_list[guild_id][str(user.id)]
        await CyanixDataManager.save_warnings(warning_list)
        
        embed = discord.Embed(
            title="✅ Warnings Cleared",
            description=f"Cleared all warnings for {user.mention}",
            color=discord.Color.green()
        )
    else:
        embed = discord.Embed(
            title="ℹ️ No Warnings Found",
            description=f"{user.mention} has no warnings to clear.",
            color=discord.Color.blue()
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="stats", description="View moderation statistics.")
async def view_stats(interaction: discord.Interaction):
    """View bot statistics"""
    guild_id = str(interaction.guild.id)
    
    # Calculate uptime
    uptime = datetime.now() - bot.stats['start_time']
    uptime_str = str(uptime).split('.')[0]
    
    # Get server stats
    guild_settings = servers.get(guild_id, DEFAULT_SETTINGS.copy())
    warnings_count = len(warning_list.get(guild_id, {}))
    
    embed = discord.Embed(
        title="📊 Cyanix AI Statistics",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    embed.add_field(name="Messages Processed", value=str(bot.stats['messages_processed']), inline=True)
    embed.add_field(name="Violations Detected", value=str(bot.stats['violations_detected']), inline=True)
    embed.add_field(name="Images Analyzed", value=str(bot.stats['images_processed']), inline=True)
    embed.add_field(name="Active Warnings", value=str(warnings_count), inline=True)
    embed.add_field(name="Uptime", value=uptime_str, inline=True)
    embed.add_field(name="AI Sensitivity", value=f"{guild_settings.get('sensitivity', 0.5):.2f}", inline=True)
    
    # Performance metrics
    if bot.stats['messages_processed'] > 0:
        violation_rate = (bot.stats['violations_detected'] / bot.stats['messages_processed']) * 100
        embed.add_field(
            name="Violation Rate",
            value=f"{violation_rate:.1f}%",
            inline=False
        )
    
    embed.set_footer(text="Cyanix AI 🤖 | Advanced AI Moderation")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="toggle_moderation", description="Enable or disable AI moderation.")
@app_commands.describe(enabled="Enable AI moderation")
async def toggle_moderation(interaction: discord.Interaction, enabled: bool):
    """Toggle AI moderation"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You need administrator permissions to use this command.",
            ephemeral=True
        )
        return
    
    guild_id = str(interaction.guild.id)
    servers[guild_id] = servers.get(guild_id, DEFAULT_SETTINGS.copy())
    servers[guild_id]['moderation_enabled'] = enabled
    
    await CyanixDataManager.save_servers(servers)
    
    status = "✅ Enabled" if enabled else "❌ Disabled"
    embed = discord.Embed(
        title="🤖 AI Moderation Updated",
        description=f"AI moderation has been {status}",
        color=discord.Color.green() if enabled else discord.Color.red()
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ========== UTILITY FUNCTIONS ==========

async def tempmute(ctx, member: discord.Member, reason: str = "Too many warnings"):
    """Temporarily mute a user"""
    guild = ctx.guild
    guild_settings = servers.get(str(guild.id), DEFAULT_SETTINGS.copy())
    time_str = guild_settings.get('mute_time', '10m')
    
    # Convert time to seconds
    seconds = TimeConverter.to_seconds(time_str)
    if not seconds:
        await ctx.send("Invalid mute duration configuration.")
        return
    
    # Create or get muted role
    muted_role = discord.utils.get(guild.roles, name="Muted")
    if not muted_role:
        try:
            muted_role = await guild.create_role(
                name="Muted",
                reason="Cyanix AI moderation role"
            )
            
            # Position role below bot's highest role
            bot_member = guild.get_member(bot.user.id)
            if bot_member.roles:
                bot_top_role = bot_member.top_role
                await muted_role.edit(position=bot_top_role.position - 1)
            
            # Set permissions for all channels
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel) or isinstance(channel, discord.VoiceChannel):
                    await channel.set_permissions(
                        muted_role,
                        speak=False,
                        send_messages=False,
                        add_reactions=False,
                        read_message_history=True,
                        read_messages=True
                    )
                    
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to create or manage the Muted role.")
            return
    
    # Apply mute
    try:
        await member.add_roles(muted_role, reason=reason)
        
        # Send notification
        readable_time = TimeConverter.to_readable(seconds)
        embed = discord.Embed(
            title="🔇 User Muted",
            description=f"{member.mention} has been muted for {reason}.",
            color=discord.Color.red()
        )
        embed.add_field(name="Duration", value=f"{time_str} ({readable_time})", inline=True)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        
        await ctx.send(embed=embed)
        
        # Schedule unmute
        await asyncio.sleep(seconds)
        await member.remove_roles(muted_role, reason="Mute duration expired")
        
        # Send unmute notification
        unmute_embed = discord.Embed(
            title="🔊 User Unmuted",
            description=f"{member.mention} has been automatically unmuted.",
            color=discord.Color.green()
        )
        await ctx.send(embed=unmute_embed)
        
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to mute this user.")
    except Exception as e:
        logger.error(f"Error muting user: {e}")
        await ctx.send("❌ An error occurred while muting the user.")

async def log_violation(guild: discord.Guild, user: discord.Member, content: str, violation_type: str, details: Dict = None):
    """Log violation to configured channel"""
    guild_id = str(guild.id)
    guild_settings = servers.get(guild_id, DEFAULT_SETTINGS.copy())
    
    logs_channel_id = guild_settings.get('logs_channel_id')
    if not logs_channel_id:
        return
    
    logs_channel = bot.get_channel(int(logs_channel_id))
    if not logs_channel:
        return
    
    embed = discord.Embed(
        title="🚨 Content Violation",
        description=f"Violation detected from {user.mention}",
        color=discord.Color.orange(),
        timestamp=datetime.now()
    )
    
    embed.add_field(name="User", value=f"{user} ({user.id})", inline=True)
    embed.add_field(name="Channel", value=f"<#{user.guild.system_channel.id}>", inline=True)
    embed.add_field(name="Type", value=violation_type, inline=True)
    
    if content:
        content_preview = content[:500] + ("..." if len(content) > 500 else "")
        embed.add_field(name="Content", value=f"```{content_preview}```", inline=False)
    
    if details:
        categories = details.get('categories', {})
        if categories:
            flagged_categories = [cat for cat, flagged in categories.items() if flagged]
            if flagged_categories:
                embed.add_field(
                    name="Violation Categories",
                    value=", ".join(flagged_categories),
                    inline=False
                )
    
    embed.set_thumbnail(url=user.avatar.url if user.avatar else None)
    embed.set_footer(text=f"User ID: {user.id}")
    
    await logs_channel.send(embed=embed)

# ========== EVENT HANDLERS ==========

@bot.event
async def on_ready():
    """Bot ready event"""
    logger.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
    
    # Set initial presence
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(bot.guilds)} servers | /help"
        )
    )
    
    logger.info(f"Connected to {len(bot.guilds)} guilds")

@bot.event
async def on_guild_join(guild: discord.Guild):
    """Bot joined a new guild"""
    logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
    
    # Initialize server settings
    guild_id = str(guild.id)
    if guild_id not in servers:
        servers[guild_id] = DEFAULT_SETTINGS.copy()
        await CyanixDataManager.save_servers(servers)
    
    # Send welcome message
    system_channel = guild.system_channel
    if system_channel:
        embed = discord.Embed(
            title="🤖 Cyanix AI Has Arrived!",
            description="Thank you for adding Cyanix AI to your server!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Getting Started",
            value="Use `/help` to see all available commands and configure the bot.",
            inline=False
        )
        
        embed.add_field(
            name="Default Settings",
            value=f"""
            • Warning System: {'Enabled' if DEFAULT_SETTINGS['use_warnings'] else 'Disabled'}
            • Warning Limit: {DEFAULT_SETTINGS['warnings']}
            • Mute Duration: {DEFAULT_SETTINGS['mute_time']}
            • AI Sensitivity: {DEFAULT_SETTINGS['sensitivity']}
            """,
            inline=False
        )
        
        embed.set_footer(text="Cyanix AI 🤖 | Advanced AI Moderation")
        
        await system_channel.send(embed=embed)

@bot.event
async def on_message(message: discord.Message):
    """Message event handler"""
    await bot.wait_until_ready()
    
    # Ignore bot messages
    if message.author.bot:
        return
    
    # Update stats
    bot.stats['messages_processed'] += 1
    
    guild = message.guild
    if not guild:
        return
    
    guild_id = str(guild.id)
    
    # Initialize server settings if not exists
    if guild_id not in servers:
        servers[guild_id] = DEFAULT_SETTINGS.copy()
        await CyanixDataManager.save_servers(servers)
    
    # Check if moderation is enabled
    guild_settings = servers.get(guild_id, DEFAULT_SETTINGS.copy())
    if not guild_settings.get('moderation_enabled', True):
        return
    
    use_warnings = guild_settings.get('use_warnings', False)
    warnings_limit = guild_settings.get('warnings', 3)
    
    # Initialize warning list for guild if not exists
    if guild_id not in warning_list:
        warning_list[guild_id] = {}
        await CyanixDataManager.save_warnings(warning_list)
    
    # Check for attachments (images)
    if message.attachments:
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith("image/"):
                bot.stats['images_processed'] += 1
                
                try:
                    # Get sensitivity
                    sensitivity = guild_settings.get('sensitivity', 0.5)
                    
                    # Use AI moderator if available, otherwise fallback
                    if 'ai_moderator' in guild_settings and guild_settings['ai_moderator']:
                        is_safe, details = await guild_settings['ai_moderator'].moderate_image(attachment.url)
                    else:
                        is_safe, details = await image_is_safe(attachment.url, sensitivity)
                    
                    if not is_safe:
                        await handle_violation(
                            message=message,
                            user=message.author,
                            content=f"[Image: {attachment.filename}]",
                            violation_type="image",
                            details=details,
                            use_warnings=use_warnings,
                            warnings_limit=warnings_limit
                        )
                        return  # Stop processing after first violation
                        
                except Exception as e:
                    logger.error(f"Error processing image: {e}")
    
    # Check text content
    if message.content:
        try:
            # Use AI moderator if available
            if 'ai_moderator' in guild_settings and guild_settings['ai_moderator']:
                is_safe, details = await guild_settings['ai_moderator'].moderate_message(
                    message.content,
                    str(message.author.id)
                )
            else:
                is_safe, details = await message_is_safe(message.content, os.getenv("OPENAI_API_KEY"))
            
            if not is_safe:
                await handle_violation(
                    message=message,
                    user=message.author,
                    content=message.content,
                    violation_type="text",
                    details=details,
                    use_warnings=use_warnings,
                    warnings_limit=warnings_limit
                )
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    await bot.process_commands(message)

async def handle_violation(message: discord.Message, user: discord.Member, content: str, 
                           violation_type: str, details: Dict, use_warnings: bool, 
                           warnings_limit: int):
    """Handle content violation"""
    # Update stats
    bot.stats['violations_detected'] += 1
    
    guild = message.guild
    guild_id = str(guild.id)
    
    # Delete the violating message
    try:
        await message.delete()
        logger.info(f"Deleted {violation_type} violation from {user.id} in {guild.name}")
    except discord.Forbidden:
        logger.warning(f"No permission to delete message in {guild.name}")
    except discord.NotFound:
        pass  # Message already deleted
    
    # Log the violation
    await log_violation(guild, user, content, violation_type, details)
    
    # Handle warnings if enabled
    if not use_warnings:
        # Just send a notification
        notification = await message.channel.send(
            f"⚠️ {user.mention}, your message was removed for violating community guidelines.",
            delete_after=10
        )
        return
    
    # Initialize user warnings if not exists
    user_id = str(user.id)
    if user_id not in warning_list[guild_id]:
        warning_list[guild_id][user_id] = {
            'count': 0,
            'last_warning': datetime.now().isoformat(),
            'history': []
        }
    
    # Add warning
    warning_list[guild_id][user_id]['count'] += 1
    warning_list[guild_id][user_id]['last_warning'] = datetime.now().isoformat()
    warning_list[guild_id][user_id]['history'].append({
        'timestamp': datetime.now().isoformat(),
        'type': violation_type,
        'content': content[:200]  # Store truncated content
    })
    
    await CyanixDataManager.save_warnings(warning_list)
    
    current_warnings = warning_list[guild_id][user_id]['count']
    warnings_left = max(0, warnings_limit - current_warnings)
    
    # Check if user should be muted
    if current_warnings >= warnings_limit:
        # Reset warnings and mute
        warning_list[guild_id][user_id]['count'] = 0
        await CyanixDataManager.save_warnings(warning_list)
        
        # Mute the user
        await tempmute(message.channel, user, f"Reached {warnings_limit} warnings")
    else:
        # Send warning notification
        embed = discord.Embed(
            title="⚠️ Content Warning",
            description=f"{user.mention}, your message was removed for violating community guidelines.",
            color=discord.Color.orange()
        )
        
        embed.add_field(name="Warning Count", value=f"{current_warnings}/{warnings_limit}", inline=True)
        embed.add_field(name="Warnings Left", value=str(warnings_left), inline=True)
        
        if details and 'categories' in details:
            flagged = [cat for cat, flagged in details['categories'].items() if flagged]
            if flagged:
                embed.add_field(name="Violation Type", value=", ".join(flagged), inline=False)
        
        await message.channel.send(embed=embed, delete_after=15)

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    """Handle edited messages"""
    if before.content == after.content:
        return
    
    # Re-check edited messages
    await on_message(after)

# ========== ERROR HANDLING ==========

@bot.event
async def on_command_error(ctx: commands.Context, error):
    """Handle command errors"""
    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(
            title="❌ Permission Denied",
            description="You don't have permission to use this command.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, ephemeral=True)
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore unknown commands
    else:
        logger.error(f"Command error: {error}")
        
        embed = discord.Embed(
            title="❌ An Error Occurred",
            description="An unexpected error occurred. Please try again later.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, ephemeral=True)

# ========== MAIN EXECUTION ==========

if __name__ == "__main__":
    # Validate environment variables
    BOT_TOKEN = os.getenv("token")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    if not BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN not found in environment variables")
        exit(1)
    
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not found. Some features may not work correctly.")
    
    # Load triggering words if enabled
    USE_TRIGGERING_WORDS = os.getenv("USE_TRIGGERING_WORDS", "False").lower() == "true"
    TRIGGERING_WORDS = []
    
    if USE_TRIGGERING_WORDS:
        TRIGGERING_WORDS_FILE = os.getenv("TRIGGERING_WORDS")
        if TRIGGERING_WORDS_FILE and os.path.exists(TRIGGERING_WORDS_FILE):
            try:
                with open(TRIGGERING_WORDS_FILE, "r") as file:
                    TRIGGERING_WORDS = [word.strip() for word in file.read().split(",")]
                logger.info(f"Loaded {len(TRIGGERING_WORDS)} triggering words")
            except Exception as e:
                logger.error(f"Error loading triggering words: {e}")
        else:
            logger.warning("TRIGGERING_WORDS_FILE not specified or not found")
    
    # Start the bot
    logger.info("Starting Cyanix AI bot...")
    try:
        bot.run(BOT_TOKEN)
    except discord.LoginFailure:
        logger.error("Invalid bot token. Please check your DISCORD_BOT_TOKEN.")
    except KeyboardInterrupt:
        logger.info("Bot shutting down...")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")