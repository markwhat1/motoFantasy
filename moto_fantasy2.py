import json
import re
from datetime import datetime
import time
from configparser import ConfigParser

import pandas as pd
import pygsheets
import requests
from bs4 import BeautifulSoup

# Load config.ini
parser = ConfigParser()
parser.read('config.ini')

# MotocrossFantasy.com variables and URLs
series = parser.get('motocross_fantasy', 'series')
leagueID = parser.get('motocross_fantasy', 'leagueID')
username = parser.get('motocross_fantasy', 'username')
password = parser.get('motocross_fantasy', 'password')

mf_url_base = parser.get('motocross_fantasy', 'mf_url')
mf_url_status = f"{mf_url_base}/user/team-status"
mf_url_team_standings = f"{mf_url_base}/user/bench-racing-divisions/{leagueID}"
mf_url_week_standings = f"{mf_url_base}/user/weekly-standings/{leagueID}"
mf_url_race_results = f"{mf_url_base}/user/race-results"
mf_url_top_picks = f"{mf_url_base}/user/top-picks/2020-SX"

# Live timing JSON URL
live_url = f"http://americanmotocrosslive.com/xml/{series.lower()}/RaceResults.json"
announce_url = f"http://americanmotocrosslive.com/xml/{series.lower()}/Announcements.json"


class RiderList:

    def __init__(self):
        self.payload = {'login_username': username, 'login_password': password, 'login': 'true'}
        self.session = requests.Session()
        self.s = self.session.post(mf_url_base, data=self.payload)
        self.active_race = None

    def mf_master(self):
        # Use 'with' to ensure the session context is closed after use.
        with self.session as s:
            s.post(mf_url_base, data=self.payload)

            # Check for presence of Pick Rider links, and download tables if present, otherwise load csv file
            # TO DO find text from pick-riders link that says "Waiting For Rider List"
            html = s.

            if "Waiting For Rider List" in link_text:
                riders = pd.read_csv('data/rider_lists.csv')
            else:
                riders = mf_rider_tables(s)
                rider_list_to_sheets(riders)
        return riders

    def mf_list_status(self):
        html = self.session.get(mf_url_status).content
        soup = BeautifulSoup(html, 'lxml')
        rider_links = soup.find('a', href=re.compile('pick-riders'))
        link_text = rider_links.string

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

    divisions = [450, 250]
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
        # rider_tables = pd.read_html(table.prettify(), flavor='bs4')
        rider_tables = pd.read_html(table, flavor='bs4')

        # read_html returns list of DataFrames, only need first one
        df_table = rider_tables[0]

        # Add Class column to beginning of DataFrame
        df_table.insert(0, 'class', div, allow_duplicates=True)

        # Merge rider lists
        rider_lists.append(df_table)

    # Combine DataFrames into one table for processing
    df_riders = pd.concat(rider_lists, ignore_index=True)

    # Drop blank column in position [1]; axis=1 means columns
    df_riders.drop(df_riders.columns[1], axis=1, inplace=True)

    # Rename columns to logical headers
    cols = ['class', 'mf_name', 'hc', 'lf', 'udog']

    if len(df_riders.columns) == 5:
        df_riders.columns = cols
        df_riders['mf_name'] = format_name(df_riders['mf_name'])
    else:
        print("Rider columns could not be found.")

    df_riders.to_csv('data/rider_lists.csv', index=False)
    return df_riders


def check_sheets_update(status):
    client = pygsheets.authorize(client_secret='auth/client_secret.json')
    ss = client.open('2020 fantasy supercross')

    wks = ss.worksheet_by_title('update')
    old_status = wks.get_value('A1')
    update_data = False
    if old_status != status:
        update_data = True
        print('Rider list update will be performed.')
        wks.update_value('A1', status)
    return update_data


def rider_list_to_sheets(rider_list):
    client = pygsheets.authorize(client_secret='auth/client_secret.json')
    ss = client.open('2020 fantasy supercross')
    wks = ss.worksheet_by_title('rider_list')
    wks.clear(start='B1')
    wks.set_dataframe(rider_list, (3, 1))

    # df_450 = rider_list[rider_list['class'] == 450]
    # df_250 = rider_list[rider_list['class'] == 250]
    #
    # wks_450 = ss.worksheet_by_title('450_riders')
    # wks_450.clear()
    # wks_450.set_dataframe(df_450, (1, 1))
    #
    # wks_250 = ss.worksheet_by_title('250_riders')
    # wks_250.clear()
    # wks_250.set_dataframe(df_250, (1, 1))
    return


def get_live_timing():
    r = requests.get(live_url)
    live_timing = json.loads(r.text)

    column_names = {'A': 'pos', 'F': 'name', 'N': 'num', 'L': 'laps', 'G': 'gap', 'D': 'diff', 'BL': 'bestlap',
                    'LL': 'lastlap', 'S': 'status'}

    df_live_timing = pd.DataFrame.from_records(live_timing['B'], columns=list(column_names.keys()))
    df_live_timing.rename(columns=column_names, inplace=True)
    df_live_timing['name'] = format_name(df_live_timing['name'])

    # Save live timing DataFrame to CSV
    df_live_timing.to_csv('data/live_timing.csv', index=False)

    # Assemble current race information
    # status = live_timing['A']
    # location = live_timing['T']  # Race location/name - 'Washougal'
    # if series == 'sx':
    #     long_moto_name = live_timing['S']
    #     short_moto_name = live_timing['S']
    #     division = live_timing['S']
    # else:
    #     long_moto_name = live_timing['S'].split(' (', 1)[0]  # '450 Class Moto #2'
    #     short_moto_name = long_moto_name.split('Class ', 1)[1]
    #     division = long_moto_name.split('Class ', 1)[0]
    #
    # client = pygsheets.authorize(client_secret='auth/client_secret.json')
    # ss = client.open('2020 fantasy supercross')
    # wks = ss.worksheet_by_title('live_timing')
    #
    # # Updates to current race information
    # wks.update_values('A1:D1', [[series.upper(), location, division, short_moto_name]])

    # Update live timing table beneath current race information
    #     wks.set_dataframe(df_live_timing, (3, 1))  # Live timing table
    return df_live_timing


