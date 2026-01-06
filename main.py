import discord
import os
import json
import pomice
from discord.ext import tasks
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from collections import deque
from datetime import datetime

test_server = 1005623551962918933

@tasks.loop(seconds=5)
async def dashboard_updater():
    for guild in client.guilds:
        player: pomice.Player = guild.voice_client
        if not player:
            continue

        if player.is_connected and player.is_playing:
            await update_dashboard(player)

class discordClient(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="rr>", intents=discord.Intents.all())
        self.synced = False
        self.database_synced = False
        self.pomice = pomice.NodePool()
    
    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced:
            await tree.sync()
            self.synced = True
            print("Command tree synced")
        if not self.database_synced:
            self.database_synced = True
            print("Database Initialized")
        if not dashboard_updater.is_running():
            dashboard_updater.start()

        
        # Create Pomice node
        await self.pomice.create_node(
            bot=self,
            host='127.0.0.1',
            port=8080,
            password='youshallnotpass',
            identifier='MAIN'
        )
        print(f"Pomice node created")
        
        await self.change_presence(activity=discord.Game(name="/help"))
        print(f"{self.user}: Initialized")

    async def on_pomice_track_start(self, player, track):
        if player and player.channel:
            status = f"🔴 {track.title} - {track.author}"
            try:
                await player.channel.edit(status=status)
            except Exception as e:
                print(f"Failed to edit channel status: {e}")
        
        add_activity(player, f"▶️ Now playing: **{track.title}**")
        await update_dashboard(player)

    async def on_pomice_track_end(self, player, track, reason):
        if not hasattr(player, 'custom_queue'):
            player.custom_queue = []
        if not hasattr(player, 'loop'):
            player.loop = False

        if player.loop:
            return await player.play(track)
        
        if not player.custom_queue:
            if player.channel:
                try:
                    await player.channel.edit(status=None)
                except Exception as e:
                    print(f"Failed to clear channel status: {e}")
            add_activity(player, "⏹️ Playback finished.")
            await update_dashboard(player)
            return
        
        next_song = player.custom_queue.pop(0)
        await player.play(next_song)

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        with open('kicklist.json', 'r') as f1:
            kick_data = json.load(f1)
        if not member.bot:
            if not before.channel and after.channel:
                if str(after.channel.id) in kick_data:
                    kick_list = kick_data[str(after.channel.id)]
                    for kicked in kick_list:
                        if int(kicked) == member.id:
                            await member.move_to(None)
            elif before.channel and not after.channel:
                if not before.channel.members:
                    if str(before.channel.id) in kick_data:
                        del kick_data[str(before.channel.id)]
                        with open('kicklist.json', 'w') as f1:
                            json.dump(kick_data, f1)
        with open('music_voice_channels.json', 'r') as f:
            data = json.load(f)
        if not member.bot:
            if not before.channel and after.channel:
                if str(member.guild.id) in data:
                    channelInData = False
                    for channel_id in list(data[str(member.guild.id)]['channels']):
                        if after.channel.id == int(channel_id):
                            channelInData = True
                    if channelInData:
                        interactive_ch = await client.fetch_channel(after.channel.id)
                        if not interactive_ch is None:
                            category_id = interactive_ch.category_id
                            if not category_id is None:
                                category = discord.utils.get(member.guild.categories, id=int(category_id))
                                vc = await member.guild.create_voice_channel(f"{member.name}'s VC", category=category)
                                return await member.move_to(vc)
                            else:
                                vc = await member.guild.create_voice_channel(f"{member.name}'s VC")
                                return await member.move_to(vc)
                else:
                    return
                channel = discord.utils.get(member.guild.channels, name=f"{member.name}'s VC")
                if not channel is None:
                    if after.channel.id != channel.id:
                        await channel.delete()
            elif before.channel and not after.channel:
                channel = discord.utils.get(member.guild.channels, name=f"{member.name}'s VC")
                if not channel is None:
                    await channel.delete()

    async def on_guild_remove(self, guild):
        with open('blacklist.json', 'r') as f:
            data = json.load(f)
        try:
            del data[str(guild.id)]
            with open('blacklist.json', 'w') as f:
                json.dump(data, f)
        except:
            pass

        with open('music_voice_channels.json', 'r') as f:
            data = json.load(f)
        try:
            del data[str(guild.id)]
            with open('music_voice_channels.json', 'w') as f:
                json.dump(data, f)
        except:
            pass

client = discordClient()
#tree = app_commands.CommandTree(client)
tree = client.tree

os.chdir(os.getcwd())

NOARTWORK = "https://img.freepik.com/premium-vector/free-vector-youtube-icon-logo-social-media-logo_901408-454.jpg?w=740"

def add_activity(player: pomice.Player, text: str):
    """Add an activity to the player's recent activities log"""
    if not hasattr(player, 'recent_activities'):
        player.recent_activities = deque(maxlen=10)
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    activity_entry = f"`{timestamp}` {text}"
    
    # Limit each activity entry to 100 characters
    if len(activity_entry) > 100:
        activity_entry = activity_entry[:97] + "..."
    
    player.recent_activities.appendleft(activity_entry)

def truncate_text(text: str, max_length: int) -> str:
    """Truncate text to a maximum length"""
    if len(text) > max_length:
        return text[:max_length - 3] + "..."
    return text

