# -*- coding: utf-8 -*-
"""八字分析层：五行量化、旺衰、格局、喜用忌、神煞、干支合冲刑害。

说明：排盘（四柱、藏干、十神、大运）是确定性的历法计算；本模块的旺衰评分、
格局判定与喜用取舍属于「可解释的术数模型」，不是物理测量。所有数字都按
文件中写明的权重算出，便于复核与调整，而不是黑箱输出。
"""

from chart import (
    GAN, ZHI, HIDE_GAN, HIDE_RATIO, SHI_SHEN,
    ELEMENT_OF_GAN, ELEMENT_OF_ZHI,
)

# ── 五行生克 ─────────────────────────────────────────────────────────────────
ELEMENTS = ("木", "火", "土", "金", "水")
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}   # 我生
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}       # 我克


def _sheng_of(element):
    """生我的五行。"""
    for k, v in SHENG.items():
        if v == element:
            return k
    return None


# ── 五行权重（可解释参数）────────────────────────────────────────────────────
# 天干各 1.0；地支按柱位加权：月令最重，日支次之。
GAN_WEIGHT = 1.0
ZHI_WEIGHT = {"年柱": 1.0, "月柱": 1.6, "日柱": 1.2, "时柱": 1.0}

TEN_GOD_PARTY = {
    "比肩": "比劫", "劫财": "比劫",
    "正印": "印星", "偏印": "印星",
    "食神": "食伤", "伤官": "食伤",
    "正财": "财星", "偏财": "财星",
    "正官": "官杀", "七杀": "官杀",
}


def ten_god_of(day_gan, gan):
    if gan == day_gan:
        return "比肩"
    return SHI_SHEN[day_gan + gan]


def wuxing_profile(pillars, day_gan):
    """按权重统计八字五行力量，返回总量、百分比、明细。"""
    detail = []
    totals = {e: 0.0 for e in ELEMENTS}

    for p in pillars:
        w = GAN_WEIGHT
        el = p["wuxing_gan"]
        totals[el] += w
        detail.append({
            "source": "%s天干%s" % (p["name"], p["gan"]),
            "gan": p["gan"], "element": el, "weight": round(w, 3),
            "ten_god": ten_god_of(day_gan, p["gan"]),
        })
        base = ZHI_WEIGHT.get(p["name"], 1.0)
        hidden = HIDE_GAN[p["zhi"]]
        ratios = HIDE_RATIO[len(hidden)]
        for h, ratio in zip(hidden, ratios):
            w = base * ratio
            el = ELEMENT_OF_GAN[h]
            totals[el] += w
            detail.append({
                "source": "%s地支%s藏%s" % (p["name"], p["zhi"], h),
                "gan": h, "element": el, "weight": round(w, 3),
                "ten_god": ten_god_of(day_gan, h),
            })

    total = sum(totals.values())
    pct = {e: round(v / total * 100, 1) if total else 0.0 for e, v in totals.items()}
    return {
        "totals": {e: round(v, 2) for e, v in totals.items()},
        "percent": pct,
        "total": round(total, 2),
        "detail": detail,
    }


def _season(month_zhi):
    if month_zhi in "寅卯辰":
        return "春"
    if month_zhi in "巳午未":
        return "夏"
    if month_zhi in "申酉戌":
        return "秋"
    return "冬"


def _de_ling(day_el, month_el):
    """得令状态：旺/相/休/囚/死。"""
    if month_el == day_el:
        return "旺"
    if SHENG[month_el] == day_el:
        return "相"
    if SHENG[day_el] == month_el:
        return "休"
    if KE[day_el] == month_el:
        return "囚"
    if KE[month_el] == day_el:
        return "死"
    return "平"


