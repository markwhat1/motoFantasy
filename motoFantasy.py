import json
import re

import keyring
import pandas as pd
import pygsheets
import requests
from bs4 import BeautifulSoup

import values

# MotocrossFantasy.com variables and URLs
leagueID = 4370
event = 8
first_race_id = 437
race_id_450 = first_race_id + (event * 2 - 2)
race_id_250 = first_race_id + (event * 2 - 1)

mf_url_base = 'https://www.motocrossfantasy.com/user/'
mf_url_status = mf_url_base + 'team-status'
mf_url_team_standings = mf_url_base + 'bench-racing-divisions/' + str(leagueID)
mf_url_week_standings = mf_url_base + 'weekly-standings/' + str(leagueID)
mf_url_race_results = mf_url_base + 'race-results'
mf_url_top_picks = mf_url_base + 'top-picks/2017-MX'


def mf_master():
    ses = requests.session()

    # we're now going to use the session in 3 different function calls
    mf_auth(ses)
    df_riders = mf_rider_tables(ses)

    # once this function ends we either need to pass the session up to the
    # calling function or it will be gone forever
    return df_riders


def mf_auth(session):
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
    session.post(mf_url_base, data=payload)


def mf_find_table_urls(ses):
    """
    Returns rider table list from 'motocrossfantasy.com'
    division = 450 or 250 only
    """
    html = ses.get(mf_url_status).content
    soup = BeautifulSoup(html, 'lxml')

    table_urls = []
    for link in soup.find_all('a', href=re.compile('pick-riders')):
        table_urls.append(link['href'])

    divisions = [250, 450]
    div_dict = {k: v for (k, v) in zip(divisions, table_urls)}
    return div_dict


def mf_rider_tables(ses):
    rider_urls = mf_find_table_urls(ses)

    rider_lists = []
    for div in rider_urls.keys():
        html = ses.get(rider_urls.get(div)).content
        soup = BeautifulSoup(html, 'lxml')
        table = soup.find('table')

        # Use prettify() to feed html into pandas
        rider_tables = pd.read_html(table.prettify(), flavor='bs4')

        # Print number of tables found
        print(str(len(rider_tables)) + " " + str(div) + " class " + " table(s) was found!")

        # read_html returns list of DataFrames, only need first one
        df_table = rider_tables[0]

        # Add Class column to beginning of DataFrame
        df_table.insert(0, "Class", int(div), allow_duplicates=True)

        # Merge rider lists
        rider_lists.append(df_table)

    # Combine DataFrames into one table for processing
    df_riders = pd.concat(rider_lists, ignore_index=True)

    # Drop blank column in position [1]; axis=1 means columns
    df_riders.drop(df_riders.columns[1], axis=1, inplace=True)

    # Rename columns to logical headers
    cols = ['Class', 'Name', 'HC', 'LF', 'UD']

    if len(df_riders.columns) == 5:
        df_riders.columns = cols
        df_riders['Name'] = format_name(df_riders['Name'])
    else:
        print("Rider columns could not be found.")
    return df_riders


def format_name(df_column):
    df = pd.Series(df_column).to_frame(name='name')
    splits = df['name'].str.split(' ')
    df['last'] = splits.str[1]
    df['first'] = splits.str[0]
    df['first'] = df['first'].str.slice(0, 1) + str('.')
    df['name'] = df['last'].str.cat(
        df['first'], sep=', ')
    df = df.loc[:, 'name']
    return df


def live_timing_to_sheets(series='MX'):
    r = requests.get(live_url)
    live_timing = json.loads(r.text)

    column_names = {'A': 'pos', 'F': 'name', 'N': 'num', 'L': 'laps', 'G': 'gap',
                    'D': 'diff', 'BL': 'bestlap', 'LL': 'lastlap', 'S': 'status'}

    df_live_timing = pd.DataFrame.from_records(
        live_timing['B'], columns=list(column_names.keys()))
    df_live_timing.rename(columns=column_names, inplace=True)
    df_live_timing['name'] = format_name(df_live_timing['name'])

    # Assemble current race information
    status = live_timing['A']
    location = live_timing['T']  # Race location/name - 'Washougal'
    long_moto_name = live_timing['S'].split(' (', 1)[0] # '450 Class Moto #2'
    short_moto_name = long_moto_name.split('Class ', 1)[1]
    division = long_moto_name.split('Class ', 1)[0]

    gc = pygsheets.authorize(no_cache=True)

    # Open spreadsheet and then worksheet
    sh = gc.open('2017 fantasy supercross')
    wks = sh.worksheet_by_title('live timing')

    # Updates to current race information
    wks.update_cell('K2', series) # Series (MX or SX)
    wks.update_cell('L2', location) # Location
    wks.update_cell('M2', division) # Class
    wks.update_cell('N2', short_moto_name) # Event
    wks.set_dataframe(df_live_timing, (1, 1)) # Live timing table
    return


def season(series='SX'):
    if series == 'MX':
        series_value = 0
    elif series == 'SX':
        series_value = 1
    else:
        print('... What season is it?')

    live_url = 'http://americanmotocrosslive.com/xml/' + series + '/RaceResults.json'

    pts = values.pts[series_value]
    pts_udog = values.pts_udog[series_value]
    pts_dict = values.pts_dict[series_value]
    pts_dict_udog = values.pts_dict_udog[series_value]
    return [live_url, pts, pts_udog, pts_dict, pts_dict_udog]


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


# Datebase beginning
'''
df = live_timing_parse()
conn = sqlite3.connect('liveTiming.db')
c = conn.cursor()

df.to_sql("liveResults", conn, if_exists="replace")

df2 = pd.read_sql_query("select * from liveResults", conn)
print(df2)
'''

if __name__ == "__main__":


    # Assign all point dictionaries/lists to variables
    my_variables = season('MX')
    live_url = my_variables[0]
    pts, pts_udog = my_variables[1:3]
    pts_dict, pts_dict_udog = my_variables[3:5]

    # mf_master()
    live_timing_to_sheets()