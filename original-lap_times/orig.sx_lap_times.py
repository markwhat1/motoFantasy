#http://live.amasupercross.com/xml/sx/RaceResults.json?

import urllib2
import twitter
import time
import pandas as pd
import itertools
import random
import config
import json
import re
from xml.etree import cElementTree as ET

tweetThis = True

topXDict = {0 : 10, 10 : 5, 15 : 3}
positionsToTweet = 22
maxNRAttempts = 190
sleepTime = random.randint(12,16)
exitCount = 0
lastLap = "0"

raceComplete = False

raceStrings = ['MAIN','HEAT', 'LCQ', 'SEMI', 'LAST CHANCE QUALIFIER', 'MOTO']  #Last Chance Qualifier

url = "http://live.amasupercross.com/xml/sx/RaceResultsWeb.xml?"
infoUrl = "http://live.amasupercross.com/xml/sx/Announcements.json"

bubbleDict = {('450','HEAT') : 4, ('450','SEMI') : 5, ('450','LAST CHANCE QUALIFIER') : 4,
              ('250','HEAT') : 9, ('250', 'LAST CHANCE QUALIFIER') : 4, ('450', 'LCQ') : 4, ('250', 'LCQ') : 4}


tweet_names_on_laps = [1,5,10,15,20]

def get_event_info(event):
    class_name_pattern = re.compile("\d{3}")
    class_name_list = class_name_pattern.findall(event)
    if len(class_name_list) > 0:
        class_name = str(class_name_list[0])
    else:
        class_name = None

    event_name = matchInList(event)

    event_number_pattern = re.compile("(\#\d{1}|\s\d{1})")

    event_number_list = event_number_pattern.findall(event)
    if len(event_number_list) > 0:
        if len(event_number_list[0]) == 2 : event_number = event_number_list[0][1]
    else:
        event_number = None
    return class_name, event_name, event_number


def matchInList(string):

    #matching_list = [i for i, x in enumerate(raceStrings) if x in string.upper()]
    matching_list = [s for s in raceStrings if s in string.upper()]   #[s for s in some_list if "abc" in s]

    if matching_list:
        return matching_list[0]

    return None


def getLapTimes():

    tweets = []
    global lastLap
    global positionsToTweet
    global raceComplete

    try:
        data = urllib2.urlopen(infoUrl, timeout=3)
    except urllib2.URLError, e:
        return e, None
    try:
        event_header = json.loads(data.read())
        class_name, event_name, event_number = get_event_info(event_header["S"].upper())

        if not event_name:  #checking to see if we care about this event
            return "Not Ready", None

    except Exception as e:
        return e, None

    try:
        raceData = urllib2.urlopen(url, timeout=3)
    except urllib2.URLError, e:
        return e, None

    try:
        tree = ET.parse(raceData)
        root = tree.getroot()

        riders = root.findall("./B")
        #Lap = str(riders[0].attrib['L']).strip()

        lenghtOfAnnouncements = len(event_header["B"])
        lastAnnoucement = event_header["B"][lenghtOfAnnouncements-1]["M"]

        if lastAnnoucement.find("Session Complete") > -1 and not raceComplete:
            raceComplete = True
            tweet = "Checkers "

            if event_name != "MAIN":
                bubblePos = bubbleDict.get((class_name, event_name),-1)
                riders[bubblePos-1].attrib['N'] = "(" + riders[bubblePos-1].attrib['N'] + ")"
                tweets.append(getROTweet(tweet, riders, positionsToTweet,bubblePos))
                #tweets.append(tweet)

                #riders[bubblePos-1].attrib['F'] = "(" + riders[bubblePos-1].attrib['F'] + ")"
                tweets.append(tweet + getRO(riders, "F", bubblePos))
            else:
                tweets.append(getROTweet(tweet, riders, positionsToTweet,3))
                tweets.append(tweet + getRO(riders, "F", 10))

            return 'OK', tweets

        elif lastAnnoucement.find("Session Complete") > -1:
            return "Not Ready", None
        else:
            Lap = str(riders[0].attrib['L']).strip()
            tweet = 'L' + Lap + "  "

        if raceComplete: raceComplete = False

        #are we still on the same lap the last time we tweeted
        if  Lap == lastLap:
            return "Not Ready", None

        #Have we completed a lap yet
        gapTest = riders[1].attrib['G']
        if gapTest == '--.---' or gapTest == '00.000' or gapTest == '-.---' or gapTest == '0.000' or Lap == '0':
            return 'Not Ready', None

        #riders that are currently on the lead lap
        ridersOnLeadLap = list(itertools.takewhile(lambda x: x.attrib['G'].find('ap') == -1, riders))

        #get how many 'spaced' riders will be tweeted based on the current lap number
        topX = getTopX(int(Lap))

        #Check to see if we have enough riders on the same lead lap to tweet
        if len(ridersOnLeadLap) < topX:
            return 'Not Ready', None

        if event_name != "MAIN": #if we are in a qualifying race
            bubblePos = bubbleDict.get((class_name, event_name),-1)
            riders[bubblePos-1].attrib['N'] = "(" + riders[bubblePos-1].attrib['N'] + ")"

        tweet = getROTweet(tweet, riders, positionsToTweet, topX)
        tweets.append(tweet)

        if int(Lap) in tweet_names_on_laps:
            if event_name != "MAIN":
                bubblePos = bubbleDict.get((class_name, event_name),-1)
                #riders[bubblePos-1].attrib['F'] = "(" + riders[bubblePos-1].attrib['F'] + ")"
                tweets.append(getRO(riders, "F", bubblePos))
            else:
                tweets.append(getRO(riders, "F", 10))

        lastLap = Lap

        return 'OK', tweets

    except Exception as e:
        return e, None


