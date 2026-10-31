# -*- coding: utf-8 -*-
"""专题推测层（topics）：把命局结构与大运流年落到八个生活领域。

设计原则
--------
1. 结论来自「结构（十神配置/宫位/扶抑调候）定倾向」＋「大运流年引动定应期」，不掷骰子、不编事件。
2. 每个专题都给：倾向、技术依据、有利年份、需留意年份、可执行建议、置信度。
3. 领域：婚恋 / 事业 / 财富 / 学业 / 健康 / 六亲 / 迁移 / 人际。
4. 只谈倾向与时机；健康类只作作息参考，不作诊断。

对外接口
--------
build_topics(report) -> dict          report 为 bazi.build_report() 的返回值
render_topics_text(topics) -> str     技术版文本
"""

from chart import HIDE_GAN, ELEMENT_OF_GAN
from analysis import (ten_god_of, TEN_GOD_PARTY, YI_MA, _group_of, KE,
                      ZHI_LIU_HE, ZHI_CHONG, ZHI_HAI, ZHI_PO, ZHI_XING,
                      PARTIAL_XING, SELF_XING)

VERSION = 3
MODEL = ("专题推测＝「命局结构（十神配置、宫位、扶抑调候）定倾向」＋「大运流年引动定应期」，"
         "每个领域独立给依据与置信度；只谈倾向与时机，不预测具体事件。")
LIMITS = [
    "专题是倾向不是命定：同样的盘，环境、选择和努力不同，结果差很多。",
    "出生时间不准时，宫位（尤其时柱=子女/晚年）与流年应期会明显漂移。",
    "健康、投资、法律等事项以专业意见为准，本层只作自我观察的参考。",
]

ELEMENT_ORGAN = {
    "木": ("肝、胆、筋、目", "情绪与疏泄"),
    "火": ("心、小肠、血脉、舌", "睡眠与心血管"),
    "土": ("脾、胃、肌肉、口", "消化与代谢"),
    "金": ("肺、大肠、皮毛、鼻", "呼吸与皮肤"),
    "水": ("肾、膀胱、骨、耳", "泌尿、生殖与精力"),
}
ELEMENT_DIRECTION = {"木": "东方", "火": "南方", "土": "中部", "金": "西方", "水": "北方"}
ELEMENT_ENV = {
    "木": "绿化多、偏东文教或种植类环境",
    "火": "偏南、温暖，能源/电子/传媒密集",
    "土": "中部或内陆，地产/基建/仓储类",
    "金": "偏西，金融/制造/器械/规则密集",
    "水": "偏北或沿海，港口、物流、贸易、信息流动型",
}
ELEMENT_SUBJECT = {
    "木": "文科、教育、出版、医药、种植类",
    "火": "传媒、能源、电子、餐饮、表演类",
    "土": "地产、土木、管理、农业、仓储类",
    "金": "理工、工程、器械、金融、法律、数据类",
    "水": "语言、贸易、物流、信息、互联网、金融流动类",
}
GOD_INDUSTRY = {
    "正官": ["体制内、行政管理", "法务合规、公共事务"],
    "七杀": ["竞争性行业、销售", "工程/军警/风控等高压岗位"],
    "正财": ["财务、会计", "稳定经营、供应链"],
    "偏财": ["市场、投资、贸易", "自由职业、副业"],
    "食神": ["技术、产品", "餐饮、内容创作"],
    "伤官": ["创意、设计、演艺", "研发、自媒体"],
    "正印": ["教育、科研、医疗", "文教、资格认证"],
    "偏印": ["研究、心理、术数", "偏门技术与咨询"],
    "比肩": ["团队协作、合伙", "同辈资源型工作"],
    "劫财": ["资源整合、销售", "合作竞争型岗位"],
}
SPOUSE_TRAIT = {
    "正官": "有主见、讲规矩、责任感强的人",
    "七杀": "行动力强、气场足、略带强势的人",
    "正财": "务实、会过日子、重现实条件的人",
    "偏财": "活络、会来事、社交面广的人",
    "食神": "温和、会生活、有手艺或口味的人",
    "伤官": "聪明、有才华、个性鲜明的人",
    "正印": "稳重、顾家、像长辈一样照顾人的人",
    "偏印": "有自己世界、想法独特的人",
    "比肩": "像朋友一样平等相处的人",
    "劫财": "热情、讲义气、边界感需要磨合的人",
}

PARTY_LABEL = {"比劫": "同辈/自立", "印星": "学习/长辈", "食伤": "表达/创造",
               "财星": "钱与资源", "官杀": "责任/压力"}


# ── 基础工具 ────────────────────────────────────────────────────────────────
def _sex_of(report):
    s = (report.get("input") or {}).get("sex")
    if s in ("male", "m", "男", 1):
        return "男"
    if s in ("female", "f", "女", 0):
        return "女"
    return None


def _god_table(pillars, day_gan):
    """[(党, 十神, 柱位, 来源)]；来源 ∈ 干/本气/中气/余气/日主。"""
    hits = []
    for idx, p in enumerate(pillars):
        slot = p.get("name") or ("年柱", "月柱", "日柱", "时柱")[idx]
        for i, cg in enumerate(p.get("canggan") or []):
            g = ten_god_of(day_gan, cg)
            src = "本气" if i == 0 else ("中气" if i == 1 else "余气")
            hits.append((TEN_GOD_PARTY.get(g), g, slot, src))
        g = ten_god_of(day_gan, p["gan"])
        hits.append((TEN_GOD_PARTY.get(g), g, slot, "日主" if idx == 2 else "干"))
    return hits


