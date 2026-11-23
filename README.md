# worldwright —— 用 `3dworld` 搭的「造界」

#A production PCG pipeline separates generation, validation and presentation.

> 出处：vgsources.com《Generative AI vs. Traditional Procedural Generation in Games》
> （2026-11-23 调研）。本项目按这三层分工：worldbuilder（generation）/
> superengine（validation）/ 3dworld + worldwright（presentation）。

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

## 工具：自动找机位

「找不到能证明能力的那一帧」在一天里发生三次（水面、洞窟、运动模糊），
每次都是手调相机。这个工具把它变成流程：

```bash
python -m worldwright.tools.find_camera --scene assets/r03_city.scene.json
```

1. 从 `Mesh.world_aabb` 累出**场景包围盒**（自动跳过 ground/floor，否则会被地面撑到几百米）；
2. 生成**六个候选机位**：俯视 / 四向侧视 / 内部；
3. 每个渲染一帧，算 **平均亮度 + 标准差**；
4. 全黑或纯色（std < 6）的机位直接标 `EMPTY`，省掉人眼确认。

**局限（已定位到原因，2026-11-23 实测）**：

- **已排除**：
  - 雾被 far 截断 —— `near=0.1 / far=450` 是**相机裁剪面**，不是雾的 near/far。
    俯视 190m、fov 60° 时地面距离仅 190~245m，没碰到 far。
  - target 指向正下方 / 距离 152m / 高度 190m —— 三者都让画面更均匀，**必然无效**
    （已证：`low_alt_35` 才有变化，抬高只会更糊）。
- **根因（两个分支，实测都成立）**：
  1. **地面零信号**：`fog_off` 后 std 从 **5.18 → 2.90**、均值从 [67,59,55]
     降到 [26,23,24]（地面色）→ **原来的信号全靠雾的径向斜坡撑着**，
     地面本身是单色平面 + 均匀光照，俯视时法线全朝上。
  2. **`fog_falloff` 是距离项、不是高度项**：`falloff=0` 后均值冲到 [144,131,121]
     （接近 `fog_color` 经 tonemap 的值）→ 190m 处雾**饱和**。
     原值 0.026 在**抑制**远处雾（特征长度约 38m）。
- **修法（已实测有效）**：机位压到 **35m** → std 5.18→**13.39**、
  unique 239→**453**、radialΔ 1.92→**22.17**。
- **影响面**：所有 `h ≫ 38m` 的俯视位姿。
  **本工具的 `top` 机位已从正俯视改成 60° 俯角。**
- **判读方法**：`python -m worldwright.tools.frame_stat <png>`
  - `std_gray`：<1 真常数 / <8 极弱 / ≥8 有结构 —— **但它会被大面积渐变骗**
    （`top35` 的 std=36 里很大一块是"暗天空 vs 亮地面"）。
  - `unique`：颜色种类数 —— **最可靠**。`top` 只有 21 种，`top35` 有 749 种。
  - `radialΔ`（中心与四角差）：非 0 = 有径向斜坡。
  **三者一起看**：std 大但 unique 低 → 是渐变不是内容。


## W1 的 3/3 是什么范围（重要，避免误判"还剩 9 幕没做"）

`worldbuilder` 只产出**三类**世界数据：`terrain_source` / `town` / `dungeon_source`。
12 幕里能对上号的只有三幕：

| 幕 | worldbuilder 数据源 |
|---|---|
| r02 地脉 | `height` + `rivers`（terrain_source） |
| r03 城邦 | `generate_town()` 的 ward + streets |
| r06 洞窟 | `generate_dungeon()` 的 grid + rooms |

**剩下 9 幕（机械/晶体/群/体/场/虚空/回环/收束）在 worldbuilder 里没有对应数据源** ——
它们不是"没做完"，是**"这一类场景本来就不由 worldbuilder 生成"**。

所以 W1 的 3/3 是**"worldbuilder 覆盖范围内的全部"**，不是"12 个里的 3 个"。
剩下 9 幕只有两条路：
1. **保持手搓**（合理：它们本来就不是地理类场景）；
2. **扩展 worldbuilder**（比如加机械/晶体的 generator）—— 那是另一个项目级决定，
   得先问清楚"这些场景是否该由 worldbuilder 负责"。

## 现状（诚实版）

| 层 | 状态 | 说明 |
|---|---|---|
| **`bridge.py`** | ✅ **W0 通** | 接上 `superengine.boot()`，8 条契约校验 + worldbuilder 世界数据断言 |
| `capabilities/` | 0 / 94 | 但**大部分能力其实在另外三个仓里**，见 `docs/ARCHITECTURE.md` |
| `regions/` | 12 个原型 | 从 `film/gen/` 迁入，仍是"手搓几何"，待改为消费 worldbuilder |
| `world/` | 空 | 旧版世界层留在 `film/world.py` |
| `delivery/` | 空 | 旧版 799s 成片作为**基线**保留 |

