# -*- coding: utf-8 -*-
"""格局与干支关系的定向单测（与排盘解耦，直接构造四柱）。

运行：python tests/verify_relations.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import analysis  # noqa: E402

PILLAR_NAMES = ["年柱", "月柱", "日柱", "时柱"]


def mk(gzs):
    return [{"gan": g[0], "zhi": g[1], "name": n} for g, n in zip(gzs, PILLAR_NAMES)]


RELATION_CASES = [
    # 四柱                        应包含的关系关键字
    (["甲子", "己丑", "丙寅", "丁卯"], ["天干合", "地支六合"]),
    (["甲子", "丙午", "戊辰", "庚申"], ["地支六冲"]),
    (["甲子", "乙未", "丙辰", "丁巳"], ["地支六害"]),
    (["甲子", "乙酉", "丙辰", "丁巳"], ["地支相破"]),
    (["甲午", "丙午", "戊辰", "庚申"], ["地支自刑"]),
    (["甲寅", "乙巳", "戊申", "庚申"], ["地支三刑"]),
    (["甲子", "丙申", "戊辰", "庚午"], ["地支三合"]),
]

# 不应出现自刑的样本（子子不是自刑，自刑仅辰午酉亥）
NO_SELF_XING = [["甲子", "丙子", "戊辰", "庚申"], ["甲戌", "丙戌", "戊寅", "庚申"]]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    failures = []

    for gzs, must in RELATION_CASES:
        rel = analysis.relations(mk(gzs))
        for key in must:
            if not any(key in r for r in rel):
                failures.append("%s 应含有「%s」，实得 %s" % (gzs, key, rel))

    for gzs in NO_SELF_XING:
        rel = analysis.relations(mk(gzs))
        if any("自刑" in r for r in rel):
            failures.append("%s 不应出现自刑，实得 %s" % (gzs, rel))

    # 格局：用真实日期验证（依赖排盘）
    import chart
    pattern_cases = [
        ((1995, 1, 20), "偏印格"),
        ((1984, 2, 20), "建禄格"),
        ((2024, 2, 4), "正财格"),
    ]
    for (y, m, d), expect in pattern_cases:
        c = chart.build(y, m, d, 12, 0, 0, sex=None)
        ge = analysis.pattern(c["pillars"], c["day_gan"])
        if ge["name"] != expect:
            failures.append("%04d-%02d-%02d 格局 期望 %s 实得 %s（%s/%s）" % (
                y, m, d, expect, ge["name"], ge["month_zhi"], ge["month_god"]))
        for t in ge["transparent"]:
            if t["pillar"] == "日柱":
                failures.append("%04d-%02d-%02d 透干不应包含日柱" % (y, m, d))

    total = sum(len(x[1]) for x in RELATION_CASES) + len(NO_SELF_XING) + len(pattern_cases)
    print("关系/格局单测：%d 项" % total)
    if failures:
        print("失败：")
        for f in failures:
            print("  ✗ " + f)
        return 1
    print("全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
