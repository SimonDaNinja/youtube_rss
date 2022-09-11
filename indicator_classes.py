# Parent to all indicator classes
class IndicatorClass:
    def __init__(self):
        raise InstantiateIndicatorClassError

class NoCanvas(IndicatorClass):
    def __init__(self):
        pass

    def __exit__(self, dummy1, dummy2, dummy3):
        pass

    def __enter__(self):
        pass

# returned from menu method to indicate that application flow should step
# closer to the root menu
class ReturnFromMenu(IndicatorClass):
    pass

# indicates whether selection query should return by index, item or both
class QueryStyle(IndicatorClass):
    pass

# indicates that selection query should return by index
class IndexQuery(QueryStyle):
    pass

# indicates that selection query should return by item
class ItemQuery(QueryStyle):
    pass

# indicates that selection query should return by both item and index
class CombinedQuery(QueryStyle):
    pass

"""
Exception classes
"""

class InstantiateIndicatorClassError(Exception):
    def __init__(self, message="Can't instantiate an indicator class!"):
        self.message = message
        Exception.__init__(self, self.message)
