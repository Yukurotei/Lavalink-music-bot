import discord
import typing
import wavelink
import sqlite3
import json
import asyncio
from discord.ext import commands

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.loop.create_task(self.create_nodes())

    async def create_nodes(self):
        await self.bot.wait_until_ready()
        await wavelink.NodePool.create_node(bot=self.bot, host="127.0.0.1", port="2333", password="youshallnotpass", region="asia")
        #await wavelink.NodePool.create_node(bot=self.bot, host="127.0.0.1", port="443", password="passcal", region="asia")
        #await wavelink.NodePool.create_node(bot=self.bot, host="127.0.0.1", port="2333", password="123", region="asia")
    
    def convert(self, seconds: int, auto_format=False):
        """
        Funciton convert(seconds: int, auto_format: bool=False) -> string:
            Convert seconds to hours, minutes and seconds\n
            Prameter:
                seconds: int; provide the time you want to convert in seconds
                auto_format: bool=false; default set to false, if set to true, It will auto formate the result
        
            Return -> string:
                returns the final converted string
        """
        min, sec = divmod(seconds, 60)
        hour, min = divmod(min, 60)
        converted = '%d:%02d:%02d' % (hour, min, sec)
        if auto_format:
            final = "`" + converted + "`"
        else:
            final = converted
        return final

    @commands.Cog.listener()
    async def on_ready(self):
        print("music cog ready! (beta)")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node):
        print(f"Node <{node.identifier}> ready!")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(f"Unknown command")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, player: wavelink.Player, track: wavelink.Track, reason):
        ctx = player.ctx
        vc: player = ctx.voice_client

        if vc.loop:
            return await vc.play(track)
        
        if vc.queue.is_empty:
            return await ctx.send("Nothing to play")
        
        next_song = vc.queue.get()
        song = await wavelink.YouTubeTrack.search(query=str(next_song), return_first=True)
        if not song.uri == None:
                ur = song.uri
        else:
            ur = "None"
        if not song.author == None:
            au = song.author
        else:
            au = "None"
        if song.is_stream():
            stream = "True"
        else:
            stream = "False"
        await vc.play(song)
        embed = discord.Embed(title=f"Now Playing `{song.title}`", description=f"Info:\nSong length, {self.convert(int(song.duration), auto_format=True)}\nAuthor, {au}\nLink, {ur}\nStream, {stream}", color=discord.Color.blue())
        await ctx.send(embed=embed)
        player.ctx = ctx
        
    @commands.Cog.listener()
    async def on_wavelink_track_stuck(player: wavelink.Player, track: wavelink.Track, threshold):
        try:
            ctx = player.ctx
            vc: player = ctx.voice_client
            await vc.ctx.send("Oops! the track is stuck for a sec")
        except Exception as e:
            print(e)

    @commands.command(name="join", aliases=["connect", "summon"], description="Join the voice channel you provided or the music channel you are in")
    async def join_commad(self, ctx, channel: typing.Optional[discord.VoiceChannel]):
        try:
            if channel is None:
                channel = ctx.author.voice.channel
            
            node = wavelink.NodePool.get_node()
            player = node.get_player(ctx.guild)

            if player is not None:
                if player.is_connected():
                    return await ctx.send("bot is already connected to a voice channel")
            
            await channel.connect(cls=wavelink.Player)
            embed = discord.Embed(title=f"Connected to {channel.name}", color=discord.Color.from_rgb(255, 255, 255))
            await ctx.send(embed=embed)
        except AttributeError:
            await ctx.send("You are not in a voice channel!")

    @commands.command(name="leave", aliases=["disconnect", "quit"], description="Leave the Voice channel")
    async def leave_command(self, ctx):
        with open('blacklist.json', 'r') as f:
            data = json.load(f)
        if str(ctx.guild.id) in data:
            if str(ctx.author.id) in data[str(ctx.guild.id)]:
                blacklisted = True
            else:
                blacklisted = False
        else:
            blacklisted = False
        node = wavelink.NodePool.get_node()
        player = node.get_player(ctx.guild)

        if player is None:
            return await ctx.send("bot is not connected to any voice channel")
        vc: wavelink.Player = ctx.voice_client
        if vc.is_playing():
            return await ctx.send("Bot is playing a song! Use `rr?stop` to stop the music")
        if blacklisted:
            return await ctx.author.send(f"You are blacklisted in {ctx.guild.name}! So you can't let the bot leave the voice channel!")
        await player.disconnect()
        embed=discord.Embed(title="Disconnected", color=discord.Color.from_rgb(255, 255, 255))
        await ctx.send(embed=embed)
    
    @commands.command(name="play", description="search the music name you provided and play it")
    async def play_command(self, ctx, *, search: str):
        try:
            if not ctx.author.voice:
                return await ctx.send("Join a voice channel first!")
            song = await wavelink.YouTubeTrack.search(query=search, return_first=True)
            
            if not ctx.voice_client:
                vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
            else:
                vc: wavelink.Player = ctx.voice_client
            
            if vc.queue.is_empty and not vc.is_playing():
                await vc.play(song)
                if not song.uri == None:
                    ur = song.uri
                else:
                    ur = "None"
                if not song.author == None:
                    au = song.author
                else:
                    au = "None"
                if song.is_stream():
                    stream = "True"
                else:
                    stream = "False"
                embed = discord.Embed(title=f"Now Playing `{song.title}`", description=f"Info:\nSong length, {self.convert(int(song.duration), auto_format=True)}\nAuthor, {au}\nLink, {ur}\nStream, {stream}", color=discord.Color.from_rgb(255, 255, 255))
            else:
                await vc.queue.put_wait(song)
                embed = discord.Embed(title=f"Added `{song}` to the queue", color=discord.Color.from_rgb(255, 255, 255))
            await ctx.send(embed=embed)
            vc.ctx = ctx
            setattr(vc, "loop", False)
        except Exception as e:
            await ctx.send(e)

    @commands.command(name="overrideplay", description="Play the music without adding it to the query and override all songs")
    async def overrideplay_command(self, ctx, *, search: str):
        with open('blacklist.json', 'r') as f:
            data = json.load(f)
        if str(ctx.guild.id) in data:
            if str(ctx.author.id) in data[str(ctx.guild.id)]:
                blacklisted = True
            else:
                blacklisted = False
        else:
            blacklisted = False
        if not ctx.author.voice:
            return await ctx.send("Join a voice channel first!")
        song = await wavelink.YouTubeTrack.search(query=search, return_first=True)
        
        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        else:
            vc: wavelink.Player = ctx.voice_client
        
        if blacklisted:
            return await ctx.author.send(f"You are blacklisted in {ctx.guild.name}! You can't override play!")
        if vc.queue.is_empty:
            await vc.play(song)
            if not song.uri == None:
                ur = song.uri
            else:
                ur = "None"
            if not song.author == None:
                au = song.author
            else:
                au = "None"
            if song.is_stream():
                stream = "True"
            else:
                stream = "False"
            embed = discord.Embed(title=f"Now Playing `{song.title}`", description=f"Info:\nSong length, {self.convert(int(song.duration), auto_format=True)}\nAuthor, {au}\nLink, {ur}\nStream, {stream}", color=discord.Color.from_rgb(255, 255, 255))
        else:
            await ctx.send("The queue is not empty, use the stop command to clear the queue!")
        await ctx.send(embed=embed)
        vc.ctx = ctx
        setattr(vc, "loop", False)
    
    @commands.command(name="stop", description="Finish the music(It will finish the music and clear queue)")
    async def stop_command(self, ctx):
        try:
            with open('blacklist.json', 'r') as f:
                data = json.load(f)
            if str(ctx.guild.id) in data:
                if str(ctx.author.id) in data[str(ctx.guild.id)]:
                    blacklisted = True
                else:
                    blacklisted = False
            else:
                blacklisted = False
            if not blacklisted:
                node = wavelink.NodePool.get_node()
                player = node.get_player(ctx.guild)

                if player is None:
                    return await ctx.send("Bot is not connected to any voice channel")
                else:
                    vc: wavelink.Player = ctx.voice_client
                
                if player.is_playing:
                    if not vc.loop:
                        if not vc.queue.is_empty:
                            vc.queue.clear()
                            await player.stop()
                        else:
                            await player.stop()
                        embed=discord.Embed(title="Playback Stoped", color=discord.Color.from_rgb(255, 255, 255))
                        return await ctx.send(embed=embed)
                    else:
                        return await ctx.send("Loop is on! use `rr?loop` to turn off looping and then use stop command!")
                else:
                    return await ctx.send("Nothing is playing")
            else:
                return await ctx.author.send(f"You are blacklisted in {ctx.guild.name}! You can't let the bot stop playing a song!")
        except Exception as e:
            print(e)

    @commands.command(name="skip", description="Skip this song and move on to the next song if there is one")
    async def skip_command(self, ctx):
        with open('blacklist.json', 'r') as f:
            data = json.load(f)
        if str(ctx.guild.id) in data:
            if str(ctx.author.id) in data[str(ctx.guild.id)]:
                blacklisted = True
            else:
                blacklisted = False
        else:
            blacklisted = False
        node = wavelink.NodePool.get_node()
        player = node.get_player(ctx.guild)

        if player is None:
            return await ctx.send("Bot is not connected to any voice channel")
        else:
            vc: wavelink.Player = ctx.voice_client
        
        if blacklisted:
            return await ctx.author.send(f"You are blacklisted in {ctx.guild.name}! You can't skip a song!")
        
        if player.is_playing:
            await player.stop()
            embed=discord.Embed(title="Playback Skipped", color=discord.Color.from_rgb(255, 255, 255))
            return await ctx.send(embed=embed)
        else:
            return await ctx.send("Nothing is playing")

    @commands.command(name="pause", description="pause the music if it is playing one")
    async def pause_command(self, ctx):
        with open('blacklist.json', 'r') as f:
            data = json.load(f)
        if str(ctx.guild.id) in data:
            if str(ctx.author.id) in data[str(ctx.guild.id)]:
                blacklisted = True
            else:
                blacklisted = False
        else:
            blacklisted = False
        if blacklisted:
            return await ctx.author.send(f"You are blacklisted in {ctx.guild.name}! You can't pause a song!")
        node = wavelink.NodePool.get_node()
        player = node.get_player(ctx.guild)

        if player is None:
            return await ctx.send("Bot is not connected to any voice channel")
        
        if not player.is_paused():
            if player.is_playing():
                await player.pause()
                embed = discord.Embed(title="Playback Paused", color=discord.Color.from_rgb(255, 255, 255))
                return await ctx.send(embed=embed)
            else:
                return await ctx.send("Nothing is playing")
        else:
            return await ctx.send("Playback is Already paused")
    
    @commands.command(name="resume", aliases=["continue"], description="resume the music if it is playing one")
    async def resume_command(self, ctx):
        with open('blacklist.json', 'r') as f:
            data = json.load(f)
        if str(ctx.guild.id) in data:
            if str(ctx.author.id) in data[str(ctx.guild.id)]:
                blacklisted = True
            else:
                blacklisted = False
        else:
            blacklisted = False
        if blacklisted:
            return await ctx.author.send(f"You are blacklisted in {ctx.guild.name}! You can't resume a song!")
        node = wavelink.NodePool.get_node()
        player = node.get_player(ctx.guild)

        if player is None:
            return await ctx.send("bot is not connected to any voice channel")
        
        if player.is_paused():
            await player.resume()
            embed = discord.Embed(title="Playback resumed", color=discord.Color.from_rgb(255, 255, 255))
            return await ctx.send(embed=embed)
        else:
            return await ctx.send("playback is not paused")

    @commands.command(name="volume", description="Change the music volume between 1 and 100")
    async def volume_command(self, ctx, to:int):
        with open('blacklist.json', 'r') as f:
            data = json.load(f)
        if str(ctx.guild.id) in data:
            if str(ctx.author.id) in data[str(ctx.guild.id)]:
                blacklisted = True
            else:
                blacklisted = False
        else:
            blacklisted = False
        if blacklisted:
            return await ctx.author.send(f"You are blacklisted in {ctx.guild.name}! You can't change the volume!")
        if not ctx.voice_client:
            return await ctx.send("I am not even in a voice channel!")
        if to > 100:
            return await ctx.send("Volume should be between 1 and 100")
        elif to < 1:
            return await ctx.send("Volume should be between 1 and 100")
        
        node = wavelink.NodePool.get_node()
        player = node.get_player(ctx.guild)

        await player.set_volume(to)
        embed = discord.Embed(title=f"Changed volume to {to}", color=discord.Color.from_rgb(255, 255, 255))
        await ctx.send(embed=embed)
    
    @commands.command(name="loop", description="Loop the music")
    async def loop_command(self, ctx):
        with open('blacklist.json', 'r') as f:
            data = json.load(f)
        if str(ctx.guild.id) in data:
            if str(ctx.author.id) in data[str(ctx.guild.id)]:
                blacklisted = True
            else:
                blacklisted = False
        else:
            blacklisted = False
        if blacklisted:
            return await ctx.author.send(f"You are blacklisted in {ctx.guild.name}! You can't loop a song!")
        if not ctx.voice_client:
            return await ctx.send("I am not in a voice channel!")
        elif not ctx.author.voice:
            return await ctx.send("You are not in a voice channel!")
        else:
            vc: wavelink.Player = ctx.voice_client
        
        if vc.loop == False:
            vc.loop = True
        else:
            setattr(vc, "loop", False)
        
        if vc.loop:
            return await ctx.send("Loop is now **Enabled!**")
        else:
            return await ctx.send("Loop is now **Disabled!**")

    @commands.command(name="queue", description="Show the queue")
    async def queue_command(self, ctx):
        if not ctx.voice_client:
            return await ctx.send("I'm not in a voice channel!")
        elif not ctx.author.voice:
            return await ctx.send("You are not in a voice channel!")
        else:
            vc: wavelink.Player = ctx.voice_client

        if vc.queue.is_empty:
            return await ctx.send("Queue is empty")
        
        embed = discord.Embed(title="Queue", color=discord.Color.from_rgb(255, 255, 255))
        queue = vc.queue.copy()
        song_count = 0
        for song in queue:
            song_count += 1
            embed.add_field(name=f"Song {song_count}", value=f"`{song}`")

        return await ctx.send(embed=embed)

    @commands.command(name="nowplaying", aliases=["now_playing", "np"], description="See the song that is plaing right now")
    async def now_playing_command(self, ctx: commands.Context):
        node = wavelink.NodePool.get_node()
        player = node.get_player(ctx.guild)

        if player is None:
            return await ctx.reply("Bot is not connected to any voice channel")
        
        if player.is_playing():
            if not player.track.info['uri'] == None:
                ur = player.track.info['uri']
            else:
                ur = "None"
            if not player.track.info['author'] == None:
                au = player.track.info['author']
            else:
                au = "None"
            embed = discord.Embed(title=f"Now Playing `{player.track}`", description=f"Info:\nSong length, {self.convert(int(player.track.length), auto_format=True)}\nAuthor, {au}\nLink, {ur}", color=discord.Color.from_rgb(255, 255, 255))
        
            return await ctx.send(embed=embed)
        else:
            await ctx.reply("Nothing is playing right now")
    
    @commands.command(name="search", description="Search a song and select the one you want to play")
    async def search_command(self, ctx: commands.Context, *, search: str):
        try:
            tracks = await wavelink.YouTubeTrack.search(query=search)
        except:
            return await ctx.reply(embed=discord.Embed(title="Something went wrong while searching for this track", color=discord.Color.from_rgb(255, 255, 255)))
        
        if tracks is None:
            return await ctx.reply("No tracks found")

        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        else:
            vc: wavelink.Player = ctx.voice_client
        
        embed = discord.Embed(
            title="Select the track: ",
            description=("\n".join(f"**{i+1}. {t.title}**" for i, t in enumerate(tracks[:5]))),
            color=discord.Color.from_rgb(255, 255, 255)
        )
        msg = await ctx.send(embed=embed)

        emojis_list = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '❌']
        emojis_dict = {
            '1️⃣': 0,
            '2️⃣': 1,
            '3️⃣': 2,
            '4️⃣': 3,
            '5️⃣': 4,
            '❌': -1
        }

        for emoji in list(emojis_list[:min(len(tracks), len(emojis_list))]):
            await msg.add_reaction(emoji)

        def check(res, user):
            return(res.emoji in emojis_list and user == ctx.author and res.message.id == msg.id)
        
        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
        except asyncio.TimeoutError:
            await msg.delete()
            return
        else:
            await msg.delete()
        
        node = wavelink.NodePool.get_node()
        player = node.get_player(ctx.guild)

        try:
            if emojis_dict[reaction.emoji] == -1: return
            choosed_track = tracks[emojis_dict[reaction.emoji]]
        except:
            return
        
        vc: wavelink.Player = ctx.voice_client or await ctx.author.voice.channel.connect(cls=wavelink.Player)

        if not player.is_playing() and not player.is_paused():
            try:
                await vc.play(choosed_track)
            except:
                return await ctx.reply(emoji=discord.Embed(title="Something went wrong while playing this track", color=discord.Color.from_rgb(255, 255, 255)))
        else:
            await vc.queue.put_wait(choosed_track)

        await ctx.send(embed=discord.Embed(title=f"Added {choosed_track.title} to the queue", color=discord.Color.from_rgb(255, 255, 255)))
        vc.ctx = ctx
        setattr(vc, "loop", False)

    @commands.command(name="info", description="search the music name you provided and show the info of it", aliases=["information"])
    async def info_command(self, ctx, *, search: str):
        song = await wavelink.YouTubeTrack.search(query=search, return_first=True)
        if not song.uri == None:
            ur = song.uri
        else:
            ur = "None"
        if not song.author == None:
            au = song.author
        else:
            au = "None"
        if song.is_stream():
            stream = "True"
        else:
            stream = "False"
        embed = discord.Embed(title=f"Info about `{song.title}`", description=f"Info:\nSong length, {self.convert(int(song.duration), auto_format=True)}\nAuthor, {au}\nLink, {ur}\nStream, {stream}", color=discord.Color.from_rgb(255, 255, 255))
        await ctx.send(embed=embed)
    
    @commands.command(name="addsong", description="Add a song to your song list")
    async def addsong_command(self, ctx, *, song: str):
        try:
            so = await wavelink.YouTubeTrack.search(query=song, return_first=True)
            so1 = str(so) + ", "
            db = sqlite3.connect('main.sqlite')
            cursor = db.cursor()
            cursor.execute(f"SELECT song_list FROM main WHERE user_id = {ctx.author.id}")
            result = cursor.fetchone()
            if result is None:
                sql = ("INSERT INTO main(user_id, song_list) VALUES(?,?)")
                val = (ctx.author.id, so1)
                await ctx.send(f"First song added! {so}")
            elif result is not None:
                if not str(so) in result[0]:
                    sfinal = result[0] + (so1)
                    sql = ("UPDATE main SET song_list = ? WHERE user_id = ?")
                    val = (sfinal, ctx.author.id,)
                    await ctx.send(f"Song has been added: {so}")
                else:
                    db.commit()
                    cursor.close()
                    db.close()
                    return await ctx.send(f"There is already a song named `{so}` in your list!")
            cursor.execute(sql, val)
            db.commit()
            cursor.close()
            db.close()
        except Exception as e:
            await ctx.send(e)


    @commands.command(name="addurl", description="Add a url to your url song list")
    async def addurl_command(self, ctx, *, song: str):
        try:
            if not "http" in song:
                return await ctx.send("It's not a url!")
            so = await wavelink.YouTubeTrack.search(query=song, return_first=True)
            so1 = str(so.uri) + ", "
            db = sqlite3.connect('co.sqlite')
            cursor = db.cursor()
            cursor.execute(f"SELECT song_url FROM co WHERE user_id = {ctx.author.id}")
            result = cursor.fetchone()
            if result is None:
                sql = ("INSERT INTO co(user_id, song_url) VALUES(?,?)")
                val = (ctx.author.id, so1)
                await ctx.send(f"First url added! {so}")
            elif result is not None:
                sfinal = result[0] + (so1)
                sql = ("UPDATE co SET song_url = ? WHERE user_id = ?")
                val = (sfinal, ctx.author.id,)
                await ctx.send(f"Url has been added: {so}")
            cursor.execute(sql, val)
            db.commit()
            cursor.close()
            db.close()
        except Exception as e:
            return await ctx.send(e)
    
    @commands.command(name="mysonglist", description="Show your song list")
    async def mysonglist_command(self, ctx):
        try:
            db = sqlite3.connect('main.sqlite')
            cursor = db.cursor()
            cursor.execute(f"SELECT song_list FROM main WHERE user_id = {ctx.author.id}")
            result = cursor.fetchone()
            if result is None:
                cursor.close()
                db.close()
                return await ctx.send("You don't have any song in your list")
            elif result is not None:
                result = " ".join(result)
                result = result.replace(", ", "\n")
                embed = discord.Embed(title="Your song list", description=f"{result}", color=discord.Color.from_rgb(255, 255, 255))
                await ctx.send(embed=embed)
                cursor.close()
                db.close()
        except Exception as e:
            await ctx.send(e)

    @commands.command(name="myurllist", description="Show your url song list")
    async def myurllist_command(self, ctx):
        try:
            msg = await ctx.send("Processing through database, this might take a while depending on how many url you have added")
            db = sqlite3.connect('co.sqlite')
            cursor = db.cursor()
            cursor.execute(f"SELECT song_url FROM co WHERE user_id = {ctx.author.id}")
            result = cursor.fetchone()
            if result is None:
                cursor.close()
                db.close()
                return await ctx.send("You don't have any url(s) in your list")
            elif result is not None:
                embed = discord.Embed(title="Your url song list", color=discord.Color.from_rgb(255, 255, 255))
                list_ = []
                for url in result[0].split(", "):
                    list_.append("".join(url))
                list_.pop()
                for url in list_:
                    name = await wavelink.YouTubeTrack.search(query=url, return_first=True)
                    embed.add_field(name=f"{name}", value=f"{url}", inline=False)
                #result = " ".join(result)
                await msg.edit(embed=embed, content="")
                cursor.close()
                db.close()
        except Exception as e:
            await ctx.send(e)
    
    @commands.command(name="deletesongandurllist", description="Delete your song list AND your url song list")
    async def deletesonglist_command(self, ctx):
        db = sqlite3.connect('main.sqlite')
        cursor = db.cursor()
        cursor.execute(f"SELECT song_list FROM main WHERE user_id = {ctx.author.id}")
        result = cursor.fetchone()
        if result is not None:
            try:
                sql = ("DELETE FROM main WHERE user_id = ?")
                val = (ctx.author.id,)
                cursor.execute(sql, val)
                await ctx.send("Sucessfully removed your song list")
            except Exception as e:
                await ctx.send(e)
        elif result is None:
            db.commit()
            cursor.close()
            db.close()
            return await ctx.send("You don't have a song list!")
        db.commit()
        cursor.close()
        db.close()

def setup(bot):
  bot.add_cog(Music(bot))