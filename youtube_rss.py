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

from tkinter import W
import feedparser
import json
import socket
import os
import time
import urllib
import asyncio
import aiohttp
from aiohttp_socks import ProxyConnector
from aiohttp_socks import ProxyType
import subprocess
import secrets
import argparse
import presentation
import indicator_classes
import parser_classes

#############
# constants #
#############

HOME = os.environ.get('HOME')
YOUTUBE_RSS_DIR = '/'.join([HOME,'.youtube_rss'])
THUMBNAIL_DIR = '/'.join([YOUTUBE_RSS_DIR, 'thumbnails'])
THUMBNAIL_SEARCH_DIR = '/'.join([THUMBNAIL_DIR, 'search'])
DATABASE_PATH  = '/'.join([YOUTUBE_RSS_DIR, 'database'])
LOG_PATH = '/'.join([YOUTUBE_RSS_DIR, 'log'])

ANY_INDEX = -1
MAX_CONNECTIONS=30

###########
# classes #
###########

"""
Other classes
"""

# manages socks5 auths used for Tor stream isolation
class CircuitManager:
    def __init__(self, nCircuits = 15, ttl = 600):
        self.ttl = ttl
        self.nCircuits = 15
        self.i = 0
        self.expiryTime = 0

    def initiateCircuitAuths(self):
        self.circuitAuths=[generateNewSocks5Auth() for i in range(self.nCircuits)]

    def getAuth(self):
        # if ttl is over, reinitiate circuit auth list
        if self.expiryTime < time.time():
            self.initiateCircuitAuths()
            self.expiryTime = time.time() + self.ttl
        # circulate over the various auths so that you don't use the same circuit all the
        # time
        self.i += 1
        return self.circuitAuths[self.i%self.nCircuits]

# item of the sort provided in list to doMethodMenu; it is provided a description of an
# option presented to the user, a function that will be executed if chosen by the user,
# and all arguments that the function needs
class MethodMenuDecision:
    def __init__(self, description, function, *args, **kwargs):
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.description = description

    def __str__(self):
        return str(self.description)

    def executeDecision(self):
        return self.function(*self.args, **self.kwargs)

class FeedVideoDescriber:
    def __init__(self, video):
        self.video = video

    def __str__(self):
        return self.video['title'] + (' (unseen!)' if not self.video['seen'] else '')

    def getThumbnail(self):
        return self.video['thumbnail file']

class VideoQueryObjectDescriber:
    def __init__(self, videoQueryObject):
        self.videoQueryObject = videoQueryObject

    def __str__(self):
        return self.videoQueryObject.title

    def getThumbnail(self):
        return '/'.join([THUMBNAIL_SEARCH_DIR, 
            self.videoQueryObject.videoId + '.jpg'])

class FeedDescriber:
    def __init__(self, feed, channelTitle):
        self.feed = feed
        self.channelTitle = channelTitle

    def __str__(self):
        return ''.join([self.channelTitle, ': (', str(sum([1 for video in self.feed
            if not video['seen']])),'/',str(len(self.feed)), ')'])

class AdHocKey:
    def __init__(self, key, item, activationIndex = ANY_INDEX):
        self.key = key
        self.item = item
        self.activationIndex = activationIndex

    def isValidIndex(self, index):
        if self.activationIndex == ANY_INDEX:
            return True
        else:
            return index == self.activationIndex

    def __eq__(self,other):
        if isinstance(other, int):
            return other == self.key
        if isinstance(other, chr):
            return other == chr(self.key)
        if isinstance(other, AdHocKey):
            return other.key == self.key and other.item == self.item and \
                    other.activationIndex == self.activationIndex
        else:
            raise TypeError

class MarkAllAsReadKey(AdHocKey):
    def __init__(self, channelId, activationIndex, database, key=ord('a')):
        item =  MethodMenuDecision(
                    f"mark all by {channelId} as read",
                    doMarkChannelAsRead,
                    database,
                    channelId
                )
        AdHocKey.__init__(self, key=key, item=item, activationIndex=activationIndex)

