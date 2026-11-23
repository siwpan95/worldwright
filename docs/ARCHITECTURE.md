# worldwright 的定位：四仓流水线里的「表现层」

> 2026-11-23 13:40。本文修正了 `README.md` 里的定位 —— 之前我以为 worldwright
> 要"自己接 94 个能力"，实际上**能力早就在另外三个仓里，而且已经装配好了**。

## 1. 四仓关系（实测，非设想）

```
worldbuilder ──┐  worldspec_source / terrain_source / dungeon_source
an-engine   ──┼─→ superengine ──→ ctx ──→ worldwright
3dworld     ──┘  terrain_sink / render_sink    （12 个区域的表现 + 编排）
                 ↓
            contracts + assembly + Hmr（热重载）
```

`superengine.assembly.boot()` 实测输出：

```
worldbuilder: worldspec_source 1.0.0 in >=1.0,<2.0
              terrain_source  1.0.0 in >=1.0,<2.0
              dungeon_source  1.0.0 in >=1.0,<2.0
tdworld:      terrain_sink    1.0.0 in >=1.0,<2.0
              render_sink     1.0.0 in >=1.0,<2.0
anengine:     gameplay_world  1.0.0 in >=1.0,<2.0
              mapgraph_source 1.0.0 in >=1.0,<2.0
              rules_kernel    1.0.0 in >=1.0,<2.0
```

**这三行是"全链路打通"的现成地基。** 我之前花了 10 小时在 `3dworld-demos/film/`
里自己拼几何，而这些契约一直就绪。

## 2. 各层职责（对照业界 PCG 管线）

调研结论（`vgsources.com` / `realsoftgames.com` / AAA 管线指南）一致指出，
生产级程序化管线分三层，**且必须分离**：

> "A production PCG pipeline usually separates **generation, validation and
> presentation**."

| 层 | 业界叫法 | 本项目的仓 | 已有什么 |
|---|---|---|---|
| **生成** | generation | `worldbuilder`（36 py / 7938 行） | terrain / town / dungeon / wfc / road / hydro / climate / poi / loot |
| **校验** | validation | `superengine`（28 py / 3883 行） | 契约版本校验 / fiber 装配 / 门禁 / 实现热替换 |
| **表现** | presentation | `3dworld`（58 engine 模块）+ **`worldwright`** | 渲染 sink + 12 区编排 |

**worldwright 只做第三层里的"编排与呈现"**：
- 拿 `worldbuilder` 生成的世界数据（不自己造地形/城镇/地牢）
- 通过 `tdworld` 的 `render_sink` 渲染（不自己实现 shader）
- 用 `superengine` 的 `Hmr` 热调（不自己写热重载）

## 3. 之前错在哪（一句话）

**我把"表现层"当成了"全栈"，于是重写了生成层（手搓几何）和校验层（自己试错）。**

结果：几何 100%、内容 53%、能力调用 10%（`CAPABILITY-MAP.md` 实测）。
而真正的三层分离架构，全哥早就建好了 —— `superengine` 的 README 第一行就写着
"只做契约、桥接、装配、门禁，不含任何算法"。

## 4. 12 个区域怎么落到这套架构上

| 区域 | 数据从哪来 | 表现怎么做 |
|---|---|---|
| r02 地脉 | `worldbuilder.terrain_source` | `tdworld.terrain_sink` |
| r03 城邦 | `worldbuilder.town` + `roadnet` + `wfc` | 程序化立面 + `csm` 投影 |
| r06 洞窟 | `worldbuilder.dungeon_source` | 元胞 + `volumetrics`（火把光） |
| r09 场 | `worldbuilder.noise` + `roadnet` 的图 | `curves` + `compute` 流场 |
| 其余 8 区 | 已有的区域生成器（保留） | 逐步接入 `csm`/`soft_shadow`/`dof`/`oit` |

**关键变化**：r02/r03/r06 这三区**不再手搓几何**，改为消费 worldbuilder 的数据。

## 5. 里程碑（替换掉旧的 M0-M5）

| 里程碑 | 内容 | 验收 |
|---|---|---|
| **W0** 桥接 | `worldwright/bridge.py`：`boot()` → `ctx` → 拿 worldspec / terrain / dungeon | `python -m worldwright.bridge --check` 打印三仓契约与一份 terrain 摘要 |
| **W1** 三区重做 | r02/r03/r06 改消费 worldbuilder | 每区的节点数、瓦片数与 worldbuilder 输出**一致**（不是"看起来像"） |
| **W2** 表现升级 | csm / soft_shadow / volumetrics / dof / oit 接进 `tdworld.render_sink` | 同机位开关前后对比图 + 调用计数 |
| **W3** 热调 | 接 `superengine.live`（Hmr）+ `devloop` | 改 `configs/dev.json` 的 seed，地形就地重建，**不重启进程** |
| **W4** 世界编排 | 12 区统一坐标 + 流式加载 | 一条连续路径 |
| **W5** 出片 | delivery | 成片（最后） |

**W3 就是你要的"实时漫游 + 参数热调"** —— 不需要再调研，`superengine/live.py`
已经实现了 Cordis `Hmr` 的两阶段 reload（先重导入、再换 fiber、失败整体回滚）。

## 6. 实时漫游

`superengine/live.py` 的 Hmr 解决"**改参数**"，没解决"**用键盘走**"。
但这两件事可以分开做：
- 热调 → 直接用 Hmr（W3）
- 漫游 → `worldwright` 加一个 pyglet 实时循环（W4 之后，2-4h）

**所以 `PLAN-REALTIME.md` 里 R0/R1 的结论仍然有效，但优先级降到 W4 之后**：
先让世界有内容（W1/W2），再让人能走进去。