async def ensure_dashboard_channel(player: pomice.Player):
    """Ensure the dashboard channel and message are still valid, recreate if needed"""
    if not hasattr(player, 'dashboard_channel_id') or not hasattr(player, 'dashboard_message_id'):
        return False
    
    try:
        channel = await client.fetch_channel(player.dashboard_channel_id)
        message = await channel.fetch_message(player.dashboard_message_id)
        player.dashboard_message = message
        return True
    except (discord.errors.NotFound, discord.errors.Forbidden, AttributeError):
        player.dashboard_message = None
        player.dashboard_channel_id = None
        player.dashboard_message_id = None
        return False

async def update_dashboard(player: pomice.Player, force_new=False):
    """Update or create the centralized music dashboard"""
    if not player.is_connected:
        return

    # Check if we need to ensure/recreate dashboard
    if not force_new and hasattr(player, 'dashboard_message') and player.dashboard_message:
        if not await ensure_dashboard_channel(player):
            force_new = True

    embed = discord.Embed(
        title="🎵 Music Dashboard",
        color=discord.Color.red() if player.is_paused else discord.Color.blue(),
        timestamp=datetime.now()
    )

    # NOW PLAYING SECTION
    if player.current:
        track = player.current
        duration = await convert(int(track.length), auto_format=False)
        position = await convert(int(player.position), auto_format=False)
        requester = getattr(player, 'current_requester', 'Unknown')

        track_title = truncate_text(track.title, 80)
        track_author = truncate_text(track.author or "Unknown", 50)

        status_title = (
            "⏸️ Now Paused"
            if player.is_paused
            else "▶️ Now Playing"
        )

        now_playing_text = (
            f"**{track_title}**\n"
            f"🎤 Artist: {track_author}\n"
            f"⏱️ Duration: `{position}` / `{duration}`\n"
            f"👤 Requested by: {truncate_text(requester, 30)}"
        )

        embed.add_field(
            name=status_title,
            value=now_playing_text,
            inline=False
        )
    else:
        embed.add_field(name="▶️ Now Playing", value="*Nothing is playing*", inline=False)

    # VOLUME & LOOP STATUS (Small section)
    volume = player.volume
    loop_status = "🔁 On" if getattr(player, 'loop', False) else "➡️ Off"
    embed.add_field(name="🔊 Volume", value=f"`{volume}%`", inline=True)
    embed.add_field(name="🔄 Loop", value=loop_status, inline=True)
    embed.add_field(name="🔗 Connected", value=f"{player.channel.mention}", inline=True)

    # QUEUE SECTION (First 3 songs)
    if hasattr(player, 'custom_queue') and player.custom_queue:
        queue_text = ""
        for i, track in enumerate(player.custom_queue[:3]):
            truncated_title = truncate_text(track.title, 60)
            queue_text += f"`{i+1}.` **{truncated_title}**\n"
        if len(player.custom_queue) > 3:
            queue_text += f"\n*...and {len(player.custom_queue) - 3} more*"
        
        # Limit queue section to 1000 characters
        queue_text = truncate_text(queue_text, 1000)
        embed.add_field(name="📋 Up Next", value=queue_text, inline=False)
    else:
        embed.add_field(name="📋 Up Next", value="*Queue is empty*", inline=False)

    # RECENT ACTIVITIES (Large section)
    if hasattr(player, 'recent_activities') and player.recent_activities:
        # Take up to 8 activities and ensure total doesn't exceed 1024 chars
        activities_list = list(player.recent_activities)[:8]
        activity_text = "\n".join(activities_list)
        
        # Limit activities section to 1024 characters (Discord field limit)
        activity_text = truncate_text(activity_text, 1024)
        embed.add_field(name="📜 Recent Activity", value=activity_text, inline=False)
    else:
        embed.add_field(name="📜 Recent Activity", value="*No recent activity*", inline=False)

    embed.set_footer(text="Use /help to see all available commands")

    # Send or update the dashboard
    try:
        if force_new or not hasattr(player, 'dashboard_message') or player.dashboard_message is None:
            # Create new dashboard
            if hasattr(player, 'dashboard_channel_id'):
                try:
                    channel = await client.fetch_channel(player.dashboard_channel_id)
                except:
                    channel = player.interaction.channel if hasattr(player, 'interaction') else None
            else:
                channel = player.interaction.channel if hasattr(player, 'interaction') else None
            
            if channel:
                # Delete old dashboard if it exists
                if hasattr(player, 'dashboard_message') and player.dashboard_message:
                    try:
                        await player.dashboard_message.delete()
                    except:
                        pass
                
                player.dashboard_message = await channel.send(embed=embed)
                player.dashboard_channel_id = channel.id
                player.dashboard_message_id = player.dashboard_message.id
        else:
            # Update existing dashboard
            try:
                await player.dashboard_message.edit(embed=embed)
            except discord.errors.NotFound:
                await update_dashboard(player, force_new=True)
            except Exception as e:
                print(f"Error updating dashboard: {e}")
                await update_dashboard(player, force_new=True)
    except Exception as e:
        print(f"Failed to create/update dashboard: {e}")

async def simple_embed(content: str, color: discord.Color=discord.Color.red()):
    embed = discord.Embed(title=None, description=content, color=color)
    return embed

async def comp_embed(title: str, description: str, color: discord.Color=discord.Color.red(), author_name: str=None, author_avatar_url: str=None, footer: str=None):
    embed = discord.Embed(title=title, description=description, color=color)
    if author_name is not None and author_avatar_url is not None:
        embed.set_author(name=author_name, icon_url=author_avatar_url)
    if footer is not None:
        embed.set_footer(text=footer)
    
    return embed

