# -*- coding: utf-8 -*-
"""能力注册表 —— 每个能力必须包装一个**真实存在的引擎模块**。

三条自检（根除过去反复踩的"静默没接上"）：
1. `module` import 不到 → 注册时直接抛异常；
2. 场景依赖了某能力，但该能力的 `stats()['calls'] == 0` → 渲染时报错；
3. `produces` 槽位无人消费 → 警告。

这个文件是 M0 的核心。没有它，后面的"接入"会重蹈"看起来接了、其实没跑"的覆辙。
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field


@dataclass
class Capability:
    name: str                 # 'csm'
    module: str               # 'world3d.engine.csm'（必须存在）
    produces: str             # 'shadow_map'（进管线哪个槽位）
    calls: int = 0
    last_t: float = -1.0
    meta: dict = field(default_factory=dict)

    def touch(self, t: float):
        self.calls += 1
        self.last_t = float(t)

    def stats(self) -> dict:
        return {'name': self.name, 'module': self.module,
                'produces': self.produces, 'calls': self.calls,
                'last_t': self.last_t}


class Registry:
    def __init__(self):
        self._caps: dict[str, Capability] = {}

    def register(self, name, module, produces):
        """注册并**立即验证模块可导入** —— 失败就炸，不留到运行时。"""
        importlib.import_module(module)          # 不存在则 ImportError
        cap = Capability(name=name, module=module, produces=produces)
        self._caps[name] = cap
        return cap

    def get(self, name) -> Capability:
        return self._caps[name]

    def require(self, names, t):
        """场景声明依赖后调用：没有任何调用记录就报错。"""
        dead = [n for n in names if n in self._caps and self._caps[n].calls == 0]
        if dead:
            raise RuntimeError(f'场景声明依赖这些能力，但它们一次都没被调用: {dead}')

    def report(self) -> list[dict]:
        return sorted((c.stats() for c in self._caps.values()),
                      key=lambda d: d['name'])

    def unwired(self, all_modules):
        """返回"还没接"的模块（用于 README 的 94 行达标表）。"""
        wired = {c.module for c in self._caps.values()}
        return [m for m in all_modules if m not in wired]