class MarkEntryAsReadKey(AdHocKey):
    def __init__(self, video, activationIndex, key=ord('a')):
        item =  MethodMenuDecision(
                    "mark video as read",
                    lambda video : video.update({'seen':(not video['seen'])}),
                    video
                )
        AdHocKey.__init__(self, key=key, item=item, activationIndex=activationIndex)

#############
# functions #
#############

"""
Functions for retreiving and processing network data
"""

# use this function to generate new socks5 authentication (for tor stream 
# isolation)
def generateNewSocks5Auth(userNameLen = 30, passwordLen = 30):
    alphaNumeric = "QWERTYUIOPASDFGHJKLZXCVBNMqwertyuiopasdfghjklzxcvbnm1234567890"
    username = "".join([rnd.choice(alphaNumeric) for i in range(userNameLen)])
    password = "".join([rnd.choice(alphaNumeric) for i in range(passwordLen)])
    return username, password

# use this function to get content (typically hypertext or xml) using HTTP from YouTube
async def getHttpContent(url, useTor, semaphore, auth=None, contentType='text'):
    if useTor:
        if auth is not None:
            username, password = auth
        else:
            username = None
            password = None
        connector = ProxyConnector(proxy_type=ProxyType.SOCKS5, host = "127.0.0.1", 
                port = 9050, username=username, password = password, rdns = True)
    else:
        connector = None

    # This cookie lets us avoid the YouTube consent page
    cookies = {'CONSENT':'YES+'}
    headers = {'Accept-Language':'en-US'}
    await semaphore.acquire()
    async with aiohttp.ClientSession(connector=connector, cookies = cookies) as session:
        session.headers['Accept-Language']='en-US'
        async with session.get(url, headers=headers) as response:
            if contentType == 'text':
                result = await response.text()
            elif contentType == 'bytes':
                result = await response.read()
            else:
                raise ValueError(f"unknown content type: {contentType}")
    semaphore.release()
    return result

# if you have a channel id, you can use this function to get the rss address
def getRssAddressFromChannelId(channelId):
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channelId}"

# use this function to get a list of query results from searching for a channel
# results are of the type ChannelQueryObject
async def getChannelQueryResults(query, useTor=False, auth=None):
    url = 'https://youtube.com/results?search_query=' + urllib.parse.quote(query) + \
            '&sp=EgIQAg%253D%253D'
    semaphore = asyncio.Semaphore(MAX_CONNECTIONS)
    getTask = asyncio.create_task(getHttpContent(url, useTor=useTor, semaphore=semaphore,
        auth=auth))
    htmlContent = await getTask
    parser = parser_classes.ChannelQueryParser()
    parser.feed(htmlContent)
    return parser.resultList

# use this function to get a list of query results from searching for a video
# results are of the type VideoQueryObject
async def getVideoQueryResults(query, ueberzug, useTor=False, auth=None):
    url = 'https://youtube.com/results?search_query=' + urllib.parse.quote(query) + \
            '&sp=EgIQAQ%253D%253D'
    semaphore = asyncio.Semaphore(MAX_CONNECTIONS)
    getTask = asyncio.create_task(getHttpContent(url, semaphore=semaphore, useTor=useTor, 
        auth=auth))
    htmlContent = await getTask
    parser = parser_classes.VideoQueryParser()
    parser.feed(htmlContent)
    if ueberzug:
        if os.path.isdir(THUMBNAIL_SEARCH_DIR):
            shutil.rmtree(THUMBNAIL_SEARCH_DIR)
        os.mkdir(THUMBNAIL_SEARCH_DIR)
        thumbnailTask = asyncio.create_task(getSearchThumbnails(parser.resultList,
            ueberzug, semaphore=semaphore, useTor=useTor, auth = auth))
        await thumbnailTask

    return parser.resultList

# use this function to get rss entries from channel id
async def getRssEntriesFromChannelId(channelId, semaphore, useTor=False, auth=None):
    rssAddress = getRssAddressFromChannelId(channelId)
    getTask = asyncio.create_task(getHttpContent(rssAddress, useTor, semaphore=semaphore,
        auth=auth))
    rssContent = await getTask
    entries = feedparser.parse(rssContent)['entries']
    return entries

