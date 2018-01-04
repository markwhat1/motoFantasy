import pandas as pd
import requests
import pygsheets


all_points = {'mx': {
    'normal': {1: 25, 2: 22, 3: 20, 4: 18, 5: 16, 6: 15, 7: 14, 8: 13, 9: 12, 10: 11, 11: 10, 12: 9, 13: 8, 14: 7,
               15: 6, 16: 5, 17: 4, 18: 3, 19: 2, 20: 1, 21: 0, 22: 0, 23: 0, 24: 0, 25: 0, 26: 0, 27: 0, 28: 0, 29: 0,
               30: 0, 31: 0, 32: 0, 33: 0, 34: 0, 35: 0, 36: 0, 37: 0, 38: 0, 39: 0, 40: 0},
    'udog': {1: 50, 2: 44, 3: 40, 4: 36, 5: 32, 6: 30, 7: 28, 8: 26, 9: 24, 10: 22, 11: 10, 12: 9, 13: 8, 14: 7, 15: 6,
             16: 5, 17: 4, 18: 3, 19: 2, 20: 1, 21: 0, 22: 0, 23: 0, 24: 0, 25: 0, 26: 0, 27: 0, 28: 0, 29: 0, 30: 0,
             31: 0, 32: 0, 33: 0, 34: 0, 35: 0, 36: 0, 37: 0, 38: 0, 39: 0, 40: 0}}, 'sx': {
    'normal': {1: 25, 2: 22, 3: 20, 4: 18, 5: 16, 6: 15, 7: 14, 8: 13, 9: 12, 10: 11, 11: 10, 12: 9, 13: 8, 14: 7,
               15: 6, 16: 5, 17: 4, 18: 3, 19: 2, 20: 1, 21: 1, 22: 1},
    'udog': {1: 50, 2: 44, 3: 40, 4: 36, 5: 32, 6: 30, 7: 28, 8: 26, 9: 24, 10: 22, 11: 10, 12: 9, 13: 8, 14: 7, 15: 6,
             16: 5, 17: 4, 18: 3, 19: 2, 20: 1, 21: 1, 22: 1}}}

raceCompleteDict = {("250", "1"): False, ("250", "2"): False, ("450", "1"): False, ("450", "2"): False,
                    ("250", "HEAT", "1"): False, ("250", "HEAT", "2"): False, ("250", "LCQ"): False,
                    ("250", "MAIN"): False, ("450", "HEAT", "1"): False, ("450", "HEAT", "2"): False,
                    ("450", "SEMI", "1"): False, ("450", "SEMI", "2"): False, ("450", "LCQ"): False,
                    ("450", "MAIN"): False}

bubbleDict = {('450', 'HEAT'): 4, ('450', 'SEMI'): 5, ('450', 'LCQ'): 4, ('450', 'LAST CHANCE QUALIFIER'): 4,
              ('250', 'HEAT'): 9, ('250', 'LCQ'): 4, ('250', 'LAST CHANCE QUALIFIER'): 4}


class Event:
    def __init__(self, series):
        series_types = ['mx', 'sx']
        if series.lower() not in series_types:
            raise ValueError(f'Invalid series type: {series}')
        self.series = series.lower()
        self.lt_url = f'http://americanmotocrosslive.com/xml/{self.series}/RaceResults.json'
        self.live_timing = None
        # self.info_url = None
        self.location = None  # Race location/name - 'Washougal'
        self.long_moto_name = None  # '450 Class Moto #2'
        self.moto_num = None  # 1 or 2
        self.division = None  # 250 or 450
        self.rider_count = None  # Int up to 40
        self.points_dict = all_points[self.series]

    def get_event_info(self):
        r = requests.get(self.lt_url)
        resp = r.json()

        self.location = resp['T']  # Race location/name - 'Washougal'
        self.long_moto_name = resp['S'].split(' (', 1)[0]  # '450 Class Moto #2'
        self.moto_num = int(self.long_moto_name.split('#', 1)[1])
        self.division = self.long_moto_name.split('Class ', 1)[0]
        self.rider_count = resp['R']
        return resp

    def get_live_timing(self):
        r = requests.get(self.lt_url)
        resp = r.json()

        # Take rider list and turn it into DataFrame
        columns = {'A': 'pos', 'F': 'name', 'N': 'num', 'L': 'laps', 'G': 'gap', 'D': 'diff', 'BL': 'best_lap',
                   'LL': 'last_lap', 'S': 'status'}
        df_lt = pd.DataFrame(resp['B'], columns=columns)
        df_lt = df_lt.rename(columns=columns)

        # Reformat name in Smith, J. format
        df_lt['name'] = format_name(df_lt['name'])

        # Add division column
        df_lt.insert(len(df_lt.columns), "division", self.division, allow_duplicates=True)
        print(df_lt.head())
        return df_lt

    def main(self):
        self.get_event_info()
        self.get_live_timing()


class Workbook:
    def __init__(self, workbook):
        self.wb = self.open_workbook(workbook)

    def open_workbook(self, workbook):
        service_file = 'service_creds.json'
        gc = pygsheets.authorize(service_file=service_file, no_cache=True)
        wb = gc.open(workbook)
        return wb

    def set_live_timing(self, live_timing_df):
        wks = self.wb.worksheet_by_title('live timing')
        wks.clear(start='A1', end='I41')
        wks.set_dataframe(live_timing_df, (1,1))
        return

    def get_picked_riders(self):
        wks = self.wb.worksheet_by_title('picked riders')
        df_all = wks.get_as_df(has_header=True, start='A1', end='C41')
        df = df_all[df_all['Rider'].notnull()]
        print(df.head())
        print(df.shape)

    def main(self):
        self.get_picked_riders()


def format_name(df_column):
    df = pd.Series(df_column).to_frame(name='name')
    splits = df['name'].str.split(' ')
    df['last'] = splits.str[1]
    df['first'] = splits.str[0]
    df['first'] = df['first'].str.slice(0, 1) + str('.')
    df['name'] = df['last'].str.cat(df['first'], sep=', ')
    df = df.loc[:, 'name']
    return df


if __name__ == "__main__":
    lt = Event('SX')
    lt.main()
    variables = lt.__dict__.items()

    wb = Workbook('2017 fantasy supercross')
    wb.main()
    # for item in variables:
    #     print(item)  # print(variables)
