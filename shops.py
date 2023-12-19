import json
import logging
import sqlite3
from collections import Counter
from collections import defaultdict
from discord import Embed
from discord.ext import commands
from datetime import datetime, timezone, timedelta

from items import get_item, parse_items, title
from shops_stocked_items import *

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

DATABASE = 'stork.db'
# TABLE shops (discordid text, item text) 
# TABLE shops_stock (item text, time timestamp)

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

BLANKCHAR = '\u200b' # discord embed fields can't be empty
DISCORD_CHAR_LIMIT = 2000

class shops(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open('settings.json', 'r') as f:
            content = json.load(f)
            self.color = int(content['color'][2:], base=16)
            self.admin_ids = [int(discid) for discid in content['permissions']['admins']]
            self.stocking_admin_ids = [int(discid) for discid in content['permissions']['stocking_admins']]

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

        rows = c.execute("SELECT * FROM shops_stock").fetchall()
        for item, time in rows:
            stock_time = time.replace(tzinfo=timezone.utc)
            if stock_time < last_restock_time:
                c.execute("DELETE FROM shops_stock WHERE item = ?", (item, ))

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
            rows = c.execute("SELECT * FROM shops WHERE item = ?", (item, )).fetchall()
            items_to_count[item] = len(rows)
            if rows:
                user_pings.update([f'<@{disc_id}>' for disc_id, timestamp in rows])

        done(conn)
        user_pings = list(user_pings)
        ping_msgs = [' '.join(user_pings[i:i+60]) for i in range(0, len(user_pings), 60)] 

        return self.generate_item_embeds([item for item, count in sorted(items_to_count.items())]), ping_msgs

    def generate_item_embeds(self, items):
        # input: sorted list of lowercase items from potentially different sources
        desc = ','.join([title(i) for i in items if ITEM_TO_TYPE[i] == ""])
        if desc:
            desc = '**Uncategorized:** ' + desc
        desc = f'Server last restocked: **{self.str_time_since()}**\n\n' + desc

        out = []
        item_types = set([ITEM_TO_TYPE[i] for i in items])

        if (len(item_types & WHISKERS_ITEM_TYPES) > 0):
            whiskers_embed=Embed(title="🎁 Jump to Whiskers' store", url="https://www.pixelcatsend.com/city/general-store#contentarea", \
                description=desc)
            for item_type in [COMMON, UNCOMMON, RARE]:
                whiskers_embed.add_field(name=item_type, value='\n'.join([title(i) for i in items if ITEM_TO_TYPE[i] == item_type]) + BLANKCHAR, inline=True)
            out.append(whiskers_embed)

        if (len(item_types & BLACK_MARKET_ITEM_TYPES) > 0):
            black_market_embed=Embed(title="💰 Jump to Black Market", url="https://www.pixelcatsend.com/city/black-market#contentarea", \
                description=desc)
            for item_type in [HUNTER, GATHERER, MINER, FISHER, BUG, GARDENER, HERBALIST, FARMER, FLOCKHERD]:
                black_market_embed.add_field(name=item_type, value='\n'.join([title(i) for i in items if ITEM_TO_TYPE[i] == item_type]) + BLANKCHAR, inline=True)
            out.append(black_market_embed)

        return out

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

        rows = c.execute("SELECT discordid FROM shops").fetchall()
        user_ids = set([int(r[0]) for r in rows])

        dead_users = {}
        for user_id in user_ids:
            member = self.bot.get_user(user_id)
            if member == None:
                dead_users[user_id] = []

        for dead_user_id in dead_users.keys():
            for row in c.execute("SELECT item FROM shops WHERE discordid = ?", (dead_user_id, )):
                dead_users[dead_user_id].append(row[0])
            c.execute("DELETE FROM shops WHERE discordid = ?", (dead_user_id, ))
        done(conn)

        logger.info(f'**{len(dead_users)} dead users cleaned from database: ** {str(dead_users)}')
        return f'**{len(dead_users)} cleaned: ** {str(dead_users)}'

    @commands.command()
    async def stock(self, ctx, *, contents):
        self.clean_stock()
        conn = connect()
        c = conn.cursor()

        now = datetime.now(timezone.utc)
        rows = c.execute("SELECT * FROM shops_stock").fetchall()
        stocked_items = {row[0]: row[1] for row in rows}
        
        valid_input_items = parse_items(contents, '\n')
        new_items = []
        existing_items = []
        for item in valid_input_items:
            # not already inputted since the last restock
            if item not in list(stocked_items.keys()):
                c.execute(f"INSERT INTO shops_stock VALUES (?,?)", (item, now))
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
            embeds, ping_msgs = self.get_pings(new_items)
            if ping_msgs:
                for i, msg in enumerate(ping_msgs):
                    if i == len(ping_msgs) - 1:
                        await ctx.send(msg)
                        for embed in embeds:
                            await ctx.send(embed=embed)
                    else:
                        await ctx.send(msg)
            else:
                for embed in embeds:
                    await ctx.send(embed=embed)

    @commands.command(aliases=['w', 'whisk', 'stocked', 'bm', 'shops'])
    async def all_stocked_items(self, ctx):
        self.clean_stock()
        conn = connect()
        c = conn.cursor()
        rows = c.execute("SELECT * FROM shops_stock").fetchall()
        embeds = self.generate_item_embeds(sorted([row[0] for row in rows]))
        for embed in embeds:
            await ctx.send(embed=embed)
        done(conn)

    @commands.command(aliases=['req'])
    async def request(self, ctx, *, item_names_str):
        out = await self.request_for_user(ctx, ctx.message.author.id, item_names_str)
        await ctx.send(out)

    @commands.command(aliases=['fill', 'received', 'unlist', 'receive'])
    async def fulfill(self, ctx, *, item_names_str):
        out = await self.fulfill_for_user(ctx, ctx.message.author.id, item_names_str)
        await ctx.send(out)

    @commands.command(aliases=['reqs', 'list'])
    async def requests(self, ctx):
        out = await self.requests_for_user(ctx, ctx.message.author.id)
        await ctx.send(out)

    @commands.command(aliases=['userreq'])
    async def user_request(self, ctx, user_id, *, item_names_str):
        if ctx.message.author.id not in self.admin_ids and \
            ctx.message.author.id not in self.stocking_admin_ids: 
            logger.info(f'Attempted user_request by {ctx.message.author.name} ({ctx.message.author.id}) with insufficient permissions')
            return

        out = await self.request_for_user(ctx, user_id, item_names_str)
        await ctx.send(out)

    @commands.command(aliases=['userfill'])
    async def user_fulfill(self, ctx, user_id, *, item_names_str):
        if ctx.message.author.id not in self.admin_ids and \
            ctx.message.author.id not in self.stocking_admin_ids: 
            logger.info(f'Attempted user_fulfill by {ctx.message.author.name} ({ctx.message.author.id}) with insufficient permissions')
            return

        out = await self.fulfill_for_user(ctx, user_id, item_names_str)
        await ctx.send(out)

    @commands.command(aliases=['userreqs', 'userlist'])
    async def user_requests(self, ctx, user_id):
        if ctx.message.author.id not in self.admin_ids and \
            ctx.message.author.id not in self.stocking_admin_ids: 
            logger.info(f'Attempted user_requests by {ctx.message.author.name} ({ctx.message.author.id}) with insufficient permissions')
            return

        out = await self.requests_for_user(ctx, user_id)
        await ctx.send(out)

    @commands.command()
    async def wipe(self, ctx, *, items=''):
        if ctx.message.author.id not in self.admin_ids and \
            ctx.message.author.id not in self.stocking_admin_ids: 
            logger.info(f'Attempted wipe by {ctx.message.author.name} ({ctx.message.author.id}) with insufficient permissions')
            return
        conn = connect()
        c = conn.cursor()
        if items:
            for item in parse_items(items):
                c.execute("DELETE FROM shops_stock WHERE item = ?", (item,))
            await ctx.send("Wiped items.")  
        else:
            c.execute("DELETE FROM shops_stock")
            await ctx.send("Wiped entire stock.")  
        done(conn)

    @commands.command()
    async def stats(self, ctx):
        conn = connect()
        c = conn.cursor()
        rows = c.execute("SELECT * FROM shops").fetchall()
        done(conn)

        users = len(set([row[0] for row in rows]))
        counter = Counter([row[1] for row in rows])
        top = counter.most_common(10)
        longest = max([len(name) for name, num in top])
        top_str = '\n'.join([f'{title(name):{longest+2}s} {num}' for name, num in top])

        out = f'**{users}** users requesting **{len(counter)}** unique items for a total of **{len(rows)}** requested items'
        out += f'\n```{top_str}```'
        await ctx.send(out)

    @commands.command(aliases=['allreqs'])
    async def requests_all(self, ctx):
        conn = connect()
        c = conn.cursor()
        rows = c.execute("SELECT * FROM shops").fetchall()
        done(conn)

        users = len(set([row[0] for row in rows]))
        counter = Counter([row[1] for row in rows])
        inverted = defaultdict(set)
        for k, v in counter.items():
            inverted[v].add(k)

        out = f'**{users}** users requesting **{len(counter)}** unique items for a total of **{len(rows)}** requested items'
        await ctx.send(out)

        all_list = [f'**{k}**: ' + ', '.join(title_sort(v)) for k, v in sorted(inverted.items(), reverse=True)]
        current_msg = ''
        for i in range(len(all_list)):
            if len(current_msg) + len(all_list[i]) < DISCORD_CHAR_LIMIT * .9:
                current_msg += '\n' + all_list[i]
            else:
                await ctx.send(current_msg.strip())
                current_msg = all_list[i]
        if current_msg:
            # TODO bandaid fix for too many items only being requested once
            if len(current_msg) > DISCORD_CHAR_LIMIT * .9:
                split = current_msg.split(', ')
                await ctx.send(', '.join(split[:len(split)//2]))
                await ctx.send(', '.join(split[len(split)//2:]))
            else:
                await ctx.send(current_msg)

    @commands.command(aliases=['spyreqs', 'spyreq'])
    async def requests_spy(self, ctx, *, item_name):
        self.clean_db()
        item = list(parse_items(item_name))[0]

        conn = connect()
        c = conn.cursor()

        item = get_item(c, item)
        rows = c.execute("SELECT discordid FROM shops WHERE item = ?", (item, )).fetchall()
        if len(rows) == 0:
            requesters = []
        else:
            requesters = [int(row[0]) for row in rows]
        done(conn)

        names = ' '.join([f'@{self.bot.get_user(r).name}#{self.bot.get_user(r).discriminator}' for r in requesters])
        await ctx.send(f'**{len(requesters)}** users requested **{title(item)}**: ```{names}```')

    @commands.command(aliases=['rereq'])
    async def requests_rename(self, ctx, *, msg):
        if ctx.message.author.id not in self.admin_ids and \
            ctx.message.author.id not in self.stocking_admin_ids: 
            logger.info(f'Attempted request rename by {ctx.message.author.name} ({ctx.message.author.id}) with insufficient permissions')
            return

        if ',' not in msg: 
            return
        item, new_name = [x.lower().strip() for x in msg.split(',')]

        conn = connect()
        c = conn.cursor()

        rows = c.execute("SELECT * FROM shops WHERE item = ?", (item, )).fetchall()
        ids = []
        if len(rows) > 0:
            c.execute("DELETE FROM shops WHERE item = ?", (item, ))
            for discordid, item_ in rows:
                c.execute("INSERT INTO shops VALUES (?,?)", (discordid, new_name))
                ids.append(discordid)
        done(conn)

        out = f'Renamed **{len(rows)}** requests from **{title(item)}** to **{title(new_name)}**.'
        out += f'\n```{", ".join(ids)}```'
        await ctx.send(out)

    #-----------------------------------------

    async def request_for_user(self, ctx, discordid, item_names):
        items_list = parse_items(item_names)
        logger.info(f'{ctx.message.author.name} requested {len(items_list)} items')
        
        conn = connect()
        c = conn.cursor()
        dupes, successes, warnings = [], [], []
        for item in items_list:
            item = get_item(c, item)
            rows = c.execute("SELECT * FROM shops WHERE discordid = ? AND item = ?", (discordid, item)).fetchall()
            if len(rows) == 0:
                c.execute(f"INSERT INTO shops VALUES (?,?)", (discordid, item))
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
            return out

    async def fulfill_for_user(self, ctx, discordid, item_names):
        items_list = parse_items(item_names)
        logger.info(f'{ctx.message.author.name} fulfilled {len(items_list)} items')

        conn = connect()
        c = conn.cursor()
        fails, successes = [], []
        for item in items_list:
            item = get_item(c, item)
            rows = c.execute("SELECT * FROM shops WHERE discordid = ? AND item = ?", (discordid, item)).fetchall()
            if len(rows) > 0:
                c.execute("DELETE FROM shops WHERE discordid = ? AND item = ?", (discordid, item))
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
            return out

    async def requests_for_user(self, ctx, discordid):
        conn = connect()
        c = conn.cursor()
        items_list = []
        warnings = []
        for row in c.execute("SELECT * FROM shops WHERE discordid = ?", (discordid, )):
            items_list.append(row[1])
            if row[1] not in ALL_ITEMS_STOCKED:
                warnings.append(row[1])
        done(conn)

        out = f':page_facing_up: You have **{len(items_list)}** requested item(s): '
        out += f'{", ".join(title_sort(items_list))}'
        if warnings:
            out += f'\n:warning: **{len(warnings)}** potentially invalid requests: {", ".join(title_sort(warnings))}\n'
        return out


#-----------------------------------------

def setup(bot):
    bot.add_cog(shops(bot))

#-----------------------------------------

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

