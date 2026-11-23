# -*- coding: utf-8 -*-
"""第 VI 幕「洞窟」场景生成器 —— 两层高度场夹出的地下通道 + 火把。

为什么用"双层 heightfield"而不是元胞洞穴
------------------------------------
`logic/ca` 是通用元胞自动机（OuterTotalistic / BriansBrain / Wireworld），
做洞穴要先随机初始化再跑 4~5 轮平滑规则，再把 2D 网格挤出成 3D —— 那是
`cellward` 的完整管线。本幕要的是"一条可以穿行的地下通道"，用**两层噪声高度场**
（洞底向上、洞顶倒挂）夹出空腔，20 行就能出画面，且天然有"石柱/挤压"的观感
（两层起伏不同步的地方会接近甚至相交）。

元胞洞穴留给后续精修（那需要"真正的分岔与洞室"），本文件保持
"通道 + 火把"的最小结构。
"""
import argparse
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILM_DIR = os.path.dirname(HERE)
ROOT = os.path.dirname(FILM_DIR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from world3d.logic.noise import heightmap                      # noqa: E402

DURATION = 64.0
GRID = 72
CAVE_W = 110.0            # 洞窟宽（x）
CAVE_D = 210.0            # 洞窟长（z）
FLOOR_H = 11.0            # 洞底起伏幅度
CEIL_BASE = 31.0          # 洞顶基准高度
CEIL_H = -17.0            # 洞顶起伏（负 = 向下垂）
TORCH_COUNT = 9
SEED = 20261127

SCENE_PATH = os.path.join(FILM_DIR, 'scenes', '06_cave.scene.json')
SHOT_PATH = os.path.join(FILM_DIR, 'shots', '06_cave.shot.json')


def _cave_grid(w, h, seed):
    """元胞自动机洞穴（`logic/ca` 的 OuterTotalisticRule）。

    初始化 48% 墙，跑 5 轮 B5678/S45678 —— 这是经典的"洞穴平滑"规则：
    邻居墙多的保持墙、墙少的被侵蚀，几轮后自然形成连通洞室与通道。

    然后**强制清出一条中央走廊**（宽度 8 格）：元胞洞穴的空地率约 55%，
    相机沿 z 直线穿行时会频繁撞墙；留一条走廊既保证运镜可行，
    两侧又保留元胞生成的洞室结构。

    返回 1=墙、0=空地。
    """
    from world3d.logic.ca import OuterTotalisticRule
    rng = random.Random(seed)
    g = [[1 if rng.random() < 0.48 else 0 for _ in range(w)] for _ in range(h)]
    rule = OuterTotalisticRule('cave', born=(5, 6, 7, 8),
                               survive=(4, 5, 6, 7, 8))
    for _ in range(5):
        g = rule.step(g)
    for r in range(h):
        for c in range(w // 2 - 4, w // 2 + 4):
            g[r][c] = 0
    return g


def _to_hm(grid, wall_val, empty_val):
    """元胞图 → 高度图（0..1）。墙与空地各给一个高度，形成"实心墙/空洞"。"""
    return [[round(wall_val if cell else empty_val, 4) for cell in row]
            for row in grid]


def _heights(seed, scale, octaves):
    hm = heightmap(GRID, GRID, scale=scale, seed=seed, octaves=octaves, gain=0.52)
    lo = min(v for r in hm for v in r)
    hi = max(v for r in hm for v in r)
    span = (hi - lo) or 1.0
    return [[round((v - lo) / span, 4) for v in r] for r in hm]


def _rock(dark=0.24):
    return {'preset': 'marble', 'base_color': [dark, dark * 0.94, dark * 0.86],
            'roughness': 0.92, 'metallic': 0.0}


def build_scene():
    kids = []
    grid = _cave_grid(GRID, GRID, SEED)
    walls = sum(sum(r) for r in grid)
    print(f'[cave] 元胞洞穴：{walls / (GRID * GRID):.0%} 墙 / '
          f'{1 - walls / (GRID * GRID):.0%} 空地')
    kids.append({
        'name': 'floor',
        # 墙处抬高、空地压低 ⇒ 洞底出现"土台"
        'mesh': {'builder': 'heightfield',
                 'args': {'hm': _to_hm(grid, 0.56, 0.05),
                          'width': CAVE_W, 'depth': CAVE_D,
                          'height': FLOOR_H, 'y_base': 0.0,
                          'color': [0.26, 0.23, 0.20]}},
        'material': _rock(0.42),
    })
    kids.append({
        'name': 'ceil',
        # 倒挂：墙处压低（垂下来）、空地保持高 ⇒ 与洞底夹出通道
        'mesh': {'builder': 'heightfield',
                 'args': {'hm': _to_hm(grid, 0.46, 0.96),
                          'width': CAVE_W, 'depth': CAVE_D,
                          'height': CEIL_H, 'y_base': CEIL_BASE,
                          'color': [0.18, 0.16, 0.15]}},
        'material': _rock(0.13),
    })
    # 火把：沿通道两侧，交替左右；自发光暖橙（全场唯一光源感）
    for i in range(TORCH_COUNT):
        s = (i + 0.5) / TORCH_COUNT
        z = CAVE_D * 0.5 - s * CAVE_D
        side = -1.0 if i % 2 == 0 else 1.0
        x = side * (CAVE_W * 0.30)
        y = 9.5 + 2.2 * math.sin(i * 1.7)
        kids.append({
            'name': f'torch_{i}',
            'translation': [round(x, 2), round(y, 2), round(z, 2)],
            'mesh': {'builder': 'sphere',
                     'args': {'radius': 0.88, 'segments': 16, 'rings': 12,
                              'color': [1.0, 0.62, 0.24]}},
            'material': {'preset': 'gold', 'base_color': [1.0, 0.70, 0.30],
                         'roughness': 0.35, 'metallic': 0.0,
                         'emissive': [3.8, 1.75, 0.55]},
        })
        # 火把底座（小石柱）
        kids.append({
            'name': f'torchbase_{i}',
            'translation': [round(x, 2), round(y - 1.2, 2), round(z, 2)],
            'mesh': {'builder': 'cylinder',
                     'args': {'radius': 0.30, 'height': 2.0, 'segments': 8,
                              'color': [0.22, 0.20, 0.18]}},
            'material': _rock(0.26),
        })
    return {
        'name': '06-cave',
        'environment': {
            # 几乎无环境光：靠火把 + Bloom 撑亮度，暗处留给观众想象
            'sun_dir': [0.1, 0.95, 0.2],
            'sun_color': [0.45, 0.42, 0.40],
            'sun_intensity': 0.16,
            'sky_zenith': [0.030, 0.026, 0.024],
            'sky_horizon': [0.055, 0.045, 0.040],
            'sky_ground': [0.020, 0.018, 0.016],
            'ibl_intensity': 0.18,
            'sky_intensity': 0.12,
            'fog_density': 0.016,
            'fog_falloff': 0.045,
            'fog_color': [0.10, 0.085, 0.070],
        },
        'root': {'name': 'root', 'children': kids},
    }


def build_shot():
    """相机沿通道穿行：起点在洞外看洞口，中段贴地穿行，末段仰望洞顶。"""
    n = 128                                  # 64s × 2
    times, pos, tgt = [], [], []
    for i in range(n):
        s = i / (n - 1)
        t = s * DURATION
        z = CAVE_D * 0.52 - s * CAVE_D * 0.92
        x = 2.6 * math.sin(s * 6.0)
        # 高度：从洞口外的 18m 降到通道里的 8m，末尾抬到 12m 看洞顶
        y = 14.0 - 9.5 * min(1.0, s * 2.2) + 4.0 * max(0.0, s - 0.78) * 3.0
        pos.append([round(x, 3), round(y, 3), round(z, 3)])
        # 注视点：前方 24m；末段抬高看洞顶
        look_up = max(0.0, (s - 0.78) / 0.22)
        ty = 3.0 + 18.0 * look_up
        tgt.append([round(x * 0.4, 3), round(ty, 3), round(z - 24.0, 3)])
        times.append(round(t, 3))
    return {
        'version': 1,
        'name': '06_cave',
        'duration': DURATION,
        'scene': 'scenes/06_cave.scene.json',
        'acts': [
            {'t': 0.0, 'label': '洞口'},
            {'t': 14.0, 'label': '入洞'},
            {'t': 32.0, 'label': '火把'},
            {'t': 50.0, 'label': '深处'},
            {'t': 64.0, 'label': '仰望'},
        ],
        'notes': '128 关键帧；y 18→7→11，末段抬高注视点看洞顶。',
        'channels': [
            {'node': '$camera', 'prop': 'position', 'interpolation': 'LINEAR',
             'times': times, 'values': pos},
            {'node': '$camera', 'prop': 'target', 'interpolation': 'LINEAR',
             'times': times, 'values': tgt},
            {'node': '$camera', 'prop': 'fov', 'interpolation': 'LINEAR',
             'times': [0.0, DURATION], 'values': [62.0, 58.0]},
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    scene = build_scene()
    shot = build_shot()
    n = len(scene['root']['children'])
    print(f'[cave] OK: {n} 节点（2 地形 + {TORCH_COUNT} 火把）/ '
          f'{len(shot["channels"][0]["times"])} 关键帧')
    if args.check:
        return 0
    for path, data in ((SCENE_PATH, scene), (SHOT_PATH, shot)):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write(chr(10))
        with open(path, encoding='utf-8') as f:
            json.load(f)
        print(f'[cave] 写入 {path} ({os.path.getsize(path) / 1024:.1f} KB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
