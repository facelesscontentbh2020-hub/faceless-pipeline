#!/usr/bin/env python3
"""
Faceless Shorts generator — cloud edition (GitHub Actions).
Usage: python3 pipeline/make_video.py <script.json> <output_dir>
Repo layout: voice/ (downloaded by workflow), broll/, Anton-Regular.ttf at repo root.
"""
import json, math, os, random, re, subprocess, sys, wave

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KOKORO_MODEL = os.path.join(BASE, "voice", "kokoro-v1.0.onnx")
KOKORO_VOICES = os.path.join(BASE, "voice", "voices-v1.0.bin")
BROLL = os.path.join(BASE, "broll")
FONT = os.path.join(BASE, "Anton-Regular.ttf")
FONT_NAME = "Anton" if os.path.exists(FONT) else "DejaVu Sans"
W, H, FPS = 1080, 1920, 30
GAP = 0.18

# Curated narration voices (Kokoro v1.0) and pacing — rotated per video so the
# channel doesn't sound like one robot on a loop.
VOICES = [
    ("am_michael", 0.98),   # warm US male (the original)
    ("am_onyx", 0.96),      # deep US male
    ("am_fenrir", 1.02),    # energetic US male
    ("af_heart", 1.00),     # natural US female
    ("af_bella", 1.00),     # bright US female
    ("bm_george", 0.97),    # British male
]

_kokoro = None
_voice_choice = None


def pick_voice(seed_text):
    """Stable per-video choice: same script -> same voice, different scripts vary."""
    global _voice_choice
    if _voice_choice is None:
        idx = int(__import__("hashlib").md5(seed_text.encode()).hexdigest(), 16) % len(VOICES)
        _voice_choice = VOICES[idx]
        print(f"voice: {_voice_choice[0]} @ {_voice_choice[1]}")
    return _voice_choice


def synth_line(text, out_wav, seed_text=""):
    global _kokoro
    import numpy as np
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(KOKORO_MODEL, KOKORO_VOICES)
    voice, speed = pick_voice(seed_text or text)
    samples, sr = _kokoro.create(text, voice=voice, speed=speed)
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    with wave.open(out_wav, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return len(samples) / sr


def concat_voice(wavs, out_wav):
    with wave.open(wavs[0]) as w0:
        sr, sw, ch = w0.getframerate(), w0.getsampwidth(), w0.getnchannels()
    silence = b"\x00" * int(GAP * sr) * sw * ch
    with wave.open(out_wav, "w") as out:
        out.setnchannels(ch); out.setsampwidth(sw); out.setframerate(sr)
        for i, wv in enumerate(wavs):
            with wave.open(wv) as w:
                out.writeframes(w.readframes(w.getnframes()))
            if i < len(wavs) - 1:
                out.writeframes(silence)


# Four procedural music styles, rotated per video.
MUSIC_STYLES = {
    "ambient_minor": dict(bar=4.0, octave=0.20, pulse=0.0, chords=[
        [110.0, 130.81, 164.81], [98.0, 123.47, 146.83],
        [87.31, 110.0, 130.81], [103.83, 123.47, 155.56]]),
    "uplift_major": dict(bar=3.2, octave=0.16, pulse=0.0, chords=[
        [130.81, 164.81, 196.0], [146.83, 174.61, 220.0],
        [110.0, 138.59, 164.81], [123.47, 155.56, 185.0]]),
    "dark_tension": dict(bar=5.0, octave=0.10, pulse=0.0, chords=[
        [82.41, 98.0, 123.47], [77.78, 92.5, 116.54],
        [82.41, 103.83, 123.47], [73.42, 87.31, 110.0]]),
    "lofi_pulse": dict(bar=2.4, octave=0.14, pulse=0.10, chords=[
        [104.65, 124.47, 155.56], [93.24, 116.54, 139.29],
        [124.47, 155.56, 186.66], [110.0, 130.81, 164.81]]),
}


def make_music(duration, out_wav, seed_text="", sr=22050):
    import numpy as np
    style_name = sorted(MUSIC_STYLES)[
        int(__import__("hashlib").md5(("m" + seed_text).encode()).hexdigest(), 16)
        % len(MUSIC_STYLES)]
    st = MUSIC_STYLES[style_name]
    print(f"music: {style_name}")
    n = int(duration * sr)
    t = np.arange(n) / sr
    audio = np.zeros(n)
    bar = st["bar"]
    for i in range(int(math.ceil(duration / bar))):
        s, e = int(i * bar * sr), min(int((i + 1) * bar * sr), n)
        if s >= n:
            break
        seg_t = t[s:e]
        seg = np.zeros(e - s)
        for f in st["chords"][i % 4]:
            seg += 0.28 * np.sin(2 * np.pi * f * seg_t)
            seg += st["octave"] * np.sin(2 * np.pi * f * 2 * seg_t)
        env = np.clip(np.minimum((seg_t - seg_t[0]) / 0.8,
                                 (seg_t[-1] - seg_t) / 0.8 + 0.05), 0, 1)
        audio[s:e] += seg * env
    if st["pulse"] > 0:  # soft rhythmic pulse for lofi feel
        beat = 60.0 / (240.0 / bar)
        pulse_env = 0.5 * (1 + np.cos(2 * np.pi * (t / beat % 1.0) * np.pi / np.pi))
        audio *= (1 - st["pulse"]) + st["pulse"] * np.clip(pulse_env, 0, 1)
    audio *= 0.35 / max(1e-9, np.max(np.abs(audio)))
    fade = min(n, int(1.5 * sr))
    audio[-fade:] *= np.linspace(1, 0, fade)
    pcm = (audio * 32767).astype(np.int16)
    with wave.open(out_wav, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def pick_broll(lines, keywords):
    clips = []
    if os.path.isdir(BROLL):
        clips = [os.path.join(BROLL, f) for f in sorted(os.listdir(BROLL))
                 if f.lower().endswith((".mp4", ".mov", ".webm")) and not f.startswith(".")]
    if not clips:
        return [None] * len(lines)
    rng = random.Random(hash(lines[0]))
    used, picks = set(), []
    for i, line in enumerate(lines):
        kws = (keywords[i] if keywords and i < len(keywords) else []) + \
              re.findall(r"[a-z]{4,}", line.lower())
        scored = []
        for c in clips:
            name = os.path.basename(c).lower()
            score = sum(2 for k in kws if k in name) - (3 if c in used else 0)
            scored.append((score + rng.random(), c))
        best = max(scored)[1]
        used.add(best)
        picks.append(best)
    return picks


def render_segment(clip, dur, idx, tmp):
    seg = os.path.join(tmp, f"seg{idx}.mp4")
    d = round(dur + GAP, 3)
    if clip:
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H},fps={FPS},"
              f"eq=brightness=-0.06:saturation=1.1,setsar=1")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1",
               "-i", clip, "-t", str(d), "-vf", vf, "-an",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
               "-pix_fmt", "yuv420p", seg]
    else:
        vf = (f"gradients=size={W}x{H}:speed=0.015:nb_colors=3:"
              f"c0=0x16213e:c1=0x1a3a6b:c2=0x3b2a6b:duration={d}:rate={FPS}")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", vf,
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
               "-pix_fmt", "yuv420p", seg]
    subprocess.run(cmd, check=True)
    return seg


