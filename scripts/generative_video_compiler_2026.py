#!/usr/bin/env python3
"""
Generative Video Compiler — 2026 revision
=========================================

A randomised temporal collage engine. It samples contiguous runs of frames from
a library of found footage, layers three parallel streams, blends them, and
cross-dissolves the result into a doubled-rate image sequence.

WHAT CHANGED FROM THE 2024 SCRIPT
---------------------------------
The 2024 script (kept alongside this one as `generative_video_compiler_2024.py`)
is the one that actually produced *Taken Pictures*. Reading it back in 2026
turned up several things it did not do, despite the design document saying it
would:

1. **Blend modes were never applied.** Each container was assigned a random mode
   from multiply / screen / overlay / soft-light, printed to the console — and
   then ignored. Every layer was composited with `multiply`.
2. **Opacity was never applied.** `randomOpacity` (30–70%) was likewise assigned,
   printed, and never read.
3. **The recognition pass did nothing.** InceptionV3 was loaded and every frame
   was preprocessed for it, but `predict()` was never called. The model was
   loaded and discarded, 360 times.
4. **No video was compiled.** `subprocess` was imported but unused; the final
   step only renamed files into a folder.

(1) and (2) together are why every export came out roughly four times darker
than intended — multiply always darkens, and it ran at full strength with no
opacity to soften it. That darkness was corrected by hand, with curves, in
Premiere, for the entire life of the project.

This revision applies the blend modes and opacities as originally specified,
drops the dead recognition pass (and with it the TensorFlow dependency), makes
the paths configurable, and will compile the video if ffmpeg is available.

Dependencies: pillow, numpy, tqdm.  Optional: ffmpeg on PATH.
"""

from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

try:
    from tqdm import tqdm
except ImportError:                                     # tqdm is a nicety, not a requirement
    def tqdm(x, **kw):
        return x


# ---------------------------------------------------------------- blend modes

def _multiply(b, t):    return b * t
def _screen(b, t):      return 1 - (1 - b) * (1 - t)
def _overlay(b, t):     return np.where(b <= 0.5, 2 * b * t, 1 - 2 * (1 - b) * (1 - t))
def _soft_light(b, t):  return (1 - 2 * t) * b ** 2 + 2 * t * b

BLEND_MODES = {
    'multiply':   _multiply,
    'screen':     _screen,
    'overlay':    _overlay,
    'soft_light': _soft_light,
}


def composite(base: np.ndarray, top: np.ndarray, mode: str, opacity: float) -> np.ndarray:
    """Blend `top` onto `base` and mix by `opacity` — the step the 2024 script skipped."""
    blended = BLEND_MODES[mode](base, top)
    return np.clip(blended * opacity + base * (1.0 - opacity), 0.0, 1.0)


# ---------------------------------------------------------------------- core

