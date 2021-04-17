#! /usr/bin/env python3

#   SimonDaNinja/youtube_rss - a set of tools for supporting development
#   of anonymous RSS-based YouTube client applications

#   Copyright (C) 2021  Simon Liljestrand

#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.

#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.

#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

#   Contact by email: simon@simonssoffa.xyz

from html.parser import HTMLParser
import requests as req
import re
import feedparser
import json
import curses
import socket
try:
    from tor_requests.tor_requests import getHttpResponseUsingSocks5
    from tor_requests.tor_requests import generateNewSocks5Auth
except:
    print("you probably haven't run the command\ngit submodule update --init --recursive")
    exit()
import subprocess
import os
import time

#############
# constants #
#############

HOME = os.environ.get('HOME')
YOUTUBE_RSS_DIR = '/'.join([HOME,'.youtube_rss'])
DATABASE_PATH  = '/'.join([YOUTUBE_RSS_DIR, 'database'])

HIGHLIGHTED = 1
NOT_HIGHLIGHTED = 2

###########
# classes #
###########

# parser classes #

# Parser used for extracting an RSS Address from channel page HTML
class RssAddressParser(HTMLParser):

    def __init__(self):
        super(RssAddressParser, self).__init__(convert_charrefs=True)
        self.rssAddress = None

    def handle_starttag(self, tag, attrs):
        attrDict = dict(attrs)
        if 'type' in attrDict and attrDict['type'] == 'application/rss+xml':
            self.rssAddress = attrDict['href']

# Parser used for extracting information about channels from YouTube channel query HTML
class ChannelQueryParser(HTMLParser):

    def __init__(self):
        super(ChannelQueryParser, self).__init__(convert_charrefs=True)
        self.isScriptTag = False
        self.resultList = None

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.isScriptTag = True

    def handle_data(self, data):
        if self.isScriptTag:
            self.isScriptTag = False
            if 'var ytInitialData' in data:
                pattern = re.compile('"channelRenderer":\{"channelId":"([^"]+)",' + \
                        '"title":\{"simpleText":"([^"]+)"')
                tupleList = pattern.findall(data)
                resultList = []
                for tup in tupleList:
                    resultList.append(ChannelQueryObject(channelId = tup[0], 
                        title = tup[1]))
                self.resultList = resultList

# Parser used for extracting information about channels from YouTube channel query HTML
class VideoQueryParser(HTMLParser):

    def __init__(self):
        super(VideoQueryParser, self).__init__(convert_charrefs=True)
        self.isScriptTag = False
        self.resultList = None

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.isScriptTag = True

    def handle_data(self, data):
        if self.isScriptTag:
            self.isScriptTag = False
            if 'var ytInitialData' in data:
                pattern = re.compile('videoId":"([^"]+)","thumbnail":\{"thumbnails":' + \
                        '\[\{"url":"[^"]+","width":[0-9]+,"height":[0-9]+\},\{"url"' + \
                        ':"[^"]+","width":[0-9]+,"height":[0-9]+\}\]\},"title":\{' + \
                        '"runs":\[\{"text":"[^"]+"\}\],"accessibility":\{' + \
                        '"accessibilityData":\{"label":"([^"]+)"\}')
                tupleList = pattern.findall(data)
                resultList = []
                for tup in tupleList:
                    resultList.append(VideoQueryObject(videoId = tup[0], title = tup[1]))
                self.resultList = resultList

# other classes #

class VideoQueryObject:
    def __init__(self, videoId = None, title = None):
        self.videoId   = videoId
        self.title     = title
        if videoId is not None:
            self.url = f"http://youtube.com/watch?v={videoId}"
        else:
            self.url = None

    def __str__(self):
        return f"{self.title}"

class ChannelQueryObject:
    def __init__(self, channelId = None, title = None):
        self.channelId = channelId
        self.title     = title

    def __str__(self):
        return f"{self.title}  --  (channel ID {self.channelId})"

class CircuitManager:
    def __init__(self, nCircuits = 15, ttl = 600):
        self.ttl = ttl
        self.nCircuits = 15
        self.i = 0
        self.expiryTime = None
        self.initiateCircuitAuths()

    def initiateCircuitAuths(self):
        self.circuitAuths=[generateNewSocks5Auth() for i in range(self.nCircuits)]

    def getAuth(self):
        # if circuits have never been used, start ttl timer
        if self.expiryTime is None:
            self.expiryTime = time.time() + self.ttl
        # if ttl is over, reinitiate circuit auth list
        elif self.expiryTime < time.time():
            self.initiateCircuitAuths()
            self.expiryTime = time.time() + self.ttl
        # circulate over the various auths so that you don't use the same circuit all the
        # time
        self.i += 1
        return self.circuitAuths[self.i%self.nCircuits]

