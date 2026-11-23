# -*- coding: utf-8 -*-
"""第 VIII 幕「法则·体」场景生成器 —— 刚体堆叠与散落碎块。

视觉母题：**重力**。一座逐层收分的塔（每层旋转一点，像被拧过的积木），
四周散落着塌下来的碎块 —— 暗示"这里曾经塌过一次"。
相机绕塔半圈并缓缓下降，最后贴地穿过碎块区。

为什么不做真物理
--------------
真刚体要跑 `logic/` 的碰撞求解 + 每帧积分，本幕没有"动作戏"，静态堆叠已经
能表达"体"的母题（重量、支撑、秩序与崩塌）。真物理留给后续精修。
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

DURATION = 58.0
SEED = 20261124
LAYERS = 9
DEBRIS = 70

SCENE_PATH = os.path.join(FILM_DIR, 'scenes', '08_body.scene.json')
SHOT_PATH = os.path.join(FILM_DIR, 'shots', '08_body.shot.json')


def _stone(b=0.30, rough=0.86):
    return {'preset': 'marble', 'base_color': [b, b * 0.95, b * 0.88],
            'roughness': rough, 'metallic': 0.0}


def _quat_y(deg):
    h = math.radians(deg) * 0.5
    return [0.0, math.sin(h), 0.0, math.cos(h)]


def build_scene():
    rng = random.Random(SEED)
    kids = []
    # 地基
    kids.append({
        'name': 'podium',
        'mesh': {'builder': 'cylinder',
                 'args': {'radius': 16.0, 'height': 1.6, 'segments': 40,
                          'color': [0.24, 0.23, 0.21]}},
        'material': _stone(0.26, 0.90),
    })
    # 塔：逐层收分 + 旋转
    y = 1.6
    for i in range(LAYERS):
        w = 9.0 * (1.0 - i / (LAYERS + 1.6)) + 1.2
        h = 1.55
        kids.append({
            'name': f'layer{i}',
            'translation': [0.0, round(y + h * 0.5, 3), 0.0],
            'rotation': _quat_y(11.0 * i),
            'mesh': {'builder': 'box',
                     'args': {'sx': round(w, 3), 'sy': h, 'sz': round(w, 3),
                              'color': [0.34 - i * 0.012, 0.32 - i * 0.012,
                                        0.29 - i * 0.010]}},
            'material': _stone(0.40 - i * 0.012, 0.78),
        })
        y += h
    # 散落碎块
    for i in range(DEBRIS):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(9.0, 30.0)
        w = rng.uniform(0.6, 2.6)
        h = rng.uniform(0.4, 1.5)
        d = rng.uniform(0.6, 2.4)
        kids.append({
            'name': f'debris{i}',
            'translation': [round(math.cos(a) * r, 2),
                            round(h * 0.5 + rng.uniform(-0.1, 0.25), 2),
                            round(math.sin(a) * r, 2)],
            'rotation': _quat_y(rng.uniform(0, 360)),
            'mesh': {'builder': 'box',
                     'args': {'sx': round(w, 3), 'sy': round(h, 3),
                              'sz': round(d, 3),
                              'color': [0.30, 0.28, 0.25]}},
            'material': _stone(0.30, 0.88),
        })
    return {
        'name': '08-body',
        'environment': {
            'sun_dir': [0.58, 0.46, 0.67],
            'sun_color': [0.96, 0.90, 0.80],
            'sun_intensity': 1.85,
            'sky_zenith': [0.10, 0.12, 0.16],
            'sky_horizon': [0.30, 0.28, 0.26],
            'sky_ground': [0.07, 0.07, 0.065],
            'ibl_intensity': 0.50,
            'sky_intensity': 0.40,
            'fog_density': 0.0045,
            'fog_falloff': 0.035,
            'fog_color': [0.28, 0.26, 0.24],
        },
        'root': {'name': 'root', 'children': kids},
    }


def build_shot():
    n = 116                                  # 58s × 2
    times, pos, tgt = [], [], []
    for i in range(n):
        s = i / (n - 1)
        ang = math.radians(-120.0 + 210.0 * s)
        rad = 40.0 - 18.0 * (s ** 1.25)
        y = 22.0 - 15.0 * (s ** 1.15)
        pos.append([round(math.cos(ang) * rad, 3), round(max(y, 4.2), 3),
                    round(math.sin(ang) * rad, 3)])
        tgt.append([0.0, round(2.0 + 9.0 * (1.0 - s) ** 1.3, 3), 0.0])
        times.append(round(s * DURATION, 3))
    return {
        'version': 1, 'name': '08_body', 'duration': DURATION,
        'scene': 'scenes/08_body.scene.json',
        'acts': [{'t': 0.0, 'label': '残塔'}, {'t': 20.0, 'label': '绕行'},
                 {'t': 38.0, 'label': '下降'}, {'t': 58.0, 'label': '碎块'}],
        'notes': '相机 116 关键帧：绕塔 210°、半径 40→22、高度 22→7。',
        'channels': [
            {'node': '$camera', 'prop': 'position', 'interpolation': 'LINEAR',
             'times': times, 'values': pos},
            {'node': '$camera', 'prop': 'target', 'interpolation': 'LINEAR',
             'times': times, 'values': tgt},
            {'node': '$camera', 'prop': 'fov', 'interpolation': 'LINEAR',
             'times': [0.0, DURATION], 'values': [52.0, 58.0]},
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    scene, shot = build_scene(), build_shot()
    n = len(scene['root']['children'])
    print(f'[body] OK: {n} 节点（塔 {LAYERS} 层 + 碎块 {DEBRIS}）/ '
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
        print(f'[body] 写入 {path} ({os.path.getsize(path) / 1024:.1f} KB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
