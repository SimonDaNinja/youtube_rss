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
try:
    from tor_requests.tor_requests import getHttpResponseUsingSocks5
except:
    print("you probably haven't run the command\ngit submodule update --init --recursive")
    exit()
import subprocess
import os

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
        attrDict = attrsToDict(attrs)
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
                pattern = re.compile('"channelRenderer":\{"channelId":"([^"]+)","title":\{"simpleText":"([^"]+)"')
                tupleList = pattern.findall(data)
                resultList = []
                for tup in tupleList:
                    resultList.append(ChannelQueryObject(channelId = tup[0], title = tup[1]))
                self.resultList = resultList

# other classes #

class ChannelQueryObject:
    def __init__(self, channelId = None, title = None):
        self.channelId = channelId
        self.title     = title

    def __str__(self):
        return f"{self.title}  --  (channel ID {self.channelId})"

#############
# functions #
#############

# help functions #

def doClear():
    os.system('clear')

def doPressEnterToContinue():
    input('\npress enter to continue')

# use this function to convert the attrs parameter used in HTMLParser into a dict
def attrsToDict(attrs):
    attrDict = {}
    for avp in attrs:
        attrDict[avp[0]] = avp[1]
    return attrDict

# use this function to escape a YouTube query for the query URL
# TODO: implement this function more properly
def escapeQuery(query):
    return query.replace(' ', '+').replace('++','+')

#use this function to get html for a youtube channel query
def getChannelQueryHtml(query, getHttpContent = req.get):
    url = 'https://youtube.com/results?search_query=' + escapeQuery(query) + '&sp=EgIQAg%253D%253D'
    try:
        response = getHttpContent(url)
    except req.exceptions.ConnectionError:
        return None
    if response.text is not None:
        return response.text
    else:
        return None

def printMenu(query, menu, stdscr, choiceIndex):
    stdscr.clear()
    height, width = stdscr.getmaxyx()
    screenCenterX = width//2
    screenCenterY = height//2
    nRowsToPrint = (len(menu)+2)//2

    menuWidth = max([len(str(item)) for item in menu])
    itemX = screenCenterX - menuWidth//2

    if nRowsToPrint > height:
        ySelected = screenCenterY - nRowsToPrint + choiceIndex + 2
        offset = (ySelected - screenCenterY)
    else:
        offset = 0

    titleX = screenCenterX-len(query)//2
    titleY = screenCenterY-nRowsToPrint - offset
    if titleY >0 and titleY<height:
        stdscr.addstr(titleY, titleX, query)
    for i, item in enumerate(menu):
        itemString = str(item)
        attr = curses.color_pair(HIGHLIGHTED if i == choiceIndex else NOT_HIGHLIGHTED)
        stdscr.attron(attr)
        itemY = screenCenterY - nRowsToPrint + i + 2 - offset
        if itemY >0 and itemY<height:
            stdscr.addstr(itemY, itemX, itemString)
        stdscr.attroff(attr)
    stdscr.refresh()

def doYnQueryNcursesWrapped(query):
    return curses.wrapper(doYnQueryNcurses, query)

def doYnQueryNcurses(stdscr, query):
    choiceIndex = 0
    return doSelectionQueryNcurses(stdscr, query, ['yes','no'])=='yes'

def doSelectionQueryNcursesWrapped(query, options, indexChoice=False):
    return curses.wrapper(doSelectionQueryNcurses, query, options, indexChoice=indexChoice)

