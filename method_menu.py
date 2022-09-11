import constants
import presentation
import indicator_classes

"""
classes
"""

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

"""
functions
"""

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