def strength(pillars, day_gan, profile):
    """旺衰评分：同党（比劫+印）占比 + 得令/得地/得势修正。"""
    day_el = ELEMENT_OF_GAN[day_gan]
    totals = profile["totals"]
    same = totals[day_el] + totals[_sheng_of(day_el)]
    other = sum(totals.values()) - same
    total = same + other
    ratio = same / total if total else 0.0

    month_zhi = pillars[1]["zhi"]
    month_el = ELEMENT_OF_ZHI[month_zhi]
    ling = _de_ling(day_el, month_el)

    # 得地：地支藏干中出现比劫或印星（日主有根）
    roots = []
    for p in pillars:
        for h in HIDE_GAN[p["zhi"]]:
            el = ELEMENT_OF_GAN[h]
            if el == day_el or el == _sheng_of(day_el):
                roots.append("%s%s藏%s" % (p["name"], p["zhi"], h))
    # 得势：天干同党（比劫/印）数量（日主本身不计入「同党个数」）
    helpers = 0
    for idx, p in enumerate(pillars):
        if idx == 2:          # 日柱天干是日主本身，不是「另一个同党」
            continue
        god = ten_god_of(day_gan, p["gan"])
        if TEN_GOD_PARTY.get(god) in ("比劫", "印星"):
            helpers += 1

    score = ratio
    score += {"旺": 0.05, "相": 0.03, "休": -0.02, "囚": -0.04, "死": -0.06}.get(ling, 0.0)
    if roots:
        score += 0.03
    if helpers >= 2:
        score += 0.02
    score = max(0.0, min(1.0, score))

    if score >= 0.62:
        label = "身强"
    elif score >= 0.53:
        label = "偏强"
    elif score >= 0.45:
        label = "中和"
    elif score >= 0.37:
        label = "偏弱"
    else:
        label = "身弱"

    # 特殊格局候选（只提示，需人工判断）
    special = []
    if ratio >= 0.85:
        special.append("同党占比 ≥85%，需人工判断是否属「从强/专旺」；若是，常规扶抑结论不适用。")
    elif ratio <= 0.15:
        special.append("异党占比 ≥85%，需人工判断是否属「从弱/从格」；若是，常规扶抑结论不适用。")

    return {
        "ratio": round(ratio, 4),
        "score": round(score, 4),
        "label": label,
        "same_party": {
            "total": round(same, 2),
            "percent": round(ratio * 100, 1),
            "elements": [day_el, _sheng_of(day_el)],
        },
        "other_party": {
            "total": round(other, 2),
            "percent": round((1 - ratio) * 100, 1),
        },
        "de_ling": {"month_zhi": month_zhi, "month_element": month_el,
                    "state": ling, "season": _season(month_zhi)},
        "de_di": roots,
        "de_shi_heads": helpers,
        "special_hints": special,
        "model": "同党占比 = (比劫+印)/(全部)；再按得令/得地/得势加减，阈值 0.62/0.53/0.45/0.37",
    }


# ── 格局 ─────────────────────────────────────────────────────────────────────
GE_JU_BY_GOD = {
    "比肩": "建禄格",
    "劫财": "月劫格",
    "正官": "正官格",
    "七杀": "七杀格",
    "正财": "正财格",
    "偏财": "偏财格",
    "食神": "食神格",
    "伤官": "伤官格",
    "正印": "正印格",
    "偏印": "偏印格",
}


def pattern(pillars, day_gan):
    month = pillars[1]
    hidden = HIDE_GAN[month["zhi"]]
    ben_qi = hidden[0]
    god = ten_god_of(day_gan, ben_qi)

    # 月令藏干透干情况（年/月/时干出现月令所藏之干；日干为日主本身，不计透出）
    transparent = []
    for h in hidden:
        for idx, p in enumerate(pillars):
            if idx == 2:
                continue
            if p["gan"] == h:
                transparent.append({"gan": h, "god": ten_god_of(day_gan, h),
                                    "pillar": p["name"]})

    # 取格顺序：禄/刃月 → 杂气月看透干 → 本气
    used_god = god
    if month["zhi"] == LU_SHEN[day_gan]:
        ge = "建禄格"
        used_god = "比肩"
        basis = "月令%s为日主临官（禄）位" % month["zhi"]
    elif month["zhi"] == YANG_REN[day_gan]:
        ge = "月劫格（阳刃格）"
        used_god = "劫财"
        basis = "月令%s为日主帝旺（刃）位" % month["zhi"]
    elif month["zhi"] in "辰戌丑未" and transparent:
        tg = transparent[0]["god"]
        used_god = tg
        if tg in ("比肩", "劫财"):
            ge = "比劫格（杂气）"
        else:
            ge = GE_JU_BY_GOD.get(tg, "杂气格")
        basis = "杂气月，藏干%s（%s）透于%s" % (
            transparent[0]["gan"], tg, transparent[0]["pillar"])
    elif god in ("比肩", "劫财"):
        ge = "比劫格（杂气）"
        basis = "月令本气%s → %s" % (ben_qi, god)
    else:
        ge = GE_JU_BY_GOD.get(god, "杂气格")
        basis = "月令本气%s → %s" % (ben_qi, god)

    # 全局十神统计（年/月/时干 + 四支本气；日主天干不重复计入）
    gods = []
    for idx, p in enumerate(pillars):
        if idx != 2:
            gods.append(ten_god_of(day_gan, p["gan"]))
        gods.append(ten_god_of(day_gan, HIDE_GAN[p["zhi"]][0]))
    count = {}
    for g in gods:
        count[g] = count.get(g, 0) + 1

    hints = []
    if used_god == "正官" and count.get("伤官", 0) >= 1:
        hints.append("官格见伤官：伤官见官，需有印制伤或财通关。")
    if used_god == "七杀" and count.get("食神", 0) >= 1:
        hints.append("杀格见食神：食神制杀，为常用的成格路径。")
    if used_god in ("正财", "偏财") and (count.get("比肩", 0) + count.get("劫财", 0)) >= 2:
        hints.append("财格比劫偏多：需官杀护财或食伤通关。")
    if used_god == "食神" and count.get("偏印", 0) >= 1:
        hints.append("食神格见偏印：枭神夺食，需财制枭。")
    if used_god in ("正印", "偏印") and count.get("正财", 0) + count.get("偏财", 0) >= 2:
        hints.append("印格财多：财星破印，需比劫护印。")
    if ge.startswith("建禄格") or ge.startswith("月劫格"):
        if count.get("正官", 0) + count.get("七杀", 0) == 0:
            hints.append("禄/劫格无官杀：多主竞争、自主，宜见官杀或食伤立格。")

    return {
        "month_zhi": month["zhi"],
        "month_ben_qi": ben_qi,
        "month_god": god,          # 月令本气十神（原始信息）
        "used_god": used_god,      # 实际取格所用十神（杂气月可能来自透干）
        "name": ge,
        "basis": basis,            # 取格依据的说明文字
        "transparent": transparent,
        "hints": hints,
        "note": "默认以月令本气取格；杂气月（辰戌丑未）先看藏干透出。"
                "成格/破格细节请结合 references/interpretation.md 复核。",
    }


