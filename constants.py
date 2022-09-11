import os

HOME = os.environ.get('HOME')
YOUTUBE_RSS_DIR = '/'.join([HOME,'.youtube_rss'])
THUMBNAIL_DIR = '/'.join([YOUTUBE_RSS_DIR, 'thumbnails'])
THUMBNAIL_SEARCH_DIR = '/'.join([THUMBNAIL_DIR, 'search'])
DATABASE_PATH  = '/'.join([YOUTUBE_RSS_DIR, 'database'])
LOG_PATH = '/'.join([YOUTUBE_RSS_DIR, 'log'])

ANY_INDEX = -1
MAX_CONNECTIONS=30
