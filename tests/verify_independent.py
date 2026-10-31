# -*- coding: utf-8 -*-
"""独立交叉校验：不依赖内置历法库，用儒略日公式与五鼠遁重算，再与排盘结果对照。

这是与 tests/verify.py 互补的第二条证据链：
  - verify.py 校验「固定基准值」；
  - 本脚本校验「实现 vs 独立公式」在任意抽样日期上的一致性。

运行：python tests/verify_independent.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import chart  # noqa: E402

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"


def jdn(y, m, d):
    """公历日期的儒略日数（Meeus Ch.7）。"""
    a = (14 - m) // 12
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    return d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045


def day_gz(y, m, d):
    i = (jdn(y, m, d) + 49) % 60
    return GAN[i % 10] + ZHI[i % 12]


def year_gz(y):
    i = (y - 4) % 60
    return GAN[i % 10] + ZHI[i % 12]


def hour_gz(day_gan, hour):
    zi = 0 if hour == 23 else ((hour + 1) // 2) % 12
    return GAN[(GAN.index(day_gan) % 5 * 2 + zi) % 10] + ZHI[zi]


CASES = [
    (1949, 10, 1, 15), (2000, 1, 1, 12), (2000, 1, 7, 12), (1990, 6, 15, 11),
    (2024, 2, 4, 16), (2024, 2, 4, 17), (1900, 1, 1, 10), (2023, 2, 4, 10),
    (2100, 6, 1, 8), (1988, 12, 31, 22), (2001, 7, 13, 3), (1969, 7, 20, 21),
]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    failures = []
    for (y, m, d, h) in CASES:
        c = chart.build(y, m, d, h, 0, 0, sex=None)
        got = [x["ganzhi"] for x in c["pillars"]]
        want_day = day_gz(y, m, d)          # 非 23 点，不需要换日
        want_hour = hour_gz(want_day[0], h)
        if got[2] != want_day:
            failures.append("%04d-%02d-%02d 日柱 期望 %s 实得 %s" % (y, m, d, want_day, got[2]))
        if got[3] != want_hour:
            failures.append("%04d-%02d-%02d 时柱 期望 %s 实得 %s" % (y, m, d, want_hour, got[3]))
        # 年柱只在远离立春（3–11 月）的样本上核对，避免交节时刻争议
        if 3 <= m <= 11 and got[0] != year_gz(y):
            failures.append("%04d-%02d-%02d 年柱 期望 %s 实得 %s" % (y, m, d, year_gz(y), got[0]))

    total = len(CASES) * 2
    print("独立公式校验：%d 个样本，%d 项日柱/时柱对比（另有年柱抽样）" % (len(CASES), total))
    if failures:
        print("失败：")
        for f in failures:
            print("  ✗ " + f)
        return 1
    print("全部一致 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
