# -*- coding: utf-8 -*-
"""八字排盘与分析 CLI。

用法示例：
  python bazi.py --date 1990-06-15 --time 12:00 --sex male \
      --zone Asia/Shanghai --longitude 116.4 --true-solar-time
  python bazi.py --date 1990-06-15 --time 12:00 --sex female --json

时间处理约定（重要）：
  * --date/--time 是「出生证明上记录的当地钟表时间」；
  * 用 IANA 时区（默认 Asia/Shanghai）换算 UTC，自动扣除夏令时（如中国 1986-1991），
    得到排盘用的「标准时」；
  * 加 --true-solar-time --longitude 时改用「真太阳时」= 地方平太阳时 + 均时差；
  * 八字月/年柱按节气交节时刻划分，日柱按儒略日连续干支推算。
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chart  # noqa: E402
import analysis  # noqa: E402
import analysis_v3 as a3  # noqa: E402
import plain as plainmod  # noqa: E402
import topics as topicsmod  # noqa: E402
import divination as divmod  # noqa: E402
import ziwei as ziweimod  # noqa: E402
import fusion as fusionmod  # noqa: E402
try:  # 可选模块：文件缺失时八字主体仍可运行
    import astrology as astromod  # noqa: E402
except Exception:  # pragma: no cover
    astromod = None
try:
    import numerology as nummod  # noqa: E402
except Exception:  # pragma: no cover
    nummod = None
try:
    import qimen as qimenmod  # noqa: E402
except Exception:  # pragma: no cover
    qimenmod = None


# ── 均时差（Equation of Time）────────────────────────────────────────────────
def equation_of_time(utc_dt):
    """均时差，单位分钟（真太阳时 - 平太阳时）。NOAA 拟合式，1800-2100 内约 ±0.5 分钟。"""
    doy = utc_dt.timetuple().tm_yday
    frac = (utc_dt.hour - 12) / 24.0 + utc_dt.minute / 1440.0 + utc_dt.second / 86400.0
    gamma = 2.0 * math.pi / 365.0 * (doy - 1 + frac)
    return 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )


def used_from_utc(utc_dt, t):
    """把 UTC 绝对时刻换算到「排盘采用的时间标尺」（标准时或真太阳时）。"""
    if t["used_kind"] == "tst":
        eot = equation_of_time(utc_dt)
        return (utc_dt + timedelta(hours=t["longitude"] / 15.0)
                + timedelta(minutes=eot)).replace(tzinfo=None)
    return (utc_dt + timedelta(hours=t["standard_offset_hours"])).replace(tzinfo=None)


def used_from_cst(cst_str, t):
    """把北京时间（UTC+8）字符串换算到排盘采用的时间标尺。"""
    dt = datetime.strptime(cst_str, "%Y-%m-%d %H:%M:%S")
    utc = (dt - timedelta(hours=8)).replace(tzinfo=timezone.utc)
    return used_from_utc(utc, t)


def resolve_time(year, month, day, hour, minute, second, zone_name,
                 longitude, use_true_solar):
    """把「记录的钟表时间」解析为标准时 / 真太阳时，并给出 UTC 与 UTC+8 等价时刻。

    返回的 used_dt 用于日柱/时柱；cst_dt 用于年柱/月柱与起运（节气表按 UTC+8）。
    """
    try:
        zone = ZoneInfo(zone_name)
    except Exception:
        raise SystemExit(
            "无法识别的时区 %r。请使用 IANA 时区名，例如 Asia/Shanghai。" % zone_name)
    naive = datetime(year, month, day, hour, minute, second)
    warnings = []

    aware = naive.replace(tzinfo=zone)
    # 夏令时「拨快」跳过的本地时间 / 「回拨」重复的本地时间
    back = aware.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
    if back != naive:
        warnings.append(
            "该本地时间落在夏令时拨快的跳过区间（钟表不存在），已按 UTC 等效时刻换算；"
            "请核对出生时间记录。")
    else:
        alt = naive.replace(tzinfo=zone, fold=1)
        if alt.utcoffset() != aware.utcoffset():
            warnings.append(
                "该本地时间在夏令时回拨时出现两次（歧义），已按较早的一次（fold=0）换算；"
                "如记录的是较晚一次，请注明。")

    utc = aware.astimezone(timezone.utc)
    offset = aware.utcoffset()
    dst = aware.dst() or timedelta(0)
    standard_offset = offset - dst  # 去掉夏令时后的标准时偏移
    standard = (utc + standard_offset).replace(tzinfo=None)
    cst_dt = (utc + timedelta(hours=8)).replace(tzinfo=None)

    result = {
        "civil": naive.strftime("%Y-%m-%d %H:%M:%S"),
        "zone": zone_name,
        "utc_offset_hours": offset.total_seconds() / 3600.0,
        "dst_hours": dst.total_seconds() / 3600.0,
        "standard_offset_hours": standard_offset.total_seconds() / 3600.0,
        "utc": utc.strftime("%Y-%m-%d %H:%M:%S"),
        "cst": cst_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "cst_dt": cst_dt,
        "utc_dt": utc,
        "standard": standard.strftime("%Y-%m-%d %H:%M:%S"),
        "used": standard.strftime("%Y-%m-%d %H:%M:%S"),
        "used_dt": standard,
        "used_kind": "standard",
        "used_label": "标准时" if dst == timedelta(0) else "标准时（已扣除夏令时）",
        "true_solar": None,
        "longitude": longitude,
        "warnings": warnings,
    }
    if dst != timedelta(0):
        result["dst_note"] = "记录的钟表时间处于夏令时期间，已自动减去 %g 小时得到标准时。" % (
            dst.total_seconds() / 3600.0)

    if use_true_solar:
        if longitude is None:
            raise SystemExit("--true-solar-time 需要同时提供 --longitude（出生地经度，东经为正）。")
        eot = equation_of_time(utc)
        tst = (utc + timedelta(hours=longitude / 15.0) + timedelta(minutes=eot)).replace(tzinfo=None)
        result["true_solar"] = tst.strftime("%Y-%m-%d %H:%M:%S")
        result["equation_of_time_minutes"] = round(eot, 2)
        result["lon_correction_minutes"] = round((longitude - standard_offset.total_seconds() / 3600.0 * 15.0) * 4, 2)
        result["used"] = tst.strftime("%Y-%m-%d %H:%M:%S")
        result["used_dt"] = tst
        result["used_kind"] = "tst"
        result["used_label"] = "真太阳时"
    return result


# ── 文本排版（按东亚显示宽度对齐）───────────────────────────────────────────
def _dw(text):
    import unicodedata
    width = 0
    for ch in str(text):
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def _pad(text, width, align="left"):
    gap = width - _dw(text)
    if gap <= 0:
        return str(text)
    if align == "right":
        return " " * gap + str(text)
    return str(text) + " " * gap


def _row(cells, widths, aligns=None):
    aligns = aligns or ["left"] * len(cells)
    return "  ".join(_pad(c, w, a) for c, w, a in zip(cells, widths, aligns))


def _table(header, rows, aligns=None):
    """按内容自动计算列宽，返回带表头的表格行列表。"""
    n = len(header)
    widths = [0] * n
    for r in [header] + rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], _dw(cell))
    aligns = aligns or ["left"] * n
    return [_row(r, widths, aligns) for r in [header] + rows]


def _el_text(el):
    """五行 → 「火（丙丁）」形式；空值安全。"""
    if not el:
        return "—"
    return "%s（%s）" % (el, a3.ELEMENT_TO_GAN_TEXT.get(el, ""))


# ── 构建完整报告 ─────────────────────────────────────────────────────────────
def build_report(args):
    t = resolve_time(
        args.date.year, args.date.month, args.date.day,
        args.time.hour, args.time.minute, args.time.second,
        args.zone, args.longitude, args.true_solar_time,
    )
    used = t["used_dt"]
    cst = t["cst_dt"]

    sex = {"male": 1, "m": 1, "男": 1, "female": 0, "f": 0, "女": 0}.get(
        (args.sex or "").lower(), None)
    if args.sex is None:
        sex = None
    elif sex is None:
        raise SystemExit("--sex 只接受 male/female/m/f/男/女")

    focus_year = args.focus_year if args.focus_year else datetime.now().year
    display_dt = datetime.strptime(t["standard"], "%Y-%m-%d %H:%M:%S")
    c = chart.build(
        used.year, used.month, used.day, used.hour, used.minute, used.second,
        sect=args.sect, sex=sex, dayun_count=args.dayun_count,
        qiyun_sect=args.qiyun_sect, focus_year=focus_year, cst=cst,
        display=display_dt,
    )
    if args.liuyue:
        c["liuyue"] = chart.liuyue(c["day_gan"], focus_year)
    day_gan = c["day_gan"]

    profile = analysis.wuxing_profile(c["pillars"], day_gan)
    # 旺衰/格局/喜用 用 v3 模型（结构力加权、子平取格、四法合参）
    st = a3.strength(c["pillars"], day_gan, profile)
    st3 = None
    if args.time_unknown:
        prof3 = analysis.wuxing_profile(c["pillars"][:3], day_gan)
        st3 = a3.strength(c["pillars"][:3], day_gan, prof3)
    ge = a3.pattern(c["pillars"], day_gan, st)
    ys = a3.yong_shen(day_gan, profile, st, ge, c["pillars"])
    ss = analysis.shen_sha(c["pillars"], day_gan)
    rel = analysis.relations(c["pillars"])
    comb = analysis.combinations(c["pillars"], day_gan)

    # 大运 / 流年：基调打分（v3 用神角色加权）+ 与命局/彼此的引动
    for dy in c.get("dayun", {}).get("list", []):
        dy["favorability"] = a3.flow_favorability(ys, dy["ganzhi"])
    for ly in c.get("liunian", []):
        ly["favorability"] = a3.flow_favorability(ys, ly["ganzhi"])
    a3.annotate_flow(c["pillars"], c.get("dayun", {}).get("list", []),
                     c.get("liunian", []), ys, ge, st)

    warnings = list(t.get("warnings", []))
    prev_jie = c["jieqi"]["prev_jie"]
    nxt = c["jieqi"]["next_jie"]
    for label, jq in (("上一个节", prev_jie), ("下一个节", nxt)):
        if not jq:
            continue
        jq_used = used_from_cst(jq["time"], t)
        diff_min = abs((used - jq_used).total_seconds()) / 60.0
        if diff_min <= 30:
            warnings.append(
                "%s「%s」在 %s（按%s显示），与所用出生时刻仅差 %.0f 分钟："
                "月柱/年柱对校正方式敏感，请务必核对出生时间、时区与真太阳时设定。" % (
                    label, jq["name"], jq_used.strftime("%Y-%m-%d %H:%M:%S"),
                    t["used_label"], diff_min))
    if t["dst_hours"]:
        warnings.append(t.get("dst_note", ""))
    if sex is None:
        warnings.append("未提供性别（--sex），因此未计算大运；大运方向依赖性别，建议补充。")
    if used.hour == 23:
        both = {}
        for s in (1, 2):
            cc = chart.build(used.year, used.month, used.day, used.hour, used.minute,
                             used.second, sect=s, sex=sex, dayun_count=1,
                             qiyun_sect=args.qiyun_sect, focus_year=focus_year,
                             cst=cst)
            both[s] = (cc["pillars"][2]["ganzhi"], cc["pillars"][3]["ganzhi"])
        warnings.append(
            "生于晚子时（23:00–23:59）：流派1 日柱 %s / 时柱 %s；流派2 日柱 %s / 时柱 %s。"
            "本报告采用流派%d，两个流派都应与用户确认（--sect 1/2）。" % (
                both[1][0], both[1][1], both[2][0], both[2][1], args.sect))
    c["time_pillar_reliable"] = not args.time_unknown
    c["assumed_time"] = t["used"]
    if args.time_unknown:
        warnings.append(
            "出生时辰未知：时柱按传入的 %s 假定计算，不可信；旺衰评分、喜用、神煞、合冲中含时柱成分，"
            "仅供参考。请只把年/月/日三柱的结构当作可靠信息，并优先向用户确认时辰。" % t["used"])

    return {
        "input": {
            "date": args.date.isoformat(),
            "time": args.time.strftime("%H:%M:%S"),
            "time_unknown": bool(args.time_unknown),
            "lunar_input": getattr(args, "lunar_input", None),
            "sex": args.sex,
            "sect": args.sect,
            "qiyun_sect": args.qiyun_sect,
            "zone": args.zone,
            "longitude": args.longitude,
            "latitude": getattr(args, "latitude", None),
            "true_solar_time": args.true_solar_time,
        },
        "time": {k: v for k, v in t.items() if not k.endswith("_dt")},
        "jieqi_used": {
            "scale": t["used_label"],
            "prev_jie": {"name": prev_jie["name"],
                         "time": used_from_cst(prev_jie["time"], t).strftime("%Y-%m-%d %H:%M:%S")}
            if prev_jie else None,
            "next_jie": {"name": nxt["name"],
                         "time": used_from_cst(nxt["time"], t).strftime("%Y-%m-%d %H:%M:%S")}
            if nxt else None,
        },
        "chart": c,
        "analysis": {
            "wuxing": profile,
            "strength": st,
            "strength_3pillar": st3,
            "pattern": ge,
            "combinations": comb,
            "yong_shen": ys,
            "shen_sha": ss,
            "relations": rel,
        },
        "warnings": warnings,
        "method": {
            "version": 3,
            "day_pillar_epoch": "2000-01-07 = 甲子日（儒略日连续干支）",
            "year_boundary": "立春交节时刻",
            "month_boundary": "十二节（立春/惊蛰/清明/立夏/芒种/小暑/立秋/白露/寒露/立冬/大雪/小寒）交节时刻",
            "zi_hour": "23:00-00:59 为子时；sect=2 日柱不换、sect=1 日柱换次日",
            "wuxing_weights": "天干各 1.0；地支年1.0/月1.6/日1.2/时1.0，藏干按 1/2/3 个分别 1.0；0.7/0.3；0.6/0.25/0.15"
                              "（五行力量表沿用此口径；旺衰改用 structure_force 结构力口径）",
            "strength_model": a3.STRENGTH_MODEL,
            "pattern_model": a3.PATTERN_NOTE,
            "yong_shen_model": "扶抑/调候/通关/病药四法各自出结论，再按"
                               "「特殊格 > 破格救应 > 调候急需 > 病药 > 扶抑」仲裁；"
                               "调候按《穷通宝鉴》120 格（日干×月支）取首选/辅佐天干，"
                               "寒暖指数 = 月令温度基准 + 2.0×(火-水)/总结构力，"
                               "|指数|≥1.2 判急需、≥0.6 判需要，只用于定急缓。",
            "flow_favorability": "大运/流年基调分：用神×2.2、喜神×1.3、忌神×-1.9、仇神×-1.0、闲神 0；"
                                 "天干/地支本气各×1.0，中余气×0.3；截断到 [-4,4]。",
            "flow_timing": "引动分叠加：地支冲/合/刑/害/破/自刑、天干合/冲、伏吟/反吟（天克地冲）、"
                           "半合局、岁运并临；大运=基调×0.55+引动，流年=基调×0.5+引动（岁运并临±1.0）。"
                           "领域按引动十神与实际落宫给出；置信度=基调与引动是否同向。",
            "combinations": "十神结构组合按「透干 > 月令本气 > 其他本气」取级，并按 rank（3=透干/2=月令本气/1=藏支）排序；藏支组合不列；成格仍需复核旺衰与破格因素。",
            "disclaimer": "计算部分是可复算的历法；旺衰/格局/喜用属于术数模型，非科学结论，不用于医疗、法律、投资等决策。",
        },
    }


# ── 文本渲染 ─────────────────────────────────────────────────────────────────
def render_text(report):
    t = report["time"]
    c = report["chart"]
    a = report["analysis"]
    lines = []

    lines.append("═══ 八字排盘 ═══")
    lines.append("")
    lines.append("【输入与时间校正】")
    li = report["input"].get("lunar_input")
    if li:
        lines.append("  农历输入　　　：%d年%s月%s日 → 公历 %s" % (
            li["year"], ("闰" if li["leap"] else "") + str(li["month"]),
            li["day"], li["solar"]))
    lines.append("  出生地钟表时间：%s（%s，UTC%+g%s）" % (
        t["civil"], t["zone"], t["utc_offset_hours"],
        "，夏令时" if t["dst_hours"] else ""))
    lines.append("  换算标准时　　：%s" % t["standard"])
    if t["true_solar"]:
        lines.append("  真太阳时　　　：%s（经度 %g°E，经度差 %+.1f 分，均时差 %+.1f 分）" % (
            t["true_solar"], t["longitude"],
            t["lon_correction_minutes"], t["equation_of_time_minutes"]))
    lines.append("  排盘采用　　　：%s %s" % (t["used_label"], t["used"]))
    lines.append("  农历　　　　　：%s；生肖（按立春）：%s" % (
        c["lunar"]["text"], c["lunar"]["shengxiao"]))
    jq = report.get("jieqi_used") or {}
    if jq.get("prev_jie"):
        lines.append("  前一节（%s）：%s %s" % (
            jq.get("scale", ""), jq["prev_jie"]["name"], jq["prev_jie"]["time"]))
    if jq.get("next_jie"):
        lines.append("  后一节（%s）：%s %s" % (
            jq.get("scale", ""), jq["next_jie"]["name"], jq["next_jie"]["time"]))
    lines.append("  边界标尺　　　：年/月柱按北京时间(UTC+8)的节气时刻；日/时柱按排盘采用时间")
    lines.append("")

    # 四柱表
    p = c["pillars"]
    header = ["", "年柱", "月柱", "日柱", "时柱"]
    body = [
        ["天干"] + [x["gan"] for x in p],
        ["地支"] + [x["zhi"] for x in p],
        ["十神"] + [("日主" if i == 2 else x["shishen_gan"]) for i, x in enumerate(p)],
        ["藏干"] + ["/".join(x["canggan"]) for x in p],
        ["藏神"] + ["/".join(x["canggan_shishen"]) for x in p],
        ["纳音"] + [x["nayin"] for x in p],
        ["地势"] + [x["dishi"] for x in p],
        ["旬空"] + [x["xunkong"] for x in p],
    ]
    lines.append("【四柱】")
    lines.extend(_table(header, body))
    if not c.get("time_pillar_reliable", True):
        lines.append("  ⚠ 时辰未知：时柱按传入的 %s 假定计算，仅占位；旺衰/喜用等含时柱成分，仅供参考。"
                     % c.get("assumed_time", "假定时刻"))
    lines.append("")
    lines.append("  胎元：%s（%s）　命宫：%s（%s）　身宫：%s（%s）" % (
        c["taiyuan"]["ganzhi"], c["taiyuan"]["nayin"],
        c["minggong"]["ganzhi"], c["minggong"]["nayin"],
        c["shengong"]["ganzhi"], c["shengong"]["nayin"]))
    lines.append("")

    # 大运
    if "dayun" in c:
        d = c["dayun"]
        lines.append("【大运】方向：%s；起运：%s（%s）" % (
            "顺行" if d["forward"] else "逆行", d["start"]["text"], d["start"]["solar"]))
        lines.append("  （起运/交运时刻按北京时间 UTC+8；出生在境外时区时可差数小时，日期级判断不受影响）")
        head = ["序", "大运", "十神(干)", "综合喜忌", "起始年", "年龄(虚岁)", "交运时刻"]
        rows = []
        fy = report.get("focus_year", 2026)
        for i, dy in enumerate(d["list"], 1):
            mark = "（当前）" if dy["start_year"] <= fy <= dy["end_year"] else ""
            fav = dy.get("favorability") or {}
            tm = dy.get("timing") or {}
            rows.append([str(i), dy["ganzhi"] + mark, dy["shishen_gan"],
                         "%s(%+.1f)" % (tm.get("label") or fav.get("label", "—"),
                                        tm.get("score") if tm else fav.get("score", 0.0)),
                         "%d-%d" % (dy["start_year"], dy["end_year"]),
                         "%d-%d" % (dy["start_age"], dy["end_age"]),
                         dy["jiaoyun"]])
        lines.extend(_table(head, rows))
        lines.append("  综合喜忌＝基调×0.55＋与命局的合冲引动（见方法学）；只表十年基调与结构，不是事件预测。")
        cur = None
        for dy in d["list"]:
            if dy["start_year"] <= fy <= dy["end_year"]:
                cur = dy
                break
        if cur and cur.get("timing"):
            tm = cur["timing"]
            lines.append("  当前大运 %s（%d-%d）：综合 %s %+.1f（基调 %s %+.1f，引动 %+.2f，置信度%s）" % (
                cur["ganzhi"], cur["start_year"], cur["end_year"],
                tm["label"], tm["score"], tm["base"]["label"], tm["base"]["score"],
                tm["activation_score"], tm["confidence"]))
            if tm.get("themes"):
                lines.append("    领域：%s" % "、".join(tm["themes"]))
            if tm.get("major_events"):
                lines.append("    重大引动：%s" % "；".join(
                    e["detail"] for e in tm["major_events"][:4]))
            else:
                lines.append("    与命局无明显合冲引动，以基调为主。")
        other = [dy for dy in d["list"] if dy is not cur and dy.get("timing")
                 and abs(dy["timing"].get("activation_score", 0)) >= 0.6]
        if other:
            lines.append("  引动较明显的大运：")
            for dy in other[:5]:
                tm = dy["timing"]
                lines.append("    %s（%d-%d，%+.1f）：%s" % (
                    dy["ganzhi"], dy["start_year"], dy["end_year"],
                    tm["activation_score"],
                    "；".join(e["detail"] for e in tm["major_events"][:2]) or "基调之外的小引动"))
        lines.append("")

    # 流年（聚焦年 ±6）
    lines.append("【流年】聚焦 %d（%s）" % (report.get("focus_year", 2026),
                                          [x["ganzhi"] for x in c["liunian"] if x["is_focus"]][0]))
    rows = [["年份", "干支", "十神(干)", "综合喜忌", "所属大运", "藏神"]]
    for ly in c["liunian"]:
        fav = ly.get("favorability") or {}
        tm = ly.get("timing") or {}
        rows.append([str(ly["year"]), ly["ganzhi"], ly["shishen_gan"],
                     "%s(%+.1f)" % (tm.get("label") or fav.get("label", "—"),
                                    tm.get("score") if tm else fav.get("score", 0.0)),
                     ly.get("dayun_ganzhi") or "—",
                     "/".join(ly["shishen_zhi"])])
    lines.extend(_table(rows[0], rows[1:]))
    lines.append("  （按公历年列出；立春前出生者，该公历年干支仍属上一年）")

    # 流年要点：仅列聚焦年 ±3 内、且与命局/大运有互动的年份
    fy = report.get("focus_year", 2026)
    focus_items = [
        ly for ly in c["liunian"]
        if abs(ly["year"] - fy) <= 3 and ly.get("interactions")
    ]
    if focus_items:
        lines.append("【流年要点】（综合＝基调×0.5＋命局/大运引动，见方法学）")
        for ly in focus_items:
            tm = ly.get("timing") or {}
            fav = ly.get("favorability") or {}
            if tm:
                lines.append("  %d %s（基调：%s %+.1f；综合 %s %+.1f，引动 %+.2f，置信度%s）" % (
                    ly["year"], ly["ganzhi"], tm["base"]["label"], tm["base"]["score"],
                    tm["label"], tm["score"], tm["activation_score"], tm["confidence"]))
                if tm.get("themes"):
                    lines.append("      领域：%s" % "、".join(tm["themes"]))
                if tm.get("yingqi"):
                    lines.append("      应期：%s" % "；".join(tm["yingqi"][:4]))
            else:
                lines.append("  %d %s（基调：%s %+.1f）：%s" % (
                    ly["year"], ly["ganzhi"], fav.get("label", "—"), fav.get("score", 0.0),
                    "；".join(ly.get("interactions") or [])[:120]))
    lines.append("")

    # 流月（仅 --liuyue 时输出）
    if c.get("liuyue"):
        lines.append("【流月】%d 年（以节气为界，寅月起）" % report.get("focus_year", 2026))
        mrows = [["月序", "节气区间", "干支", "十神(干)", "藏神"]]
        for i, m in enumerate(c["liuyue"], 1):
            span = "—"
            if m.get("start") and m.get("end"):
                span = "%s~%s" % (m["start"][5:10].replace("-", "/"),
                                  m["end"][5:10].replace("-", "/"))
            mrows.append([str(i), span, m["ganzhi"], m["shishen_gan"],
                          "/".join(m["shishen_zhi"])])
        lines.extend(_table(mrows[0], mrows[1:]))
        lines.append("  （节气区间为北京时间；境外出生或真太阳时下需换算后再对照）")
        lines.append("")

    # 五行
    lines.append("【五行力量】加权占比（模型见文末方法）")
    totals = a["wuxing"]["totals"]
    pct = a["wuxing"]["percent"]
    seg = "  ".join("%s %5.2f (%4.1f%%)" % (e, totals[e], pct[e]) for e in analysis.ELEMENTS)
    lines.append("  " + seg)
    same = a["strength"]["same_party"]
    other = a["strength"]["other_party"]
    lines.append("  同党（比劫+印 %s）：%.2f（%.1f%%）　异党（食伤+财+官杀）：%.2f（%.1f%%）" % (
        "/".join(same["elements"]), same["total"], same["percent"],
        other["total"], other["percent"]))
    lines.append("  日主：%s（%s）　旺衰：%s（综合评分 %.3f%s）　月令：%s（%s，日主处「%s」地）" % (
        c["day_gan"], c["day_gan_wuxing"], a["strength"]["label"], a["strength"]["score"],
        "，含时柱假定" if not c.get("time_pillar_reliable", True) else "",
        a["strength"]["de_ling"]["month_zhi"],
        a["strength"]["de_ling"]["month_element"],
        a["strength"]["de_ling"]["state"]))
    roots = a["strength"]["de_di"]
    lines.append("  得地：%s　天干同党：%d 个" % (
        "、".join(roots) if roots else "无根", a["strength"]["de_shi_heads"]))
    for h in a["strength"].get("special_hints", []):
        lines.append("  · " + h)
    stv = a["strength"]
    sh = stv.get("party_shares") or {}
    if sh:
        lines.append("  五党结构力：比劫 %.1f%%／印星 %.1f%%／食伤 %.1f%%／财星 %.1f%%／官杀 %.1f%%" % (
            sh.get("比劫", 0) * 100, sh.get("印星", 0) * 100, sh.get("食伤", 0) * 100,
            sh.get("财星", 0) * 100, sh.get("官杀", 0) * 100))
    if stv.get("structure_notes"):
        lines.append("  结构折损：%s" % "；".join(str(n.get("detail", n)) for n in stv["structure_notes"][:6]))
    if stv.get("special"):
        lines.append("  ⚑ 特殊格：%s（%s）" % (
            stv["special"]["type"], "；".join(stv["special"].get("reasons") or [])))
    lines.append("  旺衰置信度：%s（越接近分级阈值越不确定；阈值 %s）" % (
        stv.get("confidence", "—"), "、".join("%.2f" % x for x in a3.STRENGTH_CUTS)))
    if a.get("strength_3pillar"):
        s3 = a["strength_3pillar"]
        lines.append("  三柱（不含时柱）旺衰：%s（评分 %.3f）——时辰未知时以这一版为准" % (
            s3["label"], s3["score"]))
    lines.append("")

    # 格局与喜用
    ge = a["pattern"]
    lines.append("【格局】%s（月令 %s，%s）" % (
        ge["name"], ge["month_zhi"], ge.get("basis", "本气%s → %s" % (
            ge["month_ben_qi"], ge["month_god"]))))
    if ge["transparent"]:
        lines.append("  透干：%s" % "、".join(
            "%s干%s(%s)" % (x["pillar"], x["gan"], x["god"]) for x in ge["transparent"]))
    if ge.get("take_method"):
        lines.append("  取格：%s　类别：%s　用法：%s" % (
            ge["take_method"], ge.get("category", "—"), ge.get("shun_ni") or "—"))
    if ge.get("xiang_shen"):
        lines.append("  相神：%s" % "；".join(
            "%s→%s" % (x["party"], x["role"]) for x in ge["xiang_shen"]))
    if ge.get("status"):
        lines.append("  成败：%s　%s（置信度%s）" % (
            ge["status"], ge.get("status_note", ""), ge.get("confidence", "—")))
    for g in ge.get("good") or []:
        lines.append("  ＋ %s（%s）" % (g["desc"], "、".join(g.get("members") or []) or "—"))
    for b in ge.get("bad") or []:
        lines.append("  － %s（%s）" % (b["desc"], "、".join(b.get("members") or []) or "—"))
    for r in ge.get("rescue") or []:
        lines.append("  ★ 救应：%s（%s）" % (r["desc"], "、".join(r.get("members") or [])))
    if not (ge.get("good") or ge.get("bad") or ge.get("rescue")):
        for h in ge["hints"]:
            lines.append("  · " + h)

    # 十神结构（脚本自动识别，仅供结构层面参考）
    combos = a.get("combinations") or []
    lines.append("【十神结构】")
    if combos:
        lines.append("  （按透干程度排序：透干 > 半透 > 月令；并见时结合旺衰取主次，不要全盘当结论）")
        for x in combos:
            lines.append("  · %s（%s）：%s；%s" % (
                x["name"], x["level"], "、".join(x["members"]), x["note"]))
    else:
        lines.append("  未见「透干/月令」级的典型结构组合（藏支组合未列，避免噪声）。")
    lines.append("")

    ys = a["yong_shen"]
    role_map = ys.get("shen_roles") or {}
    if role_map:
        xi = [e for e, r in role_map.items() if r in ("用神", "喜神")]
        ji = [e for e, r in role_map.items() if r in ("忌神", "仇神")]
        lines.append("【喜用】喜：%s　忌：%s" % ("、".join(xi) or "—", "、".join(ji) or "—"))
    else:
        lines.append("【喜用】喜：%s　忌：%s" % (
            "、".join(ys["useful_elements"]) or "—", "、".join(ys["avoid_elements"]) or "—"))
    if ys.get("primary_elements"):
        lines.append("  主用：%s；次用：%s" % (
            "、".join(ys.get("primary_elements") or []) or "—",
            "、".join(ys.get("secondary_elements") or []) or "—"))
    lines.append("  理由：%s" % ys["reason"])
    if ys["tiaohou"] not in (ys["reason"] or ""):
        lines.append("  调候：%s" % ys["tiaohou"])
    arb = ys.get("arbitration") or {}
    if arb.get("rule"):
        lines.append("  仲裁：%s　优先级：%s" % (
            arb["rule"], " > ".join(arb.get("order") or [])))
    roles = ys.get("shen_roles") or {}
    if roles:
        order = ["用神", "喜神", "忌神", "仇神", "闲神"]
        grp = {}
        for el, role in roles.items():
            grp.setdefault(role, []).append(el)
        lines.append("  角色：" + "；".join(
            "%s=%s" % (r, "/".join(grp[r])) for r in order if grp.get(r)))
    for f in ys.get("yong_shen_force") or []:
        lines.append("  用神力量：%s——%s（%s）" % (
            _el_text(f.get("element")), f.get("status", ""), f.get("note", "")))
    methods = ys.get("methods") or {}
    fy = methods.get("fuyi") or {}
    if fy.get("desc"):
        lines.append("  扶抑：%s（%s，ratio %.3f）" % (
            fy["desc"], fy.get("label", ""), fy.get("ratio", 0.0)))
    tg = methods.get("tongguan") or []
    if tg:
        lines.append("  通关：%s" % "；".join(
            "%s与%s→%s（权重%.2f）" % (x["pair"][0], x["pair"][1], _el_text(x["bridge"]),
                                    x["weight"]) for x in tg))
    bing = methods.get("bingyao") or []
    if bing:
        lines.append("  病药：%s" % "；".join(
            "%s → 药：%s" % (b["bing"], "、".join(_el_text(e) for e in b["yao"]) or "—")
            for b in bing[:3]))
    if ys.get("conflict"):
        lines.append("  ⚠ 冲突：" + ys["conflict"])
    lines.append("")

    # 神煞
    lines.append("【神煞】（传统辅参，次于五行旺衰）")
    if a["shen_sha"]:
        for name, where in a["shen_sha"].items():
            lines.append("  %s：%s" % (name, "、".join(where)))
    else:
        lines.append("  无常用神煞命中")
    lines.append("")

    # 关系
    lines.append("【干支关系】")
    if a["relations"]:
        for r in a["relations"]:
            lines.append("  · " + r)
    else:
        lines.append("  四柱内部无明显合冲刑害")
    lines.append("")

    if report["warnings"]:
        lines.append("【注意】")
        for w in report["warnings"]:
            if w:
                lines.append("  ⚠ " + w)
        lines.append("")

    lines.append("【方法学与免责】")
    lines.append("  历法：日柱纪元 2000-01-07 = 甲子日；年柱以立春为界；月柱以十二节为界；时柱用五鼠遁。")
    lines.append("  旺衰：柱位权重×藏干分层×十神亲和的「结构力」模型（月支 0.40 最重），")
    lines.append("        刑冲合害按类型折损（冲 55%/刑 80%/合害 88%），输出同党结构力 ratio 与置信度；")
    lines.append("        三合、三会另加权，日干本身不计入同党。")
    lines.append("  格局：子平真诠取格（月令本气→中气→余气之透干，皆不透取本气；禄刃单列），")
    lines.append("        判顺用/逆用、相神、成格条件、破格因素、救应与月令损伤。")
    lines.append("  喜用：扶抑 / 调候 / 通关 / 病药 四法各出结论，再按")
    lines.append("        「特殊格 > 破格救应 > 调候急需 > 病药 > 扶抑」仲裁，并标出用神有力与否。")
    lines.append("        调候取《穷通宝鉴》120 格表（日干×月支），寒暖指数只定急缓。")
    lines.append("  大运流年：综合分 = 基调分（用神角色加权）＋ 引动分（干支合冲刑害、伏吟、反吟、")
    lines.append("        半合、岁运并临）；另给领域与置信度。应期只列显著引动，不预测具体事件。")
    lines.append("  以上除历法外均为规则化术数模型，属传统民俗文化，并非科学结论，")
    lines.append("  不宜作为医疗、法律、投资或重大人生决策的唯一依据。")
    return "\n".join(lines).replace("。；", "；")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="八字排盘与分析：四柱、藏干、十神、大运、流年、五行旺衰、格局喜用、神煞。",
    )
    parser.add_argument("--date", required=True, help="公历日期 YYYY-MM-DD（--lunar 时为农历）")
    parser.add_argument("--time", required=True, help="记录的钟表时间 HH:MM[:SS]")
    parser.add_argument("--lunar", action="store_true",
                        help="把 --date 当作农历日期（闰月再加 --leap）")
    parser.add_argument("--leap", action="store_true", help="配合 --lunar：该农历月为闰月")
    parser.add_argument("--sex", default=None, help="male/female/m/f/男/女（算大运用）")
    parser.add_argument("--zone", default="Asia/Shanghai", help="IANA 时区，默认 Asia/Shanghai")
    parser.add_argument("--longitude", type=float, default=None,
                        help="出生地经度（东经为正），配合 --true-solar-time")
    parser.add_argument("--true-solar-time", action="store_true",
                        help="用真太阳时排盘（需 --longitude）")
    parser.add_argument("--latitude", type=float, default=None,
                        help="出生地纬度（北纬为正，占星宫位/上升用；缺省按 30°N 并在输出中提示）")
    parser.add_argument("--sect", type=int, choices=(1, 2), default=2,
                        help="晚子时流派：1 换日柱；2 不换日柱（默认）")
    parser.add_argument("--qiyun-sect", type=int, choices=(1, 2), default=2,
                        help="起运计算：1 按天数时辰；2 按分钟（默认，更细）")
    parser.add_argument("--dayun-count", type=int, default=9, help="大运轮数，默认 9（≥1）")
    parser.add_argument("--focus-year", type=int, default=None,
                        help="流年聚焦年，默认当前年份")
    parser.add_argument("--time-unknown", action="store_true",
                        help="出生时辰未知：标记时柱不可靠并加入警告")
    parser.add_argument("--liuyue", action="store_true",
                        help="附带聚焦年的流月（文本与 JSON 都输出）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--plain", action="store_true",
                        help="输出通俗版（人话解读：结论/性格/钱与工作/感情/健康/近几年/建议），与 --json 同用则写入 plain 字段")
    parser.add_argument("--plain-only", action="store_true",
                        help="只输出通俗版正文（隐含 --plain，且不输出技术版）")
    parser.add_argument("--topics", action="store_true",
                        help="追加专题推测（婚恋/事业/财富/学业/健康/六亲/迁移/人际），与 --json 同用写入 topics 字段")
    parser.add_argument("--brief", action="store_true",
                        help="只输出一屏内的人话摘要（≤400 字；隐含 --plain，不输出技术版），适合快速回复")
    parser.add_argument("--topic", default=None,
                        help="只保留指定的专题域，逗号分隔：love/career/wealth/study/health/family/move/people（隐含 --topics）")
    parser.add_argument("--divination", action="store_true",
                        help="追加其它术数交叉参考（小六壬/梅花易数/六爻纳甲/称骨/星座/生肖纳音/紫微斗数），与 --json 同用写入 divination 字段")
    parser.add_argument("--ziwei", action="store_true",
                        help="单独输出紫微斗数命盘（十二宫/主星/四化/大限），与 --json 同用写入 ziwei 字段")
    parser.add_argument("--qimen", action="store_true",
                        help="输出奇门遁甲时家转盘（节气定局/九宫/九星八门八神/值符值使），与 --json 同用写入 qimen 字段")
    parser.add_argument("--fusion", action="store_true",
                        help="跨体系融合层：把八字/紫微/西洋占星/印度占星/数字学/民俗占法映射到 9 个生活领域，做一致性与张力分析，与 --json 同用写入 fusion 字段")
    parser.add_argument("--astro", action="store_true",
                        help="输出西洋本命占星盘（十行星/宫位/相位/元素平衡/月相）与印度占星（Lahiri 岁差/27 宿/上升），与 --json 同用写入 astrology 字段")
    parser.add_argument("--numerology", action="store_true",
                        help="输出数字学分析（生命灵数/生日数/态度数/成熟数/九宫格/个人周期，可加姓名分析），与 --json 同用写入 numerology 字段")
    parser.add_argument("--name", default=None,
                        help="姓名（数字学姓名分析用；中文名需同时给 --strokes 笔画）")
    parser.add_argument("--strokes", default=None,
                        help="姓名笔画，逗号分隔，如 \"7,6\"（配合 --name 做五格分析）")
    parser.add_argument("--surname-len", type=int, default=1,
                        help="姓氏字数（复姓用 2），默认 1")
    args = parser.parse_args(argv)

    # 先解析时间
    try:
        fmt = "%H:%M:%S" if args.time.count(":") == 2 else "%H:%M"
        args.time = datetime.strptime(args.time, fmt).time()
    except ValueError:
        parser.error("--time 格式应为 HH:MM 或 HH:MM:SS，例如 12:00")

    # 再解析日期：农历输入不能先按公历 strptime 校验（农历二月可有 29/30 日）
    raw_date = args.date
    try:
        parts = [int(x) for x in raw_date.split("-")]
        if len(parts) != 3:
            raise ValueError
        dy, dm, dd = parts
    except ValueError:
        parser.error("--date 格式应为 YYYY-MM-DD，例如 1990-06-15")

    if args.dayun_count < 1:
        parser.error("--dayun-count 需 ≥ 1")
    if args.longitude is not None and not (-180.0 <= args.longitude <= 180.0):
        parser.error("--longitude 需在 [-180, 180] 之间（东经为正、西经为负）")
    if args.latitude is not None and not (-90.0 <= args.latitude <= 90.0):
        parser.error("--latitude 需在 [-90, 90] 之间（北纬为正、南纬为负）")

    topic_only = None
    if getattr(args, "topic", None):
        topic_only = [x.strip() for x in
                      str(args.topic).replace("，", ",").split(",") if x.strip()]
        bad = [x for x in topic_only if x not in topicsmod.TOPIC_IDS]
        if bad:
            parser.error("--topic 只支持 %s，不认识：%s"
                         % ("/".join(topicsmod.TOPIC_IDS), "、".join(bad)))

    # 农历输入：先换算成公历，再走统一的时间校正流程
    args.lunar_input = None
    if args.lunar:
        month = -dm if args.leap else dm
        try:
            sy, sm, sd, sh, smi, ss = chart.lunar_to_solar(
                dy, month, dd, args.time.hour, args.time.minute, args.time.second)
        except Exception as exc:
            parser.error("农历日期无效：%s" % exc)
        args.lunar_input = {
            "year": dy,
            "month": dm,
            "day": dd,
            "leap": bool(args.leap),
            "solar": "%04d-%02d-%02d %02d:%02d:%02d" % (sy, sm, sd, sh, smi, ss),
        }
        args.date = datetime(sy, sm, sd).date()
        args.time = datetime(2000, 1, 1, sh, smi, ss).time()
    else:
        try:
            args.date = datetime(dy, dm, dd).date()
        except ValueError:
            parser.error("--date 不是有效的公历日期：%s" % raw_date)

    report = build_report(args)
    report["focus_year"] = args.focus_year or datetime.now().year

    want_plain = bool(args.plain or getattr(args, "plain_only", False)
                      or getattr(args, "brief", False))
    if want_plain:
        report["plain"] = plainmod.build_plain(report)

    want_topics = bool(getattr(args, "topics", False) or topic_only)
    if want_topics:
        report["topics"] = topicsmod.build_topics(report)
        if topic_only:
            report["topics"] = topicsmod.filter_topics(report["topics"], topic_only)

    want_divination = bool(getattr(args, "divination", False))
    if want_divination:
        report["divination"] = divmod.build_divination(report)

    want_ziwei = bool(getattr(args, "ziwei", False))
    if want_ziwei:
        report["ziwei"] = ziweimod.chart_ziwei(report)

    want_qimen = bool(getattr(args, "qimen", False))
    if want_qimen:
        if qimenmod is not None:
            report["qimen"] = qimenmod.chart_qimen(report)
        else:  # 模块缺失时降级，不影响其它层
            report["qimen"] = {"available": False,
                               "note": "奇门遁甲模块（scripts/qimen.py）未安装或导入失败。"}

    want_fusion = bool(getattr(args, "fusion", False))

    # 西洋/印度占星、数字学：单独请求或融合层需要时计算（融合层复用，避免重复算）
    want_astro = bool(getattr(args, "astro", False))
    if (want_astro or want_fusion) and astromod is not None:
        report["astrology"] = astromod.chart_natal(report)

    want_numerology = bool(getattr(args, "numerology", False))
    if (want_numerology or want_fusion
            or getattr(args, "name", None) or getattr(args, "strokes", None)) and nummod is not None:
        strokes = None
        if getattr(args, "strokes", None):
            try:
                strokes = [int(x) for x in args.strokes.replace("，", ",").split(",") if x.strip()]
            except ValueError:
                parser.error("--strokes 应为逗号分隔的整数，如 \"7,6\"")
        report["numerology"] = nummod.numerology(
            report, name=getattr(args, "name", None), strokes=strokes,
            surname_len=getattr(args, "surname_len", 1))

    if want_fusion:
        report["fusion"] = fusionmod.build_fusion(report)

    if args.json:
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif getattr(args, "brief", False):
        sys.stdout.reconfigure(encoding="utf-8")
        print(plainmod.render_brief_text(report["plain"]))
    elif getattr(args, "plain_only", False):
        sys.stdout.reconfigure(encoding="utf-8")
        print(plainmod.render_plain_text(report["plain"], report))
    elif args.plain:
        sys.stdout.reconfigure(encoding="utf-8")
        print(plainmod.render_plain_text(report["plain"], report))
        print("────────── 技术版附在后面 ──────────\n")
        print(render_text(report))
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(render_text(report))
    if want_topics and not args.json:
        sys.stdout.reconfigure(encoding="utf-8")
        print(topicsmod.render_topics_text(report["topics"], only=topic_only))
    if want_divination and not args.json:
        sys.stdout.reconfigure(encoding="utf-8")
        print(divmod.render_divination_text(report["divination"]))
    if want_ziwei and not args.json and not want_divination:
        # --divination 已含紫微段，同时给出时不重复打印
        sys.stdout.reconfigure(encoding="utf-8")
        print(ziweimod.render_ziwei_text(report["ziwei"]))
    if want_qimen and not args.json:
        sys.stdout.reconfigure(encoding="utf-8")
        qimen_data = report.get("qimen")
        if qimen_data and qimen_data.get("available") is not False and qimenmod is not None:
            print(qimenmod.render_qimen_text(qimen_data))
        elif qimen_data:
            print("【奇门遁甲】" + str(qimen_data.get("note", "模块未安装")))
    if want_fusion and not args.json:
        sys.stdout.reconfigure(encoding="utf-8")
        print(fusionmod.render_fusion_text(report["fusion"]))
    if want_astro and not args.json:
        astro_chart = report.get("astrology")
        if astro_chart and astromod is not None:
            sys.stdout.reconfigure(encoding="utf-8")
            print(astromod.render_natal_text(astro_chart))
    if want_numerology and not args.json:
        num_data = report.get("numerology")
        if num_data and nummod is not None:
            sys.stdout.reconfigure(encoding="utf-8")
            print(nummod.render_numerology_text(num_data))


if __name__ == "__main__":
    main()
