# -*- coding: utf-8 -*-
"""桥接层 —— worldwright 消费 superengine 装配好的三仓。

为什么存在
----------
worldwright 是**表现层**，不自己造地形/城镇/地牢（那是 worldbuilder 的活），
也不自己实现 shader（那是 3dworld 的活）。它只做一件事：**把三仓的输出
拿过来，编排成 12 个区域。**

这个模块就是那个"拿"的入口。三条纪律：
1. **不复制算法**：所有世界数据必须来自 `ctx.worldbuilder.*`；
2. **契约先行**：拿数据前先看 `contract_report()`，版本不兼容就停；
3. **可离线**：`--check` 能在无窗口环境跑（不碰 GL），方便 CI 与"只验契约"。

用法::

    python -m worldwright.bridge --check          # 只验契约 + 打印地形摘要
    python -m worldwright.bridge --terrain 32     # 生成 32x32 地形并打统计
"""
from __future__ import annotations

import argparse
import os
import sys

# superengine / worldbuilder 都在同级 repos 下，不在 PyPI 上。
# 注意层级：repos/superengine/superengine/__init__.py —— 要加的是**项目根**
# `repos/superengine`，不是 `repos`（后者会让 Python 找到没有 __init__ 的目录）。
_REPOS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _name in ('superengine', 'worldbuilder', 'an-engine'):
    _p = os.path.join(_REPOS, _name)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)


def boot_engine(config: str | None = None):
    """装配三仓；返回 (ctx, 契约报告)。失败时抛异常，不吞。"""
    from superengine.assembly import boot
    return boot(config)


def contract_table(report: dict) -> list[tuple[str, str, str]]:
    """把契约报告摊平成 (仓, 契约名, 版本区间) 三元组。"""
    rows = []
    for repo, caps in (report.get('contracts') or {}).items():
        if isinstance(caps, dict):
            for name, spec in caps.items():
                rows.append((repo, name, str(spec)))
        else:
            rows.append((repo, str(caps), ''))
    return sorted(rows)


def world_summary(ctx, size: int = 24, seed: int = 20261123) -> dict:
    """从 worldbuilder 拿一整个世界，返回**可断言的统计**。

    关键：`ctx.worldbuilder` **本身就是** `terrain_source`（`WorldbuilderBridge`
    实现了 `generate`），不存在 `ctx.worldbuilder.terrain_source` 这个属性 ——
    首版按契约名去取，拿到的是 None。这里直接调 bridge 自己。

    `generate()` 返回的是完整世界：height / filled / water / sea_level /
    temperature / precipitation / biomes / rivers / lakes / coast / acc / meta。
    我们只统计"能证明它真的生成了"的那几项。
    """
    import numpy as np

    wb = getattr(ctx, 'worldbuilder', None)
    if wb is None:
        raise RuntimeError('ctx 上没有 worldbuilder 服务（装配失败？）')
    w = wb.generate(int(size), int(size), seed=int(seed))
    h = np.asarray(w['height'], dtype=float)
    return {
        'shape': h.shape,
        'min': round(float(h.min()), 4),
        'max': round(float(h.max()), 4),
        'mean': round(float(h.mean()), 4),
        'biomes': int(len(np.unique(np.asarray(w['biomes'])))),
        'rivers': int(len(w.get('rivers') or [])),
        'lakes': int(len(w.get('lakes') or {})),
        'sea_level': round(float(w.get('sea_level', 0.0)), 4),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只验契约')
    ap.add_argument('--terrain', type=int, default=0, help='生成 NxN 地形并打统计')
    ap.add_argument('--config', default=None)
    args = ap.parse_args(argv)

    ctx, report = boot_engine(args.config)
    rows = contract_table(report)
    print(f'[bridge] 装配成功，{len(rows)} 条契约：')
    for repo, name, spec in rows:
        print(f'  {repo:14} {name:20} {spec}')

    if args.terrain:
        st = world_summary(ctx, args.terrain)
        print(f'[bridge] world {st["shape"]} height {st["min"]}~{st["max"]} '
              f'(mean {st["mean"]}) biomes={st["biomes"]} '
              f'rivers={st["rivers"]} lakes={st["lakes"]} sea={st["sea_level"]}')
        # 三个断言：起伏非零 / 有多个生物群系 / 有河流 —— 生成器真的跑了
        assert st['max'] > st['min'], '高度场是常量平面 —— 生成器没真的跑'
        assert st['biomes'] >= 2, f'生物群系只有 {st["biomes"]} 种，不合理'
        assert st['rivers'] >= 1, '一条河都没有，水系没生成'
        print('[bridge] world 断言通过（起伏/生物群系/河流）')

    print('BRIDGE_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
