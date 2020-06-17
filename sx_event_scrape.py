import requests
import pandas as pd


RACE_NUM = 15

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

for key, value in event_urls.items():
    event_urls[key] = value.replace('XXXXX', f'S{str(2000 + (RACE_NUM * 5))}')


def check_current_race():
    RACE_COMPLETE = True
    while RACE_COMPLETE = True:

        
        for k, v in event_urls.items():
            r = requests.get(v)


r = requests.get(event_urls.get('250 Main Event'))

if "Page Not Found"
print(r.status_code)

# tables = pd.read_html(r.text)
# print(tables[0])
