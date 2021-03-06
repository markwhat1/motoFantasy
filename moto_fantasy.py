# import argparse
import calendar
import csv
import json
import re
import time
from configparser import ConfigParser
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import pygsheets
import requests
from bs4 import BeautifulSoup

# Load config.ini
parser = ConfigParser()
parser.read('config.ini')

# ArgParse setup
# arg_parser = argparse.ArgumentParser(description='This is a MotocrossFantasy program', )

# MotocrossFantasy.com variables and URLs
series = parser.get('motocross_fantasy', 'series')
leagueID = parser.get('motocross_fantasy', 'leagueID')
username = parser.get('motocross_fantasy', 'username')
password = parser.get('motocross_fantasy', 'password')
race_type = parser.get('motocross_fantasy', 'race_type')

mf_url = parser.get('motocross_fantasy', 'mf_url')
mf_url_status = f'{mf_url}/user/team-status'

# Live timing JSON URL
live_url = f'http://americanmotocrosslive.com/xml/{series.lower()}/RaceResults.json'
announce_url = f'http://americanmotocrosslive.com/xml/{series.lower()}/Announcements.json'

# List of valid race names
valid_races = ['450 Main Event', '450 Main Event #1', '450 Main Event #2', '450 Main Event #3', '450 Heat #1',
               '450 Heat #2', '450 LCQ', '250 Main Event', '250 Main Event #1', '250 Main Event #2',
               '250 Main Event #3', '250 Heat #1', '250 Heat #2', '250 LCQ']

# List of valid event urls with tables of results
event_urls = {
    '250 Entry List': 'https://supercrosslive.com/results/current/2020/XXXXX/S2ENTRYLIST.html',
    '450 Entry List': 'https://supercrosslive.com/results/current/2020/XXXXX/S1ENTRYLIST.html',
    '250 Heat #1': 'https://supercrosslive.com/results/current/2020/XXXXX/S2H1RES.html',
    '250 Heat #2': 'https://supercrosslive.com/results/current/2020/XXXXX/S2H2RES.html',
    '450 Heat #1': 'https://supercrosslive.com/results/current/2020/XXXXX/S1H1RES.html',
    '450 Heat #2': 'https://supercrosslive.com/results/current/2020/XXXXX/S1H2RES.html',
    '250 LCQ': 'https://supercrosslive.com/results/current/2020/XXXXX/S2L1RES.html',
    '450 LCQ': 'https://supercrosslive.com/results/current/2020/XXXXX/S1L1RES.html',
    '250 Main Event-Provisional': 'https://supercrosslive.com/results/current/2020/XXXXX/S2F1RES.html',
    '450 Main Event-Provisional': 'https://supercrosslive.com/results/current/2020/XXXXX/S1F1RES.html',
    '250 Main Event': 'https://supercrosslive.com/results/current/2020/XXXXX/S2F1PRESS.html',
    '450 Main Event': 'https://supercrosslive.com/results/current/2020/XXXXX/S1F1PRESS.html',
    '450 Main Event #1': 'https://www.supercrosslive.com/results/current/2020/XXXXX/S1E1RES.html',
    '450 Main Event #2': 'https://www.supercrosslive.com/results/current/2020/XXXXX/S1E2RES.html',
    '450 Main Event #3': 'https://www.supercrosslive.com/results/current/2020/XXXXX/S1E3RES.html',
    '250 Main Event #1': 'https://www.supercrosslive.com/results/current/2020/XXXXX/S2E1RES.html',
    '250 Main Event #2': 'https://www.supercrosslive.com/results/current/2020/XXXXX/S2E2RES.html',
    '250 Main Event #3': 'https://www.supercrosslive.com/results/current/2020/XXXXX/S2E3RES.html',
}

# Data files
race_log = 'data/race_log.csv'
rider_list_dir = 'data/rider_lists.csv'
live_timing_dir = 'data/live_timing.csv'


def get_mf_data():
    payload = {'login_username': username, 'login_password': password, 'login': 'true'}

    # Get file modification date and check if it was modified today
    p = Path(rider_list_dir)
    modified_date = date.fromtimestamp(p.stat().st_mtime)
    if date.today() == modified_date:
        # print('Returning rider_lists from csv file...')
        return pd.read_csv(rider_list_dir)
    else:
        print('Checking if updated rider lists is available...')

        # Use 'with' to ensure the session context is closed after use.
        with requests.Session() as s:
            s.post(mf_url, data=payload)

            # Get rider list url contents to check
            resp = s.get(mf_url_status)

            # Make sure username is in html to verify login was successful, else show error message
            assert username in resp.text, 'It appears authentication was unsuccessful...'

            # Check if "Waiting For Rider List" present or if rider lists are available
            if 'Waiting For Rider List' in resp.text:
                print('Rider lists are not currently available for download...')
                print(f'Loading lists from file that were saved on {modified_date}...')
                return pd.read_csv(rider_list_dir)
            else:
                print('Fetching updated rider lists...')
                return get_mf_rider_tables(s, data_dir=rider_list_dir)