SEASON_TIAOHOU = {
    "冬": ("火", None, "冬月水寒，调候多喜火来暖局（火为官杀或印，视日主而定）。"),
    "夏": ("水", None, "夏月火炎，调候多喜水来润局（水为财或官杀，视日主而定）。"),
    "春": ("火", "金", "春月木旺，调候多取火以泄秀，或金以修削，视日主旺衰。"),
    "秋": ("水", "火", "秋月金旺，调候多取水以润，或火以炼，视日主旺衰。"),
}


def _dedupe(seq):
    out = []
    for x in seq:
        if x and x not in out:
            out.append(x)
    return out


def _format_members(hits):
    """把 [(十神, 柱位), ...] 合并成「官杀(年、月)、印(时)」式短标签。"""
    groups = {}
    order = []
    for g, s in hits:
        if g not in groups:
            groups[g] = []
            order.append(g)
        if s not in groups[g]:
            groups[g].append(s)
    return ["%s(%s)" % (g, "、".join(groups[g])) for g in order]


def yong_shen(day_gan, profile, st, ge):
    """按旺衰给出喜用/忌，并给出主次与「调候 vs 扶抑」冲突提示。

    属于规则化的术数模型，不是预测；模型参数保留在返回字段里便于复核。
    """
    day_el = ELEMENT_OF_GAN[day_gan]
    yin = _sheng_of(day_el)          # 印：生我
    bi = day_el                     # 比劫：同我
    shi = SHENG[day_el]             # 食伤：我生
    cai = KE[day_el]                # 财：我克
    guan = None                     # 官杀：克我
    for k, v in KE.items():
        if v == day_el:
            guan = k
            break

    label = st["label"]
    season = st["de_ling"]["season"]
    th_primary, th_secondary, tiaohou = SEASON_TIAOHOU[season]
    reasons = []
    conflict = None

    if label in ("身强", "偏强"):
        useful = [guan, shi, cai]
        avoid = [yin, bi]
        primary = [guan]
        secondary = [shi, cai]
        reasons.append("日主偏旺，取克、泄、耗为用：官杀克身为先，食伤泄秀次之，财星耗身为辅。")
    elif label in ("身弱", "偏弱"):
        useful = [yin, bi]
        avoid = [shi, cai, guan]
        primary = [yin]
        secondary = [bi]
        reasons.append("日主偏弱，取生扶为用：印星生身为先，比劫帮身次之；食伤、财、官杀为忌。")
    else:
        primary = [th_primary]
        secondary = [e for e in (th_secondary,) if e]
        useful = primary + secondary
        avoid = []
        reasons.append("日主中和，扶抑不是主导，取调候与流通：%s" % tiaohou)

    if primary[0] in avoid:
        conflict = ("调候所喜的「%s」恰是扶抑所忌（%s）：两法冲突时以保全日主为先，"
                    "调候只作参考，或取能通关的五行。" % (primary[0], "、".join(avoid)))
        reasons.append(conflict)
    elif th_primary in avoid:
        conflict = ("调候喜「%s」以调寒暖，但「%s」在扶抑上属忌神："
                    "此时以扶抑（%s）为主，调候只作次要修正，不硬取调候。" % (
                        th_primary, th_primary, "、".join(primary)))
        reasons.append(conflict)

    return {
        "useful_elements": _dedupe(useful),
        "avoid_elements": _dedupe(avoid),
        "primary_elements": _dedupe(primary),
        "secondary_elements": _dedupe(secondary),
        "reasons": reasons,
        "reason": "；".join(r.rstrip("。") for r in reasons),
        "tiaohou": tiaohou,
        "tiaohou_element": th_primary,
        "conflict": conflict,
        "caveat": "喜用取舍在术数内部即有多派；此结果仅为本模型的规则化建议，"
                  "需结合大运、格局成败与调候综合判断，不构成对具体事件的预测。",
    }


