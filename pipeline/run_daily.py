#!/usr/bin/env python3
"""
Daily orchestrator for GitHub Actions.
1. Picks the next unposted script from content/queue.json
2. Renders the video, verifies it
3. Writes output/<slug>.mp4 + .post.json, sets GitHub outputs
State (queue index + history) is committed back to the repo by the workflow.
"""
import datetime, json, os, subprocess, sys, wave

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "pipeline"))
import make_video  # noqa: E402

QUEUE = os.path.join(BASE, "content", "queue.json")
HISTORY = os.path.join(BASE, "content", "history.json")
OUT = os.path.join(BASE, "output")


def fail(msg):
    print(f"::error::{msg}")
    sys.exit(1)


def verify(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    dur = float(p.stdout.strip())
    if not (15 <= dur <= 65):
        fail(f"Duration {dur:.1f}s outside 15-65s")
    p = subprocess.run(["ffmpeg", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    import re
    m = re.search(r"mean_volume: (-?[\d.]+) dB", p.stderr)
    if not m:
        fail("No audio detected")
    mean = float(m.group(1))
    if not (-30 <= mean <= -8):
        fail(f"Audio mean volume {mean} dB out of range")
    print(f"verify OK: {dur:.1f}s, mean {mean} dB")


def main():
    with open(QUEUE) as f:
        queue = json.load(f)
    history = []
    if os.path.exists(HISTORY):
        with open(HISTORY) as f:
            history = json.load(f)
    posted_slugs = {h["slug"] for h in history}

    script = next((s for s in queue if s["slug"] not in posted_slugs), None)
    if script is None:
        fail("Queue exhausted! Add more scripts to content/queue.json")

    today = datetime.date.today().isoformat()
    script["slug"] = f"{today}_{script['slug']}"

    os.makedirs(OUT, exist_ok=True)
    sp = os.path.join(OUT, "todays_script.json")
    with open(sp, "w") as f:
        json.dump(script, f)

    final, meta = make_video.make(sp, OUT)
    verify(final)

    history.append({"slug": script["slug"].split("_", 1)[1], "date": today,
                    "title": meta["title"]})
    with open(HISTORY, "w") as f:
        json.dump(history, f, indent=2)

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"video={final}\n")
            f.write(f"slug={script['slug']}\n")
            f.write(f"meta={final.replace('.mp4', '.post.json')}\n")
    print("run_daily complete")


if __name__ == "__main__":
    main()
