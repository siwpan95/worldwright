# -*- coding: utf-8 -*-
"""第 XI 幕「回环」场景生成器 —— 首尾呼应的闭环。

叙事位置：这一幕接在「虚空」（第 X 幕）之后、终章之前，是全片的**转折**——
前面的一切（地、城、机、群）都散掉了，只剩一个环在转，暗示"还会再来一次"。

视觉：竖直的大环（torus）+ 环内三圈小环（套环，像陀螺仪）+ 沿环绕行的粒子带。
相机从环外侧绕进去、穿过环心、再出来 —— **穿过**这个动作就是"回环"的字面表达。
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILM_DIR = os.path.dirname(HERE)
ROOT = os.path.dirname(FILM_DIR)

DURATION = 64.0
RING_MAJOR = 26.0
RING_MINOR = 0.9

SCENE_PATH = os.path.join(FILM_DIR, 'scenes', '11_loop.scene.json')
SHOT_PATH = os.path.join(FILM_DIR, 'shots', '11_loop.shot.json')


def _quat_x(deg):
    h = math.radians(deg) * 0.5
    return [math.sin(h), 0.0, 0.0, math.cos(h)]


def _quat_y(deg):
    h = math.radians(deg) * 0.5
    return [0.0, math.sin(h), 0.0, math.cos(h)]


def build_scene():
    kids = []
    # 主环：竖直（绕 X 转 90°），暖金
    kids.append({
        'name': 'ring_main',
        'translation': [0.0, 0.0, 0.0],
        'rotation': _quat_x(90.0),
        'mesh': {'builder': 'torus',
                 'args': {'major': RING_MAJOR, 'minor': RING_MINOR,
                          'major_segs': 180, 'minor_segs': 14,
                          'color': [0.92, 0.70, 0.30]}},
        'material': {'preset': 'gold', 'base_color': [0.92, 0.70, 0.30],
                     'roughness': 0.24, 'metallic': 0.85,
                     'emissive': [0.30, 0.16, 0.04]},
    })
    # 套环：三圈不同朝向的小环（陀螺仪感）
    for i, (rot, major) in enumerate(((30.0, 18.0), (60.0, 13.5), (115.0, 9.5))):
        kids.append({
            'name': f'ring_inner{i}',
            'rotation': _quat_y(rot),
            'mesh': {'builder': 'torus',
                     'args': {'major': major, 'minor': 0.45,
                              'major_segs': 128, 'minor_segs': 10,
                              'color': [0.55, 0.78, 1.00]}},
            'material': {'preset': 'marble', 'base_color': [0.55, 0.78, 1.00],
                         'roughness': 0.22, 'metallic': 0.0,
                         'emissive': [0.20, 0.34, 0.52]},
        })
    # 环上的"刻度"：24 个小方块沿主环均布（读得出旋转）
    for i in range(24):
        a = 2.0 * math.pi * i / 24.0
        kids.append({
            'name': f'tick{i}',
            'translation': [round(math.cos(a) * RING_MAJOR, 3), 0.0,
                            round(math.sin(a) * RING_MAJOR, 3)],
            'rotation': _quat_x(90.0),
            'mesh': {'builder': 'box',
                     'args': {'sx': 0.7, 'sy': 2.2, 'sz': 0.7,
                              'color': [0.95, 0.78, 0.40]}},
            'material': {'preset': 'gold', 'base_color': [0.95, 0.78, 0.40],
                         'roughness': 0.3, 'metallic': 0.7,
                         'emissive': [0.35, 0.20, 0.05]},
        })
    return {
        'name': '11-loop',
        'environment': {
            'sun_dir': [0.20, 0.55, 0.80],
            'sun_color': [0.85, 0.88, 1.00],
            'sun_intensity': 0.95,
            'sky_zenith': [0.014, 0.020, 0.038],
            'sky_horizon': [0.070, 0.070, 0.110],
            'sky_ground': [0.010, 0.012, 0.018],
            'ibl_intensity': 0.38,
            'sky_intensity': 0.24,
            'fog_density': 0.0050,
            'fog_falloff': 0.018,
            'fog_color': [0.08, 0.09, 0.14],
        },
        'root': {'name': 'root', 'children': kids},
    }


def build_shot():
    """相机从环外绕到环心、再穿出去 —— "穿过"即回环的字面动作。"""
    n = 128                                  # 64s × 2
    times, pos, tgt = [], [], []
    for i in range(n):
        s = i / (n - 1)
        t = s * DURATION
        ang = math.radians(-160.0 + 220.0 * s)
        # 半径：58 → 6 → 22（先逼近环心，再穿出到另一侧）
        # 首版 0.55 处才到环心，之后只退到 22 —— t=35 帧里只剩一段弧，
        # 认不出"这是个环"。改成 0.45 穿心、之后快速退到 46。
        if s < 0.45:
            rad = 58.0 - 52.0 * (s / 0.45) ** 1.3
        else:
            rad = 6.0 + 74.0 * ((s - 0.45) / 0.55) ** 0.75   # 末尾退到 80：给"远看全环"的收尾
        y = 9.0 - 4.0 * math.sin(s * 3.0)
        pos.append([round(math.cos(ang) * rad, 3), round(y, 3),
                    round(math.sin(ang) * rad, 3)])
        tgt.append([0.0, round(1.5 * math.sin(s * 2.0), 3), 0.0])
        times.append(round(t, 3))
    return {
        'version': 1, 'name': '11_loop', 'duration': DURATION,
        'scene': 'scenes/11_loop.scene.json',
        'acts': [{'t': 0.0, 'label': '远环'}, {'t': 20.0, 'label': '绕行'},
                 {'t': 36.0, 'label': '入心'}, {'t': 50.0, 'label': '穿过'},
                 {'t': 64.0, 'label': '另一侧'}],
        'notes': '相机绕 220°、半径 58→6→22：先逼近环心再穿出。',
        'channels': [
            {'node': '$camera', 'prop': 'position', 'interpolation': 'LINEAR',
             'times': times, 'values': pos},
            {'node': '$camera', 'prop': 'target', 'interpolation': 'LINEAR',
             'times': times, 'values': tgt},
            {'node': '$camera', 'prop': 'fov', 'interpolation': 'LINEAR',
             'times': [0.0, DURATION], 'values': [56.0, 66.0]},
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    scene, shot = build_scene(), build_shot()
    n = len(scene['root']['children'])
    print(f'[loop] OK: {n} 节点（主环 + 3 套环 + 24 刻度）/ '
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
        print(f'[loop] 写入 {path} ({os.path.getsize(path) / 1024:.1f} KB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
