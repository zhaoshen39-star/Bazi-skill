"""plain.py —— 把 v3 分析报告翻译成人话。

设计原则：
1. 不懂八字的人也能看懂：不出现「结构力」「用神」「十神」等术语（术语只放在最后的
   「名词翻译」表里），五行/十神一律换成生活化的说法。
2. 预测只讲「会有什么感觉、适合做什么、避开什么」，不下断语、不报事件。
3. 全部由报告 JSON 数据驱动，不含针对某个人的硬编码，可复算、可测试。

对外接口：
- build_plain(report) -> dict            结构化通俗版报告
- render_plain_text(plain) -> str       通俗版纯文本
"""

from __future__ import annotations

ELEMENT_USE = {
    "水": "沟通、变化、流动性的机会（信息、贸易、物流、互联网一类）",
    "金": "专业、规则与硬技能（技术、金融、理工、器械一类）",
    "木": "创意、内容与成长型的事（内容、教育、设计、策划一类）",
    "火": "表达、曝光与带动气氛（传播、销售、餐饮、活动一类）",
    "土": "稳定、积累与长期主义（地产、工程、制造、行政一类）",
}

ELEMENT_IMAGE = {
    "水": "像水：脑子转得快、适应力强，也容易被环境带着走",
    "金": "像金属：讲规则、重结果，对自己要求高",
    "木": "像树：爱生长、点子多，需要有人帮你修方向",
    "火": "像火：热情、直给，容易被情绪推着走",
    "土": "像土：稳、能扛，容易把事都揽在自己身上",
}

PARTY_TRAIT = {
    "比劫": "偏自立，很多事习惯自己做主，不太爱开口求人",
    "印星": "爱学习、信专业，遇到问题先找方法和靠山",
    "食伤": "有表达欲和点子，喜欢把想法做出来给人看",
    "财星": "对钱和现实条件敏感，做事先算账",
    "官杀": "责任心重、在意评价，容易给自己加压",
}

GOD_TRAIT = {
    "正财": "看重稳定收入，花钱有计划",
    "偏财": "对机会型收入敏感，愿意试新路子",
    "正官": "守规矩、要面子，怕出错",
    "七杀": "抗压、敢冲，但也容易紧绷",
    "正印": "学东西快，愿意跟着前辈和体系走",
    "偏印": "爱钻偏门、有自己的一套，有时不太合群",
    "食神": "温和、会享受，表达不急不躁",
    "伤官": "嘴快、有锋芒，创意强但容易顶人",
    "比肩": "主见强，愿意自己扛",
    "劫财": "讲义气、朋友多，但钱容易一起花",
}

GOD_TOPIC = {
    "正财": "稳定收入",
    "偏财": "机会财和异性缘",
    "正官": "工作和责任",
    "七杀": "压力和竞争",
    "正印": "学习和贵人",
    "偏印": "钻研和灵感",
    "食神": "表达和享受",
    "伤官": "创意和自由",
    "比肩": "同辈和自立",
    "劫财": "合作和朋友",
}

SPOUSE_TYPE = {
    "正财": "务实、会过日子的人",
    "偏财": "活络、会来事的人",
    "正官": "稳当、讲规矩的人",
    "七杀": "有主见、敢作敢当的人",
    "正印": "温和、能照顾人的人",
    "偏印": "有点特别、圈子不大的人",
    "食神": "脾气温和、爱生活的人",
    "伤官": "聪明有才华、有点个性的人",
    "比肩": "和你像、能并肩走的人",
    "劫财": "热闹、朋友多的人",
}

PATTERN_PLAIN = {
    "正财格": "稳扎稳打的收入型，适合正职加长期积累",
    "偏财格": "机会型的财路，适合副业、资源整合这类活",
    "正官格": "适合有规矩、有层级的平台",
    "七杀格": "适合压力大但能出成绩的岗位",
    "正印格": "专业、研究、教育型的路子",
    "偏印格": "偏门、技术、研究型的路子",
    "食神格": "内容、手艺、服务型的路子",
    "伤官格": "创意、表达、技术型的路子",
    "建禄格": "自立型，适合自己带摊子或跟人合伙",
    "月劫格（阳刃格）": "竞争型，靠冲劲拿结果",
    "比劫格": "靠人脉和合作的路子",
}

