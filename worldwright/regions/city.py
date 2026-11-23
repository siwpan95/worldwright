# -*- coding: utf-8 -*-
"""第 III 幕「城邦」场景生成器 —— 一条主街 + 两侧密集街区。

范围说明（2026-11-23）
--------------------
引擎有 `logic/town.generate_town()`（Voronoi 街区 + 城墙 + 街道，返回
bounds/center/wall/plaza/streets/wards 的 dict）。本轮**没有**接入它：
深挖 ward→patches 的内部结构需要额外时间，而本幕的当务之急是把"城邦"的
视觉基调立起来（密集建筑 + 相机穿街 + 黄昏暖光）。布局源留作精修项，
接口保持"建筑列表 → box"，换成 town 输出时只需改 `_build_blocks()`。

构图
----
主街沿 Z 轴、宽 10 米（|x| < 5 留空），两侧 7 行 × 12 列的街区网格，
建筑高度 5~26 米随机（靠中心越高，形成天际线）。相机沿主街俯冲：
从 42 米高空降到 7 米，贴着街面飞出去。
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

DURATION = 80.0
SEED = 20261123
STREET_HALF = 5.0          # 主街半宽
PITCH = 10.6               # 街区网格间距（密：13→10.6）
ROWS = 14                  # 沿 Z 的街区数
COLS = 5                   # 每侧沿 X 的街区数

SCENE_PATH = os.path.join(FILM_DIR, 'scenes', '03_city.scene.json')
SHOT_PATH = os.path.join(FILM_DIR, 'shots', '03_city.shot.json')


def _metal_like(b, rough=0.72):
    return {'preset': 'marble', 'base_color': [b, b * 0.96, b * 0.90],
            'roughness': rough, 'metallic': 0.0}


def _build_blocks():
    """两侧街区：box 建筑 + 高度随离中心距离衰减（形成天际线）。"""
    rng = random.Random(SEED)
    kids = []
    idx = 0
    for row in range(ROWS):
        z = (ROWS - 1) * 0.5 * PITCH - row * PITCH
        # 沿街方向越靠中间越高（"城心"），两头矮
        center_falloff = 1.0 - abs(z) / ((ROWS * 0.5) * PITCH + 1e-6)
        for side in (-1, 1):
            for col in range(COLS):
                if rng.random() < 0.14:          # 空地/小广场
                    continue
                x = side * (STREET_HALF + 4.6 + col * PITCH)
                w = 8.6 + rng.uniform(-1.2, 1.2)
                d = 8.6 + rng.uniform(-1.2, 1.2)
                # 高度 8~40m：首版 5~26 在 7m 相机高度下看只像"郊区平房"
                h = (8.0 + 32.0 * max(0.06, center_falloff)
                     * (0.45 + 0.75 * rng.random()))
                # 越靠街越亮一点（临街店铺感），靠里更暗
                shade = 0.135 + 0.105 * (1.0 - col / COLS)   # 压暗：首版 0.26~0.42 在主街上像两堵白墙
                kids.append({
                    'name': f'blk_{idx}',
                    'translation': [round(x, 3), round(h * 0.5, 3), round(z, 3)],
                    'mesh': {'builder': 'box',
                             'args': {'sx': round(w, 3), 'sy': round(h, 3),
                                      'sz': round(d, 3),
                                      'color': [shade, shade * 0.93, shade * 0.82]}},
                    'material': _metal_like(shade, 0.80),
                })
                idx += 1
    return kids


def build_scene():
    kids = []
    # --- 地面 / 街道 ---
    kids.append({
        'name': 'ground',
        'mesh': {'builder': 'ground_grid',
                 'args': {'half': 110, 'tile': 4.0,
                          'color_a': [0.20, 0.18, 0.16],
                          'color_b': [0.15, 0.135, 0.12]}},
        'material': _metal_like(0.22, 0.88),
    })
    # --- 主街：一条略亮的石板带（压在地面上方 2cm，避免 z-fighting）---
    kids.append({
        'name': 'street',
        'mesh': {'builder': 'plane',
                 'args': {'width': STREET_HALF * 2.0, 'depth': ROWS * PITCH,
                          'segs': 24, 'y': 0.02,
                          'color': [0.27, 0.25, 0.22]}},
        'material': _metal_like(0.28, 0.80),
    })
    kids += _build_blocks()
    return {
        'name': '03-city',
        'environment': {
            # 黄昏侧逆光：长影子、暖墙、冷天
            'sun_dir': [-0.62, 0.28, 0.73],
            'sun_color': [1.00, 0.68, 0.40],
            'sun_intensity': 1.45,
            'sky_zenith': [0.10, 0.13, 0.24],
            'sky_horizon': [0.52, 0.38, 0.30],
            'sky_ground': [0.09, 0.08, 0.07],
            'ibl_intensity': 0.60,
            'sky_intensity': 0.55,
            'fog_density': 0.0026,
            'fog_falloff': 0.030,
            'fog_color': [0.46, 0.38, 0.33],
        },
        'root': {'name': 'root', 'children': kids},
    }


def build_shot():
    """相机沿主街俯冲（程序化密集关键帧，沿用第 II 幕的教训）。"""
    n = 160                                  # 80s × 2
    times, pos, tgt = [], [], []
    for i in range(n):
        s = i / (n - 1)
        t = s * DURATION
        # z 只走 +110 → -58：街区 z 范围是 ±(ROWS*PITCH/2)=±74，
        # 首版走到 -120 时已飞出城，末段 17 秒只剩街面和天空。
        z = 110.0 - s * 168.0                # +110 → -58
        x = 1.8 * math.sin(s * 7.2)          # 轻微蛇形
        # 高度：起手 42 米俯瞰天际线，**中段就得压到街面**（首版 s^0.85 在
        # 中点还有 24m，画面全是屋顶）。改 s^0.55 让下降更早、更狠。
        y = 42.0 - 35.0 * (s ** 0.55) + 2.5 * math.sin(s * 5.0)
        pos.append([round(x, 3), round(max(y, 5.5), 3), round(z, 3)])
        # 注视点：前方 30m、比相机低 4m（贴街飞行时看街面而非天空）
        tgt.append([round(x * 0.5, 3), round(max(y - 4.0, 2.0), 3), round(z - 30.0, 3)])
        times.append(round(t, 3))
    return {
        'version': 1,
        'name': '03_city',
        'duration': DURATION,
        'scene': 'scenes/03_city.scene.json',
        'acts': [
            {'t': 0.0, 'label': '远眺城郭'},
            {'t': 24.0, 'label': '越墙'},
            {'t': 48.0, 'label': '主街'},
            {'t': 66.0, 'label': '街面'},
            {'t': 80.0, 'label': '出城'},
        ],
        'notes': '相机 160 个等距关键帧，LINEAR；高度 42→6、z +120→-120，轻微蛇形。',
        'channels': [
            {'node': '$camera', 'prop': 'position', 'interpolation': 'LINEAR',
             'times': times, 'values': pos},
            {'node': '$camera', 'prop': 'target', 'interpolation': 'LINEAR',
             'times': times, 'values': tgt},
            {'node': '$camera', 'prop': 'fov', 'interpolation': 'LINEAR',
             'times': [0.0, DURATION], 'values': [56.0, 52.0]},
            {'node': '$env', 'prop': 'sun_intensity', 'interpolation': 'LINEAR',
             'times': [0.0, 30.0, DURATION], 'values': [1.6, 2.35, 2.10]},
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)

    scene = build_scene()
    n_blk = sum(1 for c in scene['root']['children'] if c['name'].startswith('blk_'))
    if n_blk < 80:
        print(f'[city] FAIL: 建筑太少（{n_blk}）')
        return 1
    shot = build_shot()
    print(f'[city] OK: {len(scene["root"]["children"])} 节点（{n_blk} 栋建筑）/ '
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
        print(f'[city] 写入 {path} ({os.path.getsize(path) / 1024:.1f} KB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
