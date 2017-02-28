import re
import sqlite3
from collections import OrderedDict

import keyring
import pandas as pd
import pygsheets
import requests
from bs4 import BeautifulSoup
from lxml import etree


# TODO Rearrange code in a master function along the lines of this site: http://stackoverflow.com/questions/26310467/python-requests-keep-session-between-function
[jjjj](URL)


##################
SX = True
##################

# Points Lists
pts_sx = [25, 22, 20, 18, 16, 15, 14, 13, 12, 11,  # 1-10
          10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1, 1]     # 11-22
pts_mx = [25, 22, 20, 18, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3,
          2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
top10x2 = [50, 44, 40, 36, 32, 30, 28, 26, 24, 22]
udog_pts_sx = [50, 44, 40, 36, 32, 30, 28, 26, 24, 22,
               10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1, 1]
udog_pts_mx = [50, 44, 40, 36, 32, 30, 28, 26, 24, 22, 10, 9, 8, 7, 6, 5, 4, 3,
               2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

pts_sxdict = dict(zip(range(1, 23), pts_sx))
udog_pts_sxdict = dict(zip(range(1, 23), top10x2 + pts_sx[10:]))
pts_mxdict = dict(zip(range(1, 41), pts_mx))
udog_pts_mxdict = dict(zip(range(1, 41), top10x2 + pts_mx[10:]))

# MotocrossFantasy.com URLS
mfUrl_base = 'https://www.motocrossfantasy.com/'
mfUrl_results = 'https://www.motocrossfantasy.com/user/race-results'


# Chooce URLS based on which season it is
if SX:
    points, udogPoints = pts_sx, udog_pts_sx
    infoUrl = 'http://live.amasupercross.com/xml/sx/Announcements.json'
    liveTimingUrl = 'http://live.amasupercross.com/xml/sx/RaceResultsWeb.xml'
elif not SX:  # i.e. it is MX season
    points, udogPoints = pts_mx, udog_pts_mx
    infoUrl = 'http://americanmotocrosslive.com/xml/mx/Announcements.json'
    liveTimingUrl = 'http://americanmotocrosslive.com/xml/mx/RaceResultsWeb.xml'
else:
    print('...What season is it?')


def mf_auth():
    """
    Returns an authenticated ession with at 'motocrossfantasy.com'.
    Password is fetched from Windows Credentials Vault.
    """
    username = 'markwhat'
    password = keyring.get_password("motocrossfantasy", username)
    payload = {
        'login_username': username,
        'login_password': password,
        'login': 'true'
    }
    session = requests.Session()
    s = session.post(mfUrl_base, data=payload)
    return session


def mf_rider_tables_update():
    """
    Returns rider table list from 'motocrossfantasy.com'
    division = 450 or 250 only
    """
    mfUrl_list_source = 'https://www.motocrossfantasy.com/user/team-status'

    session = mf_auth()

    r = session.get(mfUrl_list_source)
    soup = BeautifulSoup(r.text, 'lxml')
    table_urls = soup.find_all(href=re.compile('pick-rider'))
    tableURL_450 = table_urls[0]['href']
    tableURL_250 = table_urls[1]['href']

    d = {}
    for i in range(len(table_urls)):
        if i == 0:
            division = 450
        elif i == 1:
            division = 250
        else:
            print("No proper division found.")

        doc = session.get(table_urls[i]['href'])
        soup = BeautifulSoup(doc.text, 'lxml')
        table = soup.find('table')

        heads = table.find_all('th')
        headers = [th.text for th in heads]

        data = [[] for n in range(len(headers))]
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            for c in range(len(data)):
                if len(cols) > 0:
                    data[c].append(cols[c].text)
        d[i] = pd.DataFrame(data)
        d[i] = d[i].transpose()
        d[i].insert(0, 'Class', division)

    # Combine DataFrames into one table for processing
    df_riderlists = d[0].append(d[1], ignore_index=True)
    
    # Drop first blank column
    df_riderlists.drop(df_riderlists.columns[1], axis=1, inplace=True)

    # Rename columns to logical headers
    cols = ['Class', 'Name', 'HC', 'LF', 'UD']
    df_riderlists.columns = cols

    # Remove multiple spaces and replace with a single space
    df_riderlists['Name'] = df_riderlists['Name'].str.replace('\s+', ' ')

    # Reformat names from "First Last" to "Last, F."
    splits = df_riderlists['Name'].str.split(' ')
    df_riderlists['last'] = splits.str[1]
    df_riderlists['first'] = splits.str[0]
    df_riderlists['first'] = df_riderlists['first'].str.slice(0, 1) + str('.')
    df_riderlists['Name'] = df_riderlists['last'].str.cat(
                                             df_riderlists['first'], sep=', ')
    df_riderlists.pop('last')
    df_riderlists.pop('first')
    print(df_riderlists)

    gc = pygsheets.authorize()

    # Open spreadsheet and then workseet
    sh = gc.open('2017 fantasy supercross')
    wks = sh.worksheet_by_title("rider lists")
    wks.set_dataframe(df_riderlists, 'A1')
    return


def get_race_info():
    info = requests.get(infoUrl).json()
    raceInfo = info["S"].split(' (', 1)[0]  # '450 Class Moto #2'
    motoNum = raceInfo.split('#', 1)[1]
    motoClass = raceInfo.split(' ', 1)[0]
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
    return df_livetiming


def live2gsheets():
    gc = pygsheets.authorize()

    # Open spreadsheet and then workseet
    sh = gc.open('2017 fantasy supercross')
    wks = sh.worksheet_by_title("liveTiming2")
    df = live_timing_parse()
    wks.set_dataframe(df, 'A1')
    return


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






# Datebase beginning
'''
df = live_timing_parse()
conn = sqlite3.connect('liveTiming.db')
c = conn.cursor()

df.to_sql("liveResults", conn, if_exists="replace")

df2 = pd.read_sql_query("select * from liveResults", conn)
print(df2)
'''
mf_rider_tables_update()

# if __name__ == '__main__':
#     # To run from Python, not needed when called from Excel.
#     # Expects the Excel file next to this source file, adjust accordingly.
#     path =
#     os.path.abspath(os.path.join(os.path.dirname(__file__),'myfile.xlsm'))
#     path = 'C:\\Users\\mwhatc\\Google Drive\\Spreadsheets\\fantasy
#     motocross\\'
#     Workbook.set_mock_caller(path + 'motoFantasy.xlsm')
