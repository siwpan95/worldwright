# -*- coding: utf-8 -*-
"""第 XII 幕「收束」场景生成器 —— 回到一粒光。

叙事：全片最后一幕。十幕造出来的东西全部退场，只剩开场那团星尘，然后连它也
缩成一个点。**相机在这幕是"往外退"的**（其余各幕都在往里进），
这个反方向就是"收束"。

实现极简：没有几何，只有 `project.json` 里的粒子（preset 0）与本文件的
一个小核心球。亮度靠 `sun_intensity` 通道一路降到 0 —— 画面自然渐黑，
不需要额外的 fade pass。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILM_DIR = os.path.dirname(HERE)

DURATION = 47.0

SCENE_PATH = os.path.join(FILM_DIR, 'scenes', '12_finale.scene.json')
SHOT_PATH = os.path.join(FILM_DIR, 'shots', '12_finale.shot.json')


def build_scene():
    return {
        'name': '12-finale',
        'environment': {
            'sun_dir': [0.2, 0.5, 0.84],
            'sun_color': [0.85, 0.88, 1.00],
            'sun_intensity': 0.55,
            'sky_zenith': [0.010, 0.012, 0.022],
            'sky_horizon': [0.030, 0.033, 0.048],
            'sky_ground': [0.006, 0.007, 0.010],
            'ibl_intensity': 0.18,
            'sky_intensity': 0.12,
            'fog_density': 0.0030,
            'fog_falloff': 0.012,
            'fog_color': [0.04, 0.045, 0.065],
        },
        'root': {
            'name': 'root',
            'children': [{
                # 全片最后一粒光：开场星盘的中心，也是收尾唯一留下的东西
                'name': 'seed',
                'mesh': {'builder': 'sphere',
                         'args': {'radius': 1.5, 'segments': 24, 'rings': 16,
                                  'color': [1.0, 0.97, 0.90]}},
                'material': {'preset': 'marble',
                             'base_color': [1.0, 0.97, 0.90],
                             'roughness': 0.4, 'metallic': 0.0,
                             'emissive': [2.2, 1.9, 1.5]},
            }],
        },
    }


def build_shot():
    n = 94                                   # 47s × 2
    times, pos, tgt = [], [], []
    for i in range(n):
        s = i / (n - 1)
        # 相机**一路后退**：18 → 380（与全片其他幕方向相反）
        d = 18.0 + 362.0 * (s ** 1.55)
        y = 4.0 + 26.0 * (s ** 1.2)
        pos.append([round(1.5 * s, 3), round(y, 3), round(d, 3)])
        tgt.append([0.0, 0.0, 0.0])
        times.append(round(s * DURATION, 3))
    return {
        'version': 1, 'name': '12_finale', 'duration': DURATION,
        'scene': 'scenes/12_finale.scene.json',
        'acts': [{'t': 0.0, 'label': '余烬'}, {'t': 14.0, 'label': '退'},
                 {'t': 30.0, 'label': '远'}, {'t': 47.0, 'label': '一点'}],
        'notes': '相机距离 18→380（全片唯一的反向运镜）；sun_intensity 一路降到 0.02。',
        'channels': [
            {'node': '$camera', 'prop': 'position', 'interpolation': 'LINEAR',
             'times': times, 'values': pos},
            {'node': '$camera', 'prop': 'target', 'interpolation': 'LINEAR',
             'times': times, 'values': tgt},
            {'node': '$camera', 'prop': 'fov', 'interpolation': 'LINEAR',
             'times': [0.0, DURATION], 'values': [56.0, 30.0]},
            # 亮度收束：不是靠 fade pass，而是把环境光与太阳一起压掉
            {'node': '$env', 'prop': 'sun_intensity', 'interpolation': 'LINEAR',
             'times': [0.0, 20.0, DURATION], 'values': [0.55, 0.30, 0.02]},
            {'node': '$env', 'prop': 'ibl_intensity', 'interpolation': 'LINEAR',
             'times': [0.0, DURATION], 'values': [0.18, 0.02]},
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    scene, shot = build_scene(), build_shot()
    print(f'[finale] OK: {len(scene["root"]["children"])} 节点 / '
          f'{len(shot["channels"][0]["times"])} 关键帧 / {len(shot["channels"])} 通道')
    if args.check:
        return 0
    for path, data in ((SCENE_PATH, scene), (SHOT_PATH, shot)):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write(chr(10))
        with open(path, encoding='utf-8') as f:
            json.load(f)
        print(f'[finale] 写入 {path} ({os.path.getsize(path) / 1024:.1f} KB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
