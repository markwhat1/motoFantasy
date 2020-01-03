import json
import re

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


# Create pos/points dictionaries
pts_sx = [26, 23, 21, 19, 18, 17, 16, 15, 14, 13,  # 1-10
          12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]  # 11-22
dict_sx = dict(zip(range(1, len(pts_sx) + 1), pts_sx))
dict_sx_udog = dict_sx.copy()
for key in dict_sx_udog.keys():
    if key <= 10:
        dict_sx_udog[key] *= 2

pts_mx = [25, 22, 20, 18, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3,
          2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
dict_mx = dict(zip(range(1, len(pts_mx) + 1), pts_mx))
dict_mx_udog = dict_mx.copy()
for key in dict_mx_udog.keys():
    if key <= 10:
        dict_mx_udog[key] *= 2

# Create master pos/points nested dictionary, then select dictionary based on series
pts_all = dict()
pts_all['mx'] = {}
pts_all['mx']['normal'] = dict_mx
pts_all['mx']['udog'] = dict_mx_udog
pts_all['sx'] = {}
pts_all['sx']['normal'] = dict_sx
pts_all['sx']['udog'] = dict_sx_udog

points = pts_all[series.lower()]


# print(points)


def mf_master():
    payload = {
        'login_username': username,
        'login_password': password,
        'login': 'true'
    }

    # Use 'with' to ensure the session context is closed after use.
    with requests.Session() as s:
        s.post(mf_url_base, data=payload)

        html = s.get(mf_url_status).content
        soup = BeautifulSoup(html, 'lxml')
        status = soup.find('h3')
        # if check_sheets_update(status):
        riders = mf_rider_tables(s)
        rider_list_to_sheets(riders)
        # print(status.text)

    return


def check_sheets_update(status):
    client = pygsheets.authorize(no_cache=True)
    ss = client.open('2020 fantasy supercross')

    wks = ss.worksheet_by_title('rider_list')
    old_status = wks.get_value('A1')
    if old_status == status:
        update_data = False
        pass
    else:
        update_data = True
        # wks.update_value('A1', val=status)
    return update_data


def create_pts_dict(cur_series, points):
    dict_pos = dict(zip(range(1, len(points) + 1), points))
    dict_pos_udog = dict_pos.copy()
    for key in dict_pos_udog.keys():
        if key <= 10:
            dict_pos_udog[key] *= 2
    dict_pts = dict()
    dict_pts[cur_series.lower()] = dict()
    dict_pts[cur_series.lower()]['normal'] = dict_pos
    dict_pts[cur_series.lower()]['udog'] = dict_pos_udog
    print(dict_pts)
    return dict_pts


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
    print(rider_urls)

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

    df_riders.to_csv('rider_lists.csv')

    return df_riders


def format_name(df_column):
    """
    df_column: DataSeries
    """
    df = pd.Series(df_column).to_frame(name='name')
    splits = df['name'].str.split(' ')
    df['last'] = splits.str[1]
    df['first'] = splits.str[0]
    df['first'] = df['first'].str.slice(0, 1) + str('.')
    df['name'] = df['last'].str.cat(
        df['first'], sep=', ')
    df = df.loc[:, 'name']
    return df


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


def live_timing_to_sheets(ser):
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
    if ser == 'sx':
        long_moto_name = live_timing['S']
        short_moto_name = live_timing['S']
        division = live_timing['S']
    else:
        long_moto_name = live_timing['S'].split(' (', 1)[0]  # '450 Class Moto #2'
        short_moto_name = long_moto_name.split('Class ', 1)[1]
        division = long_moto_name.split('Class ', 1)[0]

    client = pygsheets.authorize(no_cache=True)
    ss = client.open('2020 fantasy supercross')
    # ss.DataRange(start='A1', end='D1', worksheet='live_timing')
    wks = ss.worksheet_by_title('live_timing')

    # Updates to current race information
    # wks.update_values('A1:D1', values=([series.upper(), location, division, short_moto_name]))  # Series (MX or SX)

    # wks.update_cell('B1', location)  # Location
    # wks.update_cell('C1', division)  # Class
    # wks.update_cell('D1', short_moto_name)  # Event
    wks.set_dataframe(df_live_timing, (3, 1))  # Live timing table
    return df_live_timing


def get_rider_pts(live_pos, icap, udog):
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
    print(live_url)

    print(mf_master())

    # pts_sx = [26, 23, 21, 19, 18, 17, 16, 15, 14, 13,  # 1-10
    #           12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]  # 11-22
    # create_pts_dict('sx', pts_sx)
    # x = 1
    # while x < 60:
    #     print(f"Downloading live timing data, update #{x}.")
    #     live_timing_to_sheets(series)
    #     time.sleep(30)
    #     x += 1


    # mf_master()
    # live_timing_to_sheets(series)
