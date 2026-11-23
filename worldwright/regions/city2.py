"""第 III 幕「城邦」—— 真 Voronoi 布局版。

与旧版（网格街区）的区别
--------------------
旧版是"5×14 网格 + 抖动"，整齐但不像城市。这一版用 `logic/town.generate_town()`
的 **Voronoi 街区**（12 个 ward，每个是一个不规则多边形），再在 ward 内撒建筑。

**按新原则：先定相机，再定几何**
------------------------------
前两次失败（02 水俯视看不见、06 洞穴相机高过墙顶）都是"几何先造好、再找机位"。
这次反过来：
1. 先定相机的运动 —— 沿最长的一条 street（真折线）飞行，y=11；
2. 再定建筑高度 —— 上限 24m，保证 y=11 时两侧是"墙"而不是"矮房"；
3. 最后定街区尺度 —— 由 town 的 bounds 决定（约 98×90m）。

这样相机不会高过建筑、也不会埋进墙里。
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
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from world3d.logic.town import generate_town

DURATION = 80.0
SEED = 7
N_WARDS = 12
SCALE_TO = 200

# 相机参数（先定这些，再定几何 —— 见模块 docstring）
CAM_Y = 11.0
CAM_FOV = (54.0, 48.0)

SCENE_PATH = os.path.join(FILM_DIR, 'scenes', '03_city.scene.json')
SHOT_PATH = os.path.join(FILM_DIR, 'shots', '03_city.shot.json')


def _stone(b=0.22, rough=0.82):
    return {'preset': 'marble', 'base_color': [b, b * 0.95, b * 0.88],
            'roughness': rough, 'metallic': 0.0}


def _poly_bounds(poly):
    """取多边形包围盒 (minx, maxx, miny, maxy)，兼容 vertices 是点列表/属性。"""
    verts = getattr(poly, 'vertices', None) or list(poly)
    xs = [float(v.x) for v in verts]
    ys = [float(v.y) for v in verts]
    return min(xs), max(xs), min(ys), max(ys)


def _dist_to_streets(x, z, streets):
    """点到所有街道折线的最短距离（米）。用来给建筑留出路面 —— 首版没做这个，
    建筑直接撒满了街道，相机一进去就埋进墙里。"""
    best = 1e9
    for st in streets:
        for i in range(len(st) - 1):
            ax, az = float(st[i].x), float(st[i].y)
            bx, bz = float(st[i + 1].x), float(st[i + 1].y)
            dx, dz = bx - ax, bz - az
            L2 = dx * dx + dz * dz
            t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0,
                ((x - ax) * dx + (z - az) * dz) / L2))
            best = min(best, math.hypot(x - (ax + t * dx), z - (az + t * dz)))
    return best


def build_scene(town):
    rng = random.Random(SEED)
    kids = []
    # 地面（按 town bounds 铺满 + 余量）
    minx, maxx, miny, maxy = town['bounds']
    cx, cz = (minx + maxx) * 0.5, (miny + maxy) * 0.5
    span = max(maxx - minx, maxy - miny) * 0.75
    kids.append({
        'name': 'ground',
        'mesh': {'builder': 'ground_grid',
                 'args': {'half': int(span) + 8, 'tile': 4.0,
                          'color_a': [0.16, 0.145, 0.13],
                          'color_b': [0.11, 0.10, 0.09]}},
        'material': _stone(0.20, 0.88),
    })

    # 每个 ward 的包围盒内撒建筑；高度上限 24m（相机 y=11 时两侧成"墙"）
    n = 0
    for wi, ward in enumerate(town['wards']):
        poly = ward.get('polygon')
        if poly is None:
            continue
        x0, x1, y0, y1 = _poly_bounds(poly)
        w, d = x1 - x0, y1 - y0
        if w < 3 or d < 3:
            continue
        # 按 ward 面积决定建筑数（约每 90 平米一栋，最少 2 栋）
        count = max(1, min(4, int(w * d / 200)))
        for k in range(count):
            bw = rng.uniform(2.6, min(7.0, w * 0.42))
            bd = rng.uniform(2.6, min(7.0, d * 0.42))
            bx = bz = None
            for _try in range(12):          # 最多试 12 次找一个不压街道的位置
                cx_ = rng.uniform(x0 + bw * 0.5, x1 - bw * 0.5)
                cz_ = rng.uniform(y0 + bd * 0.5, y1 - bd * 0.5)
                if _dist_to_streets(cx_, cz_, town['streets']) > 11.0:
                    bx, bz = cx_, cz_
                    break
            if bx is None:
                continue                     # 这个 ward 挤不下，跳过
            bh = rng.uniform(6.0, 24.0)
            shade = rng.uniform(0.13, 0.24)
            kids.append({
                'name': f'bld_{wi}_{k}',
                'translation': [round(bx, 2), round(bh * 0.5, 2), round(bz, 2)],
                'mesh': {'builder': 'box',
                         'args': {'sx': round(bw, 2), 'sy': round(bh, 2),
                                  'sz': round(bd, 2),
                                  'color': [round(shade, 3),
                                            round(shade * 0.94, 3),
                                            round(shade * 0.84, 3)]}},
                'material': _stone(shade, 0.80),
            })
            n += 1
    print(f'[city2] {len(town["wards"])} 个 Voronoi ward → {n} 栋建筑')
    return {
        'name': '03-city',
        'environment': {
            'sun_dir': [-0.62, 0.34, 0.71],
            'sun_color': [1.00, 0.70, 0.44],
            'sun_intensity': 1.55,
            'sky_zenith': [0.09, 0.12, 0.21],
            'sky_horizon': [0.46, 0.34, 0.28],
            'sky_ground': [0.08, 0.07, 0.06],
            'ibl_intensity': 0.55,
            'sky_intensity': 0.48,
            'fog_density': 0.0070,
            'fog_falloff': 0.026,
            'fog_color': [0.42, 0.35, 0.30],
        },
        'root': {'name': 'root', 'children': kids},
    }, (cx, cz, span)


def build_shot(town, center_span):
    """沿最长的一条 street 飞（真折线路径）。"""
    cx, cz, span = center_span
    # 选最长街道
    best, best_len = None, -1.0
    for st in town['streets']:
        if len(st) < 2:
            continue
        L = sum(math.hypot(st[i + 1].x - st[i].x, st[i + 1].y - st[i].y)
                for i in range(len(st) - 1))
        if L > best_len:
            best, best_len = st, L
    if best is None:
        best = [type('P', (), {'x': cx, 'y': cz - span * 0.6})(),
                type('P', (), {'x': cx, 'y': cz + span * 0.6})()]

    # 把折线按弧长重采样成 N 个等距点
    pts = [(float(p.x), float(p.y)) for p in best]
    segs = [(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]))
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

    n = 160
    times, pos, tgt = [], [], []
    for i in range(n):
        s = i / (n - 1)
        # 从街道一端稍微外面进、到另一端出
        u = -0.05 + 1.10 * s
        x, z = at(u)
        # 高度：起手略高看天际线（16m），中段降到街面（11m），末尾再抬（14m）
        y = 22.0 - 7.0 * math.sin(min(1.0, s * 2.4) * math.pi * 0.5) + 3.0 * max(0.0, s - 0.8) / 0.2
        pos.append([round(x, 2), round(y, 2), round(z, 2)])
        # 注视点：前方一点（沿街方向）
        nx, nz = at(min(1.0, u + 0.10))
        tgt.append([round(nx, 2), round(y - 2.5, 2), round(nz, 2)])
        times.append(round(s * DURATION, 3))
    return {
        'version': 1, 'name': '03_city', 'duration': DURATION,
        'scene': 'scenes/03_city.scene.json',
        'acts': [{'t': 0.0, 'label': '入城'}, {'t': 20.0, 'label': '街'},
                 {'t': 44.0, 'label': '转'}, {'t': 64.0, 'label': '深街'},
                 {'t': 80.0, 'label': '出'}],
        'notes': f'相机沿最长街道（{best_len:.1f}m / {len(best)} 点折线）飞行，'
                 f'y 16→11→14；建筑高上限 24m（相机低于墙顶）。',
        'channels': [
            {'node': '$camera', 'prop': 'position', 'interpolation': 'LINEAR',
             'times': times, 'values': pos},
            {'node': '$camera', 'prop': 'target', 'interpolation': 'LINEAR',
             'times': times, 'values': tgt},
            {'node': '$camera', 'prop': 'fov', 'interpolation': 'LINEAR',
             'times': [0.0, DURATION], 'values': list(CAM_FOV)},
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    town = generate_town(seed=SEED, n_wards=N_WARDS, scale_to=SCALE_TO)
    scene, center_span = build_scene(town)
    shot = build_shot(town, center_span)
    n = len(scene['root']['children'])
    print(f'[city2] OK: {n} 节点 / {len(shot["channels"][0]["times"])} 关键帧')
    if args.check:
        return 0
    for path, data in ((SCENE_PATH, scene), (SHOT_PATH, shot)):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write(chr(10))
        with open(path, encoding='utf-8') as f:
            json.load(f)
        print(f'[city2] 写入 {path} ({os.path.getsize(path) / 1024:.1f} KB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
