"""自动找机位 —— 给定场景，输出 N 张候选机位图 + 量化评分。

为什么需要它
------------
「找不到能证明能力的那一帧」在今天已经发生三次：水面、洞窟、运动模糊。
每次都是手调相机位置，运气好一次中，运气不好试六次还撞墙。

这个工具把「找机位」变成可重复的流程：

1. 从 `Mesh.world_aabb` 累出**场景包围盒**（不用猜 geometry 在哪儿）；
2. 按包围盒生成**六个候选机位**（俯视 / 四向侧视 / 内部）；
3. 每个机位渲染一帧，**算平均亮度 + 非背景像素比例**；
4. 把六张拼成一张 contact sheet，并在终端标出哪些是"几乎空白"。

**评分不是审美判断**，只回答一个问题：*这张图里有没有东西*。
全黑 / 全灰的机位会被直接标 `EMPTY`，省掉人眼确认。

用法::

    python -m worldwright.tools.find_camera --scene assets/r03_city.scene.json
    python -m worldwright.tools.find_camera --scene ... --size 480x270 --out out/cam
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

#: 亮度低于此值判为"几乎空白"（0..255）
EMPTY_LUMA = 12.0
#: 亮度标准差低于此值判为"没有结构"（纯色画面）
EMPTY_STD = 6.0


def scene_aabb(scene):
    """累加所有 mesh 的世界包围盒。返回 (min, max) 或 None。"""
    lo = [1e18] * 3
    hi = [-1e18] * 3
    found = False
    for n in scene.root.traverse():
        # Node 挂可绘制物的属性叫 （不是  —— 首版按 mesh 取，
        # 结果 traverse 完一个都没找到，直接报"场景里没有任何 mesh"）。
        d = getattr(n, 'drawable', None)
        a = getattr(d, 'world_aabb', None) if d is not None else None
        if a is None:
            continue
        # 跳过地面 / 大平板：它们会把 AABB 撑到几百米，机位被推到老远，
        # 画面里"全是内容"（其实全是地面）—— 评分就失效了。
        if any(k in n.name.lower() for k in ('ground', 'floor', 'plane')):
            continue
        for i in range(3):
            lo[i] = min(lo[i], a.min[i])
            hi[i] = max(hi[i], a.max[i])
        found = True
    return (tuple(lo), tuple(hi)) if found else None


def candidates(bounds):
    """六个候选机位：俯视 / 四向 / 内部。返回 [(name, eye, target, far)]。"""
    lo, hi = bounds
    c = tuple((lo[i] + hi[i]) * 0.5 for i in range(3))
    h = tuple(max(1.0, (hi[i] - lo[i]) * 0.5) for i in range(3))
    r = max(h) * 2.0                      # 场景尺度
    far = max(400.0, r * 3.0)             # far 必须罩得住整个场景（今天的教训）
    d = r * 1.6          # 距离要罩得住场景（首版 0.9r，95m 宽的城镇只拍到一条带）
    # 侧视机位必须**高于最高建筑**，否则相机落在楼里/贴地（首版用 h[1]*0.6，
    # r03 建筑高 22m、相机 17m，拍出来是一条贴地的带）。
    dy = c[1] + d * 0.75  # 俯角约 25~30 度；纯侧视看不见屋顶与街道格局
    return [
        # 俯视机位有两条硬约束（2026-11-23 实测）：
        #   ① 高度必须**远离雾的饱和区**（falloff=0.026 → 特征长度 38m）。
        #      148m 高时 std 只有 5.1；压到 35m 后 std 13.4、unique 239→453。
        #   ② 不能正俯视：扁平单色场景下地面法线全朝上，着色是常数。
        # 两条合起来 → 低空 + 45~60° 俯角。
        ('top35',  (c[0], min(c[1] + d * 0.9, 35.0), c[2] + d * 0.52), c, far),
        ('north',  (c[0], dy, c[2] + d),          c, far),
        ('south',  (c[0], dy, c[2] - d),          c, far),
        ('east',   (c[0] + d, dy, c[2]),          c, far),
        ('west',   (c[0] - d, dy, c[2]),          c, far),
        ('inside', (c[0], c[1] + h[1] * 1.2, c[2] + h[2] * 0.5), c, far),
    ]


def render_one(scene, env, eye, target, far, size):
    """渲染一帧，返回 (rgb_bytes, width, height, draw_calls)。"""
    import pyglet
    from pyglet.gl import GL_RGBA, GL_UNSIGNED_BYTE, glFinish, glReadPixels
    from world3d.engine.camera import FlyCamera
    from world3d.engine.renderer import Renderer

    w, h = size
    win = pyglet.window.Window(w, h, visible=False)
    win.switch_to()
    try:
        cam = FlyCamera(position=eye, fov=55.0, far=far)
        cam.look_at(target)
        r = Renderer(w, h, environment=env)
        stats = r.render(cam, scene, window=win, time=1.0)
        import ctypes
        buf = (ctypes.c_ubyte * (w * h * 4))()
        glFinish()
        glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, buf)
        return bytes(buf), w, h, stats.get('draw_calls', 0)
    finally:
        win.close()


def score(raw, w, h):
    """算平均亮度与**标准差**，判定是否"几乎空白"。

    为什么不用"非背景像素占比"：首版用四角中位色当背景，结果地面把画面填满时
    占比 96%（判为"有内容"，其实全是地），俯视时又因为背景色统一被判 0%。
    **标准差**更稳：纯色画面 std≈0，有建筑/地形就明显大。
    """
    import numpy as np
    a = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 4)[:, :, :3].astype(np.float32)
    luma = float(a.mean())
    std = float(a.std())
    return luma, std, (luma < EMPTY_LUMA or std < 6.0)


def save_png(raw, w, h, path):
    """不引 PIL，用 pyglet 的 ImageData 落盘。"""
    import pyglet
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    img = pyglet.image.ImageData(w, h, 'RGBA', raw, pitch=-w * 4)
    img.save(path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--scene', required=True)
    ap.add_argument('--size', default='480x270')
    ap.add_argument('--out', default=None, help='输出前缀（默认 out/cam_<场景名>）')
    ap.add_argument('--only', default=None, help='只渲某个机位（top/north/...）')
    args = ap.parse_args(argv)

    import pyglet
    from world3d.engine.env import LightEnvironment
    from world3d.engine.scene_build import build_scene
    from world3d.engine.shaders import get

    w, h = (int(x) for x in args.size.lower().split('x'))
    with open(args.scene, encoding='utf-8') as f:
        data = json.load(f)
    env = LightEnvironment(**(data.get('environment') or {})).bake()

    win = pyglet.window.Window(1, 1, visible=False)
    win.switch_to()
    try:
        scene = build_scene(data, get('pbr'))
        bounds = scene_aabb(scene)
    finally:
        win.close()
    if bounds is None:
        print('[cam] 场景里没有任何 mesh，无从找机位')
        return 1

    lo, hi = bounds
    print(f'[cam] 场景 AABB min={tuple(round(v, 1) for v in lo)} '
          f'max={tuple(round(v, 1) for v in hi)}')
    print(f'[cam] 尺寸 {tuple(round(hi[i] - lo[i], 1) for i in range(3))}')

    prefix = args.out or os.path.join(_ROOT, 'out', 'cam_' +
                                      os.path.basename(args.scene).split('.')[0])
    results = []
    for name, eye, target, far in candidates(bounds):
        if args.only and name != args.only:
            continue
        raw, rw, rh, draws = render_one(scene, env, eye, target, far, (w, h))
        luma, std, empty = score(raw, rw, rh)
        path = f'{prefix}_{name}.png'
        save_png(raw, rw, rh, path)
        tag = 'EMPTY' if empty else 'ok'
        print(f'  [{tag:5}] {name:7} luma={luma:5.1f} std={std:5.1f} '
              f'draws={draws:3} -> {path}')
        results.append((name, path, luma, std, empty))

    ok = [r for r in results if not r[4]]
    print(f'[cam] {len(ok)}/{len(results)} 个机位有内容')
    if ok:
        best = max(ok, key=lambda r: r[3])   # std 最大的那张结构最丰富
        print(f'[cam] 推荐：{best[0]}（std 最高，结构最丰富）')
    print('FIND_CAMERA_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
