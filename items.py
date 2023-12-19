import json
import logging
import sqlite3
from collections import Counter
from discord.ext import commands
from datetime import datetime, timezone, timedelta
import string

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

DATABASE = 'stork.db'
# TABLE item_alias (item text, alias text)
# TABLE item_value (item text, value integer)

class items(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open('settings.json', 'r') as f:
            content = json.load(f)
            self.color = int(content['color'][2:], base=16)
            self.admin_ids = [int(discid) for discid in content['permissions']['admins']]

    #-----------------------------------------

    @commands.command()
    async def value(self, ctx, *, contents):
        if ctx.message.author.id not in self.admin_ids: 
            logger.debug(f'Attempted items.value() by {ctx.message.author.name} ({ctx.message.author.id}) with insufficient permissions')
            return

        conn = connect()
        c = conn.cursor()

        def get_value(line):
            val = line.strip().replace('sell value: ', '').replace(' notes', '')
            if is_int(val):
                return int(val)
            return 0

        rows = c.execute("SELECT * FROM item_value").fetchall()
        existing_items = {row[0]: row[1] for row in rows}
        new_values = {}
        replaced_values = {}

        current_item = ''
        lines = contents.lower().replace('\r', '').split('\n')
        for line in lines:
            if is_item(line):
                current_item = line
            elif current_item and 'sell value: ' in line:
                if current_item in existing_items:
                    replaced_values[current_item] = get_value(line)
                else:
                    new_values[current_item] = get_value(line)
                current_item = ''

        for item, val in new_values.items():
            c.execute(f"INSERT INTO item_value VALUES (?,?)", (item, val))
        for item, val in replaced_values.items():
            c.execute(f"UPDATE item_value SET value = (?) WHERE item = (?)", (val, item))

        done(conn)
        await ctx.message.delete()

        out = ''
        if new_values:
            out += f'**{len(new_values)} new values:** '
            out += ', '.join(f'{title(item)} ({val})' for item, val in new_values.items())
            out += '\n'
        if replaced_values:
            out += f'**{len(replaced_values)} replaced values:** '
            out += ', '.join(f'{title(item)} ({val})' for item, val in replaced_values.items())
        await ctx.send(out)

    @commands.command()
    async def price(self, ctx, *, contents):
        conn = connect()
        c = conn.cursor()

        item_list = [get_item(c, item.strip()) for item in contents.lower().split(',')]

        appraised_items = {}
        valueless_items = []
        for item in item_list:
            row = c.execute("SELECT * FROM item_value WHERE item = ?", (item, )).fetchone()
            if row is None:
                valueless_items.append(item)
            else:
                appraised_items[item] = row[1]
        done(conn)

        out = ''
        if appraised_items:
            out += 'For out of season items, multiply Whiskers price by 3. Some items that can be quicksold are not sold by Whiskers.\n'
            for item, val in appraised_items.items():
                out += f'**{title(item)}:** {val} quicksale, {val*4} whiskers\n'
        if valueless_items:
            out += f':x: Values could not be found for **{len(valueless_items)}** items.'
        await ctx.send(out)

    @commands.command()
    async def appraise(self, ctx, *, contents):
        conn = connect()
        c = conn.cursor()

        def get_qty(line):
            val = line.strip().replace('qty: ', '')
            if is_int(val):
                return int(val)
            return 0

        item_quantities = {}
        current_qty = 0

        lines = contents.lower().replace('\r', '').split('\n')
        for line in lines:
            if current_qty and is_item(line):
                item_quantities[line] = current_qty
                current_qty = 0
            elif 'qty: ' in line:
                current_qty = get_qty(line)

        rows = c.execute("SELECT * FROM item_value").fetchall()
        item_values = {row[0]: row[1] for row in rows}

        total_notes = 0
        total_items = 0
        valueless_items = []
        for item, qty in item_quantities.items():
            if item in item_values:
                total_notes += item_values[item] * qty
                total_items += qty
            else:
                valueless_items.append(item)

        done(conn)
        await ctx.message.delete()

        out = f'Quicksale value of **{total_notes}** notes for {len(item_quantities)} unique items and {total_items} total items.\n'
        if valueless_items:
            out += f':x: **{len(valueless_items)}** items with no available value: '
            out += ', '.join(title_sort(valueless_items))
            out += '\n'
        if total_items:
            out += ':white_check_mark: '
            out += ', '.join(f'{title(item)} ({qty})' for item, qty in item_quantities.items() if item not in valueless_items)
        await ctx.send(out)

    #-----------------------------------------

    @commands.command(aliases=['listalias', 'aliaslist', 'aliases'])
    async def list_alias(self, ctx):
        conn = connect()
        c = conn.cursor()
        rows = c.execute("SELECT * FROM item_alias").fetchall()
        done(conn)

        alias_map = {}
        for row in rows:
            item, alias = row
            if item in alias_map:
                alias_map[item].append(alias)
            else:
                alias_map[item] = [alias]

        out = []
        for item in sorted(alias_map):
            aliases = alias_map[item]
            aliases = [title(a) for a in aliases]
            out.append(f'**{title(item)}** [ {", ".join(aliases)} ]')

        out_msgs = ['\n'.join(out[i:i+30]) for i in range(0, len(out), 30)] 
        for out_msg in out_msgs:
            await ctx.send(out_msg)

    @commands.command(aliases=['alias'])
    async def add_alias(self, ctx, *, msg):
        if ',' not in msg: 
            return
        item, alias = [x.lower().strip() for x in msg.split(',')]

        conn = connect()
        c = conn.cursor()
        rows = c.execute("SELECT * FROM item_alias WHERE item = ? AND alias = ?", (item, alias)).fetchall()
        if len(rows) == 0:
            c.execute(f"INSERT INTO item_alias VALUES (?,?)", (item, alias))
            await ctx.send(f':white_check_mark: `{title(alias)}` is now an alias for `{title(item)}`')
        else:
            await ctx.send(f':x: `{title(alias)}` was already an alias for `{title(item)}`')
        done(conn)

    @commands.command(aliases=['dealias', 'unalias'])
    async def remove_alias(self, ctx, *, msg):
        if ',' not in msg: 
            return
        item, alias = [x.lower().strip() for x in msg.split(',')]

        conn = connect()
        c = conn.cursor()
        rows = c.execute("SELECT * FROM item_alias WHERE item = ? AND alias = ?", (item, alias)).fetchall()
        if len(rows) > 0:
            c.execute("DELETE FROM item_alias WHERE item = ? AND alias = ?", (item, alias))
            await ctx.send(f':white_check_mark: `{title(alias)}` is no longer an alias for `{title(item)}`')
        else:
            await ctx.send(f':x: `{title(alias)}` was not an alias for `{title(item)}`')
        done(conn)

#-----------------------------------------

def setup(bot):
    bot.add_cog(items(bot))

#-----------------------------------------

def title(i):
    return string.capwords(i)

def title_sort(l):
    return sorted([title(x) for x in l])

def connect():
    return sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES)

def done(conn):
    conn.commit()
    conn.close()

def is_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

# these are imported in whiskers.py

def is_item(item):
    disqualifiers = ['paper note', 'qty:', 'cost:', 'id#', 'sell value']
    disqualifiers.extend(['resources', 'trinkets', 'clothing', 'decor', 'buildings', 'gear', 'collectables'])
    for bad_key in disqualifiers:
        if bad_key in item.lower() or item.lower().strip() == '' or is_int(item):
            return False
    return True

def parse_items(item_list, delim=','):
    return set([i.lower().strip() for i in item_list.split(delim) if is_item(i)])

def get_item(cursor, name):
    potential_alias = cursor.execute("SELECT * FROM item_alias WHERE alias = ?", (name, )).fetchone()
    if potential_alias is None: # no aliases, return original item name
        return name
    return potential_alias[0]