def _h(table, party=None, god=None, sources=None, slots=None):
    out = []
    for party_name, god_name, slot, src in table:
        if party and party_name != party:
            continue
        if god and god_name != god:
            continue
        if sources and src not in sources:
            continue
        if slots and slot not in slots:
            continue
        out.append((god_name, slot, src))
    return out


def _fmt(hits):
    return "、".join("%s(%s%s)" % (g, s, src) for g, s, src in hits)


_LIUHE_N = {"".join(sorted(k)) for k in ZHI_LIU_HE}
_CHONG_N = {"".join(sorted(k)) for k in ZHI_CHONG}
_HAI_N = {"".join(sorted(k)) for k in ZHI_HAI}
_PO_N = {"".join(sorted(k)) for k in ZHI_PO}
_XING_N = {"".join(sorted(k)) for k in PARTIAL_XING}


def _pair_kind(a, b):
    key = "".join(sorted([a, b]))
    if a == b:
        return "伏吟" if a in SELF_XING else None
    if key in _LIUHE_N:
        return "合"
    if key in _CHONG_N:
        return "冲"
    if key in _HAI_N:
        return "害"
    if key in _PO_N:
        return "破"
    if key in _XING_N:
        return "刑"
    return None


def _branch_state(pillars, idx):
    zhi = pillars[idx]["zhi"]
    slot = pillars[idx].get("name") or ("年柱", "月柱", "日柱", "时柱")[idx]
    out = []
    for j, p in enumerate(pillars):
        if j == idx:
            continue
        kind = _pair_kind(zhi, p["zhi"])
        if kind:
            other = p.get("name") or ("年柱", "月柱", "日柱", "时柱")[j]
            out.append((kind, other))
    return slot, zhi, out


def _ma_of_chart(pillars):
    """命带驿马：年支/日支三合局之马若出现在四支中。返回 [(柱位, 马)]。"""
    out = []
    for idx in (0, 2):
        grp = _group_of(pillars[idx]["zhi"])
        if not grp:
            continue
        ma = YI_MA[grp]
        for p in pillars:
            if p["zhi"] == ma:
                out.append((p.get("name") or "?", ma))
    return out


def _elem_force(strength):
    force = strength.get("force") or {}
    return {el: round(force.get(el, 0.0), 3) for el in ("木", "火", "土", "金", "水")}


def _shares(strength):
    ps = strength.get("party_shares") or {}
    return {k: round(ps.get(k, 0.0) * 100.0, 1) for k in ("比劫", "印星", "食伤", "财星", "官杀")}


def _conf(n):
    return "高" if n >= 4 else ("中" if n >= 2 else "低")


def _basis(kind, detail):
    return {"kind": kind, "detail": detail}


# ── 流年触发 ────────────────────────────────────────────────────────────────
def _year_rows(report, day_gan):
    rows = []
    ma_targets = {}
    for idx in (0, 2):
        p = report["chart"]["pillars"][idx]
        grp = _group_of(p["zhi"])
        if grp:
            ma_targets.setdefault(YI_MA[grp], []).append(p.get("name") or "?")
    for ly in report["chart"].get("liunian") or []:
        gz = ly.get("ganzhi") or ""
        if len(gz) != 2:
            continue
        gg = ten_god_of(day_gan, gz[0])
        zb = ten_god_of(day_gan, HIDE_GAN.get(gz[1], [gz[1]])[0])
        timing = ly.get("timing") or {}
        rows.append({
            "year": ly.get("year"),
            "ganzhi": gz,
            "gan_god": gg,
            "zhi_god": zb,
            "gan_party": TEN_GOD_PARTY.get(gg),
            "zhi_party": TEN_GOD_PARTY.get(zb),
            "score": timing.get("score"),
            "label": timing.get("label"),
            "events": [e for e in (timing.get("events") or []) if isinstance(e, dict)],
            "ma": ma_targets.get(gz[1]) or [],
        })
    return rows, ma_targets