def ass_time(sec):
    return f"{int(sec // 3600)}:{int(sec % 3600 // 60):02d}:{sec % 60:05.2f}"


def build_ass(lines, durations, out_ass):
    fs = 155 if FONT_NAME == "Anton" else 95
    head = f"""[Script Info]
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, BorderStyle
Style: Cap,{FONT_NAME},{fs},&H00FFFFFF,&H00000000,&H80000000,1,8,3,5,70,70,0,1
Style: CapY,{FONT_NAME},{fs},&H0000D7FF,&H00000000,&H80000000,1,8,3,5,70,70,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    hot = re.compile(r"[\d$%]|money|rich|wealth|poor|broke|dollar|bank|salary|"
                     r"debt|invest|save|spend|brain|mind|secret|never|free", re.I)
    evs, t0 = [], 0.0
    for line, dur in zip(lines, durations):
        words = line.split()
        chunks, cur = [], []
        for w in words:
            cur.append(w)
            if len(cur) == 3 or sum(len(x) for x in cur) > 13 or w[-1] in ".!?,:":
                chunks.append(cur); cur = []
        if cur:
            chunks.append(cur)
        weights = [sum(len(w) + 2.5 for w in ch) for ch in chunks]
        tot = sum(weights)
        t = t0
        for ch, wt in zip(chunks, weights):
            cd = wt / tot * dur
            txt = " ".join(ch).upper().replace("{", "").replace("}", "")
            style = "CapY" if hot.search(txt) else "Cap"
            fx = r"{\fad(50,30)\t(0,80,\fscx100\fscy100)\fscx85\fscy85}"
            evs.append(f"Dialogue: 0,{ass_time(t)},{ass_time(t + cd)},{style},,0,0,0,,{fx}{txt}")
            t += cd
        t0 += dur + GAP
    with open(out_ass, "w") as f:
        f.write(head + "\n".join(evs) + "\n")


def make(script_path, out_dir):
    with open(script_path) as f:
        sc = json.load(f)
    os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(out_dir, "_tmp")
    os.makedirs(tmp, exist_ok=True)
    final = os.path.join(out_dir, f"{sc['slug']}.mp4")

    lines = sc["lines"]
    wavs, durations = [], []
    for i, line in enumerate(lines):
        wv = os.path.join(tmp, f"l{i}.wav")
        durations.append(synth_line(line, wv, seed_text=sc["slug"]))
        wavs.append(wv)
    total = sum(durations) + GAP * (len(lines) - 1)

    voice_all = os.path.join(tmp, "voice.wav")
    concat_voice(wavs, voice_all)
    music = os.path.join(tmp, "music.wav")
    make_music(total + 0.6, music, seed_text=sc["slug"])

    picks = pick_broll(lines, sc.get("keywords"))
    segs = [render_segment(c, d, i, tmp) for i, (c, d) in enumerate(zip(picks, durations))]

    ass = os.path.join(tmp, "caps.ass")
    build_ass(lines, durations, ass)

    with open(os.path.join(tmp, "vconcat.txt"), "w") as f:
        for s in segs:
            f.write(f"file '{os.path.basename(s)}'\n")
    dur = round(total + 0.4, 2)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-f", "concat", "-safe", "0", "-i", os.path.join(tmp, "vconcat.txt"),
                    "-i", voice_all, "-i", music,
                    "-filter_complex",
                    f"[0:v]tpad=stop_mode=clone:stop_duration=1,ass={ass}:fontsdir={BASE},vignette=PI/4.6[v];"
                    f"[2:a]volume=0.30[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=2,"
                    f"apad=pad_dur=0.4,loudnorm=I=-15:TP=-1.2[a]",
                    "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                    "-c:a", "aac", "-b:a", "160k", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    "-t", str(dur), final], check=True)

    meta = {"file": os.path.basename(final), "slug": sc["slug"], "title": sc["title"],
            "caption": sc["caption"] + "\n\n" + " ".join(sc["hashtags"]),
            "duration_sec": dur}
    with open(final.replace(".mp4", ".post.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"DONE {final} ({dur:.1f}s)")
    return final, meta


if __name__ == "__main__":
    make(sys.argv[1], sys.argv[2])
