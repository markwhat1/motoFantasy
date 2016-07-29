# http://live.amasupercross.com/xml/sx/RaceResults.json?

import urllib.request, urllib.error, urllib.parse
import twitter
import time
import pandas as pd
import itertools
import random
import config
import json
import re
from xml.etree import cElementTree as ET

MX = False  #for MX and SX mode
tweetThis = False

topXDict = {0 : 10, 10 : 5, 15 : 3}
positionsToTweet = 22
maxNRAttempts = 190
sleepTime = random.randint(12,16)
exitCount = 0
lastLap = "0"

raceComplete = False

raceStrings = ['MAIN','HEAT','MOTO', 'LCQ', 'SEMI', 'LAST CHANCE QUALIFIER']  #Last Chance Qualifier
#raceCompleteDict = {("250","1") : False, ("250","2") : False, ("450","1") : False, ("450","2") : False}
raceCompleteDict = {("250","1") : False, ("250","2") : False, ("450","1") : False, ("450","2") : False,
                ("250", "HEAT", "1") : False, ("250", "HEAT", "2") : False, ("250", "LCQ") : False,
                ("250", "MAIN") : False,  ("450", "HEAT", "1") : False, ("450", "HEAT", "2") : False,
                ("450", "SEMI", "1") : False, ("450", "SEMI", "2") : False, ("450", "LCQ") : False,
                ("450", "MAIN") : False}

if MX:
    url = "http://americanmotocrosslive.com/xml/mx/RaceResultsWeb.xml?"
    infoUrl = "http://americanmotocrosslive.com/xml/mx/Announcements.json"
    points = { 1 : 25, 2 : 22, 3 : 20, 4 : 18, 5 : 16, 6 : 15, 7 : 14, 8 : 13, 9 : 12, 10 : 11,
           11 : 10, 12 : 9, 13 : 8, 14 : 7, 15 : 6, 16 : 5, 17 : 4, 18 : 3, 19 : 2, 20 : 1}

else:
    url = "http://live.amasupercross.com/xml/sx/RaceResultsWeb.xml?"
    infoUrl = "http://live.amasupercross.com/xml/sx/Announcements.json"

    bubbleDict = {('450','HEAT') : 4, ('450','SEMI') : 5, ('450','LAST CHANCE QUALIFIER') : 4,
                  ('250','HEAT') : 9, ('250', 'LAST CHANCE QUALIFIER') : 4, ('450', 'LCQ') : 4, ('250', 'LCQ') : 4}



def getLapTimes():

    tweets = []
    global lastLap
    global positionsToTweet
    global raceComplete

    try:
        data = urllib.request.urlopen(infoUrl, timeout=3)
    except urllib.error.URLError as e:
        return e, None
    try:
        d = json.loads(data.read())
        raceDesc = d["S"].upper()
        if not any(substring in raceDesc for substring in raceStrings):  #checking to see if we are racing
            return "Not Ready", None

        #Check to see if this race is in the raceCompleteDict dict

    except Exception as e:
        return e, None

    try:
        raceData = urllib.request.urlopen(url, timeout=3)
    except urllib.error.URLError as e:
        return e, None

    try:
        #tree = xml.etree.cElementTree.parse(raceData)
        tree = ET.parse(raceData)
        root = tree.getroot()

        riders = root.findall("./B")

        #check to see if we are on a new lap
        Lap = str(riders[0].attrib['L']).strip()
        pattern = re.compile("\d{3}")
        className = str(pattern.findall(raceDesc)[0])



        if MX:
            #pattern = re.compile("\s[1-2]{1}")
            #moto = str(pattern.findall(raceDesc)[0]).strip()

            pattern = re.compile("[\s|#][1-2]{1}")
            moto = str(pattern.findall(raceDesc)[0]).strip()

            if moto.startswith("#"):
                moto = moto[1]

            print("This is moto " + moto)
            
            #raceComplete = raceCompleteDict[(className, moto)]
        else:
            moto = 0 #hack
            if raceDesc.find("MAIN") == -1: #if we are in a qualifying race
                racePos = matchInList(raceDesc)  #need to know if this is a semi or a heat or ? in order to know the bubble position
                print(("cn = " + str(className)))
                print(("rp = " + str(racePos)))
                print(("rs = " + str(raceStrings[racePos])))
                bubblePos = bubbleDict.get((className,raceStrings[racePos]),-1)
                print(("bp = " + str(bubblePos)))
            else:
                bubblePos = 50

        lenghtOfAnnouncements = len(d["B"])
        lastAnnoucement = d["B"][lenghtOfAnnouncements-1]["M"]
        
        

        if lastAnnoucement.find("Session Complete") > -1 and not raceComplete:#Dict[(className, moto)]:

            if MX and moto == '1':
                saveTopX(riders, className)

            #raceCompleteDict[(className, moto)] = True
            raceComplete = True
            tweet = "Checkers "
            tweet = getROTweet(tweet, riders, positionsToTweet,3)
            tweets.append(tweet)

            if MX and moto == "2":
                oaTweet = "Checkers " + getOATweet(riders, className)

                if len(oaTweet) > 140:
                    oaTweet = oaTweet[:137] + '...'

                tweets.append(oaTweet)

            return 'OK', tweets

        elif lastAnnoucement.find("Session Complete") > -1:
            return "Not Ready", None
        else:
            tweet = 'L' + Lap + "  "

        if raceComplete: raceComplete = False

        if  Lap == lastLap:# and not raceCompleteDict[(className, moto)]:
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

        tweet = getROTweet(tweet, riders, positionsToTweet, topX, bubblePos)
        tweets.append(tweet)

        #if this is MX and moto 2 then we can start the OA tweets
        if MX and moto == '2':
            oaTweet = 'L' + Lap + getOATweet(riders, className)

            if len(oaTweet) > 140:
                oaTweet = oaTweet[:137] + '...'

            tweets.append(oaTweet)

        lastLap = Lap

        #if lastAnnoucement.find("Session Complete") > -1:
        #    raceCompleteDict[(className, moto)] = True

        return 'OK', tweets

    except Exception as e:
        return e, None