def flow_favorability(ys, ganzhi):
    """给一个大运/流年干支按喜用五行打分（-4~4，可解释的规则模型）。

    权重：天干/地支本气 1.0；主用 ×2、次用 ×1.3、喜用 ×1、忌神 ×-1.5；
    藏干各 0.3。结果用于大运、流年的「基调加减」，不是事件预测。
    """
    useful = set(ys.get("useful_elements") or [])
    avoid = set(ys.get("avoid_elements") or [])
    primary = set(ys.get("primary_elements") or [])
    secondary = set(ys.get("secondary_elements") or [])

    if len(ganzhi) < 2 or ganzhi[0] not in ELEMENT_OF_GAN or ganzhi[1] not in ELEMENT_OF_ZHI:
        return {"label": "中性", "score": 0.0, "reasons": []}

    def weight(el, base):
        if el in primary:
            return base * 2.0
        if el in secondary:
            return base * 1.3
        if el in useful:
            return base
        if el in avoid:
            return -base * 1.5
        return 0.0

    gan, zhi = ganzhi[0], ganzhi[1]
    score = 0.0
    reasons = []

    eg = ELEMENT_OF_GAN[gan]
    score += weight(eg, 1.0)
    if eg in primary:
        reasons.append("天干%s属%s（主用）" % (gan, eg))
    elif eg in useful:
        reasons.append("天干%s属%s（喜用）" % (gan, eg))
    elif eg in avoid:
        reasons.append("天干%s属%s（忌神）" % (gan, eg))

    ez = ELEMENT_OF_ZHI[zhi]
    score += weight(ez, 1.0)
    if ez in primary:
        reasons.append("地支%s属%s（主用）" % (zhi, ez))
    elif ez in useful:
        reasons.append("地支%s属%s（喜用）" % (zhi, ez))
    elif ez in avoid:
        reasons.append("地支%s属%s（忌神）" % (zhi, ez))

    hidden_notes = []
    for h in HIDE_GAN[zhi]:
        el = ELEMENT_OF_GAN[h]
        w = weight(el, 0.3)
        score += w
        if w and len(hidden_notes) < 2:
            flag = "喜" if w > 0 else "忌"
            hidden_notes.append("藏%s属%s（%s）" % (h, el, flag))
    if hidden_notes:
        reasons.append("；".join(hidden_notes))

    score = max(-4.0, min(4.0, round(score, 2)))
    if score >= 1.6:
        label = "喜"
    elif score >= 0.5:
        label = "偏喜"
    elif score > -0.5:
        label = "中性"
    elif score > -1.6:
        label = "偏忌"
    else:
        label = "忌"
    return {"label": label, "score": score, "reasons": reasons}


def _god_entries(pillars, day_gan):
    """返回 (透干, 各支本气, 所有藏干) 的 (十神, 柱位) 列表。"""
    tou, ben, cang = [], [], []
    for idx, p in enumerate(pillars):
        if idx != 2:  # 日干是日主，不算透出的十神
            tou.append((ten_god_of(day_gan, p["gan"]), p["name"]))
        hidden = HIDE_GAN[p["zhi"]]
        ben.append((ten_god_of(day_gan, hidden[0]), p["name"]))
        for h in hidden:
            cang.append((ten_god_of(day_gan, h), p["name"]))
    return tou, ben, cang


def _struct_rank(pillars, day_gan, names):
    """某组十神的出现强度：3=透干，2=月令本气，1=其他本气，0=仅藏支，-1=无。"""
    tou, ben, cang = _god_entries(pillars, day_gan)
    want = set(names)
    hits_tou = [(g, s) for g, s in tou if g in want]
    hits_ben = [(g, s) for g, s in ben if g in want]
    hits_cang = [(g, s) for g, s in cang if g in want]
    if not hits_cang:
        return -1, []
    if hits_tou:
        return 3, hits_tou
    if hits_ben:
        if any(s == "月柱" for _, s in hits_ben):
            return 2, hits_ben
        return 1, hits_ben
    return 0, hits_cang