# use this function to initialize the database (dict format so it's easy to save as json)
def initiateYouTubeRssDatabase():
    database = {}
    database['feeds'] = {}
    database['id to title'] = {}
    database['title to id'] = {}
    return database

# use this function to add a subscription to the database
def addSubscriptionToDatabase(channelId, ueberzug, channelTitle, refresh=False,
        useTor=False, circuitManager=None):
    database = parseDatabaseFile(DATABASE_PATH)
    database['feeds'][channelId] = []
    database['id to title'][channelId] = channelTitle
    database['title to id'][channelTitle] = channelId
    outputDatabaseToFile(database, DATABASE_PATH)
    auth = None
    if circuitManager is not None and useTor:
        auth = circuitManager.getAuth()
    if refresh:
        asyncio.run(refreshSubscriptionsByChannelId( [channelId], ueberzug, useTor=useTor, 
                auth=auth))

def deleteThumbnailsByChannelTitle(database, channelTitle):
    if channelTitle not in database['title to id']:
        return
    channelId = database['title to id'][channelTitle]
    deleteThumbnailsByChannelId(database, channelId)
    return

def deleteThumbnailsByChannelId(database, channelId):
    if channelId not in database['id to title']:
        return
    feed = database['feeds'][channelId]
    for entry in feed:
        if os.path.isfile(entry['thumbnail file']):
            os.remove(entry['thumbnail file'])

# use this function to remove a subscription from the database by channel title
def removeSubscriptionFromDatabaseByChannelTitle(database, channelTitle):
    if channelTitle not in database['title to id']:
        return
    channelId = database['title to id'][channelTitle]
    removeSubscriptionFromDatabaseByChannelId(database, channelId)
    return

# use this function to remove a subscription from the database by channel ID
def removeSubscriptionFromDatabaseByChannelId(database, channelId):
    if channelId not in database['id to title']:
        return
    channelTitle = database['id to title'].pop(channelId)
    database['title to id'].pop(channelTitle)
    database['feeds'].pop(channelId)
    outputDatabaseToFile(database, DATABASE_PATH)


# use this function to retrieve new RSS entries for a subscription and add them to
# a database

async def refreshSubscriptionsByChannelId(channelIdList, ueberzug, useTor=False, 
        auth=None):
    database = parseDatabaseFile(DATABASE_PATH)
    localFeeds = database['feeds']
    tasks = []

    semaphore = asyncio.Semaphore(MAX_CONNECTIONS)

    for channelId in channelIdList:
        localFeed = localFeeds[channelId]
        tasks.append(asyncio.create_task(refreshSubscriptionByChannelId(channelId, localFeed, 
            semaphore=semaphore, useTor=useTor, auth=auth)))

    for task in tasks:
        await task

    if ueberzug:
        await asyncio.create_task(getThumbnailsForAllSubscriptions(channelIdList, 
            database, semaphore=semaphore, useTor=useTor, auth=auth))
    outputDatabaseToFile(database, DATABASE_PATH)

async def refreshSubscriptionByChannelId(channelId, localFeed, semaphore, useTor=False,
        auth=None):
    task = asyncio.create_task(getRssEntriesFromChannelId(channelId, semaphore=semaphore, useTor=useTor, 
            auth=auth))
    remoteFeed = await task
    if remoteFeed is not None:
        remoteFeed.reverse()
        for entry in remoteFeed:
            filteredEntry = getRelevantDictFromFeedParserDict(entry)

            filteredEntryIsNew = True
            for i, localEntry in enumerate(localFeed):
                if localEntry['id'] == filteredEntry['id']:
                    filteredEntryIsNew = False
                    # in case any relevant data about the entry is changed, update it
                    filteredEntry['seen'] = localEntry['seen']
                    if filteredEntry['thumbnail'] == localEntry['thumbnail'] and \
                            'thumbnail file' in filteredEntry:
                        filteredEntry['thumbnail file'] = localEntry['thumbnail file']
                    localFeed[i] = filteredEntry
                    break
            if filteredEntryIsNew:
                localFeed.insert(0, filteredEntry)