def get_announcements():
    r = requests.get(announce_url)
    announce = json.loads(r.text)
    return announce


def comb_live_timing_to_sheets(sheet, data=None):
    if data is None:
        df_live = get_live_timing()
        df_rider = mf_master()

        # Keep only needed columns from rider lists
        df_rider = df_rider[['mf_name', 'hc', 'udog']]
        df_rider['mf_name'] = df_rider['mf_name'].str.replace('McAdoo', 'Mcadoo')
        df_rider['mf_name'] = df_rider['mf_name'].str.replace('DeCotis', 'Decotis')

        # Merge LiveTiming and rider lists on name columns
        # Left keeps all rows from live_timing, even if no matches found
        df = df_live.merge(df_rider, how='left', left_on='name', right_on='mf_name')

        # Calc adjusted position, then set any 0 values to 1 as you can't finish less than 1
        df['adj_pos'] = df['pos'] - df['hc']
        df['adj_pos'] = df.adj_pos.mask(df.adj_pos <= 0, 1)
        df = df.fillna(0, downcast='infer')

        # Create points dictionary and then map adj_pos values to each point total
        points = create_pts_dict()
        df['pts_normal'] = df['adj_pos'].map(points['normal'])
        df['pts_udog'] = df['adj_pos'].map(points['udog'])

        # When these filters are true, don't change values; if not true, set value to 0
        filter1 = df['udog'] == 'Yes'
        filter2 = df['adj_pos'] <= 10
        df['pts_udog'] = df.pts_udog.where(filter1 & filter2, 0)

        # Find max points between udog and normal point totals, then drop unused columns
        df['pts'] = df[['pts_normal', 'pts_udog']].max(axis=1)
        df = df.drop(['mf_name', 'pts_normal', 'pts_udog', 'adj_pos'], axis=1)  #
        df = df.fillna(0, downcast='infer')
        df.style.hide_index()

        # df.sort_values(by=['pts', 'name'], ascending=[False, True])
    else:
        df = data

    # Upload combined LiveTiming dataframe to Google Sheets
    client = pygsheets.authorize(client_secret='auth/client_secret.json')
    ss = client.open('2020 fantasy supercross')
    wks = ss.worksheet_by_title(sheet)
    wks.clear(start='A1')
    wks.set_dataframe(df, (1, 1))  # Live timing table
    return df


def format_name(df_column):
    """
    :df: DataSeries:
    """
    df = pd.Series(df_column).to_frame(name='name')
    splits = df['name'].str.split(' ')
    df['last'] = splits.str[1]
    df['first'] = splits.str[0]
    df['first'] = df['first'].str.slice(0, 1) + str('.')
    df['name'] = df['last'].str.cat(df['first'], sep=', ')
    df = df.loc[:, 'name']
    return df


def create_pts_dict():
    # Create pos/points dictionaries
    if series == 'sx':
        pts = [26, 23, 21, 19, 18, 17, 16, 15, 14, 13,  # 1-10
               12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]  # 11-22
    else:
        pts = [25, 22, 20, 18, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3,  # 1-18
               2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # 19-40

    dict_pos = dict(zip(range(1, len(pts) + 1), pts))
    dict_pos_udog = dict_pos.copy()
    for i in dict_pos_udog.keys():
        if i <= 10:
            dict_pos_udog[i] *= 2
    dict_pts = dict()
    dict_pts['normal'] = dict_pos
    dict_pts['udog'] = dict_pos_udog
    return dict_pts


def fix_race_name(event_str):
    event_str = event_str.split(' - ')[0]  # Returns race title only
    event_str = re.sub(" [0-9]{1,2} Minute.*", "", event_str)
    # race = re.sub("([0-9]{3}) SX", "\1SX", race)
    event_str = race.replace('250 SX', '250SX')
    event_str = race.replace('450 SX', '450SX')
    event_str = race.replace('450 Main', '450SX Main')
    event_str = race.replace('Last Chance Qualifier', 'LCQ')
    return event_str


if __name__ == "__main__":
    x = 1
    while x < 100:
        comb_df = comb_live_timing_to_sheets(sheet='live_timing', data=None)

        # Format time
        dateTimeObj = datetime.now()
        timestamp = dateTimeObj.strftime("%I:%M:%S")

        # Test Announcements.json for race being complete
        announcements = get_announcements()  # Returns JSON object
        race = announcements['S']
        race = fix_race_name(race)

        # Save current race to Google Sheets
        client = pygsheets.authorize(client_secret='auth/client_secret.json')
        ss = client.open('2020 fantasy supercross')
        wks = ss.worksheet_by_title('update')
        wks.update_value('A2', race)

        print(f"{timestamp}: Downloading live timing data for the {race}.")

        valid_races = ['450SX Main Event', '250SX Main Event', '250SX Heat #1', '250SX Heat #2', '450SX Heat #1',
                       '450SX Heat #2', '250SX LCQ', '450SX LCQ']
        if race not in valid_races:
            print(f'"{race}" name will need to be corrected to successfully save results.')
        else:
            complete_str = 'Session Complete'  # Search in M keys
            event_list = announcements['B']
            for event in event_list:
                if complete_str in event['M']:
                    print(f'{race} has completed. Saving copy of live timing.')
                    comb_live_timing_to_sheets(sheet=race, data=comb_df)

        time.sleep(30)
        x += 1