def _triggers(row):
    """一年对八域的触发：[(domain, kind, note, weight)]。"""
    out = []
    gz = row["ganzhi"]
    parties = {row["gan_party"], row["zhi_party"]}
    for e in row["events"]:
        tgt = e.get("target") or ""
        etype = e.get("type") or ""
        detail = e.get("detail") or ""
        delta = e.get("delta") or 0
        is_gan = etype.startswith("天干")
        if "日柱" in tgt and not is_gan:
            if "合" in etype:
                out.append(("love", "发力", "夫妻宫被引动：%s" % detail, 0.4))
            elif "冲" in etype:
                out.append(("love", "波动", "夫妻宫受冲：%s" % detail, 0.4))
                out.append(("health", "注意", "日支受冲：%s" % detail, 0.3))
        if "月柱" in tgt and ("冲" in etype or "害" in etype):
            out.append(("career", "波动", "事业宫被引动：%s" % detail, 0.35))
        if "年柱" in tgt and ("冲" in etype or "合" in etype):
            out.append(("family", "波动", "长辈/根基宫被引动：%s" % detail, 0.3))
            out.append(("move", "波动", "年柱引动：异地/远行事务增多", 0.3))
        if "时柱" in tgt and "冲" in etype:
            out.append(("family", "波动", "子女/晚辈宫受冲：%s" % detail, 0.3))
            out.append(("move", "波动", "时柱受冲：住地或远端事务变动", 0.3))
        if delta <= -0.5 and "忌" in (e.get("role") or ""):
            out.append(("health", "注意", "忌神受冲之年：%s" % detail, 0.2))

    if "财星" in parties:
        out.append(("wealth", "发力" if row["gan_party"] == "财星" else "波动",
                    "财星之年：财务与资源主题", 0.35))
        out.append(("love", "机遇", "财星之年：感情/伴侣主题活跃", 0.3))
        out.append(("study", "波动", "财星之年：现实事务易分心", 0.2))
    if "官杀" in parties:
        out.append(("career", "发力", "官杀之年：工作、责任、上级主题", 0.35))
        out.append(("study", "发力", "官杀之年：考试/功名主题", 0.3))
        out.append(("people", "注意", "官杀之年：上级压力或竞争", 0.25))
    if "印星" in parties:
        out.append(("study", "发力", "印星之年：学业、文书、证照主题", 0.4))
        out.append(("career", "机遇", "印星之年：平台、资质、靠山", 0.25))
        out.append(("people", "机遇", "印星之年：长辈/贵人助力", 0.25))
    if "食伤" in parties:
        out.append(("career", "波动", "食伤之年：求变、创意、自由职业", 0.3))
        out.append(("wealth", "机遇", "食伤之年：技艺生财的机会", 0.3))
        out.append(("family", "机遇", "食伤之年：子女/晚辈主题", 0.2))
    if "比劫" in parties:
        out.append(("wealth", "注意", "比劫之年：竞争、分账、破财风险", 0.4))
        out.append(("people", "注意", "比劫之年：同辈竞争或合作分利", 0.3))
        out.append(("family", "机遇", "比劫之年：兄弟/同辈主题", 0.2))
    if row["ma"]:
        out.append(("move", "发力", "驿马之年（%s）：出行、调动、异地机会" % "、".join(row["ma"]), 0.4))
    if gz[1] in ("寅", "申", "巳", "亥"):
        out.append(("move", "波动", "四马之地之年：环境变动概率升高", 0.2))
    return out


def _windows(rows, domain, limit_good=4, limit_warn=2):
    good, warn = [], []
    for row in rows:
        trig = None
        for d, kind, note, w in _triggers(row):
            if d != domain:
                continue
            if (trig is None) or w > trig[2]:
                trig = (kind, note, w, row)
        if not trig:
            continue
        kind, note, w, r = trig
        score = r["score"]
        # 有动静但当年基调偏忌：归入「需留意」，避免把忌年说成机遇
        if kind in ("机遇", "发力") and score is not None and score < -0.5:
            kind = "波动"
            note = note + "（当年基调%s %.1f，属「动而不顺」，宜谨慎）" % (
                r["label"] or "", score)
        item = {"year": r["year"], "ganzhi": r["ganzhi"], "kind": kind, "note": note,
                "score": score, "label": r["label"]}
        (good if kind in ("机遇", "发力") else warn).append(item)
    good.sort(key=lambda x: (-(x["score"] if x["score"] is not None else -9), x["year"]))
    warn.sort(key=lambda x: ((x["score"] if x["score"] is not None else 9), x["year"]))
    return good[:limit_good], warn[:limit_warn]


# ── 八个专题 ────────────────────────────────────────────────────────────────
def _topic_love(ctx):
    pillars, table, shares = ctx["pillars"], ctx["table"], ctx["shares"]
    sex = ctx["sex"]
    star = "财星" if sex == "男" else ("官杀" if sex == "女" else "财星")
    star_gods = ("正财", "偏财") if sex != "女" else ("正官", "七杀")
    star_name = "妻星（财）" if sex == "男" else ("夫星（官杀）" if sex == "女" else "感情星（财）")
    share = shares.get(star, 0)
    tou = [h for h in _h(table, party=star, sources=("干",))]
    cang = [h for h in _h(table, party=star, sources=("本气",))]
    day_slot, day_zhi, day_state = _branch_state(pillars, 2)
    spouse_hits = [h for h in _h(table, slots=("日柱",), sources=("本气",))]
    spouse_god = spouse_hits[0][0] if spouse_hits else None
    bijie = shares.get("比劫", 0)
    rel = ctx["shen_sha"]

    basis, signals = [], []
    basis.append(_basis("星位", "%s 结构力占比 %.1f%%，%s" % (
        star_name, share, ("透干见 " + _fmt(tou)) if tou else ("仅藏支 " + (_fmt(cang) or "无")))))
    signals.append(1 if share >= 18 else 0)
    if tou:
        signals.append(1)
    if spouse_god:
        basis.append(_basis("夫妻宫", "日支 %s 本气为 %s → 配偶气质偏「%s」" % (
            day_zhi, spouse_god, SPOUSE_TRAIT.get(spouse_god, "待定"))))
        signals.append(1)
    if day_state:
        txt = "、".join("%s%s" % (k, o) for k, o in day_state)
        basis.append(_basis("夫妻宫关系", "日支与它支：%s" % txt))
        if any(k == "冲" for k, _ in day_state):
            signals.append(1)
    for name in ("红鸾", "天喜", "桃花"):
        if name in rel:
            basis.append(_basis("神煞", "%s落在%s" % (name, "、".join(rel[name]))))
            signals.append(1)
    if sex == "男" and bijie >= 20:
        basis.append(_basis("比劫", "比劫占比 %.1f%% 偏高：感情上易有竞争或分账结构" % bijie))
        signals.append(1)

    summary = []
    if share >= 18 and tou:
        summary.append("感情线不算冷，星透又有底子，属于「想谈就能遇到」的类型，但要看你自己主不主动。")
    elif share >= 18:
        summary.append("感情主题在命里分量不轻，但星藏不透，多靠相处慢慢显现，不适合速成式择偶。")
    elif share <= 8:
        summary.append("感情星偏弱，缘分更依赖环境与主动经营，晚一点定反而稳。")
    else:
        summary.append("感情星在中位，属于正常节奏，遇到对的人就会推进。")
    if any(k == "冲" for k, _ in day_state):
        summary.append("夫妻宫受冲，关系里容易聚少离多或节奏反复，沟通频率比形式更重要。")
    elif any(k == "合" for k, _ in day_state):
        summary.append("夫妻宫被合，感情上容易被牵住、也容易遇到「黏在一起」的关系。")
    if sex == "男" and bijie >= 20:
        summary.append("比劫偏旺，注意「朋友/同辈介入感情」和钱上的边界。")
    if not sex:
        summary.append("（性别未知，按财星看感情；若是女命请按官杀重排。）")

    good, warn = _windows(ctx["rows"], "love")
    advice = ["先看对方是否稳定可靠、能不能一起扛事，再看心动程度。",
              "关系里的钱要分清：别用花钱来表达在意，也别替对方担债。",
              "合适年份多参与社交、少宅，机会多出现在「动」的场合。"]
    confidence = _conf(sum(list(signals)))
    if confidence == "低":
        advice.append("本项信号偏少，只作参考。")
    return {
        "id": "love", "title": "婚恋与伴侣", "summary": "".join(summary),
        "level": "偏顺" if (share >= 18 and not any(k == "冲" for k, _ in day_state)) else "中平",
        "confidence": confidence, "basis": basis,
        "windows": good + warn, "risks": [b["detail"] for b in basis if "冲" in b["detail"] or "竞争" in b["detail"]],
        "advice": advice,
    }


