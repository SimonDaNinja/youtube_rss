import curses
import inspect
import indicator_classes
import asyncio

HIGHLIGHTED = 1
NOT_HIGHLIGHTED = 2


# This function displays a message while the user waits for a function to execute
def doWaitScreen(message, cb, *args, **kwargs):
    return curses.wrapper(doWaitScreenNcurses, message, cb, *args, **kwargs)

# This function is where the Ncurses level of doWaitScreen starts.
# It should never be called directly, but always through doWaitScreen!
def doWaitScreenNcurses(stdscr, message, cb, *args, **kwargs):
    curses.curs_set(0)
    curses.init_pair(HIGHLIGHTED, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(NOT_HIGHLIGHTED, curses.COLOR_WHITE, curses.COLOR_BLACK)
    printMenu(message, [], stdscr, 0, showItemNumber=False)
    if inspect.iscoroutinefunction(cb):
        return asyncio.run(cb(*args, **kwargs))
    else:
        return cb(*args, **kwargs)

# This Function gets a yes/no response to some query from the user
def doYesNoQuery(query):
    return curses.wrapper(doYnQueryNcurses, query)

# This function is where the Ncurses level of doYesNoQuery starts.
# It should never be called directly, but always through doYesNoQuery!
def doYnQueryNcurses(stdscr, query):
    return doSelectionQueryNcurses(stdscr, query, ['yes','no'], 
            indicator_classes.ItemQuery, showItemNumber=False) == 'yes'

# This function lets the user choose an object from a list
def doSelectionQuery(query, options, queryStyle=indicator_classes.ItemQuery, 
        initialIndex=None, showItemNumber=True, adHocKeys=[]):
    return curses.wrapper(doSelectionQueryNcurses, query, options,
            queryStyle=queryStyle, initialIndex=initialIndex,
            showItemNumber=showItemNumber, adHocKeys=adHocKeys)

# This function is where the Ncurses level of doSelectionQuery starts.
# It should never be called directly, but always through doSelectionQuery!
def doSelectionQueryNcurses(stdscr, query, options, 
        queryStyle=indicator_classes.ItemQuery, initialIndex=None, showItemNumber=True, 
        adHocKeys=[]):
    curses.curs_set(0)
    curses.init_pair(HIGHLIGHTED, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(NOT_HIGHLIGHTED, curses.COLOR_WHITE, curses.COLOR_BLACK)
    jumpNumList = []
    if initialIndex is not None:
        choiceIndex = initialIndex
    else:
        choiceIndex = 0
    while True:
        printMenu(query, options, stdscr, choiceIndex, showItemNumber=showItemNumber,
                jumpNumStr = ''.join(jumpNumList))
        key = stdscr.getch()
        # Ad hoc keys should always take first precedence

        if key in adHocKeys:
            for adHocKey in adHocKeys:
                if adHocKey.isValidIndex(choiceIndex):
                    if queryStyle is indicator_classes.ItemQuery:
                        return adHocKey.item
                    elif queryStyle is indicator_classes.IndexQuery:
                        return choiceIndex
                    elif queryStyle is indicator_classes.CombinedQuery:
                        return adHocKey.item, choiceIndex

        elif key in [curses.KEY_UP, ord('k')]:
            jumpNumList = []
            choiceIndex = (choiceIndex-1)%len(options)
        elif key in [curses.KEY_DOWN, ord('j')]:
            jumpNumList = []
            choiceIndex = (choiceIndex+1)%len(options)
        elif key in [ord(digit) for digit in '1234567890']:
            if len(jumpNumList) < 6:
                jumpNumList.append(chr(key))
        elif key in [curses.KEY_BACKSPACE, ord('\b'), ord('\x7f')]:
            if jumpNumList:
                jumpNumList.pop()
        elif key == ord('g'):
            jumpNumList = []
            choiceIndex = 0
        elif key == ord('G'):
            jumpNumList = []
            choiceIndex = len(options)-1
        elif key in [ord('q'), ord('h'), curses.KEY_LEFT]:
            raise KeyboardInterrupt
        elif key in [curses.KEY_ENTER, 10, 13, ord('l'), curses.KEY_RIGHT]:
            if jumpNumList:
                jumpNum = int(''.join(jumpNumList))
                choiceIndex = min(jumpNum-1, len(options)-1)
                jumpNumList = []
            elif queryStyle is indicator_classes.ItemQuery:
                return options[choiceIndex]
            elif queryStyle is indicator_classes.IndexQuery:
                return choiceIndex
            elif queryStyle is indicator_classes.CombinedQuery:
                return options[choiceIndex], choiceIndex
            else:
                raise UnknownQueryStyle(f"Unknown query style: {queryStyle}")

    
# This function displays a piece of information to the user until they confirm having
# seen it
def doNotify(message):
    doSelectionQuery(message, ['ok'], showItemNumber=False)

# This function gets a string of written input from the user
def doGetUserInput(query, maxInputLength=40):
    return curses.wrapper(doGetUserInputNcurses, query, maxInputLength=maxInputLength)

# This function is where the Ncurses level of doGetUserInput starts.
# It should never be called directly, but always through doGetUserInput!
def doGetUserInputNcurses(stdscr, query, maxInputLength=40):
    curses.curs_set(0)
    curses.init_pair(HIGHLIGHTED, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(NOT_HIGHLIGHTED, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.curs_set(0)
    curserPosition = 0
    userInputChars = []
    while True:
        printMenu(query, [''.join(userInputChars), ''.join(['—' if i==curserPosition else
            ' ' for i in range(maxInputLength)])], stdscr, 0,
                xAlignment=maxInputLength//2, showItemNumber=False)
        key = stdscr.getch()
        if key in [curses.KEY_BACKSPACE, ord('\b'), ord('\x7f')]:
            deleteIndex = curserPosition-1
            if deleteIndex >= 0 : userInputChars.pop(curserPosition-1)
            curserPosition = max(0, curserPosition-1)
        elif key in [curses.KEY_DC]:
            deleteIndex = curserPosition+1
            if deleteIndex <= len(userInputChars) : userInputChars.pop(curserPosition)
        elif key in [curses.KEY_ENTER, 10, 13]:
            return ''.join(userInputChars)
        elif key == curses.KEY_LEFT:
            curserPosition = max(0, curserPosition-1)
        elif key == curses.KEY_RIGHT:
            curserPosition = min(len(userInputChars), curserPosition+1)
        elif key == curses.KEY_RESIZE:
            pass
        elif len(userInputChars) < maxInputLength:
            userInputChars.insert(curserPosition,chr(key))
            curserPosition = min(maxInputLength, curserPosition+1)

# This function is used to visually represent a query and a number of menu items to the 
# user, by using nCurses. It is used for all text printing in the program (even where
# no application level menu is presented, i.e by simply not providing a query and no
# menu objects)
def printMenu(query, menu, stdscr, choiceIndex, xAlignment=None, showItemNumber=True, 
        jumpNumStr=''):
    stdscr.clear()
    height, width = stdscr.getmaxyx()
    screenCenterX = width//2
    screenCenterY = height//2
    nRowsToPrint = (len(menu)+2)

    if xAlignment is not None:
        itemX = max(min(screenCenterX - xAlignment, width-2),0)
    elif menu:
        menuWidth = max([len(f"{i+1}: {item}" if showItemNumber else str(item)) for i, 
            item in enumerate(menu)])
        itemX = max(screenCenterX - menuWidth//2, 0)
    else:
        itemX = None
    
    if itemX != 0 and itemX is not None:
        itemX = max(min(itemX, width-2),0)

    jumpNumStr = jumpNumStr[:max(min(len(jumpNumStr), width-1),0)]
    if jumpNumStr:
        stdscr.addstr(0,0,jumpNumStr)

    offset = 0
    titleY = screenCenterY-nRowsToPrint//2
    if nRowsToPrint >= height-2:
        yTitleTheoretical = screenCenterY - nRowsToPrint//2
        ySelectedTheoretical = (yTitleTheoretical + 2 + choiceIndex)
        yLastTheoretical = yTitleTheoretical + nRowsToPrint-1
        offset = min(max(ySelectedTheoretical-screenCenterY, yTitleTheoretical), 
                yLastTheoretical - (height-2))
    titleY -= offset

    titleX = max(screenCenterX-(len(query)//2),0)
    if titleX != 0:
        titleX = max(min(abs(titleX), width)*(titleX//abs(titleX)),0)
    if len(query) >= width-1:
        query = query[0:width-1]
    if titleY >= 0 and titleY<height-1:
        stdscr.addstr(titleY, titleX, query)
    for i, item in enumerate(menu):
        itemString = f"{i+1}: {item}" if showItemNumber else str(item)
        if itemX + len(itemString) >= width-1:
            itemString = itemString[:max((width-itemX-2),0)]
        attr = curses.color_pair(HIGHLIGHTED if i == choiceIndex else NOT_HIGHLIGHTED)
        stdscr.attron(attr)
        itemY = screenCenterY - nRowsToPrint//2 + i + 2 - offset
        if itemY >= 0 and itemY < height-1 and itemString:
            stdscr.addstr(itemY, itemX, itemString)
        stdscr.attroff(attr)
    stdscr.refresh()

"""
Exception classes
"""

# indicates that the provided query style is not supported
class UnknownQueryStyle(Exception):
    pass
