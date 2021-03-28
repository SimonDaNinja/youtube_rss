#! /usr/bin/env python3
from html.parser import HTMLParser
import requests as req
import re
import feedparser
try:
    from tor_requests.tor_requests import getHttpResponseUsingSocks5
    from tor_requests.tor_requests import generateNewSocks5Auth
except:
    print("you probably haven't run the command\ngit submodule update --init --recursive")
    exit()
import subprocess


###########
# classes #
###########

# parser classes #

# Parser used for extracting an RSS Adress from channel page HTML
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
    return response.text

# use this function to ask an interactive yes/no question to the user
def doYnQuery(query):
    yn = ""
    while True:
        yn = input(query + ' [y/n] ').lower()
        if yn not in ['y', 'n']:
            print('invalid response!')
        else:
            break
    if yn == 'y':
        return True
    return False

# central functions #

# if you have a channel url, you can use this function to extract the rss address
def getRssAddressFromChannelUrl(url, getHttpContent = req.get):
    response = getHttpContent(url)
    htmlContent = response.text
    parser = RssAddressParser()
    parser.feed(htmlContent)
    return parser.rssAddress

# if you have a channel id, you can use this function to get the rss address
def getRssAddressFromChannelId(channelId):
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channelId}"

# use this function to get query results from searching for a channel
def getChannelQueryResults(query, getHttpContent = req.get):
    htmlContent = getChannelQueryHtml(query, getHttpContent = getHttpContent)
    parser = ChannelQueryParser()
    parser.feed(htmlContent)
    return parser.resultList

# use this function to get rss entries from channel id
def getRssEntriesFromChannelId(channelId, getHttpContent = req.get):
    rssAdress = getRssAddressFromChannelId(channelId)
    response = getHttpContent(rssAdress)
    rssContent = response.text
    entries = feedparser.parse(rssContent)['entries']
    return entries

def openUrlInMpv(url, useTor=False):
    while True:
        command = ['mpv']
        if useTor:
            username, password = generateNewSocks5Auth()
            command.append(f'--ytdl-raw-options=proxy=[socks5://{username}:{password}@127.0.0.1:9050]')
        command.append(url)
        mpvProcess = subprocess.Popen(command, stdout = subprocess.DEVNULL, stderr = subprocess.STDOUT)
        mpvProcess.wait()
        result = mpvProcess.poll()
        if result in [0,4] or not doYnQuery(f"Something went wrong when playing the video (exit code: {result}). Try again?"):
            break

if __name__ == '__main__':
    useTor = doYnQuery("Do you want to use tor?")
    if useTor:
        getHttpContent = getHttpResponseUsingSocks5
    else:
        getHttpContent = req.get
    query = input("enter channel to search for: ")
    resultList = getChannelQueryResults(query)
    print(f"these channels were found by searching for '{query}':\n")
    for i, result in enumerate(resultList):
        print(f"search result {i+1}:\nTitle: {result.title}\nChannel ID: {result.channelId}\nRSS feed: {getRssAddressFromChannelId(result.channelId)}\n")
        if doYnQuery('Is this the channel whose RSS you want to parse?'):
            entries = getRssEntriesFromChannelId(result.channelId, getHttpContent = getHttpContent)
            break
    
    print("\nthese videos are in the rss feed:\n")
    for entry in entries:
        print(f'video title: {entry.title}\nvideo url: {entry.link}\n')
        if doYnQuery("Do you want to view this video?"):
            openUrlInMpv(entry.link, useTor)
            break
