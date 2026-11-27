#!/usr/bin/env python3
"""Synthesize a soft campfire crackle bed (no samples, no network).

    python3 autopilot/firesound.py out.wav --seconds 10 [--seed 7]

Layers: a low filtered-noise "flame breath", frequent tiny crackles, and a few
louder wood pops. Stereo, 48 kHz. Use as plan.json audio.music with
original_volume 0 when the clip was recorded without sound.
"""
import argparse
import wave

import numpy as np

SR = 48000


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def burst(rng, length, decay, hp=True):
    n = rng.standard_normal(length)
    if hp:
        n = np.diff(n, prepend=0.0)               # crude high-pass = brighter snap
    env = np.exp(-np.arange(length) / (decay * SR))
    return n * env


def channel(rng, seconds):
    n = int(seconds * SR)
    out = np.zeros(n)
    # flame breath: slow-moving low noise
    bed = lowpass(rng.standard_normal(n), 400)
    swell = 0.6 + 0.4 * np.sin(np.linspace(0, seconds * 2 * np.pi * 0.23, n) + rng.uniform(0, 6))
    out += bed * swell * 0.35
    # tiny crackles
    t = 0.0
    while t < seconds:
        t += rng.exponential(1 / 14)
        i = int(t * SR)
        L = int(rng.uniform(0.002, 0.012) * SR)
        if i + L < n:
            out[i:i + L] += burst(rng, L, rng.uniform(0.001, 0.004)) * rng.uniform(0.05, 0.35)
    # wood pops
    t = rng.uniform(0.3, 1.2)
    while t < seconds:
        i = int(t * SR)
        L = int(0.06 * SR)
        if i + L < n:
            pop = burst(rng, L, rng.uniform(0.006, 0.015), hp=False)
            out[i:i + L] += lowpass(pop, 2500) * rng.uniform(0.5, 1.0) * 2.0
            # a little sizzle after the pop
            k = int(0.25 * SR)
            if i + k < n:
                out[i:i + k] += burst(rng, k, 0.08) * 0.04
        t += rng.uniform(0.7, 2.2)
    # fade edges so it loops without a click
    f = int(0.05 * SR)
    out[:f] *= np.linspace(0, 1, f)
    out[-f:] *= np.linspace(1, 0, f)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seconds", type=float, default=10)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    left, right = channel(rng, a.seconds), channel(rng, a.seconds)
    mix = 0.75 * left + 0.25 * right, 0.25 * left + 0.75 * right
    st = np.stack(mix, axis=1)
    st /= np.max(np.abs(st)) / 0.8
    pcm = (st * 32767).astype("<i2")
    with wave.open(a.out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"wrote {a.out} ({a.seconds}s)")


if __name__ == "__main__":
    main()