def doSelectionQueryNcurses(stdscr, query, options, indexChoice=False):
    curses.curs_set(0)
    curses.init_pair(HIGHLIGHTED, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(NOT_HIGHLIGHTED, curses.COLOR_WHITE, curses.COLOR_BLACK)
    choiceIndex = 0
    while True:
        printMenu(query, options, stdscr, choiceIndex)
        key = stdscr.getch()
        if key == curses.KEY_UP:
            choiceIndex = max(choiceIndex-1, 0)
        elif key == curses.KEY_DOWN:
            choiceIndex = min(choiceIndex+1, len(options)-1)
        elif key == curses.KEY_ENTER or key in [10, 13]:
            return choiceIndex if indexChoice else options[choiceIndex]
    
# use this function to ask an interactive yes/no question to the user
def doYnQuery(query, default=None, clear=True):
    verdict = False
    if clear:
        doClear()
    while True:
        yn = input(query + ' [y/n] ').lower()
        if yn not in ['y', 'n'] if default is None else yn not in ['y', 'n', '']:
            print('invalid response!')
        else:
            break
    if yn == 'y' or (yn == '' and default == 'y'):
        verdict = True
    return verdict

def doSelectionQuery(query, options, default=None, indexChoice=False, clear=True):
    if clear:
        doClear()
    query += f' [1-{len(options)}] '
    if default is not None:
        query += f'({default}) '
    while True:
        ans = input("\n".join([f"{i+1}: {option}" for i, option in enumerate(options)] + ['\n' + query]))
        if ans == '' and default is not None:
            selection = options.index(default) if indexChoice else default
            break
        elif not ans.isdigit() or int(ans)-1 not in range(len(query)):
            print('invalid response!')
        else:
            selection = int(ans)-1 if indexChoice else options[int(ans)-1]
            break
    return selection

# central functions #

# if you have a channel url, you can use this function to extract the rss address
def getRssAddressFromChannelUrl(url, getHttpContent = req.get):
    try:
        response = getHttpContent(url)
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
def getChannelQueryResults(query, getHttpContent = req.get):
    htmlContent = getChannelQueryHtml(query, getHttpContent = getHttpContent)
    if htmlContent is not None:
        parser = ChannelQueryParser()
        parser.feed(htmlContent)
        return parser.resultList
    else:
        return None

# use this function to get rss entries from channel id
def getRssEntriesFromChannelId(channelId, getHttpContent = req.get):
    rssAddress = getRssAddressFromChannelId(channelId)
    try:
        response = getHttpContent(rssAddress)
    except req.exceptions.ConnectionError:
        return None
    if response.text is not None:
        rssContent = response.text
        entries = feedparser.parse(rssContent)['entries']
        return entries
    else:
        return None

def initiateYouTubeRssDatabase():
    database = {}
    database['feeds'] = {}
    database['id to title'] = {}
    database['title to id'] = {}
    return database

def addSubscriptionToDatabase(database, channelId, channelTitle, refresh=False, getHttpContent=req.get):
    if channelId in database['feeds']:
        doClear()
        print("\nAlready subscribed to this channel!")
        doPressEnterToContinue()
        return True
    database['feeds'][channelId] = []
    database['id to title'][channelId] = channelTitle
    database['title to id'][channelTitle] = channelId
    if refresh:
        return refreshSubscriptionsByChannelId([channelId], database, getHttpContent=getHttpContent)
    return True

def removeSubscriptionFromDatabaseByChannelTitle(database, channelTitle):
    if channelTitle not in database['title to id']:
        return
    channelId = database['title to id'][channelTitle]
    removeSubscriptionFromDatabaseByChannelId(database, channelId)

def removeSubscriptionFromDatabaseByChannelId(database, channelId):
    if channelId not in database['id to title']:
        return
    channelTitle = database['id to title'].pop(channelId)
    database['title to id'].pop(channelTitle)
    database['feeds'].pop(channelId)
    outputDatabaseToFile(database, DATABASE_PATH)


def refreshSubscriptionsByChannelId(channelIdList, database, getHttpContent=req.get):
    localFeeds = database['feeds']
    for channelId in channelIdList:
        localFeed = localFeeds[channelId]
        remoteFeed = getRssEntriesFromChannelId(channelId, getHttpContent=getHttpContent)
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

def openUrlInMpv(url, useTor=False, maxResolution=1080):
    while True:
        try:
            command = []
            if useTor:
                command.append('torsocks')
                command.append('-i')
            command.append('mpv')
            command.append(url)
            mpvProcess = subprocess.Popen(command, stdout = subprocess.DEVNULL, stderr = subprocess.STDOUT)
            mpvProcess.wait()
            result = mpvProcess.poll()
        except KeyboardInterrupt:
            mpvProcess.kill()
            mpvProcess.wait()
            result = mpvProcess.poll()
            pass
        if result in [0,4] or not doYnQueryNcursesWrapped(f"Something went wrong when playing the video (exit code: {result}). Try again?"):
            break
    return result in [0,4]

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

# Demonstration Functions #

def doInteractiveChannelSubscribe(database, getHttpContent=req.get):
    doClear()
    query = input("Enter channel to search for: ")
    doClear()
    querying = True
    while querying:
        resultList = getChannelQueryResults(query, getHttpContent = getHttpContent)
        if resultList is not None:
            result = doSelectionQueryNcursesWrapped(f"search results for {query}, choose which channel to supscribe to", resultList)
            refreshing = True
            while refreshing:
                if not addSubscriptionToDatabase(database, result.channelId, result.title, refresh=True, getHttpContent = getHttpContent):
                    if not doYnQueryNcursesWrapped("Something went wrong with the connection. Try again?"):
                        querying = False
                        refreshing = False
                else:
                    refreshing = False
            outputDatabaseToFile(database, DATABASE_PATH)
            querying = False
        else:
            if not doYnQueryNcursesWrapped("Something went wrong with the connection. Try again?"):
                querying = False

def doInteractiveChannelUnsubscribe(database):
    doClear()
    channelTitleList = [key for key in database['title to id']]
    if not channelTitleList:
        doClear()
        print('You are not subscribed to any channels')
        doPressEnterToContinue()
        return
    channelTitle = doSelectionQueryNcursesWrapped("Which channel do you want to unsubscribe from?", channelTitleList)
    removeSubscriptionFromDatabaseByChannelTitle(database, channelTitle)

def doShowSubscriptions(database):
    doClear()
    if not database['title to id']:
        print('You are not subscribed to any channels')
    else:
        print("You are subscribed to these channels:")
        for title in database['title to id']:
            print(f"\ntitle: {title}\nid: {database['title to id'][title]}")
    doPressEnterToContinue()

def doInteractivePlayVideo(database, useTor):
    channelMenuList = list(database['title to id'])
    doClear()
    if not channelMenuList:
        print('\nYou are not subscribed to any channels')
        doPressEnterToContinue()
        return
    channelTitle = doSelectionQueryNcursesWrapped("Which channel do you want to watch a video from?", channelMenuList)
    channelId = database['title to id'][channelTitle]
    videos = database['feeds'][channelId]
    videosMenuList = [video['title'] + (' (unseen!)' if not video['seen'] else '') for video in videos]
    video = videos[doSelectionQueryNcursesWrapped("Which video do you want to watch?", videosMenuList, indexChoice=True)]
    videoUrl = video['link']
    resolutionMenuList = [1080, 720, 480, 240]
    maxResolution = doSelectionQueryNcursesWrapped("Which maximum resolution do you want to use?", resolutionMenuList)
    result = openUrlInMpv(videoUrl, useTor=useTor, maxResolution=maxResolution)
    if not video['seen']:
        video['seen'] = result
        outputDatabaseToFile(database, DATABASE_PATH)

def doShowDatabase(database):
    print(getDatabaseString(database))
    doPressEnterToContinue()

def doRefreshSubscriptions(database, getHttpContent = req.get):
    channelIdList = list(database['id to title'])
    refreshing = True
    while refreshing:
        if not refreshSubscriptionsByChannelId(channelIdList, database, getHttpContent = getHttpContent):
            if not doYnQueryNcursesWrapped("Something went wrong with the connection. Try again?"):
                refreshing = False
        else:
            refreshing = False
    outputDatabaseToFile(database, DATABASE_PATH)

# main section (demonstration of tools)

if __name__ == '__main__':
    try:
        doClear()
        if not os.path.isdir(YOUTUBE_RSS_DIR):
            os.mkdir(YOUTUBE_RSS_DIR)
        if os.path.isfile(DATABASE_PATH):
            database = parseDatabaseFile(DATABASE_PATH)
        else:
            database = initiateYouTubeRssDatabase()

        useTor = doYnQueryNcursesWrapped("Do you want to use tor?")
        if useTor:
            getHttpContent = getHttpResponseUsingSocks5
        else:
            getHttpContent = req.get

        menuOptions =   {
                            "Subscribe to new channel"  : doInteractiveChannelSubscribe,
                            "Unsubscribe from channel"  : doInteractiveChannelUnsubscribe,
                            "Browse subscriptions"      : doInteractivePlayVideo,
                            "Refresh subscriptions"     : doRefreshSubscriptions,
                            "Quit"                      : None
                        }

        menuList = list(menuOptions)

        while True:
            choice = doSelectionQueryNcursesWrapped("What do you want to do?", menuList)
            chosenFunction = menuOptions[choice]

            # handle special cases #
            # if user wants to quit:
            try:
                if chosenFunction is None:
                    exit()
                # if function needs an http get method
                elif chosenFunction in [doInteractiveChannelSubscribe, doRefreshSubscriptions]:
                    chosenFunction(database, getHttpContent)
                # if function needs to know if Tor is used
                elif chosenFunction in [doInteractivePlayVideo]:
                    chosenFunction(database, useTor)
                # default case: choice only needs to use database
                else:
                    chosenFunction(database)
            except KeyboardInterrupt:
                pass
    except KeyboardInterrupt:
        print("")
        exit()
