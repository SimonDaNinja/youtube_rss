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

#############
# functions #
#############

# help functions #

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
    response = getHttpContent(url)
    if response.text is not None:
        return response.text

# use this function to ask an interactive yes/no question to the user
def doYnQuery(query):
    while True:
        yn = input(query + ' [y/n] ').lower()
        if yn not in ['y', 'n']:
            print('invalid response!')
        else:
            break
    if yn == 'y':
        return True
    return False

def doSelectionQuery(query, options):
    while True:
        ans = input("\n" + "\n".join([f"{i+1}: {option}" for i, option in enumerate(options)] + ['\n' + query + f' (1-{len(options)}) ']))
        if not ans.isdigit() or int(ans)-1 not in range(len(query)):
            print('invalid response!')
        else:
            return int(ans)-1

# central functions #

# if you have a channel url, you can use this function to extract the rss address
def getRssAddressFromChannelUrl(url, getHttpContent = req.get):
    response = getHttpContent(url)
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
    response = getHttpContent(rssAddress)
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
        print("\nAlready subscribed to this channel!")
        return
    database['feeds'][channelId] = []
    database['id to title'][channelId] = channelTitle
    database['title to id'][channelTitle] = channelId
    if refresh:
        refreshSubscriptionsByChannelId([channelId], database, getHttpContent=getHttpContent)

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
                if filteredEntry not in localFeed:
                    localFeed.insert(0, filteredEntry)
            return True
        else:
            return False

def openUrlInMpv(url, useTor=False):
    while True:
        command = []
        if useTor:
            command.append('torsocks')
        command.append('mpv')
        command.append(url)
        mpvProcess = subprocess.Popen(command, stdout = subprocess.DEVNULL, stderr = subprocess.STDOUT)
        mpvProcess.wait()
        result = mpvProcess.poll()
        if result in [0,4] or not doYnQuery(f"Something went wrong when playing the video (exit code: {result}). Try again?"):
            break

def getRelevantDictFromFeedParserDict(feedparserDict):
    outputDict =    {
                        'id'        : feedparserDict['id'],
                        'link'      : feedparserDict['link'],
                        'title'     : feedparserDict['title'],
                        'thumbnail' : feedparserDict['media_thumbnail'][0]['url']
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
    query = input("Enter channel to search for: ")
    querying = True
    while querying:
        resultList = getChannelQueryResults(query, getHttpContent = getHttpContent)
        if resultList is not None:
            print(f"Going through search results for '{query}'...\n")
            for i, result in enumerate(resultList):
                print(f"Search result {i+1}:\nTitle: {result.title}\nChannel ID: {result.channelId}\nRSS feed: {getRssAddressFromChannelId(result.channelId)}\n")
                if doYnQuery('Add this channel to subscriptions?'):
                    addSubscriptionToDatabase(database, result.channelId, result.title, refresh=True, getHttpContent = getHttpContent)
                    break
            outputDatabaseToFile(database, DATABASE_PATH)
            querying = False
        else:
            if not doYnQuery("Something went wrong with the connection. Try again?"):
                querying = False

def doInteractiveChannelUnsubscribe(database):
    channelTitleList = [key for key in database['title to id']]
    if not channelTitleList:
        print('\nYou are not subscribed to any channels')
        return
    channelTitle = channelTitleList[doSelectionQuery("Which channel do you want to unsubscribe from?", channelTitleList)]
    removeSubscriptionFromDatabaseByChannelTitle(database, channelTitle)

def doShowSubscriptions(database):
    if not database['title to id']:
        print('\nYou are not subscribed to any channels')
        return
    print("\nYou are subscribed to these channels:\n")
    for title in database['title to id']:
        print(f"title: {title}\nid: {database['title to id'][title]}")

def doInteractivePlayVideo(database, useTor):
    channelMenuList = list(database['title to id'])
    if not channelMenuList:
        print('\nYou are not subscribed to any channels')
        return
    channelTitle = channelMenuList[doSelectionQuery("Which channel do you want to watch a video from?", channelMenuList)]
    channelId = database['title to id'][channelTitle]
    videos = database['feeds'][channelId]
    videosMenuList = [video['title'] for video in videos]
    videoUrl = videos[doSelectionQuery("Which video do you want to watch?", videosMenuList)]['link']
    openUrlInMpv(videoUrl, useTor=useTor)

def doShowDatabase(database):
    print(getDatabaseString(database))

def doRefreshSubscriptions(database, getHttpContent = req.get):
    channelIdList = list(database['id to title'])
    refreshing = True
    while refreshing:
        if not refreshSubscriptionsByChannelId(channelIdList, database, getHttpContent = getHttpContent):
            if not doYnQuery("Something went wrong with the connection. Try again?"):
                refreshing = False
        else:
            refreshing = False
    outputDatabaseToFile(database, DATABASE_PATH)

# main section (demonstration of tools)

if __name__ == '__main__':
    if not os.path.isdir(YOUTUBE_RSS_DIR):
        os.mkdir(YOUTUBE_RSS_DIR)
    if os.path.isfile(DATABASE_PATH):
        database = parseDatabaseFile(DATABASE_PATH)
    else:
        database = initiateYouTubeRssDatabase()

    print("\nSimonDaNinja/youtube_rss  Copyright (C) 2021  Simon Liljestrand\n" +
    "This program comes with ABSOLUTELY NO WARRANTY.\n" +
    "This is free software, and you are welcome to redistribute it\n" +
    "under certain conditions.\n")

    useTor = doYnQuery("Do you want to use tor?")
    if useTor:
        getHttpContent = getHttpResponseUsingSocks5
    else:
        getHttpContent = req.get


    menuOptions =   {
                        "Subscribe to new channel"  : doInteractiveChannelSubscribe,
                        "Unsubscribe from channel"  : doInteractiveChannelUnsubscribe,
                        "Show subscriptions"        : doShowSubscriptions,
                        "Play video"                : doInteractivePlayVideo,
                        "Show database"             : doShowDatabase,
                        "Refresh subscriptions"     : doRefreshSubscriptions,
                        "Quit"                      : None
                    }

    menuList = list(menuOptions)

    while True:
        choice = menuList[doSelectionQuery("What do you want to do?", menuList)]
        chosenFunction = menuOptions[choice]

        # handle special cases #
        # if user wants to quit:
        if chosenFunction is None:
            break
        # if function needs an http get method
        elif chosenFunction in [doInteractiveChannelSubscribe, doRefreshSubscriptions]:
            chosenFunction(database, getHttpContent)
        # if function needs to know if Tor is used
        elif chosenFunction in [doInteractivePlayVideo]:
            chosenFunction(database, useTor)
        # default case: choice only needs to use database
        else:
            chosenFunction(database)