def _topic_career(ctx):
    pillars, table, shares = ctx["pillars"], ctx["table"], ctx["shares"]
    ge = ctx["pattern"]
    ys = ctx["ys"]
    order = sorted(shares.items(), key=lambda kv: -kv[1])
    top = [k for k, v in order if v >= 15][:2] or [order[0][0]]
    basis, signals = [], []

    path = []
    guan = shares.get("官杀", 0)
    shi = shares.get("食伤", 0)
    cai = shares.get("财星", 0)
    yin = shares.get("印星", 0)
    if guan >= 18:
        path.append("组织/管理/责任型（官杀）")
    if shi >= 12:
        path.append("技术/创意/表达型（食伤）")
    if cai >= 28:
        path.append("经营/资源/成交型（财星）")
    if yin >= 15:
        path.append("专业/学术/资格型（印星）")
    if not path:
        path.append("常规岗位稳步积累型")
    basis.append(_basis("结构", "五党结构力：%s；主路径 %s" % (
        "，".join("%s %.1f%%" % (PARTY_LABEL.get(k, k), v) for k, v in order),
        "＋".join(path))))
    signals.append(len(path))
    basis.append(_basis("格局", "%s（%s，%s）" % (ge.get("name"), ge.get("category"), ge.get("status"))))
    signals.append(1)
    xiang = [x.get("party") for x in (ge.get("xiang_shen") or [])]
    if xiang:
        basis.append(_basis("相神", "相神：%s" % "、".join(str(x) for x in xiang)))
        signals.append(1)

    role = ys.get("shen_roles") or {}
    yong_el = [el for el, r in role.items() if r == "用神"]
    xi_el = [el for el, r in role.items() if r == "喜神"]
    if yong_el:
        basis.append(_basis("环境", "用神五行为 %s：%s" % (
            "、".join(yong_el), "；".join(ELEMENT_ENV.get(e, "") for e in yong_el))))
        signals.append(1)

    god_industries = []
    for g, _slot, _src in _h(table, sources=("干",)):
        for item in GOD_INDUSTRY.get(g, []):
            if item not in god_industries:
                god_industries.append(item)
    for el in (yong_el or [])[:2]:
        subj = ELEMENT_SUBJECT.get(el)
        if subj and ("偏"+el not in god_industries):
            god_industries.append(subj)
    good, warn = _windows(ctx["rows"], "career")
    summary = ("事业路数是「%s」。" % "＋".join(path)) if path else ""
    if guan >= 18 and yin >= 12:
        summary += "官印相生的味道：适合在有规则、有平台的地方一级级往上走，不适合野蛮生长。"
    elif shi >= 15:
        summary += "食伤偏旺：靠手艺、表达或产品说话，比纯熬资历更快出成绩。"
    elif cai >= 30:
        summary += "财星偏重：离钱近的岗位（经营、成交、资源整合）最能发挥，但别单打独斗。"
    else:
        summary += "适合按部就班积累，靠专业度取胜。"
    if ctx["strength"].get("label") in ("身弱", "偏弱"):
        summary += "身偏弱，职场要先借平台和团队，前期别硬扛超出能力的盘子。"
    advice = [
        "选岗位先看「有没有靠山/平台/正规体系」，再看薪水。",
        "把一项硬技能练到能换钱的程度（用神五行方向优先）。",
        "换工作优先挑印星/官杀引动的年份（见下方窗口），别在纯忌年里裸辞。",
    ]
    if god_industries:
        advice.insert(1, "行业方向可参考：%s。" % "；".join(god_industries[:3]))
    status = ge.get("status") or ""
    if status == "成格":
        level = "偏顺"
    elif status in ("破格", "败中有救"):
        level = "偏吃力"
    else:
        level = "中平"
    return {
        "id": "career", "title": "事业与职业方向", "summary": summary,
        "level": level,
        "confidence": _conf(sum(signals)), "basis": basis, "windows": good + warn,
        "risks": [b["detail"] for b in basis if "压力" in b["detail"]],
        "advice": advice,
    }


