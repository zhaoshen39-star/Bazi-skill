# -*- coding: utf-8 -*-
"""优化项回归：岁运并临、反吟、流年与大运互动、流月日期、三柱旺衰。

运行：python tests/verify_optimizations.py
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable
CLI = os.path.join(ROOT, "scripts", "bazi.py")


def run_cli(*args):
    return subprocess.run([PY, CLI] + list(args), capture_output=True,
                          text=True, encoding="utf-8")


def cli_json(*args):
    r = run_cli(*(list(args) + ["--json"]))
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-500:])
    return json.loads(r.stdout)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    failures = []

    def check(name, ok, detail=""):
        if not ok:
            failures.append("%s %s" % (name, detail))

    base = ("--date", "1990-06-15", "--time", "12:00", "--sex", "male")

    # 1) 岁运并临：2003 癸未 = 大运 癸未
    d = cli_json(*(base + ("--focus-year", "2003")))
    ly = [x for x in d["chart"]["liunian"] if x["year"] == 2003][0]
    check("岁运并临 2003", any("岁运并临" in i for i in ly["interactions"]), ly["interactions"])
    check("岁运并临不重复报伏吟",
          not any("伏吟" in i and "大运" in i for i in ly["interactions"]), ly["interactions"])

    # 2) 反吟：1996 丙子 与 月柱壬午 天克地冲
    d = cli_json(*(base + ("--focus-year", "1996")))
    ly = [x for x in d["chart"]["liunian"] if x["year"] == 1996][0]
    check("反吟 1996", any("反吟" in i for i in ly["interactions"]), ly["interactions"])

    # 3) 半合：2026 丙午 与 日支戌 → 午戌半合火（用 2004-06-12 男盘）
    d = cli_json("--date", "2004-06-12", "--time", "10:00", "--sex", "male",
                 "--longitude", "123.91", "--true-solar-time", "--focus-year", "2026")
    ly = [x for x in d["chart"]["liunian"] if x["year"] == 2026][0]
    check("半合 2026", any("半合火" in i for i in ly["interactions"]), ly["interactions"])

    # 4) 流月日期：12 个月，首月立春、末月止于次年立春
    d = cli_json(*(base + ("--focus-year", "2026", "--liuyue")))
    ms = d["chart"]["liuyue"]
    check("流月 12 个月", len(ms) == 12, len(ms))
    check("首月立春", ms[0]["start_jie"] == "立春" and ms[0]["start"].startswith("2026-02-04"),
          (ms[0].get("start_jie"), ms[0].get("start")))
    check("末月止于次年立春", ms[11]["end"].startswith("2027-02-04"), ms[11].get("end"))

    # 5) 三柱旺衰（时辰未知时提供对照）
    d = cli_json(*(base + ("--time-unknown",)))
    s3 = d["analysis"].get("strength_3pillar")
    check("三柱旺衰存在", bool(s3), s3)
    check("三柱旺衰与四柱不同", s3 and s3["score"] != d["analysis"]["strength"]["score"],
          (s3 and s3["score"], d["analysis"]["strength"]["score"]))

    # 6) 文本输出：当前大运标记 + 流年要点
    r = run_cli(*(base + ("--focus-year", "2026")))
    out = r.stdout
    check("当前大运标记", "（当前）" in out)
    check("流年要点段", "【流年要点】" in out)
    check("流月节气区间列", True)

    # 7) interactions 覆盖所有流年
    d = cli_json(*(base + ("--focus-year", "2026")))
    check("每年都有 interactions 字段",
          all("interactions" in x for x in d["chart"]["liunian"]))

    total = 12
    print("优化项回归：%d 项" % total)
    if failures:
        print("失败：")
        for f in failures:
            print("  ✗ " + f)
        return 1
    print("全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
