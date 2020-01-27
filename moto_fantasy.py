import json
import re
from datetime import datetime, date
import time
from configparser import ConfigParser
from pathlib import Path

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


def mf_master():
    rider_list_dir = 'data/rider_lists.csv'
    payload = {'login_username': username, 'login_password': password, 'login': 'true'}

    # Get file modification date and check if it was modified today
    p = Path(rider_list_dir)
    modified_date = date.fromtimestamp(p.stat().st_mtime)
    if date.today() == modified_date:
        print('Returning rider_lists from csv file.')
        return pd.read_csv(rider_list_dir)
    else:
        print('Checking if updated rider list is available...')

        # Use 'with' to ensure the session context is closed after use.
        with requests.Session() as s:
            s.post(mf_url_base, data=payload)

            # Check for presence of Pick Rider links, and download tables if present, otherwise load csv file
            # TO DO find text from pick-riders link that says "Waiting For Rider List"
            resp = s.get(mf_url_status)
            # Make sure username is in html to verify login was successful
            assert username in resp.text, 'It appears authentication was unsuccessful.'
            if "Waiting For Rider List" in resp.text:
                print('Rider lists are not currently available for download, loading lists from file.')
                return pd.read_csv(rider_list_dir)
            else:
                print('Fetching updated rider lists.')
                return get_mf_rider_tables(s, data_dir=rider_list_dir)


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


def get_mf_rider_tables(ses, data_dir):
    rider_urls = get_mf_table_urls(ses)

    rider_lists = []
    for div in rider_urls.keys():
        html = ses.get(rider_urls.get(div)).content
        soup = BeautifulSoup(html, 'lxml')
        table = soup.find('table')
        if table:
            # read_html requires html in string format
            rider_tables = pd.read_html(str(table), flavor='bs4')

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


def get_live_timing_table(num_retries=3):
    for attempt_no in range(num_retries):
        try:
            r = requests.get(live_url)
            live_timing = json.loads(r.text)

            # New column names in dictionary for replacement
            column_names = {'A': 'pos', 'F': 'name', 'N': 'num', 'L': 'laps', 'G': 'gap', 'D': 'diff', 'BL': 'bestlap',
                            'LL': 'lastlap', 'S': 'status'}

            df_live_timing = pd.DataFrame.from_records(live_timing['B'], columns=list(column_names.keys()))
            df_live_timing.rename(columns=column_names, inplace=True)
            df_live_timing['name_formatted'] = format_name(df_live_timing['name'])

            # Save live timing DataFrame to CSV
            df_live_timing.to_csv('data/live_timing.csv', index=False)
            return df_live_timing
        except ValueError as error:  # ValueError includes json.decoder.JSONDecodeError
            if attempt_no < (num_retries - 1):
                print(f'Error: {error}')
            else:
                raise error


def get_announcements(num_retries=3):
    while True:
        # for attempt_no in range(num_retries):
        try:
            r = requests.get(announce_url)
            announce = json.loads(r.text)
            # return announce
        except ValueError as error:  # ValueError includes json.decoder.JSONDecodeError
            # if attempt_no < (num_retries - 1):
            print(f'Error: {error}')
            # else:
            #     raise error
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
    client = pygsheets.authorize(client_secret='auth/client_secret.json')
    ss = client.open('2020 fantasy supercross')
    wks = ss.worksheet_by_title(sheet)
    wks.clear(start='A2', end='L100')
    wks.set_dataframe(df, (2, 1))  # Live timing table to cell A2
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
    event_str = event_str.replace('Last Chance Qualifier', 'LCQ')
    if 'Heat' in event_str:
        event_str = re.sub("(\d{3}).*(Heat).*?#(\d).*", "\g<1> \g<2> #\g<3>", event_str)
    elif 'LCQ' in event_str:
        event_str = re.sub("(\d{3}).*(LCQ).*", "\g<1> \g<2>", event_str)
    elif 'Main Event #' in event_str:  # Fix Main Events for Triple Crowns
        event_str = re.sub("(\d{3}).*(Main Event).*?#([0-9]).*", "\g<1> \g<2> #\g<3>", event_str)
    elif 'Main Event' in event_str:
        event_str = re.sub("(\d{3}).*(Main Event).*", "\g<1> \g<2>", event_str)
    # event_str = re.sub("\s+", " ", event_str)
    # event_str = re.sub("\s[0-9]{1,2}\sMinute.*", "", event_str)  # Remove ## Minutes Plus 1 Lap text
    # event_str = re.sub("([0-9]{3})(\s?S?X?)(.*)", "\g<1>SX \g<3>", event_str)
    return event_str


def get_current_time():
    date_time_obj = datetime.now()
    return date_time_obj.strftime("%I:%M:%S")


def save_race_log(event):
    race_log = 'data/race_log.txt'
    # Open file in append mode
    with open(race_log, 'a+') as f:
        # Move to beginning of the file
        f.seek(0)
        # Get list of saved races by lines
        race_list = f.read().splitlines()
        print(f'race_list: {race_list}')
        # Get last race from list, unless list is empty, then return null value
        if race_list:
            last_race = race_list[-1]
        else:
            last_race = ''
        print(f'Last race: {last_race}')
        if last_race == event:
            return False
        else:
            f.write(f'{event}\n')
            return True


def save_current_race(event):
    current_race_log = 'data/current_race.txt'
    # Open file in write mode
    with open(current_race_log, "w+") as f:
        saved_race = f.read()
        if saved_race == event:
            return True
        else:
            f.write(event)
            return False


if __name__ == "__main__":
    x = 1
    while x < 100:
        comb_df = comb_live_timing_to_sheets(sheet='live_timing', data=None)

        # Test Announcements.json for race being complete
        announcements = get_announcements()  # Returns JSON object
        race = announcements['S']
        race = fix_race_name(race)

        # Save current race to make decisions on how to proceed later in script
        save_current_race(race)
        new_race = save_race_log(race)

        # Log all race names to file
        # new_race = True if new race added to log and False if race already added
        new_race = False
        race_saved = False
        while race_saved is False:
            complete_str = 'Session Complete'  # Search in M keys
            event_list = announcements['B']
            for event in event_list:
                if complete_str in event['M']:
                    print(f'{race} has completed. Saving copy of live timing.')
                    comb_live_timing_to_sheets(sheet=race, data=comb_df)
                    race_saved = True

        # Save current race to Google Sheets
        client = pygsheets.authorize(client_secret='auth/client_secret.json')
        ss = client.open('2020 fantasy supercross')
        wks = ss.worksheet_by_title('update')
        wks.update_value('A2', race)

        timestamp = get_current_time()
        print(f"{timestamp}: Downloading live timing data for {race}.")

        valid_races = ['450 Main Event', '450 Main Event #1', '450 Main Event #2', '450 Main Event #3',
                       '250 Main Event', '250 Main Event #1', '250 Main Event #2', '250 Main Event #3',
                       '250 Heat #1', '250 Heat #2', '450 Heat #1', '450 Heat #2',
                       '250 LCQ', '450 LCQ']
        if race not in valid_races:
            print(f'"{race}" name will need to be corrected to successfully save results.')
        else:
            complete_str = 'Session Complete'  # Search in M keys
            event_list = announcements['B']
            for event in event_list:
                if complete_str in event['M']:
                    print(f'{race} has completed. Saving copy of live timing.')
                    comb_live_timing_to_sheets(sheet=race, data=comb_df)
        #
        time.sleep(30)
        x += 1