def _topic_wealth(ctx):
    pillars, table, shares = ctx["pillars"], ctx["table"], ctx["shares"]
    zheng = _h(table, god="正财")
    pian = _h(table, god="偏财")
    tou_z = _h(table, god="正财", sources=("干",))
    tou_p = _h(table, god="偏财", sources=("干",))
    cai = shares.get("财星", 0)
    shi = shares.get("食伤", 0)
    bijie = shares.get("比劫", 0)
    guan = shares.get("官杀", 0)
    basis, signals = [], []

    def _spot(tou, cang):
        hits = tou or cang
        return "、".join("%s%s" % (s, src) for _g, s, src in hits) if hits else "无"

    basis.append(_basis("财星", "财星结构力 %.1f%%；正财：%s；偏财：%s" % (
        cai, _spot(tou_z, [h for h in zheng if h[2] == "本气"]),
        _spot(tou_p, [h for h in pian if h[2] == "本气"]))))
    signals.append(1 if cai >= 18 else 0)
    if shi >= 12:
        basis.append(_basis("生财", "食伤 %.1f%% 可生财：靠手艺/表达赚钱的线路成立" % shi))
        signals.append(1)
    if bijie >= 20:
        basis.append(_basis("夺财", "比劫 %.1f%% 偏旺：合作分账、朋友借贷是主要漏财点" % bijie))
        signals.append(1)
    if guan >= 18 and cai >= 15:
        basis.append(_basis("护财", "官杀 %.1f%% 护财：制度/平台/合同能帮你守住钱" % guan))
        signals.append(1)
    # 财库：按财星五行取库（木未/火戌/金丑/水辰），土无库
    day_el = ELEMENT_OF_GAN[ctx["day_gan"]]
    cai_el = KE[day_el]
    ku_of = {"木": "未", "火": "戌", "金": "丑", "水": "辰"}
    ku = ku_of.get(cai_el)
    zhai = [p["zhi"] for p in pillars if ku and p["zhi"] == ku]
    if zhai:
        basis.append(_basis("财库", "财星属%s，四支见财库 %s：财有库可存，重在「积累＋不折腾」" % (
            cai_el, ku)))
        signals.append(1)    

    role = ctx["ys"].get("shen_roles") or {}
    if role.get("财星") == "忌神" or (role.get("水") == "用神" and cai >= 30):
        pass
    good, warn = _windows(ctx["rows"], "wealth")
    summary = []
    if cai >= 28:
        summary.append("命里钱的分量重（财星 %.0f%%），天生离钱/资源近，机会多。" % cai)
        if ctx["strength"].get("label") in ("身弱", "偏弱"):
            summary.append("但身偏弱、财偏重，属于「看得见钱、要费力才留得住」：现金流和平台比机会更重要。")
    elif cai >= 15:
        summary.append("财务状况中上，稳定收入为主，偏财靠机会补充。")
    else:
        summary.append("财星不重，钱主要靠专业与稳定收入积累，别指望一夜暴富。")
    if shi >= 12:
        summary.append("食伤能生财：靠技能、内容或产品变现比纯打工更顺。")
    if bijie >= 20:
        summary.append("比劫偏旺，最忌合伙不分账、替人担保、借钱给朋友。")
    advice = ["收入分三份：生活、应急（6–12 个月）、长期；先建应急再谈投资。",
              "不借贷放大投资、不替人担保、不跟朋友合伙不分账。",
              "大额决策放在窗口里列出的「有利年份」，忌年只做防守。"]
    return {
        "id": "wealth", "title": "财富与赚钱方式", "summary": "".join(summary),
        "level": "偏顺" if cai >= 20 else "中平", "confidence": _conf(sum(signals)),
        "basis": basis, "windows": good + warn,
        "risks": [b["detail"] for b in basis if "漏财" in b["detail"] or "分账" in b["detail"]],
        "advice": advice,
    }


