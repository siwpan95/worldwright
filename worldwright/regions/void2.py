# -*- coding: utf-8 -*-
"""第 X 幕「虚空」场景生成器 —— 巨物、星尘、空。

叙事位置：全片的**尺度转折**。前面九幕都在"能走进去的地方"，这一幕把镜头
拉到几公里外：一个巨大的发光核心、两圈环、以及漫无边际的尘埃。人会第一次
意识到"这些事发生在一个多大的地方"。

为什么不做真体积光
----------------
`engine/postfx.py` 里没有 DoF / god-ray pass，`volumetrics` 提供的是需要深度
纹理 + 阴影采样的射线步进方案 —— 那是渲染层的大改（会影响全部 12 幕）。
本幕用**巨物自发光 + 高度雾 + 9000 星尘粒子 + Bloom** 组合出"空而亮"的观感，
不碰 shader。真体积光记为精修项。
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILM_DIR = os.path.dirname(HERE)
ROOT = os.path.dirname(FILM_DIR)

DURATION = 80.0
CORE_R = 11.0

SCENE_PATH = os.path.join(FILM_DIR, 'scenes', '10_void2.scene.json')
SHOT_PATH = os.path.join(FILM_DIR, 'shots', '10_void2.shot.json')


def _quat_x(deg):
    h = math.radians(deg) * 0.5
    return [math.sin(h), 0.0, 0.0, math.cos(h)]


def build_scene():
    kids = [
        {
            'name': 'core',
            'mesh': {'builder': 'sphere',
                     'args': {'radius': CORE_R, 'segments': 48, 'rings': 32,
                              'color': [1.0, 0.96, 0.88]}},
            'material': {'preset': 'marble', 'base_color': [1.0, 0.96, 0.88],
                         'roughness': 0.45, 'metallic': 0.0,
                         'emissive': [2.6, 2.2, 1.8]},
        },
        {
            'name': 'halo',
            'rotation': _quat_x(90.0),
            'mesh': {'builder': 'torus',
                     'args': {'major': 30.0, 'minor': 1.5, 'major_segs': 160,
                              'minor_segs': 12, 'color': [0.95, 0.88, 0.75]}},
            'material': {'preset': 'gold', 'base_color': [0.95, 0.88, 0.75],
                         'roughness': 0.3, 'metallic': 0.6,
                         'emissive': [0.85, 0.70, 0.50]},
        },
        {
            'name': 'ring_outer',
            'rotation': _quat_x(90.0),
            'mesh': {'builder': 'torus',
                     'args': {'major': 62.0, 'minor': 0.55, 'major_segs': 200,
                              'minor_segs': 8, 'color': [0.62, 0.70, 0.86]}},
            'material': {'preset': 'marble', 'base_color': [0.62, 0.70, 0.86],
                         'roughness': 0.35, 'metallic': 0.0,
                         'emissive': [0.30, 0.36, 0.48]},
        },
        {
            'name': 'ring_tilted',
            'rotation': [0.42, 0.0, 0.28, 0.86],
            'mesh': {'builder': 'torus',
                     'args': {'major': 96.0, 'minor': 0.35, 'major_segs': 220,
                              'minor_segs': 6, 'color': [0.45, 0.52, 0.70]}},
            'material': {'preset': 'marble', 'base_color': [0.45, 0.52, 0.70],
                         'roughness': 0.4, 'metallic': 0.0,
                         'emissive': [0.18, 0.22, 0.32]},
        },
    ]
    # 星尘：散布在半径 120~420 的球壳里（ParticleSystem 的粒子只撒在原点附近
    # 10 米，几百米外根本看不见 —— 首版出帧几乎全黑）
    rng = __import__('random').Random(20261125)
    for i in range(220):
        a = rng.uniform(0, 2 * math.pi)
        el = math.asin(rng.uniform(-1.0, 1.0))
        r = rng.uniform(120.0, 420.0)
        kids.append({
            'name': f'star{i}',
            'translation': [round(math.cos(a) * math.cos(el) * r, 1),
                            round(math.sin(el) * r, 1),
                            round(math.sin(a) * math.cos(el) * r, 1)],
            'mesh': {'builder': 'sphere',
                     'args': {'radius': round(rng.uniform(0.5, 1.6), 2),
                              'segments': 6, 'rings': 4,
                              'color': [0.86, 0.90, 1.00]}},
            'material': {'preset': 'marble', 'base_color': [0.86, 0.90, 1.00],
                         'roughness': 0.5, 'metallic': 0.0,
                         'emissive': [round(rng.uniform(0.30, 0.85), 2),
                                      round(rng.uniform(0.32, 0.88), 2),
                                      round(rng.uniform(0.38, 1.00), 2)]},
        })
    # 三根体积光柱（专用节点）：从核心外围往下打，给"空"一点方向感
    # 宽度 ×5：本幕相机从 760m 外推进，20m 宽的光柱在远处只有几个像素
    for i, (sx, sz, w, it) in enumerate(((36.0, 18.0, 120.0, 0.55),
                                         (-44.0, -26.0, 150.0, 0.42),
                                         (10.0, -52.0, 100.0, 0.34))):
        kids.append({
            'name': f'shaft{i}',
            'render': 'volumetric',
            'translation': [sx, 34.0, sz],
            'params': {'x': sx, 'y': 34.0, 'z': sz, 'height': 160.0, 'width': w,
                       'intensity': it, 'color': [1.0, 0.90, 0.72]},
        })
    return {
        'name': '10-void',
        'environment': {
            'sun_dir': [0.12, 0.30, 0.95],
            'sun_color': [0.60, 0.66, 0.85],
            'sun_intensity': 0.30,
            'sky_zenith': [0.006, 0.008, 0.016],
            'sky_horizon': [0.020, 0.024, 0.038],
            'sky_ground': [0.004, 0.005, 0.008],
            'ibl_intensity': 0.10,
            'sky_intensity': 0.06,
            'fog_density': 0.0016,
            'fog_falloff': 0.006,
            'fog_color': [0.03, 0.035, 0.055],
        },
        'root': {'name': 'root', 'children': kids},
    }


def build_shot():
    """相机从极远推进到近处，最后从核心侧旁掠过。"""
    n = 160
    times, pos, tgt = [], [], []
    for i in range(n):
        s = i / (n - 1)
        # 距离：760 → 42；用 s^1.8 让"靠近"集中在后半段（前段几乎是静止的远望）
        d = 760.0 - 718.0 * (s ** 1.80)
        ang = math.radians(-96.0 + 46.0 * s)
        y = 30.0 - 18.0 * (s ** 1.3) + 6.0 * math.sin(s * 2.2)
        pos.append([round(math.cos(ang) * d * 0.28, 3), round(max(y, 4.0), 3),
                    round(math.sin(ang) * d, 3)])
        tgt.append([0.0, 0.0, 0.0])
        times.append(round(s * DURATION, 3))
    return {
        'version': 1, 'name': '10_void2', 'duration': DURATION,
        'scene': 'scenes/10_void2.scene.json',
        'acts': [{'t': 0.0, 'label': '一点'}, {'t': 22.0, 'label': '靠近'},
                 {'t': 48.0, 'label': '显形'}, {'t': 66.0, 'label': '环'},
                 {'t': 80.0, 'label': '掠过'}],
        'notes': '相机距离 760→42（s^1.8：靠近集中在后半段）；x 只为轻微视差。',
        'channels': [
            {'node': '$camera', 'prop': 'position', 'interpolation': 'LINEAR',
             'times': times, 'values': pos},
            {'node': '$camera', 'prop': 'target', 'interpolation': 'LINEAR',
             'times': times, 'values': tgt},
            {'node': '$camera', 'prop': 'fov', 'interpolation': 'LINEAR',
             'times': [0.0, DURATION], 'values': [38.0, 64.0]},
            {'node': '$env', 'prop': 'fog_density', 'interpolation': 'LINEAR',
             'times': [0.0, DURATION], 'values': [0.0009, 0.0022]},
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    scene, shot = build_scene(), build_shot()
    print(f'[void2] OK: {len(scene["root"]["children"])} 节点 / '
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
        print(f'[void2] 写入 {path} ({os.path.getsize(path) / 1024:.1f} KB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
