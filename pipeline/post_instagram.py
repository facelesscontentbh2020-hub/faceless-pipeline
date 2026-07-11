#!/usr/bin/env python3
"""
Publish a Reel via the Instagram Graph API.
Usage: python3 post_instagram.py <public_video_url> <post.json path>

Env vars (GitHub secrets):
  IG_USER_ID        - Instagram professional account ID
  META_ACCESS_TOKEN - long-lived user access token (refresh every ~60 days)
"""
import json, os, sys, time
import requests

GRAPH = "https://graph.facebook.com/v21.0"


def main(video_url, meta_path):
    ig_user = os.environ["IG_USER_ID"]
    token = os.environ["META_ACCESS_TOKEN"]
    with open(meta_path) as f:
        meta = json.load(f)

    # 1. create media container
    r = requests.post(f"{GRAPH}/{ig_user}/media", data={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": meta["caption"],
        "share_to_feed": "true",
        "access_token": token,
    }, timeout=60)
    r.raise_for_status()
    container = r.json()["id"]
    print(f"container {container}")

    # 2. poll until processed (up to 5 min)
    for _ in range(60):
        s = requests.get(f"{GRAPH}/{container}",
                         params={"fields": "status_code", "access_token": token},
                         timeout=30).json()
        code = s.get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise RuntimeError(f"IG processing error: {s}")
        time.sleep(5)
    else:
        raise RuntimeError("IG processing timed out")

    # 3. publish
    r = requests.post(f"{GRAPH}/{ig_user}/media_publish", data={
        "creation_id": container, "access_token": token,
    }, timeout=60)
    r.raise_for_status()
    print(f"PUBLISHED to Instagram: media id {r.json()['id']}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