# use this function to open a YouTube video url in mpv
def openUrlInMpv(url, useTor=False, maxResolution=1080, circuitManager = None):
    try:
        command = []
        if useTor:
            auth = circuitManager.getAuth()
            command.append('torsocks')
            command.append('-u')
            command.append(auth[0])
            command.append('-p')
            command.append(auth[1])
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

# use this function to get the data we care about from the entries found by the RSS parser
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

# use this function to read database from json string
def parseDatabaseContent(content):
    return json.loads(content)

# use this function to read database from json file
def parseDatabaseFile(filename):
    with open(filename, 'r') as filePointer:
        return json.load(filePointer)

# use this function to return json representation of database as string
def getDatabaseString(database):
    return json.dumps(database, indent=4)

# use this function to write json representation of database to file
def outputDatabaseToFile(database, filename):
    with open(filename, 'w') as filePointer:
        return json.dump(database, filePointer, indent=4)

"""
Application control flow
"""

def doMarkChannelAsRead(database, channelId):
    allAreAlreadyMarkedAsRead = True
    for video in database['feeds'][channelId]:
        if not video['seen']:
            allAreAlreadyMarkedAsRead = False
            break
    for video in database['feeds'][channelId]:
        video['seen'] = not allAreAlreadyMarkedAsRead
    outputDatabaseToFile(database, DATABASE_PATH)

# this is the application level flow entered when the user has chosen to search for a
# video
def doInteractiveSearchForVideo(ueberzug, useTor=False, circuitManager=None):
    query = presentation.doGetUserInput("Search for video: ")
    querying = True
    while querying:
        try:
            auth = None
            if useTor and circuitManager is not None:
                auth = circuitManager.getAuth()
            resultList = presentation.doWaitScreen("Getting video results...", getVideoQueryResults,
                    query, ueberzug, useTor=useTor, auth=auth)
            if resultList:
                menuOptions = [
                    MethodMenuDecision(
                        VideoQueryObjectDescriber(result),
                        playVideo,
                        result.url,
                        useTor=useTor,
                        circuitManager=circuitManager
                    ) for result in resultList
                ]
                menuOptions.insert(0, MethodMenuDecision("[Go back]", doReturnFromMenu))
                doMethodMenu(f"Search results for '{query}':",menuOptions, ueberzug=ueberzug)
                querying = False
            else:
                presentation.doNotify("no results found")
                querying = False
        except Exception as e:
            if not presentation.doYesNoQuery(f"Something went wrong! Try again?"):
                querying = False
    if os.path.isdir(THUMBNAIL_SEARCH_DIR):
        shutil.rmtree(THUMBNAIL_SEARCH_DIR)

async def getThumbnailsForAllSubscriptions(channelIdList, database, semaphore, useTor=False, auth=None):
    feeds = database['feeds']
    tasks = []
    for channelId in channelIdList:
        feed = feeds[channelId]
        tasks.append(asyncio.create_task(getThumbnailsForFeed(feed, 
            semaphore=semaphore, useTor=useTor, auth=auth)))
    for task in tasks:
        await task


async def getThumbnailsForFeed(feed, semaphore, useTor=False, auth = None):
    getTasks = {}

    for entry in feed:
        if 'thumbnail file' in entry:
            continue
        videoId = entry['id'].split(':')[-1]
        thumbnailFileName = '/'.join([THUMBNAIL_DIR, videoId + 
                '.jpg'])
        getTask = asyncio.create_task(getHttpContent(entry['thumbnail'], useTor=useTor,
                semaphore=semaphore, auth = auth, contentType = 'bytes'))
        getTasks[entry['id']] = (getTask, thumbnailFileName)

    for entry in feed:
        if 'thumbnail file' in entry:
            continue
        thumbnailContent = await getTasks[entry['id']][0]
        thumbnailFileName = getTasks[entry['id']][1]
        entry['thumbnail file'] = thumbnailFileName
        open(thumbnailFileName, 'wb').write(thumbnailContent)

async def getSearchThumbnails(resultList, ueberzug, semaphore, useTor = False, auth=None):
    tasks = []
    for result in resultList:
        tasks.append(asyncio.create_task(getSearchThumbnailFromSearchResult(result, 
            ueberzug, semaphore = semaphore, useTor=useTor, auth=auth)))
    for task in tasks:
        await task