def combinations(pillars, day_gan):
    """识别常见十神结构组合（透干/月令优先，藏支组合不列，避免噪声）。

    返回 [{name, level, members, note}]；仅为结构提示，是否成格仍需结合旺衰与破格因素。
    """
    rules = [
        ("官印相生", ("正官",), ("正印", "偏印"),
         "官生印、印生身，主贵气与承接；身弱更喜，身强则看是否印重身滞。"),
        ("杀印相生", ("七杀",), ("正印", "偏印"),
         "七杀有印化，杀不攻身而转生扶；多主压力可转化为权柄。"),
        ("食神制杀", ("七杀",), ("食神",),
         "食神制七杀，主以才艺/规则化解压力；忌财星透出党杀破格。"),
        ("伤官配印", ("伤官",), ("正印", "偏印"),
         "伤官配印，主聪明有锋芒但知收敛；印轻财重时易破格。"),
        ("食伤生财", ("食神", "伤官"), ("正财", "偏财"),
         "食伤生财，主以才华换资源；身弱财多时需印比帮身。"),
        ("财官相生", ("正财", "偏财"), ("正官",),
         "财生官，主资源与责任相连；官杀混杂时需清格。"),
        ("枭神夺食", ("偏印",), ("食神",),
         "偏印夺食，主思路多而执行受阻；喜财星制枭、或比劫通关。"),
        ("伤官见官", ("伤官",), ("正官",),
         "伤官见官，传统主是非与规则冲突；有印制伤或财通关则减。"),
        ("财星破印", ("正财", "偏财"), ("正印", "偏印"),
         "财星破印，主现实压力挤占学习/长辈助力；身弱印为用神时尤需注意。"),
    ]
    out = []
    seen = set()
    for name, a_names, b_names, note in rules:
        ra, ha = _struct_rank(pillars, day_gan, a_names)
        rb, hb = _struct_rank(pillars, day_gan, b_names)
        if ra < 0 or rb < 0:
            continue
        top = max(ra, rb)
        if top < 2:   # 至少一方透干或居月令本气，否则视为藏支噪声
            continue
        if ra >= 3 and rb >= 3:
            level = "透干"
        elif top >= 3:
            level = "半透"
        else:
            level = "月令"
        members = _format_members(ha + hb)
        key = (name, tuple(members))
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": name, "level": level, "members": members,
                    "note": note, "rank": top})

    # 特殊组合：需要计数/阳刃等额外条件
    tou, ben, _ = _god_entries(pillars, day_gan)
    bi_jie = [g for g, _ in tou + ben if g in ("比肩", "劫财")]
    cai_present = any(g in ("正财", "偏财") for g, _ in tou + ben)
    if len(bi_jie) >= 2 and cai_present and "比劫夺财" not in seen:
        r_bj, _ = _struct_rank(pillars, day_gan, ("比肩", "劫财"))
        out.append({"name": "比劫夺财", "level": "透干/本气",
                    "members": ["比劫×%d" % len(bi_jie)],
                    "note": "比劫党多而财星受夺：需官杀制比劫或食伤通关，财才可保。",
                    "rank": max(r_bj, 2)})
        seen.add("比劫夺财")

    zhis = [p["zhi"] for p in pillars]
    ren = YANG_REN.get(day_gan)
    if ren and ren in zhis:
        ra7, ha7 = _struct_rank(pillars, day_gan, ("七杀",))
        if ra7 >= 2 and "杀刃相济" not in seen:
            out.append({"name": "杀刃相济", "level": "月令/透干",
                        "members": _format_members(ha7) + ["阳刃(%s)" % ren],
                        "note": "七杀配阳刃，主魄力与承压；忌刃重无制或杀轻刃旺。",
                        "rank": max(ra7, 2)})
            seen.add("杀刃相济")

    if "官杀混杂" not in seen:
        ra_g, ha_g = _struct_rank(pillars, day_gan, ("正官",))
        ra_s, ha_s = _struct_rank(pillars, day_gan, ("七杀",))
        if ra_g >= 1 and ra_s >= 1:
            members = _format_members(ha_g + ha_s)
            out.append({"name": "官杀混杂", "level": "本气/透干",
                        "members": members,
                        "note": "正官与七杀同见，传统称官杀混杂：需去杀留官或去官留杀，"
                                "否则压力与规则易相互牵扯。",
                        "rank": max(ra_g, ra_s)})
            seen.add("官杀混杂")

    # 按透干程度排序（同 rank 时「透干 > 半透 > 月令」，再保持规则顺序）
    _level_order = {"透干": 3, "半透": 2, "月令": 1}
    out.sort(key=lambda x: (-(x.get("rank") or 0),
                            -_level_order.get(x.get("level"), 1)))

    for item in out:
        item["note"] = item["note"] + "（结构提示，成格需复核旺衰与破格因素。）"
    return out


# ── 神煞 ─────────────────────────────────────────────────────────────────────
TIAN_YI = {"甲": "丑未", "戊": "丑未", "庚": "丑未", "乙": "子申", "己": "子申",
           "丙": "亥酉", "丁": "亥酉", "壬": "卯巳", "癸": "卯巳", "辛": "寅午"}
WEN_CHANG = {"甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
             "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯"}
YI_MA = {"申子辰": "寅", "寅午戌": "申", "巳酉丑": "亥", "亥卯未": "巳"}
TAO_HUA = {"申子辰": "酉", "寅午戌": "卯", "巳酉丑": "午", "亥卯未": "子"}
HUA_GAI = {"申子辰": "辰", "寅午戌": "戌", "巳酉丑": "丑", "亥卯未": "未"}
JIANG_XING = {"申子辰": "子", "寅午戌": "午", "巳酉丑": "酉", "亥卯未": "卯"}
YANG_REN = {"甲": "卯", "乙": "寅", "丙": "午", "丁": "巳", "戊": "午",
            "己": "巳", "庚": "酉", "辛": "申", "壬": "子", "癸": "亥"}
LU_SHEN = {"甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
           "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子"}