def _topic_study(ctx):
    table, shares = ctx["table"], ctx["shares"]
    yin = shares.get("印星", 0)
    guan = shares.get("官杀", 0)
    shi = shares.get("食伤", 0)
    rel = ctx["shen_sha"]
    basis, signals = [], []
    tou_yin = _h(table, party="印星", sources=("干",))
    basis.append(_basis("印星", "印星 %.1f%%%s" % (yin, ("，透干见 " + _fmt(tou_yin)) if tou_yin else "")))
    signals.append(1 if yin >= 15 else 0)
    if guan >= 15:
        basis.append(_basis("官星", "官杀 %.1f%%：考试/功名这条线有抓手" % guan))
        signals.append(1)
    if "文昌贵人" in rel:
        basis.append(_basis("神煞", "文昌贵人落 %s" % "、".join(rel["文昌贵人"])))
        signals.append(1)
    cai = shares.get("财星", 0)
    if cai - yin >= 8:
        basis.append(_basis("干扰", "财 %.1f%% 高于印：现实事务/赚钱念头容易挤占学习时间" % cai))
        signals.append(1)
    if shi >= 15:
        basis.append(_basis("实践", "食伤 %.1f%%：边做边学比纯啃书本更有效" % shi))
        signals.append(1)

    role = ctx["ys"].get("shen_roles") or {}
    yong_el = [el for el, r in role.items() if r in ("用神", "喜神")]
    subj = [ELEMENT_SUBJECT[e] for e in yong_el if e in ELEMENT_SUBJECT]
    if subj:
        basis.append(_basis("方向", "用神/喜神五行对应的学科方向：%s" % "；".join(subj[:2])))
        signals.append(1)

    good, warn = _windows(ctx["rows"], "study")
    summary = []
    if yin >= 18:
        summary.append("印星偏旺：适合系统学习、拿学历和资格证，学习本身就是你的加分项。")
    elif yin >= 10:
        summary.append("印星中位：学习能力正常，靠方法和环境（好老师/好平台）提升。")
    else:
        summary.append("印星偏弱：不适合纯理论长跑，更适合「用得上」的短周期技能学习。")
    if cai - yin >= 8:
        summary.append("财星压印：读书期间容易被赚钱/生活事务打断，需要固定学习时段。")
    if guan >= 15:
        summary.append("官星有根：考试型路线（考编、考证、升学）比自由发挥更占便宜。")
    advice = ["优先选「毕业就能换钱」的专业/证书，不要为了学位而学位。",
              "考试年份挑印星/官星引动的年份，避开财星旺的年份硬考。",
              "用神方向：%s。" % ("、".join(subj[:1]) if subj else "以专业匹配和现实条件为准")]
    return {
        "id": "study", "title": "学业与考试", "summary": "".join(summary),
        "level": "偏顺" if yin >= 15 else "中平", "confidence": _conf(sum(signals)),
        "basis": basis, "windows": good + warn,
        "risks": [b["detail"] for b in basis if "打断" in b["detail"]],
        "advice": advice,
    }


def _topic_health(ctx):
    strength = ctx["strength"]
    ys = ctx["ys"]
    force = _elem_force(strength)
    total = sum(force.values()) or 1.0
    role = ys.get("shen_roles") or {}
    basis, signals = [], []
    weakest = min(force, key=lambda k: force[k])
    strongest = max(force, key=lambda k: force[k])
    basis.append(_basis("五行偏枯", "结构力：%s；最弱 %s（%.1f%%），最旺 %s（%.1f%%）" % (
        "，".join("%s %.1f%%" % (k, v / total * 100) for k, v in force.items()),
        weakest, force[weakest] / total * 100, strongest, force[strongest] / total * 100)))
    signals.append(1)
    organ_w = ELEMENT_ORGAN.get(weakest, ("-", "-"))
    basis.append(_basis("弱处", "%s（%s）偏弱 → 对应 %s，平时多留意%s" % (
        weakest, role.get(weakest, "闲神"), organ_w[0], organ_w[1])))
    signals.append(1)
    organ_s = ELEMENT_ORGAN.get(strongest, ("-", "-"))
    basis.append(_basis("旺处", "%s（%s）偏旺 → %s 容易先出状况" % (
        strongest, role.get(strongest, "闲神"), organ_s[0])))
    th = ys.get("methods", {}).get("tiaohou") or {}
    if th.get("grade") in ("急需", "需要"):
        basis.append(_basis("调候", "寒暖指数 %.2f（%s）：%s" % (
            th.get("index", 0), th.get("grade"), th.get("desc") or "")))
        signals.append(1)

    good, warn = _windows(ctx["rows"], "health")
    summary = []
    tone = "偏薄，能量容易透支" if strength.get("label") in ("身弱", "偏弱") else "尚可，但别长期单点消耗"
    summary.append("体质底子%s：%s是长期要照顾的短板；%s容易因过度使用先报警。" % (
        tone, organ_w[0], organ_s[0]))
    if th.get("grade") == "急需":
        summary.append("寒暖失衡明显，作息和饮食一乱最先反应，夏天/熬夜尤其要注意。")
    if strength.get("label") in ("身弱", "偏弱"):
        summary.append("这类底子别长期高强度透支：恢复比硬撑重要。")
    advice = ["规律作息＋体检：重点看 %s 相关指标（仅作方向，不作诊断）。" % organ_w[0].split("、")[0],
              "运动选低冲击、长期能坚持的，别靠爆发式突击。",
              "忌年（下方窗口）少熬夜、少应酬、别硬扛，身体的事优先看医生。"]
    return {
        "id": "health", "title": "健康与体质", "summary": "".join(summary),
        "level": "中平", "confidence": _conf(sum(signals)), "basis": basis,
        "windows": good + warn, "risks": [organ_w[0] + "偏弱", organ_s[0] + "易过用"],
        "advice": advice,
    }


