# 7/17/2023 
# DEPRECATED
# replaced by shops.py

import json
import logging
import sqlite3
from collections import Counter
from collections import defaultdict
from discord import Embed
from discord.ext import commands
from datetime import datetime, timezone, timedelta
from items import get_item, parse_items

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

DATABASE = 'stork.db'
# TABLE whiskers (discordid text, item text) 
# TABLE whiskers_stock (item text, time timestamp)

SECS_PER_HR = 60*60

# 0, 6, 12, 18 ET
# 4, 10, 16, 22 UTC during daylight savings
FIRST_RESTOCK_MINS = 4*60 + 2
SECOND_RESTOCK_MINS = FIRST_RESTOCK_MINS + 60*6*1
THIRD_RESTOCK_MINS = FIRST_RESTOCK_MINS + 60*6*2
FOURTH_RESTOCK_MINS = FIRST_RESTOCK_MINS + 60*6*3

# 5, 11, 17, 23 UTC else
# FIRST_RESTOCK_MINS = 5*60 + 2
# SECOND_RESTOCK_MINS = FIRST_RESTOCK_MINS + 60*6*1
# THIRD_RESTOCK_MINS = FIRST_RESTOCK_MINS + 60*6*2
# FOURTH_RESTOCK_MINS = FIRST_RESTOCK_MINS + 60*6*3

COMMON = "Common 🐟"
UNCOMMON = "Uncommon 🪶"
RARE = "Rare 🌹"
STOCKED = {
    COMMON: "Bantam Eggs, Black Ink, Bricks, Bug Flour, Cotton, Fish, Iron Bars, Large Autumn Leaves, Large Crunchy Leaves, Large Leaves, Mixed Seeds, Paints, Poultry, Red Meat, Rice, Rocks, Spool Of Thread, Sticks, Sticky Glue, Tea Leaves, Wooden Planks",
    UNCOMMON: "Cat-Tatoes, Catbage, Catrots, Clay, Crayfish, Crickets, Feathers, Freshwater Mussels, Graphite, Iron Ore, Leather, Oil, Paper Bark, Sand, Silkworm Cocoon, Snow Ants, Snowmeowtoes, Snowpeas, Snowspider Silk, Wildflowers, Woolly Bun Wool",
    RARE: "Black Tulips, Bleeding Hearts, Bones, Broccatli, Button Mushrooms, Catmint, Caulimeower, Chamomile, Chromite, Cobalt Ore, Copper Ore, Crocus, Daisies, Dandelion, Fallen Meteorite, Fireflies, Forget-Me-Not, Fur Hide, Gold Ore, Green Dianthus, Honeycomb, Lakeweed, Licorice, Limestone, Mini-Pig Cheese, Mini-Pig Milk, Nickel Ore, Nitratine, Not-Holly, Parsley, Periwinkle, Poisonous Mushrooms, Red Carnations, Rosemary, Scales, Silver Fireflies, Silver Ore, Silverseal, Snowcap Mushrooms, Snowdrops, Starfruit, Sulfur, Sunflowers, Sweet Cat-Tatoes, Thyme, Tiger Lilies, Tin, Tree Sap, Uncut Amethyst, Uncut Diamond, Uncut Emerald, Uncut Quartz, Uncut Rose Quartz, Uncut Ruby, Uncut Sapphire, Violets, Walnuts, Watermeowlon, Wintermint"
}

ALL_ITEMS_STOCKED = []
ITEM_TO_TYPE = defaultdict(str)
for k, v in STOCKED.items():
    STOCKED[k] = STOCKED[k].lower().split(', ')
    ALL_ITEMS_STOCKED.extend(STOCKED[k])
    for item in STOCKED[k]:
        ITEM_TO_TYPE[item] = k

BLANKCHAR = '\u200b' # discord embed fields can't be empty

