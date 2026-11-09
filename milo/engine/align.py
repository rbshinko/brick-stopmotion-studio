"""Word timings: faster-whisper on out/voice.wav, matched to the script with difflib,
word gaps snapped to real silences in the audio -> out/words.json"""
import difflib, json, os, subprocess
import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
from epdata import WORK, LINES, tts_text, words, norm

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = WORK
# real silence only: shorter dips are stop closures inside words (the p in "apron")
SIL_DB, GAP_MIN, SEARCH = -44.0, 0.06, 0.22


def silences(y, sr):
    win = int(0.005 * sr)
    pad = np.pad(np.abs(y), win, mode="edge")
    m = np.lib.stride_tricks.sliding_window_view(pad, 2 * win + 1).max(axis=1) < 10 ** (SIL_DB / 20)
    d = np.diff(np.concatenate([[0], m.astype(np.int8), [0]]))
    return [(s / sr, e / sr) for s, e in zip(np.where(d == 1)[0], np.where(d == -1)[0])
            if (e - s) / sr >= GAP_MIN]


def transcribe(path):
    model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
    prompt = " ".join(tts_text(l) for l in LINES)
    # decode with ffmpeg rather than PyAV: 16 kHz mono float32
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", "16000",
                          "-f", "f32le", "-"], check=True, capture_output=True).stdout
    audio = np.frombuffer(raw, np.float32)
    segs, _ = model.transcribe(audio, language="en", word_timestamps=True, beam_size=5,
                               initial_prompt=prompt, vad_filter=False)
    out = []
    for s in segs:
        for w in s.words:
            for piece in w.word.replace("-", " ").split():
                if norm(piece):
                    out.append({"w": norm(piece), "start": w.start, "end": w.end, "p": w.probability})
    return out


def match(script, heard):
    a, b = [norm(w["text"]) for w in script], [h["w"] for h in heard]
    times = [None] * len(script)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                h = heard[j1 + k]
                times[i1 + k] = [h["start"], h["end"], h["p"] if tag == "equal" else 0.0]
        elif tag == "replace":
            # spread the heard span evenly over the script words
            t0, t1 = heard[j1]["start"], heard[j2 - 1]["end"]
            n = i2 - i1
            for k in range(n):
                times[i1 + k] = [t0 + (t1 - t0) * k / n, t0 + (t1 - t0) * (k + 1) / n, 0.0]
    # words whisper missed entirely: interpolate between neighbours
    for i, t in enumerate(times):
        if t is None:
            prev = next((times[j][1] for j in range(i - 1, -1, -1) if times[j]), 0.0)
            nxt = next((times[j][0] for j in range(i + 1, len(times)) if times[j]), prev + 0.3)
            run = [j for j in range(i, len(times)) if times[j] is None]
            run = run[:next((k for k in range(1, len(run)) if run[k] != run[k - 1] + 1), len(run))]
            for k, j in enumerate(run):
                times[j] = [prev + (nxt - prev) * k / len(run), prev + (nxt - prev) * (k + 1) / len(run), -1.0]
    return times


def snap(times, sil, dur):
    """Whisper swallows pauses into the next word: give each gap the longest silence near it."""
    used = set()
    for i in range(len(times) - 1):
        b = times[i][1]
        # a short dip may only move the next word's start up to its middle;
        # a long one (line or inner pause) is never a stop closure, so it may go further
        lo, hi = times[i][0] + 0.04, times[i + 1][1] - 0.04
        mid = (times[i + 1][0] + times[i + 1][1]) / 2 + 0.03
        cands = [(e - s, k) for k, (s, e) in enumerate(sil)
                 if k not in used and s < b + SEARCH and e > b - SEARCH and s >= lo and e <= hi
                 and (e - s >= 0.09 or e <= mid)]
        if cands:
            _, k = max(cands)
            used.add(k)
            times[i][1], times[i + 1][0] = sil[k]
        elif times[i + 1][0] < times[i][1]:
            times[i + 1][0] = times[i][1]
    lead = [e for s, e in sil if s <= 0.001]
    if lead:
        times[0][0] = max(times[0][0], lead[0])
    tail = [s for s, e in sil if e >= dur - 0.001]
    if tail:
        times[-1][1] = min(max(times[-1][1], times[-1][0] + 0.1), tail[0]) if tail[0] > times[-1][0] else times[-1][1]
    return times


def main():
    path = os.path.join(OUT, "voice.wav")
    y, sr = sf.read(path, dtype="float32")
    heard = transcribe(path)
    script = words()
    times = snap(match(script, heard), silences(y, sr), len(y) / sr)
    res = []
    for i, (w, (s, e, p)) in enumerate(zip(script, times)):
        res.append({"i": i, "text": w["text"], "key": w["key"], "line": w["line"],
                    "start": round(s, 3), "end": round(e, 3), "conf": round(p, 2)})
    with open(os.path.join(OUT, "words.json"), "w") as f:
        json.dump({"duration": len(y) / sr, "words": res}, f, indent=1)
    print("heard:", " ".join(h["w"] for h in heard))
    for li in range(len(LINES)):
        ws = [r for r in res if r["line"] == li]
        flag = [r["text"] for r in ws if r["conf"] < 0.5]
        print(f"{li+1:2d} {ws[0]['start']:6.2f}-{ws[-1]['end']:6.2f}  " +
              " ".join(f"{r['text']}@{r['start']:.2f}" for r in ws) + (f"   LOW: {flag}" if flag else ""))


if __name__ == "__main__":
    main()