**W0 的实测输出**：

```
[bridge] 装配成功，8 条契约
[bridge] world (24, 24) height 0.3639~0.6969 (mean 0.5541)
         biomes=11 rivers=10 lakes=3 sea=0.5261
[bridge] world 断言通过（起伏/生物群系/河流）
```

**W1 已完成两区**：

| 区 | 消费什么 | 数据如何影响画面 |
|---|---|---|
| **r02 地脉** | `height` + `rivers` | 地形用 `height`（64×64→96×96）；**相机沿最长的一条河飞**（改 seed → 河变 → 路线变） |
| **r06 洞窟** | `generate_dungeon()` 的 `grid/rooms/connections` | 地板/洞顶用 grid 反转；**相机沿房间连接的 BFS 序列走**（不再需要"强制清一条走廊"这种手搓补丁）；4 盏火把点光源 |
| **r03 城邦** | `town.generate_town()` 的 12 ward + 6 streets | 建筑在 **ward 多边形内**网格切分（点在多边形内判定 + 避让街道 5.5m）；**相机沿最长街道折线飞** |

出图：`out/r02_t20.png`（河谷）、`out/r06_t30.png`（洞窟内景）。

**迁移来的 12 个原型只做一件事：把场景"搭出来"。它们不是建模单元**，
因为它们调用的是 `geometry.box()`，不是 `engine.csm` / `logic.wfc`。
把它们重构成"调能力"的建模单元，是本项目的核心工作。

## 推进路线（建模优先，出片最后）

**四仓分工**（详见 `docs/ARCHITECTURE.md`）：
`worldbuilder`（生成）→ `superengine`（校验/装配/热重载）→ `tdworld`（渲染）→
**`worldwright`（12 区表现与编排）**。

| 里程碑 | 内容 | 完成标志 | 状态 |
|---|---|---|---|
| **W0** 桥接 | `bridge.py`：boot → 契约 → worldbuilder 世界数据 | 契约 8 条 + 世界断言过 | ✅ |
| **W1** 三区重做 | r02/r03/r06 改消费 worldbuilder | 与 worldbuilder 输出**一致** | ✅ **3/3**（见下注） |
| **W2** 表现升级 | 6 个能力逐个接入（dof / motionblur / oit / csm / soft_shadow / volumetrics） | 每项：开关对比 + 调用计数 | **2.5 / 6** |
| **W3** 热调 | 接 `superengine.live`（Cordis Hmr） | 改 seed 就地重建，不重启进程 | 待做 |
| **W4** 世界编排 | 12 区统一坐标 + 流式加载 | 一条连续路径 | 待做 |
| **W5** 出片 | delivery | 成片（最后） | 待做 |

**W2 明细**（每项单独发版，像 0.9.2 的点光源那样）：

| 能力 | 版本 | 状态 | 说明 |
|---|---|---|---|
| dof 景深 | 0.9.3 | ⚠️ 管线通 | focus 标定未收敛（整片都虚） |
| motionblur | 0.9.4 | ⚠️ 部分 | 有模糊证据、方向性未确认 |
| oit 透明 | — | ❌ **阻塞** | 接线完成，但**透明路径把颜色洗白**（同一块红板：不透明 [134,37,36] / 透明 [167,167,166]）。范围已缩到 `wboit_composite` 的权重函数与色彩空间 |
| csm 级联阴影 | — | ❌ 未做 | 需 shadow map FBO + 光源视角 pass + pbr 采样 |
| soft_shadow | — | ❌ 未做 | 依赖 csm |
| volumetrics | — | ❌ 未做 | 射线步进 + 深度采样（第 X 幕收益最大） |

**W3 就是"实时漫游 + 参数热调"的地基** —— `superengine/live.py` 已实现 Cordis
`Hmr` 两阶段 reload，不需要重新调研。

**顺序不可颠倒**：W0-W3 没完成就做 W5，结果就是过去 10 小时的东西。

## 与旧资产的关系

| 旧资产 | 处理 |
|---|---|
| `3dworld-demos/film/gen/*.py` | **已迁入 `regions/`**，作为"原型"保留；逐步重写为调能力 |
| `3dworld-demos/film/*.md` | 审计与计划留在原处（历史记录），本文是新起点 |
| 旧成片 799s | 保留为**基线**，不删除；新平台产出 v2 后对比 |
| `3dworld` 引擎 | 继续反哺：M1/M2 会暴露引擎侧缺口（过去 6 次反哺都来自这种压力） |

## 许可

MIT。与 `3dworld` / `3dworld-globe` 一致。
