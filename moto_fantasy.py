import json
import re
import time

# import keyring
import pandas as pd
import pygsheets
import requests
from bs4 import BeautifulSoup

# MotocrossFantasy.com variables and URLs
series = 'sx'
leagueID = 4370
username = 'markwhat'
password = 'bea1+9-@oD4YBKE7sdbX'

mf_url_base = 'https://www.motocrossfantasy.com'
mf_url_status = f"{mf_url_base}/user/team-status"
mf_url_team_standings = f"{mf_url_base}/user/bench-racing-divisions/{leagueID}"
mf_url_week_standings = f"{mf_url_base}/user/weekly-standings/{leagueID}"
mf_url_race_results = f"{mf_url_base}/user/race-results"
mf_url_top_picks = f"{mf_url_base}/user/top-picks/2020-SX"

live_url = f"http://americanmotocrosslive.com/xml/{series.lower()}/RaceResults.json"


def mf_master():
    payload = {'login_username': username, 'login_password': password, 'login': 'true'}

    # Use 'with' to ensure the session context is closed after use.
    with requests.Session() as s:
        s.post(mf_url_base, data=payload)

        # Get current week header from status page to see if update required
        html = s.get(mf_url_status).content
        soup = BeautifulSoup(html, 'lxml')
        status = soup.h3.get_text()
        print(f'"{status}" is the current status.')

        # Check if status is the same or if rider lists need to be updated
        if check_sheets_update(status):
            riders = mf_rider_tables(s)
            rider_list_to_sheets(riders)
        else:
            riders = pd.read_csv('rider_lists.csv')
    return riders


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
        print(f"{len(rider_tables)} {div} class table(s) were found!")

        # read_html returns list of DataFrames, only need first one
        df_table = rider_tables[0]

        # Add Class column to beginning of DataFrame
        df_table.insert(0, "Class", div, allow_duplicates=True)

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

    df_riders.to_csv('rider_lists.csv', index=False)
    return df_riders


def check_sheets_update(status):
    client = pygsheets.authorize(no_cache=True)
    ss = client.open('2020 fantasy supercross')

    wks = ss.worksheet_by_title('update')
    old_status = wks.get_value('A1')
    if old_status == status:
        print('No rider list update required. Loading CSV data.')
        update_data = False
        pass
    else:
        print('Rider list update will be performed.')
        update_data = True
        wks.update_value('A1', status)
    return update_data


def rider_list_to_sheets(rider_list):
    client = pygsheets.authorize(no_cache=True)
    ss = client.open('2020 fantasy supercross')

    wks = ss.worksheet_by_title('rider_list')
    wks.clear(start='B1')
    wks.set_dataframe(rider_list, (3, 1))

    # df_450 = rider_list[rider_list['Class'] == 450]
    # df_250 = rider_list[rider_list['Class'] == 250]
    #
    # wks_450 = ss.worksheet_by_title('450_riders')
    # wks_450.clear()
    # wks_450.set_dataframe(df_450, (1, 1))
    #
    # wks_250 = ss.worksheet_by_title('250_riders')
    # wks_250.clear()
    # wks_250.set_dataframe(df_250, (1, 1))
    return


def live_timing_to_sheets():
    r = requests.get(live_url)
    live_timing = json.loads(r.text)

    column_names = {'A': 'pos', 'F': 'name', 'N': 'num', 'L': 'laps', 'G': 'gap', 'D': 'diff', 'BL': 'bestlap',
                    'LL': 'lastlap', 'S': 'status'}

    df_live_timing = pd.DataFrame.from_records(live_timing['B'], columns=list(column_names.keys()))
    df_live_timing.rename(columns=column_names, inplace=True)
    df_live_timing['name'] = format_name(df_live_timing['name'])

    # Save live timing DataFrame to CSV
    df_live_timing.to_csv('live_timing.csv', index=False)

    # Assemble current race information
    status = live_timing['A']
    location = live_timing['T']  # Race location/name - 'Washougal'
    if series == 'sx':
        long_moto_name = live_timing['S']
        short_moto_name = live_timing['S']
        division = live_timing['S']
    else:
        long_moto_name = live_timing['S'].split(' (', 1)[0]  # '450 Class Moto #2'
        short_moto_name = long_moto_name.split('Class ', 1)[1]
        division = long_moto_name.split('Class ', 1)[0]

    client = pygsheets.authorize(no_cache=True)
    ss = client.open('2020 fantasy supercross')
    wks = ss.worksheet_by_title('live_timing')

    # Updates to current race information
    wks.update_values('A1:D1', [[series.upper(), location, division, short_moto_name]])

    # Update live timing table beneath current race information
    wks.set_dataframe(df_live_timing, (3, 1))  # Live timing table
    return df_live_timing


def format_name(df_column):
    """
    df_column: DataSeries
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
               12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]   # 11-22
    else:
        pts = [25, 22, 20, 18, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3,   # 1-18
               2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # 19-40

    dict_pos = dict(zip(range(1, len(pts) + 1), pts))
    dict_pos_udog = dict_pos.copy()
    for x in dict_pos_udog.keys():
        if x <= 10:
            dict_pos_udog[x] *= 2
    dict_pts = dict()
    dict_pts['normal'] = dict_pos
    dict_pts['udog'] = dict_pos_udog
    return dict_pts


if __name__ == "__main__":
    # Update rider lists on Google Sheets; save riders DataFrame
    # df_rider_list = mf_master()
    # print(df_rider_list)
    # df_live_timing = live_timing_to_sheets()
    # print(df_live_timing)

    df_live = pd.read_csv('live_timing.csv')
    df_live = df_live[['pos', 'name']]
    df_rider = pd.read_csv('rider_lists.csv')
    df_rider = df_rider[['Name', 'HC', 'UD']]
    print(df_live)
    print(df_rider)

    df2 = df_live.merge(df_rider, how='left', left_on='name', right_on='Name')
    df2['adj_pos'] = df2['pos'] - df2['HC']
    df2['adj_pos'] = df2.adj_pos.mask(df2.adj_pos == 0, 1)
    df2 = df2.fillna(0, downcast='infer')

    points = create_pts_dict()

    df2['pts_normal'] = df2['adj_pos'].map(points['normal'])
    df2['pts_udog'] = df2['adj_pos'].map(points['udog'])
    print(df2)

    filter1 = df2['UD'] == 'Yes'
    filter2 = df2['adj_pos'] <= 10
    df2['pts_udog'] = df2.pts_udog.where(filter1 & filter2, 0)

    df2['pts'] = df2[['pts_normal', 'pts_udog']].max(axis=1)
    df2 = df2.drop(['Name', 'pts_normal', 'pts_udog'], axis=1)
    df2 = df2.fillna(0, downcast='infer')

    # df2['pts_udog'] = df2.pts_udog.where(df2.UD == 'Yes' & df2.adj_pos <= 10, 0)
    # df2['pts_udog'] = df2.pts_udog.where(df2.adj_pos <= 10, 0)

    print(df2)

    # x = 1
    # while x < 60:
    #     print(f"Downloading live timing data, update #{x}.")
    #     live_timing_to_sheets()
    #     time.sleep(30)
    #     x += 1

    # mf_master()  # live_timing_to_sheets(series)
