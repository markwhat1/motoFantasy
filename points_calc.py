import requests
from bs4 import BeautifulSoup

# import pp

# import easygui as eg

points = {1: 25, 2: 22, 3: 20, 4: 18, 5: 16, 6: 15, 7: 14, 8: 13, 9: 12, 10: 11,
          11: 10, 12: 9, 13: 8, 14: 7, 15: 6, 16: 5, 17: 4, 18: 3, 19: 2, 20: 1,
          21: 0, 22: 0, 23: 0, 24: 0, 25: 0, 26: 0, 27: 0, 28: 0, 29: 0, 30: 0,
          31: 0, 32: 0, 33: 0, 34: 0, 35: 0, 36: 0, 37: 0, 38: 0, 39: 0, 40: 0}

mx_url = "http://americanmotocrosslive.com/xml/mx/RaceResultsWeb.xml"
sx_url = ""


def live_timing_pos():
    liveTimingDict = ''
    Global = liveTimingDict
    r = requests.get(mx_url)
    live_timing = BeautifulSoup(r.text, 'html.parser')
    positions = live_timing.find_all('b')
    pos_list = []
    rider_list = []
    for position in positions:  # find each level of the live timing grid
        name = position.get('f')  # rider name
        pos = int(position.get('a'))  # rider position
        # live_timing_dict = '{'names' : 'pos'}'
        pos_list.append(pos)
        rider_list.append(name)
        liveTimingDict = dict(zip(pos_list, rider_list))
    print(liveTimingDict)
    return liveTimingDict

# def pick_riders():
# 	question = 'Please pick your riders:'
# 	title = 'Rider Lists'
# 	listOfOptions = live_timing_pos()
# 	choice = eg.multchoicebox(question, title, listOfOptions)
# 	print(choice)

picked_riders = ['K. Roczen', 'E. Tomac', 'B. Tickle', 'J. Barcia']

live_timing_pos()

"""
for rider in picked_riders:
	if rider in live_timing_pos():
		points = LT_dict.get(rider)
		print(points)
	else:
		print('Nothing works')

"""
# if picked_riders[0] in live_timing_pos():
# 	print('TRUE!')
# else:
# 	print('FALSE!!')


# print(live_timing_pos())


# # riders = soup.findall("b")
# print(json)
# print(riders)
