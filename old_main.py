import discord
import os
import json
import sqlite3
from discord.ext import commands
from discord.ext.menus import MenuPages, ListPageSource
from dotenv import load_dotenv

bot = commands.Bot(command_prefix="rr?", intents=discord.Intents.all())

current_path = os.getcwd()

async def load_cog():
  for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
      bot.load_extension(f'cogs.{filename[:-3]}')

os.chdir(current_path)

@bot.event
async def on_ready():
    await load_cog()
    db = sqlite3.connect('main.sqlite')
    cursor = db.cursor()
    cursor.execute('''
      CREATE TABLE IF NOT EXISTS main(
        user_id TEXT,
        song_list TEXT
      )
    ''')
    db.commit()
    cursor.close()
    db.close()
    db1 = sqlite3.connect('co.sqlite')
    cursor1 = db1.cursor()
    cursor1.execute('''
      CREATE TABLE IF NOT EXISTS co(
        user_id TEXT,
        song_url TEXT
      )
    ''')
    db1.commit()
    cursor1.close()
    db1.close()
    await bot.change_presence(activity=discord.Game(name="rr?help"))
    print("Bot ready!")

@bot.event
async def on_voice_state_update(member, before, after):
  try:
    with open('music_voice_channels.json', 'r') as f:
      data = json.load(f)
    if not member.bot:
      if after.channel is not None:
        if str(member.guild.id) in data:
          channelInData = False
          for channel_id in list(data[str(member.guild.id)]['channels']):
            if after.channel.id == int(channel_id):
              channelInData = True
          if channelInData:
            interactive_ch = bot.get_channel(after.channel.id)
            if not interactive_ch is None:
              category_id = interactive_ch.category_id
              if not category_id is None:
                category = discord.utils.get(member.guild.categories, id=int(category_id))
                vc = await member.guild.create_voice_channel(f"{member.name}#{member.discriminator}'s VC", category=category)
                return await member.move_to(vc)
              else:
                vc = await member.guild.create_voice_channel(f"{member.name}#{member.discriminator}'s VC")
                return await member.move_to(vc)
        else:
          return
        channel = discord.utils.get(member.guild.channels, name=f"{member.name}#{member.discriminator}'s VC")
        if not channel is None:
          if after.channel.id != channel.id:
            await channel.delete()
      elif after.channel is None:
        channel = discord.utils.get(member.guild.channels, name=f"{member.name}#{member.discriminator}'s VC")
        if not channel is None:
          await channel.delete()
  except Exception as e:
    print(e)

@bot.event
async def on_guild_remove(guild):
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

@bot.command()
@commands.is_owner()
async def reload(ctx, cog_name: str):
  if cog_name.lower() == "all":
    for filename in os.listdir('./cogs'):
      if filename.endswith('.py'):
        bot.reload_extension(f'cogs.{filename[:-3]}')
    await ctx.send("Sucessfuly reloaded all cogs")
  else:
    if os.path.exists(f'./cogs/{cog_name}.py'):
      if ".py" in cog_name:
        bot.reload_extension(f'cogs.{cog_name[:-3]}')
      else:
        bot.reload_extension(f'cogs.{cog_name}')
      await ctx.send(f"Sucessfuly reloaded {cog_name}")
    else:
      return await ctx.send(f"There is no cog called {cog_name}")

@bot.command(description="blacklist a member(Give limitation)")
@commands.has_permissions(manage_messages=True)
async def blacklist(ctx, member: discord.Member):
  if not member.id == ctx.author.id:
    with open("blacklist.json", 'r') as f:
      blacklist_data = json.load(f)
    if str(ctx.guild.id) in blacklist_data:
      if not str(member.id) in blacklist_data[str(ctx.guild.id)]:
        if not member.guild_permissions.manage_messages:
          blacklist_data[str(ctx.guild.id)][str(member.id)] = {}
          await ctx.send("Member blacklisted!")
        else:
          return await ctx.send("That member is a mod!")
      else:
        return await ctx.send("That member is already blacklisted!")
    else:
      if not member.guild_permissions.manage_messages:
        blacklist_data[str(ctx.guild.id)] = {}
        blacklist_data[str(ctx.guild.id)][str(member.id)] = {}
        await ctx.send("Member blacklisted!")
      else:
        return await ctx.send("That member is a mod!")
  else:
    return await ctx.send("You can't blacklist yourself!")
  with open('blacklist.json', 'w') as f:
    json.dump(blacklist_data, f)

@bot.command(description="Whitelist a member(unblacklist)")
@commands.has_permissions(manage_messages=True)
async def whitelist(ctx, member: discord.Member):
  if not member.id == ctx.author.id:
    with open("blacklist.json", 'r') as f:
      blacklist_data = json.load(f)
    if str(ctx.guild.id) in blacklist_data:
      if str(member.id) in blacklist_data[str(ctx.guild.id)]:
        del blacklist_data[str(ctx.guild.id)][str(member.id)]
        await ctx.send("Member whitelisted!")
      else:
        return await ctx.send("That member is not blacklisted!")
    else:
      return await ctx.send("No one is blacklisted in your server!")
  else:
    return await ctx.send("You can't whitelist yourself!")
  with open('blacklist.json', 'w') as f:
    json.dump(blacklist_data, f)

@bot.command(description="Add a interactive VC to make a VC for a certain member")
@commands.has_permissions(manage_guild=True)
async def create_interactive_vc(ctx, channel: discord.VoiceChannel):
  try:
    with open('music_voice_channels.json', 'r') as f:
      data = json.load(f)
    
    if not str(ctx.guild.id) in data:
      channel_list = []
      channel_list.append(channel.id)
      data[str(ctx.guild.id)] = {}
      data[str(ctx.guild.id)]['channels'] = {}
      data[str(ctx.guild.id)]['channels'] = channel_list
    else:
      channel_list = list(data[str(ctx.guild.id)]['channels'])
      channel_list.append(channel.id)
      data[str(ctx.guild.id)]['channels'] = channel_list


    with open('music_voice_channels.json', 'w') as f:
      json.dump(data, f, indent=2)
    
    await ctx.send("Channel set!")
  except Exception as e:
    raise e

@bot.command(description="Remove a interactive VC")
@commands.has_permissions(manage_guild=True)
async def remove_interactive_vc(ctx, channel: discord.VoiceChannel):
  try:
    with open('music_voice_channels.json', 'r') as f:
      data = json.load(f)
    
    if not str(ctx.guild.id) in data:
      return ctx.send("No interactive VC found!")
    else:
      channel_list = list(data[str(ctx.guild.id)]['channels'])
      channel_list.remove(channel.id)
      data[str(ctx.guild.id)]['channels'] = channel_list
      if len(channel_list) == 0:
        del data[str(ctx.guild.id)]
  

    with open('music_voice_channels.json', 'w') as f:
      json.dump(data, f, indent=2)
    
    await ctx.send("Channel removed!")
  except Exception as e:
    raise e

@bot.command(description="(OWNER ONLY)Leave a server")
@commands.is_owner()
async def leave_server(ctx, guild_id: str):
  id = int(guild_id)
  guild = bot.get_guild(id)
  await guild.leave()
  await ctx.send(f"I've sucessfuly left guild **{guild.name}**")

load_dotenv()

token = os.getenv('token')
bot.run(token)