def getROTweet(tweet, riders, positionsToTweet, topX, bubblePos=40):
     #in MX we can't tweet all the racers and in SX we need to make sure we have at least X
    if len(riders) < positionsToTweet:
        positionsToTweet = len(riders)

    for x in range(positionsToTweet):
        if x == 0: #if this is the first placed rider then no spaces are necessary
            tweet = tweet + riders[x].attrib['N']
        else:
            if x < topX: #add gap spaces to these riders
                spaceCount = int(getTime(riders[x].attrib['G'])) + 1 #getTime() does a rough calculation of gaps and returns a 'space count'
                tweet = tweet + "_" * spaceCount
                if not MX and x == (bubblePos - 1):
                    tweet = tweet + '*' + riders[x].attrib['N']
                else:
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


def matchInList(header):

    race = "HEAT" #str(header[2])
    racePosList = [i for i, x in enumerate(raceStrings) if x in race.upper()]

    if racePosList:
        return racePosList[0]
    return -1


def getOATweet(riders, motoClass):

    print('Getting OA Tweet for the ' + motoClass + ' class')

    topX = len(riders)

    d = getMotoOne(motoClass)
    print('Got Moto One results')

    df = pd.DataFrame(columns=('riderNum', 'Points', 'MotoTwoPos'))

    for x in range(0,topX):

        try:
            motoOnePoints = int(d[riders[x].attrib['N']])
        except:
            motoOnePoints = 0
            pass


        motoTwoPoints = points.get(x+1,0)
        df.loc[x] = [riders[x].attrib['N'], (motoOnePoints + motoTwoPoints), (x + 1)]

    df = df.sort_index(by=['Points','MotoTwoPos'], ascending=[False,True])
    df = df.reset_index()

    oaTweet = ' OA '

    for x in range(0,10):
        oaTweet +=  '(' + str((x + 1)) + ')' + df.ix[x].riderNum + '__'

    return oaTweet[:len(oaTweet) - 2]


def getMotoOne(className):

    d = {}

    filePath = "/home/haffner/lap/" + className
    with open(filePath) as f:
        for line in f:
            (key, val) = line.split(',')
            d[key] = val

    return d


def saveTopX(riders, className):

    print(className)

    topX = len(riders)

    filePath = "/home/haffner/lap/" + className
    file = open(filePath, "w")

    for x in range(0,topX):
        file.write(riders[x].attrib['N'] + ',' + str(points.get(x+1,0)) + '\n')


    file.close()

    print('Done with save')


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

if __name__ == '__main__':

    if tweetThis == True:
        #the necessary twitter authentification
        my_auth = twitter.OAuth(config.twitter["token"], config.twitter["token_secret"], config.twitter["consumer_key"], config.twitter["consumer_secret"])
        twit = twitter.Twitter(auth=my_auth)

    while True:
        print("Trying...")
        status, tweets = getLapTimes()

        #exit()

        if status == 'OK':
            exitCount = 0
            print(tweets)
            if tweetThis == True:
                for tweet in tweets:
                    print('tweeting - ' + tweet)
                    twit.statuses.update(status=tweet) #Lap Times Tweet
        else:
            exitCount = exitCount + 1
            print('Exit Count is ' + str(exitCount) + ' out of ' + str(maxNRAttempts))

        #exitCount keeps track of the number of times that getLapTimes() returns 'Not Ready'
        #This will stop the script when it exceeds maxNRAttempts
        if exitCount > maxNRAttempts:
            exit()

        print(status)

        sleepTime = random.randint(12,16)
        print('Sleeping for ' + str(sleepTime) + ' seconds')
        time.sleep(sleepTime) #puts the app to sleep for a predetermined amount of time