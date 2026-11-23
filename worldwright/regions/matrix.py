"""能力矩阵生成器 —— 67 个 demo → 12 幕的归属表，**缺一个就报错**。

为什么用生成器而不是手写 markdown
--------------------------------
"67 个 demo 全部有归属"是 M2 的验收硬指标。手写表格只能证明"我写过那一行"，
证明不了"没有漏"；而漏掉的那几个恰恰是最不会被想起来的（比如 `crowdward`
因为默认静止被排除过、`choreoward`/`kkriegerward` 是同壳重复被排除过）。
生成器把归属写成**数据**，然后用集合差集当场对账 —— 缺 / 多 / 重 三种错都拦。

用法::

    python film/gen/matrix.py            # 生成 film/capability_matrix.md
    python film/gen/matrix.py --check     # 只校验，不写文件（CI/提交前用）
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILM_DIR = os.path.dirname(HERE)
ROOT = os.path.dirname(FILM_DIR)

#: 幕 id → (幕名, 时长, [demo 名], 该幕承载的引擎能力落点)
#: demo 名 = `examples/<name>.py` 去掉扩展名。**每幕的主归属唯一**，
#: 跨幕复用（如 mountain 在 X 主用、XI 复用）只在备注里写，不重复计入。
ACTS = {
    '01_void': ('空无', 24.0,
                ['particles_gpu', 'particleward'],
                'engine/particles.py（GPU 实例化）、postfx Bloom'),
    '02_terrain': ('地脉', 66.0,
                   ['terrain_flyover', 'terrainward', 'cdlod_terrain', 'water_waves',
                    'volumetric_fog', 'godhand', 'demoscene_tunnel'],
                   ('logic/terrain、terrain_lod、terrain_clipmap、logic/waves、'
                   'engine/volumetrics、core/terrain_core、shaders→tunnel')),
    '03_city': ('城邦', 80.0,
                ['wardfall', 'lindenwood', 'collapseward', 'texward', 'sandward',
                 'material_lab', 'shadow_map', 'crowdward', 'blockworld',
                 'minecraft_style', 'tower_defense', 'scene_walker'],
                ('logic/town、logic/lsystem、logic/wfc、engine/proctex、engine/texproj、'
                'engine/texture、engine/soft_shadow、behavior_tree + pathing_core、'
                'logic/blocks、games/tower_defense、adaptive_music')),
    '04_machine': ('机械', 74.0,
                   ['choreoward', 'boxward', 'brickward', 'eventward', 'fsmward',
                    'skinned_creature', 'ozzward', 'gltfward', 'kkriegerward'],
                   ('logic/skeleton、logic/animation、anim/ozz_lite、engine/skin、'
                   'engine/gltf、engine/orchestration.Bus、engine/fsm、logic/choreography')),
    '05_crystal': ('晶体', 64.0,
                   ['crystalward', 'posterward', 'raymarch_sdf', 'stillhall', 'dof_focus'],
                   ('engine/spectrum、spectral_glsl、sdf2d、sdf2d_glsl、'
                   'shaders→raymarch、engine/dof、games/hall')),
    '06_cave': ('洞窟', 64.0,
                ['dungeonward', 'cellward', 'voxel_terrain', 'brogueward', 'rayhold',
                 'liminall'],
                ('logic/dungeon、logic/ca、logic/voxel、logic/fov、engine/particles、'
                'shaders→tunnel、logic/liminall、games/fps')),
    '07_swarm': ('法则·群', 58.0,
                 ['boids', 'boidward', 'swarmward', 'pulsefall'],
                 'logic/boids、engine/particles、games/storm、games/pulse、engine/audio'),
    '08_body': ('法则·体', 58.0,
                ['rigidward', 'box2dward', 'wboit_demo'],
                'physics/jolt_lite、physics/box2d_lite、engine/oit'),
    '09_field': ('法则·场', 54.0,
                 ['pointcloud_edl', 'gpu_cull_field', 'computeward', 'curveward',
                  'flowward', 'reactward'],
                 ('engine/pointcloud、engine/gpu_cull、engine/compute、logic/curves、'
                 'engine/framegraph')),
    '10_void': ('虚空', 80.0,
                ['voidward', 'solar_system', 'nordic_saga', 'kid_a_walker_3d',
                 'mountain', 'motion_blur'],
                ('logic/skeleton（轨道）、games/void、logic/nordic_saga、logic/kid_a、'
                'engine/motionblur、adaptive_music')),
    '11_loop': ('回环', 64.0,
                ['csm_shadow'],
                'engine/csm（另复用 mountain 的气象、lindenwood 的季节、volumetrics）'),
    '12_finale': ('收束', 47.0,
                  ['engine_showcase', 'frame_graph', 'replayward', 'director',
                   'scene_viewer', 'audioward'],
                  ('renderer(PBR/IBL) + postfx + framegraph + presentation/film + '
                  'logic/replay + presentation/timeline_ui')),
}


def all_demos():
    """``examples/*.py`` 里的演示名（排除下划线开头的内部件）。"""
    d = os.path.join(ROOT, 'examples')
    return sorted(f[:-3] for f in os.listdir(d)
                  if f.endswith('.py') and not f.startswith('_'))


def audit():
    """返回 (归属映射, 未归属, 重复归属, 幽灵引用, 总时长)。"""
    owner, dup = {}, []
    for act_id, (_title, _dur, demos, _cap) in ACTS.items():
        for name in demos:
            if name in owner:
                dup.append((name, owner[name], act_id))
            owner[name] = act_id
    existing = set(all_demos())
    unowned = sorted(existing - set(owner))
    ghosts = sorted(set(owner) - existing)
    total = sum(v[1] for v in ACTS.values())
    return owner, unowned, dup, ghosts, total


def render():
    owner, unowned, dup, ghosts, total = audit()
    xfade = 1.2
    film_len = total - xfade * (len(ACTS) - 1)
    lines = [
        '# 能力矩阵 —— 67 个 demo → 12 幕',
        '',
        '> **本文件由 `film/gen/matrix.py` 生成，不要手改。**',
        '> 归属写成数据、覆盖用集合差集对账：缺 / 多 / 重三种错都会让脚本非零退出。',
        '',
        (f'- 幕数 **{len(ACTS)}**，各幕时长合计 **{total:.1f}s**，'
        f'扣掉 {len(ACTS) - 1} 处 xfade {xfade}s 后成片 **{film_len:.1f}s**'),
        (f'- demo 总数 **{len(all_demos())}**，已归属 **{len(owner)}**，'
        f'未归属 **{len(unowned)}**'),
        '',
        '| # | 幕 | 时长 | demo 数 | demo（= 能力载体） | 引擎能力落点 |',
        '|---|---|---:|---:|---|---|',
    ]
    for i, (act_id, (title, dur, demos, cap)) in enumerate(ACTS.items(), 1):
        lines.append(f'| {i} | `{act_id}` {title} | {dur:.0f}s | {len(demos)} | '
                     f'{", ".join("`" + d + "`" for d in demos)} | {cap} |')
    lines += [
        '',
        '## 跨幕复用（不重复计入归属）',
        '',
        '- `mountain`：X 幕主用（远景孤峰），XI 幕复用其气象（雨雪）',
        '- `lindenwood`：III 幕主用（L-System 植被），XI 幕复用其季节色',
        '- `volumetric_fog`：II 幕主用（高度雾），XI 幕复用（光柱随光向变化）',
        '- `csm_shadow`：XI 幕主用（级联光向变化），XII 幕复用（全 pass 叠加）',
        '- `liminall`：VI 幕主用（后室走廊），X 幕复用（梦境插叙）',
        '',
        '## 判定口径',
        '',
        '- **"有归属"≠"能播"**：本表只回答"这个能力在哪一幕被消费"。',
        '  能否播由 `verify_demos.py` 的全量冒烟与每幕的 `probe.py` 帧证据回答。',
        '- **主归属唯一**：一个 demo 只记在它贡献最大的那一幕，复用写在上面单独一节。',
        '  否则"67 全归属"这个数会因为跨幕复用而虚高。',
        '',
    ]
    return '\n'.join(lines), unowned, dup, ghosts, total


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只校验，不写文件')
    args = ap.parse_args(argv)

    text, unowned, dup, ghosts, total = render()
    problems = []
    if unowned:
        problems.append(f'未归属的 demo（{len(unowned)}）: {unowned}')
    if dup:
        problems.append(f'重复归属: {dup}')
    if ghosts:
        problems.append(f'引用了不存在的 demo: {ghosts}')

    if problems:
        print('[matrix] **FAIL**')
        for p in problems:
            print('  -', p)
        return 1

    print(f'[matrix] OK：{len(all_demos())} 个 demo 全部有唯一归属，'
          f'{len(ACTS)} 幕合计 {total:.0f}s')
    if not args.check:
        out = os.path.join(FILM_DIR, 'capability_matrix.md')
        with open(out, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        print(f'[matrix] 已写入 {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