def _topic_family(ctx):
    pillars, table, shares = ctx["pillars"], ctx["table"], ctx["shares"]
    basis, signals = [], []
    yin = shares.get("印星", 0)
    cai = shares.get("财星", 0)
    bijie = shares.get("比劫", 0)
    shi = shares.get("食伤", 0)
    guan = shares.get("官杀", 0)
    sex = ctx["sex"]

    for idx, label in ((0, "年柱（祖辈/根基）"), (1, "月柱（父母/兄弟）"), (3, "时柱（子女/晚辈）")):
        slot, zhi, state = _branch_state(pillars, idx)
        if state:
            basis.append(_basis("宫位", "%s 与它支：%s" % (label, "、".join("%s%s" % (k, o) for k, o in state))))
            signals.append(1)
    basis.append(_basis("十神", "印 %.1f%%（母/长辈）、财 %.1f%%（父/现实）、比劫 %.1f%%（兄弟/同辈）、食伤 %.1f%%（子女/表达，男命）、官杀 %.1f%%（子女，女命）" % (
        yin, cai, bijie, shi, guan)))
    signals.append(1)

    child_star = "食伤" if sex != "女" else "官杀"
    child_share = shares.get(child_star, 0)
    if child_share >= 12:
        basis.append(_basis("子女星", "%s %.1f%%：子女缘分不薄" % (child_star, child_share)))
        signals.append(1)

    good, warn = _windows(ctx["rows"], "family")
    summary = []
    if any(k == "冲" for k, _ in _branch_state(pillars, 1)[2]):
        summary.append("父母/兄弟宫受冲：与家人容易聚少离多，或有各自奔波的结构，联系频率比同住更重要。")
    else:
        summary.append("父母/兄弟宫较稳：家庭关系以常态相处为主。")
    if bijie >= 20:
        summary.append("比劫偏旺：兄弟姐妹或同辈朋友的互动多，但钱上要分清。")
    if child_share >= 12:
        summary.append("子女星不弱：和晚辈/子女的缘分和话题都不缺。")
    else:
        summary.append("子女星偏弱：与子女的缘分更依赖后天经营（女命看官杀）。")
    advice = ["与家人相处少用「应该」标准，多用具体行动表达。",
              "家庭的钱账分开算，别让亲情替别人的财务决定兜底。",
              "宫位被引动的年份（见窗口）多回家/多沟通，别只转账。"]
    return {
        "id": "family", "title": "六亲与家庭", "summary": "".join(summary),
        "level": "中平", "confidence": _conf(sum(signals)), "basis": basis,
        "windows": good + warn, "risks": [],
        "advice": advice,
    }


def _topic_move(ctx):
    pillars = ctx["pillars"]
    basis, signals = [], []
    ma = _ma_of_chart(pillars)
    sibian = [p["zhi"] for p in pillars if p["zhi"] in ("寅", "申", "巳", "亥")]
    basis.append(_basis("驿马", ("命带驿马：%s" % "、".join("%s支%s" % (s, z) for s, z in ma)) if ma else "四支未见驿马"))
    signals.append(1 if ma else 0)
    basis.append(_basis("马地", "四马之地（寅申巳亥）见：%s" % ("、".join(sibian) if sibian else "无")))
    if sibian:
        signals.append(1)
    for idx, label in ((0, "年支（根基）"), (3, "时支（远方/晚年）")):
        slot, zhi, state = _branch_state(pillars, idx)
        if state:
            kinds = "、".join("%s%s" % (k, o) for k, o in state)
            basis.append(_basis("宫位", "%s %s 与它支：%s" % (label, zhi, kinds)))
            if any(k in ("冲", "合") for k, _ in state):
                signals.append(1)
    role = ctx["ys"].get("shen_roles") or {}
    yong = [el for el, r in role.items() if r == "用神"] or [el for el, r in role.items() if r == "喜神"]
    if yong:
        basis.append(_basis("方位", "用神五行 %s → 宜往 %s" % (
            "、".join(yong), "；".join("%s（%s）" % (ELEMENT_DIRECTION[e], ELEMENT_ENV[e]) for e in yong))))
        signals.append(1)

    good, warn = _windows(ctx["rows"], "move")
    summary = []
    if ma:
        summary.append("命带驿马，且马在四支内：这辈子不太容易「一辈子待在一个地方」，调动、外派、异地发展的机会比常人多。")
    else:
        summary.append("四支无驿马：迁移不是强驱动，若不是外部机会推着走，你更倾向在熟悉的地方扎根。")
    if len(sibian) >= 2:
        summary.append("四马之地占比高，动象明显：适合流动性强的行业或城市切换。")
    if yong:
        summary.append("方向以用神五行为准：%s。" % "；".join(
            "%s—%s" % (ELEMENT_DIRECTION[e], ELEMENT_ENV[e]) for e in yong[:2]))
    advice = ["换城市/出国优先挑驿马年、冲合年支时支的年份（见窗口）。",
              "真正的迁移要等「信号年」：文件、签证、offer 落在窗口里更顺。",
              "异地发展先解决「钱和落脚点」，别把浪漫当计划。"]
    return {
        "id": "move", "title": "迁移与方位", "summary": "".join(summary),
        "level": "偏顺" if ma else "中平", "confidence": _conf(sum(signals)),
        "basis": basis, "windows": good + warn, "risks": [],
        "advice": advice,
    }