YUE_DE = {"寅午戌": "丙", "申子辰": "壬", "亥卯未": "甲", "巳酉丑": "庚"}
TIAN_DE = {"寅": "丁", "卯": "申", "辰": "壬", "巳": "辛", "午": "亥", "未": "甲",
           "申": "癸", "酉": "寅", "戌": "丙", "亥": "乙", "子": "巳", "丑": "庚"}
GU_CHEN = {"亥子丑": "寅", "寅卯辰": "巳", "巳午未": "申", "申酉戌": "亥"}
GUA_SU = {"亥子丑": "戌", "寅卯辰": "丑", "巳午未": "辰", "申酉戌": "未"}
HONG_LUAN = {"子": "卯", "丑": "寅", "寅": "丑", "卯": "子", "辰": "亥", "巳": "戌",
             "午": "酉", "未": "申", "申": "未", "酉": "午", "戌": "巳", "亥": "辰"}
KUI_GANG = {"庚辰", "庚戌", "壬辰", "戊戌"}
# 三合局神煞（以年支所属局查）
WANG_SHEN = {"申子辰": "亥", "寅午戌": "巳", "巳酉丑": "申", "亥卯未": "寅"}
JIE_SHA = {"申子辰": "巳", "寅午戌": "亥", "巳酉丑": "寅", "亥卯未": "申"}
ZAI_SHA = {"申子辰": "午", "寅午戌": "子", "巳酉丑": "卯", "亥卯未": "酉"}
# 金舆（以日干查）
JIN_YU = {"甲": "辰", "乙": "巳", "丙": "未", "丁": "申", "戊": "未",
          "己": "申", "庚": "戌", "辛": "亥", "壬": "丑", "癸": "寅"}


def _group_of(zhi):
    for key in ("申子辰", "寅午戌", "巳酉丑", "亥卯未"):
        if zhi in key:
            return key
    return None


def _year_group(zhi):
    for key in ("亥子丑", "寅卯辰", "巳午未", "申酉戌"):
        if zhi in key:
            return key
    return None


def shen_sha(pillars, day_gan):
    """常用神煞（以日干、年支、月支为主查），返回 {神煞名: [命中的柱位/说明]}。"""
    year_zhi = pillars[0]["zhi"]
    month_zhi = pillars[1]["zhi"]
    day_zhi = pillars[2]["zhi"]
    hits = {}

    def add(name, matched):
        if matched:
            hits[name] = matched

    # 以日干查地支
    for name, table in (("天乙贵人", TIAN_YI), ("文昌贵人", WEN_CHANG),
                        ("羊刃", YANG_REN), ("禄神", LU_SHEN)):
        target = table.get(day_gan)
        matched = []
        if target:
            for p in pillars:
                if p["zhi"] in target:
                    matched.append("%s支%s" % (p["name"], p["zhi"]))
        add(name, matched)

    # 以年支三合查
    yg = _group_of(year_zhi)
    if yg:
        for name, table in (("驿马", YI_MA), ("桃花", TAO_HUA),
                            ("华盖", HUA_GAI), ("将星", JIANG_XING)):
            target = table[yg]
            matched = [p["name"] + "支" + p["zhi"] for p in pillars if p["zhi"] == target]
            add(name, matched)

    # 月德 / 天德
    if month_zhi:
        mg = _group_of(month_zhi)
        if mg:
            target = YUE_DE[mg]
            matched = [p["name"] + "干" + p["gan"] for p in pillars if p["gan"] == target]
            add("月德贵人", matched)
        target = TIAN_DE.get(month_zhi)
        if target:
            matched = [p["name"] + ("支" if target in ZHI else "干") + target
                       for p in pillars
                       if p["gan"] == target or p["zhi"] == target]
            add("天德贵人", matched)

    # 孤辰 / 寡宿（以年支查）
    year_group = _year_group(year_zhi)
    if year_group:
        add("孤辰", [p["name"] + "支" + p["zhi"] for p in pillars
                    if p["zhi"] == GU_CHEN[year_group]])
        add("寡宿", [p["name"] + "支" + p["zhi"] for p in pillars
                    if p["zhi"] == GUA_SU[year_group]])

    # 红鸾 / 天喜（以年支查）
    hl = HONG_LUAN.get(year_zhi)
    if hl:
        add("红鸾", [p["name"] + "支" + p["zhi"] for p in pillars if p["zhi"] == hl])
        tx = ZHI[(ZHI.index(hl) + 6) % 12]
        add("天喜", [p["name"] + "支" + p["zhi"] for p in pillars if p["zhi"] == tx])

    # 魁罡（日柱）
    day_gz = pillars[2].get("ganzhi") or (pillars[2]["gan"] + pillars[2]["zhi"])
    if day_gz in KUI_GANG:
        add("魁罡", ["日柱" + day_gz])

    # 亡神 / 劫煞 / 灾煞（以年支三合局查）
    if yg:
        for name, table in (("亡神", WANG_SHEN), ("劫煞", JIE_SHA), ("灾煞", ZAI_SHA)):
            target = table[yg]
            add(name, [p["name"] + "支" + p["zhi"] for p in pillars if p["zhi"] == target])

    # 金舆（以日干查）
    jy = JIN_YU.get(day_gan)
    if jy:
        add("金舆", [p["name"] + "支" + p["zhi"] for p in pillars if p["zhi"] == jy])

    # 日柱旬空落于其他柱
    day_xk = pillars[2].get("xunkong")
    if day_xk:
        for z in day_xk:
            add("日柱旬空", [p["name"] + "支" + p["zhi"] for p in pillars if p["zhi"] == z])

    return hits


