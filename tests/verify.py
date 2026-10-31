# -*- coding: utf-8 -*-
"""回归校验：四柱、晚子时流派、节气边界、夏令时还原、节气时刻精度。

运行：
  python tests/verify.py
退出码 0 表示全部通过。
"""

import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(SKILL, "scripts"))

import bazi  # noqa: E402
import chart  # noqa: E402
from lunar_python import Solar  # noqa: E402


def _pillars(date_s, time_s, zone, sect=2):
    d = datetime.strptime(date_s, "%Y-%m-%d")
    t = datetime.strptime(time_s, "%H:%M:%S" if time_s.count(":") == 2 else "%H:%M")
    r = bazi.resolve_time(d.year, d.month, d.day, t.hour, t.minute, t.second,
                          zone, None, False)
    used = r["used_dt"]
    c = chart.build(used.year, used.month, used.day, used.hour, used.minute,
                    used.second, sect=sect, sex=None)
    return {k: c["pillars"][i]["ganzhi"] for i, k in enumerate(("year", "month", "day", "time"))}, r, c


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    with open(os.path.join(HERE, "fixtures.json"), encoding="utf-8") as f:
        fx = json.load(f)

    failures = []
    passed = 0

    def check(name, ok, detail=""):
        nonlocal passed
        if ok:
            passed += 1
        else:
            failures.append("%s %s" % (name, detail))

    # 1) 四柱基准
    for case in fx["charts"]:
        got, r, _ = _pillars(case["date"], case["time"], case["zone"])
        for key, want in case["expected"].items():
            check("[四柱] %s %s" % (case["id"], key), got[key] == want,
                  "期望 %s 实得 %s" % (want, got[key]))
        if case.get("expected_standard"):
            check("[夏令时] %s" % case["id"],
                  r["standard"] == case["expected_standard"],
                  "期望 %s 实得 %s" % (case["expected_standard"], r["standard"]))

    # 2) 晚子时流派
    for case in fx["zi_hour"]:
        got, _, _ = _pillars(case["date"], case["time"], "Asia/Shanghai", sect=case["sect"])
        for key, want in case["expected"].items():
            check("[子时 sect%d] %s %s" % (case["sect"], case["id"], key),
                  got[key] == want, "期望 %s 实得 %s" % (want, got[key]))

    # 3) 节气边界
    for case in fx["jie_boundary"]:
        got, _, _ = _pillars(case["date"], case["time"], case["zone"])
        for key, want in case["expected"].items():
            check("[节气边界] %s %s" % (case["id"], key), got[key] == want,
                  "期望 %s 实得 %s" % (want, got[key]))

    # 4) 节气时刻精度（对照外部历书；按节气所在月份选探测日，避免跨年别名）
    TERM_MONTH = {
        "小寒": 1, "大寒": 1, "立春": 2, "雨水": 2, "惊蛰": 3, "春分": 3,
        "清明": 4, "谷雨": 4, "立夏": 5, "小满": 5, "芒种": 6, "夏至": 6,
        "小暑": 7, "大暑": 7, "立秋": 8, "处暑": 8, "白露": 9, "秋分": 9,
        "寒露": 10, "霜降": 10, "立冬": 11, "小雪": 11, "大雪": 12, "冬至": 12,
    }
    TERM_ALIAS = {
        "小寒": "XIAO_HAN", "大寒": "DA_HAN", "立春": "LI_CHUN", "雨水": "YU_SHUI",
        "惊蛰": "JING_ZHE", "春分": "CHUN_FEN", "清明": "QING_MING", "谷雨": "GU_YU",
        "立夏": "LI_XIA", "小满": "XIAO_MAN", "芒种": "MANG_ZHONG", "夏至": "XIA_ZHI",
        "小暑": "XIAO_SHU", "大暑": "DA_SHU", "立秋": "LI_QIU", "处暑": "CHU_SHU",
        "白露": "BAI_LU", "秋分": "QIU_FEN", "寒露": "HAN_LU", "霜降": "SHUANG_JIANG",
        "立冬": "LI_DONG", "小雪": "XIAO_XUE", "大雪": "DA_XUE", "冬至": "DONG_ZHI",
    }
    for term in fx["solar_terms"]:
        probe = Solar.fromYmd(term["year"], TERM_MONTH.get(term["name"], 6), 15)
        table = probe.getLunar().getJieQiTable()
        entry = table.get(term["name"])
        if entry is None or entry.getYear() != term["year"]:
            entry = None
            alias = TERM_ALIAS.get(term["name"])
            for _k, v in table.items():
                if v.getYear() == term["year"] and _k in (term["name"], alias):
                    entry = v
                    break
        if entry is None:
            failures.append("[节气] %s %s 未在节气表中找到" % (term["year"], term["name"]))
            continue
        got = entry.toYmdHms()
        official = term["official"]
        delta = abs((datetime.strptime(got, "%Y-%m-%d %H:%M:%S")
                     - datetime.strptime(official, "%Y-%m-%d %H:%M:%S")).total_seconds())
        check("[节气] %s %s" % (term["year"], term["name"]),
              delta <= term["tolerance_seconds"],
              "官方 %s / 实算 %s，差 %.0f 秒" % (official, got, delta))

    # 5) 大运方向与起运
    c = chart.build(1990, 6, 15, 11, 0, 0, sex=1)
    dy = c["dayun"]
    check("[大运] 阳年男顺行", dy["forward"] is True, str(dy["forward"]))
    check("[大运] 首运为癸未", dy["list"][0]["ganzhi"] == "癸未", dy["list"][0]["ganzhi"])
    check("[大运] 起运年龄合理", 6 <= dy["start"]["year"] <= 9, str(dy["start"]))

    # 6) 农历换算（含闰月）
    sy, sm, sd, _, _, _ = chart.lunar_to_solar(1990, 5, 23)
    check("[农历] 1990 年五月廿三 = 1990-06-15", (sy, sm, sd) == (1990, 6, 15),
          "实得 %04d-%02d-%02d" % (sy, sm, sd))
    sy2, sm2, sd2, _, _, _ = chart.lunar_to_solar(2023, -2, 1)
    back = Solar.fromYmd(sy2, sm2, sd2).getLunar()
    check("[农历] 闰月往返一致", back.getMonth() == -2 and back.getDay() == 1,
          "闰二月初一 -> %04d-%02d-%02d -> 月%d 日%d" % (sy2, sm2, sd2, back.getMonth(), back.getDay()))

    total = passed + len(failures)
    print("通过 %d / %d" % (passed, total))
    if failures:
        print("\n失败项：")
        for f in failures:
            print("  ✗ " + f)
        return 1
    print("全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
