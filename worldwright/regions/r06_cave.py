"""r06 洞窟 —— 消费 worldbuilder 的地牢图（W1 第二区）。

与旧版（`film/gen/cave.py`）的区别
---------------------------------
| | 旧版 | 本版 |
|---|---|---|
| 洞窟形态 | `ca` 元胞自动机 + **强制清一条中央走廊** | `worldbuilder.generate_dungeon()` 的 10 个房间 + 9 条连接 |
| 相机 | 沿 z 轴直线（会撞墙，所以强行清走廊） | **按房间连接图走**，天然不撞墙 |
| 房间 | 无 | 10 个矩形房间（`x/y/w/h/cx/cy`） |

**"强制清走廊"是手搓的补丁**：因为元胞洞穴不保证连通，我只能人为挖一条直的。
本版的地牢图本身就连通（`connections` 是图），**相机可以真的按房间走**。

用法::

    python -m worldwright.regions.r06_cave
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (r'D:\projects\repos\superengine', r'D:\projects\repos\worldbuilder',
           _ROOT):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

GW, GH = 44, 30              # 地牢网格
ROOMS = 12
WORLD_W, WORLD_D = 120.0, 82.0
FLOOR_H, CEIL_H = 12.0, -18.0
FLOOR_BASE, CEIL_BASE = 0.0, 26.0
DURATION = 64.0
SEED = 20261123

SCENE_OUT = os.path.join(_ROOT, 'assets', 'r06_cave.scene.json')
SHOT_OUT = os.path.join(_ROOT, 'assets', 'r06_cave.shot.json')


def build_dungeon():
    from superengine.assembly import boot
    ctx, _ = boot()
    return ctx.worldbuilder.generate_dungeon(GW, GH, rooms=ROOMS)


def _room_path(d):
    """用 connections 做 BFS，得到一条按房间走的访问序列（0 号房出发）。"""
    adj = {i: [] for i in range(len(d['rooms']))}
    for a, b in d['connections']:
        adj[a].append(b)
        adj[b].append(a)
    seen, order, queue = {0}, [0], [0]
    while queue:
        cur = queue.pop(0)
        for nb in adj[cur]:
            if nb not in seen:
                seen.add(nb)
                order.append(nb)
                queue.append(nb)
    return order, len(seen)


def build_scene(d):
    g = np.asarray(d['grid'])
    # 地板：可走处低、墙处高；洞顶：反过来（墙垂下来）
    floor = [[0.05 if v else 0.62 for v in row] for row in g]
    ceil = [[0.96 if v else 0.40 for v in row] for row in g]
    return {
        'name': 'r06-cave',
        'environment': {
            'sun_dir': [0.88, 0.34, -0.32],   # 侧光：洞顶挡住顶光，只有斜射进洞口的光能照到内壁
            'sun_color': [1.00, 0.86, 0.66],   # 暖光，像洞口透进来的日光
            'sun_intensity': 1.75,
            'sky_zenith': [0.008, 0.010, 0.016],
            'sky_horizon': [0.028, 0.030, 0.040],
            'sky_ground': [0.004, 0.005, 0.007],
            'ibl_intensity': 0.62,
            'sky_intensity': 0.30,
            'fog_density': 0.0090,
            'fog_falloff': 0.020,
            'fog_color': [0.045, 0.042, 0.040],
        },
        # 点光源（引擎 0.9.2 起 scene JSON 支持）：前 4 个房间各一盏火把。
        # 上限就是 4（shader 里是 4 个具名 uniform）；radius 12m 让光只覆盖
        # 本房间，不泄漏到隔壁 —— 这正是 0.9.2 加平滑窗口要解决的问题。
        'lights': [
            {'pos': [round((r['cx'] / (GW - 1) - 0.5) * WORLD_W, 2),
                     3.4,
                     round((r['cy'] / (GH - 1) - 0.5) * WORLD_D, 2)],
             'color': [900.0, 540.0, 250.0],   # HDR：1/d² 在 10m 处只剩 1%，所以颜色要给到千量级
             'radius': 12.0}
            for r in d['rooms'][:4]
        ],
        'root': {'name': 'root', 'children': [
            {'name': 'floor',
             'mesh': {'builder': 'heightfield',
                      'args': {'hm': floor, 'width': WORLD_W, 'depth': WORLD_D,
                               'height': FLOOR_H, 'y_base': FLOOR_BASE,
                               'color': [0.30, 0.27, 0.23]}},
             'material': {'preset': 'marble', 'base_color': [0.30, 0.27, 0.23],
                          'roughness': 0.88, 'metallic': 0.0}},
            {'name': 'ceil',
             'mesh': {'builder': 'heightfield',
                      'args': {'hm': ceil, 'width': WORLD_W, 'depth': WORLD_D,
                               'height': CEIL_H, 'y_base': CEIL_BASE,
                               'color': [0.17, 0.15, 0.14]}},
             'material': {'preset': 'marble', 'base_color': [0.17, 0.15, 0.14],
                          'roughness': 0.92, 'metallic': 0.0}},
            # 火把：每个房间中心一颗自发光球。
            # **没有点光源**（3dworld 的 env 只有方向光 + IBL），所以火把只照亮
            # 自己的球体，不照亮墙面 —— 首版完全没放，画面全黑。
            *[{'name': f'torch{i}',
               'translation': [round((r['cx'] / (GW - 1) - 0.5) * WORLD_W, 2),
                               3.2,
                               round((r['cy'] / (GH - 1) - 0.5) * WORLD_D, 2)],
               'mesh': {'builder': 'sphere',
                        'args': {'radius': 0.5, 'segments': 10, 'rings': 8,
                                 'color': [1.0, 0.72, 0.36]}},
               'material': {'preset': 'marble', 'base_color': [1.0, 0.72, 0.36],
                            'roughness': 0.4, 'metallic': 0.0,
                            'emissive': [2.6, 1.5, 0.55]}}
              for i, r in enumerate(d['rooms'])],
        ]},
    }


def build_shot(d):
    order, reached = _room_path(d)
    if reached < len(d['rooms']):
        raise RuntimeError(f'地牢图不连通：只到达 {reached}/{len(d["rooms"])} 个房间')

    def room_world(idx):
        r = d['rooms'][idx]
        wx = (r['cx'] / (GW - 1) - 0.5) * WORLD_W
        wz = (r['cy'] / (GH - 1) - 0.5) * WORLD_D
        return wx, wz

    # 房间序列 → 折线；每段插值出若干关键帧
    n_per_seg = 12
    times, pos, tgt = [], [], []
    total_frames = (len(order) - 1) * n_per_seg
    for si in range(len(order) - 1):
        a, b = room_world(order[si]), room_world(order[si + 1])
        for k in range(n_per_seg):
            u = k / n_per_seg
            wx = a[0] + (b[0] - a[0]) * u
            wz = a[1] + (b[1] - a[1]) * u
            f = (si * n_per_seg + k) / max(1, total_frames)
            # 洞窟内相机：地板之上 4.5m，缓慢上下浮动
            pos.append([round(wx, 2), round(6.5 + 0.6 * np.sin(f * 11.0), 2), round(wz, 2)])
            # 注视点：下一段方向
            vx = (b[0] - a[0]) or 0.001
            vz = (b[1] - a[1]) or 0.001
            n = (vx * vx + vz * vz) ** 0.5
            tgt.append([round(wx + vx / n * 17.0, 2), round(3.6, 2),
                        round(wz + vz / n * 17.0, 2)])
            times.append(round(f * DURATION, 3))
    # 收尾
    pos.append(pos[-1])
    tgt.append(tgt[-1])
    times.append(round(DURATION, 3))
    return {
        'version': 1, 'name': 'r06_cave', 'duration': DURATION,
        'scene': 'assets/r06_cave.scene.json',
        'acts': [{'t': 0.0, 'label': '入洞'}, {'t': DURATION, 'label': '深处'}],
        'notes': (f'相机沿地牢图的 BFS 房间序列（{len(order)} 房 / {reached} 连通）走，'
                  f'每段 {n_per_seg} 帧。'),
        'channels': [
            {'node': '$camera', 'prop': 'position', 'interpolation': 'LINEAR',
             'times': times, 'values': pos},
            {'node': '$camera', 'prop': 'target', 'interpolation': 'LINEAR',
             'times': times, 'values': tgt},
            {'node': '$camera', 'prop': 'fov', 'interpolation': 'LINEAR',
             'times': [0.0, DURATION], 'values': [66.0, 58.0]},
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    d = build_dungeon()
    scene = build_scene(d)
    shot = build_shot(d)
    n_rooms = len(d['rooms'])
    n_conn = len(d['connections'])
    cov = float(np.asarray(d['grid']).mean())
    print(f'[r06] 地牢 {GW}x{GH} / {n_rooms} 房 / {n_conn} 连接 / 可走 {cov:.0%} / '
          f'相机 {len(shot["channels"][0]["times"])} 帧')
    if args.check:
        print('R06_CHECK_OK')
        return 0
    os.makedirs(os.path.dirname(SCENE_OUT), exist_ok=True)
    for path, data in ((SCENE_OUT, scene), (SHOT_OUT, shot)):
        with open(path, 'w', encoding='utf-8', newline='') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write(chr(10))
        with open(path, encoding='utf-8') as f:
            json.load(f)
        print(f'[r06] 写入 {path} ({os.path.getsize(path) / 1024:.1f} KB)')
    print('R06_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