async def convert(milliseconds: int, auto_format=False):
    """Convert milliseconds to hours, minutes and seconds"""
    seconds = round(milliseconds) / 1000
    min, sec = divmod(seconds, 60)
    hour, min = divmod(min, 60)
    converted = '%d:%02d:%02d' % (hour, min, sec)
    if auto_format:
        final = "`" + converted + "`"
    else:
        final = converted
    return final

async def isQueueEmpty(player: pomice.Player):
    if not hasattr(player, 'custom_queue'):
        return True
    return not player.custom_queue

@tree.command(name="help", description="Shows help")
@app_commands.describe(command="The command to show help")
async def help_command(interaction: discord.Interaction, command: str=None):
    if command is None:
        embed = await comp_embed("Commands", description="List of commands you can use", author_name=client.user.display_name, author_avatar_url=client.user.display_avatar.url)
        for cmd in tree.get_commands():
            embed.add_field(name=f"/{cmd.name}", value=cmd.description, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        cmd_for_help = tree.get_command(command)
        if cmd_for_help is None:
            return await interaction.response.send_message(f"No command called {command} found", ephemeral=True)
        embed = await comp_embed(f"Help for {cmd_for_help.name}", description=f"{cmd_for_help.description}", author_name=client.user.display_name, author_avatar_url=client.user.display_avatar.url)
        parm_str = ""
        for parm in cmd_for_help.parameters:
            parm_str = parm_str + f"{parm.name}: {parm.description}\n"
        embed.add_field(name="Parameters", value=parm_str)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="join", description="Joins the current voice channel you are in or a specific voice channel")
@app_commands.describe(channel="The channel to join")
async def join_command(interaction: discord.Interaction, channel: discord.VoiceChannel=None):
    if channel is None:
        if not interaction.user.voice is None:
            channel = interaction.user.voice.channel
        else:
            return await interaction.response.send_message("You are not in a voice channel!", ephemeral=True)
    
    player = interaction.guild.voice_client

    if player is not None:
        if player.is_connected:
            return await interaction.response.send_message("Bot is already in a voice channel! Use /fuckoff to disconnect me!", ephemeral=True)

    player = await channel.connect(cls=pomice.Player)
    player.custom_queue = []
    player.loop = False
    player.dashboard_message = None
    player.dashboard_channel_id = interaction.channel.id
    player.recent_activities = deque(maxlen=10)
    player.interaction = interaction

    await interaction.guild.change_voice_state(channel=channel, self_deaf=True)
    
    add_activity(player, f"✅ Bot joined **{channel.name}**")
    await update_dashboard(player, force_new=True)
    try:
        await interaction.response.send_message(f"✅ Connected to `{channel.name}` - Dashboard created!", ephemeral=True)
    except:
        pass

@tree.command(name="fuckoff", description="Leaves the channel that the bot is in (disconnect)")
async def leave_command(interaction: discord.Interaction):
    with open('blacklist.json', 'r') as f:
            data = json.load(f)
    if str(interaction.guild.id) in data:
        if str(interaction.user.id) in data[str(interaction.guild.id)]:
            blacklisted = True
        else:
            blacklisted = False
    else:
        blacklisted = False
    
    player = interaction.guild.voice_client

    if player is None:
        return await interaction.response.send_message("bot is not connected to any voice channel", ephemeral=True)
    
    if player.is_playing:
        return await interaction.response.send_message("Bot is playing a song! Use `/clear` to stop the music and clear the queue", ephemeral=True)
    if blacklisted:
        return await interaction.response.send_message(f"You are blacklisted in `{interaction.guild.name}`! So you can't let the bot leave the voice channel!", ephemeral=True)
    
    if hasattr(player, 'dashboard_message') and player.dashboard_message:
        try:
            await player.dashboard_message.delete()
        except discord.errors.NotFound:
            pass
            
    if player.channel:
        try:
            await player.channel.edit(status=None)
        except Exception as e:
            print(f"Failed to clear channel status on disconnect: {e}")
    await player.disconnect()
    await interaction.response.send_message(embed=await simple_embed("Disconnected"), ephemeral=True)

@tree.command(name="play", description="Play a song")
@app_commands.describe(search="The thing to search for")
async def play_command(interaction: discord.Interaction, search: str):
    try:
        if not interaction.user.voice:
            return await interaction.response.send_message("Join a voice channel first!", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)

        player: pomice.Player = interaction.guild.voice_client
        if not player:
            player_check = interaction.guild.voice_client

            if player_check is not None:
                if player_check.is_connected:
                    return await interaction.followup.send("Bot is already in a voice channel! Use /fuckoff to disconnect me!", ephemeral=True)
            
            player = await interaction.user.voice.channel.connect(cls=pomice.Player)
            player.custom_queue = []
            player.loop = False
            player.dashboard_channel_id = interaction.channel.id
            player.recent_activities = deque(maxlen=10)
            await interaction.guild.change_voice_state(channel=interaction.user.voice.channel, self_deaf=True)
        
        results = await player.get_tracks(search)
        if not results:
            return await interaction.followup.send(f"No songs found for `{search}`.", ephemeral=True)

        if isinstance(results, pomice.Playlist):
            song = results.tracks[0]
        else:
            song = results[0]
        
        if not hasattr(player, 'custom_queue'):
            player.custom_queue = []
            player.loop = False
            player.recent_activities = deque(maxlen=10)

        requester_name = interaction.user.display_name
        
        if not player.is_playing and not player.custom_queue:
            await player.play(song)
            player.current_requester = requester_name
            add_activity(player, f"🎵 **{interaction.user.display_name}** added **{truncate_text(song.title, 40)}**")
            response = f"▶️ Now playing: **{truncate_text(song.title, 60)}**"
        else:
            player.custom_queue.append(song)
            add_activity(player, f"➕ **{interaction.user.display_name}** queued **{truncate_text(song.title, 40)}**")
            response = f"➕ Added to queue: **{truncate_text(song.title, 60)}**"
        
        player.interaction = interaction
        await update_dashboard(player)
        await interaction.followup.send(response, ephemeral=True)
    except Exception as e:
        try:
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)
        except:
            print(f"Error in play command: {e}")

