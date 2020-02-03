import json
import re
from datetime import datetime, date
import time
from configparser import ConfigParser
from pathlib import Path
import argparse

import pandas as pd
import pygsheets
import requests
from bs4 import BeautifulSoup

# Load config.ini
parser = ConfigParser()
parser.read('config.ini')

# ArgParse setup
arg_parser = argparse.ArgumentParser(description='This is a MotocrossFantasy program', )

# MotocrossFantasy.com variables and URLs
series = parser.get('motocross_fantasy', 'series')
leagueID = parser.get('motocross_fantasy', 'leagueID')
username = parser.get('motocross_fantasy', 'username')
password = parser.get('motocross_fantasy', 'password')
race_type = parser.get('motocross_fantasy', 'race_type')

mf_url_base = parser.get('motocross_fantasy', 'mf_url')
mf_url_status = f"{mf_url_base}/user/team-status"
mf_url_team_standings = f"{mf_url_base}/user/bench-racing-divisions/{leagueID}"
mf_url_week_standings = f"{mf_url_base}/user/weekly-standings/{leagueID}"
mf_url_race_results = f"{mf_url_base}/user/race-results"
mf_url_top_picks = f"{mf_url_base}/user/top-picks/2020-SX"

# Live timing JSON URL
live_url = f"http://americanmotocrosslive.com/xml/{series.lower()}/RaceResults.json"
announce_url = f"http://americanmotocrosslive.com/xml/{series.lower()}/Announcements.json"

# Google Sheet workbook
workbook = '2020 fantasy supercross'

# Data files
race_log = 'data/race_log.txt'
comp_race_log = 'data/comp_race_log.txt'
rider_list_dir = 'data/rider_lists.csv'
live_timing_dir = 'data/live_timing.csv'


def mf_master():
    payload = {'login_username': username, 'login_password': password, 'login': 'true'}

    # Get file modification date and check if it was modified today
    p = Path(rider_list_dir)
    modified_date = date.fromtimestamp(p.stat().st_mtime)
    if date.today() == modified_date:
        print('Returning rider_lists from csv file.')
        return pd.read_csv(rider_list_dir)
    else:
        print('Checking if updated rider lists is available...')

        # Use 'with' to ensure the session context is closed after use.
        with requests.Session() as s:
            s.post(mf_url_base, data=payload)

            html = s.get(mf_url_top_picks).text
            rider_tables_test = pd.read_html(html)
            print(rider_tables_test)
            print(type(rider_tables_test))

            # Get rider list url contents to check
            resp = s.get(mf_url_status)

            # Make sure username is in html to verify login was successful, else show error message
            assert username in resp.text, 'It appears authentication was unsuccessful.'

            # Check if "Waiting For Rider List" present or if rider lists are available
            if "Waiting For Rider List" in resp.text:
                print('Rider lists are not currently available for download, loading lists from file.')
                return pd.read_csv(rider_list_dir)
            else:
                print('Fetching updated rider lists.')
                return get_mf_rider_tables(s, data_dir=rider_list_dir)


def get_mf_rider_tables(ses, data_dir):
    rider_urls = get_mf_table_urls(ses)

    rider_lists = []
    for div in rider_urls.keys():
        # Get rider list html and read into pandas DataFrame
        # read_html returns list of DataFrames if multiple tables are found
        html = ses.get(rider_urls.get(div)).text
        rider_tables = pd.read_html(html)

        if rider_tables:
            # read_html returns list of DataFrames, only need first one
            df_table = rider_tables[0]

            # Add Class column to beginning of DataFrame
            df_table.insert(0, 'class', div, allow_duplicates=True)

            # Add rider lists to same list
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

    df_riders.to_csv(data_dir, index=False)
    return df_riders


def get_mf_table_urls(ses):
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


def google_wks(wb, ws):
    g = pygsheets.authorize(client_secret='auth/client_secret.json')
    w = g.open(wb)
    return w.worksheet_by_title(ws)


def rider_list_to_sheets(rider_list):
    s = google_wks(wb=workbook, ws='rider_list')
    s.clear(start='B1')
    s.set_dataframe(rider_list, (3, 1))
    return


def get_live_timing_table():
    while True:
        try:
            r = requests.get(live_url)
            live_timing = json.loads(r.text)
        except ValueError as error:  # ValueError includes json.decoder.JSONDecodeError
            print(f'Error: {error}')
        break

    # New column names in dictionary for replacement
    column_names = {'A': 'pos', 'F': 'name', 'N': 'num', 'L': 'laps', 'G': 'gap', 'D': 'diff', 'BL': 'bestlap',
                    'LL': 'lastlap', 'S': 'status'}

    df_live_timing = pd.DataFrame.from_records(live_timing['B'], columns=list(column_names.keys()))
    df_live_timing.rename(columns=column_names, inplace=True)
    df_live_timing['name_formatted'] = format_name(df_live_timing['name'])

    # Save live timing DataFrame to CSV
    df_live_timing.to_csv(live_timing_dir, index=False)
    return df_live_timing


def get_announcements():
    while True:
        try:
            r = requests.get(announce_url)
            announce = json.loads(r.text)  # return announce
        except ValueError as error:  # ValueError includes json.decoder.JSONDecodeError
            print(f'Error: {error}')
        else:
            break

    return announce