def get_mf_rider_urls(ses):
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


def get_mf_rider_tables(ses, data_dir):
    rider_urls = get_mf_rider_urls(ses)

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
        df_riders['mf_name'] = df_riders['mf_name'].str.title()
        df_riders['mf_name'] = format_name(df_riders['mf_name'])
    else:
        print('Rider columns could not be found.')

    dataframe_to_sheets(df=df_riders, sheet='rider_list')
    df_riders.to_csv(data_dir, index=False)
    return df_riders


def get_live_timing_table():
    live_timing = get_json(live_url)

    # New column names in dictionary for replacement
    column_names = {'A': 'pos', 'F': 'name', 'N': 'num', 'L': 'laps', 'G': 'gap', 'D': 'diff', 'BL': 'bestlap',
                    'LL': 'lastlap', 'S': 'status'}

    # Replace live_timing column names with column_name dictionary
    df_live_timing = pd.DataFrame.from_records(live_timing['B'], columns=list(column_names.keys()))
    df_live_timing.rename(columns=column_names, inplace=True)
    df_live_timing['name'] = df_live_timing['name'].str.title()  # Title = Capital first letter, then lowercase
    df_live_timing['name_formatted'] = format_name(df_live_timing['name'])

    # Save live timing DataFrame to CSV
    df_live_timing.to_csv(live_timing_dir, index=False)
    return df_live_timing


def merge_live_timing(data=None, live_data=None, rider_data=None):
    if data:
        df = data
    else:
        df_riders = get_mf_data()
        df_live = get_live_timing_table()

        # Keep only needed columns from rider lists
        df_riders = df_riders[['mf_name', 'hc', 'udog']]

        # Corrections that were needed before changing all names to title() case
        # df_riders['mf_name'] = df_riders['mf_name'].str.replace('McAdoo', 'Mcadoo')
        # df_riders['mf_name'] = df_riders['mf_name'].str.replace('DeCotis', 'Decotis')

        # Merge LiveTiming and rider lists on name columns
        # "how='left'" keeps all rows from live_timing, even if no matches found
        df = df_live.merge(df_riders, how='left', left_on='name_formatted', right_on='mf_name')

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

        # Drop unnecessary columns
        df = df.drop(['mf_name', 'pts_normal', 'pts_udog', 'adj_pos'], axis=1)  #
        df = df.fillna(0, downcast='infer')
        df.style.hide_index()
    return df


def dataframe_to_sheets(df, sheet):
    s = workbook.worksheet_by_title(sheet)
    s.clear(start='A2', end='M100')
    # Set DataFrame to cell A3
    s.set_dataframe(df, (3, 1))  # (row, column)
    return


def get_json(url):
    while True:
        try:
            r = requests.get(url)
            data = json.loads(r.text)  # return announce
        except ValueError as error:  # ValueError includes json.decoder.JSONDecodeError
            print(f'Error: {error}')
        else:
            break
    return data


def save_test_data(version):
    data1 = get_json(announce_url)
    data2 = get_json(live_url)
    r_name = fix_race_name(data2['S'])
    version = version.replace(':', '.')
    live_file = f'test_data/live_timing_{r_name}_{version}.json'
    announce_file = f'test_data/announce_{r_name}_{version}.json'
    with open(announce_file, 'w+') as lf:
        json.dump(data1, lf)
    with open(live_file, 'w+') as lf:
        json.dump(data2, lf)
    return


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
        event_str = re.sub(r"(\d{3}).*(Heat).*?#(\d).*", r"\g<1> \g<2> #\g<3>", event_str)
    elif 'LCQ' in event_str:
        event_str = re.sub(r"(\d{3}).*(LCQ).*", r"\g<1> \g<2>", event_str)
    elif 'Main Event #' in event_str:  # Fix Main Events for Triple Crowns
        event_str = re.sub(r"(\d{3}).*(Main Event).*?#([0-9]).*", r"\g<1> \g<2> #\g<3>", event_str)
    elif 'Main Event' in event_str:
        event_str = re.sub(r"(\d{3}).*(Main Event).*", r"\g<1> \g<2>", event_str)
    return event_str


def get_current_time():
    date_time_obj = datetime.now()
    return date_time_obj.strftime('%I:%M:%S')


