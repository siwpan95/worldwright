# worldwright —— 用 `3dworld` 搭的「造界」

> 项目代号《造界》。**按独立游戏规格推进的世界建模项目**。
> 视频是它最后的副产品，不是目标。

## 仓库角色定位

| 项 | 值 |
|---|---|
| 类型 | **应用 / 世界建模**（不是 demo，不是视频工程） |
| 依赖 | `3dworld`（PyPI，导入名 `world3d`） |
| 体量目标 | **30,000+ 行**（对标 `3dworld-globe` 的 7,917 行 × 4~6） |
| 为什么这么大 | 12 个 **globe 级别**的区域 + 一套 94 模块的能力调度层 |

**为什么必须独立成仓**：挂在本仓最早的形态（`3dworld-demos/film/`）是错的。
`demos` 是"67 个最小可运行示例"的集合，每个几百行；而本项目全部落实后
是 3 万行的世界建模工程。**把它放在 demos 下，等于宣告它只是个附属品**——
过去 10 小时的所有"急于出片"的决策，都是从那个位置长出来的。

## 它是什么

一个**世界**，由 12 个区域组成，每个区域是完整的建模单元：

```
区域 = 几何 + 材质 + 光照 + 物理 + 行为 + 音频 + 验证
```

「出片」只是 `delivery/` 的最后一步：把世界跑一遍、录下来。
**没有世界，就没有片子**——这是过去做反了的地方。

## 目录

```
worldwright/
  capabilities/          能力层：每个能力包装一个引擎模块（94 个待接）
    render/              csm soft_shadow volumetrics dof motionblur oit reflect
    geom/                terrain clipmap voxel pointcloud gltf
    sim/                 physics rigid fieldext ca
    behave/              fsm bt fov wfc lsystem dungeon
    material/            proctex texproj spectrum sdf2d
    audio/               adaptive fusion
    anim/                skin skeleton
    registry.py          能力协议 + 启动自检 + 调用统计
  regions/               12 个区域（建模单元）
    r01_void/ r02_terrain/ ... r12_finale/
  world/                 编排层：世界坐标、区域连接、流式加载
  delivery/              产出层：相机、编码、成片（**最后做**）
assets/                  程序化资产配置
tools/                   编辑器 / 预览 / 校验
tests/
docs/
```

## 现状（诚实版）

| 层 | 状态 | 说明 |
|---|---|---|
| `capabilities/` | **0 / 94** | 只有目录骨架，一个能力都没接 |
| `regions/` | 12 个**原型** | 从 `3dworld-demos/film/gen/` 迁入的生成器，仍是"手搓几何" |
| `world/` | 空 | 旧版世界层留在 `film/world.py` |
| `delivery/` | 空 | 旧版 799s 成片作为**基线**保留在 `3dworld-demos/film/out/` |
| 测试 | 空 | — |

**迁移来的 12 个原型只做一件事：把场景"搭出来"。它们不是建模单元**，
因为它们调用的是 `geometry.box()`，不是 `engine.csm` / `logic.wfc`。
把它们重构成"调能力"的建模单元，是本项目的核心工作。

## 推进路线（建模优先，出片最后）

| 里程碑 | 内容 | 完成标志 |
|---|---|---|
| **M0** 能力底座 | `registry.py`：能力协议 + 自检 + 统计 | 故意写错模块路径 → 启动失败；`--list` 列出 94 个模块的接入状态 |
| **M1** 渲染与材质 | csm / soft_shadow / volumetrics / dof / motionblur / oit / reflect / proctex / texproj / spectrum / sdf2d | 11 个 pass 可在任意场景开关，前后对比图 + 调用计数 |
| **M2** 模拟与行为 | physics / physics3d / blocks / compute / gpu_cull / fsm / bt / fov / wfc / lsystem / dungeon / curves / noise_vec | 每个能力有"它真的跑了"的证据（轨迹 CSV / 状态日志 / 生成结果） |
| **M3** 区域建模 | 12 个区域逐个重构成建模单元 | 每个区域：资产清单齐 + 能力调用非零 + 单区可独立渲染 |
| **M4** 世界编排 | world/ + 流式加载 + 区域过渡 | 一条连续相机路径穿过 12 区 |
| **M5** 出片 | delivery/ | 成片（**这一步最不重要，但必须最后做**） |

**顺序不可颠倒**：M0-M3 没完成就做 M5，结果就是过去 10 小时的东西——
一个奇美拉。

## 与旧资产的关系

| 旧资产 | 处理 |
|---|---|
| `3dworld-demos/film/gen/*.py` | **已迁入 `regions/`**，作为"原型"保留；逐步重写为调能力 |
| `3dworld-demos/film/*.md` | 审计与计划留在原处（历史记录），本文是新起点 |
| 旧成片 799s | 保留为**基线**，不删除；新平台产出 v2 后对比 |
| `3dworld` 引擎 | 继续反哺：M1/M2 会暴露引擎侧缺口（过去 6 次反哺都来自这种压力） |

## 许可

MIT。与 `3dworld` / `3dworld-globe` 一致。