class MethodMenuDecision:
    def __init__(self, string, function, *args, **kwargs):
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.string = string

    def __str__(self):
        return self.string

    def executeDecision(self):
        return self.function(*self.args, **self.kwargs)

class ReturnFromMenu:
    pass

class QueryStyle:
    pass

class IndexQuery(QueryStyle):
    pass

class ItemQuery(QueryStyle):
    pass

class CombinedQuery(QueryStyle):
    pass

class UnknownQueryStyle(Exception):
    pass


#############
# functions #
#############

"""
Functions for presentation
"""

def doMethodMenu(query, menuOptions):
    index = 0
    try:
        while True:
            methodMenuDecision, index = doSelectionQuery(query, menuOptions, 
                    initialIndex=index, queryStyle=CombinedQuery)
            try:
                result = methodMenuDecision.executeDecision()
            except KeyboardInterrupt:
                result = None
                pass
            if result is ReturnFromMenu:
                return
    except KeyboardInterrupt:
        return

def doReturnFromMenu():
    return ReturnFromMenu

def doWaitScreen(message, waitFunction, *args, **kwargs):
    return curses.wrapper(doWaitScreenNcurses, message, waitFunction, *args, **kwargs)

def doWaitScreenNcurses(stdscr, message, waitFunction, *args, **kwargs):
    curses.curs_set(0)
    curses.init_pair(HIGHLIGHTED, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(NOT_HIGHLIGHTED, curses.COLOR_WHITE, curses.COLOR_BLACK)
    printMenu(message, [], stdscr, 0, showItemNumber=False)
    return waitFunction(*args, **kwargs)

def doYesNoQuery(query):
    return curses.wrapper(doYnQueryNcurses, query)

def doYnQueryNcurses(stdscr, query):
    choiceIndex = 0
    return doSelectionQueryNcurses(stdscr, query, ['yes','no'], showItemNumber=False)=='yes'

def doSelectionQuery(query, options, queryStyle=ItemQuery, initialIndex=None,
        showItemNumber=True):
    return curses.wrapper(doSelectionQueryNcurses, query, options, 
            queryStyle=queryStyle, initialIndex=initialIndex,
            showItemNumber=showItemNumber)

def doSelectionQueryNcurses(stdscr, query, options, queryStyle=ItemQuery, 
        initialIndex=None, showItemNumber=True):
    curses.curs_set(0)
    curses.init_pair(HIGHLIGHTED, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(NOT_HIGHLIGHTED, curses.COLOR_WHITE, curses.COLOR_BLACK)
    jumpNumList = []
    if initialIndex is not None:
        choiceIndex = initialIndex
    else:
        choiceIndex = 0
    while True:
        printMenu(query, options, stdscr, choiceIndex, showItemNumber=showItemNumber,
                jumpNumStr = ''.join(jumpNumList))
        key = stdscr.getch()
        if key == curses.KEY_UP:
            jumpNumList = []
            choiceIndex = (choiceIndex-1)%len(options)
        elif key == curses.KEY_DOWN:
            jumpNumList = []
            choiceIndex = (choiceIndex+1)%len(options)
        elif key in [ord(digit) for digit in '1234567890']:
            if len(jumpNumList) < 6:
                jumpNumList.append(chr(key))
        elif key == curses.KEY_BACKSPACE:
            if jumpNumList:
                jumpNumList.pop()
        elif key in [curses.KEY_ENTER, 10, 13]:
            if jumpNumList:
                jumpNum = int(''.join(jumpNumList))
                choiceIndex = min(jumpNum-1, len(options)-1)
                jumpNumList = []
            elif queryStyle is ItemQuery:
                return options[choiceIndex]
            elif queryStyle is IndexQuery:
                return choiceIndex
            elif queryStyle is CombinedQuery:
                return options[choiceIndex], choiceIndex
            else:
                raise UnknownQueryStyle
    
def doNotify(message):
    doSelectionQuery(message, ['ok'], showItemNumber=False)

def doGetUserInput(query, maxInputLength=40):
    return curses.wrapper(doGetUserInputNcurses, query, maxInputLength=maxInputLength)

def doGetUserInputNcurses(stdscr, query, maxInputLength=40):
    curses.curs_set(0)
    curses.init_pair(HIGHLIGHTED, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(NOT_HIGHLIGHTED, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.curs_set(0)
    validChars = [ord(letter) for letter in \
            'qwertyuiopasdfghjklzxcvbnmåäöQWERTYUIOPASDFGHJKLZXCVBNMÅÄÖ1234567890 _+']
    userInputChars = []
    while True:
        printMenu(query, [''.join(userInputChars)], stdscr, 0,
                xAlignment=maxInputLength//2, showItemNumber=False)
        key = stdscr.getch()
        if key == curses.KEY_BACKSPACE:
            if userInputChars: userInputChars.pop()
        elif key in [curses.KEY_ENTER, 10, 13]:
            return ''.join(userInputChars)
        elif key in validChars and len(userInputChars) < maxInputLength:
            userInputChars.append(chr(key))

def printMenu(query, menu, stdscr, choiceIndex, xAlignment=None, showItemNumber=True, jumpNumStr=''):
    stdscr.clear()
    height, width = stdscr.getmaxyx()
    screenCenterX = width//2
    screenCenterY = height//2
    nRowsToPrint = (len(menu)+2)

    if xAlignment is not None:
        itemX = max(min(screenCenterX - xAlignment, width-2),0)
    elif menu:
        menuWidth = max([len(f"{i+1}: {item}" if showItemNumber else str(item)) for i, 
            item in enumerate(menu)])
        itemX = max(screenCenterX - menuWidth//2, 0)
    else:
        itemX = None
    
    if itemX != 0 and itemX is not None:
        itemX = max(min(itemX, width-2),0)

    jumpNumStr = jumpNumStr[:max(min(len(jumpNumStr), width-1),0)]
    if jumpNumStr:
        stdscr.addstr(0,0,jumpNumStr)

    offset = 0
    titleY = screenCenterY-nRowsToPrint//2
    if nRowsToPrint >= height-2:
        yTitleTheoretical = screenCenterY - nRowsToPrint//2
        ySelectedTheoretical = (yTitleTheoretical + 2 + choiceIndex)
        offset = max(ySelectedTheoretical-screenCenterY, yTitleTheoretical)
    titleY -= offset

    titleX = max(screenCenterX-(len(query)//2),0)
    if titleX != 0:
        titleX = max(min(abs(titleX), width)*(titleX//abs(titleX)),0)
    if len(query) >= width-1:
        query = query[0:width-1]
    if titleY >= 0 and titleY<height-1:
        stdscr.addstr(titleY, titleX, query)
    for i, item in enumerate(menu):
        itemString = f"{i+1}: {item}" if showItemNumber else str(item)
        if itemX + len(itemString) >= width-1:
            itemString = itemString[:max((width-itemX-2),0)]
        attr = curses.color_pair(HIGHLIGHTED if i == choiceIndex else NOT_HIGHLIGHTED)
        stdscr.attron(attr)
        itemY = screenCenterY - nRowsToPrint//2 + i + 2 - offset
        if itemY >= 0 and itemY < height-1 and itemString:
            stdscr.addstr(itemY, itemX, itemString)
        stdscr.attroff(attr)
    stdscr.refresh()

"""
Functions for retreiving and processing network data
"""

# use this function to escape a YouTube query for the query URL
# TODO: implement this function more properly
def escapeQuery(query):
    query = query.replace('+', '%2B')
    query = query.replace(' ', '+')
    return query

def unProxiedGetHttpContent(url, session=None, method = 'GET', postPayload = {}):
    if session is None:
        if method == 'GET':
            return req.get(url)
        elif method == 'POST':
            return reg.post(url, postPayload)
    else:
        if method == 'GET':
            return session.get(url)
        elif method == 'POST':
            return session.post(url, postPayload)

def getYouTubeHtml(url, useTor, circuitManager):
    session = req.Session()
    session.headers['Accept-Language']='en-US'
    # This cookie lets us avoid the YouTube consent page
    session.cookies['CONSENT']='YES+'
    if useTor:
        socks5Username, socks5Password = circuitManager.getAuth()
        response = getHttpResponseUsingSocks5(url, session=session, 
                username=socks5Username, password=socks5Password)
    else:
        response = unProxiedGetHttpContent(url, session=session)

    return response.text

# if you have a channel url, you can use this function to extract the rss address
def getRssAddressFromChannelUrl(url, useTor=False):
    try:
        response = getYouTubeHtml(url, useTor=useTor)
    except req.exceptions.ConnectionError:
        return None
    if response.text is not None:
        htmlContent = response.text
        parser = RssAddressParser()
        parser.feed(htmlContent)
        return parser.rssAddress
    else:
        return None

# if you have a channel id, you can use this function to get the rss address
def getRssAddressFromChannelId(channelId):
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channelId}"

# use this function to get query results from searching for a channel
def getChannelQueryResults(query, useTor=False, circuitManager=None):
    url = 'https://youtube.com/results?search_query=' + escapeQuery(query) + \
            '&sp=EgIQAg%253D%253D'
    htmlContent = getYouTubeHtml(url, useTor=useTor, circuitManager=circuitManager)
    parser = ChannelQueryParser()
    parser.feed(htmlContent)
    return parser.resultList

# use this function to get query results from searching for a video
def getVideoQueryResults(query, useTor=False, circuitManager=None):
    url = 'https://youtube.com/results?search_query=' + escapeQuery(query) + \
            '&sp=EgIQAQ%253D%253D'
    htmlContent = getYouTubeHtml(url, useTor=useTor, circuitManager=circuitManager)
    parser = VideoQueryParser()
    parser.feed(htmlContent)
    return parser.resultList

# use this function to get rss entries from channel id
def getRssEntriesFromChannelId(channelId, useTor=False, circuitManager=None):
    rssAddress = getRssAddressFromChannelId(channelId)
    rssContent = getYouTubeHtml(rssAddress, useTor, circuitManager=circuitManager)
    entries = feedparser.parse(rssContent)['entries']
    return entries

def initiateYouTubeRssDatabase():
    database = {}
    database['feeds'] = {}
    database['id to title'] = {}
    database['title to id'] = {}
    return database

def addSubscriptionToDatabase(database, channelId, channelTitle, refresh=False,
        useTor=False, circuitManager=None):
    database['feeds'][channelId] = []
    database['id to title'][channelId] = channelTitle
    database['title to id'][channelTitle] = channelId
    if refresh:
        refreshSubscriptionsByChannelId([channelId], database, useTor=useTor, 
                circuitManager=circuitManager)

def removeSubscriptionFromDatabaseByChannelTitle(database, channelTitle):
    if channelTitle not in database['title to id']:
        return ReturnFromMenu
    channelId = database['title to id'][channelTitle]
    removeSubscriptionFromDatabaseByChannelId(database, channelId)
    return ReturnFromMenu

def removeSubscriptionFromDatabaseByChannelId(database, channelId):
    if channelId not in database['id to title']:
        return
    channelTitle = database['id to title'].pop(channelId)
    database['title to id'].pop(channelTitle)
    database['feeds'].pop(channelId)
    outputDatabaseToFile(database, DATABASE_PATH)


def refreshSubscriptionsByChannelId(channelIdList, database, useTor=False, 
        circuitManager=None):
    localFeeds = database['feeds']
    for channelId in channelIdList:
        localFeed = localFeeds[channelId]
        remoteFeed = getRssEntriesFromChannelId(channelId, useTor=useTor, 
                circuitManager=circuitManager)
        if remoteFeed is not None:
            remoteFeed.reverse()
            for entry in remoteFeed:
                filteredEntry = getRelevantDictFromFeedParserDict(entry)
                filteredEntryIsNew = True
                for localEntry in localFeed:
                    if compareFeedDicts(localEntry, filteredEntry):
                        filteredEntryIsNew = False
                        break
                if filteredEntryIsNew:
                    localFeed.insert(0, filteredEntry)
            return True
        else:
            return False
    return True

def openUrlInMpv(url, useTor=False, maxResolution=1080):
    try:
        command = []
        if useTor:
            command.append('torsocks')
            command.append('-i')
        command += ['mpv', \
                f'--ytdl-format=bestvideo[height=?{maxResolution}]+bestaudio/best']
        command.append(url)
        mpvProcess = subprocess.Popen(command, stdout = subprocess.DEVNULL, 
                stderr = subprocess.STDOUT)
        mpvProcess.wait()
        result = mpvProcess.poll()
    except KeyboardInterrupt:
        mpvProcess.kill()
        mpvProcess.wait()
        result = -1
    return result == 0

def compareFeedDicts(lhs,rhs):
    return lhs['id'] == rhs['id']

def getRelevantDictFromFeedParserDict(feedparserDict):
    outputDict =    {
                        'id'        : feedparserDict['id'],
                        'link'      : feedparserDict['link'],
                        'title'     : feedparserDict['title'],
                        'thumbnail' : feedparserDict['media_thumbnail'][0]['url'],
                        'seen'      : False
                    }
    return outputDict

"""
Functions for managing database persistence between user sessions
"""

def parseDatabaseContent(content):
    return json.loads(content)

def parseDatabaseFile(filename):
    with open(filename, 'r') as filePointer:
        return json.load(filePointer)

def getDatabaseString(database):
    return json.dumps(database, indent=4)

def outputDatabaseToFile(database, filename):
    with open(filename, 'w') as filePointer:
        return json.dump(database, filePointer, indent=4)

"""
Functions for controlling main flow of the application
"""

def doInteractiveSearchForVideo(database, useTor=False, circuitManager=None):
    query = doGetUserInput("Search for video: ")
    querying = True
    while querying:
        try:
            resultList = doWaitScreen("Getting video results...", getVideoQueryResults,
                    query, useTor=useTor, circuitManager=circuitManager)
            if resultList:
                menuOptions = [
                    MethodMenuDecision(
                        str(result),
                        playVideo,
                        result.url,
                        useTor=useTor
                    )
                    for result in resultList
                ]
                menuOptions.insert(0, MethodMenuDecision("[Go back]", doReturnFromMenu))
                doMethodMenu(f"Search results for '{query}':",menuOptions)
                querying = False
            else:
                doNotify("no results found")
                querying = False
        except req.exceptions.ConnectionError:
            if not doYesNoQuery("Something went wrong with the connection. Try again?"):
                querying = False
            

def doInteractiveChannelSubscribe(database, useTor=False, circuitManager=None):
    query = doGetUserInput("Enter channel to search for: ")
    querying = True
    while querying:
        try:
            resultList = doWaitScreen("Getting channel results...", 
                    getChannelQueryResults, query, useTor=useTor, 
                    circuitManager=circuitManager)
            if resultList is not None and resultList:
                menuOptions = [
                    MethodMenuDecision(
                        str(result),
                        doChannelSubscribe,
                        result,
                        database,
                        useTor,
                        circuitManager
                    )
                    for result in resultList
                ]
                menuOptions.insert(0, MethodMenuDecision('[Go back]', doReturnFromMenu))
                doMethodMenu(f"search results for '{query}', choose which " + \
                        "channel to supscribe to", menuOptions)
                querying = False
            else:
                if not doYesNoQuery("No results found. Try again?"):
                    querying = False
        except req.exceptions.ConnectionError:
            if not doYesNoQuery("Something went wrong with the connection. Try again?"):
                querying = False

def doChannelSubscribe(result, database, useTor, circuitManager):
    refreshing = True
    if result.channelId in database['feeds']:
        doNotify("Already subscribed to this channel!")
        return
    while refreshing:
        try:
            doWaitScreen(f"getting data from feed for {result.title}...",
                    addSubscriptionToDatabase,database, result.channelId,
                    result.title, refresh=True, useTor=useTor,
                    circuitManager=circuitManager)
            refreshing = False
        except req.exceptions.ConnectionError:
            if not doYesNoQuery("Something went wrong with the " + \
                    "connection. Try again?"):
                querying = False
                refreshing = False
    outputDatabaseToFile(database, DATABASE_PATH)
    return ReturnFromMenu

def doInteractiveChannelUnsubscribe(database):
    if not database['title to id']:
        doNotify('You are not subscribed to any channels')
        return
    menuOptions = [
        MethodMenuDecision(
            channelTitle,
            removeSubscriptionFromDatabaseByChannelTitle,
            database,
            channelTitle
        )
        for channelTitle in database['title to id']
    ]
    menuOptions.insert(0, MethodMenuDecision('[Go back]', doReturnFromMenu))
    doMethodMenu("Which channel do you want to unsubscribe from?", menuOptions)

def doShowSubscriptions(database):
    if not database['title to id']:
        doNotify('You are not subscribed to any channels')
    else:
        doNotify("You are subscribed to these channels:")
        for title in database['title to id']:
            doNotify(f"\ntitle: {title}\nid: {database['title to id'][title]}")

def doInteractiveBrowseSubscriptions(database, useTor):
    channelMenuList = list(database['title to id'])
    if not channelMenuList:
        doNotify('You are not subscribed to any channels')
        return
    menuOptions = [
        MethodMenuDecision(
            channelTitle,
            doSelectVideoFromSubscription,
            database,
            channelTitle,
            useTor
        )
        for channelTitle in database['title to id']
    ]
    menuOptions.insert(0, MethodMenuDecision('[Go back]', doReturnFromMenu))
    doMethodMenu("Which channel do you want to watch a video from?", menuOptions)

def doSelectVideoFromSubscription(database, channelTitle, useTor):
    channelId = database['title to id'][channelTitle]
    videos = database['feeds'][channelId]
    menuOptions = [
        MethodMenuDecision(
            video['title'] + (' (unseen!)' if not video['seen'] else ''),
            doPlayVideoFromSubscription,
            video,
            useTor
        )
        for video in videos
    ]
    menuOptions.insert(0, MethodMenuDecision("[Go back]", doReturnFromMenu))
    doMethodMenu("Which video do you want to watch?", menuOptions)

def doPlayVideoFromSubscription(video, useTor):
    result = playVideo(video['link'], useTor)
    if not video['seen']:
        video['seen'] = result
        outputDatabaseToFile(database, DATABASE_PATH)

def playVideo(videoUrl, useTor=False):
    resolutionMenuList = [1080, 720, 480, 240]
    maxResolution = doSelectionQuery("Which maximum resolution do you want to use?",
            resolutionMenuList)
    result = False
    while not result:
        result = doWaitScreen("playing video...", openUrlInMpv, videoUrl, useTor=useTor,
                maxResolution=maxResolution)
        if result or not doYesNoQuery(f"Something went wrong when playing the " + \
                "video. Try again?"):
            break
    return result

def doShowDatabase(database):
    doNotify(getDatabaseString(database))

def doRefreshSubscriptions(database, useTor=False, circuitManager=None):
    channelIdList = list(database['id to title'])
    refreshing = True
    while refreshing:
        try:
            doWaitScreen("refreshing subscriptions...", refreshSubscriptionsByChannelId,
                    channelIdList, database, useTor=useTor, circuitManager=circuitManager)
            refreshing = False
        except req.exceptions.ConnectionError:
            if not doYesNoQuery("Something went wrong with the connection. Try again?"):
                refreshing = False
    outputDatabaseToFile(database, DATABASE_PATH)

# main section (demonstration of tools)

if __name__ == '__main__':
    try:
        if not os.path.isdir(YOUTUBE_RSS_DIR):
            os.mkdir(YOUTUBE_RSS_DIR)
        if os.path.isfile(DATABASE_PATH):
            database = parseDatabaseFile(DATABASE_PATH)
        else:
            database = initiateYouTubeRssDatabase()

        useTor = doYesNoQuery("Do you want to use tor?")
        if useTor:
            circuitManager = CircuitManager()
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                result = sock.connect_ex(('127.0.0.1',9050))
            if result != 0:
                if doYesNoQuery("Tor daemon not found on port 9050! " + \
                        "Continue without tor?"):
                    useTor=False
                else:
                    doNotify("Can't find Tor daemon. Exiting program.")
                    exit()
        else:
            circuitManager = None

        menuOptions =   [
            MethodMenuDecision( 
                "Search for video",
                doInteractiveSearchForVideo,
                database,
                useTor=useTor,
                circuitManager=circuitManager
            ),
            MethodMenuDecision( 
                "Refresh subscriptions",
                doRefreshSubscriptions,
                database,
                useTor=useTor,
                circuitManager=circuitManager
            ),
            MethodMenuDecision( 
                "Browse subscriptions",
                doInteractiveBrowseSubscriptions,
                database,
                useTor = useTor
            ),
            MethodMenuDecision( 
                "Subscribe to new channel",
                doInteractiveChannelSubscribe,
                database,
                useTor=useTor,
                circuitManager=circuitManager
            ),
            MethodMenuDecision( 
                "Unsubscribe from channel",
                doInteractiveChannelUnsubscribe,
                database
            ),
            MethodMenuDecision(
                "Quit",
                doReturnFromMenu
            )
        ]

        doMethodMenu("What do you want to do?", menuOptions)
    except KeyboardInterrupt:
        exit()
