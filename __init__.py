import discord
from discord.ext import commands
import json
import logging
import sys

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

prefix = ('/')

intents = discord.Intents(guilds=True, messages=True, members=True)
bot = commands.Bot(command_prefix=prefix, intents=intents)

mods = ['shops', 'items', 'cats', 'catsite_util', 'shortcuts'] # modules
initial_extensions = mods

bot.remove_command("help")

with open('settings.json', 'r') as f:
    content = json.load(f)
    embedcolor = int(content['color'][2:], base=16)
    admin_ids = [int(discid) for discid in content['permissions']['admins']]

@bot.event  
async def on_ready():
    logger.info(f'Logged in as {bot.user.name}; ID {bot.user.id}')

#-----------------------------------------

@bot.command()
async def kill(ctx):
    if ctx.message.author.id not in admin_ids: 
        logger.debug(f'Attempted kill by {ctx.message.author.name} ({ctx.message.author.id}) with insufficient permissions')
        return
    embed = discord.Embed(description='Goodnight! Restarting soon.', colour = discord.Colour(embedcolor))
    await ctx.send(embed = embed)
    await bot.logout()
    sys.exit()

@bot.command()
async def reloadall(ctx, *, params=""):
    out = []
    for extension_name in initial_extensions:
        bot.unload_extension(extension_name)
        try:
            bot.load_extension(extension_name)
        except (AttributeError, ImportError) as e:
            await ctx.send("```py\n{}: {}\n```".format(type(e).__name__, str(e)))
        out.append("**{}** loaded.".format(extension_name))
    await ctx.send('\n'.join(out))

@bot.command()
async def load(ctx, extension_name : str):
    try:
        bot.load_extension(extension_name)
    except (AttributeError, ImportError) as e:
        await ctx.send("```py\n{}: {}\n```".format(type(e).__name__, str(e)))
        return
    await ctx.send("**{}** loaded.".format(extension_name))

@bot.command()
async def unload(ctx, extension_name : str):
    bot.unload_extension(extension_name)
    await ctx.send("**{}** unloaded.".format(extension_name))

@bot.command()
async def reload(ctx, extension_name : str):
    bot.unload_extension(extension_name)
    try:
        bot.load_extension(extension_name)
    except (AttributeError, ImportError) as e:
        await ctx.send("```py\n{}: {}\n```".format(type(e).__name__, str(e)))
        return
    await ctx.send("**{}** reloaded.".format(extension_name))

@bot.command()
async def color(ctx):
    await ctx.send('#'+hex(embedcolor)[2:])

#-----------------------------------------

if __name__ == "__main__":
    for extension in initial_extensions:
        try:
            bot.load_extension(extension)
        except Exception as e:
            exc = '{}: {}'.format(type(e).__name__, e)
            logger.warning('Failed to load extension {}\n{}'.format(extension, exc))

    with open('token.txt', 'r') as f:
        token = f.read()
        bot.run(token)