class whiskers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open('settings.json', 'r') as f:
            content = json.load(f)
            self.color = int(content['color'][2:], base=16)
            self.admin_ids = [int(discid) for discid in content['permissions']['admins']]
            self.whiskers_admin_ids = [int(discid) for discid in content['permissions']['stocking_admins']]

    #-----------------------------------------

    def last_restock(self):
        now = datetime.now(timezone.utc)
        mins_since_utc_midn = now.hour*60 + now.minute

        restock_time = None
        if mins_since_utc_midn < FIRST_RESTOCK_MINS:
            restock_time = datetime(now.year, now.month, now.day, 
                hour = FOURTH_RESTOCK_MINS//60, 
                minute = FOURTH_RESTOCK_MINS - 60*(FOURTH_RESTOCK_MINS//60), 
                tzinfo = timezone.utc) - timedelta(days=1)
        else:
            last = FIRST_RESTOCK_MINS
            if mins_since_utc_midn < SECOND_RESTOCK_MINS:
                last = FIRST_RESTOCK_MINS
            elif mins_since_utc_midn < THIRD_RESTOCK_MINS:
                last = SECOND_RESTOCK_MINS
            elif mins_since_utc_midn < FOURTH_RESTOCK_MINS:
                last = THIRD_RESTOCK_MINS
            elif mins_since_utc_midn >= FOURTH_RESTOCK_MINS:
                last = FOURTH_RESTOCK_MINS
            restock_time = datetime(now.year, now.month, now.day, 
                hour = last//60, 
                minute = last - 60*(last//60), 
                tzinfo = timezone.utc)

        return restock_time

    def clean_stock(self):
        last_restock_time = self.last_restock()
        conn = connect()
        c = conn.cursor()

        rows = c.execute("SELECT * FROM whiskers_stock").fetchall()
        for item, time in rows:
            stock_time = time.replace(tzinfo=timezone.utc)
            if stock_time < last_restock_time:
                c.execute("DELETE FROM whiskers_stock WHERE item = ?", (item, ))

        done(conn)

    def str_time_since(self, timestamp=None):
        if timestamp == None:
            timestamp = self.last_restock()
        now = datetime.now(timezone.utc)
        time_since = now - timestamp
        seconds = time_since.seconds
        hours_since = seconds // SECS_PER_HR
        return f'{hours_since}h {(seconds - SECS_PER_HR*hours_since) // 60}m'

    def get_pings(self, item_list):
        conn = connect()
        c = conn.cursor()

        items_to_count = {}
        user_pings = set()

        for item in item_list:
            rows = c.execute("SELECT * FROM whiskers WHERE item = ?", (item, )).fetchall()
            items_to_count[item] = len(rows)
            if rows:
                user_pings.update([f'<@{disc_id}>' for disc_id, timestamp in rows])

        done(conn)
        user_pings = list(user_pings)
        ping_msgs = [' '.join(user_pings[i:i+60]) for i in range(0, len(user_pings), 60)] 

        return self.generate_item_embed([item for item, count in sorted(items_to_count.items())]), ping_msgs

    def generate_item_embed(self, items):
        # input: sorted list of lowercase items
        desc = ','.join([i.title() for i in items if ITEM_TO_TYPE[i] == ""])
        if desc:
            desc = '**Uncategorized:** ' + desc
        desc = f'Server last restocked: **{self.str_time_since()}**\n\n' + desc
        embed=Embed(title="🎁 Jump to Whiskers' store", url="https://www.pixelcatsend.com/city/general-store#contentarea", \
            description=desc)
        embed.add_field(name=COMMON, value='\n'.join([i.title() for i in items if ITEM_TO_TYPE[i] == COMMON]) + BLANKCHAR, inline=True)
        embed.add_field(name=UNCOMMON, value='\n'.join([i.title() for i in items if ITEM_TO_TYPE[i] == UNCOMMON]) + BLANKCHAR, inline=True)
        embed.add_field(name=RARE, value='\n'.join([i.title() for i in items if ITEM_TO_TYPE[i] == RARE]) + BLANKCHAR, inline=True)
        return embed 

    @commands.command(aliases=['cleandb', 'clean_db'])
    async def clean_db_cmd(self, ctx):
        # clean out users who have left the server
        if ctx.message.author.id not in self.admin_ids:
            logger.info(f'Attempted database clean by {ctx.message.author.name} ({ctx.message.author.id}) with insufficient permissions')
            return

        await ctx.send(self.clean_db())

    def clean_db(self):
        conn = connect()
        c = conn.cursor()

        rows = c.execute("SELECT discordid FROM whiskers").fetchall()
        user_ids = set([int(r[0]) for r in rows])

        dead_users = {}
        for user_id in user_ids:
            member = self.bot.get_user(user_id)
            if member == None:
                dead_users[user_id] = []

        for dead_user_id in dead_users.keys():
            for row in c.execute("SELECT item FROM whiskers WHERE discordid = ?", (dead_user_id, )):
                dead_users[dead_user_id].append(row[0])
            c.execute("DELETE FROM whiskers WHERE discordid = ?", (dead_user_id, ))
        done(conn)

        logger.info(f'**{len(dead_users)} dead users cleaned from database: ** {str(dead_users)}')
        return f'**{len(dead_users)} cleaned: ** {str(dead_users)}'

    @commands.command()
    async def stock(self, ctx, *, contents):
        self.clean_stock()
        conn = connect()
        c = conn.cursor()

        now = datetime.now(timezone.utc)
        rows = c.execute("SELECT * FROM whiskers_stock").fetchall()
        stocked_items = {row[0]: row[1] for row in rows}
        
        valid_input_items = parse_items(contents, '\n')
        new_items = []
        existing_items = []
        for item in valid_input_items:
            # not already inputted since the last restock
            if item not in list(stocked_items.keys()):
                c.execute(f"INSERT INTO whiskers_stock VALUES (?,?)", (item, now))
                new_items.append(item)
            else:
                existing_items.append(item)

        done(conn)
        await ctx.message.delete()
        out = f'Thank you for stocking **{len(new_items)}** new items, {ctx.message.author.mention}!'
        if existing_items:
            out += f'\nAn additional {len(existing_items)} items were previously stocked.'
        await ctx.send(out)

        if new_items:
            embed, ping_msgs = self.get_pings(new_items)
            for i, msg in enumerate(ping_msgs):
                if i == len(ping_msgs) - 1:
                    await ctx.send(msg, embed=embed)
                else:
                    await ctx.send(msg)

    @commands.command(aliases=['w'])
    async def whisk(self, ctx):
        self.clean_stock()
        conn = connect()
        c = conn.cursor()
        rows = c.execute("SELECT * FROM whiskers_stock").fetchall()
        await ctx.send(embed=self.generate_item_embed(sorted([row[0] for row in rows])))
        done(conn)

    @commands.command(aliases=['req'])
    async def request(self, ctx, *, item_names):
        items_list = parse_items(item_names)
        logger.info(f'{ctx.message.author.name} requested {len(items_list)} items')
        
        conn = connect()
        c = conn.cursor()
        discordid = ctx.message.author.id 
        dupes, successes, warnings = [], [], []
        for item in items_list:
            item = get_item(c, item)
            rows = c.execute("SELECT * FROM whiskers WHERE discordid = ? AND item = ?", (discordid, item)).fetchall()
            if len(rows) == 0:
                c.execute(f"INSERT INTO whiskers VALUES (?,?)", (discordid, item))
                successes.append(item)
            else:
                dupes.append(item)
            if item not in ALL_ITEMS_STOCKED:
                warnings.append(item)
        done(conn)

        out = ''
        if len(successes):
            out += f':white_check_mark: **{len(successes)}** requested: {", ".join(title_sort(successes))}\n'
        if len(dupes):
            out += f':x: **{len(dupes)}** already requested: {", ".join(title_sort(dupes))}\n'
        if len(warnings):
            out += f':warning: **{len(warnings)}** potentially invalid requests: {", ".join(title_sort(warnings))}\n'
        if out:
            await ctx.send(out)

    @commands.command(aliases=['fill', 'received', 'unlist', 'receive'])
    async def fulfill(self, ctx, *, item_names):
        items_list = parse_items(item_names)
        logger.info(f'{ctx.message.author.name} fulfilled {len(items_list)} items')

        conn = connect()
        c = conn.cursor()
        discordid = ctx.message.author.id 
        fails, successes = [], []
        for item in items_list:
            item = get_item(c, item)
            rows = c.execute("SELECT * FROM whiskers WHERE discordid = ? AND item = ?", (discordid, item)).fetchall()
            if len(rows) > 0:
                c.execute("DELETE FROM whiskers WHERE discordid = ? AND item = ?", (discordid, item))
                successes.append(item)
            else:
                fails.append(item)
        done(conn)

        out = ''
        if len(successes):
            out += f':white_check_mark: **{len(successes)}** fulfilled: {", ".join(title_sort(successes))}\n'
        if len(fails):
            out += f':x: {len(fails)} nonrequests: {", ".join(title_sort(fails))}\n'
        if out:
            await ctx.send(out)

    @commands.command(aliases=['reqs', 'list'])
    async def requests(self, ctx):
        conn = connect()
        c = conn.cursor()
        discordid = ctx.message.author.id 
        items_list = []
        warnings = []
        for row in c.execute("SELECT * FROM whiskers WHERE discordid = ?", (discordid, )):
            items_list.append(row[1])
            if row[1] not in ALL_ITEMS_STOCKED:
                warnings.append(row[1])
        done(conn)

        out = f':page_facing_up: You have **{len(items_list)}** requested item(s): '
        out += f'{", ".join(title_sort(items_list))}'
        if warnings:
            out += f'\n:warning: **{len(warnings)}** potentially invalid requests: {", ".join(title_sort(warnings))}\n'
        await ctx.send(out)

    @commands.command()
    async def wipe(self, ctx, *, items=''):
        if ctx.message.author.id not in self.admin_ids and \
            ctx.message.author.id not in self.whiskers_admin_ids: 
            logger.info(f'Attempted wipe by {ctx.message.author.name} ({ctx.message.author.id}) with insufficient permissions')
            return
        conn = connect()
        c = conn.cursor()
        if items:
            for item in parse_items(items):
                c.execute("DELETE FROM whiskers_stock WHERE item = ?", (item,))
            await ctx.send("Wiped items.")  
        else:
            c.execute("DELETE FROM whiskers_stock")
            await ctx.send("Wiped entire stock.")  
        done(conn)

    @commands.command()
    async def stats(self, ctx):
        conn = connect()
        c = conn.cursor()
        rows = c.execute("SELECT * FROM whiskers").fetchall()
        done(conn)

        users = len(set([row[0] for row in rows]))
        counter = Counter([row[1] for row in rows])
        top = counter.most_common(10)
        longest = max([len(name) for name, num in top])
        top_str = '\n'.join([f'{name.title():{longest+2}s} {num}' for name, num in top])

        out = f'**{users}** users requesting **{len(counter)}** unique items for a total of **{len(rows)}** requested items'
        out += f'\n```{top_str}```'
        await ctx.send(out)

    @commands.command(aliases=['allreqs'])
    async def requests_all(self, ctx):
        conn = connect()
        c = conn.cursor()
        rows = c.execute("SELECT * FROM whiskers").fetchall()
        done(conn)

        users = len(set([row[0] for row in rows]))
        counter = Counter([row[1] for row in rows])
        inverted = defaultdict(set)
        for k, v in counter.items():
            inverted[v].add(k)

        all_str = '\n'.join([f'**{k}**: ' + ', '.join(title_sort(v)) for k, v in sorted(inverted.items(), reverse=True)])

        out = f'**{users}** users requesting **{len(counter)}** unique items for a total of **{len(rows)}** requested items \n{all_str}'
        await ctx.send(out)

    @commands.command(aliases=['spyreqs', 'spyreq'])
    async def requests_spy(self, ctx, *, item_name):
        self.clean_db()
        item = list(parse_items(item_name))[0]

        conn = connect()
        c = conn.cursor()

        item = get_item(c, item)
        rows = c.execute("SELECT discordid FROM whiskers WHERE item = ?", (item, )).fetchall()
        if len(rows) == 0:
            requesters = []
        else:
            requesters = [int(row[0]) for row in rows]
        done(conn)

        names = ' '.join([f'@{self.bot.get_user(r).name}#{self.bot.get_user(r).discriminator}' for r in requesters])
        await ctx.send(f'**{len(requesters)}** users requested **{item.title()}**: ```{names}```')

    @commands.command(aliases=['rereq'])
    async def requests_rename(self, ctx, *, msg):
        if ctx.message.author.id not in self.admin_ids and \
            ctx.message.author.id not in self.whiskers_admin_ids: 
            logger.info(f'Attempted request rename by {ctx.message.author.name} ({ctx.message.author.id}) with insufficient permissions')
            return

        if ',' not in msg: 
            return
        item, new_name = [x.lower().strip() for x in msg.split(',')]

        conn = connect()
        c = conn.cursor()

        rows = c.execute("SELECT * FROM whiskers WHERE item = ?", (item, )).fetchall()
        ids = []
        if len(rows) > 0:
            c.execute("DELETE FROM whiskers WHERE item = ?", (item, ))
            for discordid, item_ in rows:
                c.execute("INSERT INTO whiskers VALUES (?,?)", (discordid, new_name))
                ids.append(discordid)
        done(conn)

        out = f'Renamed **{len(rows)}** requests from **{item.title()}** to **{new_name.title()}**.'
        out += f'\n```{", ".join(ids)}```'
        await ctx.send(out)

#-----------------------------------------

def setup(bot):
    bot.add_cog(whiskers(bot))

#-----------------------------------------

def title_sort(l):
    return sorted([x.title() for x in l])

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

