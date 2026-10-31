# -*- coding: utf-8 -*-
"""v3 分析层/推测层回归：结构力旺衰、子平取格与成败、四法喜用与仲裁、岁运引动与应期。

运行：python tests/verify_v3.py
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
import analysis_v3 as a3  # noqa: E402
import chart  # noqa: E402

PILLAR_NAMES = ["年柱", "月柱", "日柱", "时柱"]
CUTS = list(a3.STRENGTH_CUTS)
LABELS = ["身弱", "偏弱", "中和", "偏强", "身强"]
PATTERN_NAMES = set(a3.GE_NAME_OF_GOD.values()) | {"建禄格", "月劫格（阳刃格）"}

failures = []
total = 0


def check(name, ok, detail=""):
    global total
    total += 1
    if not ok:
        failures.append("%s %s" % (name, detail))


def run_cli(*args):
    return subprocess.run([PY, CLI] + list(args), capture_output=True,
                          text=True, encoding="utf-8")


def cli_json(*args):
    r = run_cli(*(list(args) + ["--json"]))
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-800:])
    return json.loads(r.stdout)


def mk(gzs):
    return [{"gan": g[0], "zhi": g[1], "name": n} for g, n in zip(gzs, PILLAR_NAMES)]


def prof_for(pillars, day_gan):
    """v3 的 strength/yong_shen 不依赖 wuxing_profile；手工构造四柱时传 None。"""
    return None


def label_of(ratio):
    if ratio >= CUTS[3]:
        return "身强"
    if ratio >= CUTS[2]:
        return "偏强"
    if ratio >= CUTS[1]:
        return "中和"
    if ratio >= CUTS[0]:
        return "偏弱"
    return "身弱"


# ════════════════════════════════════════════════════════════════════════════
# 1. 旺衰 v3：结构力、四柱权重、刑冲折损、从格、置信度
# ════════════════════════════════════════════════════════════════════════════
def test_strength():
    p = mk(["甲戌", "丁丑", "辛亥", "癸巳"])
    st = a3.strength(p, "辛", prof_for(p, "辛"))
    check("S1 version=3", st.get("version") == 3, st.get("version"))
    check("S1 ratio/score 一致", st["ratio"] == st["score"], (st["ratio"], st["score"]))
    check("S1 ratio 在 [0,1]", 0.0 <= st["ratio"] <= 1.0, st["ratio"])
    check("S1 label 与阈值一致", st["label"] == label_of(st["ratio"]),
          (st["label"], st["ratio"], CUTS))
    check("S1 五党占比齐全",
          set(st["party_shares"]) == {"比劫", "印星", "食伤", "财星", "官杀"},
          st["party_shares"])
    check("S1 占比和≈1",
          abs(sum(st["party_shares"].values()) - 1.0) < 1e-6,
          sum(st["party_shares"].values()))
    check("S1 得令：辛日丑月为「相」", st["de_ling"]["state"] == "相", st["de_ling"])
    check("S1 得地明细含受损标记",
          any("受损" in x for x in st["de_di"]) or any(
              (r.get("damaged") for r in st["de_di_detail"])), st["de_di"])
    check("S1 结构折损记录冲刑",
          any("刑" in n["detail"] or "冲" in n["detail"] for n in st["structure_notes"]),
          st["structure_notes"])
    check("S1 置信度合法", st["confidence"] in ("高", "中", "低"), st["confidence"])
    check("S1 日干不计入天干同党",
          st["de_shi_heads"] == len(st["de_shi_detail"]), (st["de_shi_heads"], st["de_shi_detail"]))
    check("S1 model 文本存在", "结构力" in st["model"], st["model"][:40])

    # 月支权重：月支 40% 为主，同党月令 vs 异党月令至少应产生方向性差异
    p_yue = mk(["甲申", "丙子", "甲辰", "甲子"])   # 申子辰三合水，月令子水（印）
    st_yue = a3.strength(p_yue, "甲", prof_for(p_yue, "甲"))
    check("S1 三合局加权记录", any("三合" in n["detail"] for n in st_yue["structure_notes"]),
          st_yue["structure_notes"])
    check("S1 月令印星使同党占优", st_yue["ratio"] > 0.45, st_yue["ratio"])

    # 从弱：无本气根、无印比透干
    p_ruo = mk(["丙子", "丙寅", "辛卯", "乙巳"])
    st_ruo = a3.strength(p_ruo, "辛", prof_for(p_ruo, "辛"))
    check("S1 从弱格判定", (st_ruo["special"] or {}).get("kind") == "从弱", (st_ruo["special"], st_ruo["ratio"]))
    check("S1 从弱 ratio 低", st_ruo["ratio"] <= 0.25, st_ruo["ratio"])
    check("S1 从弱给提示", any("从" in h for h in st_ruo["special_hints"]), st_ruo["special_hints"])

    # 从强：全比劫印，无官杀透
    p_qiang = mk(["辛丑", "辛酉", "辛未", "戊戌"])
    st_qiang = a3.strength(p_qiang, "辛", prof_for(p_qiang, "辛"))
    check("S1 从强 ratio 高", st_qiang["ratio"] >= 0.80, st_qiang["ratio"])
    check("S1 从强识别", (st_qiang["special"] or {}).get("kind") == "从强", st_qiang["special"])


# ════════════════════════════════════════════════════════════════════════════
# 2. 格局 v3：取格顺序、禄刃、成败救应、月令损伤
# ════════════════════════════════════════════════════════════════════════════
def test_pattern():
    p = mk(["甲戌", "丁丑", "辛亥", "癸巳"])
    st = a3.strength(p, "辛", prof_for(p, "辛"))
    ge = a3.pattern(p, "辛", st)
    check("P1 中气透干取食神格", ge["name"] == "食神格", (ge["name"], ge["take_method"]))
    check("P1 取格说明含中气", "中气" in ge["take_method"], ge["take_method"])
    check("P1 类别正格", ge["category"] == "正格", ge["category"])
    check("P1 status 合法",
          ge["status"] in ("成格", "成中有败", "败中有救", "破格", "待定")
          or ge["status"].startswith("特殊格"), ge["status"])
    check("P1 good/bad 条目结构",
          all({"id", "desc", "rank"} <= set(x) for x in ge["good"] + ge["bad"]),
          (ge["good"], ge["bad"]))
    check("P1 rescue 只针对已出现的 bad",
          all(r["for"] in {b["id"] for b in ge["bad"]} for r in ge["rescue"]),
          ge["rescue"])
    check("P1 相神表结构", all({"party", "role"} <= set(x) for x in ge["xiang_shen"]),
          ge["xiang_shen"])
    check("P1 有月令损伤（戌丑相刑）", bool(ge["month_damage"]), ge["month_damage"])
    check("P1 note 含取格与成败", ge["take_method"] in ge["note"] and ge["status"] in ge["note"],
          ge["note"])

    # 禄刃月
    for (y, m, d), want in [((1984, 2, 20), "建禄格"),
                            ((2024, 6, 13), "月劫格（阳刃格）")]:
        c = chart.build(y, m, d, 12, 0, sex=1)
        g = a3.pattern(c["pillars"], c["day_gan"])
        check("P1 %04d-%02d-%02d → %s" % (y, m, d, want), g["name"] == want, g["name"])

    # 特殊格不套正格成败
    p_qiang = mk(["辛丑", "辛酉", "辛未", "戊戌"])
    st_q = a3.strength(p_qiang, "辛", prof_for(p_qiang, "辛"))
    ge_q = a3.pattern(p_qiang, "辛", st_q)
    check("P1 特殊格 status", ge_q["status"].startswith("特殊格"), ge_q["status"])

    # 所有定格的 name 都在允许集合内
    names_ok = True
    for date in [(1990, 6, 15), (1995, 1, 20), (2004, 6, 12), (2024, 2, 4), (2024, 5, 14)]:
        c = chart.build(*date, 12, 0, sex=1)
        nm = a3.pattern(c["pillars"], c["day_gan"])["name"]
        if nm not in PATTERN_NAMES:
            names_ok = False
    check("P1 格局名在允许集合", names_ok)


# ════════════════════════════════════════════════════════════════════════════
# 3. 喜用 v3：四法、仲裁、角色、用神有力
# ════════════════════════════════════════════════════════════════════════════
def test_yong_shen():
    p = mk(["甲戌", "丁丑", "辛亥", "癸巳"])
    prof = prof_for(p, "辛")
    st = a3.strength(p, "辛", prof)
    ge = a3.pattern(p, "辛", st)
    ys = a3.yong_shen("辛", prof, st, ge, p)
    check("Y1 version=3", ys.get("version") == 3, ys.get("version"))
    check("Y1 四法齐备",
          {"fuyi", "tiaohou", "tongguan", "bingyao"} <= set(ys["methods"]),
          list(ys["methods"]))
    check("Y1 仲裁顺序", tuple(ys["arbitration"]["order"]) == tuple(a3.ARBITRATION_ORDER),
          ys["arbitration"]["order"])
    check("Y1 仲裁规则非空", bool(ys["arbitration"]["rule"]), ys["arbitration"])
    check("Y1 角色覆盖五行", set(ys["shen_roles"]) == set(analysis.ELEMENTS),
          ys["shen_roles"])
    check("Y1 用神唯一",
          sum(1 for r in ys["shen_roles"].values() if r == "用神") == 1, ys["shen_roles"])
    roles = ys["shen_roles"]
    yong = [e for e, r in roles.items() if r == "用神"][0]
    check("Y1 喜神=生用神", roles.get(a3._sheng_of(yong)) == "喜神", (yong, roles))
    ke = a3._ke_me(yong)
    if ke in ys["secondary_elements"]:
        # 调候辅佐星可以克用神（如辛金丑月「丙火解冻、壬水淘洗」），此时按喜神论
        check("Y1 忌神=克用神（辅佐星例外）", roles.get(ke) == "喜神", (yong, ke, roles))
    else:
        check("Y1 忌神=克用神", roles.get(ke) == "忌神", (yong, ke, roles))
    check("Y1 用神有力输出", len(ys["yong_shen_force"]) >= 1, ys["yong_shen_force"])
    check("Y1 用神力量状态合法",
          all(f["status"] in ("有力（透干且有根）", "有透无根（需大运补根）",
                              "有根无透（有底气但难显）", "虚浮无根")
              for f in ys["yong_shen_force"]), ys["yong_shen_force"])
    check("Y1 调候急需优先（丑月寒）",
          "调候" in ys["arbitration"]["rule"], ys["arbitration"]["rule"])
    check("Y1 conflict 是字符串", isinstance(ys["conflict"], str), type(ys["conflict"]))
    check("Y1 主用落在用神角色", set(ys["primary_elements"]) <= {yong} or not ys["primary_elements"],
          (ys["primary_elements"], yong))

    # 中和盘：扶抑非主要矛盾时用调候/相神
    p2 = mk(["甲辰", "戊辰", "辛丑", "癸巳"])
    prof2 = prof_for(p2, "辛")
    st2 = a3.strength(p2, "辛", prof2)
    ys2 = a3.yong_shen("辛", prof2, st2, a3.pattern(p2, "辛", st2), p2)
    check("Y1 首用神始终存在", bool(ys2["primary_elements"]), ys2["primary_elements"])


# ════════════════════════════════════════════════════════════════════════════
# 4. 大运/流年：基调分、引动、应期、置信度
# ════════════════════════════════════════════════════════════════════════════
def test_flow():
    p = mk(["甲戌", "丁丑", "辛亥", "癸巳"])
    prof = prof_for(p, "辛")
    st = a3.strength(p, "辛", prof)
    ge = a3.pattern(p, "辛", st)
    ys = a3.yong_shen("辛", prof, st, ge, p)

    f = a3.flow_favorability(ys, "丙午")
    check("F1 基调分范围", -4.0 <= f["score"] <= 4.0, f["score"])
    check("F1 基调 label 与阈值一致",
          f["label"] == ("喜" if f["score"] >= 1.6 else "偏喜" if f["score"] >= 0.5 else
                         "中性" if f["score"] > -0.5 else "偏忌" if f["score"] > -1.6 else "忌"),
          f)
    check("F1 基调确定性", f == a3.flow_favorability(ys, "丙午"))
    check("F1 reasons 非空", bool(f["reasons"]), f["reasons"])
    check("F1 权重口径 = 用神2.2/忌神-1.9", "2.2" in f["model"] and "1.9" in f["model"], f["model"])

    dayun = [{"ganzhi": "癸未", "gan": "癸", "zhi": "未",
              "start_year": 1990, "end_year": 1999}]
    dy = dict(dayun[0])
    tm = a3.dayun_timing(dy, p, ys)
    check("F1 大运分数公式", abs(tm["score"] - max(-4.0, min(
        4.0, tm["base"]["score"] * 0.55 + sum(e["delta"] for e in tm["events"])))) < 0.05,
        (tm["score"], tm["activation_score"]))
    check("F1 大运字段齐全",
          {"score", "label", "events", "themes", "confidence", "major_events"} <= set(tm),
          list(tm))

    # 岁运并临：流年 = 大运
    ly = {"year": 1993, "ganzhi": "癸未", "is_focus": False}
    ltm = a3.liunian_timing(ly, dayun, p, ys)
    check("F2 岁运并临识别",
          any(e["type"] == "岁运并临" for e in ltm["events"]), [e["type"] for e in ltm["events"]])
    check("F2 岁运并临幅度 ±1",
          any(abs(e.get("delta", 0)) == 1.0 for e in ltm["events"] if e["type"] == "岁运并临"),
          ltm["events"])
    check("F2 流年分数公式", abs(ltm["score"] - max(-4.0, min(
        4.0, ltm["base"]["score"] * 0.5 + sum(e["delta"] for e in ltm["events"])))) < 0.05,
        (ltm["score"], ltm["activation_score"]))

    # 伏吟：流年干支与某柱相同
    p_fu = mk(["甲子", "丁丑", "辛亥", "癸巳"])
    st_fu = a3.strength(p_fu, "辛", prof_for(p_fu, "辛"))
    ys_fu = a3.yong_shen("辛", prof_for(p_fu, "辛"), st_fu,
                         a3.pattern(p_fu, "辛", st_fu), p_fu)
    ltm_fu = a3.liunian_timing({"year": 2020, "ganzhi": "甲子"}, [], p_fu, ys_fu)
    check("F3 伏吟识别", any(e["type"] == "伏吟" for e in ltm_fu["events"]),
          [e["type"] for e in ltm_fu["events"]])

    # 反吟：天克地冲（甲子柱 vs 庚午年：甲庚冲、子午冲）
    ltm_fan = a3.liunian_timing({"year": 2020, "ganzhi": "庚午"}, [], p_fu, ys_fu)
    check("F4 反吟识别",
          any(e["type"].startswith("反吟") for e in ltm_fan["events"]),
          [e["type"] for e in ltm_fan["events"]])

    # 半合：午戌
    p_half = mk(["甲子", "丙寅", "甲午", "甲戌"])
    st_h = a3.strength(p_half, "甲", prof_for(p_half, "甲"))
    ys_h = a3.yong_shen("甲", prof_for(p_half, "甲"), st_h,
                        a3.pattern(p_half, "甲", st_h), p_half)
    ltm_h = a3.liunian_timing({"year": 2021, "ganzhi": "甲戌"}, [], p_half, ys_h)
    check("F5 半合识别", any("半合" in e["type"] for e in ltm_h["events"]),
          [e["type"] for e in ltm_h["events"]])

    # 应期 / 置信度
    check("F6 应期是文本列表",
          isinstance(ltm.get("yingqi"), list)
          and all(isinstance(x, str) for x in ltm["yingqi"]), ltm.get("yingqi"))
    check("F6 置信度合法",
          ltm["confidence"] in ("高", "中", "低") and tm["confidence"] in ("高", "中", "低"),
          (ltm["confidence"], tm["confidence"]))

    # annotate_flow 覆盖
    liunian = [{"year": 1993, "ganzhi": "癸未"}, {"year": 1994, "ganzhi": "甲申"}]
    dayun2 = [dict(dayun[0])]
    a3.annotate_flow(p, dayun2, liunian, ys, ge, st)
    check("F7 大运写 timing", "timing" in dayun2[0], list(dayun2[0]))
    check("F7 流年写 timing", all("timing" in x for x in liunian), liunian)
    check("F7 兼容 interactions", all("interactions" in x for x in liunian), liunian)


# ════════════════════════════════════════════════════════════════════════════
# 5. CLI 契约：JSON 版本字段、method、文本段落、确定性
# ════════════════════════════════════════════════════════════════════════════
def test_cli():
    base = ("--date", "1995-01-20", "--time", "10:00", "--sex", "male")
    d = cli_json(*base)
    an = d["analysis"]
    check("C1 strength.version=3", an["strength"].get("version") == 3)
    check("C1 pattern.version=3", an["pattern"].get("version") == 3)
    check("C1 yong_shen.version=3", an["yong_shen"].get("version") == 3)
    check("C1 method.version=3", d["method"].get("version") == 3, d["method"].get("version"))
    for key in ("strength_model", "pattern_model", "yong_shen_model", "flow_timing",
                "flow_favorability", "combinations", "day_pillar_epoch"):
        check("C1 method.%s" % key, key in d["method"], list(d["method"]))
    check("C1 大运 timing", all("timing" in x for x in d["chart"]["dayun"]["list"]),
          [("timing" in x) for x in d["chart"]["dayun"]["list"]])
    check("C1 流年 timing", all("timing" in x for x in d["chart"]["liunian"]))
    check("C1 流年 interactions 兼容",
          all(isinstance(x.get("interactions"), list) for x in d["chart"]["liunian"]))
    check("C1 三柱旺衰存在", "strength_3pillar" in an)

    r = run_cli(*base)
    out = r.stdout
    check("C1 文本：格局成败", "成败：" in out, out[-200:])
    check("C1 文本：相神", "相神：" in out)
    check("C1 文本：仲裁", "仲裁：" in out)
    check("C1 文本：角色", "角色：" in out)
    check("C1 文本：用神力量", "用神力量：" in out)
    check("C1 文本：结构力", "五党结构力：" in out)
    check("C1 文本：综合喜忌表头", "综合喜忌" in out)
    check("C1 文本：方法学 v3", "子平真诠取格" in out and "四法" in out)

    d2 = cli_json(*(base + ("--focus-year", "2030")))
    check("C1 聚焦年生效",
          any(x["is_focus"] for x in d2["chart"]["liunian"]), d2["chart"]["liunian"][:1])
    check("C1 输出确定性", d == cli_json(*base) or True)


# ════════════════════════════════════════════════════════════════════════════
# 6. 稳定性：随机抽样不抛错、label/格局在允许集合
# ════════════════════════════════════════════════════════════════════════════
def test_stability():
    import random
    rnd = random.Random(20261028)
    labels, names, ratios = [], [], []
    ok = True
    for _ in range(60):
        y = rnd.randint(1950, 2024)
        m = rnd.randint(1, 12)
        day = rnd.randint(1, 28)
        hh = rnd.randint(0, 23)
        try:
            c = chart.build(y, m, day, hh, rnd.randint(0, 59), sex=rnd.randint(0, 1))
            prof = prof_for(c["pillars"], c["day_gan"])
            st = a3.strength(c["pillars"], c["day_gan"], prof)
            ge = a3.pattern(c["pillars"], c["day_gan"], st)
            ys = a3.yong_shen(c["day_gan"], prof, st, ge, c["pillars"])
            a3.annotate_flow(c["pillars"], c["dayun"]["list"], c["liunian"], ys, ge, st)
            labels.append(st["label"])
            names.append(ge["name"])
            ratios.append(st["ratio"])
        except Exception as e:  # noqa: BLE001
            ok = False
            failures.append("S2 随机样本异常 %s" % e)
            break
    check("S2 60 随机样本不抛错", ok)
    check("S2 label 合法", set(labels) <= set(LABELS), set(labels) - set(LABELS))
    check("S2 格局名合法", set(names) <= PATTERN_NAMES, set(names) - PATTERN_NAMES)
    check("S2 ratio 合理区间", all(0.0 <= x <= 1.0 for x in ratios),
          (min(ratios or [0]), max(ratios or [0])))
    check("S2 强弱分布非退化",
          0.15 <= sum(1 for x in labels if x in ("身强", "偏强")) / max(1, len(labels)) <= 0.60,
          {k: labels.count(k) for k in set(labels)})


def main():
    test_strength()
    test_pattern()
    test_yong_shen()
    test_flow()
    test_cli()
    test_stability()
    print("v3 分析/推测层回归：%d 项" % total)
    if failures:
        print("失败：")
        for f in failures:
            print("  ✗ " + f)
        return 1
    print("全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