@tree.command(name="clear", description="Stop the current song and clear the queue")
async def clear_command(interaction: discord.Interaction):
    try:
        with open('blacklist.json', 'r') as f:
            data = json.load(f)
        if str(interaction.guild.id) in data:
            if str(interaction.user.id) in data[str(interaction.guild.id)]:
                blacklisted = True
            else:
                blacklisted = False
        else:
            blacklisted = False
        if not blacklisted:
            player = interaction.guild.voice_client

            if player is None:
                return await interaction.response.send_message("Bot is not connected to any voice channel", ephemeral=True)
            
            if player.is_playing:
                if not player.loop:
                    if player.custom_queue:
                        player.custom_queue.clear()
                    await player.stop()
                    add_activity(player, f"⏹️ **{interaction.user.display_name}** cleared playback")
                    await update_dashboard(player)
                    return await interaction.response.send_message("⏹️ Playback stopped and queue cleared", ephemeral=True)
                else:
                    return await interaction.response.send_message("Loop is on! use `/loop` to turn off looping and then use clear command!", ephemeral=True)
            else:
                return await interaction.response.send_message("Nothing is playing", ephemeral=True)
        else:
            return await interaction.response.send_message(f"You are blacklisted in {interaction.guild.name}! You can't let the bot stop playing a song!", ephemeral=True)
    except Exception as e:
        try:
            await interaction.response.send_message(str(e), ephemeral=True)
        except:
            print(f"Error in clear command: {e}")

@tree.command(name="stop", description="Pause the current song")
async def pause_command(interaction: discord.Interaction):
    with open('blacklist.json', 'r') as f:
        data = json.load(f)
    if str(interaction.guild.id) in data:
        if str(interaction.user.id) in data[str(interaction.guild.id)]:
            blacklisted = True
        else:
            blacklisted = False
    else:
        blacklisted = False
    if blacklisted:
        return await interaction.response.send_message(f"You are blacklisted in {interaction.guild.name}! You can't pause a song!", ephemeral=True)
    
    player = interaction.guild.voice_client

    if player is None:
        return await interaction.response.send_message("Bot is not connected to any voice channel", ephemeral=True)
    
    if not player.is_paused:
        if player.is_playing:
            await player.set_pause(True)
            add_activity(player, f"⏸️ **{interaction.user.display_name}** paused playback")
            await update_dashboard(player)
            return await interaction.response.send_message("⏸️ Playback paused", ephemeral=True)
        else:
            return await interaction.response.send_message("Nothing is playing", ephemeral=True)
    else:
        return await interaction.response.send_message("Playback is already paused", ephemeral=True)

@tree.command(name="resume", description="Resume the currently paused song")
async def resume_command(interaction: discord.Interaction):
    with open('blacklist.json', 'r') as f:
        data = json.load(f)
    if str(interaction.guild.id) in data:
        if str(interaction.user.id) in data[str(interaction.guild.id)]:
            blacklisted = True
        else:
            blacklisted = False
    else:
        blacklisted = False
    if blacklisted:
        return await interaction.response.send_message(f"You are blacklisted in {interaction.guild.name}! You can't resume a song!", ephemeral=True)
    
    player = interaction.guild.voice_client

    if player is None:
        return await interaction.response.send_message("bot is not connected to any voice channel", ephemeral=True)
    
    if player.is_paused:
        await player.set_pause(False)
        add_activity(player, f"▶️ **{interaction.user.display_name}** resumed playback")
        await update_dashboard(player)
        return await interaction.response.send_message("▶️ Playback resumed", ephemeral=True)
    else:
        return await interaction.response.send_message("playback is not paused", ephemeral=True)

@tree.command(name="volume", description="Changes the volume")
@app_commands.describe(to="The volume to adjust to (between 1 and 100)")
async def volume_command(interaction: discord.Interaction, to: int):
    with open('blacklist.json', 'r') as f:
        data = json.load(f)
    if str(interaction.guild.id) in data:
        if str(interaction.user.id) in data[str(interaction.guild.id)]:
            blacklisted = True
        else:
            blacklisted = False
    else:
        blacklisted = False
    if blacklisted:
        return await interaction.response.send_message(f"You are blacklisted in {interaction.guild.name}! You can't change the volume!", ephemeral=True)
    if not interaction.guild.voice_client:
        return await interaction.response.send_message("I am not even in a voice channel!", ephemeral=True)
    if to > 100:
        return await interaction.response.send_message("Volume should be between 1 and 100", ephemeral=True)
    elif to < 1:
        return await interaction.response.send_message("Volume should be between 1 and 100", ephemeral=True)
    
    player = interaction.guild.voice_client

    await player.set_volume(to)
    add_activity(player, f"🔊 **{interaction.user.display_name}** set volume to **{to}%**")
    await update_dashboard(player)
    await interaction.response.send_message(f"🔊 Volume set to {to}%", ephemeral=True)

