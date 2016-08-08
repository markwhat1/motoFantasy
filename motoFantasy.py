from bs4 import BeautifulSoup
from collections import OrderedDict

import pandas as pd
import re
import requests
import xmltodict
from lxml import etree, html
from lxml.cssselect import CSSSelector

##################
sxSeason = False
##################

# Points Lists
points_sx = [25, 22, 20, 18, 16, 15, 14, 13, 12, 11,  # 1-10
             10, 9, 8, 7, 6, 5, 4, 3, 2, 1,           # 11-20
             1, 1]                                    # 21-22
points_mx = [25, 22, 20, 18, 16, 15, 14, 13, 12, 11,  # 1-10
             10, 9, 8, 7, 6, 5, 4, 3, 2, 1,           # 11-20
             0, 0, 0, 0, 0, 0, 0, 0, 0, 0,            # 21-30
             0, 0, 0, 0, 0, 0, 0, 0, 0, 0]            # 31-40
udogPoints_sx = [50, 44, 40, 36, 32, 30, 28, 26, 24, 22,  # 1-10, 2x
                 10, 9, 8, 7, 6, 5, 4, 3, 2, 1,           # 11-20
                 1, 1]                                    # 21-22
udogPoints_mx = [50, 44, 40, 36, 32, 30, 28, 26, 24, 22,  # 1-10, 2x
                 10, 9, 8, 7, 6, 5, 4, 3, 2, 1,           # 11-20
                 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,            # 21-30
                 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]            # 31-40

# Live Timing URLS
baseurl_sx = 'http://live.amasupercross.com/xml/sx/'
baseurl_mx = 'http://americanmotocrosslive.com/xml/mx/'
raceInfoUrl = 'Announcements.json'
raceResultsUrl = 'RaceResultsWeb.xml'

# MotocrossFantasy.com URLS
mf_URL = 'https://www.motocrossfantasy.com/'
mf_ResultsURL = 'https://www.motocrossfantasy.com/user/race-results'
mf_riderListsURL = 'https://www.motocrossfantasy.com/user/team-status'

if sxSeason is True:
    points, udogPoints = points_sx, udogPoints_sx
    infoUrl = baseurl_sx + raceInfoUrl
    iveTimingURL = baseurl_sx + raceResultsUrl
elif sxSeason is False:  # i.e. it is MX season
    points, udogPoints = points_mx, udogPoints_mx
    infoUrl = baseurl_mx + raceInfoUrl
    iveTimingURL = baseurl_mx + raceResultsUrl
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
    r = s.post(mf_URL, data=payload)
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
    r = s.get(mf_riderListsURL)
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


def live_timing_xml_parse():
    lt_attrs = ['@N', '@F', '@L', '@G', '@D', '@LL', '@BL',
                '@S', '@S1', '@S2', '@S3', '@S4']
    lt_keys = ['num', 'name', 'laps', 'gap', 'diff', 'lastlap', 'bestlap',
               'status', 'seg1', 'seg2', 'seg3', 'seg4']
    lt_values = []
    lt_info = {'seg4': '@S4', 'gap': '@G', 'seg3': '@S3', 'num': '@N',
               'laps': '@L', 'name': '@F', 'lastlap': '@LL', 'seg2': '@S2',
               'diff': '@D', 'bestlap': '@BL', 'seg1': '@S1', 'status': '@S'}
    tree = etree.parse(liveTimingURL)
    for i in range(len(lt_attrs)):
        value = tree.xpath('//A/B/' + lt_attrs[i])
        lt_values.append(value)
    lt_dict = OrderedDict(zip(lt_keys, lt_values))
    df_livetiming = pd.DataFrame(lt_dict, index=list(range(1, 41)))
    df_livetiming.index.name = 'pos'
    print(df_livetiming)


def live_timing_update():
    text = requests.get(liveTimingURL).text  # Get XML
    dict_initial = xmltodict.parse(text, dict_constructor=dict)
    dict_final = dict_initial['A']['B']
    correctOrder = ['@A', '@N', '@F', '@L', '@G', '@D', '@LL', '@BL', '@S',
                    '@S1', '@S2', '@S3', '@S4', '@C', '@H', '@I', '@IN', '@LS',
                    '@LT', '@MLT', '@MLTBy', '@MSTLT', '@MSTS1', '@MSTS2',
                    '@MSTS3', '@MSTS4', '@P', '@RM', '@T', '@V']
    nameReplace = {'@A': 'pos', '@F': 'name', '@N': 'num',
                   '@L': 'laps', '@G': 'gap', '@D': 'diff',
                   '@LL': 'lastlap', '@BL': 'bestlap',
                   '@S': 'status', '@S1': 'seg1', '@S2': 'seg2',
                   '@S3': 'seg3', '@S4': 'seg4'}

    df_liveTiming = pd.DataFrame(dict_final, columns=correctOrder)
    df_liveTiming = df_liveTiming.loc[:, '@A':'@S4']
    df_liveTiming.rename(columns=nameReplace, inplace=True)
    print(df_liveTiming)

    # Write to Excel workbook
    path = 'C:\\Users\\mwhatc\\Google Drive\\Spreadsheets\\fantasy motocross\\'
    wb = 'motoFantasy.xlsx'
    writer = pd.ExcelWriter(path + wb)
    df_liveTiming.to_excel(writer, 'liveTimingData')
    writer.save()

divs = [450, 250]
for i in range(len(divs)):
    results = mf_scrape(mf_ResultsURL, i)
    results.split('/', 1)
    print(results)

print(get_race_info())
# get_race_info()
# live_timing_xml_parse()
# live_timing_update()

# if __name__ == '__main__':
#     # To run from Python, not needed when called from Excel.
#     # Expects the Excel file next to this source file, adjust accordingly.
#     path =
#     os.path.abspath(os.path.join(os.path.dirname(__file__),'myfile.xlsm'))
#     path = 'C:\\Users\\mwhatc\\Google Drive\\Spreadsheets\\fantasy
#     motocross\\'
#     Workbook.set_mock_caller(path + 'motoFantasy.xlsm')
#     live_timing_update()
