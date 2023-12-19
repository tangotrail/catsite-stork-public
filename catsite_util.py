import json
import logging
import sqlite3
from discord.ext import commands
from datetime import datetime, timedelta
from datetime import date as dtdate
from zoneinfo import ZoneInfo

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

SEASONS = { 0: 'Spring', 1: 'Summer', 2: 'Autumn', 3: 'Winter' }
SEASONS_EMOTES = ['🌸', '🌴', '🍂', '❄️']
SEASONS_INV = {v: k for k, v in SEASONS.items()}
SEASONS_INV.update({ 
    'Spr': 0, 
    'Sum': 1, 
    'Aut': 2, 
    'Win': 3,
    'Sp': 0, 
    'Su': 1, 
    'Au': 2, 
    'Wi': 3,
    'Fall': 2,
    'Fa': 2,
})
CAT_DAYS_PER_SEASON = 49 
CAT_DAYS_PER_YEAR = 4 * CAT_DAYS_PER_SEASON
CAT_ORIGIN_DATE = dtdate(2019, 9, 1)
CAT_LIFE_STAGES = [
    ('Birth', 0), 
    ('Young Kitten', 28), 
    ('Kitten', 56), 
    ('Adolescent', 84), 
    ('Adult', 112), 
]

class CatDate:
    def __init__(self, days_since_origin):
        self.days_since_origin = days_since_origin
        self.cat_season, self.cat_day, self.cat_year = self.convert_to_catdate()
        self.real_date = self.convert_from_catdate()

    def convert_to_catdate(self):
        year = self.days_since_origin // CAT_DAYS_PER_YEAR
        day_in_year = self.days_since_origin - year * CAT_DAYS_PER_YEAR
        season = day_in_year // 49  
        day_in_season = day_in_year - season * CAT_DAYS_PER_SEASON
        return season, day_in_season+1, year+1

    def convert_from_catdate(self):
        return CAT_ORIGIN_DATE + timedelta(days=self.days_since_origin)

    def cat_birth(self):
        age = (today_est() - self.real_date).days
        out = [f'A cat born on {self} is **{age}** days old.\n']
        for stage, days in CAT_LIFE_STAGES:
            if age < days:
                out.append(f'**{stage}:** {self.add(days)} ({days - age} days left)')
            else:
                out.append(f'**{stage}:** {self.add(days)}')
        return '\n'.join(out)

    def days_of_age(self):
        return (today_est() - self.real_date).days

    def add(self, days: int):
        return CatDate(self.days_since_origin + days)

    def sub(self, days: int):
        return CatDate(self.days_since_origin - days)

    def __str__(self):
        return f'{self.catdate_str()} **[ {self.date_str()} ]**'

    def catdate_str(self):
        return f'{SEASONS_EMOTES[self.cat_season]} {SEASONS[self.cat_season]} {self.cat_day}, Year {self.cat_year}'

    def date_str(self):
        return self.real_date.strftime('%b %d, %Y')

class catsite_util(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open('settings.json', 'r') as f:
            content = json.load(f)
            self.color = int(content['color'][2:], base=16)
            self.admin_ids = [int(discid) for discid in content['permissions']['admins']]

    #-----------------------------------------

    @commands.command()
    async def date(self, ctx, *, input_date=''):
        try:
            if not input_date:
                d = today_est()
            else:
                d = dtdate.fromisoformat(input_date)
        except:
            await ctx.send('Invalid format - expected YYYY-MM-DD, eg. `2021-08-02`.')
            return

        days_since_origin = (d - CAT_ORIGIN_DATE).days
        await ctx.send(self.get_catdate_info(CatDate(days_since_origin)))

    @commands.command()
    async def catdate(self, ctx, *, input_date=''):
        parsed = self.parse_catdate(input_date)
        if parsed is None:
            await ctx.send('Invalid format - expected `Autumn 24, 4` or `Autumn 24, Year 4`.')
            return

        await ctx.send(self.get_catdate_info(parsed))

    @commands.command()
    async def age(self, ctx, days_of_age: int):
        birth = CatDate((today_est() - CAT_ORIGIN_DATE).days - days_of_age)

        await ctx.send(birth.cat_birth())

    @commands.command(aliases=['bday'])
    async def birthday(self, ctx, *, input_date):
        parsed = self.parse_catdate(input_date)
        if parsed is None:
            await ctx.send('Invalid format - expected `Autumn 24, 4` or `Autumn 24, Year 4`.')
            return

        await ctx.send(parsed.cat_birth())

    def parse_catdate(self, catdate_str):
        try:
            season, day, year = catdate_str.lower().replace(', year', '').replace(',', '').split(' ')
            season = SEASONS_INV[season.title()]
            day = int(day)
            year = int(year)
        except:
            return None

        days_since_origin = (year - 1) * CAT_DAYS_PER_YEAR + season * CAT_DAYS_PER_SEASON + (day - 1)
        return CatDate(days_since_origin)

    def get_catdate_info(self, catdate):
        prev_week = catdate.sub(7)
        next_week = catdate.add(7)

        days_since = (today_est() - catdate.real_date).days
        if days_since < 0:
            out = f'{catdate} is in **{-days_since}** days.\n'
        else:
            out = f'{catdate} was **{days_since}** days ago.\n'
        out += f'**7 days ago:** {prev_week} \n**7 days later:** {next_week}'
        return out

    #-----------------------------------------

    @commands.command()
    async def source(self, ctx, *, contents):
        await ctx.send(f'<https://www.pixelcatsend.com/items&search={contents}>')

    @commands.command()
    async def user(self, ctx, *, contents):
        await ctx.send(f'<https://www.pixelcatsend.com/profile&username={contents}>')

#-----------------------------------------

def setup(bot):
    bot.add_cog(catsite_util(bot))

#-----------------------------------------

def today_est():
    return datetime.now(ZoneInfo('US/Eastern')).date()