def comb_live_timing_to_sheets(sheet, data=None):
    if data:
        df = data
    else:
        df_live = get_live_timing_table()
        df_rider = mf_master()

        # Keep only needed columns from rider lists
        df_rider = df_rider[['mf_name', 'hc', 'udog']]
        df_rider['mf_name'] = df_rider['mf_name'].str.replace('McAdoo', 'Mcadoo')
        df_rider['mf_name'] = df_rider['mf_name'].str.replace('DeCotis', 'Decotis')

        # Merge LiveTiming and rider lists on name columns
        # Left keeps all rows from live_timing, even if no matches found
        df = df_live.merge(df_rider, how='left', left_on='name_formatted', right_on='mf_name')

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

    # Upload combined LiveTiming dataframe to Google Sheets
    lt_sheet = google_wks(wb=workbook, ws=sheet)
    lt_sheet.clear(start='A2', end='L100')
    lt_sheet.set_dataframe(df, (2, 1))  # Live timing table to cell A2
    return df


def format_name(df_column):
    """
    :df: DataSeries:
    """
    df = pd.Series(df_column).to_frame(name='name')
    splits = df['name'].str.split(' ')
    df['last'] = splits.str[1]
    df['first'] = splits.str[0]
    df['first'] = df['first'].str.slice(0, 2) + str('.')
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
    event_str = event_str.replace('Last Chance Qualifier', 'LCQ')
    if 'Heat' in event_str:
        event_str = re.sub("(\d{3}).*(Heat).*?#(\d).*", "\g<1> \g<2> #\g<3>", event_str)
    elif 'LCQ' in event_str:
        event_str = re.sub("(\d{3}).*(LCQ).*", "\g<1> \g<2>", event_str)
    elif 'Main Event #' in event_str:  # Fix Main Events for Triple Crowns
        event_str = re.sub("(\d{3}).*(Main Event).*?#([0-9]).*", "\g<1> \g<2> #\g<3>", event_str)
    elif 'Main Event' in event_str:
        event_str = re.sub("(\d{3}).*(Main Event).*", "\g<1> \g<2>", event_str)
    return event_str


def get_current_time():
    date_time_obj = datetime.now()
    return date_time_obj.strftime("%I:%M:%S")


def is_new_race(log, cur_event):
    # Open file in append mode
    with open(log, 'a+') as f:
        # Move to beginning of the file
        f.seek(0)
        # Get list of saved races by lines
        race_list = f.read().splitlines()

        # Get last race from list, unless list is empty, then return null value
        if race_list:
            last_race = race_list[-1]
            if last_race == cur_event:
                return False
            else:
                f.write(f'{cur_event}\n')
                return True


def is_comp_race(log, cur_event):
    # Open file in append mode
    with open(log, 'a+') as f:
        # Move to beginning of the file
        f.seek(0)
        # Get list of saved races by lines
        race_list = f.read().splitlines()

        # Get last race from list, unless list is empty, then return null value
        if race_list:
            last_comp_race = race_list[-1]
            if last_comp_race == cur_event:
                return False
            else:
                f.write(f'{cur_event}\n')
                return True


if __name__ == "__main__":
    x = 1
    while x < 100:

        # Fetch announcements.json for race updates
        announcements = get_announcements()  # Returns JSON object
        race = announcements['S']
        race = fix_race_name(race)

        comb_df = comb_live_timing_to_sheets(sheet='live_timing', data=None)

        # Log active race and return True/False if race had already started
        race_new = is_new_race(log=race_log, cur_event=race)

        # Log completed race
        # Return True if race already completed; False if race had already completed
        race_complete = is_comp_race(log=comp_race_log, cur_event=race)

# List of possible race statuses
# new_race = True, comp_race = False -> update current race; update live_timing
# new_race = False, comp_race = False -> don't update current race; update live_timing
# new_race = False, comp_race = True -> don't update current race; update live_timing; save live_timing
# new_race = False, comp_race = False -> don't update current race; update live_timing; don't save live_timing

        # Save current race to Google Sheets 'update' worksheet
        wks = google_wks(wb=workbook, ws='update')
        wks.cell('A2').set_text_format('bold', True).value = race

        valid_races = ['450 Main Event', '450 Main Event #1', '450 Main Event #2', '450 Main Event #3',
                       '250 Main Event', '250 Main Event #1', '250 Main Event #2', '250 Main Event #3', '250 Heat #1',
                       '250 Heat #2', '450 Heat #1', '450 Heat #2', '250 LCQ', '450 LCQ']
        if race in valid_races:
            race_saved = False
            while race_saved is False:
                event_list = announcements['B']  # Returns list of events from announcements json
                complete_str = 'Session Complete'  # Search in M keys
                for event in event_list:
                    if complete_str in event['M']:
                        complete_time = event['TT']
                        print(f'{race} completed at {complete_time}. Saving copy of live timing.')
                        comb_live_timing_to_sheets(sheet=race, data=comb_df)
                        race_saved = True
        else:
            print(f'"{race}" name will need to be corrected to successfully save results.')
        timestamp = get_current_time()
        print(f"{timestamp}: Downloading live timing data for {race}.")

        time.sleep(30)
        x += 1
