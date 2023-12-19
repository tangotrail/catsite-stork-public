def filter(line_item):
    if line_item.strip() == '':
        return False

    for season in ['spring', 'summer', 'autumn', 'winter']:
        if line_item == season:
            return False

    if 'ID# ' in line_item:
        return False

    for rarity in ['very rare', 'rare', 'uncommon', 'common']:
        if f' - {rarity}' in line_item:
            return False

    if '_' in line_item and line_item.lower() == line_item:
        return False

    return True

with open('raw_items_list.txt', 'r') as f:
    contents = f.read().split('\n')
    contents = [f'"{x}"' for x in contents if filter(x)]
    
    with open('raw_items_list_out.txt', 'w') as ff:
        ff.write(', '.join(contents))