def _topic_people(ctx):
    shares = ctx["shares"]
    rel = ctx["shen_sha"]
    table = ctx["table"]
    basis, signals = [], []
    for name in ("天乙贵人", "文昌贵人", "天德贵人", "月德贵人", "金舆"):
        if name in rel:
            basis.append(_basis("贵人", "%s落 %s" % (name, "、".join(rel[name]))))
            signals.append(1)
    if "羊刃" in rel:
        basis.append(_basis("锋芒", "羊刃落 %s：有冲劲，也容易与人硬碰" % "、".join(rel["羊刃"])))
        signals.append(1)
    if "劫煞" in rel:
        basis.append(_basis("耗损", "劫煞落 %s：该方向的人或事容易消耗你" % "、".join(rel["劫煞"])))
        signals.append(1)
    bijie = shares.get("比劫", 0)
    guan = shares.get("官杀", 0)
    if bijie >= 20:
        basis.append(_basis("同辈", "比劫 %.1f%%：同辈多、竞争也多" % bijie))
        signals.append(1)
    if guan >= 20:
        basis.append(_basis("上级", "官杀 %.1f%%：来自上级/规则的压力量不小" % guan))
        signals.append(1)
    good, warn = _windows(ctx["rows"], "people")
    summary = []
    if any(n in rel for n in ("天乙贵人", "天德贵人", "月德贵人")):
        summary.append("命带贵人星：关键节点容易遇到愿意拉你一把的人，但贵人只在「你先动起来」时才出现。")
    else:
        summary.append("贵人不显：靠同辈与平台更实际，主动结识比等机会重要。")
    if bijie >= 20:
        summary.append("同辈关系旺：朋友多、合作机会多，但要防「口头合伙、分账不清」。")
    if guan >= 20:
        summary.append("与上级/规则的关系是必修课：先适应规则，再谈发挥。")
    advice = ["合作先小人后君子：分工、分钱、退出机制写清楚。",
              "贵人年（见窗口）多主动拜访/请教，别等对方来找你。",
              "比劫/七杀旺的年份，少替人背书、少做担保、少卷入他人纠纷。"]
    return {
        "id": "people", "title": "人际、贵人与小人", "summary": "".join(summary),
        "level": "偏顺" if any(n in rel for n in ("天乙贵人", "天德贵人")) else "中平",
        "confidence": _conf(sum(signals)), "basis": basis, "windows": good + warn,
        "risks": [], "advice": advice,
    }


# ── 对外入口 ────────────────────────────────────────────────────────────────
def build_topics(report):
    pillars = report["chart"]["pillars"]
    day_gan = report["chart"]["day_gan"]
    strength = report["analysis"]["strength"]
    pattern = report["analysis"]["pattern"]
    ys = report["analysis"]["yong_shen"]
    table = _god_table(pillars, day_gan)
    rows, _ma = _year_rows(report, day_gan)
    ctx = {
        "report": report, "pillars": pillars, "day_gan": day_gan,
        "day_el": ELEMENT_OF_GAN.get(day_gan, ""),
        "sex": _sex_of(report), "strength": strength, "pattern": pattern, "ys": ys,
        "shen_sha": report["analysis"].get("shen_sha") or {},
        "table": table, "shares": _shares(strength), "rows": rows,
    }
    topics = [
        _topic_love(ctx), _topic_career(ctx), _topic_wealth(ctx), _topic_study(ctx),
        _topic_health(ctx), _topic_family(ctx), _topic_move(ctx), _topic_people(ctx),
    ]
    index = []
    for row in rows:
        trig = {}
        for domain, kind, note, w in _triggers(row):
            cur = trig.get(domain)
            if (not cur) or w > cur["weight"]:
                trig[domain] = {"kind": kind, "note": note, "weight": w}
        index.append({
            "year": row["year"], "ganzhi": row["ganzhi"], "label": row["label"],
            "score": row["score"],
            "domains": [{"domain": d, "kind": v["kind"], "note": v["note"]}
                        for d, v in sorted(trig.items())],
        })
    return {"version": VERSION, "model": MODEL, "limits": LIMITS,
            "topics": topics, "year_index": index}


TOPIC_IDS = ["love", "career", "wealth", "study", "health",
             "family", "move", "people"]


def filter_topics(data, only=None):
    """只保留指定专题域（only 为 id 列表），year_index 的域条目一并过滤。"""
    if not only:
        return data
    ids = [x for x in only if x in TOPIC_IDS]
    out = dict(data)
    out["topics"] = [t for t in data["topics"] if t.get("id") in ids]
    out["year_index"] = [
        dict(row, domains=[d for d in (row.get("domains") or [])
                           if d.get("domain") in ids])
        for row in (data.get("year_index") or [])
    ]
    out["selected"] = ids
    return out


def render_topics_text(data, only=None):
    picked = [t for t in data["topics"] if not only or t.get("id") in only]
    if only:
        title = "═══ 专题推测（%d 域） ═══" % len(picked)
    else:
        title = "═══ 专题推测（八域） ═══"
    lines = ["", title, "",
             "  " + MODEL]
    if only:
        lines.append("  只列你问的域：" + "、".join(t["title"] for t in picked))
    for t in picked:
        lines.append("")
        lines.append("◆ %s（倾向：%s；置信度：%s）" % (t["title"], t["level"], t["confidence"]))
        lines.append("  结论：%s" % t["summary"])
        lines.append("  依据：")
        for b in t["basis"]:
            lines.append("    · [%s] %s" % (b["kind"], b["detail"]))
        good = [w for w in t["windows"] if w["kind"] in ("机遇", "发力")]
        warn = [w for w in t["windows"] if w["kind"] not in ("机遇", "发力")]
        if good:
            lines.append("  有利年份：")
            for w in good:
                lines.append("    · %s %s（%s）：%s；当年综合 %s %s" % (
                    w["year"], w["ganzhi"], w["kind"], w["note"],
                    w["label"] or "-", w["score"] if w["score"] is not None else "-"))
        else:
            lines.append("  有利年份：近几年没有特别明显的发力年，以稳为主。")
        if warn:
            lines.append("  需留意年份：")
            for w in warn:
                lines.append("    · %s %s（%s）：%s；当年综合 %s %s" % (
                    w["year"], w["ganzhi"], w["kind"], w["note"],
                    w["label"] or "-", w["score"] if w["score"] is not None else "-"))
        else:
            lines.append("  需留意年份：暂无特别需要提防的年份。")
        if t["advice"]:
            lines.append("  建议：")
            for a in t["advice"]:
                lines.append("    · %s" % a)
    lines.append("")
    lines.append("  说明：")
    for x in data["limits"]:
        lines.append("    · %s" % x)
    return "\n".join(lines)