PATTERN_SHORT = {
    "正财格": "稳定收入型",
    "偏财格": "机会型",
    "正官格": "规范平台型",
    "七杀格": "压力出成绩型",
    "正印格": "专业型",
    "偏印格": "偏门技术型",
    "食神格": "内容服务型",
    "伤官格": "创意表达型",
    "建禄格": "自立型",
    "月劫格（阳刃格）": "竞争型",
    "比劫格": "合作型",
}

STRENGTH_PLAIN = {
    "身弱": "底子薄，需要外力帮",
    "偏弱": "底子略薄，要有人搭把手",
    "中和": "底子均衡",
    "偏强": "底子不错，能扛事",
    "身强": "底子很足，能自己拿主意",
}

LEVEL_PLAIN = {
    "喜": "顺",
    "偏喜": "偏顺",
    "中性": "平稳",
    "偏忌": "偏吃力",
    "忌": "吃力",
}

CONF_PLAIN = {"高": "比较确定", "中": "中等把握", "低": "不太好说"}

EVENT_PLAIN = {
    "地支六合": "事情被牵在一起，聚也聚得成、拖也拖得久",
    "地支冲": "有来回变动、挪地方或换环境",
    "地支刑": "心里拧巴、容易自己跟自己较劲",
    "地支自刑": "容易想多、内耗",
    "地支害": "有暗中的不痛快",
    "地支破": "有小不顺、小破财或小摩擦",
    "天干五合": "被某件事或某个人牵住",
    "天干相冲": "有人跟你顶着来",
    "伏吟": "旧事重提、原地打转",
    "反吟": "来回拉扯，进退都别扭",
    "岁运并临": "大运和流年撞在一起，变化会放大",
    "半合局": "事情有合作或撮合的机会",
}

LIMITS = [
    "同样的八字，成长环境、选择和努力不同，结果会差很多——这里是倾向，不是命定。",
    "出生时间如果不准，晚年、子女这类结论会跟着变。",
    "这套东西是传统民俗，不替代就医、投资、法律等专业意见。",
]

GLOSSARY = [
    ("日主", "你自己，出生那天的天干"),
    ("身强 / 身弱", "你的底子能不能扛事：强是能扛，弱是容易累、要借力"),
    ("用神 / 喜神", "对你最有帮助的力量：用神是最需要的，喜神是顺带帮忙的"),
    ("忌神 / 仇神", "容易给你添乱的力量：忌神是主凶，仇神是帮凶"),
    ("十神", "把人和事分成十类角色：钱、工作、学习、同辈、表达等"),
    ("大运", "十年一段的大环境，影响这十年的主基调"),
    ("流年", "一年的运势节奏，用来看今年该进还是该守"),
    ("格局", "你天生适合走的那条路：靠什么吃饭、在什么位置最舒服"),
]


def _fmt_pct(v):
    return "%.0f%%" % (v * 100.0)


def _party_share(st, name):
    return float((st.get("party_shares") or {}).get(name, 0.0))


def _top_parties(st, n=2, floor=0.12):
    shares = st.get("party_shares") or {}
    items = sorted(shares.items(), key=lambda kv: -kv[1])
    out = [k for k, v in items[:n] if v >= floor]
    return out


def _tou_gans(report):
    out = []
    for p in report["chart"]["pillars"]:
        g = p.get("shishen_gan")
        if g and g not in out:
            out.append(g)
    return out


def _dayun_current(report):
    year = int(report.get("focus_year") or 0)
    for dy in (report["chart"].get("dayun") or {}).get("list") or []:
        if dy["start_year"] <= year <= dy["end_year"]:
            return dy
    return None


def _element_power(report):
    force = (report["analysis"]["strength"].get("force") or {})
    if not force:
        totals = report["analysis"]["wuxing"].get("totals") or {}
        return dict(totals)
    return force


