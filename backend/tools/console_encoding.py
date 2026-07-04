"""
console_encoding.py — 统一解决 Windows GBK 控制台打印 emoji 崩溃

Windows 中文系统默认控制台编码是 GBK，项目里到处有打印 ✅❌⚠️等 emoji 的
print()，GBK 编不了这些字符会直接 UnicodeEncodeError 崩溃整个进程
（problem.md 第31条）。

之前的做法是在每个独立入口文件（server.py/_selftest.py）各自复制一份
"try: sys.stdout.reconfigure(...) except: pass"，新增入口（比如这次的
test_expert.py 新分支、C 的 run.py 自测块）没人记得照抄，同一类崩溃反复
出现。这里统一成一个函数，所有独立入口只需调用这一行，不用再记住复制
那五行代码。
"""

import sys


def ensure_utf8_console() -> None:
    """把 stdout/stderr 改成 UTF-8 编码，兜底 Windows 默认 GBK 打印 emoji 崩溃。

    在标准控制台上必然生效；stdout/stderr 被重定向成不支持 reconfigure 的流
    （比如某些测试框架捕获场景）时直接跳过——不影响功能，那种场景本来就
    不会在真实控制台上崩溃。
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
