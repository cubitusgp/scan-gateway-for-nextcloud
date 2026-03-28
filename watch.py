#!/usr/bin/env python3
"""
scan-gateway - watch.py
Watches SMB drop folders and uploads files to WebDAV destinations (e.g. Nextcloud).
"""

import os
import time
import requests
from requests.auth import HTTPBasicAuth

POLL = int(os.environ.get("POLL_INTERVAL", "3"))

# Parse DESTINATIONS env var
# Format: "folder_name|webdav_url|username|password,folder_name2|webdav_url2|username2|password2"
DEST_MAP = {}
for entry in os.environ.get("DESTINATIONS", "").replace("\n", "").split(","):
    parts = entry.strip().split("|")
    if len(parts) == 4:
        name, url, user, pwd = parts
        drop = f"/drop/{name.strip()}"
        DEST_MAP[drop] = {
            "url": url.strip(),
            "user": user.strip(),
            "pwd": pwd.strip()
        }

print(f"Watching {len(DEST_MAP)} folder(s)...")
for drop, config in DEST_MAP.items():
    os.makedirs(drop, exist_ok=True)
    print(f"  SMB share: {os.path.basename(drop)} -> {config['url']}")

processed = set()


def upload(fpath, fname, url, user, pwd):
    """Upload a file to a WebDAV destination."""
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
        print(f"ERROR uploading {fname} : HTTP {r.status_code} - {r.text}")
        return False
    except Exception as e:
        print(f"ERROR uploading {fname} : {e}")
        return False


while True:
    for drop, config in DEST_MAP.items():
        if not os.path.isdir(drop):
            continue
        for f in os.listdir(drop):
            fpath = os.path.join(drop, f)
            key = f"{drop}/{f}"
            if not os.path.isfile(fpath) or key in processed:
                continue
            # Wait for file to be fully written
            size1 = os.path.getsize(fpath)
            time.sleep(2)
            size2 = os.path.getsize(fpath)
            if size1 != size2:
                continue  # Still being written
            processed.add(key)
            if upload(fpath, f, config["url"], config["user"], config["pwd"]):
                os.remove(fpath)
            else:
                processed.discard(key)  # Retry next time
    time.sleep(POLL)