async def getSearchThumbnailFromSearchResult(result, ueberzug, semaphore, useTor=False, auth=None):
    videoId = result.videoId.split(':')[-1]
    thumbnailFileName = '/'.join([THUMBNAIL_SEARCH_DIR, videoId +
            '.jpg'])
    getTask = asyncio.create_task(getHttpContent(result.thumbnail, semaphore=semaphore, useTor=useTor,
            auth = auth, contentType='bytes'))
    thumbnailContent = await getTask
    result.thumbnailFile = thumbnailFileName
    open(thumbnailFileName, 'wb').write(thumbnailContent)

# this is the application level flow entered when the user has chosen to subscribe to a
# new channel
def doInteractiveChannelSubscribe(ueberzug, useTor=False, circuitManager=None):
    query = presentation.doGetUserInput("Enter channel to search for: ")
    querying = True
    while querying:
        try:
            auth = None
            if useTor and circuitManager is not None:
                auth = circuitManager.getAuth()
            resultList = presentation.doWaitScreen("Getting channel results...", 
                    getChannelQueryResults, query, useTor=useTor, 
                    auth=auth)
            if resultList:
                menuOptions = [
                    MethodMenuDecision(
                        str(result),
                        doChannelSubscribe,
                        result=result,
                        useTor=useTor,
                        circuitManager=circuitManager,
                        ueberzug=ueberzug
                    ) for result in resultList
                ]
                menuOptions.insert(0, MethodMenuDecision('[Go back]', doReturnFromMenu))
                doMethodMenu(f"search results for '{query}', choose which " + \
                        "channel to supscribe to", menuOptions)
                querying = False
            else:
                if not presentation.doYesNoQuery("No results found. Try again?"):
                    querying = False
        except Exception:
            if not presentation.doYesNoQuery("Something went wrong. Try again?"):
                querying = False

# this is the application level flow entered when the user has chosen a channel that it
# wants to subscribe to
def doChannelSubscribe(result, useTor, circuitManager, ueberzug):
    database = presentation.doWaitScreen('', parseDatabaseFile, DATABASE_PATH)
    refreshing = True
    if result.channelId in database['feeds']:
        presentation.doNotify("Already subscribed to this channel!")
        return
    while refreshing:
        try:
            presentation.doWaitScreen(f"getting data from feed for {result.title}...",
                    addSubscriptionToDatabase, result.channelId, ueberzug,
                    result.title, refresh=True, useTor=useTor,
                    circuitManager=circuitManager)
            refreshing = False
        except Exception:
            if not presentation.doYesNoQuery("Something went wrong. Try again?"):
                doChannelUnsubscribe(result.title)
                querying = False
                refreshing = False
    return indicator_classes.ReturnFromMenu

# this is the application level flow entered when the user has chosen to unsubscribe to 
# a channel
def doInteractiveChannelUnsubscribe():
    database = presentation.doWaitScreen('', parseDatabaseFile, DATABASE_PATH)
    if not database['title to id']:
        presentation.doNotify('You are not subscribed to any channels')
        return
    menuOptions = [
        MethodMenuDecision(
            channelTitle,
            doChannelUnsubscribe,
            channelTitle
        ) for channelTitle in database['title to id']
    ]
    menuOptions.insert(0, MethodMenuDecision('[Go back]', doReturnFromMenu))
    doMethodMenu("Which channel do you want to unsubscribe from?", menuOptions)

# this is the application level flow entered when the user has chosen a channel that it
# wants to unsubscribe from
def doChannelUnsubscribe(channelTitle):
    database = presentation.doWaitScreen('', parseDatabaseFile, DATABASE_PATH)
    if ueberzug:
        deleteThumbnailsByChannelTitle(database, channelTitle)
    removeSubscriptionFromDatabaseByChannelTitle(database, channelTitle)
    outputDatabaseToFile(database, DATABASE_PATH)
    return indicator_classes.ReturnFromMenu