@tree.command(name="loop", description="Toggle looping the current song")
async def loop_command(interaction: discord.Interaction):
    with open('blacklist.json', 'r') as f:
        data = json.load(f)
    if str(interaction.guild.id) in data:
        if str(interaction.user.id) in data[str(interaction.guild.id)]:
            blacklisted = True
        else:
            blacklisted = False
    else:
        blacklisted = False
    if blacklisted:
        return await interaction.response.send_message(f"You are blacklisted in {interaction.guild.name}! You can't loop a song!", ephemeral=True)
    if not interaction.guild.voice_client:
        return await interaction.response.send_message("I am not in a voice channel!", ephemeral=True)
    elif not interaction.user.voice:
        return await interaction.response.send_message("You are not in a voice channel!", ephemeral=True)
    else:
        player: pomice.Player = interaction.guild.voice_client
    
    if not hasattr(player, 'loop'):
        player.loop = False
    
    player.loop = not player.loop
    
    if player.loop:
        add_activity(player, f"🔁 **{interaction.user.display_name}** enabled loop")
        await update_dashboard(player)
        return await interaction.response.send_message("🔁 Loop enabled", ephemeral=True)
    else:
        add_activity(player, f"➡️ **{interaction.user.display_name}** disabled loop")
        await update_dashboard(player)
        return await interaction.response.send_message("➡️ Loop disabled", ephemeral=True)

@tree.command(name="queue", description="Check the queue")
async def queue_command(interaction: discord.Interaction):
    if not interaction.guild.voice_client:
        return await interaction.response.send_message("I'm not in a voice channel!", ephemeral=True)
    elif not interaction.user.voice:
        return await interaction.response.send_message("You are not in a voice channel!", ephemeral=True)
    else:
        player: pomice.Player = interaction.guild.voice_client

    if await isQueueEmpty(player):
        return await interaction.response.send_message("Queue is empty", ephemeral=True)
    
    embed = discord.Embed(title="Queue", description=f"Current song: {player.current.title}", color=discord.Color.blue())
    queue = player.custom_queue
    song_count = 0
    for song in queue:
        song_count += 1
        embed.add_field(name=f"Song {song_count}", value=f"`{truncate_text(song.title, 80)}`", inline=False)

    return await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="removesonginqueue", description="Removes a song in the queue")
@app_commands.describe(position="The position of the song in the queue")
async def removeSongInQueue_command(interaction: discord.Interaction, position: int):
    with open('blacklist.json', 'r') as f:
        data = json.load(f)
    if str(interaction.guild.id) in data:
        if str(interaction.user.id) in data[str(interaction.guild.id)]:
            blacklisted = True
        else:
            blacklisted = False
    else:
        blacklisted = False
    if blacklisted:
        return await interaction.response.send_message(f"You are blacklisted in {interaction.guild.name}! You can't remove a song in queue!", ephemeral=True)

    if not interaction.guild.voice_client:
        return await interaction.response.send_message("I'm not in a voice channel!", ephemeral=True)
    elif not interaction.user.voice:
        return await interaction.response.send_message("You are not in a voice channel!", ephemeral=True)
    else:
        player: pomice.Player = interaction.guild.voice_client

    if await isQueueEmpty(player):
        return await interaction.response.send_message("Queue is empty", ephemeral=True)

    if position < 1 or position > len(player.custom_queue):
        return await interaction.response.send_message(f"Invalid position. The queue has {len(player.custom_queue)} songs.", ephemeral=True)

    removed_song = player.custom_queue.pop(position - 1)
    add_activity(player, f"❌ **{interaction.user.display_name}** removed **{truncate_text(removed_song.title, 40)}**")
    await update_dashboard(player)
    await interaction.response.send_message(f"❌ Removed `{truncate_text(removed_song.title, 60)}` from queue", ephemeral=True)

@tree.command(name="nowplaying", description="Check the song that is currently playing")
async def nowplaying_command(interaction: discord.Interaction):
    player = interaction.guild.voice_client

    if player is None:
        return await interaction.response.send_message("Bot is not connected to any voice channel", ephemeral=True)
    
    if player.is_playing:
        track = player.current
        requester = getattr(player, 'current_requester', 'Unknown')
        duration = await convert(int(track.length), auto_format=False)
        
        embed = discord.Embed(
            title=f"🎵 Now Playing",
            description=f"**{truncate_text(track.title, 100)}**",
            color=discord.Color.blue()
        )
        embed.add_field(name="🎤 Artist", value=truncate_text(track.author or "Unknown", 50), inline=True)
        embed.add_field(name="⏱️ Duration", value=f"`{duration}`", inline=True)
        embed.add_field(name="👤 Requested by", value=truncate_text(requester, 30), inline=True)
        if hasattr(track, 'uri') and track.uri:
            embed.add_field(name="🔗 Link", value=track.uri, inline=False)
        if hasattr(track, 'artwork_url') and track.artwork_url:
            embed.set_thumbnail(url=track.artwork_url)
        else:
            embed.set_thumbnail(url=NOARTWORK)
        
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message("Nothing is playing right now", ephemeral=True)