class GenerativeVideoCompiler:
    def __init__(self, frames_dir, output_dir, total_frames=360, drawers=3,
                 size=None, seed=None, run_min=10, run_max=75,
                 opacity_range=(0.30, 0.70)):
        self.frames_dir = Path(frames_dir)
        self.output_dir = Path(output_dir)
        self.total_frames = total_frames
        self.drawer_count = drawers
        self.size = size
        self.run_min, self.run_max = run_min, run_max
        self.opacity_range = opacity_range
        self.rng = random.Random(seed)          # seeded → a run is reproducible
        self.drawers: list[list[dict]] = []

    # -- source library ----------------------------------------------------

    def _library(self) -> list[Path]:
        """Every frame under frames_dir, grouped by folder so runs stay contiguous."""
        exts = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.webp'}
        folders: dict[Path, list[Path]] = {}
        for p in sorted(self.frames_dir.rglob('*')):
            if p.is_file() and p.suffix.lower() in exts:
                folders.setdefault(p.parent, []).append(p)
        if not folders:
            raise SystemExit(f'No images found under {self.frames_dir}')
        return folders

    # -- step 1 + 2: fill the drawers -------------------------------------

    def fill_drawers(self):
        folders = self._library()
        folder_keys = sorted(folders)
        total_available = sum(len(v) for v in folders.values())
        print(f'  library: {total_available} frames across {len(folder_keys)} folder(s)')

        for d in range(self.drawer_count):
            drawer, count = [], 0
            while count < self.total_frames:
                want = min(self.total_frames - count, self.rng.randint(self.run_min, self.run_max))
                # a container = one contiguous run, spilling into another folder if short
                picked: list[Path] = []
                while len(picked) < want:
                    src = folders[self.rng.choice(folder_keys)]
                    need = want - len(picked)
                    start = self.rng.randint(0, max(0, len(src) - 1))
                    picked.extend(src[start:start + need])
                    if len(src) <= need and len(src) == 0:
                        break
                drawer.append({
                    'images':  picked[:want],
                    'opacity': self.rng.uniform(*self.opacity_range),
                    'mode':    self.rng.choice(list(BLEND_MODES)),
                })
                count += want
            self.drawers.append(drawer)
            modes = ', '.join(sorted({c['mode'] for c in drawer}))
            print(f'  drawer {d + 1}: {len(drawer)} containers, {count} frames, modes used: {modes}')

    def _flatten(self, drawer) -> list[tuple[Path, str, float]]:
        out = []
        for c in drawer:
            for img in c['images']:
                out.append((img, c['mode'], c['opacity']))
        return out[:self.total_frames]

    # -- step 3: layer and blend ------------------------------------------

    def blend(self) -> list[Path]:
        blended_dir = self.output_dir / 'blended'
        blended_dir.mkdir(parents=True, exist_ok=True)
        streams = [self._flatten(d) for d in self.drawers]

        if self.size is None:                            # inherit the source resolution
            with Image.open(streams[0][0][0]) as probe:
                self.size = probe.size
        print(f'  compositing at {self.size[0]}x{self.size[1]}')

        written = []
        for i in tqdm(range(self.total_frames), desc='  blending'):
            path, _, _ = streams[0][i]
            base = np.asarray(Image.open(path).convert('RGB').resize(self.size), np.float32) / 255.0
            for s in streams[1:]:                        # drawer 2, then drawer 3
                path, mode, opacity = s[i]
                top = np.asarray(Image.open(path).convert('RGB').resize(self.size), np.float32) / 255.0
                base = composite(base, top, mode, opacity)
            out = blended_dir / f'bl{i:05d}.png'
            Image.fromarray((base * 255).astype(np.uint8)).save(out)
            written.append(out)
        return written

    # -- step 4: cross-dissolve to double the frame count -----------------

    def interpolate(self, blended: list[Path]) -> list[Path]:
        seq_dir = self.output_dir / 'final_sequence'
        seq_dir.mkdir(parents=True, exist_ok=True)
        n = 1
        for i in tqdm(range(len(blended)), desc='  interpolating'):
            Image.open(blended[i]).save(seq_dir / f'{n:05d}.png'); n += 1
            if i + 1 < len(blended):
                a = np.asarray(Image.open(blended[i]), np.float32)
                b = np.asarray(Image.open(blended[i + 1]), np.float32)
                mid = ((a + b) / 2).astype(np.uint8)
                Image.fromarray(mid).save(seq_dir / f'{n:05d}.png'); n += 1
        return sorted(seq_dir.glob('*.png'))

    # -- step 5: compile ---------------------------------------------------

    def compile_video(self, fps=24) -> Path | None:
        seq = self.output_dir / 'final_sequence'
        out = self.output_dir / 'output.mp4'
        cmd = ['ffmpeg', '-y', '-framerate', str(fps), '-i', str(seq / '%05d.png'),
               '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', str(out)]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except FileNotFoundError:
            print('  ffmpeg not found — frames are in', seq)
            return None
        except subprocess.CalledProcessError as e:
            print('  ffmpeg failed:', e.stderr.decode()[-400:])
            return None
        return out

    def run(self, fps=24, make_video=True):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print('filling drawers...');   self.fill_drawers()
        print('blending...');          blended = self.blend()
        print('interpolating...');     seq = self.interpolate(blended)
        print(f'  {len(seq)} frames in the final sequence')
        if make_video:
            print('compiling...')
            v = self.compile_video(fps)
            if v: print(f'  wrote {v}')
        print('done.')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--frames-dir', required=True, help='directory of source frames (searched recursively)')
    p.add_argument('--output', default='./output', help='where to write (default ./output)')
    p.add_argument('--frames', type=int, default=360, help='frames per drawer (default 360)')
    p.add_argument('--drawers', type=int, default=3, help='parallel streams to blend (default 3)')
    p.add_argument('--fps', type=int, default=24, help='output frame rate (default 24)')
    p.add_argument('--size', help='force a resolution, e.g. 1024x576 (default: source size)')
    p.add_argument('--seed', type=int, help='seed the RNG so a run can be reproduced')
    p.add_argument('--no-video', action='store_true', help='stop after the frame sequence')
    a = p.parse_args()

    size = None
    if a.size:
        w, h = a.size.lower().split('x')
        size = (int(w), int(h))

    GenerativeVideoCompiler(a.frames_dir, a.output, a.frames, a.drawers,
                            size, a.seed).run(a.fps, not a.no_video)


if __name__ == '__main__':
    sys.exit(main())