def build_plain(report):
    a = report["analysis"]
    st = a["strength"]
    ge = a["pattern"]
    ys = a["yong_shen"]
    chart = report["chart"]
    day_gan = chart["day_gan"]
    day_el = chart.get("day_gan_wuxing") or ""
    label = st.get("label") or "中和"
    roles = ys.get("shen_roles") or {}
    useful = [el for el, r in roles.items() if r == "用神"]
    helpful = [el for el, r in roles.items() if r == "喜神"]
    harmful = [el for el, r in roles.items() if r == "忌神"]
    foe = [el for el, r in roles.items() if r == "仇神"]
    primary = list(ys.get("primary_elements") or useful or ["水"])
    secondary = list(ys.get("secondary_elements") or helpful or [])

    # ---- 性格底色 ----
    profile = []
    if day_el in ELEMENT_IMAGE:
        profile.append(ELEMENT_IMAGE[day_el])
    for party in _top_parties(st):
        if party in PARTY_TRAIT:
            profile.append("你" + PARTY_TRAIT[party] + "。")
    shown = 0
    for g in _tou_gans(report):
        if g in GOD_TRAIT and shown < 3:
            profile.append("你%s。" % GOD_TRAIT[g])
            shown += 1
    if len(profile) > 5:
        profile = profile[:5]

    # ---- 长处 ----
    strengths = []
    if primary:
        strengths.append(
            "你最需要、也最能帮上忙的力量是「%s」：%s。"
            % (primary[0], ELEMENT_USE.get(primary[0], "顺着感觉走、借势做事"))
        )
    if secondary:
        strengths.append(
            "顺带能帮你的还有「%s」：%s。"
            % (secondary[0], ELEMENT_USE.get(secondary[0], "多接触相关的人和事"))
        )
    if _party_share(st, "印星") >= 0.22:
        strengths.append("学东西、考证、跟对平台，是你最快的加分方式。")
    if any(g in ("食神", "伤官") for g in _tou_gans(report)):
        strengths.append("把你的想法讲清楚、做出来给人看，别人会买账。")
    if ge.get("shun_ni", "").startswith("顺用"):
        strengths.append("走常规路线、一步一步积累，比投机更合你的性子。")

    # ---- 容易卡住的地方 ----
    watchouts = []
    if label in ("身弱", "偏弱"):
        watchouts.append("事情一多就觉得累，一个人扛不动太多，别硬撑。")
    for el in harmful[:2]:
        note = {
            "水": "想法多、情绪容易在原地打转",
            "金": "对自己要求太高，容易内耗",
            "木": "想得多、动手慢",
            "火": "容易被钱和面子牵着走",
            "土": "责任压身，容易把别人的事揽过来",
        }.get(el)
        if note:
            watchouts.append("「%s」太旺时，%s。" % (el, note))
    if _party_share(st, "财星") >= 0.30 and label in ("身弱", "偏弱"):
        watchouts.append("钱的事容易变成压力：能赚，但也得守得住。")
    if _party_share(st, "官杀") >= 0.25:
        watchouts.append("对别人的评价敏感，容易把期待当任务背在身上。")
    if st.get("special"):
        watchouts.append("你的盘偏「一边倒」，顺势做事比逆着来轻松得多。")

    # ---- 钱与工作 ----
    money_work = []
    pat_name = ge.get("name") or ""
    if pat_name in PATTERN_PLAIN:
        money_work.append("你的路子是：%s。" % PATTERN_PLAIN[pat_name])
    cai = _party_share(st, "财星")
    if cai >= 0.32:
        money_work.append("在你命里，「钱和资源」的分量很重（约四成）；你天然靠近成交、经营、资源这类事。")
    elif cai <= 0.12:
        money_work.append("你对钱本身不算敏感，更适合先把一门本事做深，钱是跟着本事来的。")
    if label in ("身弱", "偏弱"):
        money_work.append("别一个人扛整个盘子：进平台、找团队、跟对人，比单干稳。")
        money_work.append("别用借贷放大投资，现金流比机会重要。")
    else:
        money_work.append("你能扛事，可以主动争取更重要的位置。")

    # ---- 感情 ----
    relationship = []
    sex = (report["input"].get("sex") or "").lower()
    spouse_god = (chart["pillars"][2].get("canggan_shishen") or [""])[0]
    if sex in ("male", "男", "m"):
        if cai >= 0.30:
            relationship.append("感情里你容易先算现实条件，这不算错，但别让对方觉得只在算账。")
        else:
            relationship.append("感情上你不主动争，遇到合适的要更明确一点。")
    else:
        relationship.append("感情里你容易先照顾对方的感受，记得也要说出自己的需要。")
    if spouse_god:
        relationship.append("你更容易被「%s」吸引。" % SPOUSE_TYPE.get(spouse_god, "相处起来舒服的人"))
    if label in ("身弱", "偏弱") and cai >= 0.30:
        relationship.append("留意：钱和感情容易搅在一起，别用花钱来表达在意。")

    # ---- 身体 ----
    health = []
    power = _element_power(report)
    if power:
        hi = max(power, key=lambda k: power[k])
        lo = min(power, key=lambda k: power[k])
        hi_note = {
            "火": "心火、睡眠、血压容易敏感，夏天尤其",
            "土": "肠胃和消化要顾",
            "金": "呼吸道、皮肤偏敏感",
            "水": "水湿、泌尿系统要顾，别熬夜",
            "木": "肝火、情绪和睡眠连着",
        }.get(hi, "容易有偏亢的地方")
        lo_note = {
            "水": "多喝水、少熬夜",
            "金": "多做呼吸类运动、注意过敏",
            "木": "多走动、别久坐",
            "火": "多晒太阳、别把情绪憋着",
            "土": "三餐规律、少生冷",
        }.get(lo, "注意作息")
        health.append("按传统五行对应：%s偏旺，%s。" % (hi, hi_note))
        health.append("「%s」偏少：%s。" % (lo, lo_note))
        health.append("这只作作息参考，不能代替就医。")

    # ---- 大运 ----
    dy = _dayun_current(report)
    current_decade = ""
    if dy:
        t = dy.get("timing") or {}
        lvl = LEVEL_PLAIN.get(t.get("label") or (dy.get("favorability") or {}).get("label", "中性"), "平稳")
        gods = t.get("gods") or []
        topics = "、".join(GOD_TOPIC.get(g, g) for g in gods[:2]) or "日常"
        current_decade = "%d–%d 年这十年（%s）：整体%s，主题偏「%s」。" % (
            dy["start_year"], dy["end_year"], dy["ganzhi"], lvl, topics)

    # ---- 近几年预测 ----
    fy = int(report.get("focus_year") or 2026)
    forecast = []
    for ly in chart.get("liunian") or []:
        y = int(ly["year"])
        if y < fy or y > fy + 3:
            continue
        t = ly.get("timing") or {}
        base = ly.get("favorability") or {}
        lvl = LEVEL_PLAIN.get(t.get("label") or base.get("label", "中性"), "平稳")
        conf = CONF_PLAIN.get(t.get("confidence") or "中", "中等把握")
        gods = t.get("gods") or []
        topics = "、".join(GOD_TOPIC.get(g, g) for g in gods[:2])
        events = []
        for e in (t.get("events") or []):
            plain = EVENT_PLAIN.get(e.get("type", ""))
            if plain and plain not in events:
                events.append(plain)
        what = "主题是%s" % topics if topics else "没有特别集中的主题"
        if events:
            what += "；另外，%s" % events[0]
        if lvl in ("吃力", "偏吃力"):
            do = "以守为主：把账理清、把人脉和身体顾好，大动作留到下半年。"
            avoid = "忌冲动投资、替人担保、硬换赛道。"
        elif lvl in ("顺", "偏顺"):
            do = "适合推进：签约、面试、搬家、进修这类大事可以提上日程。"
            avoid = "忌因为顺就答应下所有事，留点余地。"
        else:
            do = "按部就班即可，有变动顺势接住。"
            avoid = "忌在小事上反复纠结。"
        forecast.append({
            "year": y, "ganzhi": ly.get("ganzhi"), "level": lvl,
            "confidence": conf, "what": what, "do": do, "avoid": avoid,
        })

    # ---- 三条建议 ----
    actions = []
    if primary:
        actions.append("把「%s」当主线：多往%s的方向靠。" % (
            primary[0], ELEMENT_USE.get(primary[0], "适合你的方向")))
    if label in ("身弱", "偏弱"):
        actions.append("找平台、找团队、找能带你的人，别一个人扛。")
    else:
        actions.append("可以主动争取更大的位置，但别把弦绷太紧。")
    if cai >= 0.30 and label in ("身弱", "偏弱"):
        actions.append("现金留足半年，投资不借贷、不担保。")
    elif _party_share(st, "印星") >= 0.22:
        actions.append("每年给自己加一块硬本事（证书、作品、项目），这是你的复利。")
    else:
        actions.append("身体和作息当成正事来管，别用透支换进度。")

    # ---- 一句话 ----
    hard = bool(forecast) and forecast[0]["level"] in ("吃力", "偏吃力")
    pace = "近两三年以守为主，别冒进" if hard else "节奏偏顺，可以按计划往前推"
    one_line = "%s%s，%s；%s。" % (
        day_el,
        STRENGTH_PLAIN.get(label, ""),
        PATTERN_SHORT.get(pat_name, "稳扎稳打"),
        pace,
    )
    if len(one_line) > 80:
        one_line = one_line[:79] + "。"

    return {
        "version": 1,
        "one_line": one_line,
        "profile": profile,
        "strengths": strengths,
        "watchouts": watchouts,
        "money_work": money_work,
        "relationship": relationship,
        "health": health,
        "current_decade": current_decade,
        "forecast": forecast,
        "actions": actions[:3],
        "limits": list(LIMITS),
        "glossary": [{"term": t, "plain": p} for t, p in GLOSSARY],
        "model": "通俗版：把技术分析翻译成生活语言，只讲倾向和建议，不预测具体事件。",
    }


