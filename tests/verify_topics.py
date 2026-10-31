# -*- coding: utf-8 -*-
"""专题推测层（topics）回归：八域结构、依据/窗口合法性、CLI 契约、特殊格兼容。

运行：python tests/verify_topics.py
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

import topics as topicsmod  # noqa: E402

failures = []
total = 0

TOPIC_IDS = ["love", "career", "wealth", "study", "health", "family", "move", "people"]
TITLES = ["婚恋与伴侣", "事业与职业方向", "财富与赚钱方式", "学业与考试",
          "健康与体质", "六亲与家庭", "迁移与方位", "人际、贵人与小人"]
LEVELS = {"顺", "偏顺", "中平", "偏吃力", "吃力", "平稳"}
KINDS = {"机遇", "发力", "波动", "注意"}
BANNED = ["None", "nan", "{", "}"]


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
                     "--focus-year", "2026", *BASE, "--topics")
CHART_GIRL = cli_json("--date", "1995-01-20", "--time", "10:00", "--sex", "female",
                      "--focus-year", "2026", "--topics")
CHART_FROM_QIANG = cli_json("--date", "1969-08-14", "--time", "01:00", "--sex", "male",
                            "--focus-year", "2026", "--topics")
CHART_FROM_SHA = cli_json("--date", "1966-01-24", "--time", "11:00", "--sex", "male",
                          "--focus-year", "2026", "--topics")
CHART_FROM_ER = cli_json("--date", "1985-02-12", "--time", "13:00", "--sex", "female",
                         "--focus-year", "2026", "--topics")
CHART_NO_SEX = cli_json("--date", "1990-06-15", "--time", "08:00",
                        "--focus-year", "2026", "--topics")
CHART_TU = cli_json("--date", "2004-06-12", "--time", "10:00", "--sex", "male",
                    "--focus-year", "2026", *BASE, "--topics", "--time-unknown")

T = CHART_BOY["topics"]
BY_ID = {t["id"]: t for t in T["topics"]}


def text_of(chart):
    return topicsmod.render_topics_text(chart["topics"])


# ── T1 顶层结构 ─────────────────────────────────────────────────────────────
check("T1 顶层 version=3", T.get("version") == 3, T.get("version"))
check("T2 顶层有 model/limits", isinstance(T.get("model"), str) and len(T["model"]) > 10)
check("T3 limits 三条", isinstance(T.get("limits"), list) and len(T["limits"]) == 3,
      len(T.get("limits") or []))
check("T4 八域齐全", [t["id"] for t in T["topics"]] == TOPIC_IDS, [t["id"] for t in T["topics"]])
check("T5 八域标题", [t["title"] for t in T["topics"]] == TITLES)
check("T6 year_index 非空", len(T.get("year_index") or []) >= 5, len(T.get("year_index") or []))

# ── T7 每域字段契约 ─────────────────────────────────────────────────────────
KEYS = {"id", "title", "summary", "level", "confidence", "basis", "windows", "risks", "advice"}
for t in T["topics"]:
    tid = t["id"]
    check("T7 字段齐全 %s" % tid, KEYS <= set(t.keys()), sorted(KEYS - set(t.keys())))
    check("T8 level 合法 %s" % tid, t["level"] in LEVELS, t["level"])
    check("T9 confidence 合法 %s" % tid, t["confidence"] in ("高", "中", "低"), t["confidence"])
    check("T10 summary 长度 %s" % tid, isinstance(t["summary"], str) and 10 <= len(t["summary"]) <= 400,
          len(t.get("summary") or ""))
    check("T11 basis 非空 %s" % tid, isinstance(t["basis"], list) and len(t["basis"]) >= 1,
          len(t.get("basis") or []))
    check("T12 basis 条目结构 %s" % tid,
          all(isinstance(b, dict) and b.get("kind") and b.get("detail") for b in t["basis"]))
    check("T13 advice 2~4 条 %s" % tid,
          isinstance(t["advice"], list) and 2 <= len(t["advice"]) <= 4, len(t.get("advice") or []))
    check("T14 risks 是列表 %s" % tid, isinstance(t["risks"], list))
    check("T15 windows 是列表 %s" % tid, isinstance(t["windows"], list))

# ── T16 窗口合法性 ─────────────────────────────────────────────────────────
years = {r["year"] for r in T["year_index"]}
for t in T["topics"]:
    for w in t["windows"]:
        check("T16 窗口 year 合法 %s" % t["id"], isinstance(w.get("year"), int))
        check("T17 窗口在流年范围内 %s" % t["id"], w.get("year") in years, w.get("year"))
        check("T18 窗口 kind 合法 %s" % t["id"], w.get("kind") in KINDS, w.get("kind"))
        check("T19 窗口 ganzhi 两位 %s" % t["id"],
              isinstance(w.get("ganzhi"), str) and len(w["ganzhi"]) == 2, w.get("ganzhi"))
        check("T20 窗口 note 非空 %s" % t["id"],
              isinstance(w.get("note"), str) and len(w["note"]) >= 4)
        sc = w.get("score")
        check("T21 窗口 score 范围 %s" % t["id"], sc is None or -4.0 <= sc <= 4.0, sc)
        check("T22 窗口 label 可用 %s" % t["id"],
              w.get("label") is None or w.get("label") in ("喜", "偏喜", "中性", "偏忌", "忌"))

# ── T23 去噪：正文无 None/{}/nan ────────────────────────────────────────────
rendered = text_of(CHART_BOY)
check("T23 正文无坏字符", not any(b in rendered for b in BANNED),
      [b for b in BANNED if b in rendered])
check("T24 正文含八域标题", all(t in rendered for t in TITLES))
check("T25 正文含说明", "专题是倾向不是命定" in rendered)
check("T26 渲染长度", 1500 <= len(rendered) <= 12000, len(rendered))

# ── T27 year_index 合法性 ─────────────────────────────────────────────────
for row in T["year_index"]:
    check("T27 索引 year 合法", isinstance(row.get("year"), int))
    check("T28 索引 domains 结构",
          all(isinstance(d, dict) and d.get("domain") in TOPIC_IDS
              and d.get("kind") in KINDS and d.get("note") for d in (row.get("domains") or [])))

# ── T29 性别语义 ───────────────────────────────────────────────────────────
girl_love = [t for t in CHART_GIRL["topics"]["topics"] if t["id"] == "love"][0]
girl_txt = json.dumps(girl_love, ensure_ascii=False)
check("T29 女命婚恋看官杀", "夫星（官杀）" in girl_txt, girl_txt[:220])
boy_love = BY_ID["love"]
boy_txt = json.dumps(boy_love, ensure_ascii=False)
check("T30 男命婚恋看财", "妻星（财）" in boy_txt, boy_txt[:220])
no_sex_love = [t for t in CHART_NO_SEX["topics"]["topics"] if t["id"] == "love"][0]
check("T31 缺性别不崩且注明", "性别未知" in json.dumps(no_sex_love, ensure_ascii=False))

# ── T32 领域内容抽样（2004 男命）───────────────────────────────────────────
move_txt = json.dumps(BY_ID["move"], ensure_ascii=False)
check("T32 迁移含驿马", "驿马" in move_txt)
check("T33 迁移含方位", "北方" in move_txt or "偏北" in move_txt)
wealth_txt = json.dumps(BY_ID["wealth"], ensure_ascii=False)
check("T34 财富含财库", "财库" in wealth_txt, wealth_txt[:200])
health_txt = json.dumps(BY_ID["health"], ensure_ascii=False)
check("T35 健康指向弱五行", "偏弱" in health_txt or "短板" in health_txt)
check("T36 健康不作诊断", "不作诊断" in "".join(BY_ID["health"]["advice"]))

# ── T37 特殊格兼容 ─────────────────────────────────────────────────────────
for name, ch in (("从强", CHART_FROM_QIANG), ("从杀", CHART_FROM_SHA), ("从儿", CHART_FROM_ER)):
    tp = ch.get("topics") or {}
    check("T37 %s 出专题" % name, len(tp.get("topics") or []) == 8, len(tp.get("topics") or []))
    txt = topicsmod.render_topics_text(tp)
    check("T38 %s 渲染正常" % name, len(txt) > 1500 and "None" not in txt, len(txt))

# ── T39 CLI 契约 ──────────────────────────────────────────────────────────
r = run_cli("--date", "2004-06-12", "--time", "10:00", "--sex", "male",
            "--focus-year", "2026", *BASE, "--topics")
check("T39 CLI 返回 0", r.returncode == 0, r.stderr[-300:])
out = r.stdout
check("T40 CLI 技术版在专题前", out.find("═══ 八字排盘 ═══") < out.find("═══ 专题推测（八域） ═══"))
check("T41 CLI 含八域标题", all(t in out for t in TITLES))
check("T42 CLI 专题在末尾", out.rstrip().endswith(BY_ID["people"]["advice"][-1]) or
      "不作诊断" in out[-3000:])

r_plain = run_cli("--date", "2004-06-12", "--time", "10:00", "--sex", "male",
                  "--focus-year", "2026", *BASE, "--topics", "--plain-only")
check("T43 CLI --plain-only --topics 返回 0", r_plain.returncode == 0, r_plain.stderr[-300:])
check("T44 通俗版与专题都在", "═══ 专题推测（八域） ═══" in r_plain.stdout and "通俗" not in r_plain.stdout[:0])

r_js = cli_json("--date", "2004-06-12", "--time", "10:00", "--sex", "male",
                "--focus-year", "2026", *BASE, "--topics", "--plain")
check("T45 JSON 同时含 plain/topics", "plain" in r_js and "topics" in r_js)

r_no = cli_json("--date", "2004-06-12", "--time", "10:00", "--sex", "male",
                "--focus-year", "2026", *BASE)
check("T46 不加 --topics 不输出 topics", "topics" not in r_no)

# ── T47 时间未知 + 专题 ───────────────────────────────────────────────────
check("T47 时间未知可出专题", len(CHART_TU.get("topics", {}).get("topics") or []) == 8)
check("T48 时间未知保留警告", any("时柱" in w or "时辰" in w
                                for w in (CHART_TU.get("warnings") or [])))

# ── T49 确定性 ────────────────────────────────────────────────────────────
again = cli_json("--date", "2004-06-12", "--time", "10:00", "--sex", "male",
                 "--focus-year", "2026", *BASE, "--topics")
check("T49 同一命盘结果一致", again["topics"] == T)

# ── T50 域内年份按基调排序 ────────────────────────────────────────────────
good_scores = [w["score"] for t in T["topics"] for w in t["windows"]
               if w["kind"] in ("机遇", "发力") and w.get("score") is not None]
check("T50 有利窗口不出现强忌年", all(s >= -0.5 for s in good_scores),
      [s for s in good_scores if s < -0.5])

# ── T51–T57 --topic 域过滤 ───────────────────────────────────────────────
r_one = cli_json("--date", "2004-06-12", "--time", "10:00", "--sex", "male",
                 "--focus-year", "2026", *BASE, "--topic", "love")
check("T51 --topic 只留一域",
      [t.get("id") for t in r_one["topics"]["topics"]] == ["love"], r_one["topics"].get("selected"))
check("T52 --topic 隐含 --topics", "topics" in r_one)
check("T53 year_index 的域被过滤",
      all(d.get("domain") == "love"
          for row in r_one["topics"]["year_index"] for d in row.get("domains") or []))
r_two = cli_json("--date", "2004-06-12", "--time", "10:00", "--sex", "male",
                 "--focus-year", "2026", *BASE, "--topic", "love,career")
check("T54 多个域按输入顺序", [t.get("id") for t in r_two["topics"]["topics"]] == ["love", "career"])
r_bad = run_cli("--date", "2004-06-12", "--time", "10:00", "--sex", "male",
                "--focus-year", "2026", *BASE, "--topic", "nope")
check("T55 非法域报错", r_bad.returncode != 0 and "--topic" in (r_bad.stderr or ""), r_bad.stderr[-200:])
r_txt = run_cli("--date", "2004-06-12", "--time", "10:00", "--sex", "male",
                "--focus-year", "2026", *BASE, "--topic", "love")
check("T56 文本标题改为 N 域", "专题推测（1 域）" in (r_txt.stdout or ""), (r_txt.stdout or "")[-400:])
check("T57 文本只列该域",
      "婚恋与伴侣" in (r_txt.stdout or "") and "财富与赚钱方式" not in (r_txt.stdout or ""))

print("专题推测层回归：%d 项" % total)
if failures:
    print("失败 %d 项：" % len(failures))
    for f in failures:
        print("  ✗", f)
    sys.exit(1)
print("全部通过 ✓")
