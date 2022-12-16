import os

HOME = os.environ.get('HOME')
YOUTUBE_RSS_DIR = '/'.join([HOME,'.youtube_rss'])
DATABASE_PATH  = '/'.join([YOUTUBE_RSS_DIR, 'database'])
LOG_PATH = '/'.join([YOUTUBE_RSS_DIR, 'log'])

ANY_INDEX = -1
MAX_CONNECTIONS=30