# this is the application level flow entered when the user has chosen to browse
# its current subscriptions
def doInteractiveBrowseSubscriptions(useTor, circuitManager, ueberzug):
    database = presentation.doWaitScreen('', parseDatabaseFile, DATABASE_PATH)
    menuOptions = [
        MethodMenuDecision(
            FeedDescriber(
                database['feeds'][database['title to id'][channelTitle]],
                channelTitle
            ), doSelectVideoFromSubscription,
            database,
            channelTitle,
            useTor,
            circuitManager,
            ueberzug
        ) for channelTitle in database['title to id']
    ]

    adHocKeys = [
        MarkAllAsReadKey(
            channelId,
            i+1,
            database
        ) for i, channelId in enumerate(database['feeds'])
    ]

    if not menuOptions:
        presentation.doNotify('You are not subscribed to any channels')
        return

    menuOptions.insert(0, MethodMenuDecision('[Go back]', doReturnFromMenu))
    doMethodMenu("Which channel do you want to watch a video from?", menuOptions,
            adHocKeys = adHocKeys)

# this is the application level flow entered when the user has chosen a channel while
# browsing its current subscriptions;
# the user now gets to select a video from the channel to watch
def doSelectVideoFromSubscription(database, channelTitle, useTor, circuitManager, ueberzug):
    channelId = database['title to id'][channelTitle]
    videos = database['feeds'][channelId]
    menuOptions = [
        MethodMenuDecision(
            FeedVideoDescriber(video),
            doPlayVideoFromSubscription,
            database,
            video,
            useTor,
            circuitManager
        ) for video in videos
    ]

    adHocKeys = [
        MarkEntryAsReadKey(
            video,
            i+1
        ) for i, video in enumerate(videos)
    ]
    outputDatabaseToFile(database, DATABASE_PATH)
    menuOptions.insert(0, MethodMenuDecision("[Go back]", doReturnFromMenu))
    doMethodMenu("Which video do you want to watch?", menuOptions, 
            ueberzug = ueberzug, adHocKeys=adHocKeys)
    outputDatabaseToFile(database, DATABASE_PATH)

# this is the application level flow entered when the user has selected a video to watch
# while browsing its current subscriptions
def doPlayVideoFromSubscription(database, video, useTor, circuitManager):
    result = playVideo(video['link'], useTor, circuitManager = circuitManager)
    if not video['seen']:
        video['seen'] = result
        outputDatabaseToFile(database, DATABASE_PATH)

# this is the application level flow entered when the user is watching any video from
# YouTube
def playVideo(videoUrl, useTor=False, circuitManager = None):
    resolutionMenuList = [1080, 720, 480, 240]
    maxResolution = presentation.doSelectionQuery("Which maximum resolution do you want to use?",
            resolutionMenuList)
    result = False
    while not result:
        result = presentation.doWaitScreen("playing video...", openUrlInMpv, videoUrl, useTor=useTor,
                maxResolution=maxResolution, circuitManager = circuitManager)
        if result or not presentation.doYesNoQuery(f"Something went wrong when playing the " + \
                "video. Try again?"):
            break
    return result

# this is the application level flow entered when the user has chosen to refresh its
# subscriptions
def doRefreshSubscriptions(ueberzug ,useTor=False, circuitManager=None):
    database = presentation.doWaitScreen('', parseDatabaseFile, DATABASE_PATH)
    channelIdList = list(database['id to title'])
    refreshing = True
    while refreshing:
        try:
            auth = None
            if useTor and circuitManager is not None:
                auth = circuitManager.getAuth()
            presentation.doWaitScreen("refreshing subscriptions...", refreshSubscriptionsByChannelId,
                    channelIdList, ueberzug, useTor=useTor, auth=auth)
            refreshing = False
        except aiohttp.client_exceptions.ClientConnectionError:
            if not presentation.doYesNoQuery("Something went wrong. Try again?"):
                refreshing = False

def doStartupMenu(ueberzug):
    menuOptions = [
        MethodMenuDecision(
            "Yes",
            doStartupWithTor,
            ueberzug
        ), MethodMenuDecision(
            "No",
            doMainMenu,
            ueberzug
        )
    ]
    doMethodMenu("Do you want to use tor?", menuOptions, showItemNumber=False)

