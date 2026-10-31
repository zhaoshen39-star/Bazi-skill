# -*- coding: utf-8 -*-
"""数字学层（numerology）回归：归约规则、主数保留、时间口径、九宫格、姓名、
个人周期、结构与序列化、独立 CLI 契约、真实 bazi.py 报告联调、边界。

运行：python tests/verify_numerology.py
"""

import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable
CLI = os.path.join(ROOT, "scripts", "numerology.py")
BAZI = os.path.join(ROOT, "scripts", "bazi.py")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import numerology as num  # noqa: E402

failures = []
total = 0


def check(name, ok, detail=""):
    global total
    total += 1
    if not ok:
        failures.append("%s %s" % (name, detail))


def run(args, cli=CLI):
    return subprocess.run([PY, cli] + list(args), capture_output=True,
                          text=True, encoding="utf-8")


def cli_json(*args):
    r = run(list(args) + ["--json"])
    if r.returncode != 0:
        raise SystemExit("numerology CLI 失败：%r\n%s" % (args, r.stderr[-800:]))
    return json.loads(r.stdout)


def bazi_json(*args):
    r = run(list(args) + ["--json"], cli=BAZI)
    if r.returncode != 0:
        raise SystemExit("bazi CLI 失败：%r\n%s" % (args, r.stderr[-800:]))
    return json.loads(r.stdout)


AS_OF = "2026-10-29"


def report_of(date, time="12:00:00", focus_year=2026, name=None, strokes=None,
              used=None, with_time=True):
    """构造与 bazi.build_report() 同形状的最小 report。"""
    rep = {
        "input": {"date": date, "sex": "male", "zone": "Asia/Shanghai"},
        "focus_year": focus_year,
    }
    if with_time:
        rep["input"]["time"] = time
        rep["time"] = {
            "used": used if used is not None else "%s %s" % (date, time),
            "used_label": "标准时",
            "used_kind": "standard",
        }
    if name is not None:
        rep["input"]["name"] = name
    if strokes is not None:
        rep["input"]["strokes"] = strokes
    return rep


def numerology(date, **kwargs):
    as_of = kwargs.pop("as_of", AS_OF)
    return num.numerology(report_of(date, **kwargs), as_of=as_of)


def life_path_of(date, **kwargs):
    return numerology(date, **kwargs)["life_path"]


