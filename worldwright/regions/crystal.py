"""第 V 幕「晶体」场景生成器 —— 一簇生长的晶柱。

视觉母题：**秩序从内部长出来**。24 根六棱柱从暗色地面里长出来，倾斜角度与
高度各不相同，顶端是八面体尖（`sphere` 取 4 段经度 × 2 段纬度 = 八面体）。
三色分配（青 / 紫 / 琥珀），roughness 压到 0.12 让高光锐利，像真的晶体。

为什么不做 SDF raymarch
----------------------
能力矩阵里这一幕标的是"SDF 八晶习 + raymarch 门廊"，那是 `sdfward` 的整套
shader 管线（球追踪、解析法线、软阴影）。本轮用**凸多面体拼装**表达晶习：
视觉上够用、零 shader 改动、成片确定。真正的 raymarch 晶体记为精修项。
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

DURATION = 64.0
COUNT = 24
SEED = 20261126

PALETTE = (
    ((0.20, 0.78, 0.92), (0.04, 0.26, 0.36)),      # 青
    ((0.62, 0.34, 0.94), (0.18, 0.07, 0.32)),      # 紫
    ((0.96, 0.66, 0.22), (0.34, 0.18, 0.03)),      # 琥珀
)

SCENE_PATH = os.path.join(FILM_DIR, 'scenes', '05_crystal.scene.json')
SHOT_PATH = os.path.join(FILM_DIR, 'shots', '05_crystal.shot.json')


# 注：此处曾有一个手算"q_tilt * q_yaw"的四元数函数，乘法公式写错（z 分量算成
# -st*sy，正确应为 0），结果把六棱柱**转倒**了 —— 画面里只剩一堆躺着的六边形。
# 本幕不需要倾斜（晶体本来就竖直向上），函数已删除。要写四元数乘法请用
# `world3d.engine.scene` 里的现成工具，不要手推。


def _crystal(idx, rng):
    a = rng.uniform(0, 2 * math.pi)
    r = rng.uniform(2.5, 26.0)
    x, z = math.cos(a) * r, math.sin(a) * r
    h = rng.uniform(5.0, 15.0) * (1.35 - r / 40.0)     # 外圈矮、内圈高
    rad = rng.uniform(0.7, 1.9) * (1.2 - r / 60.0)
    rng.uniform(-13.0, 13.0)
    rng.uniform(0, 360.0)
    base, emis = PALETTE[idx % len(PALETTE)]
    # 提亮 1.45 倍：深色 + 暗环境时柱体全黑、只剩顶端高光（首版就是这个问题）
    base = tuple(min(1.0, c * 1.45) for c in base)
    # roughness 0.12 等于全镜面：环境极暗时柱体全黑、只剩顶端高光（踩过）。
    # 提到 0.42 才有漫反射；emissive ×2.6 做"内部光"。
    mat = {'preset': 'marble', 'base_color': list(base),
           'roughness': 0.42, 'metallic': 0.10,
           'emissive': [round(min(1.0, c * 1.05), 3) for c in emis]}
    return {
        'name': f'cry{idx}',
        'translation': [round(x, 3), 0.0, round(z, 3)],
        # 六棱**双锥**（lathe 画菱形轮廓绕 Y 旋一圈）：两端收尖才是水晶，
        # 圆柱看起来像"彩色柱子"。端点半径取 0.02 而非 0，避免退化三角形。
        'mesh': {'builder': 'lathe',
                 'args': {'profile': [[0.02, 0.0],
                                      [round(rad, 3), round(h * 0.28, 3)],
                                      [0.02, round(h, 3)]],
                          'segments': 6,
                          'closed_top': False, 'closed_bottom': False,
                          'color': list(base)}},
        'material': mat,
    }


def build_scene():
    rng = random.Random(SEED)
    kids = [
        {
            'name': 'bed',
            'mesh': {'builder': 'ground_grid',
                     'args': {'half': 46, 'tile': 4.0,
                              'color_a': [0.09, 0.10, 0.12],
                              'color_b': [0.06, 0.07, 0.085]}},
            'material': {'preset': 'marble', 'base_color': [0.11, 0.12, 0.14],
                         'roughness': 0.55, 'metallic': 0.25},
        },
    ]
    kids += [_crystal(i, rng) for i in range(COUNT)]
    return {
        'name': '05-crystal',
        'environment': {
            'sun_dir': [-0.35, 0.58, -0.72],
            'sun_color': [0.72, 0.86, 1.00],
            'sun_intensity': 0.90,
            'sky_zenith': [0.020, 0.028, 0.052],
            'sky_horizon': [0.065, 0.080, 0.115],
            'sky_ground': [0.012, 0.014, 0.020],
            'ibl_intensity': 0.35,
            'sky_intensity': 0.20,
            'fog_density': 0.0060,
            'fog_falloff': 0.020,
            'fog_color': [0.07, 0.085, 0.13],
        },
        'root': {'name': 'root', 'children': kids},
    }


def build_shot():
    n = 128
    times, pos, tgt = [], [], []
    for i in range(n):
        s = i / (n - 1)
        ang = math.radians(-135.0 + 245.0 * s)
        rad = 76.0 - 34.0 * (s ** 1.25)
        y = 20.0 - 10.0 * (s ** 1.1) + 2.5 * math.sin(s * 3.4)
        pos.append([round(math.cos(ang) * rad, 3), round(max(y, 4.0), 3),
                    round(math.sin(ang) * rad, 3)])
        tgt.append([0.0, round(6.0 + 4.0 * (1.0 - s), 3), 0.0])
        times.append(round(s * DURATION, 3))
    return {
        'version': 1, 'name': '05_crystal', 'duration': DURATION,
        'scene': 'scenes/05_crystal.scene.json',
        'acts': [{'t': 0.0, 'label': '晶簇'}, {'t': 18.0, 'label': '环绕'},
                 {'t': 36.0, 'label': '近观'}, {'t': 52.0, 'label': '穿行'},
                 {'t': 64.0, 'label': '出簇'}],
        'notes': '相机绕 245°、半径 58→20、高度 20→8。',
        'channels': [
            {'node': '$camera', 'prop': 'position', 'interpolation': 'LINEAR',
             'times': times, 'values': pos},
            {'node': '$camera', 'prop': 'target', 'interpolation': 'LINEAR',
             'times': times, 'values': tgt},
            {'node': '$camera', 'prop': 'fov', 'interpolation': 'LINEAR',
             'times': [0.0, DURATION], 'values': [54.0, 60.0]},
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    scene, shot = build_scene(), build_shot()
    print(f'[crystal] OK: {len(scene["root"]["children"])} 节点（{COUNT} 晶柱 + 地面）/ '
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
        print(f'[crystal] 写入 {path} ({os.path.getsize(path) / 1024:.1f} KB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
