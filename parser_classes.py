from html.parser import HTMLParser
import re

"""
Parser classes
"""

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
                        '\[\{"url":"([^"]+)","width":[0-9]+,"height":[0-9]+\},\{"url"' + \
                        ':"[^"]+","width":[0-9]+,"height":[0-9]+\}\]\},"title":\{' + \
                        '"runs":\[\{"text":"[^"]+"\}\],"accessibility":\{' + \
                        '"accessibilityData":\{"label":"([^"]+)"\}')
                tupleList = pattern.findall(data)
                resultList = []
                for tup in tupleList:
                    resultList.append(VideoQueryObject(videoId = tup[0], 
                        thumbnail = tup[1], title = tup[2]))
                self.resultList = resultList

"""
help classes
"""
# contains information from one result item from channel query
class ChannelQueryObject:
    def __init__(self, channelId = None, title = None):
        self.channelId = channelId
        self.title     = title

    def __str__(self):
        return f"{self.title}  --  (channel ID {self.channelId})"

# contains information from one result item from video query
class VideoQueryObject:
    def __init__(self, videoId = None, thumbnail=None, title = None):
        self.videoId   = videoId
        self.thumbnail = thumbnail
        self.title     = title
        if videoId is not None:
            self.url = f"http://youtube.com/watch?v={videoId}"
        else:
            self.url = None

    def __str__(self):
        return f"{self.title}"