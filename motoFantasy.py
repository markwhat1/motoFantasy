from collections import OrderedDict

import pandas as pd
import requests
import xmltodict
from lxml import etree

##################
sxSeason = False
##################

if sxSeason is True:
    # Limit points to 22 positions and use the proper XML URL
    points = [25, 22, 20, 18, 16, 15, 14, 13, 12, 11,  # 1-10
              10, 9, 8, 7, 6, 5, 4, 3, 2, 1,  # 11-20
              1, 1]  # 21-22
    udogPoints = [50, 44, 40, 36, 32, 30, 28, 26, 24, 22,  # 1-10, 2x
                  10, 9, 8, 7, 6, 5, 4, 3, 2, 1,  # 11-20
                  1, 1]  # 21-22
    baseURL = 'http://live.amasupercross.com/xml/sx/'
    liveTimingURL = baseURL + 'RaceResultsWeb.xml'
    infoUrl = baseURL + 'Announcements.json'
elif sxSeason is False:
    # Extend points to 40 positions and use the proper XML URL
    points = [25, 22, 20, 18, 16, 15, 14, 13, 12, 11,  # 1-10
              10, 9, 8, 7, 6, 5, 4, 3, 2, 1,  # 11-20
              0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 21-30
              0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # 31-40
    udogPoints = [50, 44, 40, 36, 32, 30, 28, 26, 24, 22,  # 1-10, 2x
                  10, 9, 8, 7, 6, 5, 4, 3, 2, 1,  # 11-20
                  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 21-30
                  0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # 31-40
    baseURL = 'http://americanmotocrosslive.com/xml/mx/'
    liveTimingURL = baseURL + 'RaceResultsWeb.xml'
    infoUrl = baseURL + 'Announcements.json'
else:
    print('What season is it?')


def get_race_info():
    info = requests.get(infoUrl).json()
    raceInfo = info["S"].split(' (', 1)[0]  # '450 Class Moto #2'
    motoNum = raceInfo.split('#', 1)[1]
    motoClass = raceInfo.split(' ', 1)[0]
    raceLocation = info["T"]  # Race location/name - 'Washougal'
    raceDescr = raceInfo + ' at ' + raceLocation
    print(raceDescr)


def live_timing_xml_parse():
    lt_attrs = ['@A', '@N', '@F', '@L', '@G', '@D', '@LL',
                '@BL', '@S', '@S1', '@S2', '@S3', '@S4']
    lt_keys = ['pos', 'num', 'name', 'laps', 'gap', 'diff', 'lastlap',
               'bestlap', 'status', 'seg1', 'seg2', 'seg3', 'seg4']

    tree = etree.parse(liveTimingURL)
    lt_values = []
    for i in range(len(lt_attrs)):
        value = tree.xpath('//A/B/' + lt_attrs[i])
        lt_values.append(value)
    lt_dict = OrderedDict(zip(lt_keys, lt_values))
    df_liveTiming = pd.DataFrame(lt_dict)
    print(df_liveTiming)


def live_timing_update():
    text = requests.get(liveTimingURL).text  # Get XML
    dict_initial = xmltodict.parse(text, dict_constructor=dict)
    dict_final = dict_initial['A']['B']
    correctOrder = ['@A', '@N', '@F', '@L', '@G', '@D', '@LL', '@BL', '@S',
                    '@S1', '@S2', '@S3', '@S4', '@C', '@H', '@I', '@IN', '@LS',
                    '@LT', '@MLT', '@MLTBy', '@MSTLT', '@MSTS1', '@MSTS2',
                    '@MSTS3', '@MSTS4', '@P', '@RM', '@T', '@V']
    nameReplace = {'@A': 'pos', '@F': 'name', '@N': 'num',
                   '@L': 'laps', '@G': 'gap', '@D': 'diff',
                   '@LL': 'lastlap', '@BL': 'bestlap',
                   '@S': 'status', '@S1': 'seg1', '@S2': 'seg2',
                   '@S3': 'seg3', '@S4': 'seg4'}

    df_liveTiming = pd.DataFrame(dict_final, columns=correctOrder)
    df_liveTiming = df_liveTiming.loc[:, '@A':'@S4']
    df_liveTiming.rename(columns=nameReplace, inplace=True)
    print(df_liveTiming)

    # Write to Excel workbook
    path = 'C:\\Users\\mwhatc\\Google Drive\\Spreadsheets\\fantasy motocross\\'
    wb = 'motoFantasy.xlsx'
    writer = pd.ExcelWriter(path + wb)
    df_liveTiming.to_excel(writer, 'liveTimingData')
    writer.save()

    # Select the relevant elements for table
    # keyLetters = ['A', 'F', 'N', 'L', 'G',
    #               'D', 'LL', 'BL', 'S']
    # keyValues = ['pos', 'name', 'num', 'laps', 'gap',
    #              'diff', 'lastlap', 'bestlap', 'status']



    # Output the results
    # if df_liveTiming.empty:
    #     Range('liveTimingData', 'A1').value = "Error in data collection"
    # else:
    #     Range('liveTimingData', 'A1').options(index=True).value = df_liveTiming
    # return df_liveTiming


# def autoLiveTiming():
#     schedule.every(10).seconds.do(live_timing_update)
#     while 1:
#         schedule.run_pending()
#         time.sleep(1)

# get_race_info()
live_timing_xml_parse()

# live_timing_update()

# if __name__ == '__main__':
#     # To run from Python, not needed when called from Excel.
#     # Expects the Excel file next to this source file, adjust accordingly.
#     # path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'myfile.xlsm'))
#     path = 'C:\\Users\\mwhatc\\Google Drive\\Spreadsheets\\fantasy motocross\\'
#     Workbook.set_mock_caller(path + 'motoFantasy.xlsm')
#     live_timing_update()
