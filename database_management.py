import json
import os
import constants
import asyncio
import connection_management

# Database is always stored as a dict()

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

# use this function to initialize the database (dict format so it's easy to save as json)
def initiateYouTubeRssDatabase():
    database = {}
    database['feeds'] = {}
    database['id to title'] = {}
    database['title to id'] = {}
    return database

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
    outputDatabaseToFile(database, constants.DATABASE_PATH)

# use this function to retrieve new RSS entries for a subscription and add them to
# a database
async def refreshSubscriptionsByChannelId(channelIdList, useTor=False, 
        auth=None):
    database = parseDatabaseFile(constants.DATABASE_PATH)
    localFeeds = database['feeds']
    tasks = []

    semaphore = asyncio.Semaphore(constants.MAX_CONNECTIONS)

    for channelId in channelIdList:
        localFeed = localFeeds[channelId]
        tasks.append(asyncio.create_task(refreshSubscriptionByChannelId(channelId, localFeed, 
            semaphore=semaphore, useTor=useTor, auth=auth)))

    for task in tasks:
        await task

    outputDatabaseToFile(database, constants.DATABASE_PATH)

async def refreshSubscriptionByChannelId(channelId, localFeed, semaphore, useTor=False,
        auth=None):
    task = asyncio.create_task(connection_management.getRssEntriesFromChannelId(channelId, 
            semaphore=semaphore, useTor=useTor, auth=auth))
    remoteFeed = await task
    if remoteFeed is not None:
        remoteFeed.reverse()
        for entry in remoteFeed:
            filteredEntry = connection_management.getRelevantDictFromFeedParserDict(entry)

            filteredEntryIsNew = True
            for i, localEntry in enumerate(localFeed):
                if localEntry['id'] == filteredEntry['id']:
                    filteredEntryIsNew = False
                    # in case any relevant data about the entry is changed, update it
                    filteredEntry['seen'] = localEntry['seen']
                    localFeed[i] = filteredEntry
                    break
            if filteredEntryIsNew:
                localFeed.insert(0, filteredEntry)

# use this function to add a subscription to the database
def addSubscriptionToDatabase(channelId, channelTitle, refresh=False,
        useTor=False, circuitManager=None):
    database = parseDatabaseFile(constants.DATABASE_PATH)
    database['feeds'][channelId] = []
    database['id to title'][channelId] = channelTitle
    database['title to id'][channelTitle] = channelId
    outputDatabaseToFile(database, constants.DATABASE_PATH)
    auth = None
    if circuitManager is not None and useTor:
        auth = circuitManager.getAuth()
    if refresh:
        asyncio.run(refreshSubscriptionsByChannelId( [channelId], useTor=useTor, 
                auth=auth))
