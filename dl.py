#!/usr/bin/env python3

# This file differs from dl.py in that it utilizes youtube-dlp, a fork with more features (such as sponsorblock)
import os.path

from time import mktime
from datetime import datetime, timedelta
import feedparser
import yt_dlp
import opml
from yt_dlp.postprocessor.sponsorblock import SponsorBlockPP

VIDEO_DIR = '/data/data/com.termux/files/home/storage/movies/youtube/'
DATA_DIR = '/data/data/com.termux/files/home/.config/youtube-dlp-subscriptions/'

# note: if using sponsorblock, only '.ass/.lrc' file formats will be chopped alongside video.
# All other formats will have mis-synced subtitles
YDL_OPTS = {
  'ignoreerrors': True,
  'outtmpl': VIDEO_DIR + '/%(uploader)s_%(id)s.%(ext)s',
  'ffmpeg-location': '/usr/bin/ffmpeg',
  'postprocessors': [{
    'key': 'SponsorBlock',
    'when': 'pre_process'
  }, {
    'key': 'ModifyChapters',
    'remove_sponsor_segments': SponsorBlockPP.CATEGORIES.keys(),
    'force_keyframes': True,
  }],
  'write_subtitles': True, # TODO: doesn't seem to work
  'nopart': True,
  #'subtitleslang'
  'download_archive' : os.path.join(DATA_DIR, 'download_archive'),
  'format': ('best[height=1080]'
      '/(bestvideo*[height=1080]+bestaudio)'
      '/best[height=720]'
      '/(bestvideo*[height=720]+bestaudio)'
      '/(bestvideo*+bestaudio)/best'),
}

# TODO: easy way to add a channel

def main():
    outline = opml.parse(os.path.join(DATA_DIR, 'subs.xml'))

    ptime = datetime.today() - timedelta(days=2)

    for item in outline[0]:
        feed = feedparser.parse(item.xmlUrl)
        name_filter = ""
        if hasattr(item, "filter"):
            name_filter = item.filter

        videos = []
        for video in reversed(feed['items']):
            timef = video['published_parsed']
            dt = datetime.fromtimestamp(mktime(timef))
            if dt < ptime:
                continue
            if name_filter not in video['title']:
                # print(f"skipping {video['title']}")
                continue
            videos.append(video['link'])
        if not videos:
            continue
        print(f'{item.text}')
        item_opts = YDL_OPTS.copy()
        for opt in item:
            item_opts[opt.text] = opt.value
        with yt_dlp.YoutubeDL(item_opts) as ydl:
            ydl.download(videos)

    input(".")
if __name__ == '__main__':
    main()