@client.tree.command(name="search", description="Search a song with the query provided")
@app_commands.describe(search="The query to search for")
async def search_command(interaction: discord.Interaction, search: str):
    if not interaction.user.voice:
        return await interaction.response.send_message("Join a voice channel first!", ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    player: pomice.Player = interaction.guild.voice_client
    if not player:
        if interaction.guild.voice_client and interaction.guild.voice_client.is_connected:
            return await interaction.followup.send("Bot is already in a voice channel!", ephemeral=True)
        player = await interaction.user.voice.channel.connect(cls=pomice.Player)
        player.custom_queue = []
        player.loop = False
        player.dashboard_channel_id = interaction.channel.id
        player.recent_activities = deque(maxlen=10)
        await interaction.guild.change_voice_state(channel=interaction.user.voice.channel, self_deaf=True)

    tracks = await player.get_tracks(search)
    if not tracks:
        return await interaction.followup.send("No tracks found.", ephemeral=True)

    if isinstance(tracks, pomice.Playlist):
        tracks = tracks.tracks

    tracks = tracks[:5]

    class SearchView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
            self.choice: int | None = None

        async def disable_all(self):
            for item in self.children:
                item.disabled = True

        async def on_timeout(self):
            await self.disable_all()
            try:
                await message.edit(view=self)
            except discord.NotFound:
                pass

        async def handle_choice(self, interaction_: discord.Interaction, index: int):
            self.choice = index
            await self.disable_all()
            await interaction_.response.defer()
            self.stop()

        @discord.ui.button(label="1", style=discord.ButtonStyle.primary)
        async def one(self, interaction_: discord.Interaction, button: discord.ui.Button):
            await self.handle_choice(interaction_, 0)

        @discord.ui.button(label="2", style=discord.ButtonStyle.primary)
        async def two(self, interaction_: discord.Interaction, button: discord.ui.Button):
            await self.handle_choice(interaction_, 1)

        @discord.ui.button(label="3", style=discord.ButtonStyle.primary)
        async def three(self, interaction_: discord.Interaction, button: discord.ui.Button):
            await self.handle_choice(interaction_, 2)

        @discord.ui.button(label="4", style=discord.ButtonStyle.primary)
        async def four(self, interaction_: discord.Interaction, button: discord.ui.Button):
            await self.handle_choice(interaction_, 3)

        @discord.ui.button(label="5", style=discord.ButtonStyle.primary)
        async def five(self, interaction_: discord.Interaction, button: discord.ui.Button):
            await self.handle_choice(interaction_, 4)

        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
        async def cancel(self, interaction_: discord.Interaction, button: discord.ui.Button):
            self.choice = None
            await self.disable_all()
            await interaction_.response.send_message("Search cancelled.", ephemeral=True)
            self.stop()

    description = "\n".join(
        f"**{i+1}. {truncate_text(t.title, 70)}**" for i, t in enumerate(tracks)
    )

    embed = discord.Embed(
        title="Select a track",
        description=description,
        color=discord.Color.blue()
    )

    view = SearchView()
    message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    await view.wait()

    if view.choice is None:
        return

    chosen = tracks[view.choice]
    requester_name = interaction.user.display_name

    if not player.is_playing and not player.is_paused:
        await player.play(chosen)
        player.current_requester = requester_name
        add_activity(player, f"🎵 **{requester_name}** added **{truncate_text(chosen.title, 40)}**")
        response = f"▶️ Now playing: **{truncate_text(chosen.title, 60)}**"
    else:
        player.custom_queue.append(chosen)
        add_activity(player, f"➕ **{requester_name}** queued **{truncate_text(chosen.title, 40)}**")
        response = f"➕ Added to queue: **{truncate_text(chosen.title, 60)}**"

    try:
        await message.delete()
    except:
        pass
    player.interaction = interaction
    await update_dashboard(player)
    await interaction.followup.send(response, ephemeral=True)

@tree.command(name="skip", description="skip the current song")
async def skip_command(interaction: discord.Interaction):
    with open('blacklist.json', 'r') as f:
        data = json.load(f)
    if str(interaction.guild.id) in data:
        if str(interaction.user.id) in data[str(interaction.guild.id)]:
            blacklisted = True
        else:
            blacklisted = False
    else:
        blacklisted = False
    
    player = interaction.guild.voice_client

    if player is None:
        return await interaction.response.send_message("Bot is not connected to any voice channel", ephemeral=True)
    
    if blacklisted:
        return await interaction.response.send_message(f"You are blacklisted in {interaction.guild.name}! You can't skip a song!", ephemeral=True)
    
    maximum_skip_threshold = 3
    if maximum_skip_threshold > 10:
        return await interaction.followup.send("Please notify the developers about this error\nE: maximum_skip_threshold should not be greater than 10", ephemeral=True)
    if player.is_playing:
        member_count = len(player.channel.members)
        if member_count - 1 >= maximum_skip_threshold:
            await interaction.response.defer(thinking=True)
            class skipView(discord.ui.View):
                def __init__(self, channel: discord.VoiceChannel, embed: discord.Embed):
                    super().__init__(timeout=30)
                    self.channel = channel
                    self.embed = embed
                    self.voted = []
                    self.completed = False

                async def on_timeout(self):
                    for item in self.children:
                        item.disabled = True
                    try:
                        if not self.completed:
                            await interaction.edit_original_response(content="⏱️ Vote skip timed out", embed=None, view=self)
                    except discord.errors.NotFound:
                        pass
                    self.stop()
                
                @discord.ui.button(label="skip", style=discord.ButtonStyle.red, custom_id="skip_button")
                async def skip_button(self, interaction_: discord.Interaction, button: discord.ui.Button):
                    if interaction_.user.voice.channel == self.channel:
                        for voted_user in self.voted:
                            if voted_user == interaction_.user.id:
                                return await interaction_.response.send_message("You already voted!", ephemeral=True)
                        skip_vote = int(self.embed.footer.text.split(": ")[1].split("/")[0])
                        skip_vote += 1
                        if skip_vote >= maximum_skip_threshold:
                            self.completed = True
                            await player.stop()
                            add_activity(player, f"⏭️ Vote skip succeeded ({skip_vote}/{maximum_skip_threshold})")
                            await update_dashboard(player)
                            try:
                                await interaction.edit_original_response(content=f"⏭️ Skipped by vote ({skip_vote}/{maximum_skip_threshold})", embed=None, view=None)
                                await interaction_.response.send_message("Voted!", ephemeral=True)
                            except discord.errors.NotFound:
                                await interaction_.response.send_message("Voted! Song skipped.", ephemeral=True)
                            self.stop()
                        else:
                            self.voted.append(interaction_.user.id)
                            embed_ = await comp_embed(None, "Vote to skip the current song", author_name=interaction.user.display_name, author_avatar_url=interaction.user.display_avatar.url)
                            embed_.set_footer(text=f"Current people voted to skip: {str(skip_vote)}/{maximum_skip_threshold}")
                            self.embed = embed_
                            try:
                                await interaction.edit_original_response(embed=embed_, view=self)
                                await interaction_.response.send_message("Voted!", ephemeral=True)
                            except discord.errors.NotFound:
                                await interaction_.response.send_message("Voted! (The original message was deleted).", ephemeral=True)
                    else:
                        return await interaction_.response.send_message("You can't skip because you are not in the same voice channel!", ephemeral=True)

            embed = await comp_embed(None, "Vote to skip the current song", author_name=interaction.user.display_name, author_avatar_url=interaction.user.display_avatar.url, footer=f"Current people voted to skip: 0/{maximum_skip_threshold}")
            await interaction.followup.send(embed=embed, view=skipView(channel=interaction.user.voice.channel, embed=embed))
        else:
            await player.stop()
            add_activity(player, f"⏭️ **{interaction.user.display_name}** skipped the song")
            await update_dashboard(player)
            return await interaction.followup.send("⏭️ Song skipped", ephemeral=True)
    else:
        return await interaction.followup.send("Nothing is playing", ephemeral=True)
    
@tree.command(name="votekick", description="Start a vote to kick a specific member from the current voice chat until the music session ends")
@app_commands.describe(member="The member to start a vote")
async def votekick_command(interaction: discord.Interaction, member: discord.Member):
    with open('blacklist.json', 'r') as f:
        data = json.load(f)
    if str(interaction.guild.id) in data:
        if str(interaction.user.id) in data[str(interaction.guild.id)]:
            blacklisted = True
        else:
            blacklisted = False
    else:
        blacklisted = False
    
    player = interaction.guild.voice_client

    if player is None:
        return await interaction.response.send_message("Bot is not connected to any voice channel", ephemeral=True)
    
    if blacklisted:
        return await interaction.response.send_message(f"You are blacklisted in {interaction.guild.name}! You can't vote kick!", ephemeral=True)
    
    if member == interaction.user:
        return await interaction.response.send_message(f"You can't vote kick yourself!", ephemeral=True)
    maximum_vote_threshold = 3
    if maximum_vote_threshold > 10:
        return await interaction.response.send_message("Please notify the developers about this error\nE: maximum_vote_threshold should not be greater than 10", ephemeral=True)
    member_count = len(player.channel.members)
    if member_count - 1 >= maximum_vote_threshold:
        class voteView(discord.ui.View):
            def __init__(self, channel: discord.VoiceChannel, embed: discord.Embed):
                super().__init__(timeout=30)
                self.embed = embed
                self.channel = channel
                self.voted = []
                self.completed = False

            async def on_timeout(self):
                for item in self.children:
                    item.disabled = True
                try:
                    if not self.completed:
                        await interaction.edit_original_response(content="⏱️ Vote kick timed out", embed=None, view=self)
                except discord.errors.NotFound:
                    pass
                self.stop()
            
            @discord.ui.button(label="vote", style=discord.ButtonStyle.red, custom_id="vote_button")
            async def vote_button(self, interaction_: discord.Interaction, button: discord.ui.Button):
                if interaction_.user.voice.channel == self.channel:
                    for voted_user in self.voted:
                        if voted_user == interaction_.user.id:
                            return await interaction_.response.send_message("You already voted!", ephemeral=True)
                    kick_vote = int(self.embed.footer.text.split(": ")[1].split("/")[0])
                    kick_vote += 1
                    if kick_vote >= maximum_vote_threshold:
                        self.completed = True
                        with open('kicklist.json', 'r') as f1:
                            kick_data = json.load(f1)
                        if str(player.channel.id) in kick_data:
                            if str(member.id) in kick_data[str(player.channel.id)]:
                                pass
                            else:
                                kicked_list = list(kick_data[str(player.channel.id)])
                                kicked_list.append(str(member.id))
                                kick_data[str(player.channel.id)] = kicked_list
                        else:
                            kicked_list = []
                            kicked_list.append(str(member.id))
                            kick_data[str(player.channel.id)] = kicked_list
                        
                        with open('kicklist.json', 'w') as f1:
                            json.dump(kick_data, f1)
                        await member.move_to(None)
                        add_activity(player, f"👢 **{member.display_name}** was vote-kicked")
                        await update_dashboard(player)
                        try:
                            await interaction.edit_original_response(content=f"👢 Kicked **{member.display_name}** by vote", embed=None, view=None)
                            await interaction_.response.send_message("Voted!", ephemeral=True)
                        except discord.errors.NotFound:
                            await interaction_.response.send_message(f"Voted! {member.display_name} was kicked.", ephemeral=True)
                        self.stop()
                    else:
                        self.voted.append(interaction_.user.id)
                        embed_ = await comp_embed(None, f"Vote to kick `{member.display_name}`", author_name=interaction.user.display_name, author_avatar_url=interaction.user.display_avatar.url)
                        embed_.set_footer(text=f"Current people voted to kick: {str(kick_vote)}/{maximum_vote_threshold}")
                        self.embed = embed_
                        try:
                            await interaction.edit_original_response(embed=embed_, view=self)
                            await interaction_.response.send_message("Voted!", ephemeral=True)
                        except discord.errors.NotFound:
                            await interaction_.response.send_message("Voted! (The original message was deleted).", ephemeral=True)
                else:
                    return await interaction_.response.send_message("You can't vote because you are not in the same voice channel!", ephemeral=True)

        embed = await comp_embed(None, f"Vote to kick `{member.display_name}`", author_name=interaction.user.display_name, author_avatar_url=interaction.user.display_avatar.url, footer=f"Current people voted to kick: 0/{maximum_vote_threshold}")
        await interaction.response.send_message(embed=embed, view=voteView(channel=interaction.user.voice.channel, embed=embed))
    else:
        return await interaction.response.send_message(f"You can't vote kick because the member count is not {maximum_vote_threshold} in your current voice channel!")

#!!!!!!!!!!!!!!!!!!!#
#!Function commands!#
#!!!!!!!!!!!!!!!!!!!#

@tree.command(name="blacklist", description="blacklist a member(Give limitation)")
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.describe(member="The member to blacklist")
async def blacklist(interaction: discord.Interaction, member: discord.Member):
  if not member.id == interaction.user.id:
    with open("blacklist.json", 'r') as f:
      blacklist_data = json.load(f)
    if str(interaction.guild.id) in blacklist_data:
      if not str(member.id) in blacklist_data[str(interaction.guild.id)]:
        if not member.guild_permissions.manage_messages:
          blacklist_data[str(interaction.guild.id)][str(member.id)] = {}
          await interaction.response.send_message("Member blacklisted!", ephemeral=True)
        else:
          return await interaction.response.send_message("That member is a mod!", ephemeral=True)
      else:
        return await interaction.response.send_message("That member is already blacklisted!", ephemeral=True)
    else:
      if not member.guild_permissions.manage_messages:
        blacklist_data[str(interaction.guild.id)] = {}
        blacklist_data[str(interaction.guild.id)][str(member.id)] = {}
        await interaction.response.send_message("Member blacklisted!", ephemeral=True)
      else:
        return await interaction.response.send_message("That member is a mod!", ephemeral=True)
  else:
    return await interaction.response.send_message("You can't blacklist yourself!", ephemeral=True)
  with open('blacklist.json', 'w') as f:
    json.dump(blacklist_data, f)

@tree.command(name="whitelist", description="Whitelist a member(unblacklist)")
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.describe(member="The member to whitelist")
async def whitelist(interaction: discord.Interaction, member: discord.Member):
  if not member.id == interaction.user.id:
    with open("blacklist.json", 'r') as f:
      blacklist_data = json.load(f)
    if str(interaction.guild.id) in blacklist_data:
      if str(member.id) in blacklist_data[str(interaction.guild.id)]:
        del blacklist_data[str(interaction.guild.id)][str(member.id)]
        await interaction.response.send_message("Member whitelisted!", ephemeral=True)
      else:
        return await interaction.response.send_message("That member is not blacklisted!", ephemeral=True)
    else:
      return await interaction.response.send_message("No one is blacklisted in your server!", ephemeral=True)
  else:
    return await interaction.response.send_message("You can't whitelist yourself!", ephemeral=True)
  with open('blacklist.json', 'w') as f:
    json.dump(blacklist_data, f)

@tree.command(name="createinteractive", description="Add a interactive VC to make a VC for a certain member")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(channel="The channel to interact with")
async def create_interactive_vc(interaction: discord.Interaction, channel: discord.VoiceChannel):
  try:
    with open('music_voice_channels.json', 'r') as f:
      data = json.load(f)
    
    if not str(interaction.guild.id) in data:
      channel_list = []
      channel_list.append(channel.id)
      data[str(interaction.guild.id)] = {}
      data[str(interaction.guild.id)]['channels'] = {}
      data[str(interaction.guild.id)]['channels'] = channel_list
    else:
      channel_list = list(data[str(interaction.guild.id)]['channels'])
      channel_list.append(channel.id)
      data[str(interaction.guild.id)]['channels'] = channel_list

    with open('music_voice_channels.json', 'w') as f:
      json.dump(data, f, indent=2)
    
    await interaction.response.send_message("Channel set!", ephemeral=True)
  except Exception as e:
    raise e

@tree.command(name="removeinteractive", description="remove a interactive VC")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(channel="The channel to remove interaction with")
async def remove_interactive_vc(interaction: discord.Interaction, channel: discord.VoiceChannel):
  try:
    with open('music_voice_channels.json', 'r') as f:
      data = json.load(f)
    
    if not str(interaction.guild.id) in data:
      return await interaction.response.send_message("No interactive VC found!", ephemeral=True)
    else:
      channel_list = list(data[str(interaction.guild.id)]['channels'])
      channel_list.remove(channel.id)
      data[str(interaction.guild.id)]['channels'] = channel_list
      if len(channel_list) == 0:
        del data[str(interaction.guild.id)]

    with open('music_voice_channels.json', 'w') as f:
      json.dump(data, f, indent=2)
    
    await interaction.response.send_message("Channel removed!", ephemeral=True)
  except Exception as e:
    raise e

load_dotenv()

token = os.getenv('token')
client.run(token)