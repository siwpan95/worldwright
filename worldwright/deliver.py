"""W5 出片 —— 把 shot 渲成视频。

为什么不用 `preview.py` 逐帧跑
-----------------------------
`preview.py` 每次调用都**重建整个场景**（build_scene 是最贵的一步）。
2520 帧 × 1s/帧 = 40 分钟，纯浪费。

这里**只建一次场景**，循环里只做 `ShotPlayer.apply(t) + render + 读像素 + 写 PPM`，
每帧 ~30ms。PPM 是无损、零依赖、ffmpeg 直接能读的中间格式。

用法::

    python -m worldwright.deliver --scene assets/journey.scene.json \\
        --shot assets/journey.shot.json --start 0 --end 30 --fps 24 \\
        --size 640x360 --out out/journey_30s.mp4
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def render_frames(scene_path, shot_path, t0, t1, fps, size, frames_dir):
    """渲染 [t0, t1) 区间，每帧写一个 PPM。返回实际帧数。"""
    import json

    import pyglet
    from pyglet.gl import GL_RGBA, GL_UNSIGNED_BYTE, glFinish, glReadPixels
    from world3d.engine.camera import FlyCamera
    from world3d.engine.env import LightEnvironment
    from world3d.engine.renderer import Renderer
    from world3d.engine.scene_build import build_scene
    from world3d.engine.shaders import get
    from world3d.engine.shot import Shot, ShotPlayer
    with open(scene_path, encoding='utf-8') as f:
        data = json.load(f)
    w, h = size
    win = pyglet.window.Window(w, h, visible=False)
    win.switch_to()
    try:
        env = LightEnvironment(**(data.get('environment') or {})).bake()
        scene = build_scene(data, get('pbr'))
        shot = Shot.load(shot_path)
        cam = FlyCamera(position=(0, 20, 60), fov=55.0, far=800.0)
        player = ShotPlayer(shot, scene=scene, camera=cam, env=env)
        r = Renderer(w, h, environment=env)
        r.use_oit = False

        os.makedirs(frames_dir, exist_ok=True)
        n = int(round((t1 - t0) * fps))
        t_start = time.time()
        for i in range(n):
            t = t0 + i / float(fps)
            player.apply(t)
            r.render(cam, scene, window=win, time=t)
            raw = (pyglet.gl.GLubyte * (w * h * 4))()
            glFinish()
            glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, raw)
            # PPM (P6) 要 RGB + 上下翻转（GL 原点左下、图片原点左上）。
            # **必须走 numpy**：首版写的是逐像素 Python 双循环，640x360 一帧要几十秒，
            # 2000 帧就是几小时 —— numpy 只要几毫秒。
            import numpy as np
            a = np.frombuffer(bytes(raw), dtype=np.uint8).reshape(h, w, 4)[::-1, :, :3]
            with open(os.path.join(frames_dir, f'f{i:05d}.ppm'), 'wb') as fp:
                fp.write(b'P6\n%d %d\n255\n' % (w, h))
                fp.write(a.tobytes())
            if i % 50 == 0 or i == n - 1:
                el = time.time() - t_start
                eta = el / max(1, i + 1) * (n - i - 1)
                print(f'  {i + 1}/{n}  {el:.0f}s  ETA {eta:.0f}s', flush=True)
        return n
    finally:
        win.close()


def encode(frames_dir, fps, out_path, size):
    """PPM 序列 → H.264（CRF 20、yuv420p、faststart）。"""
    ff = shutil.which('ffmpeg') or 'ffmpeg'
    cmd = [ff, '-y', '-hide_banner', '-loglevel', 'error',
           '-framerate', str(fps), '-i', os.path.join(frames_dir, 'f%05d.ppm'),
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
           '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out_path]
    print('  ffmpeg:', ' '.join(cmd[1:6]), '...', flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print('  !! ffmpeg 失败:', r.stderr.strip()[-300:])
        return False
    return True


def probe(path):
    """用 ffmpeg -i 读关键字段（本机 `E:\ffmpeg\bin` 只有 ffmpeg.exe，没有 ffprobe）。"""
    ff = shutil.which('ffmpeg') or 'ffmpeg'
    try:
        r = subprocess.run([ff, '-hide_banner', '-i', path],
                           capture_output=True, text=True)
        # ffmpeg -i 把信息写在 stderr 里
        for ln in r.stderr.splitlines():
            if 'Duration' in ln or 'Stream #0:0' in ln:
                print('  ' + ln.strip())
    except (OSError, FileNotFoundError):
        print('  (无 ffmpeg，跳过探测)')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--scene', required=True)
    ap.add_argument('--shot', required=True)
    ap.add_argument('--start', type=float, default=0.0)
    ap.add_argument('--end', type=float, default=30.0)
    ap.add_argument('--fps', type=int, default=24)
    ap.add_argument('--size', default='640x360')
    ap.add_argument('--out', default=None)
    ap.add_argument('--frames-dir', default=None)
    ap.add_argument('--keep-frames', action='store_true')
    args = ap.parse_args(argv)

    w, h = (int(x) for x in args.size.lower().split('x'))
    out = args.out or os.path.join(_ROOT, 'out', 'deliver.mp4')
    frames = args.frames_dir or os.path.join(_ROOT, 'out', '_frames')
    if os.path.isdir(frames):
        for f in os.listdir(frames):
            os.remove(os.path.join(frames, f))

    t0 = time.time()
    n = render_frames(args.scene, args.shot, args.start, args.end,
                      args.fps, (w, h), frames)
    print(f'[deliver] 渲染 {n} 帧，用时 {time.time() - t0:.0f}s', flush=True)
    if not encode(frames, args.fps, out, (w, h)):
        return 1
    size_kb = os.path.getsize(out) / 1024
    print(f'[deliver] 编码完成 {out} ({size_kb:.0f} KB)')
    print(probe(out))
    if not args.keep_frames:
        shutil.rmtree(frames, ignore_errors=True)
        print('[deliver] 中间帧已清理')
    print('DELIVER_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
