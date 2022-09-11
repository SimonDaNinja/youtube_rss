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

import socket
import os
import asyncio
import aiohttp
import argparse
import presentation
import indicator_classes
import constants
import connection_management
import shutil
import database_management

###########
# classes #
###########

"""
Other classes
"""

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
        return '/'.join([constants.THUMBNAIL_SEARCH_DIR, 
            self.videoQueryObject.videoId + '.jpg'])

class FeedDescriber:
    def __init__(self, feed, channelTitle):
        self.feed = feed
        self.channelTitle = channelTitle

    def __str__(self):
        return ''.join([self.channelTitle, ': (', str(sum([1 for video in self.feed
            if not video['seen']])),'/',str(len(self.feed)), ')'])

class AdHocKey:
    def __init__(self, key, item, activationIndex = constants.ANY_INDEX):
        self.key = key
        self.item = item
        self.activationIndex = activationIndex

    def isValidIndex(self, index):
        if self.activationIndex == constants.ANY_INDEX:
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
Functions for managing database persistence between user sessions
"""

# use this function to add a subscription to the database
def addSubscriptionToDatabase(channelId, ueberzug, channelTitle, refresh=False,
        useTor=False, circuitManager=None):
    database = database_management.parseDatabaseFile(constants.DATABASE_PATH)
    database['feeds'][channelId] = []
    database['id to title'][channelId] = channelTitle
    database['title to id'][channelTitle] = channelId
    database_management.outputDatabaseToFile(database, constants.DATABASE_PATH)
    auth = None
    if circuitManager is not None and useTor:
        auth = circuitManager.getAuth()
    if refresh:
        asyncio.run(database_management.refreshSubscriptionsByChannelId( [channelId], ueberzug, useTor=useTor, 
                auth=auth))




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
    database_management.outputDatabaseToFile(database, constants.DATABASE_PATH)

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
            resultList = presentation.doWaitScreen("Getting video results...", 
                    connection_management.getVideoQueryResults, query, ueberzug, 
                    useTor=useTor, auth=auth)
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
    if os.path.isdir(constants.THUMBNAIL_SEARCH_DIR):
        shutil.rmtree(constants.THUMBNAIL_SEARCH_DIR)


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
                    connection_management.getChannelQueryResults, query, useTor=useTor, 
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
        except Exception as e:
            if not presentation.doYesNoQuery("Something went wrong. Try again?"):
                querying = False

# this is the application level flow entered when the user has chosen a channel that it
# wants to subscribe to
def doChannelSubscribe(result, useTor, circuitManager, ueberzug):
    database = presentation.doWaitScreen('', database_management.parseDatabaseFile, constants.DATABASE_PATH)
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
        except Exception as e:
            if not presentation.doYesNoQuery("Something went wrong. Try again?"):
                doChannelUnsubscribe(result.title)
                querying = False
                refreshing = False
    return indicator_classes.ReturnFromMenu

# this is the application level flow entered when the user has chosen to unsubscribe to 
# a channel
def doInteractiveChannelUnsubscribe():
    database = presentation.doWaitScreen('', database_management.parseDatabaseFile, constants.DATABASE_PATH)
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
    database = presentation.doWaitScreen('', database_management.parseDatabaseFile, constants.DATABASE_PATH)
    if ueberzug:
        database_management.deleteThumbnailsByChannelTitle(database, channelTitle)
    database_management.removeSubscriptionFromDatabaseByChannelTitle(database, channelTitle)
    database_management.outputDatabaseToFile(database, constants.DATABASE_PATH)
    return indicator_classes.ReturnFromMenu

# this is the application level flow entered when the user has chosen to browse
# its current subscriptions
def doInteractiveBrowseSubscriptions(useTor, circuitManager, ueberzug):
    database = presentation.doWaitScreen('', database_management.parseDatabaseFile, constants.DATABASE_PATH)
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
    database_management.outputDatabaseToFile(database, constants.DATABASE_PATH)
    menuOptions.insert(0, MethodMenuDecision("[Go back]", doReturnFromMenu))
    doMethodMenu("Which video do you want to watch?", menuOptions, 
            ueberzug = ueberzug, adHocKeys=adHocKeys)
    database_management.outputDatabaseToFile(database, constants.DATABASE_PATH)

# this is the application level flow entered when the user has selected a video to watch
# while browsing its current subscriptions
def doPlayVideoFromSubscription(database, video, useTor, circuitManager):
    result = playVideo(video['link'], useTor, circuitManager = circuitManager)
    if not video['seen']:
        video['seen'] = result
        database_management.outputDatabaseToFile(database, constants.DATABASE_PATH)

# this is the application level flow entered when the user is watching any video from
# YouTube
def playVideo(videoUrl, useTor=False, circuitManager = None):
    resolutionMenuList = [1080, 720, 480, 240]
    maxResolution = presentation.doSelectionQuery("Which maximum resolution do you want to use?",
            resolutionMenuList)
    result = False
    while not result:
        result = presentation.doWaitScreen("playing video...", connection_management.openUrlInMpv,
                videoUrl, useTor=useTor, maxResolution=maxResolution, circuitManager = circuitManager)
        if result or not presentation.doYesNoQuery(f"Something went wrong when playing the " + \
                "video. Try again?"):
            break
    return result

# this is the application level flow entered when the user has chosen to refresh its
# subscriptions
def doRefreshSubscriptions(ueberzug ,useTor=False, circuitManager=None):
    database = presentation.doWaitScreen('', database_management.parseDatabaseFile, 
            constants.DATABASE_PATH)
    channelIdList = list(database['id to title'])
    refreshing = True
    while refreshing:
        try:
            auth = None
            if useTor and circuitManager is not None:
                auth = circuitManager.getAuth()
            presentation.doWaitScreen("refreshing subscriptions...", 
                    database_management.refreshSubscriptionsByChannelId, channelIdList, 
                    ueberzug, useTor=useTor, auth=auth)
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
        doMainMenu(ueberzug, useTor=True, circuitManager=connection_management.CircuitManager())
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


    ueberzug = None
    if args.use_thumbnails:
        import ueberzug.lib.v0 as ueberzug

    if not os.path.isdir(constants.YOUTUBE_RSS_DIR):
        os.mkdir(constants.YOUTUBE_RSS_DIR)
    if not os.path.isdir(constants.THUMBNAIL_DIR) and ueberzug:
        os.mkdir(constants.THUMBNAIL_DIR)
    if not os.path.isfile(constants.DATABASE_PATH):
        database = database_management.initiateYouTubeRssDatabase()
        presentation.doWaitScreen('', database_management.outputDatabaseToFile, database, constants.DATABASE_PATH)
    else:
        database = presentation.doWaitScreen('', database_management.parseDatabaseFile, constants.DATABASE_PATH)

    doStartupMenu(ueberzug)
