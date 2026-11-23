"""第 VII 幕「群」场景生成器 —— 80 只 boid 的静态挂点 + 环境。

本文件只生成**节点与材质**；真正的运动在 `film/render/rigs.py` 的 `SwarmRig`
里逐帧推进（`logic/boids.Flock` 是纯 CPU 模拟，确定性由 seed + 固定 dt 保证）。

为什么用 Node 树而不是实例化
--------------------------
引擎没有对外暴露"逐帧更新实例 buffer"的接口（`instanced_grid` 是静态排列）。
本幕 80 只、每只一个低模 sphere（8×6 段 ≈ 96 三角形），总量 7680 三角形，
Node 树完全扛得住；而且沿用了第 IV 幕 IK 那套"逐帧改写节点"的机制，
不必新造一层。
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILM_DIR = os.path.dirname(HERE)
ROOT = os.path.dirname(FILM_DIR)

DURATION = 58.0   # 与 project.json 的 07_swarm.duration 必须一致
BOID_COUNT = 80
BOUNDS = 26.0

SCENE_PATH = os.path.join(FILM_DIR, 'scenes', '07_swarm.scene.json')
SHOT_PATH = os.path.join(FILM_DIR, 'shots', '07_swarm.shot.json')


def build_scene():
    kids = []
    # 群：80 个低模发光球。初始位置环形撒开（rig 第一帧就会用 Flock 的位置覆盖）
    for i in range(BOID_COUNT):
        a = 2.0 * math.pi * i / BOID_COUNT
        r = 6.0 + 3.0 * math.sin(i * 1.3)
        kids.append({
            'name': f'boid{i}',
            'translation': [round(math.cos(a) * r, 2),
                            round(6.0 + 4.0 * math.sin(i * 0.7), 2),
                            round(math.sin(a) * r, 2)],
            'mesh': {'builder': 'sphere',
                     'args': {'radius': 0.17, 'segments': 8, 'rings': 6,
                              'color': [0.72, 0.90, 1.00]}},
            'material': {'preset': 'marble', 'base_color': [0.70, 0.88, 1.00],
                         'roughness': 0.35, 'metallic': 0.0,
                         'emissive': [0.42, 0.64, 0.90]},
        })
    # 远景点：几十颗暗星，给群一个参照系（否则纯黑背景读不出运动）
    for i in range(40):
        a = 2.399963 * i                     # 黄金角撒点，避免规律排列
        el = math.asin(((i * 37) % 61) / 61.0 * 2.0 - 1.0)
        r = 150.0
        kids.append({
            'name': f'star{i}',
            'translation': [round(math.cos(a) * math.cos(el) * r, 1),
                            round(math.sin(el) * r, 1),
                            round(math.sin(a) * math.cos(el) * r, 1)],
            'mesh': {'builder': 'sphere',
                     'args': {'radius': 0.55, 'segments': 6, 'rings': 4,
                              'color': [0.8, 0.85, 0.95]}},
            'material': {'preset': 'marble', 'base_color': [0.8, 0.85, 0.95],
                         'roughness': 0.6, 'metallic': 0.0,
                         'emissive': [0.35, 0.38, 0.45]},
        })
    return {
        'name': '07-swarm',
        'environment': {
            'sun_dir': [0.35, 0.62, -0.70],
            'sun_color': [0.70, 0.80, 1.00],
            'sun_intensity': 0.85,
            'sky_zenith': [0.018, 0.026, 0.048],
            'sky_horizon': [0.060, 0.075, 0.110],
            'sky_ground': [0.012, 0.014, 0.020],
            'ibl_intensity': 0.32,
            'sky_intensity': 0.22,
            'fog_density': 0.0075,
            'fog_falloff': 0.016,
            'fog_color': [0.07, 0.09, 0.14],
        },
        'root': {'name': 'root', 'children': kids},
    }


def build_shot():
    """相机绕群做慢速环绕 + 缓慢推进；群本身在动，相机不必太花。"""
    n = 124                                  # 62s × 2
    times, pos, tgt = [], [], []
    for i in range(n):
        s = i / (n - 1)
        t = s * DURATION
        ang = math.radians(-150.0 + 200.0 * s)
        rad = 30.0 - 8.0 * s
        y = 11.0 + 4.0 * math.sin(s * 3.1)
        pos.append([round(math.cos(ang) * rad, 3), round(y, 3),
                    round(math.sin(ang) * rad, 3)])
        tgt.append([0.0, round(6.0 + 2.0 * math.sin(s * 2.0), 3), 0.0])
        times.append(round(t, 3))
    return {
        'version': 1,
        'name': '07_swarm',
        'duration': DURATION,
        'scene': 'scenes/07_swarm.scene.json',
        'acts': [
            {'t': 0.0, 'label': '远处'},
            {'t': 16.0, 'label': '接近'},
            {'t': 34.0, 'label': '入群'},
            {'t': 50.0, 'label': '穿行'},
            {'t': 62.0, 'label': '远离'},
        ],
        'notes': '相机 124 关键帧绕群环绕；群的运动会由 SwarmRig 逐帧推进。',
        'channels': [
            {'node': '$camera', 'prop': 'position', 'interpolation': 'LINEAR',
             'times': times, 'values': pos},
            {'node': '$camera', 'prop': 'target', 'interpolation': 'LINEAR',
             'times': times, 'values': tgt},
            {'node': '$camera', 'prop': 'fov', 'interpolation': 'LINEAR',
             'times': [0.0, DURATION], 'values': [58.0, 62.0]},
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    scene = build_scene()
    shot = build_shot()
    n = len(scene['root']['children'])
    print(f'[swarm] OK: {n} 节点（{BOID_COUNT} boid + {n - BOID_COUNT} 星）/ '
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
        print(f'[swarm] 写入 {path} ({os.path.getsize(path) / 1024:.1f} KB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