# ── 干支关系 ─────────────────────────────────────────────────────────────────
GAN_HE = {"甲己": "土", "乙庚": "金", "丙辛": "水", "丁壬": "木", "戊癸": "火"}
GAN_CHONG = ("甲庚", "乙辛", "丙壬", "丁癸")
ZHI_LIU_HE = {"子丑": "土", "寅亥": "木", "卯戌": "火", "辰酉": "金",
              "巳申": "水", "午未": "土"}
ZHI_SAN_HE = {"申子辰": "水", "亥卯未": "木", "寅午戌": "火", "巳酉丑": "金"}
ZHI_SAN_HUI = {"寅卯辰": "木", "巳午未": "火", "申酉戌": "金", "亥子丑": "水"}
ZHI_CHONG = ("子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥")
ZHI_HAI = ("子未", "丑午", "寅巳", "卯辰", "申亥", "酉戌")
ZHI_PO = ("子酉", "丑辰", "寅亥", "卯午", "巳申", "未戌")
ZHI_XING = {
    "寅巳申": "无恩之刑", "丑戌未": "恃势之刑", "子卯": "无礼之刑",
}
# 地支半合（两支：生地/墓地与中神）
HALF_COMBINE = {
    "申子": "水", "子辰": "水", "寅午": "火", "午戌": "火",
    "巳酉": "金", "丑酉": "金", "亥卯": "木", "卯未": "木",
}
# 两支相刑（三刑缺一时按对出现，如寅巳、寅申、丑戌等）
PARTIAL_XING = {
    frozenset(("寅", "巳")): "无恩之刑",
    frozenset(("巳", "申")): "无恩之刑",
    frozenset(("寅", "申")): "无恩之刑",
    frozenset(("丑", "戌")): "恃势之刑",
    frozenset(("戌", "未")): "恃势之刑",
    frozenset(("丑", "未")): "恃势之刑",
    frozenset(("子", "卯")): "无礼之刑",
}


def _norm_pair(a, b):
    """把两个字规范成同一顺序，保证查表不因书写顺序漏判。"""
    return "".join(sorted([a, b]))


GAN_HE_N = {_norm_pair(k[0], k[1]): v for k, v in GAN_HE.items()}
GAN_CHONG_N = {_norm_pair(a, b) for a, b in GAN_CHONG}
ZHI_LIU_HE_N = {_norm_pair(k[0], k[1]): v for k, v in ZHI_LIU_HE.items()}
ZHI_CHONG_N = {_norm_pair(a, b) for a, b in ZHI_CHONG}
ZHI_HAI_N = {_norm_pair(a, b) for a, b in ZHI_HAI}
ZHI_PO_N = {_norm_pair(a, b) for a, b in ZHI_PO}
SELF_XING = set("辰午酉亥")


def relations(pillars):
    """四柱内部的合、冲、刑、害、破、会、半合（用于大运流年叠看）。"""
    out = []
    gans = [p["gan"] for p in pillars]
    zhis = [p["zhi"] for p in pillars]
    names = [p["name"] for p in pillars]

    for i in range(4):
        for j in range(i + 1, 4):
            key = _norm_pair(gans[i], gans[j])
            if key in GAN_HE_N:
                out.append("天干合：%s%s与%s%s合%s（是否化气另看）" % (
                    names[i], gans[i], names[j], gans[j], GAN_HE_N[key]))
            if key in GAN_CHONG_N:
                out.append("天干冲：%s%s与%s%s相冲" % (
                    names[i], gans[i], names[j], gans[j]))

            zkey = _norm_pair(zhis[i], zhis[j])
            if zkey in ZHI_LIU_HE_N:
                out.append("地支六合：%s%s与%s%s合%s" % (
                    names[i], zhis[i], names[j], zhis[j], ZHI_LIU_HE_N[zkey]))
            if zkey in ZHI_CHONG_N:
                out.append("地支六冲：%s%s与%s%s相冲" % (
                    names[i], zhis[i], names[j], zhis[j]))
            if zkey in ZHI_HAI_N:
                out.append("地支六害：%s%s与%s%s相害" % (
                    names[i], zhis[i], names[j], zhis[j]))
            if zkey in ZHI_PO_N:
                out.append("地支相破：%s%s与%s%s相破" % (
                    names[i], zhis[i], names[j], zhis[j]))
            if zhis[i] == zhis[j] and zhis[i] in SELF_XING:
                out.append("地支自刑：%s%s与%s%s同支" % (
                    names[i], zhis[i], names[j], zhis[j]))

    # 三合 / 三会 / 三刑（需要三支齐）
    zset = set(zhis)
    full_sanhe = []
    for group, el in ZHI_SAN_HE.items():
        if set(group).issubset(zset):
            full_sanhe.append(group)
            out.append("地支三合：%s合%s局" % (group, el))
    for group, el in ZHI_SAN_HUI.items():
        if set(group).issubset(zset):
            out.append("地支三会：%s会%s方" % (group, el))
    full_xing = []
    for group, label in ZHI_XING.items():
        if set(group).issubset(zset):
            full_xing.append(group)
            tag = "地支相刑" if len(group) == 2 else "地支三刑"
            out.append("%s：%s（%s）" % (tag, group, label))

    # 半合：三合局缺一，仅两支（三合已全时不再重复）
    for i in range(4):
        for j in range(i + 1, 4):
            for key, el in HALF_COMBINE.items():
                if set(key) == {zhis[i], zhis[j]} and not any(
                        set(key).issubset(g) for g in full_sanhe):
                    out.append("地支半合%s：%s%s与%s%s半合" % (
                        el, names[i], zhis[i], names[j], zhis[j]))
                    break

    # 部分相刑：三刑缺一时的两支（三刑已全时不再重复）
    for i in range(4):
        for j in range(i + 1, 4):
            pair = frozenset((zhis[i], zhis[j]))
            if pair not in PARTIAL_XING:
                continue
            if any(set(group).issubset(zset) and pair.issubset(set(group))
                   for group in full_xing):
                continue
            out.append("地支相刑：%s%s与%s%s（%s）" % (
                names[i], zhis[i], names[j], zhis[j], PARTIAL_XING[pair]))

    return out


