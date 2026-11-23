# -*- coding: utf-8 -*-
"""第 II 幕「地脉」场景生成器 —— 程序化地形，JSON 只是产物。

为什么不手写 scene JSON
----------------------
``heightfield`` 要 ``hm`` 是行主序二维数组（80×80 = 6400 个数字）。手写既不可能，
也没法"改一版形状看看"——而地形是这部片子第一个有真实几何的东西，必然要迭代。

塑形逻辑（都在 ``build_heights`` 里，可调）
----------------------------------------
* **基底**：`logic.noise.heightmap` 的 fBm（引擎公共能力，不自己造噪声）；
* **边缘山脉**：按径向距离抬升，形成盆地感 —— 否则镜头一拉远就看见网格边界；
* **中央峡谷**：沿 z 轴的一条收窄凹槽，给相机一条"视线走廊"，
  也让第 II 幕末尾的运镜有明确去处（顺着峡谷飞出去接第 III 幕）。

用法::

    python film/gen/terrain.py            # 生成 scenes/02_terrain.scene.json + shots/
    python film/gen/terrain.py --check    # 只校验（高度值域 / 分辨率 / 文件存在）
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILM_DIR = os.path.dirname(HERE)
ROOT = os.path.dirname(FILM_DIR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from world3d.logic.noise import heightmap                      # noqa: E402

BASIN_V = 0.02        # 天池中心（归一化 v）：放在相机低飞段（t≈50）下方
BASIN_Z = BASIN_V * 80.0   # 换成世界 z（TERRAIN_SIZE/2 = 80）
BASIN_WATER_Y = -1.5  # 水面局部 y：坑底约 -3.1、谷底约 +2.0 ⇒ 真正积住
LAKE_Y = -1.2         # 湖面高度（谷底约 +1.4，湖在低洼处积住）
GRID = 80              # 高度图分辨率（heightfield 建议 64~128；80 是面数/细节的折中）
TERRAIN_SIZE = 160.0   # 世界尺寸（米）—— 配 60m 高才够陡（坡度 37%）
TERRAIN_HEIGHT = 60.0  # 高度幅度（米）—— 220m/20m 只有 9% 坡度，是缓丘不是峡谷
SEED = 20261122
DURATION = 66.0        # 与 project.json 的 02_terrain 一致

SCENE_PATH = os.path.join(FILM_DIR, 'scenes', '02_terrain.scene.json')
SHOT_PATH = os.path.join(FILM_DIR, 'shots', '02_terrain.shot.json')


def smoothstep(a, b, x):
    if b == a:
        return 0.0 if x < a else 1.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def build_heights():
    """返回 80×80 的 0..1 高度图（行主序，row 对应 -z 方向）。"""
    base = heightmap(GRID, GRID, scale=0.052, seed=SEED, octaves=5,
                     lacunarity=2.05, gain=0.52)
    rows = []
    for r in range(GRID):
        v = r / (GRID - 1) * 2.0 - 1.0              # -1..1，对应 z
        row = []
        for c in range(GRID):
            u = c / (GRID - 1) * 2.0 - 1.0          # -1..1，对应 x
            rad = math.hypot(u, v)

            # 边缘只护最外一圈（防止看见地形边界），权重压到很轻：
            # 2026-11-22 教训：原先把 rim 当"主山脊"（0.92 权重、rad 0.42 起），
            # 结果整个外圈被抬成高原（mean 到 42m），相机永远埋在山坡里。
            rim = smoothstep(0.80, 1.05, rad)

            # 中央峡谷：u 方向收窄、|v| 中段最深。
            # **两端封口**（2026-11-22）：heightfield 是单面网格、边缘没有裙边，
            # 相机正视 z=-80 的边界会看到地形切面（实测画面正中一条竖直亮边）。
            # 让 |v|>0.82 处谷体合拢成山，尽头就是山壁而不是网格边。
            gate = 1.0 - smoothstep(0.78, 0.94, abs(v))
            valley = (math.exp(-((u / 0.13) ** 2))
                      * smoothstep(0.04, 0.45, abs(v))
                      * gate)

            # 地形 = fBm 群山 × 峡谷压低 + 最外圈薄护边。
            # 关键是**让 base 当主角**：fBm 本身就是多峰，不需要再造一圈山；
            # 峡谷只在 |u|≈0 处压出一条走廊，两侧自然就是山。
            h = base[r][c] * (1.0 - 0.75 * valley) + rim * 0.28
            # 峡谷底再压平一点，让水体那一版有地方放
            h *= (1.0 - 0.25 * valley)
            row.append(round(max(0.0, min(1.0, h)), 4))
        rows.append(row)

    # 归一化到 0..1（2026-11-22 教训）：叠加 base/rim/wall 后整体高度会被抬高 ——
    # 实测未归一化时 mean=37.9m（height=60），相机 y=8 直接埋在山坡里。
    # 线性拉伸不改变形状，只保证「谷底 = y_base、山顶 = y_base + height」。
    flat = [v for r in rows for v in r]
    lo, hi = min(flat), max(flat)
    span = (hi - lo) or 1.0
    rows = [[(v - lo) / span for v in r] for r in rows]

    # 最后一道：**雕刻谷底**。归一化只保证全局落进 0..1，并不保证
    # "峡谷中心就是最低处" —— 实测中心行仍有 19.5m（fBm 在别处有更低的坑，
    # 归一化的 0 被那些坑占走了），相机 y=8 依然埋在山里。
    # 这里对 |u| < 0.10 直接设高度上限，让谷底明确低于相机、两侧保持山体。
    for r in range(GRID):
        for c in range(GRID):
            u = c / (GRID - 1) * 2.0 - 1.0
            v = r / (GRID - 1) * 2.0 - 1.0
            if abs(u) < 0.10 and abs(v) < 0.80:      # 封口段不雕（要留山壁）
                cap = 0.10 + (abs(u) / 0.10) ** 2 * 0.14
                rows[r][c] = min(rows[r][c], cap)
    return [[round(v, 4) for v in r] for r in rows]


def ground_at(hm, x, z):
    """世界坐标 (x, z) → 地形高度（米）。超出地形范围返回 y_base。"""
    half = TERRAIN_SIZE / 2.0
    if abs(x) > half or abs(z) > half:
        return -4.0
    c = int(round((x / half + 1.0) / 2.0 * (GRID - 1)))
    r = int(round((z / half + 1.0) / 2.0 * (GRID - 1)))
    c = max(0, min(GRID - 1, c))
    r = max(0, min(GRID - 1, r))
    return -4.0 + hm[r][c] * TERRAIN_HEIGHT


def build_scene(hm):
    """声明式场景：地形 + 环境（黄昏侧逆光，给第 II 幕一个"初开天"的调子）。"""
    return {
        'name': '02-terrain',
        'environment': {
            'sun_dir': [-0.42, 0.30, 0.86],          # 低角度侧逆光
            'sun_color': [1.00, 0.72, 0.46],         # 暖橙
            'sun_intensity': 2.10,
            'sky_zenith': [0.055, 0.075, 0.135],
            'sky_horizon': [0.42, 0.30, 0.26],
            'sky_ground': [0.075, 0.065, 0.058],
            'ibl_intensity': 0.55,
            'sky_intensity': 0.85,
            # 高度雾（引擎 0.7.9 起支持）：遮住地形边界 + 给山谷大气感。
            # 颜色贴近 sky_horizon，避免"灰白雾贴在暖天空上"的违和。
            'fog_density': 0.006,
            'fog_falloff': 0.030,
            'fog_color': [0.50, 0.46, 0.43],
        },
        'root': {
            'name': 'root',
            'children': [
                {
                    'name': 'terrain',
                    'translation': [0.0, -80.0, 0.0],   # 起始位置在地平线下（升起动画）
                    'mesh': {
                        'builder': 'heightfield',
                        'args': {
                            'hm': hm,
                            'width': TERRAIN_SIZE,
                            'depth': TERRAIN_SIZE,
                            'height': TERRAIN_HEIGHT,
                            'y_base': -4.0,
                            'color': [0.34, 0.30, 0.25],
                        },
                    },
                    'material': {
                        'preset': 'marble',
                        'base_color': [0.34, 0.30, 0.25],
                        'roughness': 0.94,
                        'metallic': 0.0,
                    },
                    # 水面**不加**（2026-11-23 第三次确认）：本幕运镜是低空穿谷、
                    # 相机始终俯视谷底，而平面水在俯视时的菲涅尔反射率只有 0.02，
                    # 只能看到一条白线（Gerstner 位移也救不了 —— 它改的是顶点，
                    # 改不了"从上往下看水是暗色/白色边"这件事）。
                    # 要真有水，得让相机贴水面平视，或给水做真折射 —— 都不在本幕。
                },
            ],
        },
    }


def build_camera_path(hm, duration=DURATION, count=130, clearance=3.5):
    """程序化相机路径：沿峡谷等距采样 + 逐点离地间隙 + **相邻段穿地检查**。

    为什么不用"5 个关键帧 + 三次样条"（2026-11-23 的教训）
    ------------------------------------------------------
    样条在关键帧**之间**会自由摆动，摆进山体没人管；而地形是 80×80 的离散
    高度场，样条根本不知道它长什么样。于是每次只能修好一个关键帧，中间段又
    穿进去 —— 症状是画面里黑色树枝状裂缝（看到被背面剔除的内表面）。
    **关键帧密度必须与地形复杂度匹配**：66 秒穿越地形，130 个点（每秒 2 个）
    才能让线性插值天然贴地。

    返回 ``(times, positions, targets)``，三者等长，直接喂 Shot 的 LINEAR 通道。
    """
    n = max(8, int(count))
    times, pos, tgt = [], [], []
    for i in range(n):
        s = i / (n - 1)
        z = 110.0 - s * 155.0                  # +110 → -45：**不飞到边界**，
        x = 2.2 * math.sin(s * 5.4)            # 轻微摆动，别像轨道车
        g = ground_at(hm, x, z)
        lift = 8.0 + 38.0 * (1.0 - s) ** 2.2   # 起手 46m 高空 → 末段 8m 贴地
        pos.append([round(x, 3), round(g + max(lift, clearance), 3), round(z, 3)])
        # 注视点：前方 26m、比相机**低 8m**。
        # ⚠️ 不能用"前方地面高度 + 2.5"：前方若是封口高山（40m+），ground 会
        # 高过相机 ⇒ 相机抬头看天，末帧变成纯天空（实测过一次）。
        # 相对相机定义才保证"永远看着地面飞"。
        zt = z - 26.0
        tgt.append([round(x * 0.6, 3), round(pos[-1][1] - 8.0, 3), round(zt, 3)])
        times.append(round(s * duration, 3))

    # 相邻段穿地检查：把线段按 6 等分取样，插值高度必须高于沿途地形 + clearance。
    # 违反就把**后点**抬高（迭代收敛，因为抬后点会同时改善相邻两段）。
    for _ in range(8):
        worst = 0.0
        for k in range(len(pos) - 1):
            a, b = pos[k], pos[k + 1]
            for j in range(1, 6):
                u = j / 6.0
                xm = a[0] + (b[0] - a[0]) * u
                zm = a[2] + (b[2] - a[2]) * u
                ym = a[1] + (b[1] - a[1]) * u
                need = ground_at(hm, xm, zm) + clearance
                if ym < need:
                    d = need - ym
                    b[1] = round(b[1] + d, 3)
                    worst = max(worst, d)
        if worst < 0.05:
            break
    return times, pos, tgt


def build_shot(hm=None):
    """演出：地形整体升起（0→16s）+ 相机沿峡谷低空穿行（全 66s）。

    相机与注视点的高度**全部由地形算**（2026-11-23）：手填数字会让整条路径
    埋在山体内部，成片里出现黑色裂缝与黑椭圆（背面剔除 + 穿模）。
    """
    if hm is not None:
        times, pos, tgt = build_camera_path(hm)
    else:
        times = [0.0, DURATION]
        pos = [[0.0, 46.0, 110.0], [0.0, 8.0, -70.0]]
        tgt = [[0.0, 2.0, 84.0], [0.0, 2.0, -96.0]]
    return {
        'version': 1,
        'name': '02_terrain',
        'duration': DURATION,
        'scene': 'scenes/02_terrain.scene.json',
        'acts': [
            {'t': 0.0, 'label': '虚空余烬'},
            {'t': 16.0, 'label': '大地升起'},
            {'t': 34.0, 'label': '掠地'},
            {'t': 52.0, 'label': '峡谷'},
            {'t': 66.0, 'label': '出峡'},
        ],
        'notes': ('相机路径由 film/gen/terrain.build_camera_path 程序化生成：'
                  '130 个等距关键帧（每秒 2 个）+ 逐点离地间隙 + 相邻段穿地检查，'
                  '用 LINEAR 插值而非样条。'),
        'channels': [
            {
                'node': 'terrain', 'prop': 'translation', 'interpolation': 'CUBICSPLINE',
                'times': [0.0, 16.0, DURATION],
                'values': [[0.0, -80.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
            },
            {
                'node': '$camera', 'prop': 'position', 'interpolation': 'LINEAR',
                'times': times, 'values': pos,
            },
            {
                'node': '$camera', 'prop': 'target', 'interpolation': 'LINEAR',
                'times': times, 'values': tgt,
            },
            {
                'node': '$camera', 'prop': 'fov', 'interpolation': 'LINEAR',
                'times': [0.0, DURATION], 'values': [58.0, 58.0],
            },
            {
                'node': '$env', 'prop': 'sun_intensity', 'interpolation': 'CUBICSPLINE',
                'times': [0.0, 16.0, 40.0, DURATION],
                'values': [0.4, 2.10, 2.60, 2.20],
            },
        ],
    }

def audit(hm):
    """校验：分辨率、值域、起伏度（太平/太碎都报错）。"""
    problems = []
    if len(hm) != GRID or any(len(r) != GRID for r in hm):
        problems.append(f'高度图尺寸不是 {GRID}x{GRID}')
    flat = [v for r in hm for v in r]
    lo, hi = min(flat), max(flat)
    if lo < 0.0 or hi > 1.0:
        problems.append(f'高度值越界: [{lo}, {hi}] 应在 0..1')
    if hi - lo < 0.25:
        problems.append(f'起伏太小（{hi - lo:.3f}）—— 会是一块平板')
    # 相邻格平均差：太碎说明噪声尺度太小，看起来像砂纸
    diffs = [abs(hm[r][c + 1] - hm[r][c]) for r in range(0, GRID, 4)
             for c in range(GRID - 1)]
    rough = sum(diffs) / len(diffs)
    if rough > 0.06:
        problems.append(f'相邻格差异过大（{rough:.4f}）—— 地形会像砂纸，调小 scale')
    return problems, (lo, hi, rough)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只校验，不写文件')
    args = ap.parse_args(argv)

    hm = build_heights()
    problems, (lo, hi, rough) = audit(hm)
    if problems:
        print('[terrain] **FAIL**')
        for p in problems:
            print('  -', p)
        return 1
    print(f'[terrain] OK: {GRID}x{GRID} 高度 [{lo:.3f}, {hi:.3f}] '
          f'起伏 {hi - lo:.3f} 相邻差 {rough:.4f}')

    if args.check:
        return 0

    scene = build_scene(hm)
    shot = build_shot(hm)
    os.makedirs(os.path.dirname(SCENE_PATH), exist_ok=True)
    with open(SCENE_PATH, 'w', encoding='utf-8', newline='') as f:
        # 2026-11-23 修：此前手写 JSON 拼接、且**只写 children[0]** ——
        # 加第二个节点（水面）时被静默丢弃，画面毫无变化，白查了一轮材质。
        # 现在整体 json.dump（hm 展开成 6400 行、文件 ~150KB，正确优先于紧凑）。
        json.dump(scene, f, ensure_ascii=False, indent=1)
        f.write(chr(10))
    with open(SHOT_PATH, 'w', encoding='utf-8', newline='') as f:
        json.dump(shot, f, ensure_ascii=False, indent=1)
        f.write('\n')

    # 自校验：手写拼接必须当场 round-trip，否则要等 probe 才炸（实测踩过一次：
    # 末尾多一个 `}` → JSONDecodeError: Extra data，报错位置离真正原因很远）。
    for path in (SCENE_PATH, SHOT_PATH):
        with open(path, encoding='utf-8') as f:
            json.load(f)
    print(f'[terrain] 写入 {SCENE_PATH} ({os.path.getsize(SCENE_PATH) / 1024:.1f} KB)')
    print(f'[terrain] 写入 {SHOT_PATH}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
