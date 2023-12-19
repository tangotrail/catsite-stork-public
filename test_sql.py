import sqlite3
conn = sqlite3.connect('stork.db')
c = conn.cursor()

# c.execute('''CREATE TABLE whiskers
# 	(discordid text, item text) ''')

# c.execute('''CREATE TABLE whiskers_stock
#  	(item text, time timestamp) ''')

# c.execute('''CREATE TABLE whiskers_alias
# 	(item text, alias text) ''')

# c.execute('''CREATE TABLE item_value
# 	(item text, value integer) ''')

# c.execute('ALTER TABLE whiskers RENAME TO shops;')
# c.execute('ALTER TABLE whiskers_stock RENAME TO shops_stock;')

###### handle ios apostrophe 
# from shops_stocked_items import *

# all_items = []
# for v in BLACK_MARKET_STOCKED.values():
#     all_items.extend(v)

# apostrophes = [item for item in all_items if "'" in item]
# print(apostrophes)
# for item in apostrophes:
# 	alias = item.replace("'", "’")
# 	alias = item.replace("'", "")
# 	c.execute(f"INSERT INTO item_alias VALUES (?,?)", (item, alias))
# 	print(item, alias)
####################

conn.commit()
conn.close()
