# -*- coding: utf-8 -*-
"""参数热调 —— 改 `assets/params.json` 的 seed，区域就地重建。

为什么不用 Cordis Hmr
--------------------
`superengine/live.py` 的 Hmr 解决的是"**改源码**热替换 fiber"，
而这里要的是"**改参数**重建数据"。两件事：
- 改 seed：数据全变，必须重新生成 scene JSON（不是热替换）；
- 改 region 代码：那才需要 Hmr。

所以这里用最笨也最可靠的办法：**轮询 params.json 的 mtime，变了就重跑该 region**。
不引 watchdog（多一个依赖），500ms 轮询对"人手改文件"足够。

用法::

    python -m worldwright.dev --region r06          # 常驻监听
    python -m worldwright.dev --region r03 --seed 7  # 只重建一次
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS = os.path.join(_ROOT, 'assets', 'params.json')

REGIONS = {
    'r02': 'worldwright.regions.r02_terrain',
    'r03': 'worldwright.regions.r03_city',
    'r06': 'worldwright.regions.r06_cave',
}


def read_params():
    if not os.path.exists(PARAMS):
        return {}
    try:
        with open(PARAMS, encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}          # 半写入的文件直接忽略，下一轮再看


def build(region: str, seed: int) -> bool:
    """重建一个区域。返回是否成功。"""
    mod = REGIONS[region]
    t0 = time.time()
    r = subprocess.run([sys.executable, '-m', mod, '--seed', str(seed)],
                       cwd=_ROOT, capture_output=True, text=True)
    dt = time.time() - t0
    if r.returncode != 0:
        print(f'  !! {region} 失败（{dt:.1f}s）：{r.stderr.strip()[-200:]}')
        return False
    tail = [ln for ln in r.stdout.strip().splitlines() if ln.startswith('[')]
    print(f'  ok {region} seed={seed}（{dt:.1f}s）')
    for ln in tail[-2:]:
        print(f'     {ln}')
    return True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--region', default='r06', choices=sorted(REGIONS))
    ap.add_argument('--seed', type=int, default=None, help='只重建一次')
    ap.add_argument('--interval', type=float, default=0.5)
    args = ap.parse_args(argv)

    if args.seed is not None:
        return 0 if build(args.region, args.seed) else 1

    print(f'[dev] 监听 {PARAMS}（改 seed 即重建，Ctrl-C 退出）')
    last_mtime = None
    last_seed = None
    while True:
        try:
            mtime = os.path.getmtime(PARAMS) if os.path.exists(PARAMS) else None
            if mtime != last_mtime:
                last_mtime = mtime
                p = read_params()
                seed = int((p.get(args.region) or {}).get('seed', 0))
                if seed != last_seed:
                    last_seed = seed
                    build(args.region, seed)
        except KeyboardInterrupt:
            print('\n[dev] 退出')
            return 0
        except Exception as e:            # 轮询循环不该因为一次读失败就死
            print(f'[dev] 忽略：{type(e).__name__}: {e}')
        time.sleep(args.interval)


if __name__ == '__main__':
    sys.exit(main())
