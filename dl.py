#!/usr/bin/env python3
"""Reads list of channels from subs.json in DATA_DIR, and downloads them to VIDEO_DIR. Also includes a command-line helper function to add a subscribtion to subs.json that can be used as a share target""" 


import os.path
import json
import re
import argparse
import pickle
import subprocess

from time import mktime
from datetime import datetime, timedelta
import feedparser
import yt_dlp
from yt_dlp.postprocessor.sponsorblock import SponsorBlockPP


# note: if using sponsorblock, only '.ass/.lrc' file formats will be chopped alongside video.
# All other formats will have mis-synced subtitles

Subs = list[dict[str, str]]

def read_archive(archive_file: str) -> dict[str, datetime]:
    """read pickle archive of downloaded videos"""
    if not os.path.isfile(archive_file):
        return {}
    with open(archive_file, 'rb') as file:
        return pickle.load(file) # type: ignore

def write_archive(archive_file: str, data: dict[str, datetime]) -> None:
    """write pickle archive of downloaded videos"""
    dirname = os.path.dirname(archive_file)
    if not os.path.isdir(dirname):
        os.makedirs(dirname)
    with open(archive_file, 'wb') as file:
        pickle.dump(data, file)

def read_subs(data_dir: str) -> Subs:
    """read subs, or return empty list if no file"""
    path = os.path.join(data_dir, "subs.json")
    if not os.path.isfile(path):
        return []

    with open(path, encoding="utf-8") as file:
        return json.loads(file.read()) #type: ignore


def write_subs(subs: Subs, data_dir: str) -> None:
    """wrapper to write subs to file"""
    if not os.path.isdir(data_dir):
        os.makedirs(data_dir)
    with open(os.path.join(data_dir, "subs.json"), "w", encoding="utf-8") as file:
        file.write(json.dumps(subs, indent=4))


def get_channel_info(url: str) -> tuple[str, str]:
    """extract channel id & name from a video or channel url"""
    # yt_dlp module doesn't give (easy) access to print output, also can't find
    # a --max-downloads
    res = subprocess.run(
            ['yt-dlp', '--max-downloads', '1', '--print', 'channel_id', '--print', 'channel', url],
            capture_output=True,
            encoding='utf-8')
    if res.returncode not in (0, 101):
        print(res.stdout, res.stderr, res.returncode)
        res.check_returncode()
    channel_id, name = res.stdout.strip().split('\n')
    return channel_id, name

def subscribe(url: str, title_filter: str, data_dir: str) -> None:
    """add channel to subs.json, optionally with a regex title filter"""
    channel_id, name = get_channel_info(url)
    subs = read_subs(data_dir)
    channel = {"id": channel_id, "name": name}

    if title_filter:
        channel["filter"] = title_filter

    if channel in subs:
        print(f"channel {channel} already in subs")
        return

    subs.append(channel)
    write_subs(subs, data_dir)
    print(f"added {channel}")


def download(args: argparse.Namespace) -> None:
    """download all videos from {days} back from subs.json"""
    ydl_opts = {
        "ignoreerrors": True,
        "outtmpl": args.video_dir + "/%(uploader)s_%(id)s.%(ext)s",
        "ffmpeg-location": "/usr/bin/ffmpeg",
        #"postprocessors": [
            #{
                #"key": 
            #{"key": "SponsorBlock", "when": "pre_process"},
            #{
            #    "key": "ModifyChapters",
            #    "remove_sponsor_segments": SponsorBlockPP.CATEGORIES.keys(),
            #    "force_keyframes": True,
            #},
        #],
        "writesubtitles": False,
        "nopart": False,
        'subtitleslangs': "en",
        #"subtitlesformat": "srt",
        "hls_use_mpegts": True,
        "simulate": args.dry_run,
        "download_archive": os.path.join(args.data_dir, "download_archive"),
        "format": (
            "best[height=1080]"
            "/(bestvideo*[height=1080]+bestaudio)"
            "/best[height=720]"
            "/(bestvideo*[height=720]+bestaudio)"
            "/(bestvideo*+bestaudio)/best"
        ), }
    outline = read_subs(args.data_dir)
    #archive = read_archive(args.archive_file)

    ptime = datetime.today() - timedelta(days=args.days_back)

    for item in outline:
        print(item["name"])
        url = f'https://www.youtube.com/feeds/videos.xml?channel_id={item["id"]}'
        feed = feedparser.parse(url)

        videos = []
        for video in reversed(feed["items"]):
            timef = video["published_parsed"]

            if datetime.fromtimestamp(mktime(timef)) < ptime:
                continue
            if 'ignore' in item and re.match(item['ignore'], video['title'], re.IGNORECASE):
                print(f"ignoring {video['title']}")
                continue
            if 'filter' in item and not re.match(item['filter'], video['title'], re.IGNORECASE):
                print(f"skipping {video['title']}")
                continue
            #if video["link"] in archive:
                #continue
            videos.append(video["link"])

        if not videos:
            continue
        # print(f"{item.text}")
        item_opts = ydl_opts.copy()
        if "opts" in item:
            for key, val in item["opts"].items():
                item_opts[key] = val
        with yt_dlp.YoutubeDL(item_opts) as ydl:
            for video in videos:
                try:
                    ydl.download([video])
                except yt_dlp.DownloadError as err:
                    print(err)
                else:
                    #archive[video] = ptime
                    print(f'downloaded {video}')
    #write_archive(args.archive_file, archive)


def main() -> None:
    """parse args and call subscribe/download"""
    parser = argparse.ArgumentParser(
        description="Automatically new videos from subscribed channels"
    )
    parser.add_argument(
        "--download", action='store_true', help="download new videos"
    )
    parser.add_argument(
        "--wait", action='store_true', help="download new videos"
    )
    parser.add_argument(
        "--dry-run", action='store_true', help="dry as the saharan desert"
    )
    parser.add_argument(
        "--subscribe", type=str, help="subscribe to channel, adding it to subs.json"
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=3,
        help="number of days back to get videos from",
    )
    parser.add_argument(
        "--filter",
        default="",
        type=str,
        help="For use when subscribing, only download videos from this channel matching this regex",
    )
    parser.add_argument(
            "--video-dir", type=str, default="~/Media/movies/youtube/")
    parser.add_argument(
            "--data-dir", type=str, default="$XDG_DATA_HOME/youtube-dlp-subscriptions/")
    parser.add_argument(
            "--archive-file", type=str, default="$XDG_DATA_HOME/youtube-dlp-subscriptions/archive")

    args = parser.parse_args()
    args.video_dir = os.path.expanduser(os.path.expandvars(args.video_dir))
    args.data_dir = os.path.expanduser(os.path.expandvars(args.data_dir))
    args.archive_file = os.path.expanduser(os.path.expandvars(args.archive_file))
    
    if args.subscribe:
        subscribe(args.subscribe, args.filter, args.data_dir)
    if args.download:
        download(args)
    if args.wait:
        input("done")


if __name__ == "__main__":
    main()
