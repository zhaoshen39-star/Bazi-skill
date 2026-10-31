# -*- coding: utf-8 -*-
"""通俗版（plain）回归：结构完整性、去术语、预测可读性、CLI 契约、特殊格兼容。

运行：python tests/verify_plain.py
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

import plain as plainmod  # noqa: E402

failures = []
total = 0

BODY_KEYS = ["profile", "strengths", "watchouts", "money_work", "relationship",
             "health", "actions"]

BANNED = [
    "结构力", "十神", "用神", "喜神", "忌神", "仇神", "正财", "偏财", "正官",
    "七杀", "正印", "偏印", "比肩", "劫财", "食神", "伤官", "神煞", "纳音",
    "伏吟", "反吟", "岁运并临", "相神", "藏干", "干支", "大运", "流年",
    "格局", "身弱", "身强", "偏弱", "偏强", "建禄", "阳刃", "天乙贵人",
]

LEVELS = {"顺", "偏顺", "平稳", "偏吃力", "吃力"}


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


BASE = ["--longitude", "123.96", "--true-solar-time"]

CHART_BOY = cli_json("--date", "2004-06-12", "--time", "10:00", "--sex", "male",
                     "--focus-year", "2027", *BASE, "--plain")
CHART_1995 = cli_json("--date", "1995-01-20", "--time", "10:00", "--sex", "female",
                      "--focus-year", "2026", "--plain")
CHART_FROM_QIANG = cli_json("--date", "1969-08-14", "--time", "01:00", "--sex", "male",
                            "--focus-year", "2026", "--plain")
CHART_FROM_SHA = cli_json("--date", "1966-01-24", "--time", "11:00", "--sex", "male",
                          "--focus-year", "2026", "--plain")
CHART_FROM_ER = cli_json("--date", "1985-02-12", "--time", "13:00", "--sex", "female",
                         "--focus-year", "2026", "--plain")
CHART_NO_SEX = cli_json("--date", "1990-06-15", "--time", "08:00",
                        "--focus-year", "2026", "--plain")

P = CHART_BOY["plain"]


def text_of(plain):
    """把 body 字段拼成一段纯文本（不含 glossary / limits）。"""
    parts = [plain["one_line"], plain.get("current_decade", "")]
    for k in BODY_KEYS:
        parts.extend(plain.get(k) or [])
    for f in plain.get("forecast") or []:
        parts.extend([f["what"], f["do"], f["avoid"]])
    return "\n".join(str(x) for x in parts)


def test_structure():
    need = ["version", "one_line", "profile", "strengths", "watchouts",
            "money_work", "relationship", "health", "current_decade",
            "forecast", "actions", "limits", "glossary", "model"]
    check("P1 字段齐全", all(k in P for k in need), [k for k in need if k not in P])
    check("P2 一句话长度合理", 8 <= len(P["one_line"]) <= 80, len(P["one_line"]))
    check("P3 一句话以句号收尾", P["one_line"].endswith("。"), P["one_line"][-6:])
    check("P4 一句话含日主五行", "水" in P["one_line"], P["one_line"])
    check("P5 性格 1–5 条", 1 <= len(P["profile"]) <= 5, len(P["profile"]))
    check("P6 长处非空", len(P["strengths"]) >= 2, len(P["strengths"]))
    check("P7 短板非空", len(P["watchouts"]) >= 2, len(P["watchouts"]))
    check("P8 钱与工作非空", len(P["money_work"]) >= 2, len(P["money_work"]))
    check("P9 感情非空", len(P["relationship"]) >= 2, len(P["relationship"]))
    check("P10 身体含就医提示",
          any("就医" in x for x in P["health"]), P["health"])
    check("P11 建议正好 3 条", len(P["actions"]) == 3, len(P["actions"]))
    check("P12 名词翻译 ≥8 条", len(P["glossary"]) >= 8, len(P["glossary"]))
    check("P13 名词翻译字段完整",
          all(g.get("term") and g.get("plain") for g in P["glossary"]), P["glossary"][:2])
    check("P14 说明含免责", any("不是命定" in x for x in P["limits"]), P["limits"])


def test_forecast():
    fs = P["forecast"]
    check("P15 预测 4 年", len(fs) == 4, len(fs))
    check("P16 预测年份连续", [f["year"] for f in fs] == [2027, 2028, 2029, 2030],
          [f["year"] for f in fs])
    check("P17 预测等级合法", all(f["level"] in LEVELS for f in fs), [f["level"] for f in fs])
    check("P18 预测三条齐全",
          all(f.get("what") and f.get("do") and f.get("avoid") for f in fs))
    check("P19 预测含人话建议",
          all(any(w in f["do"] for w in ("守", "推进", "按部就班")) for f in fs),
          [f["do"] for f in fs])
    check("P20 置信度人话化",
          all(f["confidence"] in ("比较确定", "中等把握", "不太好说") for f in fs),
          [f["confidence"] for f in fs])
    check("P21 预测不出现固定断语",
          all("一定" not in f["what"] and "必然" not in f["what"] for f in fs))


def test_plain_language():
    body = text_of(P)
    hits = [t for t in BANNED if t in body]
    check("P22 正文无术语", not hits, hits)
    check("P23 正文无 None 字面量", "None" not in body)
    check("P24 正文有具体方向建议",
          any("方向" in x or "平台" in x or "现金" in x for x in P["actions"]), P["actions"])
    rendered = plainmod.render_plain_text(P)
    head, _, tail = rendered.partition("【名词翻译】")
    check("P25 渲染文本分节", "【一句话】" not in head and "一句话：" in head)
    check("P26 名词翻译表有解释", "日主" in tail and "身强 / 身弱" in tail)
    check("P27 正文长度可控", 800 <= len(rendered) <= 6000, len(rendered))


def test_determinism():
    again = plainmod.build_plain(CHART_BOY)
    check("P28 可复算", json.dumps(again, ensure_ascii=False, sort_keys=True)
          == json.dumps(P, ensure_ascii=False, sort_keys=True))


def test_special_and_edge():
    for name, data in (("从强", CHART_FROM_QIANG), ("从杀", CHART_FROM_SHA),
                       ("从儿", CHART_FROM_ER)):
        pl = data.get("plain") or {}
        ok = pl and all(pl.get(k) for k in ("one_line", "strengths", "actions"))
        check("P29 特殊格可出通俗版（%s）" % name, bool(ok), list(pl.keys())[:5])
    pl_q = CHART_FROM_QIANG.get("plain") or {}
    check("P30 特殊格特别说明",
          any("一边倒" in x for x in (pl_q.get("watchouts") or [])), pl_q.get("watchouts"))
    pl_n = CHART_NO_SEX.get("plain") or {}
    check("P31 缺性别也能出通俗版", bool(pl_n.get("one_line")), pl_n.get("one_line"))
    check("P32 缺性别感情段不崩", len(pl_n.get("relationship") or []) >= 1,
          pl_n.get("relationship"))


def test_cli():
    r = run_cli("--date", "2004-06-12", "--time", "10:00", "--sex", "male",
                "--focus-year", "2027", *BASE, "--plain-only")
    out = r.stdout or ""
    check("P33 --plain-only 成功", r.returncode == 0, r.stderr[-300:])
    check("P34 --plain-only 含排盘行", "【排盘】甲申 庚午 壬戌 乙巳" in out, out[:80])
    check("P35 --plain-only 含全部章节",
          all(k in out for k in ("一句话：", "【你是个什么样的人】", "【接下来几年怎么走】",
                                 "【给你三条建议】", "【名词翻译】", "【说明】")))
    check("P36 --plain-only 不含技术版", "【四柱】" not in out)
    r2 = run_cli("--date", "2004-06-12", "--time", "10:00", "--sex", "male",
                 "--focus-year", "2027", *BASE, "--plain")
    out2 = r2.stdout or ""
    check("P37 --plain 附带技术版", "【四柱】" in out2 and "技术版附在后面" in out2)
    r3 = run_cli("--date", "2004-06-12", "--time", "10:00", "--sex", "male",
                 "--focus-year", "2027", *BASE, "--json")
    d3 = json.loads(r3.stdout)
    check("P38 默认 JSON 不带 plain（兼容）", "plain" not in d3)
    check("P39 默认 JSON 仍有技术字段",
          "analysis" in d3 and "pattern" in d3["analysis"])
    d4 = json.loads(run_cli("--date", "2004-06-12", "--time", "10:00", "--sex", "male",
                            "--focus-year", "2027", *BASE, "--json", "--plain").stdout)
    check("P40 --json --plain 带 plain 字段", "plain" in d4 and "one_line" in d4["plain"])
    check("P41 --json --plain 不破坏技术字段",
          d4["analysis"]["pattern"]["version"] == 3
          and d4["analysis"]["strength"]["version"] == 3)
    r5 = run_cli("--date", "1990-06-15", "--time", "08:00", "--sex", "male",
                 "--time-unknown", "--focus-year", "2026", "--plain-only")
    check("P42 --time-unknown + --plain-only 成功", r5.returncode == 0, r5.stderr[-300:])
    check("P43 --time-unknown 文本含时辰提示", "时" in (r5.stdout or ""), (r5.stdout or "")[:120])
    r6 = run_cli("--date", "1990-06-15", "--time", "08:00", "--sex", "male",
                 "--focus-year", "2026", "--brief")
    ob = (r6.stdout or "").strip()
    check("P44 --brief 返回 0", r6.returncode == 0, r6.stderr[-300:])
    check("P45 --brief 长度 ≤400 字", 0 < len(ob) <= 400, len(ob))
    check("P46 --brief 含一句话", "【一句话】" in ob, ob[:80])
    check("P47 --brief 含说明", "【说明】" in ob)
    check("P48 --brief 不输出技术版", "【四柱】" not in ob and "═══ 排盘" not in ob)
    check("P49 render_brief_text 确定性",
          plainmod.render_brief_text(P) == plainmod.render_brief_text(P))
    check("P50 --brief 也带 plain 字段", "plain" in cli_json(
        "--date", "1990-06-15", "--time", "08:00", "--sex", "male",
        "--focus-year", "2026", "--brief"))


def main():
    test_structure()
    test_forecast()
    test_plain_language()
    test_determinism()
    test_special_and_edge()
    test_cli()
    print("通俗版解读回归：%d 项" % total)
    if failures:
        print("失败：")
        for f in failures:
            print("  ✗ " + f)
        return 1
    print("全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
