"""帧统计 —— 贴着一张 PNG 跑，回答"这一帧里到底有没有信号"。

为什么独立成一个文件
------------------
判断"画面是不是空的"不能用肉眼看，也不能只报一个 std。要能回答三件事：

1. **均值落在哪** —— 与 `fog_color` 换算后的值比，判断是不是"被雾吃光"；
2. **std 有多大** —— 分通道算（合并算会把色差吃掉）；
3. **中心与四角是否相同** —— 相同 = 常数（没出图/纯色）；不同 = 有径向斜坡。

本机没装 PIL，用 pyglet 读（它本来就在依赖里）。

用法::

    python -m worldwright.tools.frame_stat out/cam_r03_city_top.png
    python -m worldwright.tools.frame_stat a.png b.png      # 批量对比
"""
from __future__ import annotations

import os
import sys


def _load(path):
    """读 PNG → float32 HxWx3（0..255）。用 pyglet，不引 PIL。"""
    import pyglet
    img = pyglet.image.load(path)
    data = img.get_image_data()
    # get_data('RGB') 在这版 pyglet 上仍返回 RGBA（4 通道），首版按 3 通道 reshape
    # 直接 ValueError（518400 = 480*270*4）。用负 stride 同时解决两件事：
    # 行紧凑 + 上下翻转（GL 原点在左下，PNG 在左上）。
    raw = data.get_data('RGBA', -data.width * 4)
    import numpy as np
    return np.frombuffer(raw, dtype=np.uint8).reshape(
        data.height, data.width, 4)[:, :, :3].astype(np.float32)


def stat(path):
    """返回 dict：均值 / 分通道 std / 灰度 std / 中心-四角差 / 唯一色数。"""
    import numpy as np
    a = _load(path)
    h, w, _ = a.shape
    gray = a.mean(2)
    center = a[h // 2, w // 2]
    corners = np.array([a[2, 2], a[2, -2], a[-2, 2], a[-2, -2]])
    return {
        'path': path,
        'size': (w, h),
        'mean': a.mean((0, 1)),
        'std_rgb': a.std((0, 1)),
        'std_gray': float(gray.std()),
        'center': center,
        'corner_mean': corners.mean(0),
        'radial_delta': float(np.abs(center - corners.mean(0)).mean()),
        'unique': len(np.unique(a.reshape(-1, 3).astype(np.uint8), axis=0)),
    }


def report(st):
    print(f'--- {os.path.basename(st["path"])}  {st["size"][0]}x{st["size"][1]}')
    m = st['mean']
    print(f'  mean RGB8 : [{m[0]:6.1f} {m[1]:6.1f} {m[2]:6.1f}]')
    s = st['std_rgb']
    print(f'  std  RGB8 : [{s[0]:6.2f} {s[1]:6.2f} {s[2]:6.2f}]   gray={st["std_gray"]:6.2f}')
    print(f'  center    : {st["center"].astype(int).tolist()}   '
          f'corner≈{st["corner_mean"].round(1).tolist()}')
    print(f'  radial Δ  : {st["radial_delta"]:6.2f}   unique={st["unique"]}')
    # 三档判读
    if st['std_gray'] < 1.0 and st['radial_delta'] < 1.0:
        print('  => 真常数：没出图，或整屏被同一种颜色覆盖')
    elif st['std_gray'] < 8.0:
        print('  => 极弱信号：可能只有一条缓慢斜坡（雾/渐变），物体本身没产生结构')
    else:
        print('  => 有结构')


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print('用法: python -m worldwright.tools.frame_stat <png> [png ...]')
        return 2
    for p in argv:
        if not os.path.exists(p):
            print(f'!! 找不到 {p}')
            continue
        report(stat(p))
    print('FRAME_STAT_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
