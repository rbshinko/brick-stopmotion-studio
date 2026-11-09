"""Render each line with Kokoro, tighten pauses, join, pitch up 1.5 semitones -> out/voice.wav (48 kHz)."""
import os, subprocess, sys
import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro
from epdata import WORK, LINES, GAP_EXTRA, tts_text

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = WORK
KOK = os.path.join(os.path.dirname(HERE), "assets", "kokoro")
SR = 24000
SIL_DB, SIL_MIN, KEEP, INNER = -44.0, 0.06, 0.035, 0.11
BASE_GAP, SEMITONES = 0.06, 1.5


def silent_mask(x, sr):
    # a sample is silent when the 5 ms window around it peaks below -44 dBFS
    win = int(0.005 * sr)
    a = np.abs(x)
    pad = np.pad(a, win, mode="edge")
    view = np.lib.stride_tricks.sliding_window_view(pad, 2 * win + 1)
    return view.max(axis=1) < 10 ** (SIL_DB / 20)


def runs(mask):
    d = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def tighten(x, sr):
    """Trim ends to KEEP of silence, shrink inner silences longer than INNER down to INNER (never stretch)."""
    m = silent_mask(x, sr)
    speech = np.where(~m)[0]
    k = int(KEEP * sr)
    x = x[max(0, speech[0] - k): speech[-1] + k + 1]
    m = silent_mask(x, sr)
    half = int(INNER / 2 * sr)
    pieces, pos = [], 0
    for s, e in runs(m):
        if s == 0 or e == len(x) or (e - s) < SIL_MIN * sr or (e - s) <= INNER * sr:
            continue
        pieces.append(x[pos:s + half])
        pos = e - half
    pieces.append(x[pos:])
    return np.concatenate(pieces)


def main():
    os.makedirs(os.path.join(OUT, "lines"), exist_ok=True)
    kok = Kokoro(os.path.join(KOK, "kokoro-v1.0.onnx"), os.path.join(KOK, "voices-v1.0.bin"))
    parts, starts, t = [], [], 0.0
    for i, line in enumerate(LINES):
        raw, sr = kok.create(tts_text(line), voice="af_heart", speed=1.32, lang="en-us")
        assert sr == SR
        sf.write(os.path.join(OUT, "lines", f"{i:02d}_raw.wav"), raw, SR)
        y = tighten(raw.astype(np.float32), SR)
        starts.append(t)
        parts.append(y)
        t += len(y) / SR
        if i < len(LINES) - 1:
            # the KEEP tails on each side already count toward the pause
            gap = max(0.0, BASE_GAP + GAP_EXTRA[i] - 2 * KEEP)
            parts.append(np.zeros(int(gap * SR), np.float32))
            t += gap
        print(f"line {i+1:2d}: {len(raw)/SR:5.2f}s raw -> {len(y)/SR:5.2f}s")
    take = np.concatenate(parts)
    sf.write(os.path.join(OUT, "voice_24k.wav"), take, SR)

    # 48 kHz, then raise pitch at the same speed: asetrate up, atempo back down
    r = 2 ** (SEMITONES / 12)
    af = f"aresample=48000,asetrate={48000 * r:.3f},aresample=48000,atempo={1 / r:.6f}"
    tmp = os.path.join(OUT, "voice_pitched.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(OUT, "voice_24k.wav"),
                    "-af", af, "-ac", "1", "-c:a", "pcm_f32le", tmp], check=True)
    y, sr = sf.read(tmp, dtype="float32")
    y *= 10 ** (-15 / 20) / np.abs(y).max()  # voice peaks at -15 dB
    sf.write(os.path.join(OUT, "voice.wav"), y, sr, subtype="FLOAT")
    os.remove(tmp)
    print(f"voice.wav: {len(y)/sr:.2f}s at {sr} Hz")


if __name__ == "__main__":
    sys.exit(main())