def getROTweet(tweet, riders, positionsToTweet, topX):

     #in MX we can't tweet all the racers and in SX we need to make sure we have at least X
    if len(riders) < positionsToTweet:
        positionsToTweet = len(riders)

    for x in range(positionsToTweet):
        if x == 0: #if this is the first place rider then no spaces are necessary
            tweet = tweet + riders[x].attrib['N']
        else:
            if x < topX: #add gap spaces to these riders
                spaceCount = int(getTime(riders[x].attrib['G'])) + 1 #getTime() does a rough calculation of gaps and returns a 'space count'
                tweet = tweet + "_" * spaceCount
                tweet = tweet + riders[x].attrib['N']
            else: #these rider are outside of the topX so we just put them in order and separate them by '-'
                if x == topX:
                    tweet = tweet + ' | ' + riders[x].attrib['N']
                else:
                    tweet = tweet + '-' + riders[x].attrib['N']


    #Shorten the lap tweet if needed.
    if len(tweet) > 140:
        tweet = tweet[:137] + '...'

    return tweet


def getTopX(lap):
    for k in topXDict:
        if lap > k:
            lapKey = k
    return topXDict[lapKey]


def getTime(t):

    colonPos = t.find(':')

    if colonPos > -1:
        timeSplit = t.split(':')
        return int(timeSplit[0]) * 60 + float(timeSplit[1])
    elif t.find('lap') > -1:
        return -1
    else:
        return float(t)

def stringBetweenTwoChars(string, char1, char2):
    stringList = []
    for x in range(0,len(string)):
        if string[x] == char1:
            char2Pos = string[x:].find(char2)
            newString = string[x + 1:(x + char2Pos)]
            stringList.append(newString)

    return stringList


def findSameNames(riders):

    names = []
    sameNames = []

    for rider in riders:
        if rider.attrib["F"][3:] in names:
            sameNames.append(rider.attrib["F"][3:])
        names.append(rider.attrib["F"][3:])

    return sameNames

def getRO(riders, riderAtt, topX, tweetPos=True, posSep="-", sep="__"):

    tweet = ""

    if riderAtt == "F":
        sameNames = findSameNames(riders)

    for x in range(topX):
        rider = riders[x].attrib[riderAtt]
        if riderAtt == "F":
            rider = rider.replace(". ", "")
            #if rider[1:] not in sameNames:
                #rider = rider[1:]

        if tweetPos:
            temp =  "P" + str(x + 1) + posSep + rider + sep
        else:
            temp = rider + sep
        tweet+= temp

    return tweet[:-len(sep)]

if __name__ == '__main__':

    if tweetThis == True:
        #the necessary twitter authentification
        my_auth = twitter.OAuth(config.twitter["token"], config.twitter["token_secret"], config.twitter["consumer_key"], config.twitter["consumer_secret"])
        twit = twitter.Twitter(auth=my_auth)

    while True:
        print "Trying..."
        status, tweets = getLapTimes()

        #exit()

        if status == 'OK':
            exitCount = 0
            print tweets
            if tweetThis == True:
                for tweet in tweets:
                    print 'tweeting - ' + tweet
                    twit.statuses.update(status=tweet) #Lap Times Tweet
        else:
            exitCount = exitCount + 1
            print 'Exit Count is ' + str(exitCount) + ' out of ' + str(maxNRAttempts)

        #exitCount keeps track of the number of times that getLapTimes() returns 'Not Ready'
        #This will stop the script when it exceeds maxNRAttempts
        if exitCount > maxNRAttempts:
            exit()

        print status

        sleepTime = random.randint(12,16)
        print 'Sleeping for ' + str(sleepTime) + ' seconds'
        time.sleep(sleepTime) #puts the app to sleep for a predetermined amount of time