def render_plain_text(plain, report=None):
    lines = []
    if report is not None:
        c = report["chart"]
        pillars = " ".join(p["ganzhi"] for p in c["pillars"])
        lines.append("【排盘】%s（日主：%s%s）" % (pillars, c["day_gan"], c.get("day_gan_wuxing", "")))
        t = report.get("time") or {}
        if t.get("used_label"):
            lines.append("【时间口径】%s（%s）" % (t["used_label"], t.get("used", "")))
        lines.append("")
    lines.append("═══ 通俗版解读 ═══")
    lines.append("")
    lines.append("一句话：" + plain["one_line"])
    lines.append("")

    def section(title, items):
        if not items:
            return
        lines.append("【%s】" % title)
        for it in items:
            lines.append("· " + it)
        lines.append("")

    section("你是个什么样的人", plain["profile"])
    section("你的长处", plain["strengths"])
    section("容易卡住的地方", plain["watchouts"])
    section("钱和工作", plain["money_work"])
    section("感情", plain["relationship"])
    section("身体", plain["health"])

    if plain.get("current_decade"):
        lines.append("【现在走到哪】")
        lines.append("· " + plain["current_decade"])
        lines.append("")

    if plain.get("forecast"):
        lines.append("【接下来几年怎么走】")
        for f in plain["forecast"]:
            lines.append("· %d 年（%s）：整体%s（%s）。%s" % (
                f["year"], f["ganzhi"], f["level"], f["confidence"], f["what"]))
            lines.append("  怎么用：%s" % f["do"])
            lines.append("  避开：%s" % f["avoid"])
        lines.append("")

    if plain.get("actions"):
        lines.append("【给你三条建议】")
        for i, a in enumerate(plain["actions"], 1):
            lines.append("%d. %s" % (i, a))
        lines.append("")

    if plain.get("glossary"):
        lines.append("【名词翻译】")
        for g in plain["glossary"]:
            lines.append("· %s：%s" % (g["term"], g["plain"]))
        lines.append("")

    lines.append("【说明】")
    for it in plain.get("limits") or LIMITS:
        lines.append("· " + it)
    return "\n".join(lines).strip() + "\n"


