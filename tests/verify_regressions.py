# -*- coding: utf-8 -*-
"""审查修复回归：时区/真太阳时交节、农历 2/29-30、得势计数、戊己禄刃、输入校验。

这些用例对应独立审查报告中的 S1、M1、M2、M3 与部分 L 项。
运行：python tests/verify_regressions.py
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable
CLI = os.path.join(ROOT, "scripts", "bazi.py")

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analysis  # noqa: E402


def run_cli(*args):
    proc = subprocess.run([PY, CLI] + list(args), capture_output=True,
                          text=True, encoding="utf-8")
    return proc.returncode, proc.stdout, proc.stderr


def cli_json(*args):
    rc, out, err = run_cli(*(list(args) + ["--json"]))
    if rc != 0:
        raise RuntimeError("CLI 失败：%s\n%s" % (args, err[-500:]))
    return json.loads(out)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    failures = []

    def check(name, ok, detail=""):
        if not ok:
            failures.append("%s %s" % (name, detail))

    # ── S1：非 UTC+8 / 真太阳时的交节判定 ─────────────────────────────
    d = cli_json("--date", "2024-02-04", "--time", "12:00", "--sex", "female",
                 "--zone", "America/New_York")
    p = [x["ganzhi"] for x in d["chart"]["pillars"]]
    check("S1 纽约 2024-02-04 12:00 已过立春", p[:2] == ["甲辰", "丙寅"], p[:2])
    check("S1 纽约 2024 大运逆行", d["chart"]["dayun"]["forward"] is False)

    d = cli_json("--date", "1990-06-06", "--time", "00:30", "--sex", "male",
                 "--zone", "America/New_York")
    p = [x["ganzhi"] for x in d["chart"]["pillars"]]
    check("S1 纽约 1990-06-06 00:30 已过芒种", p[1] == "壬午", p[1])

    d = cli_json("--date", "1990-06-06", "--time", "07:00", "--sex", "male",
                 "--zone", "Asia/Tokyo")
    p = [x["ganzhi"] for x in d["chart"]["pillars"]]
    check("S1 东京 1990-06-06 07:00 未到芒种", p[1] == "辛巳", p[1])

    d = cli_json("--date", "2024-02-04", "--time", "18:00", "--sex", "female",
                 "--longitude", "87.62", "--true-solar-time")
    p = [x["ganzhi"] for x in d["chart"]["pillars"]]
    check("S1 乌鲁木齐真太阳时 已过立春", p[:2] == ["甲辰", "丙寅"], p[:2])
    check("S1 乌鲁木齐 大运逆行", d["chart"]["dayun"]["forward"] is False)

    # ── M1：农历 2 月 29/30 日 ───────────────────────────────────────
    d = cli_json("--date", "2023-02-29", "--lunar", "--time", "12:00", "--sex", "male")
    check("M1 农历 2023-02-29", d["input"]["lunar_input"]["solar"].startswith("2023-03-20"),
          d["input"]["lunar_input"]["solar"])
    d = cli_json("--date", "2024-02-30", "--lunar", "--time", "12:00", "--sex", "male")
    check("M1 农历 2024-02-30", d["input"]["lunar_input"]["solar"].startswith("2024-04-08"),
          d["input"]["lunar_input"]["solar"])

    # ── M2：得势不把日主算作同党 ──────────────────────────────────────
    d = cli_json("--date", "2024-04-07", "--time", "12:00", "--sex", "male")
    st = d["analysis"]["strength"]
    check("M2 2024-04-07 天干同党=1", st["de_shi_heads"] == 1, st["de_shi_heads"])
    check("M2 2024-04-07 偏强", st["label"] == "偏强", (st["label"], st["score"]))

    # ── M3：戊/己 的禄刃月 ───────────────────────────────────────────
    m3 = [("2024-05-14", "建禄格"), ("2024-06-13", "月劫格（阳刃格）"),
          ("2024-05-05", "月劫格（阳刃格）"), ("2024-06-14", "建禄格")]
    for date, want in m3:
        d = cli_json("--date", date, "--time", "12:00")
        got = d["analysis"]["pattern"]["name"]
        check("M3 %s → %s" % (date, want), got == want, got)

    # ── L6：夏令时不存在/歧义时间 ─────────────────────────────────────
    d = cli_json("--date", "1986-05-04", "--time", "02:30", "--sex", "male")
    check("L6 跳过区间有警告",
          any("跳过区间" in w for w in d["warnings"]), d["warnings"])
    d = cli_json("--date", "1986-09-14", "--time", "01:30", "--sex", "male")
    check("L6 歧义时间有警告",
          any("歧义" in w for w in d["warnings"]), d["warnings"])

    # ── L7：子卯应标「相刑」而非「三刑」 ─────────────────────────────
    pillars = [{"gan": g, "zhi": z, "name": n}
               for g, z, n in [("甲", "子", "年柱"), ("丙", "卯", "月柱"),
                               ("戊", "辰", "日柱"), ("庚", "申", "时柱")]]
    rel = analysis.relations(pillars)
    check("L7 子卯标为相刑", any(r.startswith("地支相刑：子卯") for r in rel), rel)
    check("L7 子卯不标三刑", not any("三刑：子卯" in r for r in rel), rel)

    # ── L2/L4/L3/L5：CLI 提示与校验 ──────────────────────────────────
    d = cli_json("--date", "2024-02-04", "--time", "15:00", "--time-unknown")
    check("L2 时辰未知警告用实际时间",
          any("15:00:00" in w for w in d["warnings"]), d["warnings"])
    check("L2 时柱标记不可靠", d["chart"]["time_pillar_reliable"] is False)
    d = cli_json("--date", "1990-06-15", "--time", "12:00")
    check("L4 缺性别有警告", any("未提供性别" in w for w in d["warnings"]), d["warnings"])
    rc, _, _ = run_cli("--date", "1990-06-15", "--time", "12:00",
                       "--sex", "male", "--dayun-count", "0")
    check("L3 dayun-count<1 报错", rc != 0)
    rc, _, _ = run_cli("--date", "1990-06-15", "--time", "12:00",
                       "--longitude", "200", "--true-solar-time")
    check("L5 经度越界报错", rc != 0)

    total = 22
    print("回归用例：%d 项" % total)
    if failures:
        print("失败：")
        for f in failures:
            print("  ✗ " + f)
        return 1
    print("全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
