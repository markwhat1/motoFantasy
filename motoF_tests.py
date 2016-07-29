# import simplejson as json
# import requests

# r = requests.get(
#     'http://americanmotocrosslive.com/xml/mx/Announcements.json').text

# j = json.dumps(r, sort_keys=True, indent=4 * ' ')
# print(j)

import pandas as pd
from parsel import Selector
import requests
import schedule
import time
from xlwings import Workbook, Range

# from sqlalchemy import create_engine

################
sxSeason = False
################

if sxSeason is True:
    # Limit points to 22 positions and use the proper XML URL
    points = [25, 22, 20, 18, 16, 15, 14, 13, 12, 11,  # 1-10
              10, 9, 8, 7, 6, 5, 4, 3, 2, 1,  # 11-20
              1, 1]  # 21-22

    udogPoints = [50, 44, 40, 36, 32, 30, 28, 26, 24, 22,  # 1-10, 2x
                  10, 9, 8, 7, 6, 5, 4, 3, 2, 1,  # 11-20
                  1, 1]  # 21-22

    baseURL = 'http://live.amasupercross.com/xml/sx/'

elif sxSeason is False:
    # Extend points to 40 positions and use the proper XML URL
    points = [25, 22, 20, 18, 16, 15, 14, 13, 12, 11,  # 1-10
              10, 9, 8, 7, 6, 5, 4, 3, 2, 1,  # 11-20
              0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 21-30
              0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # 31-40

    udogPoints = [50, 44, 40, 36, 32, 30, 28, 26, 24, 22,  # 1-10, 2x
                  10, 9, 8, 7, 6, 5, 4, 3, 2, 1,  # 11-20
                  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 21-30
                  0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # 31-40

    baseURL = 'http://americanmotocrosslive.com/xml/mx/'

else:
    print('What season is it?')

liveTimingURL = baseURL + 'RaceResultsWeb.xml'
infoUrl = baseURL + 'Announcements.json'


def make_integers(k):
    newList = list(map(int, k))
    return newList


# def item_selector(letter):
#     selector = preSelector.css('B')
#     item = selector.xpath('@' + letter).extract()
#     return item


def live_timing_update():
    # Make a connection to the calling Excel file
    # wb = Workbook.caller()

    # Get XML text from URL
    liveTiming = requests.get(liveTimingURL).text

    # Create Selector that is pre-focused on the XML text
    preSelector = Selector(text=liveTiming, type="xml")
    selector = preSelector.css('B')

    # Select the relevant elements for table
    # pos = list(map(int, selector.xpath('@A').extract()))
    keyLetters = ['A', 'F', 'N', 'L', 'G', 'D', 'LL', 'BL', 'S']
    columns = []
    for letter in keyLetters:
        values = selector.xpath(str('@') + letter).extract()
        columns.append(values)

    # Lists to convert to make_integers
    toIntegers = [0, 2, 3]
    for i in toIntegers:
        columns[i] = make_integers(columns[i])

    pos = make_integers(columns[0])
    name = columns[1]
    number = make_integers(columns[2])
    lap = make_integers(columns[3])
    gap = columns[4]
    diff = columns[5]
    lastlap = columns[6]
    bestlap = columns[7]
    status = columns[8]

    keyValues = ['pos', 'name', 'num',
                 'laps', 'gap', 'diff',
                 'lastlap', 'bestlap', 'status']

    dict = list(zip(keyValues, columns))
    print(dict)

    # pos = selector.xpath('@A').extract()
    # pos = make_intList(pos)
    # name = selector.xpath('@F').extract()
    # number = selector.xpath('@N').extract()
    # number = list(map(int, selector.xpath('@N').extract()))  #needs to be Int
    # lap = list(map(int, selector.xpath('@L').extract()))  #needs to be Int
    # lap = selector.xpath('@L').extract()
    # gap = selector.xpath('@G').extract()
    # diff = selector.xpath('@D').extract()
    # lastlap = selector.xpath('@LL').extract()
    # bestlap = selector.xpath('@BL').extract()
    # status = selector.xpath('@S').extract()

    print(pos, name, number, lap, gap, diff, lastlap, bestlap, status)
    # print(pos, name, number)


live_timing_update()

# Python3 uses list(zip()) instead of dict(zip())
# dict = list(zip(pos, points, name, number, lap, gap,
#                 diff, lastlap, bestlap, status))

# # Create pandas DataFrame
# df_liveTiming = pd.DataFrame(dict,
#                              columns=['pos', 'points',
#                                       'name', 'num',
#                                       'laps', 'gap',
#                                       'diff', 'lastlap',
#                                       'bestlap', 'status'])

# Clear previous table
# Range('liveTiming', 'A1:I50').clear_contents()

# Output the results
# if df_liveTiming.empty:
#     Range('liveTimingData', 'A1').value = "Error in data collection"
# else:
#     Range('liveTimingData', 'A1').options(index=True).value = df_liveTiming
# return df_liveTiming
