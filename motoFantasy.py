import json
import re
import sqlite3
from collections import OrderedDict

import keyring
import pandas as pd
import pygsheets
import requests
from bs4 import BeautifulSoup
from lxml import etree

import values


# TODO Rearrange code in a master function along the lines of
# this site:
# http://stackoverflow.com/questions/26310467/python-requests-keep-session-between-function

# MotocrossFantasy.com URL constructions
leagueID = '4370'
first_raceid = 437
round = 8
raceid_450 = first_raceid + (round * 2 - 2)
raceid_250 = first_raceid + (round * 2 - 1)

mfUrl_base = 'https://www.motocrossfantasy.com/user/'
mfUrl_status = mfUrl_base + 'team-status'
mfUrl_choose450s = mfUrl_base + 'pick-riders/2017-MX/' + \
    leagueID + '/' + str(raceid_450)
mfUrl_choose250s = mfUrl_base + 'pick-riders/2017-MX/' + \
    leagueID + '/' + str(raceid_250)
mfUrl_teamstandings = mfUrl_base + 'bench-racing-divisions/' + leagueID
mfUrl_weekstandings = mfUrl_base + 'weekly-standings/' + leagueID
mfUrl_raceresults = mfUrl_base + 'race-results'
mfUrl_toppicks = mfUrl_base + 'top-picks/2017-MX'


def season(series='SX'):
    if series == 'MX':
        list_item = 0
    elif series == 'SX':
        list_item = 1
    else:
        print('... What season is it?')

    live_url = 'http://americanmotocrosslive.com/xml/' + series + '/RaceResults.json'

    pts = values.pts[list_item]
    pts_udog = values.pts_udog[list_item]
    pts_dict = values.pts_dict[list_item]
    pts_dict_udog = values.pts_dict_udog[list_item]

    return [live_url, pts, pts_udog, pts_dict, pts_dict_udog]


def mf_auth():
    """
    Returns an authenticated session with 'motocrossfantasy.com'.
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


def get_rider_pts(pos, handicap, udog):
    '''
    Get riders approrpriate pts based on handcap and underdog status.
    pos = whole number value
    handcap = whole number value
    udog = boolean test
    '''
    if handicap >= pos:
        hc_pos = 1
    else:
        hc_pos = handicap - pos
    return


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

    table_dict = {}

    for i in range(len(table_urls)):
        # Set division based on table number
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

        table_dict[i] = pd.DataFrame(data)
        table_dict[i] = table_dict[i].transpose()
        table_dict[i].insert(0, 'Class', division)

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
    info = requests.get(live_url).json()

    location = info['T']  # Race location/name - 'Washougal'
    moto = info['S'].split(' (', 1)[0]  # '450 Class Moto #2'
    motoClass = moto.split(' ', 1)[0]

    race_info = location + ': ' + moto
    return race_info


def live_timing_json():
    r = requests.get(live_url)
    livetiming = json.loads(r.text)
    column_dict = {'A': 'pos', 'N': 'num', 'F': 'name', 'L': 'laps', 'G': 'gap',
                   'D': 'diff', 'BL': 'bestlap', 'LL': 'lastlap', 'S': 'status'}

    df_livetiming = pd.DataFrame.from_records(
        livetiming['B'], index='A', columns=list(column_dict.keys()))
    df_livetiming.rename(columns=column_dict, inplace=True)
    df_livetiming.index.name = 'pos'

    df_livetiming['name'] = format_name(df_livetiming['name'])
    return df_livetiming


def format_name(df_column):
    series = pd.Series(df_column)
    df = series.to_frame(name='name')
    splits = df['name'].str.split(' ')
    df['last'] = splits.str[1]
    df['first'] = splits.str[0]
    df['first'] = df['first'].str.slice(0, 1) + str('.')
    df['name'] = df['last'].str.cat(
    df['first'], sep=', ')
    df.pop('last')
    df.pop('first')
    return df


def live2gsheets():
    gc = pygsheets.authorize()

    # Open spreadsheet and then workseet
    sh = gc.open('2017 fantasy supercross')
    wks = sh.worksheet_by_title("liveTiming2")
    df = live_timing_parse()
    wks.set_dataframe(df, 'A1')
    return


my_variables = season('MX')
live_url = my_variables[0]
pts, pts_udog = my_variables[1:3]
pts_dict, pts_dict_udog = my_variables[3:]


# Datebase beginning
'''
df = live_timing_parse()
conn = sqlite3.connect('liveTiming.db')
c = conn.cursor()

df.to_sql("liveResults", conn, if_exists="replace")

df2 = pd.read_sql_query("select * from liveResults", conn)
print(df2)
'''


if __name__ == '__main__':
    df_livetiming = live_timing_json()
    print(df_livetiming)
    # column = df_livetiming.loc[:, 'name']
    # print(type(column))
    # format_name(column)
    # print(get_race_info())
