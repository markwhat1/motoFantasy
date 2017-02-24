# import gspread
import os
import re
from collections import OrderedDict

import pandas as pd
import requests
from bs4 import BeautifulSoup
from lxml import etree

# from oauth2client.service_account import ServiceAccountCredentials
import df2gspread as d2g
import simplejson as json
from pgsheets import Client, Spreadsheet, Token
from twisted.internet import reactor, task

##################
SX = False
##################

timeout = 60.0

# Google Sheets values
gapps_id = '.apps.googleusercontent.com'
client_id = '362995481251-uoktvff3b0304l2d21vsgktmn46as8ij' + gapps_id
client_secret = 'sqCvf2ET787c6WSz5OT940-D'
access_code = '4/fxzdz-nv0BFZmCqX8hfND_g2PKXuHYZQLoJH-18aO44'
my_token = '1/rie3alfNdqs1z6OK47HtLOIka-3l5gy8KMpBPeNR7AU'
sheet_key = '16EDA8Mqe2_ikVtYEMKEgIOyDY2wOjHqaUW5effp7ZJk'
my_url = 'https://docs.google.com/spreadsheets/d/' + sheet_key

# Points Lists
pts_sx = [25, 22, 20, 18, 16, 15, 14, 13, 12, 11,  # 1-10
         10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1, 1]  # 11-22
ptsMX = [25,  22, 20, 18, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3,
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
    liveUrl = 'http://live.amasupercross.com/xml/sx/RaceResultsWeb.xml'
elif not SX:  # i.e. it is MX season
    points, udogPoints = ptsMX, udogPtsMX
    infoUrl = 'http://americanmotocrosslive.com/xml/mx/Announcements.json'
    liveUrl = 'http://americanmotocrosslive.com/xml/mx/RaceResultsWeb.xml'
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

    dataframe = pd.DataFrame(data)
    dataframe = dataframe.transpose()
    dataframe.columns = headers
    return dataframe


def riderListFind():
    s = mf_auth()
    r = s.get(mfUrl_list_source)
    soup = BeautifulSoup(r.text, 'lxml')
    urls = soup.find_all(href=re.compile('pick-rider'))
    riderURL_450s = urls[0]['href']
    riderURL_250s = urls[1]['href']
    return riderURL_450s, riderURL_250s


def get_race_info():
    info_list = []
    info = requests.get(infoUrl).json()

    raceInfo = info["S"].split(' (', 1)[0]  # '450 Class Moto #2'
    motoNum = raceInfo.split('#', 1)[1]
    motoClass = raceInfo.split(' ', 1)[0]
    raceLocation = info["T"]  # Race location/name - 'Washougal'
    raceDesc = raceInfo + ' at ' + raceLocation

    info_list.append(raceDesc)
    info_list.append(motoClass)
    info_list.append(motoNum)

    df_lt_info = pd.DataFrame(info_list)
    return df_lt_info


def live_timing_parse():
    lt_keys = ['@N', '@F', '@L', '@G',
               '@D', '@LL', '@BL', '@S']
    lt_values = ['num', 'name', 'laps', 'gap',
                 'diff', 'last lap', 'best lap', 'status']
    lt_dict = {'@BL': 'best lap',
               '@D': 'diff',
               '@F': 'name',
               '@G': 'gap',
               '@L': 'laps',
               '@LL': 'last lap',
               '@N': 'num',
               '@S': 'status'}

    tree = etree.parse(liveUrl)
    lt_data = []
    for i in range(len(lt_keys)):
        value = tree.xpath('//A/B/' + lt_keys[i])
        lt_data.append(value)

    lt_dict = OrderedDict(zip(lt_values, lt_data))
    new_index = list(range(1, 41))
    df_liveTiming = pd.DataFrame(lt_dict, index=new_index)
    df_liveTiming.index.name = 'pos'
    return df_liveTiming


def gsheets_livetiming_update():
    df_lt_info = get_race_info()
    df_liveTiming = live_timing_parse()
    c = Client(client_id, client_secret)
    t = Token(c, my_token)
    s = Spreadsheet(t, my_url)
    wks_lt_info = s.getWorksheet('Live Timing Info')
    wks_livetiming = s.getWorksheet('Live Timing')
    wks_lt_info.setDataFrame(df_lt_info)
    wks_livetiming.setDataFrame(df_liveTiming)
    pass

l = task.LoopingCall(gsheets_livetiming_update)
l.start(timeout)

reactor.run()


# df_liveTiming = live_timing_parse()
# spreadsheet = '16EDA8Mqe2_ikVtYEMKEgIOyDY2wOjHqaUW5effp7ZJk'
# wks_name = 'Live Timing'
# d2g.upload(df_liveTiming, spreadsheet, wks_name)

# sh = gc.open("motoFantasy")
# worksheet = sh.worksheet('Live Timing')
# print(data)
# worksheet.update_acell('D1', data)
# num_lines, num_columns = data.shape
# print(num_lines, num_columns)
# worksheet = sh.worksheet("Live Timing")
# worksheet.update_acell('B1', data)
