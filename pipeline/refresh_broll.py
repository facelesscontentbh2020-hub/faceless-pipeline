#!/usr/bin/env python3
"""
Auto-refresh the b-roll library from the Pexels API — runs on GitHub Actions,
never touches a local machine.

Env: PEXELS_API_KEY (free key from https://www.pexels.com/api/)

Behavior:
- Rotates through finance-relevant search categories (a few per run)
- Downloads new portrait clips at ~1080p (not 4K, to keep the repo lean)
- Names files "<keywords>-<pexels_id>.mp4" so the generator's keyword matcher works
- Tracks downloaded IDs in broll/manifest.json (no duplicates)
- Hard caps: max clips per run, max library size
Pexels license: free for commercial use, no attribution required.
"""
import json, os, random, sys
import requests

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BROLL = os.path.join(BASE, "broll")
MANIFEST = os.path.join(BROLL, "manifest.json")
API = "https://api.pexels.com/videos/search"

CLIPS_PER_RUN = 8          # weekly growth ≈ 100–200 MB
CATEGORIES_PER_RUN = 4
MAX_LIBRARY_CLIPS = 150
MAX_FILE_MB = 90           # GitHub hard limit is 100 MB

# name-prefix (drives keyword matching) -> Pexels search query
CATEGORIES = {
    "money-cash-counting": "counting money cash",
    "money-coins-saving-bank": "saving coins piggy bank",
    "bank-atm-cash": "atm bank withdraw",
    "credit-card-buy-spend": "credit card payment",
    "shopping-bags-store-spend": "shopping bags store",
    "laptop-work-typing": "working laptop typing",
    "business-meeting-people": "business meeting",
    "city-night-skyline": "city night skyline",
    "luxury-car-rich-lifestyle": "luxury car",
    "thinking-stressed-person": "worried thinking person",
    "family-home-happy": "happy family home",
    "house-real-estate-buy-home": "house keys real estate",
    "stocks-invest-chart-phone": "stock market chart phone",
    "gym-discipline-workout": "gym workout",
    "coffee-shop-cafe-spend": "coffee shop barista",
    "notebook-plan-budget-writing": "writing notebook planning",
    "phone-scrolling-social": "scrolling phone social media",
    "kitchen-cooking-home-groceries": "cooking home kitchen",
    "wallet-broke-empty-debt": "empty wallet bills stressed",
    "street-walking-city-people": "people walking city street",
}


def load_manifest():
    if os.path.exists(MANIFEST):
        with open(MANIFEST) as f:
            return json.load(f)
    return {"ids": []}


def best_file(video):
    """Pick the smallest portrait file that's still >=1080p-ish."""
    candidates = []
    for vf in video.get("video_files", []):
        w, h = vf.get("width") or 0, vf.get("height") or 0
        if h > w and 1500 <= h <= 2600:  # portrait, ~1080x1920 to ~1440x2560
            candidates.append((h, vf))
    if not candidates:
        return None
    return min(candidates)[1]  # smallest qualifying resolution


def main():
    key = os.environ["PEXELS_API_KEY"]
    headers = {"Authorization": key}
    os.makedirs(BROLL, exist_ok=True)
    manifest = load_manifest()
    known = set(manifest["ids"])
    existing = [f for f in os.listdir(BROLL) if f.endswith(".mp4")]
    if len(existing) >= MAX_LIBRARY_CLIPS:
        print(f"library at cap ({len(existing)} clips) — nothing to do")
        return

    added = 0
    cats = list(CATEGORIES.items())
    random.shuffle(cats)
    for prefix, query in cats[:CATEGORIES_PER_RUN]:
        if added >= CLIPS_PER_RUN:
            break
        r = requests.get(API, headers=headers, timeout=30, params={
            "query": query, "orientation": "portrait", "per_page": 20})
        r.raise_for_status()
        videos = r.json().get("videos", [])
        random.shuffle(videos)
        got = 0
        for v in videos:
            if got >= 2 or added >= CLIPS_PER_RUN:
                break
            vid = v["id"]
            if vid in known or not (4 <= v.get("duration", 0) <= 35):
                continue
            vf = best_file(v)
            if not vf:
                continue
            name = f"{prefix}-{vid}.mp4"
            path = os.path.join(BROLL, name)
            with requests.get(vf["link"], timeout=120, stream=True) as dl:
                dl.raise_for_status()
                with open(path, "wb") as f:
                    for chunk in dl.iter_content(1 << 20):
                        f.write(chunk)
            if os.path.getsize(path) > MAX_FILE_MB * 1024 * 1024:
                os.remove(path)
                continue
            known.add(vid)
            added += 1
            got += 1
            print(f"added {name} ({os.path.getsize(path)//(1<<20)} MB)")

    manifest["ids"] = sorted(known)
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f)
    print(f"done: {added} new clips, library now {len(existing) + added}")


if __name__ == "__main__":
    sys.exit(main())