def main():
    # ══ 一、归约与主数 ═══════════════════════════════════════════════════
    check("A1 归约 15 → 6", num._reduce_chain(15) == (6, [15, 6]))
    check("A2 归约 29 → 11 主数保留", num._reduce_chain(29) == (11, [29, 11]))
    check("A3 归约 1990 链式", num._reduce_chain(1990) == (1, [1990, 19, 10, 1]))
    check("A4 归约 11 原样", num._reduce_chain(11) == (11, [11]))
    check("A5 归约 22 原样", num._reduce_chain(22) == (22, [22]))
    check("A6 归约 33 原样", num._reduce_chain(33) == (33, [33]))
    check("A7 归约 47 → 11 主数", num._reduce_chain(47) == (11, [47, 11]))
    check("A8 归约 9 原样", num._reduce_chain(9) == (9, [9]))
    check("A9 归约 0 原样", num._reduce_chain(0) == (0, [0]))
    check("A10 _reduce(10) = 1", num._reduce(10) == 1)
    check("A11 _reduce(2027) = 11 主数", num._reduce(2027) == 11)

    try:
        num._reduce_chain(-5)
        check("A12 负数抛 ValueError", False, "未抛异常")
    except ValueError:
        check("A12 负数抛 ValueError", True)

    try:
        num._reduce_chain("15")
        check("A13 非整数抛 TypeError", False, "未抛异常")
    except TypeError:
        check("A13 非整数抛 TypeError", True)

    try:
        num._reduce_chain(True)
        check("A14 bool 抛 TypeError", False, "未抛异常")
    except TypeError:
        check("A14 bool 抛 TypeError", True)

    check("A15 MASTERS = (11, 22, 33)", num.MASTERS == (11, 22, 33))
    check("A16 含义表覆盖 12 个数字",
          set(num.NUMBER_MEANINGS) == set(range(1, 10)) | {11, 22, 33})
    full = all(
        len(num.NUMBER_MEANINGS[k][f]) >= 2
        for k in num.NUMBER_MEANINGS
        for f in ("personality", "strengths", "weaknesses", "directions"))
    check("A17 每个数字关键词 ≥2 条", full)
    masters_ok = all(num.NUMBER_MEANINGS[k]["is_master"] and
                     num.NUMBER_MEANINGS[k]["root"] == r
                     for k, r in ((11, 2), (22, 4), (33, 6)))
    check("A18 主数含义与根数字", masters_ok)
    check("A19 主数关键词标记", "主数" in num._keywords(11))

    # ══ 二、生命灵数 ═════════════════════════════════════════════════════
    lp = life_path_of("2004-06-12")
    check("B1 2004-06-12 生命灵数 6",
          lp["number"] == 6 and lp["chain"] == [15, 6] and not lp["is_master"])
    check("B2 2004-06-12 逐位数字保留 0",
          lp["digits"] == [2, 0, 0, 4, 0, 6, 1, 2] and lp["raw_sum"] == 15)
    check("B3 生命灵数 keyword 非空", len(lp["keywords"]) >= 2)
    lp = life_path_of("1980-11-29")
    check("B4 1980-11-29 是 4 不是主数",
          lp["number"] == 4 and lp["chain"] == [31, 4] and not lp["is_master"])
    lp = life_path_of("2000-03-15")
    check("B5 2000-03-15 生命灵数 11 主数",
          lp["number"] == 11 and lp["is_master"] and lp["chain"] == [11])
    lp = life_path_of("1980-11-09")
    check("B6 1980-11-09 归约链含 11",
          lp["number"] == 11 and lp["chain"] == [29, 11])
    lp = life_path_of("1990-11-01")
    check("B7 1990-11-01 生命灵数 22", lp["number"] == 22 and lp["is_master"])
    lp = life_path_of("1998-12-03")
    check("B8 1998-12-03 生命灵数 33", lp["number"] == 33 and lp["is_master"])
    check("B9 2000-01-01 生命灵数 4", life_path_of("2000-01-01")["number"] == 4)
    check("B10 1999-12-31 生命灵数 8", life_path_of("1999-12-31")["number"] == 8)
    check("B11 2024-02-29 生命灵数 3", life_path_of("2024-02-29")["number"] == 3)
    lp = life_path_of("2004-02-29")
    check("B12 2004-02-29 生命灵数 1", lp["number"] == 1 and lp["chain"] == [19, 10, 1])
    check("B13 2004-12-31 生命灵数 4", life_path_of("2004-12-31")["number"] == 4)
    lp = life_path_of("2000-02-29")
    check("B14 2000-02-29 生命灵数 6", lp["number"] == 6 and lp["chain"] == [15, 6])
    lp = life_path_of("1999-09-09")
    check("B15 1999-09-09 生命灵数 1", lp["number"] == 1 and lp["chain"] == [46, 10, 1])
    check("B16 2024-01-01 生命灵数 1",
          life_path_of("2024-01-01")["chain"] == [10, 1])
    check("B17 1900-02-19 生命灵数 22", life_path_of("1900-02-19")["number"] == 22)
    check("B18 1900-09-19 生命灵数 11", life_path_of("1900-09-19")["number"] == 11)
    check("B19 1904-09-19 生命灵数 33", life_path_of("1904-09-19")["number"] == 33)
    lp = life_path_of("2000-03-15")
    check("B20 主数关键词含「主数」", lp["keywords"][0] == "主数")
    check("B21 主数标题含启发者", "启发者" in lp["title"])

    # ══ 三、输入口径（与八字排盘一致）═══════════════════════════════════
    real = bazi_json("--date", "2004-06-12", "--time", "10:00", "--sex", "male",
                     "--focus-year", "2026")
    check("C1 真实 bazi 报告 time.used 存在", bool(real.get("time", {}).get("used")))
    data = num.numerology(real, as_of=AS_OF)
    check("C2 used 时间被采用",
          data["input"]["used_time"] == real["time"]["used"],
          "got %r" % (data["input"]["used_time"],))
    check("C3 date_source = time.used", data["input"]["date_source"] == "time.used")
    check("C4 采用日期来自 used",
          data["input"]["birth_date"] == real["time"]["used"][:10])
    check("C5 真实报告聚焦年", data["input"]["focus_year"] == 2026 and
          data["personal"]["focus_year"] == 2026)
    check("C6 真实报告生命灵数 6", data["life_path"]["number"] == 6)

    tst_report = bazi_json("--date", "2004-06-12", "--time", "23:50",
                           "--true-solar-time", "--longitude", "123.96",
                           "--focus-year", "2026")
    used = tst_report["time"]["used"]
    check("C7 真太阳时跨日（八字侧）", used.startswith("2004-06-13"), used)
    tst_data = num.numerology(tst_report, as_of=AS_OF)
    check("C8 真太阳时跨日跟随 used 日期",
          tst_data["input"]["birth_date"] == "2004-06-13"
          and tst_data["input"]["civil_date"] == "2004-06-12")
    check("C9 跨日生命灵数 = 7", tst_data["life_path"]["number"] == 7,
          repr(tst_data["life_path"]["number"]))
    check("C10 跨日 date_note 非空", bool(tst_data["input"]["date_note"]))
    check("C11 used_label 真太阳时", tst_data["input"]["time_label"] == "真太阳时")

    j = cli_json("--date", "2004-06-12", "--time", "23:50", "--true-solar-time",
                 "--longitude", "123.96", "--focus-year", "2026", "--as-of", AS_OF)
    check("C12 模块 CLI 真太阳时跨日",
          j["input"]["birth_date"] == "2004-06-13" and j["life_path"]["number"] == 7)
    check("C13 模块 CLI used_kind = tst", j["input"]["used_kind"] == "tst")

    fallback = num.numerology(report_of("2004-06-13", with_time=False), as_of=AS_OF)
    check("C14 无 time.used 回退 input.date",
          fallback["input"]["date_source"] == "input.date"
          and fallback["input"]["birth_date"] == "2004-06-13"
          and fallback["input"]["birth_time"] == "00:00:00")

    bad_used = report_of("2004-06-13")
    bad_used["time"]["used"] = "not-a-datetime"
    fb2 = num.numerology(bad_used, as_of=AS_OF)
    check("C15 used 非法回退 input.date+time",
          fb2["input"]["date_source"] == "input.date+input.time"
          and fb2["input"]["birth_time"] == "12:00:00")

    try:
        num.numerology({"input": {"sex": "male"}}, as_of=AS_OF)
        check("C16 缺日期抛 ValueError", False, "未抛异常")
    except ValueError:
        check("C16 缺日期抛 ValueError", True)

    try:
        num.numerology(["not", "dict"])
        check("C17 report 非 dict 抛 TypeError", False, "未抛异常")
    except TypeError:
        check("C17 report 非 dict 抛 TypeError", True)

    rep = report_of("2004-06-12", focus_year=2025)
    check("C18 聚焦年取自 report",
          num.numerology(rep, as_of=AS_OF)["input"]["focus_year"] == 2025)

    rep = report_of("2004-06-12")
    rep.pop("focus_year")
    rep["chart"] = {"liunian": [{"year": 2027}, {"year": 2026, "is_focus": True}]}
    check("C19 聚焦年回退 chart.liunian.is_focus",
          num.numerology(rep, as_of=AS_OF)["input"]["focus_year"] == 2026)

    rep = report_of("2004-06-12")
    rep.pop("focus_year")
    check("C20 聚焦年回退参考日期年份",
          num.numerology(rep, as_of="2031-05-06")["input"]["focus_year"] == 2031)

    rep = report_of("2004-06-12", focus_year="abc")
    try:
        num.numerology(rep, as_of=AS_OF)
        check("C21 非法 focus_year 抛 ValueError", False, "未抛异常")
    except ValueError:
        check("C21 非法 focus_year 抛 ValueError", True)

    rep = report_of("2004-06-12", focus_year=10000)
    try:
        num.numerology(rep, as_of=AS_OF)
        check("C22 越界 focus_year 抛 ValueError", False, "未抛异常")
    except ValueError:
        check("C22 越界 focus_year 抛 ValueError", True)

    rep = report_of("2004-06-12", name="John Smith")
    data = num.numerology(rep, as_of=AS_OF)
    check("C23 姓名回退 report.input.name",
          data["input"]["name"] == "John Smith" and
          data["name"]["expression"]["number"] == 8)

    rep = report_of("2004-06-12", name="张伟", strokes=[7, 6])
    data = num.numerology(rep, as_of=AS_OF)
    check("C24 笔画回退 report.input.strokes",
          data["name"]["five_grid"] is not None and
          data["name"]["five_grid"]["tian"]["raw"] == 8)

    check("C25 as_of 接受 date 对象",
          num.numerology(rep, as_of=datetime.date(2026, 10, 29))
          ["personal"]["reference_date"] == AS_OF)
    check("C26 as_of 接受 datetime 对象",
          num.numerology(rep, as_of=datetime.datetime(2026, 10, 29, 8, 0))
          ["personal"]["reference_date"] == AS_OF)

    # ══ 四、生日数与态度数 ═══════════════════════════════════════════════
    d = numerology("2004-06-12")
    check("D1 生日数 12 → 3",
          d["birthday"]["number"] == 3 and d["birthday"]["chain"] == [12, 3]
          and d["birthday"]["day"] == 12)
    check("D2 生日数 29 → 11 主数",
          numerology("1980-11-29")["birthday"]["number"] == 11 and
          numerology("1980-11-29")["birthday"]["is_master"])
    check("D3 生日数 22 → 22 主数",
          numerology("1990-11-22")["birthday"]["number"] == 22)
    check("D4 生日数 31 → 4",
          numerology("2004-12-31")["birthday"]["chain"] == [31, 4])
    check("D5 生日数 1", numerology("2000-01-01")["birthday"]["number"] == 1)
    check("D6 态度数 6+12=18 → 9",
          d["attitude"]["number"] == 9 and d["attitude"]["chain"] == [18, 9]
          and d["attitude"]["raw_sum"] == 18)
    check("D7 态度数 11+22=33 主数",
          numerology("1990-11-22")["attitude"]["number"] == 33)
    check("D8 态度数 11+11=22 主数",
          numerology("1980-11-11")["attitude"]["number"] == 22)
    check("D9 态度数 12+31=43 → 7",
          numerology("1999-12-31")["attitude"]["chain"] == [43, 7])
    check("D10 态度数 1+1=2",
          numerology("2000-01-01")["attitude"]["number"] == 2)
    check("D11 态度数 2+29=31 → 4",
          numerology("2004-02-29")["attitude"]["number"] == 4)
    check("D12 态度数 note 含归约链", "→" in d["attitude"]["note"])

    # ══ 五、个人周期 ═════════════════════════════════════════════════════
    p = numerology("2004-06-12", focus_year=2026, as_of="2026-10-29")["personal"]
    check("E1 个人年 2026 → 1",
          p["year"] == 1 and p["year_chain"] == [10, 1] and not p["year_is_master"])
    check("E2 个人月 = 11 主数",
          p["month"] == 11 and p["month_chain"] == [11] and p["month_is_master"])
    check("E3 个人日 = 4",
          p["day"] == 4 and p["day_chain"] == [40, 4])
    check("E4 参考日期与聚焦年回填",
          p["reference_date"] == "2026-10-29" and p["focus_year"] == 2026)
    check("E5 分量归约正确",
          p["components"] == {"month": 6, "day": 3, "year": 1},
          repr(p["components"]))

    p = numerology("2004-06-12", focus_year=2025, as_of="2025-10-29")["personal"]
    check("E6 2025 个人年 9 / 月 1 / 日 3",
          p["year"] == 9 and p["month"] == 1 and p["month_chain"] == [19, 10, 1]
          and p["day"] == 3 and p["day_chain"] == [30, 3])

    p = numerology("2004-06-12", focus_year=2027, as_of="2027-10-29")["personal"]
    check("E7 2027 分量年归约为主数 11",
          p["components"]["year"] == 11 and p["year"] == 2
          and p["year_chain"] == [20, 2])
    check("E8 2027 个人月 3 / 日 5",
          p["month"] == 3 and p["day"] == 5 and p["day_chain"] == [32, 5])

    p = numerology("1990-02-03", focus_year=2022, as_of="2022-10-29")["personal"]
    check("E9 1990-02-03 个人年 11 主数",
          p["year"] == 11 and p["year_is_master"] and p["year_chain"] == [11])

    p = numerology("2004-06-12", focus_year=2026, as_of="2026-01-01")["personal"]
    check("E10 参考 1 月：月 2 / 日 3", p["month"] == 2 and p["day"] == 3)
    p = numerology("2004-06-12", focus_year=2026, as_of="2026-12-31")["personal"]
    check("E11 参考 12 月：月 4 / 日 8", p["month"] == 4 and p["day"] == 8)

    p = numerology("2004-11-11", focus_year=2026, as_of="2026-10-29")["personal"]
    check("E12 2004-11-11 个人年 5 / 月 6 / 日 8",
          p["year"] == 5 and p["year_chain"] == [23, 5]
          and p["month"] == 6 and p["month_chain"] == [15, 6] and p["day"] == 8)
    check("E13 2031 个人年 6",
          numerology("2004-06-12", focus_year=2031,
                     as_of="2031-10-29")["personal"]["year"] == 6)
    check("E14 2009 分量年 11 → 个人年 2",
          numerology("2004-06-12", focus_year=2009,
                     as_of="2009-10-29")["personal"]["year"] == 2)

    d = numerology("2004-06-12", focus_year=2026)
    check("E15 input.focus_year 与 personal 一致",
          d["input"]["focus_year"] == d["personal"]["focus_year"] == 2026)
    check("E16 默认参考日期为今天",
          num.numerology(report_of("2004-06-12"))["personal"]["reference_date"]
          == datetime.date.today().isoformat())

    # ══ 六、九宫格（Lo Shu）══════════════════════════════════════════════
    g = numerology("2004-06-12")["grid"]
    check("F1 洛书布局", g["layout"] == [[4, 9, 2], [3, 5, 7], [8, 1, 6]])
    check("F2 九格数字齐全", len(g["cells"]) == 9 and
          [c["number"] for c in g["cells"]] == list(range(1, 10)))
    check("F3 行列坐标与布局一致",
          all((c["row"], c["col"]) == num.LO_SHU_POS[c["number"]] for c in g["cells"]))
    check("F4 缺失 [3,5,7,8,9]", g["missing"] == [3, 5, 7, 8, 9], repr(g["missing"]))
    check("F5 重复 2×2",
          [{"number": r["number"], "count": r["count"]} for r in g["repeats"]]
          == [{"number": 2, "count": 2}])
    check("F6 连线 8 条", len(g["lines"]) == 8 and g["total_lines"] == 8)
    check("F7 2004-06-12 无成线", g["formed_count"] == 0)
    check("F8 出生日期逐位保留 0", g["digits"] == [2, 0, 0, 4, 0, 6, 1, 2])
    check("F9 counts 合计 = 非零数字数",
          sum(g["counts"].values()) == 5, repr(sum(g["counts"].values())))
    check("F10 missing_detail 与 missing 对齐",
          len(g["missing_detail"]) == len(g["missing"]) and
          all(item["meaning"] for item in g["missing_detail"]))

    g = numerology("1984-05-23")["grid"]
    formed = [ln["name"] for ln in g["lines"] if ln["formed"]]
    check("F11 1984-05-23 缺失 [6,7]", g["missing"] == [6, 7])
    check("F12 1984-05-23 成线 4 条", g["formed_count"] == 4, repr(formed))
    check("F13 成线列表正确",
          formed == ["4-9-2", "4-3-8", "9-5-1", "2-5-8"], repr(formed))
    check("F14 成线含义非空",
          all(ln["meaning"] and not ln["missing_numbers"]
              for ln in g["lines"] if ln["formed"]))

    g = numerology("2000-01-01")["grid"]
    check("F15 2000-01-01 缺 7 格", g["missing"] == [3, 4, 5, 6, 7, 8, 9])
    check("F16 2000-01-01 重复 1×2",
          [r["count"] for r in g["repeats"] if r["number"] == 1] == [2])

    g = numerology("1919-11-19")["grid"]
    rep_counts = {r["number"]: r["count"] for r in g["repeats"]}
    check("F17 1919-11-19 重复 1×5、9×3",
          rep_counts.get(1) == 5 and rep_counts.get(9) == 3, repr(rep_counts))
    check("F18 1919-11-19 缺 2–8",
          g["missing"] == [2, 3, 4, 5, 6, 7, 8], repr(g["missing"]))

    g = numerology("2024-02-29")["grid"]
    check("F19 2024-02-29 重复 2×4",
          [r["count"] for r in g["repeats"] if r["number"] == 2] == [4])
    check("F20 2024-02-29 成线 4-9-2",
          [ln["name"] for ln in g["lines"] if ln["formed"]] == ["4-9-2"])

    g = numerology("1987-11-25")["grid"]
    check("F21 1987-11-25 成线 9-5-1 与 2-5-8",
          [ln["name"] for ln in g["lines"] if ln["formed"]] == ["9-5-1", "2-5-8"])

    # ══ 七、姓名数字 ═════════════════════════════════════════════════════
    d = num.numerology(report_of("2004-06-12"), as_of=AS_OF)
    check("G1 无姓名 provided False",
          d["name"]["provided"] is False and d["name"]["available"] is False)
    check("G2 无姓名成熟数不可算", d["maturity"]["available"] is False)

    d = numerology("2004-06-12", name="John Smith")
    nm = d["name"]
    check("G3 John Smith 表达数 8",
          nm["expression"]["number"] == 8 and nm["expression"]["chain"] == [116, 8]
          and nm["expression"]["total"] == 116)
    check("G4 John Smith 灵魂数 6",
          nm["soul_urge"]["number"] == 6 and nm["soul_urge"]["chain"] == [24, 6]
          and nm["soul_urge"]["letters"] == "OI")
    check("G5 John Smith 人格数 11 主数",
          nm["personality"]["number"] == 11 and nm["personality"]["is_master"]
          and nm["personality"]["chain"] == [92, 11])
    check("G6 主数人格关键词含主数", nm["personality"]["keywords"][0] == "主数")
    check("G7 拉丁名可用且 script 正确",
          nm["name_supported"] is True and nm["script"] == "latin"
          and nm["available"] is True)

    lower = numerology("2004-06-12", name="john smith")["name"]
    check("G8 大小写不敏感",
          lower["expression"]["number"] == 8 and lower["personality"]["number"] == 11)
    padded = numerology("2004-06-12", name="  John Smith  ")["name"]
    check("G9 首尾空格忽略",
          padded["name"] == "John Smith" and padded["expression"]["number"] == 8)

    nm = numerology("2004-06-12", name="Lynn")["name"]
    check("G10 Lynn 表达数 11 主数",
          nm["expression"]["number"] == 11 and nm["expression"]["chain"] == [65, 11])
    check("G11 Lynn 灵魂数 7（Y 作元音）",
          nm["soul_urge"]["number"] == 7 and nm["soul_urge"]["chain"] == [25, 7])
    check("G12 Lynn 人格数 4",
          nm["personality"]["number"] == 4 and nm["personality"]["chain"] == [40, 4])

    nm = numerology("2004-06-12", name="Yvonne")["name"]
    check("G13 Yvonne 表达数 5",
          nm["expression"]["number"] == 5 and nm["expression"]["chain"] == [95, 14, 5])
    check("G14 Yvonne 灵魂数 2", nm["soul_urge"]["number"] == 2)
    check("G15 Yvonne 人格数 3",
          nm["personality"]["number"] == 3 and nm["personality"]["chain"] == [75, 12, 3])

    nm = numerology("2004-06-12", name="Zhang Wei")["name"]
    check("G16 Zhang Wei 表达 3 / 灵魂 6 / 人格 6",
          nm["expression"]["number"] == 3 and nm["expression"]["total"] == 93
          and nm["soul_urge"]["number"] == 6 and nm["personality"]["number"] == 6)
    check("G17 字母映射 A=1…Z=26",
          num.LATIN_VALUES["A"] == 1 and num.LATIN_VALUES["Z"] == 26
          and num.LATIN_VALUES["J"] == 10)

    nm = numerology("2004-06-12", name="A")["name"]
    check("G18 单字母人格数 0 优雅处理",
          nm["expression"]["number"] == 1 and nm["personality"]["number"] == 0
          and "无有效数字" in nm["personality"]["title"])

    nm = numerology("2004-06-12", name="张伟")["name"]
    check("G19 中文名无笔画降级",
          nm["provided"] is True and nm["available"] is False
          and nm["name_supported"] is False and "笔画" in nm["note"])

    nm = numerology("2004-06-12", name="张伟", strokes=[7, 6])["name"]
    five = nm["five_grid"]
    check("G20 张伟五格 8/13/7/2/13",
          nm["name_supported"] is True and
          (five["tian"]["raw"], five["ren"]["raw"], five["di"]["raw"],
           five["wai"]["raw"], five["zong"]["raw"]) == (8, 13, 7, 2, 13),
          repr({k: five[k]["raw"] for k in ("tian", "ren", "di", "wai", "zong")}))
    nm = numerology("2004-06-12", name="张伟明", strokes=[7, 6, 8])["name"]
    five = nm["five_grid"]
    check("G21 张伟明五格 8/13/14/9/21",
          (five["tian"]["raw"], five["ren"]["raw"], five["di"]["raw"],
           five["wai"]["raw"], five["zong"]["raw"]) == (8, 13, 14, 9, 21))
    nm = num.numerology(report_of("2004-06-12"), name="欧阳明",
                        strokes=[15, 17, 8], surname_len=2, as_of=AS_OF)["name"]
    five = nm["five_grid"]
    check("G22 欧阳明（复姓）五格 32/25/9/16/40",
          (five["tian"]["raw"], five["ren"]["raw"], five["di"]["raw"],
           five["wai"]["raw"], five["zong"]["raw"]) == (32, 25, 9, 16, 40))
    nm = num.numerology(report_of("2004-06-12"), name="欧阳明明",
                        strokes=[15, 17, 8, 9], surname_len=2, as_of=AS_OF)["name"]
    five = nm["five_grid"]
    check("G23 欧阳明明五格 32/25/17/24/49",
          (five["tian"]["raw"], five["ren"]["raw"], five["di"]["raw"],
           five["wai"]["raw"], five["zong"]["raw"]) == (32, 25, 17, 24, 49))

    nm = numerology("2004-06-12", name="张伟", strokes="7,6")["name"]
    check("G24 笔画字符串解析", nm["name_supported"] is True and
          nm["five_grid"]["zong"]["raw"] == 13)
    nm = numerology("2004-06-12", name="张伟", strokes=[7])["name"]
    check("G25 笔画数不匹配降级",
          nm["name_supported"] is False and "不一致" in nm["note"])
    nm = numerology("2004-06-12", name="张Wei")["name"]
    check("G26 中英混排降级", nm["name_supported"] is False)
    nm = numerology("2004-06-12", name="")["name"]
    check("G27 空姓名按未提供处理", nm["provided"] is False)
    nm = num.numerology(report_of("2004-06-12"), name="张伟", strokes=[7, 6],
                        surname_len=3, as_of=AS_OF)["name"]
    check("G28 非法 surname_len 降级",
          nm["name_supported"] is False and "笔画数据无效" in nm["note"])
    nm = numerology("2004-06-12", name="张伟", strokes=[7, 0])["name"]
    check("G29 非正笔画降级", nm["name_supported"] is False)
    five = numerology("2004-06-12", name="张伟", strokes=[7, 6])["name"]["five_grid"]
    check("G30 五格 note 说明算法",
          "五格" in five["note"] and "假成数" in five["note"])
    nm = num.numerology(report_of("2004-06-12", name="John Smith"), name="Lynn",
                        as_of=AS_OF)["name"]
    check("G31 name 参数覆盖 report 姓名", nm["name"] == "Lynn")

    # ══ 八、成熟数 ═══════════════════════════════════════════════════════
    d = num.numerology(report_of("2004-06-12"), as_of=AS_OF)
    check("H1 无名时成熟数空值",
          d["maturity"]["available"] is False and d["maturity"]["number"] is None)
    d = numerology("2004-06-12", name="John Smith")
    check("H2 成熟数 6+8=14 → 5",
          d["maturity"]["available"] is True and d["maturity"]["number"] == 5
          and d["maturity"]["chain"] == [14, 5])
    d = numerology("2000-03-15", name="Lynn")
    check("H3 成熟数 11+11=22 主数",
          d["maturity"]["number"] == 22 and d["maturity"]["is_master"])
    d = numerology("2004-06-12", name="张伟", strokes=[7, 6])
    check("H4 中文五格无表达数 → 成熟数不可算",
          d["name"]["five_grid"] is not None and
          d["maturity"]["available"] is False)
    check("H5 成熟数 note 含加法", "+" in numerology(
        "2004-06-12", name="John Smith")["maturity"]["note"])
    check("H6 成熟数标题非空",
          bool(numerology("2004-06-12", name="John Smith")["maturity"]["title"]))

    # ══ 九、结构、序列化与文本渲染 ═══════════════════════════════════════
    d = numerology("2004-06-12", name="John Smith", focus_year=2026)
    expected_keys = {"version", "method", "input", "life_path", "birthday",
                     "attitude", "maturity", "personal", "grid", "name",
                     "summary", "limits"}
    check("I1 顶层字段齐全", expected_keys <= set(d))
    check("I2 version = 3", d["version"] == 3 and num.VERSION == 3)
    check("I3 method 说明体系", "毕达哥拉斯" in num.MODEL and
          "Pythagorean" in num.MODEL)
    check("I4 limits 含指定免责句",
          "数字学属现代民俗/流行心理学，无学术预测效度" in num.LIMITS[0])
    check("I5 limits 条目充足且为非空字符串",
          len(num.LIMITS) >= 5 and all(isinstance(x, str) and x for x in num.LIMITS))
    check("I6 JSON 往返一致",
          json.loads(json.dumps(d, ensure_ascii=False)) == d)
    check("I7 结果确定性",
          num.numerology(report_of("2004-06-12", name="John Smith"), as_of=AS_OF)
          == num.numerology(report_of("2004-06-12", name="John Smith"), as_of=AS_OF))
    check("I8 summary 非空且含免责句",
          isinstance(d["summary"], list) and bool(d["summary"])
          and "无学术预测效度" in d["summary"][-1])
    check("I9 summary 提到生命灵数", "生命灵数" in d["summary"][0])
    check("I10 input 关键字段",
          {"birth_date", "used_time", "focus_year", "reference_date",
           "time_scale"} <= set(d["input"]))
    check("I11 生命灵数关键词 ≥2", len(d["life_path"]["keywords"]) >= 2)
    check("I12 生命灵数取值合法",
          d["life_path"]["number"] in set(range(1, 10)) | {11, 22, 33})

    text = num.render_numerology_text(d)
    check("I13 文本含核心标题",
          isinstance(text, str) and "生命灵数" in text and "九宫格" in text
          and "数字学" in text)
    check("I14 文本含免责句", "无学术预测效度" in text)
    check("I15 文本含个人周期", "个人年" in text and "个人月" in text)
    check("I16 文本含姓名三项",
          "表达数" in text and "灵魂数" in text and "人格数" in text)
    check("I17 无名文本提示未提供", "未提供姓名" in num.render_numerology_text(
        num.numerology(report_of("2004-06-12"), as_of=AS_OF)))
    check("I18 中文无笔画文本含 name_supported",
          "name_supported = false" in num.render_numerology_text(
              numerology("2004-06-12", name="张伟")))
    check("I19 中文有笔画文本含天格",
          "天格" in num.render_numerology_text(
              numerology("2004-06-12", name="张伟", strokes=[7, 6])))
    check("I20 主数文本含主数",
          "主数" in num.render_numerology_text(numerology("2000-03-15")))
    gtext = num.render_numerology_text(num.numerology(report_of("2004-06-12"),
                                                      as_of=AS_OF))
    check("I21 九宫格渲染缺数标记", "9缺" in gtext and "4×1" in gtext)

    try:
        num.render_numerology_text("not a dict")
        check("I22 渲染非 dict 抛 TypeError", False, "未抛异常")
    except TypeError:
        check("I22 渲染非 dict 抛 TypeError", True)

    # ══ 十、独立 CLI 契约 ═════════════════════════════════════════════════
    j = cli_json("--date", "2004-06-12", "--time", "10:00", "--sex", "male",
                 "--focus-year", "2026", "--as-of", AS_OF)
    check("J1 CLI --json 输出合法", j["version"] == 3 and
          j["input"]["birth_date"] == "2004-06-12")
    check("J2 CLI 生命灵数 6", j["life_path"]["number"] == 6)
    check("J3 CLI 个人年 1", j["personal"]["year"] == 1)

    r = run(["--date", "2004-06-12", "--time", "10:00", "--focus-year", "2026",
             "--as-of", AS_OF])
    check("J4 CLI 文本模式含标题",
          r.returncode == 0 and "生命灵数" in r.stdout and "九宫格" in r.stdout)

    j = cli_json("--date", "2004-06-12", "--name", "John Smith",
                 "--focus-year", "2026", "--as-of", AS_OF)
    check("J5 CLI --name 表达数 8", j["name"]["expression"]["number"] == 8)
    check("J6 CLI --name 成熟数 5", j["maturity"]["number"] == 5)
    check("J7 CLI input.name 回填", j["input"]["name"] == "John Smith")

    j = cli_json("--date", "2004-06-12", "--name", "张伟",
                 "--focus-year", "2026", "--as-of", AS_OF)
    check("J8 CLI 中文名无笔画 name_supported=false",
          j["name"]["name_supported"] is False)
    j = cli_json("--date", "2004-06-12", "--name", "张伟", "--strokes", "7,6",
                 "--focus-year", "2026", "--as-of", AS_OF)
    check("J9 CLI --strokes 计算五格",
          j["name"]["five_grid"]["zong"]["raw"] == 13)

    j = cli_json("--date", "2004-06-12", "--focus-year", "2026", "--as-of", AS_OF)
    check("J10 CLI --as-of 影响个人月日",
          j["personal"]["month"] == 11 and j["personal"]["day"] == 4)

    j = cli_json("--date", "2004-06-12", "--focus-year", "2025", "--as-of", "2025-10-29")
    check("J11 CLI 聚焦年切换", j["personal"]["year"] == 9)

    check("J12 CLI 非法日期非零退出",
          run(["--date", "2004-13-01"]).returncode != 0)
    check("J13 CLI 缺 --date 非零退出", run([]).returncode != 0)
    check("J14 CLI 非法时间非零退出",
          run(["--date", "2004-06-12", "--time", "25:00"]).returncode != 0)
    check("J15 CLI 真太阳时缺经度非零退出",
          run(["--date", "2004-06-12", "--true-solar-time"]).returncode != 0)
    check("J16 CLI 输出为 UTF-8 中文",
          "数字学" in run(["--date", "2004-06-12"]).stdout)

    # ══ 十一、真实 bazi.py 报告联调 ══════════════════════════════════════
    check("K1 真实报告含 time.used", bool(real.get("time", {}).get("used")))
    check("K2 真实报告 input.date", real.get("input", {}).get("date") == "2004-06-12")
    d = num.numerology(real, as_of=AS_OF, name="John Smith")
    check("K3 真实报告生命灵数 6 且成熟数 5",
          d["life_path"]["number"] == 6 and d["maturity"]["number"] == 5)
    check("K4 真实报告 used 时间一致",
          d["input"]["used_time"] == real["time"]["used"])
    d2 = num.numerology(real, as_of=AS_OF)
    check("K5 真实报告九宫格一致",
          d2["grid"]["missing"] == [3, 5, 7, 8, 9])

    # ══ 十二、边界值 ═════════════════════════════════════════════════════
    d = numerology("9999-12-31", as_of="9999-12-31")
    check("L1 9999-12-31 可计算", d["life_path"]["number"] == 7 and
          d["personal"]["year"] == 8 and d["personal"]["day"] == 33,
          repr((d["life_path"]["number"], d["personal"]["year"],
                d["personal"]["day"])))
    check("L2 9999 结果可序列化", isinstance(json.dumps(d, ensure_ascii=False), str))
    d = numerology("0001-01-01", as_of="0001-01-01")
    check("L3 0001-01-01 生命灵数 3", d["life_path"]["number"] == 3)
    d = numerology("1900-01-01", as_of="1900-01-01")
    check("L4 1900-01-01 生命灵数 3", d["life_path"]["number"] == 3)
    check("L5 2000-02-29 生日数 11 主数",
          numerology("2000-02-29")["birthday"]["number"] == 11)
    check("L6 2024-02-29 态度数 4",
          numerology("2024-02-29")["attitude"]["number"] == 4)

    rep = {"input": {"date": "2004-06-12", "time": "10:00"},
           "focus_year": 2026}
    d = num.numerology(rep, as_of=AS_OF)
    check("L7 HH:MM 时间补秒", d["input"]["birth_time"] == "10:00:00")

    rep = {"input": {"date": "2004-06-12"},
           "time": {"used": "2004-06-12T10:30:00"},
           "focus_year": 2026}
    d = num.numerology(rep, as_of=AS_OF)
    check("L8 ISO T 时间可解析", d["input"]["birth_time"] == "10:30:00")

    # ── 结果 ──────────────────────────────────────────────────────
    print("数字学层回归：%d 项" % total)
    if failures:
        print("失败 %d 项：" % len(failures))
        for f in failures:
            print("  ✗ " + f)
        sys.exit(1)
    print("全部通过 ✓")


if __name__ == "__main__":
    main()