def get_current_weekday():
    # Get weekday number; 0-6 starting on Monday, 5 = Saturday
    wd_num = datetime.today().weekday()
    # Get weekday name with calendar module
    return calendar.day_name[wd_num]


def log_races(event_info):
    with open(race_log, 'a', newline='') as af:
        writer = csv.writer(af)
        writer.writerow(event_info)
    return


def last_race_logs():
    data = []
    with open(race_log, 'r', newline='') as rf:
        reader = csv.reader(rf)
        for row in reader:
            data.append(row)
    if len(data) > 2:
        last_logs = data[-2:]
    else:
        last_logs = []
        print('Insufficient data to compare.')
    return last_logs


def race_status(announce_json):
    event_list = announce_json['B']  # Returns list of events from announcements json
    complete_str = 'Session Complete'  # Search in M keys
    s = ''
    for event in event_list:
        if complete_str in event['M']:
            s = 'complete'
        else:
            s = 'incomplete'
    return s


def log_race_status():
    a = get_json(announce_url)
    # Get race title and its status ('incomplete' or 'complete')
    r = fix_race_name(a['S'])
    s = race_status(a)
    current_race_info = [r, s]
    log_races(current_race_info)
    return r, s


def clear_data_sheets():
    all_sheets = workbook.worksheets()
    for sheet in all_sheets:
        if sheet.title in valid_races:
            sheet.clear(start='A3')
    live_sheet = workbook.worksheet_by_title('live_timing')
    live_sheet.clear(start='A3', end='M200')
    update_sheet = workbook.worksheet_by_title('live_timing')
    update_sheet.cell('A1').value = ''
    print('All sheets have been cleared.')
    return


if __name__ == "__main__":
    # Google Sheet workbook
    wb_name = '2020 fantasy supercross'
    g = pygsheets.authorize(credentials_directory='auth')
    workbook = g.open(wb_name)
    print(f'"{wb_name}" authorized; {len(workbook.worksheets())} sheets found.')

    clear_sheets = False
    if clear_sheets:
        clear_data_sheets()

    x = 0
    sleep_timer = 30  # time in seconds
    while x < 100:
        if x == 0:
            x += 1
            pass
        else:
            x += 1
            time.sleep(sleep_timer)

        weekday = get_current_weekday()
        if weekday == 'Saturday':
            pass
        else:
            # If not Saturday, update rider lists then exit
            print(f'Today is {weekday}, skipping live_timing update.')
            get_mf_data()
            break

        # Get race title and its status ('incomplete' or 'complete')
        race, status = log_race_status()
        if race in valid_races:
            pass
        elif 'Practice' in race:
            print(f'{x}: Currently in {race}, races have not started yet.')
            continue
        elif 'Sighting Lap' in race:
            print(f'{x}: {race} underway, main event to start shortly.')
            continue
        else:
            print(f'{x}: "{race}" is either not tracked or will need to be corrected to successfully save results.')
            continue

        # Combine live_timing and rider_lists from scratch
        comb_df = merge_live_timing(data=None)

        # breakpoint()

        # Get last 2 race logs to compare
        logs = last_race_logs()
        if logs:
            prev_info = logs[0]
            cur_info = logs[1]
        else:
            print(f'Not enough data has been logged yet.')
            continue

        # Flow pattern to handle race day updates

        # RACE CHANGE?
        # If same race is continuing
        if cur_info[0] == prev_info[0]:
            # COMPLETION CHANGE?
            if cur_info[1] == 'incomplete':
                print(f'{x}: {race} in progress. Downloading live timing data.')
                dataframe_to_sheets(df=comb_df, sheet='live_timing')

            elif cur_info[1] == 'complete':
                if prev_info[1] == 'incomplete':
                    print(f'{x}: {race} complete. Archiving copy of live timing table.')
                    # If completion statuses are different and race is the same,
                    # then the race has to have changed from incomplete to complete
                    dataframe_to_sheets(df=comb_df, sheet='live_timing')
                    dataframe_to_sheets(df=comb_df, sheet=race)
                    wks = workbook.worksheet_by_title('live_timing')
                    complete_race_title = race + ' - Complete'
                    wks.cell('A1').value = complete_race_title
                else:
                    print(f'{x}: {race} complete. Waiting for next race to begin.')

        # Else if new race has begun
        else:
            # New race has just begun, update race name
            print(f'{x}: {race} bas begun. Downloading live timing data.')
            wks = workbook.worksheet_by_title('live_timing')
            wks.cell('A1').value = race

            # Begin updating live_timing for new race
            dataframe_to_sheets(df=comb_df, sheet='live_timing')
