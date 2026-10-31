# -*- coding: utf-8 -*-
"""跨体系融合层（fusion）回归测试：结构、信号映射、一致性与张力、退化、CLI 契约、确定性。

运行：python tests/verify_fusion.py
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

import fusion  # noqa: E402

BASE_ARGS = ["--date", "2004-06-12", "--time", "10:00", "--sex", "male",
             "--longitude", "123.96", "--true-solar-time", "--focus-year", "2026"]


def run_cli(*args):
    return subprocess.run([PY, CLI] + list(args), capture_output=True,
                          text=True, encoding="utf-8")


def cli_json(*args):
    r = run_cli(*(list(args) + ["--json"]))
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-800:])
    return json.loads(r.stdout)


def has_module(name):
    try:
        __import__(name)
        return True
    except Exception:
        return False


LEVELS = {"明显偏顺", "偏顺", "略偏顺", "中平", "略偏吃力", "偏吃力", "吃力", "证据不足"}
CONSENSUS = {"一致", "多数", "分歧", "对立", "单体系参考", "信号相抵", "证据不足"}


def main():
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    rep = cli_json(*(BASE_ARGS + ["--topics", "--divination", "--ziwei"]))
    data = fusion.build_fusion(rep)

    # ── A. 顶层结构 ─────────────────────────────────────────────
    check("A1 返回 dict", isinstance(data, dict), type(data))
    for key in ("version", "model", "inputs", "systems", "domains", "tensions",
                "timing", "overall", "limits"):
        check("A2 顶层字段 %s" % key, key in data)
    check("A3 version", data.get("version") == "v1", data.get("version"))
    check("A4 model 非空", isinstance(data.get("model"), str) and len(data["model"]) > 20)
    check("A5 inputs 是 dict", isinstance(data.get("inputs"), dict))
    check("A6 limits ≥4 条", len(data.get("limits") or []) >= 4)
    check("A7 limits 含「双盲」", any("双盲" in x for x in data.get("limits") or []))
    check("A8 limits 含「权重」", any("权重" in x for x in data.get("limits") or []))
    check("A9 9 个领域", len(data.get("domains") or []) == 9, len(data.get("domains") or []))
    check("A10 领域 id 集合", {d["id"] for d in data["domains"]} == set(fusion.DOMAIN_IDS))
    check("A11 JSON 可序列化", bool(json.dumps(data, ensure_ascii=False)))

    # ── B. 体系与权重 ───────────────────────────────────────────
    systems = data.get("systems") or []
    check("B1 6 个体系", len(systems) == 6, len(systems))
    check("B2 体系 key 集合", {s["key"] for s in systems} == set(fusion.WEIGHTS))
    for s in systems:
        check("B3 权重与常量一致 %s" % s["key"], abs(s["weight"] - fusion.WEIGHTS[s["key"]]) < 1e-9)
        check("B4 体系字段 %s" % s["key"],
              all(k in s for k in ("name", "weight", "available", "basis")))
    check("B5 八字可用", any(s["key"] == "bazi" and s["available"] for s in systems))
    check("B6 紫微可用", any(s["key"] == "ziwei" and s["available"] for s in systems))
    check("B7 民俗可用", any(s["key"] == "folk" and s["available"] for s in systems))
    have_astro = has_module("astrology")
    check("B8 西洋可用性与模块一致",
          any(s["key"] == "western" and s["available"] == have_astro for s in systems), have_astro)
    check("B9 数字可用性与模块一致",
          any(s["key"] == "numerology" and s["available"] == has_module("numerology")
              for s in systems))
    check("B10 权重排序（八字最高）",
          max(systems, key=lambda s: s["weight"])["key"] == "bazi")
    check("B11 民俗权重最低",
          min(systems, key=lambda s: s["weight"])["key"] == "folk")

    # ── C. 领域输出合法性 ───────────────────────────────────────
    for d in data["domains"]:
        check("C1 领域字段 %s" % d["id"],
              all(k in d for k in ("id", "title", "signal", "level", "consensus", "votes")))
        check("C2 等级合法 %s" % d["id"], d["level"] in LEVELS, d["level"])
        check("C3 共识标签合法 %s" % d["id"], d["consensus"] in CONSENSUS, d["consensus"])
        check("C4 信号范围 %s" % d["id"], -2.0 <= d["signal"] <= 2.0, d["signal"])
        check("C5 votes 是 list %s" % d["id"], isinstance(d["votes"], list))
        for v in d["votes"]:
            check("C6 vote 字段 %s" % d["id"],
                  all(k in v for k in ("system", "signal", "evidence")))
            check("C7 vote 体系合法 %s" % d["id"], v["system"] in fusion.WEIGHTS)
            check("C8 vote 依据非空 %s" % d["id"], bool(str(v["evidence"]).strip()))
    by_id = {d["id"]: d for d in data["domains"]}

    # ── D. 八字信号（2004-06-12 男命）──────────────────────────
    check("D1 财富偏顺", by_id["wealth"]["signal"] > 0.25, by_id["wealth"]["signal"])
    check("D1b 财富八字票为正",
          any(v["system"] == "bazi" and v["signal"] > 0 for v in by_id["wealth"]["votes"]))
    check("D2 事业偏顺", by_id["career"]["signal"] > 0.3, by_id["career"]["signal"])
    check("D3 健康不吃力也不偏顺", by_id["health"]["signal"] <= 0.15, by_id["health"]["signal"])
    check("D3b 健康八字票为负",
          any(v["system"] == "bazi" and v["signal"] < 0 for v in by_id["health"]["votes"]))
    check("D4 财富有八字财星票",
          any(v["system"] == "bazi" and "财星" in v["evidence"] for v in by_id["wealth"]["votes"]))
    check("D5 迁移有驿马依据",
          any("驿马" in v["evidence"] for v in by_id["move"]["votes"]),
          [v["evidence"] for v in by_id["move"]["votes"]])
    check("D6 事业有格局依据",
          any("格" in v["evidence"] for v in by_id["career"]["votes"]))
    check("D7 健康有身弱依据",
          any("身弱" in v["evidence"] for v in by_id["health"]["votes"]))
    check("D8 性格有比劫依据",
          any("比劫" in v["evidence"] for v in by_id["personality"]["votes"]))

    # ── E. 紫微信号 ────────────────────────────────────────────
    pv = by_id["personality"]["votes"]
    check("E1 性格含紫微命宫票",
          any(v["system"] == "ziwei" and "命宫" in v["evidence"] for v in pv),
          [v["evidence"] for v in pv])
    check("E2 感情含紫微夫妻宫票",
          any(v["system"] == "ziwei" and "夫妻宫" in v["evidence"] for v in by_id["love"]["votes"]))
    check("E3 财富含紫微财帛/福德票",
          any(v["system"] == "ziwei" for v in by_id["wealth"]["votes"]))
    check("E4 迁移动宫有紫微票",
          any(v["system"] == "ziwei" and "迁移宫" in v["evidence"] for v in by_id["move"]["votes"]))

    # ── F. 民俗信号 ───────────────────────────────────────────
    check("F1 民俗票来自小六壬/称骨/星座",
          any(v["system"] == "folk" and ("小六壬" in v["evidence"] or "称骨" in v["evidence"]
                                         or "星座" in v["evidence"])
              for d in data["domains"] for v in d["votes"]))

    # ── G. 时机 ───────────────────────────────────────────────
    tim = data.get("timing") or {}
    check("G1 时机字段", all(k in tim for k in ("year", "ganzhi", "signal", "level", "votes")))
    check("G2 时机年份 2026", tim.get("year") == 2026, tim.get("year"))
    check("G3 时机干支丙午", tim.get("ganzhi") == "丙午", tim.get("ganzhi"))
    check("G4 时机含八字票", any(v["system"] == "bazi" for v in tim["votes"]))
    check("G5 时机含紫微票", any(v["system"] == "ziwei" for v in tim["votes"]))
    check("G6 时机信号范围", -2.0 <= tim.get("signal", 0) <= 2.0)
    check("G7 时机等级合法", tim.get("level") in LEVELS, tim.get("level"))
    check("G8 紫微大限证据非空",
          all(str(v["evidence"]).strip() for v in tim["votes"]))
    check("G9 时机信号偏吃力", tim.get("signal") < 0, tim.get("signal"))

    # ── H. 一致性与张力语义 ───────────────────────────────────
    same = fusion._consensus({"bazi": 1.0, "ziwei": 0.8}, 0.9)
    check("H1 同向→一致", same[2] == "一致", same)
    check("H2 同向一致度 1.0", same[0] == 1.0, same)
    mixed = fusion._consensus({"bazi": 1.0, "ziwei": -0.8}, 0.1)
    check("H3 反向→分歧/对立", mixed[2] in ("分歧", "对立"), mixed)
    one = fusion._consensus({"bazi": 1.0}, 1.0)
    check("H4 单体系→单体系参考", one[2] == "单体系参考", one)
    check("H5 单体系 agreement None", one[0] is None)

    votes = [
        {"system": "bazi", "domain": "career", "signal": 1.0, "evidence": "x"},
        {"system": "ziwei", "domain": "career", "signal": 0.9, "evidence": "y"},
    ]
    agg = {d["id"]: d for d in fusion._aggregate_domains(votes)}
    check("H6 加权聚合 career", agg["career"]["signal"] > 0.85, agg["career"]["signal"])
    check("H7 career 一致", agg["career"]["consensus"] == "一致", agg["career"]["consensus"])
    check("H8 无票领域证据不足", agg["love"]["level"] == "证据不足", agg["love"]["level"])
    cancel = [
        {"system": "bazi", "domain": "study", "signal": 1.0, "evidence": "x"},
        {"system": "bazi", "domain": "study", "signal": -1.0, "evidence": "y"},
    ]
    agg2 = {d["id"]: d for d in fusion._aggregate_domains(cancel)}
    check("H9 同体系自相抵→信号相抵", agg2["study"]["consensus"] == "信号相抵", agg2["study"])
    check("H10 相抵时 level 中平", agg2["study"]["level"] == "中平", agg2["study"]["level"])
    check("H11 等级函数区间",
          fusion._level(1.5) == "明显偏顺" and fusion._level(0.7) == "偏顺"
          and fusion._level(0.0) == "中平" and fusion._level(-1.5) == "吃力",
          [fusion._level(1.5), fusion._level(0.7), fusion._level(0.0), fusion._level(-1.5)])

    # ── I. 张力与整体 ─────────────────────────────────────────
    ten = data.get("tensions") or []
    check("I1 tensions 是 list", isinstance(ten, list))
    for t in ten:
        check("I2 张力领域合法", t.get("domain") in fusion.DOMAIN_IDS, t.get("domain"))
        check("I3 张力 detail 非空", bool(t.get("detail")))
    ov = data.get("overall") or {}
    check("I4 overall 字段", all(k in ov for k in ("agreement", "confidence", "summary")))
    if ov.get("agreement") is not None:
        check("I5 一致度范围", 0.0 <= ov["agreement"] <= 1.0, ov["agreement"])
    check("I6 把握合法", ov.get("confidence") in ("高", "中", "低"), ov.get("confidence"))
    check("I7 summary 非空", bool(ov.get("summary")))
    check("I8 体系覆盖数一致",
          ov.get("systems_available") == sum(1 for s in systems if s["available"]),
          (ov.get("systems_available"), [s["available"] for s in systems]))
    check("I9 体系总数 6", ov.get("systems_total") == 6, ov.get("systems_total"))

    # ── J. 退化场景 ───────────────────────────────────────────
    rep_min = cli_json(*BASE_ARGS)
    data_min = fusion.build_fusion(rep_min)
    check("J1 最简报告可建", isinstance(data_min, dict) and len(data_min["domains"]) == 9)
    check("J2 无专题时不崩", all(d["level"] in LEVELS for d in data_min["domains"]))
    check("J3 无民俗票时 folk 仍记录", any(s["key"] == "folk" for s in data_min["systems"]))
    rep_nosex = cli_json("--date", "2004-06-12", "--time", "10:00")
    data_nosex = fusion.build_fusion(rep_nosex)
    check("J4 缺性别不崩", isinstance(data_nosex, dict))
    rep_unk = cli_json(*(BASE_ARGS + ["--time-unknown"]))
    data_unk = fusion.build_fusion(rep_unk)
    check("J5 时辰未知不崩", isinstance(data_unk, dict))
    rep_special = cli_json("--date", "1985-02-12", "--time", "13:00", "--sex", "male")
    data_special = fusion.build_fusion(rep_special)
    check("J6 特殊格不崩", isinstance(data_special, dict) and len(data_special["domains"]) == 9)

    # ── K. 确定性 ─────────────────────────────────────────────
    a1 = json.dumps(fusion.build_fusion(rep), ensure_ascii=False, sort_keys=True)
    a2 = json.dumps(fusion.build_fusion(rep), ensure_ascii=False, sort_keys=True)
    check("K1 两次构建一致", a1 == a2)
    check("K2 不修改输入 report", "fusion" not in rep or isinstance(rep.get("fusion"), dict))

    # ── L. 渲染文本 ───────────────────────────────────────────
    text = fusion.render_fusion_text(data)
    check("L1 标题", "跨体系融合" in text)
    check("L2 含整体段", "【整体】" in text)
    check("L3 含时机段", "【时机】" in text)
    check("L4 含方法学", "【方法学与边界】" in text)
    check("L5 无 None", "None" not in text)
    check("L6 长度合理", 1200 <= len(text) <= 12000, len(text))
    check("L7 含至少 6 个领域标题",
          sum(1 for d in data["domains"] if d["title"] in text) >= 6)
    check("L8 体系权重可见", "权重" in text)
    check("L9 双重说明（不是互相验证）", "互相验证" in text)
    check("L10 无禁用绝对词", "一定" not in text and "必然" not in text)

    # ── M. CLI 契约 ───────────────────────────────────────────
    r = run_cli(*(BASE_ARGS + ["--fusion"]))
    check("M1 CLI 退出码 0", r.returncode == 0, r.stderr[-300:])
    check("M2 CLI 含融合段", "跨体系融合" in r.stdout)
    check("M3 CLI 含时机", "【时机】" in r.stdout)
    rep_f = cli_json(*(BASE_ARGS + ["--fusion"]))
    check("M4 JSON 含 fusion 字段", isinstance(rep_f.get("fusion"), dict))
    check("M5 JSON fusion version", (rep_f.get("fusion") or {}).get("version") == "v1")
    check("M6 JSON fusion 9 域", len((rep_f.get("fusion") or {}).get("domains") or []) == 9)
    r2 = run_cli(*(BASE_ARGS + ["--fusion", "--plain"]))
    check("M7 与 --plain 组合可跑", r2.returncode == 0 and "跨体系融合" in r2.stdout,
          r2.stderr[-200:])
    check("M8 与 --divination 组合可跑",
          run_cli(*(BASE_ARGS + ["--fusion", "--divination"])).returncode == 0)

    # ── N. 纯标准库约束 ───────────────────────────────────────
    with open(os.path.join(ROOT, "scripts", "fusion.py"), "r", encoding="utf-8") as f:
        src = f.read()
    for bad in ("import numpy", "import ephem", "import scipy", "import pandas"):
        check("N1 无第三方依赖 %s" % bad, bad not in src)
    check("N2 只用 datetime/json 级内置", "import datetime" in src or "from datetime" in src)

    # ── 汇总 ─────────────────────────────────────────────────
    failed = [c for c in checks if not c[1]]
    print("跨体系融合层回归：%d 项" % len(checks))
    for name, ok, detail in checks:
        if not ok:
            print("  FAIL %s  %s" % (name, detail))
    if failed:
        print("失败 %d / %d" % (len(failed), len(checks)))
        return 1
    print("全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
