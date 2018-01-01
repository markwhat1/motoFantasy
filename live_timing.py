import requests
import xmltodict
import json
import untangle
# import pandas


all_points = {'mx': {'normal': {1: 25, 2: 22, 3: 20, 4: 18, 5: 16, 6: 15, 7: 14, 8: 13, 9: 12, 10: 11,
                                11: 10, 12: 9, 13: 8, 14: 7, 15: 6, 16: 5, 17: 4, 18: 3, 19: 2, 20: 1,
                                21: 0, 22: 0, 23: 0, 24: 0, 25: 0, 26: 0, 27: 0, 28: 0, 29: 0, 30: 0,
                                31: 0, 32: 0, 33: 0, 34: 0, 35: 0, 36: 0, 37: 0, 38: 0, 39: 0, 40: 0},
                     'udog': {1: 50, 2: 44, 3: 40, 4: 36, 5: 32, 6: 30, 7: 28, 8: 26, 9: 24, 10: 22,
                              11: 10, 12: 9, 13: 8, 14: 7, 15: 6, 16: 5, 17: 4, 18: 3, 19: 2, 20: 1,
                              21: 0, 22: 0, 23: 0, 24: 0, 25: 0, 26: 0, 27: 0, 28: 0, 29: 0, 30: 0,
                              31: 0, 32: 0, 33: 0, 34: 0, 35: 0, 36: 0, 37: 0, 38: 0, 39: 0, 40: 0}},
              'sx': {'normal': {1: 25, 2: 22, 3: 20, 4: 18, 5: 16, 6: 15, 7: 14, 8: 13, 9: 12, 10: 11,
                                11: 10, 12: 9, 13: 8, 14: 7, 15: 6, 16: 5, 17: 4, 18: 3, 19: 2, 20: 1, 21: 1, 22: 1},
                     'udog': {1: 50, 2: 44, 3: 40, 4: 36, 5: 32, 6: 30, 7: 28, 8: 26, 9: 24, 10: 22,
                              11: 10, 12: 9, 13: 8, 14: 7, 15: 6, 16: 5, 17: 4, 18: 3, 19: 2, 20: 1, 21: 1, 22: 1}}}

# Urls
live_timing_url = "http://live.amasupercross.com/xml/sx/RaceResultsWeb.xml?"
infoUrlSX = "http://live.amasupercross.com/xml/sx/Announcements.json"
urlMX = "http://americanmotocrosslive.com/xml/mx/RaceResultsWeb.xml?"
infoUrlMX = "http://americanmotocrosslive.com/xml/mx/Announcements.json"

# Lists
points = {1: 25, 2: 22, 3: 20, 4: 18, 5: 16, 6: 15, 7: 14, 8: 13, 9: 12, 10: 11,
          11: 10, 12: 9, 13: 8, 14: 7, 15: 6, 16: 5, 17: 4, 18: 3, 19: 2, 20: 1,
          21: 1, 22: 1}

raceCompleteDict = {("250", "1"): False,
                    ("250", "2"): False,
                    ("450", "1"): False,
                    ("450", "2"): False,
                    ("250", "HEAT", "1"): False,
                    ("250", "HEAT", "2"): False,
                    ("250", "LCQ"): False,
                    ("250", "MAIN"): False,
                    ("450", "HEAT", "1"): False,
                    ("450", "HEAT", "2"): False,
                    ("450", "SEMI", "1"): False,
                    ("450", "SEMI", "2"): False,
                    ("450", "LCQ"): False,
                    ("450", "MAIN"): False}

bubbleDict = {('450', 'HEAT'): 4,
              ('450', 'SEMI'): 5,
              ('450', 'LCQ'): 4,
              ('450', 'LAST CHANCE QUALIFIER'): 4,
              ('250', 'HEAT'): 9,
              ('250', 'LCQ'): 4,
              ('250', 'LAST CHANCE QUALIFIER'): 4}

nameReplace = {'@A': 'pos',
               '@F': 'name',
               '@N': 'num',
               '@L': 'laps',
               '@G': 'gap',
               '@D': 'diff',
               '@LL': 'lastlap',
               '@BL': 'bestlap',
               '@S': 'status',
               '@S1': 'seg1',
               '@S2': 'seg2',
               '@S3': 'seg3',
               '@S4': 'seg4'}


class Event:
    def __init__(self, series):
        series_types = ['mx', 'sx']
        if series.lower() not in series_types:
            raise ValueError(f'Invalid series type: "{series}"')
            
        self.series = series.lower()
        self.lt_url = self.get_live_timing_url()
        self.info_url = self.get_event_info_url()
        self.location = None  # Race location/name - 'Washougal'
        self.long_moto_name = None  # '450 Class Moto #2'
        self.moto_num = None  # 1 or 2
        self.division = None
        self.points_dict = all_points[self.series]
        # self.event_status = event_status
        # self.get_live_timing()
        # self.event_info = get_event_info()
        
    def get_event_info_url(self):
        if self.series == 'sx':
            info_url = 'http://live.amasupercross.com/xml/sx/Announcements.json'
        elif self.series == 'mx':
            info_url = 'http://americanmotocrosslive.com/xml/mx/Announcements.json'
        else:
            raise ValueError(f'Invalid series type: {self.series}')
        return info_url

    def get_live_timing_url(self):
        if self.series == 'sx':
            lt_url = 'http://live.amasupercross.com/xml/sx/Announcements.json'
        elif self.series == 'mx':
            lt_url = 'http://americanmotocrosslive.com/xml/mx/Announcements.json'
        else:
            raise ValueError(f'Invalid series type: {self.series}')
        return lt_url

    def get_event_info(self):
        info_url = self.get_event_info_url()
        r = requests.get(info_url)
        info = json.loads(r.text)
        
        self.location = info['T']  # Race location/name - 'Washougal'
        self.long_moto_name = info['S'].split(' (', 1)[0]  # '450 Class Moto #2'
        self.moto_num = int(self.long_moto_name.split('#', 1)[1])
        self.division = self.long_moto_name.split('Class ', 1)[0]
        return info
        
    def get_live_timing(self):
        lt_url = self.get_live_timing_url()
        #obj = untangle.parse(live_timing_url)
        # print(obj)
        #riders = obj.A.B
        #for rider in riders:
        #    print(rider['F'])
        #    print(type(rider))
        r = requests.get(lt_url)
        print(r.text)
        lt_dict = xmltodict.parse(r.text, process_namespaces=True)
        print(lt_dict)

if __name__ == "__main__":
    lt = Event('mx')
    lt.get_event_info()
    print(lt.moto_num)
    print(lt.division)
    print(lt.location)
    print(lt.points_dict)
    lt.get_live_timing()
    
