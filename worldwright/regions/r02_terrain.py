"""r02 地脉 —— 消费 worldbuilder 的世界数据（W1 的第一个区域）。

与旧版（`film/gen/terrain.py`）的根本区别
---------------------------------------
| | 旧版 | 本版 |
|---|---|---|
| 地形 | 自己写 fBm + 峡谷雕刻 | `worldbuilder.generate()` 的 `height` |
| 水系 | 无 | `rivers`（16 条，带 `points/length/width_max`） |
| 相机 | 手写的 z 轴直线 | **沿最长的一条河**飞 |
| 生物群系 | 无 | `biomes`（11 种）驱动地表色 |

**相机沿河**是本版的关键：河流的形状来自 worldbuilder 的水文模拟（`hydro.py`），
不是我用正弦编出来的。改 seed → 河形变 → **相机路线跟着变**。
这是"数据驱动"和"手搓"最直接的区别。

用法::

    python -m worldwright.regions.r02_terrain            # 生成 scene/shot JSON
    python -m worldwright.regions.r02_terrain --check
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

GRID = 64                 # worldbuilder 生成分辨率（再做双线性放大到 heightfield）
WORLD_M = 260.0           # 世界尺寸（米）
TERRAIN_H = 78.0          # 高度幅度
Y_BASE = -6.0
DURATION = 66.0
FPS = 30
SEED = 20261123

SCENE_OUT = os.path.join(_ROOT, 'assets', 'r02_terrain.scene.json')
SHOT_OUT = os.path.join(_ROOT, 'assets', 'r02_terrain.shot.json')


def _resize(a, n):
    """把 (H,W) 数组双线性放大到 (n,n)。纯 numpy，不引 scipy。"""
    h, w = a.shape
    yi = np.linspace(0, h - 1, n)
    xi = np.linspace(0, w - 1, n)
    y0 = np.floor(yi).astype(int).clip(0, h - 1)
    y1 = np.minimum(y0 + 1, h - 1)
    x0 = np.floor(xi).astype(int).clip(0, w - 1)
    x1 = np.minimum(x0 + 1, w - 1)
    fy = (yi - y0)[:, None]
    fx = (xi - x0)[None, :]
    top = a[y0][:, x0] * (1 - fx) + a[y0][:, x1] * fx
    bot = a[y1][:, x0] * (1 - fx) + a[y1][:, x1] * fx
    return top * (1 - fy) + bot * fy


def _biome_color(biomes):
    """11 种 biome → 地表色（简化调色板，够区分即可）。"""
    pal = [(0.16, 0.24, 0.34), (0.20, 0.34, 0.30), (0.26, 0.32, 0.20),
           (0.30, 0.28, 0.18), (0.36, 0.30, 0.20), (0.28, 0.24, 0.18),
           (0.34, 0.31, 0.26), (0.38, 0.35, 0.30), (0.22, 0.26, 0.28),
           (0.30, 0.26, 0.22), (0.24, 0.22, 0.20)]
    idx = int(np.bincount(np.asarray(biomes).flatten()).argmax())
    c = pal[idx % len(pal)]
    # 提亮 1.7 倍：首版直接用调色板原值，低角度侧逆光下地形几乎全黑
    return tuple(min(1.0, v * 1.7) for v in c), idx


def build_world_data():
    from superengine.assembly import boot
    ctx, _ = boot()
    w = ctx.worldbuilder.generate(GRID, GRID, seed=SEED)
    return w


def build_scene(w):
    hm = _resize(np.asarray(w['height'], dtype=float), 96)     # heightfield 分辨率
    col, biome_idx = _biome_color(w['biomes'])
    return {
        'name': 'r02-terrain',
        'environment': {
            'sun_dir': [-0.44, 0.30, 0.85],
            'sun_color': [1.00, 0.74, 0.50],
            'sun_intensity': 2.05,
            'sky_zenith': [0.055, 0.075, 0.135],
            'sky_horizon': [0.42, 0.31, 0.27],
            'sky_ground': [0.075, 0.065, 0.058],
            'ibl_intensity': 0.55,
            'sky_intensity': 0.80,
            'fog_density': 0.0034,
            'fog_falloff': 0.030,
            'fog_color': [0.50, 0.46, 0.43],
        },
        'root': {'name': 'root', 'children': [{
            'name': 'terrain',
            'mesh': {'builder': 'heightfield',
                     'args': {'hm': [[round(float(v), 4) for v in row] for row in hm],
                              'width': WORLD_M, 'depth': WORLD_M,
                              'height': TERRAIN_H, 'y_base': Y_BASE,
                              'color': list(col)}},
            'material': {'preset': 'marble', 'base_color': list(col),
                         'roughness': 0.94, 'metallic': 0.0},
        }]},
    }, biome_idx


def build_shot(w):
    """相机沿**最长的一条河**飞 —— 河的形状来自 worldbuilder 的水文模拟。"""
    rivers = [r for r in (w.get('rivers') or []) if r.get('points')]
    if not rivers:
        raise RuntimeError('worldbuilder 没产出河流，无从生成相机路径')
    river = max(rivers, key=lambda r: float(r.get('length', 0.0)))
    pts = [(float(x), float(y)) for x, y in river['points']]

    # 网格坐标 → 世界坐标（worldbuilder 的 (0..GRID) 映射到 ±WORLD_M/2）
    def to_world(px, py):
        return ((px / GRID - 0.5) * WORLD_M, (py / GRID - 0.5) * WORLD_M)

    # 地面高度（沿河取，用来把相机抬到水面之上）
    h = np.asarray(w['height'], dtype=float)

    def ground_at(px, py):
        ix = int(np.clip(px, 0, GRID - 1))
        iy = int(np.clip(py, 0, GRID - 1))
        return Y_BASE + float(h[iy, ix]) * TERRAIN_H

    n = int(DURATION * FPS / 10)          # 每 1/3 秒一个关键帧
    times, pos, tgt = [], [], []
    for i in range(n):
        u = i / (n - 1)
        k = u * (len(pts) - 1)
        k0 = int(k)
        k1 = min(len(pts) - 1, k0 + 1)
        f = k - k0
        px = pts[k0][0] + (pts[k1][0] - pts[k0][0]) * f
        py = pts[k0][1] + (pts[k1][1] - pts[k0][1]) * f
        wx, wz = to_world(px, py)
        gy = ground_at(px, py)
        # 相机：河面上方 9m，略微左右摆（沿河看两侧谷壁）
        pos.append([round(wx + 2.5 * np.sin(u * 9.0), 2),
                    round(gy + 22.0, 2), round(wz, 2)])
        # 注视点：前方 12m 的河道
        uk = min(1.0, u + 12.0 / max(1.0, len(pts)))
        kk = min(len(pts) - 1, int(uk * (len(pts) - 1)))
        tx, tz = to_world(*pts[kk])
        tgt.append([round(tx, 2), round(ground_at(*pts[kk]) + 3.0, 2), round(tz, 2)])
        times.append(round(u * DURATION, 3))
    return {
        'version': 1, 'name': 'r02_terrain', 'duration': DURATION,
        'scene': 'assets/r02_terrain.scene.json',
        'acts': [{'t': 0.0, 'label': '河源'}, {'t': DURATION, 'label': '入海'}],
        'notes': (f'相机沿 worldbuilder 最长河（length={river.get("length")}, '
                  f'{len(pts)} 点）飞行；地形 height {GRID}x{GRID} 放大到 96x96。'),
        'channels': [
            {'node': '$camera', 'prop': 'position', 'interpolation': 'LINEAR',
             'times': times, 'values': pos},
            {'node': '$camera', 'prop': 'target', 'interpolation': 'LINEAR',
             'times': times, 'values': tgt},
            {'node': '$camera', 'prop': 'fov', 'interpolation': 'LINEAR',
             'times': [0.0, DURATION], 'values': [56.0, 50.0]},
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    w = build_world_data()
    scene, biome_idx = build_scene(w)
    shot = build_shot(w)
    n_rivers = len(w.get('rivers') or [])
    print(f'[r02] worldbuilder: height {np.asarray(w["height"]).shape} / '
          f'{n_rivers} 条河 / biome 主色 #{biome_idx} / 相机 {len(shot["channels"][0]["times"])} 帧')
    if args.check:
        print('R02_CHECK_OK')
        return 0
    os.makedirs(os.path.dirname(SCENE_OUT), exist_ok=True)
    for path, data in ((SCENE_OUT, scene), (SHOT_OUT, shot)):
        with open(path, 'w', encoding='utf-8', newline='') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write(chr(10))
        with open(path, encoding='utf-8') as f:
            json.load(f)
        print(f'[r02] 写入 {path} ({os.path.getsize(path) / 1024:.1f} KB)')
    print('R02_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
