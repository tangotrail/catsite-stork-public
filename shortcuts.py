import json
import discord
from discord.ext import commands

class shortcuts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open('settings.json', 'r') as f:
            content = json.load(f)
            self.color = int(content['color'][2:], base=16)

        self.file = 'shortcuts.json'

    #-----------------------------------------

    # edit shortcuts
    @commands.group(invoke_without_subcommand=True, aliases=['sc'])
    async def shortcut(self, ctx):
        if ctx.invoked_subcommand is None:
            cmds = []
            cmds.append(['/sc add <name> <contents>', 'create a shortcut (name cannot have spaces)'])
            cmds.append(['/sc remove <name>', 'remove a shortcut'])
            cmds.append(['/sc list', 'list all shortcuts'])
            out = '\n'.join([f"**{cmd[0]}**\n-- {cmd[1]}" for cmd in cmds])
            out = 'Summon a shortcut with any of: /get /grab /show /lookup\n\n' + out
            await ctx.send(out)

    @commands.command(aliases=['get', 'grab', 'show', 'lookup'])
    async def shortcut_summon(self, ctx, name=''):
        if not name:
            with open(self.file, 'r') as f:
                content = json.load(f)
                if content:
                    await ctx.send('Summon a shortcut with any of: /get /grab /show /lookup\n**Available shortcuts:**\n' + ', '.join(sorted([x for x in content])))
            return 

        with open(self.file, 'r') as f:
            f = json.load(f)
            if name not in f:
                await ctx.send('Shortcut not found.')
                return
            await ctx.send(f[name])

    @shortcut.command(aliases=['add'])
    async def shortcut_add(self, ctx, name, *, msg):
        with open(self.file, 'r') as f:
            content = json.load(f)
            if name in content:
                deleted = content[name]
                await ctx.send(f"Overrode shortcut **{name}**.")
                await ctx.send(f"Old: \n>>> {deleted}")
                await ctx.send(f"New: \n>>> {msg}")
            else:
                await ctx.send(f"Created shortcut **{name}**.")
                await ctx.send(f">>> {msg}")
            content[name] = msg
        with open(self.file, 'w') as f:
            json.dump(content, f, indent=4)

    @shortcut.command(aliases=['remove'])
    async def shortcut_remove(self, ctx, name):
        with open(self.file, 'r') as f:
            content = json.load(f)
            if name in content:
                deleted = content[name]
                del content[name]
                await ctx.send(f"Deleted shortcut **{name}**.")
                await ctx.send(f">>> {deleted}")
            else:
                await ctx.send(f"Shortcut **{name}** does not exist.")
                return
        with open(self.file, 'w') as f:
            json.dump(content, f, indent=4)

    @shortcut.command(aliases=['list', 'all'])
    async def shortcut_list(self, ctx):
        with open(self.file, 'r') as f:
            content = json.load(f)
            if content:
                await ctx.send(', '.join([x for x in content]))
            else:
                await ctx.send('There are no shortcuts.')


#-----------------------------------------

def setup(bot):
    bot.add_cog(shortcuts(bot))

#-----------------------------------------
