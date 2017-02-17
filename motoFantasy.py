import re
from collections import OrderedDict

import pandas as pd
import requests
from bs4 import BeautifulSoup
from lxml import etree
import sqlite3

##################
SX = True
##################

# Points Lists
ptsSX = [25, 22, 20, 18, 16, 15, 14, 13, 12, 11,  # 1-10
         10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1, 1]  # 11-22
ptsMX = [25, 22, 20, 18, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3,
         2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
top10x2 = [50, 44, 40, 36, 32, 30, 28, 26, 24, 22]
udogPtsSX = [50, 44, 40, 36, 32, 30, 28, 26, 24, 22,
             10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1, 1]
udogPtsMX = [50, 44, 40, 36, 32, 30, 28, 26, 24, 22, 10, 9, 8, 7, 6, 5, 4, 3,
             2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

ptsSXdict = dict(zip(range(1, 23), ptsSX))
udogPtsSXdict = dict(zip(range(1, 23), top10x2 + ptsSX[10:]))
ptsMXdict = dict(zip(range(1, 41), ptsMX))
udogPtsMXdict = dict(zip(range(1, 41), top10x2 + ptsMX[10:]))

# MotocrossFantasy.com URLS
mfUrl_base = 'https://www.motocrossfantasy.com/'
mfUrl_results = 'https://www.motocrossfantasy.com/user/race-results'
mfUrl_list_source = 'https://www.motocrossfantasy.com/user/team-status'

# Chooce URLS based on which season it is
if SX:
    points, udogPoints = ptsSX, udogPtsSX
    infoUrl = 'http://live.amasupercross.com/xml/sx/Announcements.json'
    liveTimingUrl = 'http://live.amasupercross.com/xml/sx/RaceResultsWeb.xml'
elif not SX:  # i.e. it is MX season
    points, udogPoints = ptsMX, udogPtsMX
    infoUrl = 'http://americanmotocrosslive.com/xml/mx/Announcements.json'
    liveTimingUrl = 'http://americanmotocrosslive.com/xml/mx/RaceResultsWeb.xml'
else:
    print('...What season is it?')


def mf_auth():
    username = 'markwhat'
    password = 'yamaha'
    payload = {
        'login_username': username,
        'login_password': password,
        'login': 'true'
    }
    s = requests.Session()
    s = s.post(mfUrl_base, data=payload)
    return s


def mf_scrape(url, division):
    if division == 450:
        index = 0
    elif division == 250:
        index = 1
    else:
        index = 0

    s = mf_auth()
    r = s.get(url)
    soup = BeautifulSoup(r.text, 'lxml')
    tables = soup.find_all('table')
    mf_table = tables[index]

    heads = mf_table.find_all('th')
    headers = [th.text for th in heads]

    data = [[] for i in range(len(headers))]
    rows = mf_table.find_all('tr')
    for row in rows:
        cols = row.find_all('td')
        for i in range(len(data)):
            if len(cols) > 0:
                data[i].append(cols[i].text)

    df = pd.DataFrame(data)
    df = df.transpose()
    df.columns = headers
    return df


def riderListFind():
    s = mf_auth()
    r = s.get(mfUrl_list_source)
    soup = BeautifulSoup(r.text, 'lxml')
    urls = soup.find_all(href=re.compile('pick-rider'))
    riderURL_450s = urls[0]['href']
    riderURL_250s = urls[1]['href']
    return riderURL_450s, riderURL_250s


def get_race_info():
    info = requests.get(infoUrl).json()
    raceInfo = info["S"].split(' (', 1)[0]  # '450 Class Moto #2'
    # motoNum = raceInfo.split('#', 1)[1]
    # motoClass = raceInfo.split(' ', 1)[0]
    raceLocation = info["T"]  # Race location/name - 'Washougal'
    raceDesc = raceInfo + ' at ' + raceLocation
    return raceDesc


def live_timing_parse():
    lt_keys = ['@N', '@F', '@L', '@G', '@D', '@LL', '@BL', '@S']
    lt_values = ['num', 'name', 'laps', 'gap', 'diff', 'lastlap', 'bestlap', 'status']
    lt_dict = {'@BL': 'bestlap',
               '@D': 'diff',
               '@F': 'name',
               '@G': 'gap',
               '@L': 'laps',
               '@LL': 'lastlap',
               '@N': 'num',
               '@S': 'status'}

    tree = etree.parse(liveTimingUrl)

    lt_data = []
    for i in range(len(lt_keys)):
        value = tree.xpath('//A/B/' + lt_keys[i])
        lt_data.append(value)

    lt_dict = OrderedDict(zip(lt_values, lt_data))
    df_livetiming = pd.DataFrame(lt_dict, index=list(range(1, len(lt_data[0]) + 1)))
    df_livetiming.index.name = 'pos'
    print(df_livetiming)
    return df_livetiming


def live_timing_update():
    text = requests.get(liveTimingUrl)  # Get XML
    soup = BeautifulSoup(text.text, 'xml')
    rows = soup.find_all('B')
    print(rows)
    pos = []
    rider = []
    for i in range(len(rows)):
        pos = rows[i].find_all('A')
        rider.append(pos)

    print(rider)
    print(soup)
    # dict_initial = xmltodict.parse(text, dict_constructor=dict)
    # dict_final = dict_initial['A']['B']
    correctOrder = ['@A', '@N', '@F', '@L', '@G', '@D', '@LL', '@BL', '@S',
                    '@S1', '@S2', '@S3', '@S4', '@C', '@H', '@I', '@IN', '@LS',
                    '@LT', '@MLT', '@MLTBy', '@MSTLT', '@MSTS1', '@MSTS2',
                    '@MSTS3', '@MSTS4', '@P', '@RM', '@T', '@V']
    nameReplace = {'@A': 'pos',
                   '@F': 'name',
                   '@N': 'num',
                   '@L': 'laps',
                   '@G': 'gap',
                   '@D': 'diff',
                   '@LL': 'lastlap',
                   '@BL': 'bestlap',
                   '@S': 'status',
                   '@S1': 'seg1',
                   '@S2': 'seg2',
                   '@S3': 'seg3',
                   '@S4': 'seg4'}

    # df_liveTiming = pd.DataFrame(dict_final, columns=correctOrder)
    # df_liveTiming = df_liveTiming.loc[:, '@A':'@S4']
    # df_liveTiming.rename(columns=nameReplace, inplace=True)
    # print(df_liveTiming)
    #
    # # Write to Excel workbook
    # path = 'C:\\Users\\mwhatc\\Google Drive\\Spreadsheets\\fantasy motocross\\'
    # wb = 'motoFantasy.xlsx'
    # writer = pd.ExcelWriter(path + wb)
    # df_liveTiming.to_excel(writer, 'liveTimingData')
    # writer.save()


# divs = [450, 250]
# for i in range(len(divs)):
#     results = mf_scrape(mfUrl_results, i)
#     results.split('/', 1)
#     print(results)
#
# print(get_race_info())

# get_race_info()
# riderListFind()
df = live_timing_parse()
conn = sqlite3.connect('sqlite:///liveTiming.db')
c = conn.cursor()

c.execute('''CREATE TABLE liveTiming
             (pos value, trans text, symbol text, qty real, price real)''')


# if __name__ == '__main__':
#     # To run from Python, not needed when called from Excel.
#     # Expects the Excel file next to this source file, adjust accordingly.
#     path =
#     os.path.abspath(os.path.join(os.path.dirname(__file__),'myfile.xlsm'))
#     path = 'C:\\Users\\mwhatc\\Google Drive\\Spreadsheets\\fantasy
#     motocross\\'
#     Workbook.set_mock_caller(path + 'motoFantasy.xlsm')
#     live_timing_update()


# live_timing_update()
