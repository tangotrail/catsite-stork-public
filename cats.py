import json
import logging
import sqlite3
from collections import Counter
from discord.ext import commands
from datetime import datetime, timezone, timedelta

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

class cats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open('settings.json', 'r') as f:
            content = json.load(f)
            self.color = int(content['color'][2:], base=16)
            self.admin_ids = [int(discid) for discid in content['permissions']['admins']]

    #-----------------------------------------

    @commands.command()
    async def mayor(self, ctx, *, contents):
        # wipe original msg b/c it is v long
        await ctx.message.delete()
        lines = [line for line in contents.split('\n') if line]

        total = 0
        boosted = False
        summary = ''
        for i, stat in enumerate(get_stat_nicks()):
            num = int(lines[i*5 + 1])
            total += num
            boost = get_mayor_boost(num)

            summary += f'{get_stat_color(num)} {stat} {num} '
            if boost:
                summary += f'***+{boost}*** '
                boosted = True
            if i == 3: 
                summary += '\n'

        out = f'{ctx.message.author.mention} Stat total: **{total}**\n{summary}\n' 
        if not boosted:
            out += 'This cat provides no mayor boosts.'
        await ctx.send(out)

#-----------------------------------------

def setup(bot):
    bot.add_cog(cats(bot))

#-----------------------------------------

def thresholds(inputs, overflow):
    def threshold_f(num):
        for max_num, output in inputs:
            if num <= max_num:
                return output
        return overflow
    return threshold_f

def get_mayor_boost(num):
    f = thresholds([ \
        (18, 0),
        (22, 1),
        (26, 2),
        (30, 3),
    ], 4)
    return f(num)

def get_stat_color(num):
    f = thresholds([ \
        ( 6, '🔴'),
        (12, '🟠'),
        (16, '🟡'),
        (20, '🟢'),
        (24, '🔵'),
    ], '🟣')
    return f(num)

def get_stat_nicks():
    return ['STR', 'AGI', 'HLT', 'FIN', 'CLV', 'PRC', 'LCK']