def doStartupWithTor(ueberzug):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        result = sock.connect_ex(('127.0.0.1',9050))
    if result != 0:
        menuOptions = [
            MethodMenuDecision(
                "Yes",
                doMainMenu,
                ueberzug
            ), MethodMenuDecision(
                "No",
                doNotifyAndReturnFromMenu,
                "Can't find Tor daemon. Exiting program."
            )
        ]
        doMethodMenu("Tor daemon not found on port 9050! " + \
                "Continue without tor?", menuOptions, showItemNumber=False)
    else:
        doMainMenu(ueberzug, useTor=True, circuitManager=CircuitManager())
    return indicator_classes.ReturnFromMenu



def doMainMenu(ueberzug, useTor=False, circuitManager=None):
    menuOptions =   [
        MethodMenuDecision( 
            "Search for video",
            doInteractiveSearchForVideo,
            ueberzug,
            useTor=useTor,
            circuitManager=circuitManager
        ), MethodMenuDecision( 
            "Refresh subscriptions",
            doRefreshSubscriptions,
            ueberzug,
            useTor=useTor,
            circuitManager=circuitManager
        ), MethodMenuDecision( 
            "Browse subscriptions",
            doInteractiveBrowseSubscriptions,
            useTor = useTor,
            circuitManager = circuitManager,
            ueberzug = ueberzug
        ), MethodMenuDecision( 
            "Subscribe to new channel",
            doInteractiveChannelSubscribe,
            ueberzug,
            useTor=useTor,
            circuitManager=circuitManager
        ), MethodMenuDecision( 
            "Unsubscribe from channel",
            doInteractiveChannelUnsubscribe,
        ), MethodMenuDecision(
            "Quit",
            doReturnFromMenu
        )
    ]
    doMethodMenu("What do you want to do?", menuOptions)
    return indicator_classes.ReturnFromMenu

# this is a function for managing menu hierarchies; once called, a menu presents
# application flows available to the user. If called from a flow selected in a previous
# method menu, the menu becomes a new branch one step further from the root menu
def doMethodMenu(query, menuOptions, ueberzug = None, showItemNumber = True, adHocKeys = []):
    index = 0
    try:
        while True:
            methodMenuDecision, index = presentation.doSelectionQuery(query, menuOptions, 
                    ueberzug = ueberzug,
                    initialIndex=index, queryStyle=indicator_classes.CombinedQuery,
                    showItemNumber=showItemNumber, adHocKeys=adHocKeys)
            try:
                result = methodMenuDecision.executeDecision()
            except KeyboardInterrupt:
                result = None
                pass
            if result is indicator_classes.ReturnFromMenu:
                return
    except KeyboardInterrupt:
        return

def doNotifyAndReturnFromMenu(message):
    presentation.doNotify(message)
    return indicator_classes.ReturnFromMenu

# this function is an application level flow which when selected from a method menu simply
# returns to the preceding menu (one step closer to the root menu)
def doReturnFromMenu():
    return indicator_classes.ReturnFromMenu


################
# main section #
################

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="A YouTube-client for managing subscriptions and watching videos anonymously over Tor without a Google account.")
    parser.add_argument('--use-thumbnails', 
            action='store_true')
    args = parser.parse_args()


    rnd = secrets.SystemRandom()
    ueberzug = None
    if args.use_thumbnails:
        import shutil
        import ueberzug.lib.v0 as ueberzug
        presentation.ueberzug = ueberzug

    if not os.path.isdir(YOUTUBE_RSS_DIR):
        os.mkdir(YOUTUBE_RSS_DIR)
    if not os.path.isdir(THUMBNAIL_DIR) and ueberzug:
        os.mkdir(THUMBNAIL_DIR)
    if not os.path.isfile(DATABASE_PATH):
        database = initiateYouTubeRssDatabase()
        presentation.doWaitScreen('', outputDatabaseToFile, database, DATABASE_PATH)
    else:
        database = presentation.doWaitScreen('', parseDatabaseFile, DATABASE_PATH)

    doStartupMenu(ueberzug)
