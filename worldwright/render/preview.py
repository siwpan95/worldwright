# -*- coding: utf-8 -*-
"""最小预览器 —— 渲染一帧到 PNG，用来验证"世界数据真的变成了画面"。

为什么不复用 `3dworld-demos/film/render/passes.py` 的 `ActRenderer`
------------------------------------------------------------------
本仓是独立项目，不该依赖另一个应用仓的渲染脚本。这里只用 `3dworld` 的公开
API（`build_scene` / `Renderer` / `Shot` / `FlyCamera`），40 行就够出图。

用法::

    python -m worldwright.render.preview --scene assets/r02_terrain.scene.json \
        --shot assets/r02_terrain.shot.json --t 20 --out out/r02_t20.png
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


def render_frame(scene_path, shot_path, t, out_path, size=(960, 540),
                 fov_default=55.0):
    """渲染一帧。返回 (draw_calls, triangles)。"""
    import pyglet
    from pyglet.image import get_buffer_manager

    from world3d.engine.camera import FlyCamera
    from world3d.engine.env import LightEnvironment
    from world3d.engine.renderer import Renderer
    from world3d.engine.scene_build import build_scene
    from world3d.engine.shaders import get
    from world3d.engine.shot import Shot

    with open(scene_path, encoding='utf-8') as f:
        scene_data = json.load(f)
    env = LightEnvironment(**(scene_data.get('environment') or {})).bake()

    w, h = size
    win = pyglet.window.Window(w, h, visible=False)
    win.switch_to()
    try:
        scene = build_scene(scene_data, get('pbr'))
        shot = Shot.load(shot_path)

        cam = FlyCamera(position=(0.0, 20.0, 60.0), fov=fov_default, far=800.0)
        # Shot 的通道作用于命名节点；相机用保留名 '$camera'
        from world3d.engine.shot import ShotPlayer
        # 构造时传 scene/camera/env（ShotPlayer 没有 bind 方法）
        player = ShotPlayer(shot, scene=scene, camera=cam, env=env)
        applied = player.apply(float(t))
        resolved = len(shot.channels) if hasattr(shot, 'channels') else 0

        r = Renderer(w, h, environment=env)
        stats = r.render(cam, scene, window=win, time=float(t))
        os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
        get_buffer_manager().get_color_buffer().get_image_data().save(out_path)
        return stats.get('draw_calls', 0), stats.get('triangles', 0), applied, resolved
    finally:
        win.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--scene', required=True)
    ap.add_argument('--shot', required=True)
    ap.add_argument('--t', type=float, default=0.0)
    ap.add_argument('--out', default=None)
    ap.add_argument('--size', default='960x540')
    args = ap.parse_args(argv)
    w, h = (int(x) for x in args.size.lower().split('x'))
    out = args.out or os.path.join(_ROOT, 'out',
                                   f'preview_t{args.t:06.1f}.png')
    draws, tris, applied, resolved = render_frame(
        args.scene, args.shot, args.t, out, (w, h))
    print(f'[preview] t={args.t} 通道 {applied}/{resolved} | '
          f'draw_calls={draws} tris={tris} -> {out}')
    print('PREVIEW_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
