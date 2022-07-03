#!/usr/bin/env python3

# This file differs from dl.py in that it utilizes youtube-dlp, a fork with more features (such as sponsorblock)
import os.path
import json
import re

from time import mktime
from datetime import datetime, timedelta
import feedparser
import yt_dlp
from yt_dlp.postprocessor.sponsorblock import SponsorBlockPP

VIDEO_DIR = "/data/data/com.termux/files/home/storage/movies/youtube/"
DATA_DIR = "/data/data/com.termux/files/home/.config/youtube-dlp-subscriptions/"

# note: if using sponsorblock, only '.ass/.lrc' file formats will be chopped alongside video.
# All other formats will have mis-synced subtitles
YDL_OPTS = {
    "ignoreerrors": True,
    "outtmpl": VIDEO_DIR + "/%(uploader)s_%(id)s.%(ext)s",
    "ffmpeg-location": "/usr/bin/ffmpeg",
    "postprocessors": [
        {"key": "SponsorBlock", "when": "pre_process"},
        {
            "key": "ModifyChapters",
            "remove_sponsor_segments": SponsorBlockPP.CATEGORIES.keys(),
            "force_keyframes": True,
        },
    ],
    "write_subtitles": True,  # TODO: doesn't seem to work
    "nopart": True,
    #'subtitleslang'
    "download_archive": os.path.join(DATA_DIR, "download_archive"),
    "format": (
        "best[height=1080]"
        "/(bestvideo*[height=1080]+bestaudio)"
        "/best[height=720]"
        "/(bestvideo*[height=720]+bestaudio)"
        "/(bestvideo*+bestaudio)/best"
    ),
}


def read_subs():
    path = os.path.join(DATA_DIR, "subs.json")
    if not os.path.isfile(path):
        return []

    with open(path, encoding="utf-8") as file:
        return json.loads(file.read())


def write_subs(subs):
    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR)
    with open(os.path.join(DATA_DIR, "subs.json"), "w", encoding="utf-8") as file:
        file.write(json.dumps(subs))

#TODO: regex match to extract channel id
def subscribe(url):
    reg = re.search(r'(?<=youtube.com/channel/)[\w]*', url)
    if not reg:
        print(f'failed finding channel id in {url}')
        return
    channel_id = reg.group()
    subs = read_subs()
    subs.append({"id": channel_id})
    write_subs(subs)


def main():
    outline = read_subs()

    ptime = datetime.today() - timedelta(days=2)

    for item in outline:
        url = f'https://www.youtube.com/feeds/videos.xml?channel_id={item["id"]}'
        feed = feedparser.parse(url)
        name_filter = ""
        if "filter" in item:
            name_filter = item.filter

        videos = []
        for video in reversed(feed["items"]):
            timef = video["published_parsed"]
            dt = datetime.fromtimestamp(mktime(timef))
            if dt < ptime:
                continue
            if name_filter not in video["title"]:
                # print(f"skipping {video['title']}")
                continue
            videos.append(video["link"])
        if not videos:
            continue
        #print(f"{item.text}")
        item_opts = YDL_OPTS.copy()
        if 'opts' in item:
            for key, val in item["opts"].items():
                item_opts[key] = val
        with yt_dlp.YoutubeDL(item_opts) as ydl:
            ydl.download(videos)

    input(".")


if __name__ == "__main__":
    main()
