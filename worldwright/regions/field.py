# -*- coding: utf-8 -*-
"""第 IX 幕「法则·场」场景生成器 —— 矢量场里的流光通道。

视觉母题：**不可见的力**。空气里本没有东西，但让 40 条流线显形，场就看得见了。
每条流线是沿 ``x = A·sin(k·z + φ)`` 摆动的细管，相位逐条错开，
相机贴着其中一条飞 —— 你会看到"自己正沿着一条力线前进"。

为什么不做真流场
--------------
真矢量场（Perlin 涡旋 + 粒子积分）要逐帧推进粒子，而本幕的母题是**场的形状**
而不是粒子的命运。静态流线已经能把场的"走向"讲清楚，且成片确定。
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILM_DIR = os.path.dirname(HERE)
ROOT = os.path.dirname(FILM_DIR)

DURATION = 54.0
LINES = 40
LINE_LEN = 220.0
LINE_SEGS = 40
AMP = 14.0
K = 0.045

SCENE_PATH = os.path.join(FILM_DIR, 'scenes', '09_field.scene.json')
SHOT_PATH = os.path.join(FILM_DIR, 'shots', '09_field.shot.json')


def _stream(i):
    """第 i 条流线的控制点：沿 z 摆动，横向按椭圆分布。"""
    phase = i * 2.399963                       # 黄金角相位，避免整齐排列
    band = (i % 7) - 3                          # 分层（-3..3）
    pts = []
    for k in range(LINE_SEGS):
        u = k / (LINE_SEGS - 1)
        z = LINE_LEN * 0.5 - u * LINE_LEN
        x = AMP * math.sin(z * K + phase) + band * 3.2
        y = 8.0 + 5.0 * math.sin(z * K * 1.7 + phase * 1.3) + band * 0.8
        pts.append([round(x, 2), round(y, 2), round(z, 2)])
    return pts


def build_scene():
    kids = []
    for i in range(LINES):
        hue = i / max(1, LINES - 1)
        # 冷→暖的渐变：青蓝到淡金
        r = 0.35 + 0.55 * hue
        g = 0.70 + 0.18 * hue
        b = 0.95 - 0.45 * hue
        kids.append({
            'name': f'stream{i}',
            'mesh': {'builder': 'tube',
                     'args': {'points': _stream(i), 'radius': 0.085,
                              'radial': 8, 'caps': False,
                              'color': [round(r, 3), round(g, 3), round(b, 3)]}},
            'material': {'preset': 'marble',
                         'base_color': [round(r, 3), round(g, 3), round(b, 3)],
                         'roughness': 0.30, 'metallic': 0.0,
                         'emissive': [round(r * 0.45, 3), round(g * 0.45, 3),
                                      round(b * 0.45, 3)]},
        })
    return {
        'name': '09-field',
        'environment': {
            'sun_dir': [0.25, 0.70, 0.55],
            'sun_color': [0.55, 0.70, 0.95],
            'sun_intensity': 0.55,
            'sky_zenith': [0.012, 0.018, 0.032],
            'sky_horizon': [0.045, 0.060, 0.090],
            'sky_ground': [0.008, 0.010, 0.014],
            'ibl_intensity': 0.25,
            'sky_intensity': 0.16,
            'fog_density': 0.0060,
            'fog_falloff': 0.014,
            'fog_color': [0.05, 0.07, 0.11],
        },
        'root': {'name': 'root', 'children': kids},
    }


def build_shot():
    """相机沿一条流线飞行：位置取该流线的采样点并略微抬高/偏移。"""
    n = 108                                  # 54s × 2
    path = _stream(12)                       # 贴第 12 条流线
    times, pos, tgt = [], [], []
    for i in range(n):
        s = i / (n - 1)
        # 从流线中段开始，飞到接近末端
        u = 0.08 + 0.80 * s
        k = u * (LINE_SEGS - 1)
        k0, k1 = int(k), min(LINE_SEGS - 1, int(k) + 1)
        f = k - k0
        p0, p1 = path[k0], path[k1]
        x = p0[0] + (p1[0] - p0[0]) * f
        y = p0[1] + (p1[1] - p0[1]) * f + 2.4
        z = p0[2] + (p1[2] - p0[2]) * f
        pos.append([round(x, 3), round(y, 3), round(z, 3)])
        # 注视点：前方 18m 的流线位置（略降，让流线从画面上方掠过）
        uk = min(1.0, u + 0.08) * (LINE_SEGS - 1)
        kk = min(LINE_SEGS - 1, int(uk))
        tgt.append([round(path[kk][0], 3), round(path[kk][1], 3),
                    round(path[kk][2] - 18.0, 3)])
        times.append(round(s * DURATION, 3))
    return {
        'version': 1, 'name': '09_field', 'duration': DURATION,
        'scene': 'scenes/09_field.scene.json',
        'acts': [{'t': 0.0, 'label': '场'}, {'t': 18.0, 'label': '入流'},
                 {'t': 36.0, 'label': '沿力线'}, {'t': 54.0, 'label': '汇流'}],
        'notes': '相机贴第 12 条流线飞行（位置取流线采样点 +2.4m 抬高）。',
        'channels': [
            {'node': '$camera', 'prop': 'position', 'interpolation': 'LINEAR',
             'times': times, 'values': pos},
            {'node': '$camera', 'prop': 'target', 'interpolation': 'LINEAR',
             'times': times, 'values': tgt},
            {'node': '$camera', 'prop': 'fov', 'interpolation': 'LINEAR',
             'times': [0.0, DURATION], 'values': [64.0, 58.0]},
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    scene, shot = build_scene(), build_shot()
    n = len(scene['root']['children'])
    print(f'[field] OK: {n} 条流线 × {LINE_SEGS} 点 / '
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
        print(f'[field] 写入 {path} ({os.path.getsize(path) / 1024:.1f} KB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
