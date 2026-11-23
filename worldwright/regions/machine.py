# -*- coding: utf-8 -*-
"""第 III 幕「机械」场景生成器 —— 结形反应堆 + 导管阵列 + 环形平台。

设计意图
--------
前两幕是"空无"与"地脉"（自然、空旷）。这一幕要第一次出现**人造结构**：
一座悬在虚空里的机械神殿，中央一个 torus_knot 反应堆在发光，八根导管从
它身上引向环形平台。构图靠"对称 + 中心亮点"，让第 II 幕的开阔反衬这一幕的压抑。

本文件只生成**静态骨架**；骨骼/IK/蒙皮那部分（机械臂）不走 scene JSON ——
它们要逐帧求值，属于 `render/passes.py` 的活。
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILM_DIR = os.path.dirname(HERE)
ROOT = os.path.dirname(FILM_DIR)

DURATION = 74.0
KNOT_MAJOR = 6.4
KNOT_TUBE = 1.15
PLATFORM_HALF = 44.0
PILLAR_COUNT = 8
PILLAR_R = 33.0
DUCT_R = 27.0
ARM_COUNT = 4
ARM_BASE_R = 19.0          # 臂底座所在半径（在柱环 33 内侧）
L1, L2 = 2.4, 1.8          # 与 logic/choreography 的机械臂几何一致

SCENE_PATH = os.path.join(FILM_DIR, 'scenes', '04_machine.scene.json')
SHOT_PATH = os.path.join(FILM_DIR, 'shots', '04_machine.shot.json')


def _node(name, mesh, material, translation=(0.0, 0.0, 0.0), rotation=None):
    n = {'name': name, 'translation': list(translation),
         'mesh': mesh, 'material': material}
    if rotation is not None:
        n['rotation'] = list(rotation)
    return n


def _metal(bright=0.30, rough=0.42):
    """金属材质。``bright`` 是"想要的目标灰阶"，内部乘 1.55 —— 冷调环境 + 高
    metallic 会把 base_color 压得很暗，首版 0.34 的臂在画面里几乎是黑的。"""
    b = min(0.88, bright * 1.55)
    return {'preset': 'steel', 'base_color': [b, b * 0.94, b * 0.86],
            'roughness': rough, 'metallic': 0.9}


def _arm_tree(i):
    """第 i 条机械臂的节点树：turret → seg1 → seg2 → grip。

    约定与 ``logic/choreography.build_arm`` 一致（关节平移 = 前一段末端），
    所以可以把节点树直接当骨骼用：**Node 自带层级 world_matrix**，不必再引
    ``logic/skeleton``。mesh 用 ``offset`` 从关节向上延伸，贴合几何。
    """
    a = math.radians(45.0 + 90.0 * i)          # 45/135/225/315，避开 22.5° 的立柱
    bx, bz = math.cos(a) * ARM_BASE_R, math.sin(a) * ARM_BASE_R
    return {
        'name': f'arm{i}_turret',
        'translation': [round(bx, 3), 0.0, round(bz, 3)],
        'mesh': {'builder': 'cylinder',
                 'args': {'radius': 0.78, 'height': 0.6, 'segments': 14,
                          'color': [0.42, 0.40, 0.36]}},
        'material': _metal(0.34, 0.40),
        'children': [{
            'name': f'arm{i}_seg1',
            'translation': [0.0, 0.6, 0.0],
            'mesh': {'builder': 'box',
                     'args': {'sx': 0.55, 'sy': L1, 'sz': 0.55,
                              'offset': [0.0, L1 / 2.0, 0.0],
                              'color': [0.48, 0.46, 0.42]}},
            'material': _metal(0.38, 0.36),
            'children': [{
                'name': f'arm{i}_seg2',
                'translation': [0.0, L1, 0.0],
                'mesh': {'builder': 'box',
                         'args': {'sx': 0.42, 'sy': L2, 'sz': 0.42,
                                  'offset': [0.0, L2 / 2.0, 0.0],
                                  'color': [0.52, 0.50, 0.45]}},
                'material': _metal(0.40, 0.34),
                'children': [{
                    'name': f'arm{i}_grip',
                    'translation': [0.0, L2, 0.0],
                    'mesh': {'builder': 'box',
                             'args': {'sx': 0.78, 'sy': 0.42, 'sz': 0.78,
                                      'color': [0.92, 0.62, 0.22]}},
                    'material': {'preset': 'gold',
                                 'base_color': [0.92, 0.62, 0.22],
                                 'roughness': 0.30, 'metallic': 0.80,
                                 'emissive': [0.55, 0.26, 0.06]},
                }],
            }],
        }],
    }


def build_scene():
    kids = []

    # --- 环形平台：金属地面（一半在灯下、一半在暗处，靠 ibl 提亮）---
    kids.append(_node(
        'platform',
        {'builder': 'ground_grid',
         'args': {'half': int(PLATFORM_HALF), 'tile': 3.0,
                  'color_a': [0.16, 0.155, 0.15], 'color_b': [0.11, 0.105, 0.10]}},
        _metal(0.22, 0.55)))

    # --- 中央反应堆：torus_knot(2,3) 自发光，是全场唯一光源感 ---
    kids.append(_node(
        'reactor',
        {'builder': 'torus_knot',
         'args': {'p': 2, 'q': 3, 'major': KNOT_MAJOR, 'tube_r': KNOT_TUBE,
                  'tubular': 220, 'radial': 18,
                  'color': [0.95, 0.62, 0.22]}},
        {'preset': 'gold', 'base_color': [0.95, 0.62, 0.22],
         'roughness': 0.28, 'metallic': 0.85,
         'emissive': [0.95, 0.42, 0.10]},
        translation=(0.0, 7.2, 0.0)))

    # --- 八根导管：从反应堆外缘垂到平台，tube 走折线，带"工业弯折" ---
    for i in range(PILLAR_COUNT):
        a = 2.0 * math.pi * i / PILLAR_COUNT
        ca, sa = math.cos(a), math.sin(a)
        pts = [[ca * KNOT_MAJOR * 0.9, 7.0, sa * KNOT_MAJOR * 0.9],
               [ca * DUCT_R, 9.5, sa * DUCT_R],
               [ca * DUCT_R, 4.2, sa * DUCT_R],
               [ca * DUCT_R * 0.96, 0.6, sa * DUCT_R * 0.96]]
        kids.append(_node(
            f'duct_{i}',
            {'builder': 'tube',
             'args': {'points': pts, 'radius': 0.62, 'radial': 12,
                      'color': [0.42, 0.40, 0.36], 'caps': True}},
            _metal(0.34, 0.38)))

    # --- 外圈立柱：给画面一个"围合"，也让雾有东西可挂 ---
    for i in range(PILLAR_COUNT):
        a = 2.0 * math.pi * (i + 0.5) / PILLAR_COUNT
        ca, sa = math.cos(a), math.sin(a)
        kids.append(_node(
            f'pillar_{i}',
            {'builder': 'box',
             'args': {'sx': 3.2, 'sy': 18.0, 'sz': 3.2,
                      'color': [0.19, 0.185, 0.18]}},
            _metal(0.20, 0.62),
            translation=(ca * PILLAR_R, 9.0, sa * PILLAR_R)))

    # --- 四条机械臂：节点树当骨骼，逐帧由 render/rigs.py 用 IK 驱动 ---
    for i in range(ARM_COUNT):
        kids.append(_arm_tree(i))

    # --- 顶部环梁：把立柱串起来（torus 横放在高处）---
    kids.append(_node(
        'ring_beam',
        {'builder': 'torus',
         'args': {'major': PILLAR_R, 'minor': 0.85, 'major_segs': 96,
                  'minor_segs': 12, 'color': [0.26, 0.25, 0.24]}},
        _metal(0.30, 0.45),
        translation=(0.0, 18.0, 0.0)))

    return {
        'name': '04-machine',
        'environment': {
            # 冷调环境 + 一盏低角度冷光，与反应堆的暖金形成对比
            'sun_dir': [0.55, 0.42, -0.72],
            'sun_color': [0.52, 0.60, 0.82],
            'sun_intensity': 1.05,
            'sky_zenith': [0.020, 0.026, 0.042],
            'sky_horizon': [0.075, 0.085, 0.115],
            'sky_ground': [0.020, 0.020, 0.024],
            'ibl_intensity': 0.42,
            'sky_intensity': 0.30,
            'fog_density': 0.010,
            'fog_falloff': 0.022,
            'fog_color': [0.09, 0.10, 0.13],
        },
        'root': {'name': 'root', 'children': kids},
    }


def build_shot():
    """相机：由远及近的螺旋环绕，末尾掠过反应堆侧后方。

    沿用第 II 幕的教训：**程序化密集关键帧**（每秒 2 个），LINEAR 插值，
    不用 5 个关键帧插样条。
    """
    n = 148                                  # 74s × 2
    times, pos, tgt = [], [], []
    for i in range(n):
        s = i / (n - 1)
        t = s * DURATION
        # 环绕角：从 -140° 缓慢转到 +115°（约 255° 的弧），半径由 62 收到 26
        ang = math.radians(-118.0 + 250.0 * s)
        # 相机必须**在环梁（y=18）下方**：首版 y 从 26 起，全程在梁上看，
        # 画面被环梁切成上下两半（t=30 那一帧整个上半是空的）。
        # 退到**柱环外侧**（46→40）：臂底座在 19、柱环 33，相机若与臂同半径
        # （上一版 30→20）臂永远落在视线两侧、画面里只剩反应堆。
        # 柱子此时是"前景框架"而不是"挡死"——相机在外侧，柱子只切画面边缘。
        rad = 46.0 - 6.0 * (s ** 1.20)        # 46 → 40
        y = 16.0 - 4.0 * (s ** 1.10)          # 16 → 12，略低于环梁（18）
        pos.append([round(math.cos(ang) * rad, 3), round(y, 3),
                    round(math.sin(ang) * rad, 3)])
        # 注视点：反应堆中心，随 s 略微上抬（把顶部环梁也带进画面）
        tgt.append([0.0, round(7.2 + 2.4 * s, 3), 0.0])
        times.append(round(t, 3))
    return {
        'version': 1,
        'name': '04_machine',
        'duration': DURATION,
        'scene': 'scenes/04_machine.scene.json',
        'acts': [
            {'t': 0.0, 'label': '虚空中的结构'},
            {'t': 18.0, 'label': '靠近'},
            {'t': 40.0, 'label': '导管阵列'},
            {'t': 58.0, 'label': '反应堆'},
            {'t': 74.0, 'label': '侧后'},
        ],
        'notes': ('相机程序化生成：148 个等距关键帧（每秒 2 个）、LINEAR 插值，'
                  '环绕 255° 同时半径 62→26、高度 26→10。'),
        'channels': [
            {'node': '$camera', 'prop': 'position', 'interpolation': 'LINEAR',
             'times': times, 'values': pos},
            {'node': '$camera', 'prop': 'target', 'interpolation': 'LINEAR',
             'times': times, 'values': tgt},
            {'node': '$camera', 'prop': 'fov', 'interpolation': 'LINEAR',
             'times': [0.0, DURATION], 'values': [50.0, 44.0]},
            {'node': '$env', 'prop': 'sun_intensity', 'interpolation': 'LINEAR',
             'times': [0.0, DURATION], 'values': [0.55, 1.25]},
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)

    scene = build_scene()
    shot = build_shot()
    n_kids = len(scene['root']['children'])
    if n_kids < 3:
        print('[machine] FAIL: 子节点太少', n_kids)
        return 1
    print(f'[machine] OK: {n_kids} 个子节点 / {len(shot["channels"])} 条通道 / '
          f'{len(shot["channels"][0]["times"])} 关键帧')
    if args.check:
        return 0
    for path, data in ((SCENE_PATH, scene), (SHOT_PATH, shot)):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write(chr(10))
        with open(path, encoding='utf-8') as f:
            json.load(f)                       # 手写 JSON 必须当场 round-trip
        print(f'[machine] 写入 {path} ({os.path.getsize(path) / 1024:.1f} KB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