# ── 流年 / 大运 与命局的互动（岁运并临、伏吟、反吟、合冲刑害）──────────────
# 半合表见上方「干支关系」段（HALF_COMBINE），此处复用。


def _pair_relation(gan_a, zhi_a, gan_b, zhi_b, label_b, skip_fuyin=False):
    """a（流年）与 b（某柱或大运）之间的干支关系。

    a 通常是「流年」，b 是原局四柱之一或大运；label_b 用于输出描述。
    """
    out = []
    same_gz = (gan_a + zhi_a) == (gan_b + zhi_b)
    key_g = _norm_pair(gan_a, gan_b)
    key_z = _norm_pair(zhi_a, zhi_b)
    he_gan = key_g in GAN_HE_N
    chong_gan = key_g in GAN_CHONG_N
    he_zhi = key_z in ZHI_LIU_HE_N
    chong_zhi = key_z in ZHI_CHONG_N

    if same_gz and not skip_fuyin:
        out.append("伏吟：与%s同干支" % label_b)
    if chong_gan and chong_zhi:
        out.append("反吟（天克地冲）：与%s" % label_b)
        return out
    if same_gz:
        return out

    if he_gan:
        out.append("天干合（化%s）：与%s" % (GAN_HE_N[key_g], label_b))
    elif chong_gan:
        out.append("天干冲：与%s" % label_b)
    if he_zhi:
        out.append("地支六合%s：与%s" % (ZHI_LIU_HE_N[key_z], label_b))
    elif chong_zhi:
        out.append("地支六冲：与%s" % label_b)
    if key_z in ZHI_HAI_N:
        out.append("地支六害：与%s" % label_b)
    if key_z in ZHI_PO_N:
        out.append("地支相破：与%s" % label_b)
    if zhi_a == zhi_b and zhi_a in SELF_XING:
        out.append("地支自刑：与%s" % label_b)
    if {zhi_a, zhi_b} == {"子", "卯"}:
        out.append("地支相刑（子卯）：与%s" % label_b)
    half = HALF_COMBINE.get(zhi_a + zhi_b) or HALF_COMBINE.get(zhi_b + zhi_a)
    if half:
        out.append("地支半合%s：与%s" % (half, label_b))
    return out


def annotate_flow(pillars, dayun_list, liunian):
    """给每个流年补上 interactions：与四柱、与大运的互动，并标记岁运并临。"""
    for ly in liunian:
        gan, zhi = ly["ganzhi"][0], ly["ganzhi"][1]
        rels = []
        for p in pillars:
            rels.extend(_pair_relation(gan, zhi, p["gan"], p["zhi"], p["name"]))

        dy = None
        for d in dayun_list:
            if d["start_year"] <= ly["year"] <= d["end_year"]:
                dy = d
                break
        if dy:
            if gan + zhi == dy["ganzhi"]:
                rels.insert(0, "岁运并临：流年与大运同为%s" % dy["ganzhi"])
                rels.extend(_pair_relation(gan, zhi, dy["gan"], dy["zhi"],
                                           "大运" + dy["ganzhi"], skip_fuyin=True))
            else:
                rels.extend(_pair_relation(gan, zhi, dy["gan"], dy["zhi"],
                                           "大运" + dy["ganzhi"]))
        ly["interactions"] = rels
    return liunian