BRIEF_LIMIT = 400

_BRIEF_TAIL = "【说明】倾向与建议，不是确定预测；不预测具体事件。"


def render_brief_text(plain, limit=BRIEF_LIMIT):
    """一屏内的人话摘要：只留结论 + 近两年 + 可执行建议，默认 ≤400 字。"""
    cand = []
    if plain.get("one_line"):
        cand.append("【一句话】" + plain["one_line"])
    prof = plain.get("profile") or []
    if prof:
        cand.append("【性格】" + prof[0])
    st = plain.get("strengths") or []
    if st:
        cand.append("【长处】" + st[0])
    wa = plain.get("watchouts") or []
    if wa:
        cand.append("【注意】" + wa[0])
    if plain.get("current_decade"):
        cand.append("【现在】" + str(plain["current_decade"]))
    mw = plain.get("money_work") or []
    if mw:
        cand.append("【钱与工作】" + mw[0])
    for f in (plain.get("forecast") or [])[:2]:
        cand.append("【%s年】整体%s；怎么用：%s；避开：%s" % (
            f.get("year"), f.get("level"), f.get("do"), f.get("avoid")))
    for a in (plain.get("actions") or [])[:2]:
        cand.append("【建议】" + a)

    budget = limit - len(_BRIEF_TAIL) - 1
    lines = []
    used = 0
    for line in cand:
        if used + len(line) + 1 > budget:
            break
        lines.append(line)
        used += len(line) + 1
    lines.append(_BRIEF_TAIL)
    return "\n".join(lines)
