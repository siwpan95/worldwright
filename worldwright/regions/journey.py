# -*- coding: utf-8 -*-
"""W4 世界编排 —— 三个区串成一条连续路径。

现实约束
-------
`worldbuilder` 只产出 terrain / town / dungeon 三类，12 幕里只有 r02/r03/r06
能对上号（见 README「W1 的 3/3 是什么范围」）。所以 W4 的"12 区"退化成
**三段真实可用的区**：

    河谷 (r02)  →  城邦 (r03)  →  洞窟 (r06)

做法
----
1. 三个 scene JSON 的 children 沿 +X 摆开（偏移 0 / 400 / 900 米），名字加前缀
   避免 `root`/`torch0` 这类重名；
2. 一条总镜头依次穿过三段，**边界处不做硬切**——靠 `fog_density` 拉高遮住衔接；
3. 环境用 `$env` 通道随镜头切换（`ShotPlayer._apply_env` 支持任意属性，
   只切 float 字段最稳：`sun_intensity` / `fog_density`）。

用法::

    python -m worldwright.regions.journey
    python -m worldwright.render.preview --scene assets/journey.scene.json \\
        --shot assets/journey.shot.json --t 40
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))

SCENE_OUT = os.path.join(_ROOT, 'assets', 'journey.scene.json')
SHOT_OUT = os.path.join(_ROOT, 'assets', 'journey.shot.json')

#: 三个区在 X 轴上的落点（米）与各自的镜头时长（秒）
SEGMENTS = [
    ('r02', 0.0, 30.0),
    ('r03', 400.0, 26.0),
    ('r06', 900.0, 28.0),
]
FPS = 30


def _load(region):
    with open(os.path.join(_ROOT, 'assets', f'{region}_*.scene.json'
                           .replace('*', {'r02': 'terrain', 'r03': 'city', 'r06': 'cave'}[region])),
              encoding='utf-8') as f:
        return json.load(f)


def _load_shot(region):
    name = {'r02': 'terrain', 'r03': 'city', 'r06': 'cave'}[region]
    with open(os.path.join(_ROOT, 'assets', f'{region}_{name}.shot.json'),
              encoding='utf-8') as f:
        return json.load(f)


def build_scene():
    """合并三段场景。环境取**第一段**的，靠 shot 的 $env 通道在途中改。"""
    merged = None
    total = 0
    for region, offset, _dur in SEGMENTS:
        d = _load(region)
        if merged is None:
            merged = {'name': 'journey', 'environment': d['environment'],
                      'root': {'name': 'root', 'children': []}}
        prefix = f'{region}_'
        for ch in d['root']['children']:
            c = copy.deepcopy(ch)
            c['name'] = prefix + c.get('name', 'node')
            t = list(c.get('translation', [0.0, 0.0, 0.0]))
            t[0] += offset
            c['translation'] = t
            merged['root']['children'].append(c)
            total += 1
    print(f'[journey] 合并 {total} 个节点 / {len(SEGMENTS)} 段')
    return merged


def build_shot():
    """把三段的镜头按 X 偏移拼起来，环境在段间切换。"""
    times, pos, tgt = [], [], []
    env_t, env_sun, env_fog = [], [], []
    clock = 0.0
    for region, offset, dur in SEGMENTS:
        sh = _load_shot(region)
        cpos = next(c for c in sh['channels'] if c['prop'] == 'position')
        ctgt = next(c for c in sh['channels'] if c['prop'] == 'target')
        src_dur = max(1e-6, float(cpos['times'][-1]))
        n = len(cpos['times'])
        for i in range(n):
            u = cpos['times'][i] / src_dur
            p = list(cpos['values'][i])
            p[0] += offset
            pos.append([round(v, 2) for v in p])
            tg = list(ctgt['values'][min(i, len(ctgt['values']) - 1)])
            tg[0] += offset
            tgt.append([round(v, 2) for v in tg])
            times.append(round(clock + u * dur, 3))
        # 每段开头切环境（洞窟要暗、河谷要亮）
        sun = {'r02': 1.30, 'r03': 0.75, 'r06': 0.35}[region]
        fog = {'r02': 0.0032, 'r03': 0.0060, 'r06': 0.0120}[region]
        env_t += [round(clock, 3), round(clock + 1.5, 3)]
        env_sun += [env_sun[-1] if env_sun else sun, sun]
        env_fog += [env_fog[-1] if env_fog else fog, fog]
        clock += dur
    total = clock
    print(f'[journey] 总时长 {total:.0f}s / {len(times)} 关键帧')
    return {
        'version': 1, 'name': 'journey', 'duration': round(total, 3),
        'scene': 'assets/journey.scene.json',
        'acts': [{'t': 0.0, 'label': '河谷'}, {'t': 30.0, 'label': '城邦'},
                 {'t': 56.0, 'label': '洞窟'}, {'t': round(total, 1), 'label': '收'}],
        'notes': '三段拼接：河谷→城邦→洞窟，沿 +X 各偏移 0/400/900m；环境在段间 1.5s 内切换。',
        'channels': [
            {'node': '$camera', 'prop': 'position', 'interpolation': 'LINEAR',
             'times': times, 'values': pos},
            {'node': '$camera', 'prop': 'target', 'interpolation': 'LINEAR',
             'times': times, 'values': tgt},
            {'node': '$env', 'prop': 'sun_intensity', 'interpolation': 'LINEAR',
             'times': env_t, 'values': env_sun},
            {'node': '$env', 'prop': 'fog_density', 'interpolation': 'LINEAR',
             'times': env_t, 'values': env_fog},
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    for region, _, _ in SEGMENTS:
        for suffix in ('scene', 'shot'):
            name = {'r02': 'terrain', 'r03': 'city', 'r06': 'cave'}[region]
            path = os.path.join(_ROOT, 'assets', f'{region}_{name}.{suffix}.json')
            if not os.path.exists(path):
                print(f'!! 缺 {path}，先跑 python -m worldwright.regions.{region}_{name}')
                return 1
    scene = build_scene()
    shot = build_shot()
    if args.check:
        print('JOURNEY_CHECK_OK')
        return 0
    for path, data in ((SCENE_OUT, scene), (SHOT_OUT, shot)):
        with open(path, 'w', encoding='utf-8', newline='') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write(chr(10))
        with open(path, encoding='utf-8') as f:
            json.load(f)
        print(f'[journey] 写入 {path} ({os.path.getsize(path) / 1024:.1f} KB)')
    print('JOURNEY_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
