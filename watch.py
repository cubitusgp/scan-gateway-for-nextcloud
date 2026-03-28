#!/usr/bin/env python3
"""
scan-gateway - watch.py
Watches SMB drop folders and uploads files to WebDAV destinations.
Config is loaded from /config/config.json (managed by the admin UI).
"""

import json
import os
import signal
import time

import requests
from requests.auth import HTTPBasicAuth

CONFIG_FILE = "/config/config.json"
POLL = int(os.environ.get("POLL_INTERVAL", "3"))

# Write PID for admin.py to signal on config reload
with open("/tmp/watcher.pid", "w") as f:
    f.write(str(os.getpid()))

config = {}
dest_map = {}
processed = set()
reload_needed = False


def load_dest_map():
    global config, dest_map
    if not os.path.exists(CONFIG_FILE):
        dest_map = {}
        return
    with open(CONFIG_FILE) as f:
        config = json.load(f)
    dest_map = {}
    for dest in config.get("destinations", []):
        drop = f"/drop/{dest['name']}"
        os.makedirs(drop, exist_ok=True)
        dest_map[drop] = {
            "url": dest["url"],
            "user": dest["webdav_user"],
            "pwd": dest["webdav_password"]
        }
    print(f"Config loaded: {len(dest_map)} destination(s)")
    for drop, d in dest_map.items():
        print(f"  {os.path.basename(drop)} -> {d['url']}")


def handle_sighup(signum, frame):
    global reload_needed
    reload_needed = True


signal.signal(signal.SIGHUP, handle_sighup)
load_dest_map()


def upload(fpath, fname, url, user, pwd):
    dest_url = url.rstrip("/") + "/" + fname
    try:
        with open(fpath, "rb") as f:
            r = requests.put(
                dest_url,
                data=f,
                auth=HTTPBasicAuth(user, pwd),
                verify=True,
                timeout=30
            )
        if r.status_code in (200, 201, 204):
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} : {fname} -> {dest_url}")
            return True
        print(f"ERROR {fname} : HTTP {r.status_code}")
        return False
    except Exception as e:
        print(f"ERROR {fname} : {e}")
        return False


while True:
    if reload_needed:
        reload_needed = False
        load_dest_map()

    for drop, cfg in dest_map.items():
        if not os.path.isdir(drop):
            continue
        for f in os.listdir(drop):
            fpath = os.path.join(drop, f)
            key = f"{drop}/{f}"
            if not os.path.isfile(fpath) or key in processed:
                continue
            size1 = os.path.getsize(fpath)
            time.sleep(2)
            size2 = os.path.getsize(fpath)
            if size1 != size2:
                continue
            processed.add(key)
            if upload(fpath, f, cfg["url"], cfg["user"], cfg["pwd"]):
                os.remove(fpath)
            else:
                processed.discard(key)

    time.sleep(POLL)
