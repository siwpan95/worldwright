"""r03 城邦 —— 消费 worldbuilder 的 Voronoi 城镇（W1 第三区）。

与旧版（`film/gen/city.py`）的区别
---------------------------------
| | 旧版 | 本版 |
|---|---|---|
| 街区 | 5×14 规则的网格 + 抖动 | `town.generate_town()` 的 **12 个 Voronoi ward**（不规则多边形） |
| 街道 | 一条 z 轴的 plane | `streets`（6 条折线，来自城镇模型） |
| 建筑 | 每格一栋，尺寸固定 | 每个 ward 内部网格切分，**中心必须落在多边形内**才建 |
| 相机 | 沿 z 轴直线 | **沿最长的一条 street** 飞 |

**"点在多边形内"** 是这一区的关键：ward 是不规则多边形，直接按包围盒撒建筑
会溢出到隔壁街区。所以每个候选位置都要做 ray-casting 判定。

`Polygon.contains` 不在 worldbuilder 的公开 API 里，这里自己实现（8 行）。

用法::

    python -m worldwright.regions.r03_city
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (r'D:\projects\repos\superengine', r'D:\projects\repos\worldbuilder',
           _ROOT):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

SEED = 7
N_WARDS = 12
SCALE_TO = 300
DURATION = 80.0
FPS = 30
CAM_Y = 12.0

SCENE_OUT = os.path.join(_ROOT, 'assets', 'r03_city.scene.json')
SHOT_OUT = os.path.join(_ROOT, 'assets', 'r03_city.shot.json')


def _pt_in_poly(x, z, verts):
    """射线法：点 (x,z) 是否在多边形内。verts 是 [(x,z), ...]。"""
    inside = False
    n = len(verts)
    j = n - 1
    for i in range(n):
        xi, zi = verts[i]
        xj, zj = verts[j]
        if ((zi > z) != (zj > z)) and (x < (xj - xi) * (z - zi) / (zj - zi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _dist_to_streets(x, z, streets):
    """点到所有街道折线的最短距离。建筑必须避让 —— 首版忘了做，
    建筑直接压在街上，相机一进去就贴墙（和 film/gen/city2.py 同一个坑）。"""
    import math
    best = 1e9
    for st in streets:
        pts = [(float(p.x), float(p.y)) for p in st]
        for i in range(len(pts) - 1):
            ax, az = pts[i]
            bx, bz = pts[i + 1]
            dx, dz = bx - ax, bz - az
            L2 = dx * dx + dz * dz
            t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0,
                ((x - ax) * dx + (z - az) * dz) / L2))
            best = min(best, math.hypot(x - (ax + t * dx), z - (az + t * dz)))
    return best


def _poly_verts(poly):
    return [(float(p.x), float(p.y)) for p in getattr(poly, 'verts', [])]


def build_town():
    from worldbuilder.town import generate_town
    return generate_town(seed=SEED, n_wards=N_WARDS, scale_to=SCALE_TO)


def build_scene(t):
    import random
    rng = random.Random(SEED)
    kids = []
    minx, miny, maxx, maxy = t['bounds']
    cx, cz = (minx + maxx) * 0.5, (miny + maxy) * 0.5

    # 地面（按 town bounds 铺）
    span = max(maxx - minx, maxy - miny) * 0.8
    kids.append({
        'name': 'ground',
        'mesh': {'builder': 'ground_grid',
                 'args': {'half': int(span), 'tile': 4.0,
                          'color_a': [0.17, 0.155, 0.14],
                          'color_b': [0.12, 0.11, 0.10]}},
        'material': {'preset': 'marble', 'base_color': [0.17, 0.155, 0.14],
                     'roughness': 0.88, 'metallic': 0.0},
    })

    # 街道：每条折线铺一条窄 plane（简化为逐段 box，避免旋转 plane）
    for si, st in enumerate(t['streets']):
        pts = [(float(p.x), float(p.y)) for p in st]
        for k in range(len(pts) - 1):
            ax, az = pts[k]
            bx, bz = pts[k + 1]
            dx, dz = bx - ax, bz - az
            L = (dx * dx + dz * dz) ** 0.5
            if L < 0.5:
                continue
            import math
            ang = math.atan2(dz, dx)
            kids.append({
                'name': f'street{si}_{k}',
                'translation': [round((ax + bx) * 0.5, 2), 0.02, round((az + bz) * 0.5, 2)],
                'rotation': [math.cos(ang * 0.5), 0.0, math.sin(ang * 0.5), 0.0],
                'mesh': {'builder': 'box',
                         'args': {'sx': round(L, 2), 'sy': 0.06, 'sz': 6.5,
                                  'color': [0.24, 0.225, 0.20]}},
                'material': {'preset': 'marble', 'base_color': [0.24, 0.225, 0.20],
                             'roughness': 0.80, 'metallic': 0.0},
            })

    # 建筑：每个 ward 内网格切分，中心必须落在多边形内
    n_bld = 0
    for wi, w in enumerate(t['wards']):
        verts = _poly_verts(w['polygon'])
        if len(verts) < 3:
            continue
        xs = [v[0] for v in verts]
        zs = [v[1] for v in verts]
        x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
        ww, dd = x1 - x0, z1 - z0
        if ww < 4 or dd < 4:
            continue
        # 网格密度按 ward 尺寸（格宽约 6~9m）
        nx = max(2, min(4, int(ww / 7)))
        nz = max(2, min(4, int(dd / 7)))
        for ix in range(nx):
            for iz in range(nz):
                cxw = x0 + (ix + 0.5) * ww / nx
                czw = z0 + (iz + 0.5) * dd / nz
                if not _pt_in_poly(cxw, czw, verts):
                    continue
                # 避让街道：中心到任一街 < 5.5m 就不建（街宽 6.5 的一半 + 余量）
                if _dist_to_streets(cxw, czw, t['streets']) < 5.5:
                    continue
                bw = ww / nx * rng.uniform(0.55, 0.78)
                bd = dd / nz * rng.uniform(0.55, 0.78)
                bh = rng.uniform(6.0, 22.0)
                shade = rng.uniform(0.14, 0.25)
                kids.append({
                    'name': f'bld_{wi}_{ix}_{iz}',
                    'translation': [round(cxw, 2), round(bh * 0.5 + 0.1, 2), round(czw, 2)],
                    'mesh': {'builder': 'box',
                             'args': {'sx': round(bw, 2), 'sy': round(bh, 2),
                                      'sz': round(bd, 2),
                                      'color': [round(shade, 3),
                                                round(shade * 0.94, 3),
                                                round(shade * 0.83, 3)]}},
                    'material': {'preset': 'marble', 'base_color': [shade, shade * 0.94, shade * 0.83],
                                 'roughness': 0.80, 'metallic': 0.0},
                })
                n_bld += 1
    print(f'[r03] {len(t["wards"])} ward / {len(t["streets"])} 街 / {n_bld} 栋建筑')
    return {
        'name': 'r03-city',
        'environment': {
            'sun_dir': [-0.62, 0.34, 0.71],
            'sun_color': [1.00, 0.70, 0.44],
            'sun_intensity': 1.55,
            'sky_zenith': [0.09, 0.12, 0.21],
            'sky_horizon': [0.46, 0.34, 0.28],
            'sky_ground': [0.08, 0.07, 0.06],
            'ibl_intensity': 0.55,
            'sky_intensity': 0.48,
            'fog_density': 0.0028,
            'fog_falloff': 0.026,
            'fog_color': [0.42, 0.35, 0.30],
        },
        'root': {'name': 'root', 'children': kids},
    }, (cx, cz, span)


def build_shot(t, center):
    """相机沿最长的一条 street 飞（真折线）。"""
    import math
    cx, cz, span = center
    best, best_len = None, -1.0
    for st in t['streets']:
        if len(st) < 2:
            continue
        pts = [(float(p.x), float(p.y)) for p in st]
        L = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
                for i in range(len(pts) - 1))
        if L > best_len:
            best, best_len = pts, L
    if not best:
        raise RuntimeError('没有可用的 street 折线')

    pts = best
    segs = [math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
            for i in range(len(pts) - 1)]
    total = sum(segs) or 1.0

    def at(u):
        d = max(0.0, min(1.0, u)) * total
        for i, L in enumerate(segs):
            if d <= L or i == len(segs) - 1:
                f = d / L if L > 1e-9 else 0.0
                return (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f,
                        pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f)
            d -= L
        return pts[-1]

    n = 170
    times, pos, tgt = [], [], []
    for i in range(n):
        s = i / (n - 1)
        u = -0.04 + 1.08 * s
        x, z = at(u)
        # 起手略高看天际线，中段降到街面
        y = 26.0 - 7.0 * math.sin(min(1.0, s * 2.2) * math.pi * 0.5)
        pos.append([round(x, 2), round(y, 2), round(z, 2)])
        nx, nz = at(min(1.0, u + 0.10))
        tgt.append([round(nx, 2), round(y - 4.0, 2), round(nz, 2)])
        times.append(round(s * DURATION, 3))
    return {
        'version': 1, 'name': 'r03_city', 'duration': DURATION,
        'scene': 'assets/r03_city.scene.json',
        'acts': [{'t': 0.0, 'label': '入城'}, {'t': DURATION, 'label': '出城'}],
        'notes': f'相机沿最长街（{best_len:.1f}m / {len(pts)} 点）飞；y 20→13。',
        'channels': [
            {'node': '$camera', 'prop': 'position', 'interpolation': 'LINEAR',
             'times': times, 'values': pos},
            {'node': '$camera', 'prop': 'target', 'interpolation': 'LINEAR',
             'times': times, 'values': tgt},
            {'node': '$camera', 'prop': 'fov', 'interpolation': 'LINEAR',
             'times': [0.0, DURATION], 'values': [56.0, 48.0]},
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--seed', type=int, default=None,
                    help='覆盖模块里的默认种子（热调用的入口）')
    args = ap.parse_args(argv)
    global SEED
    if args.seed is not None:
        SEED = int(args.seed)
    t = build_town()
    scene, center = build_scene(t)
    shot = build_shot(t, center)
    n = len(scene['root']['children'])
    print(f'[r03] {n} 节点 / {len(shot["channels"][0]["times"])} 关键帧')
    if args.check:
        print('R03_CHECK_OK')
        return 0
    os.makedirs(os.path.dirname(SCENE_OUT), exist_ok=True)
    for path, data in ((SCENE_OUT, scene), (SHOT_OUT, shot)):
        with open(path, 'w', encoding='utf-8', newline='') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write(chr(10))
        with open(path, encoding='utf-8') as f:
            json.load(f)
        print(f'[r03] 写入 {path} ({os.path.getsize(path) / 1024:.1f} KB)')
    print('R03_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
