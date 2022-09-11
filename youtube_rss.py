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
import aiohttp
import argparse
import presentation
import indicator_classes
import constants
import connection_management
import shutil
import database_management
import method_menu

class MarkAllAsReadKey(method_menu.AdHocKey):
    def __init__(self, channelId, activationIndex, database, key=ord('a')):
        item =  method_menu.MethodMenuDecision(
                    f"mark all by {channelId} as read",
                    doMarkChannelAsRead,
                    database,
                    channelId
                )
        method_menu.AdHocKey.__init__(self, key=key, item=item, activationIndex=activationIndex)

class MarkEntryAsReadKey(method_menu.AdHocKey):
    def __init__(self, video, activationIndex, key=ord('a')):
        item =  method_menu.MethodMenuDecision(
                    "mark video as read",
                    lambda video : video.update({'seen':(not video['seen'])}),
                    video
                )
        method_menu.AdHocKey.__init__(self, key=key, item=item, activationIndex=activationIndex)


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
                    method_menu.MethodMenuDecision(
                        method_menu.VideoQueryObjectDescriber(result),
                        playVideo,
                        result.url,
                        useTor=useTor,
                        circuitManager=circuitManager
                    ) for result in resultList
                ]
                menuOptions.insert(0, method_menu.MethodMenuDecision("[Go back]", method_menu.doReturnFromMenu))
                method_menu.doMethodMenu(f"Search results for '{query}':",menuOptions, ueberzug=ueberzug)
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
                    method_menu.MethodMenuDecision(
                        str(result),
                        doChannelSubscribe,
                        result=result,
                        useTor=useTor,
                        circuitManager=circuitManager,
                        ueberzug=ueberzug
                    ) for result in resultList
                ]
                menuOptions.insert(0, method_menu.MethodMenuDecision('[Go back]', method_menu.doReturnFromMenu))
                method_menu.doMethodMenu(f"search results for '{query}', choose which " + \
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
                    method_menu.addSubscriptionToDatabase, result.channelId, ueberzug,
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
        method_menu.MethodMenuDecision(
            channelTitle,
            doChannelUnsubscribe,
            channelTitle
        ) for channelTitle in database['title to id']
    ]
    menuOptions.insert(0, method_menu.MethodMenuDecision('[Go back]', method_menu.doReturnFromMenu))
    method_menu.doMethodMenu("Which channel do you want to unsubscribe from?", menuOptions)

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
        method_menu.MethodMenuDecision(
            method_menu.FeedDescriber(
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

    menuOptions.insert(0, method_menu.MethodMenuDecision('[Go back]', method_menu.doReturnFromMenu))
    method_menu.doMethodMenu("Which channel do you want to watch a video from?", menuOptions,
            adHocKeys = adHocKeys)

# this is the application level flow entered when the user has chosen a channel while
# browsing its current subscriptions;
# the user now gets to select a video from the channel to watch
def doSelectVideoFromSubscription(database, channelTitle, useTor, circuitManager, ueberzug):
    channelId = database['title to id'][channelTitle]
    videos = database['feeds'][channelId]
    menuOptions = [
        method_menu.MethodMenuDecision(
            method_menu.FeedVideoDescriber(video),
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
    menuOptions.insert(0, method_menu.MethodMenuDecision("[Go back]", method_menu.doReturnFromMenu))
    method_menu.doMethodMenu("Which video do you want to watch?", menuOptions, 
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
        method_menu.MethodMenuDecision(
            "Yes",
            doStartupWithTor,
            ueberzug
        ), method_menu.MethodMenuDecision(
            "No",
            doMainMenu,
            ueberzug
        )
    ]
    method_menu.doMethodMenu("Do you want to use tor?", menuOptions, showItemNumber=False)

def doStartupWithTor(ueberzug):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        result = sock.connect_ex(('127.0.0.1',9050))
    if result != 0:
        menuOptions = [
            method_menu.MethodMenuDecision(
                "Yes",
                doMainMenu,
                ueberzug
            ), method_menu.MethodMenuDecision(
                "No",
                method_menu.doNotifyAndReturnFromMenu,
                "Can't find Tor daemon. Exiting program."
            )
        ]
        method_menu.doMethodMenu("Tor daemon not found on port 9050! " + \
                "Continue without tor?", menuOptions, showItemNumber=False)
    else:
        doMainMenu(ueberzug, useTor=True, circuitManager=connection_management.CircuitManager())
    return indicator_classes.ReturnFromMenu



def doMainMenu(ueberzug, useTor=False, circuitManager=None):
    menuOptions =   [
        method_menu.MethodMenuDecision( 
            "Search for video",
            doInteractiveSearchForVideo,
            ueberzug,
            useTor=useTor,
            circuitManager=circuitManager
        ), method_menu.MethodMenuDecision( 
            "Refresh subscriptions",
            doRefreshSubscriptions,
            ueberzug,
            useTor=useTor,
            circuitManager=circuitManager
        ), method_menu.MethodMenuDecision( 
            "Browse subscriptions",
            doInteractiveBrowseSubscriptions,
            useTor = useTor,
            circuitManager = circuitManager,
            ueberzug = ueberzug
        ), method_menu.MethodMenuDecision( 
            "Subscribe to new channel",
            doInteractiveChannelSubscribe,
            ueberzug,
            useTor=useTor,
            circuitManager=circuitManager
        ), method_menu.MethodMenuDecision( 
            "Unsubscribe from channel",
            doInteractiveChannelUnsubscribe,
        ), method_menu.MethodMenuDecision(
            "Quit",
            method_menu.doReturnFromMenu
        )
    ]
    method_menu.doMethodMenu("What do you want to do?", menuOptions)
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
