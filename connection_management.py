import feedparser
import asyncio
import aiohttp
import constants
import urllib
import subprocess
from aiohttp_socks import ProxyConnector
import parser_classes
from aiohttp_socks import ProxyType
import time
import secrets
import os
import shutil


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

# use this function to generate new socks5 authentication (for tor stream 
# isolation)
def generateNewSocks5Auth(userNameLen = 30, passwordLen = 30):
    rnd = secrets.SystemRandom()
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
    semaphore = asyncio.Semaphore(constants.MAX_CONNECTIONS)
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
    semaphore = asyncio.Semaphore(constants.MAX_CONNECTIONS)
    getTask = asyncio.create_task(getHttpContent(url, semaphore=semaphore, useTor=useTor, 
        auth=auth))
    htmlContent = await getTask
    parser = parser_classes.VideoQueryParser()
    parser.feed(htmlContent)
    if ueberzug:
        if os.path.isdir(constants.THUMBNAIL_SEARCH_DIR):
            shutil.rmtree(constants.THUMBNAIL_SEARCH_DIR)
        os.mkdir(constants.THUMBNAIL_SEARCH_DIR)
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

async def getSearchThumbnailFromSearchResult(result, ueberzug, semaphore, useTor=False, auth=None):
    videoId = result.videoId.split(':')[-1]
    thumbnailFileName = '/'.join([constants.THUMBNAIL_SEARCH_DIR, videoId +
            '.jpg'])
    getTask = asyncio.create_task(getHttpContent(result.thumbnail, semaphore=semaphore, useTor=useTor,
            auth = auth, contentType='bytes'))
    thumbnailContent = await getTask
    result.thumbnailFile = thumbnailFileName
    open(thumbnailFileName, 'wb').write(thumbnailContent)

async def getSearchThumbnails(resultList, ueberzug, semaphore, useTor = False, auth=None):
    tasks = []
    for result in resultList:
        tasks.append(asyncio.create_task(getSearchThumbnailFromSearchResult(result, 
            ueberzug, semaphore = semaphore, useTor=useTor, auth=auth)))
    for task in tasks:
        await task