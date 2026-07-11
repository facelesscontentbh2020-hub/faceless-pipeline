# Faceless Content Pipeline (cloud)

Fully automated faceless-shorts factory for **@moneyrewired.daily** (Money & Wealth Psychology niche).

Runs free on GitHub Actions, daily at 12pm US Central:

1. `pipeline/run_daily.py` picks the next script from `content/queue.json`
2. `pipeline/make_video.py` renders it — Kokoro AI voiceover, keyword-matched b-roll
   from `broll/`, karaoke captions (Anton), procedural background music, 1080x1920
3. Quality gates: duration + loudness checks (run fails rather than posting junk)
4. Posts to Instagram (Graph API) and YouTube (Data API); the video is hosted as a
   GitHub release asset for Instagram's `video_url`
5. Commits `content/history.json` back so nothing posts twice

Setup: see **SETUP.md**. Manual run: Actions → Daily faceless short → Run workflow.

Cost: $0/month. B-roll: Pexels (royalty-free). Voice models download from the
kokoro-onnx GitHub release at runtime (cached).

Maintenance: refresh Meta token every ~60 days; top up the queue (~6 weeks per 40
scripts) by asking Claude to write a new batch matching the style rules.
