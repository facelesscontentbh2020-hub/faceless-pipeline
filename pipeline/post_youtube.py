#!/usr/bin/env python3
"""
Upload a Short via the YouTube Data API.
Usage: python3 post_youtube.py <video path> <post.json path>

Env vars (GitHub secrets):
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
"""
import json, os, sys

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def main(video_path, meta_path):
    with open(meta_path) as f:
        meta = json.load(f)

    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    yt = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": meta["title"][:100],
            "description": meta["caption"] + "\n\nNarration is AI-generated.",
            "categoryId": "27",  # Education
            "tags": ["money", "psychology", "personal finance", "shorts"],
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            # disclose realistic synthetic audio (YouTube altered-content policy)
            "containsSyntheticMedia": True,
        },
    }
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    try:
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = req.execute()
    except Exception as e:
        if "containsSyntheticMedia" in str(e):
            body["status"].pop("containsSyntheticMedia", None)
            media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
            resp = yt.videos().insert(part="snippet,status", body=body,
                                      media_body=media).execute()
        else:
            raise
    print(f"PUBLISHED to YouTube: https://youtube.com/shorts/{resp['id']}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
