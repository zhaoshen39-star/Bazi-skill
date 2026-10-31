# -*- coding: utf-8 -*-
"""v2 优化回归：十神结构、喜忌打分、神煞扩充、干支关系、文本/JSON 契约。

运行：python tests/verify_v2.py
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
    return subprocess.run([PY, CLI] + list(args), capture_output=True,
                          text=True, encoding="utf-8")


def cli_json(*args):
    r = run_cli(*(list(args) + ["--json"]))
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-500:])
    return json.loads(r.stdout)


PILLAR_NAMES = ["年柱", "月柱", "日柱", "时柱"]


def mk(gzs):
    return [{"gan": g[0], "zhi": g[1], "name": n} for g, n in zip(gzs, PILLAR_NAMES)]


def names(combos):
    return [x["name"] for x in combos]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    failures = []
    total = 0

    def check(name, ok, detail=""):
        nonlocal total
        total += 1
        if not ok:
            failures.append("%s %s" % (name, detail))

    # ── 1. 十神结构：官印/杀印分开，不重复 ────────────────────────────
    c = analysis.combinations(mk(["辛酉", "癸亥", "甲子", "乙亥"]), "甲")
    check("官印相生", "官印相生" in names(c), names(c))
    check("官印相生用正官", "正官(年柱)" in c[0]["members"] if c else False, c)
    check("官印相生不混七杀", "杀印相生" not in names(c), names(c))

    c = analysis.combinations(mk(["辛酉", "庚申", "甲子", "丙寅"]), "甲")
    check("官杀混杂", "官杀混杂" in names(c), names(c))
    check("官印/杀印同时分列",
          "官印相生" in names(c) and "杀印相生" in names(c), names(c))
    check("官杀混杂成员", any(x["members"] == ["正官(年柱)", "七杀(月柱)"]
                          for x in c if x["name"] == "官杀混杂"), c)

    # ── 2. 杀刃 / 比劫夺财 / 食神制杀 ────────────────────────────────
    c = analysis.combinations(mk(["庚申", "己卯", "甲寅", "丙寅"]), "甲")
    check("杀刃相济", any(x["name"] == "杀刃相济" and "阳刃(卯)" in x["members"]
                        for x in c), c)

    c = analysis.combinations(mk(["甲子", "甲寅", "甲辰", "戊辰"]), "甲")
    check("比劫夺财", any(x["name"] == "比劫夺财" and x["members"] == ["比劫×3"]
                        for x in c), c)

    c = analysis.combinations(mk(["丙寅", "庚申", "甲子", "丙寅"]), "甲")
    check("食神制杀", "食神制杀" in names(c), names(c))

    # ── 3. 组合层级命名 ───────────────────────────────────────────────
    c = analysis.combinations(mk(["己卯", "丙寅", "甲午", "丁卯"]), "甲")
    legal_levels = {"透干", "半透", "月令", "透干/本气", "本气/透干", "月令/透干"}
    for x in c:
        check("合法层级", x["level"] in legal_levels, (x["name"], x["level"]))
    c = analysis.combinations(mk(["庚申", "己卯", "甲寅", "丙寅"]), "甲")
    check("杀刃层级", any(x["level"] == "月令/透干" for x in c if x["name"] == "杀刃相济"), c)

    # ── 4. 喜忌打分（规则模型）──────────────────────────────────────
    import chart
    cc = chart.build(1990, 6, 15, 12, 0, 0, sex=1, dayun_count=1, focus_year=2026)
    prof = analysis.wuxing_profile(cc["pillars"], cc["day_gan"])
    st = analysis.strength(cc["pillars"], cc["day_gan"], prof)
    ge = analysis.pattern(cc["pillars"], cc["day_gan"])
    ys = analysis.yong_shen(cc["day_gan"], prof, st, ge)
    f1 = analysis.flow_favorability(ys, "己丑")
    f2 = analysis.flow_favorability(ys, "丁亥")
    check("喜忌打分：己丑偏喜", f1["score"] > 0.5 and f1["label"] in ("喜", "偏喜"), f1)
    check("喜忌打分：丁亥偏忌", f2["score"] < -0.5 and f2["label"] in ("忌", "偏忌"), f2)
    check("喜忌打分可解释", bool(f1["reasons"]) and bool(f2["reasons"]), (f1, f2))
    check("喜忌打分有界", all(-4.0 <= x["score"] <= 4.0 for x in (f1, f2)), (f1, f2))
    check("喜忌打分确定", f1 == analysis.flow_favorability(ys, "己丑"))

    # 调候与扶抑冲突提示
    check("调候冲突提示", "调候" in ys["reason"], ys["reason"])

    # ── 5. 神煞扩充与健壮性 ─────────────────────────────────────────
    ss = analysis.shen_sha(mk(["甲申", "丙寅", "甲子", "己亥"]), "甲")
    check("亡神命中亥", "亡神" in ss and any("亥" in x for x in ss["亡神"]), ss)
    check("驿马命中寅", "驿马" in ss, ss)
    check("将星命中子", "将星" in ss, ss)
    check("无劫煞不硬造", "劫煞" not in ss, ss)

    ss = analysis.shen_sha(mk(["甲子", "丙寅", "庚辰", "丁亥"]), "庚")
    check("魁罡无 ganzhi 字段也可算", "魁罡" in ss and "日柱庚辰" in ss["魁罡"], ss)

    # ── 6. 干支关系：三合/半合/三刑/部分刑 ──────────────────────────
    rel = analysis.relations(mk(["甲子", "甲申", "甲寅", "丙午"]))
    check("申子半合水", any("半合水" in x for x in rel), rel)
    check("缺辰不报三合", not any("三合" in x for x in rel), rel)

    rel = analysis.relations(mk(["甲子", "甲申", "甲辰", "丙午"]))
    check("申子辰三合", any("三合" in x for x in rel), rel)
    check("三合齐全不重复半合", not any("半合" in x for x in rel), rel)

    rel = analysis.relations(mk(["甲寅", "甲巳", "甲子", "甲午"]))
    check("寅巳部分刑", any("相刑" in x and "无恩" in x for x in rel), rel)
    check("缺申不报三刑", not any("三刑" in x for x in rel), rel)

    rel = analysis.relations(mk(["甲寅", "甲巳", "甲申", "甲午"]))
    check("寅巳申三刑", any("三刑" in x for x in rel), rel)
    check("三刑齐全不重复部分刑", not any("相刑" in x for x in rel), rel)

    # ── 7. CLI 契约：文本 ────────────────────────────────────────────
    base = ("--date", "1990-06-15", "--time", "12:00", "--sex", "male")
    r = run_cli(*(base + ("--focus-year", "2026")))
    out = r.stdout
    check("CLI 成功", r.returncode == 0, r.stderr[-300:])
    check("文本：十神结构段", "【十神结构】" in out)
    check("文本：结构排序说明", "按透干程度排序" in out)
    check("文本：杀印相生", "杀印相生" in out)
    check("文本：错误重复官印不出现", "官印相生" not in out)
    check("文本：神煞金舆", "金舆" in out)
    check("文本：神煞天德", "天德贵人" in out)
    check("文本：喜忌列", "喜(" in out or "忌(" in out)
    check("文本：流年基调", "2026 丙午（基调：忌" in out, out[-1500:])
    check("文本：理由无。；", "。；" not in out)

    # ── 8. CLI 契约：JSON ───────────────────────────────────────────
    d = cli_json(*(base + ("--focus-year", "2026")))
    comb = d["analysis"]["combinations"]
    check("JSON combinations", isinstance(comb, list) and comb, comb)
    check("JSON combinations 字段",
          all(set(("name", "level", "members", "note")) <= set(x) for x in comb), comb)
    check("JSON combinations rank",
          all(isinstance(x.get("rank"), int) for x in comb), comb)
    ranks = [x["rank"] for x in comb]
    check("JSON combinations 按 rank 降序", ranks == sorted(ranks, reverse=True), ranks)
    dy = d["chart"]["dayun"]["list"][0]
    ly = d["chart"]["liunian"][0]
    check("JSON 大运 favorability",
          {"label", "score", "reasons"} <= set(dy["favorability"]), dy["favorability"])
    check("JSON 流年 favorability",
          {"label", "score", "reasons"} <= set(ly["favorability"]), ly["favorability"])
    check("JSON yong_shen conflict", "conflict" in d["analysis"]["yong_shen"],
          list(d["analysis"]["yong_shen"]))
    check("JSON method 含新说明",
          "combinations" in d["method"] and "flow_favorability" in d["method"], list(d["method"]))

    print("v2 优化回归：%d 项" % total)
    if failures:
        print("失败：")
        for f in failures:
            print("  ✗ " + f)
        return 1
    print("全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
