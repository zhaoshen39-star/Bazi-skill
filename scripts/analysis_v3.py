# -*- coding: utf-8 -*-
"""八字分析 v3：旺衰（柱位加权力模型）、格局（子平真诠取格/成败/相神）、
喜用（扶抑/调候/通关/病药 四法合参与仲裁）、大运流年引动推测。

与 v2（analysis.py）的差异（也是「准确度」提升的来源）：

1. 旺衰：不再用「同党占比 + 常数修正」，改为结构化的力模型——
   柱位权重（月令 0.40 为最重）× 藏干分层（本/中/余气）× 十神亲和系数，
   再按天干五合、地支冲刑害合破对「力」打折，并输出逐项明细，可复算。
2. 格局：严格按子平真诠「月令藏干透干优先」取格（本气→中气→余气→本气不透），
   禄刃月单列，杂气月按透干取用；并逐格判定「成格/成中有败/败中有救/破格」，
   给出相神与救应。
3. 喜用：扶抑、调候、通关、病药四法各自出结论，再做仲裁（特殊格 > 破格救应 >
   调候急需 > 病药 > 扶抑），并评估「用神是否有根/是否受制」，输出大运喜忌角色
   （用神/喜神/忌神/仇神/闲神）。
4. 推测：大运流年不只按五行打分，而是叠加「与命局的合冲刑害、伏吟反吟、
   岁运并临、合化、冲用神/冲忌神」等引动，给出方向、领域、置信度与应期提示。

所有数字都来自本文件写明的权重表，属于「可解释的术数模型」，不是物理测量。
"""

from chart import (
    GAN, ZHI, HIDE_GAN, HIDE_RATIO, ELEMENT_OF_GAN, ELEMENT_OF_ZHI, SHI_SHEN,
)
from analysis import (
    ELEMENTS, SHENG, KE, ten_god_of, TEN_GOD_PARTY,
    LU_SHEN, YANG_REN, GAN_HE, GAN_CHONG, ZHI_LIU_HE, ZHI_SAN_HE, ZHI_SAN_HUI,
    ZHI_CHONG, ZHI_HAI, ZHI_PO, ZHI_XING, HALF_COMBINE, PARTIAL_XING, SELF_XING,
    _norm_pair,
)
from tiaohou_table import TIAOHOU

# ═══════════════════════════════════════════════════════════════════════════
# 0. 基础工具
# ═══════════════════════════════════════════════════════════════════════════
_BEI_SHENG = {v: k for k, v in SHENG.items()}   # 生我者
_BEI_KE = {v: k for k, v in KE.items()}         # 克我者（反查：被克 -> 克者）


def _sheng_of(el):
    """生我的五行。"""
    return _BEI_SHENG[el]


def _ke_me(el):
    """克我的五行。"""
    return _BEI_KE[el]


PARTY_OF_GOD = {
    "比肩": "比劫", "劫财": "比劫",
    "正印": "印星", "偏印": "印星",
    "食神": "食伤", "伤官": "食伤",
    "正财": "财星", "偏财": "财星",
    "正官": "官杀", "七杀": "官杀",
}


def party_of_element(day_el, el):
    """某五行相对日主的「党」：比劫/印星/食伤/财星/官杀。"""
    if el == day_el:
        return "比劫"
    if el == _sheng_of(day_el):
        return "印星"
    if el == SHENG[day_el]:
        return "食伤"
    if el == KE[day_el]:
        return "财星"
    return "官杀"


def _norm_gans():
    return {_norm_pair(k[0], k[1]): el for k, el in GAN_HE.items()}


_GAN_HE_N = _norm_gans()
_GAN_CHONG_N = {_norm_pair(a, b) for a, b in GAN_CHONG}
_ZHI_LIUHE_N = {_norm_pair(k[0], k[1]): v for k, v in ZHI_LIU_HE.items()}
_ZHI_CHONG_N = {_norm_pair(a, b) for a, b in ZHI_CHONG}
_ZHI_HAI_N = {_norm_pair(a, b) for a, b in ZHI_HAI}
_ZHI_PO_N = {_norm_pair(a, b) for a, b in ZHI_PO}
_PARTIAL_XING_N = set(PARTIAL_XING.keys())

PILLAR_NAMES = ("年柱", "月柱", "日柱", "时柱")


def _pillar_name(p, idx):
    return p.get("name") or PILLAR_NAMES[idx]


# ── 地支关系判定 ────────────────────────────────────────────────────────────
def _zhi_kind(a, b):
    """两支之间的主要关系：冲/合/害/破/刑/自刑；无则 None。"""
    key = _norm_pair(a, b)
    if key in _ZHI_CHONG_N:
        return "冲"
    if key in _ZHI_LIUHE_N:
        return "合"
    if key in _ZHI_HAI_N:
        return "害"
    if key in _ZHI_PO_N:
        return "破"
    if frozenset((a, b)) in _PARTIAL_XING_N:
        return "刑"
    if a == b and a in SELF_XING:
        return "自刑"
    return None


def _gan_kind(a, b):
    """两天干之间的关系：合/冲；无则 None。"""
    key = _norm_pair(a, b)
    if key in _GAN_HE_N:
        return "合"
    if key in _GAN_CHONG_N:
        return "冲"
    return None


# ── 结构力：柱位权重 + 藏干分层 ────────────────────────────────────────────
GAN_POS_W = {"年柱": 0.06, "月柱": 0.07, "时柱": 0.07}
ZHI_POS_W = {"年柱": 0.10, "月柱": 0.40, "日柱": 0.18, "时柱": 0.12}

SUPPORT_COEF = {"比肩": 1.00, "劫财": 0.95, "正印": 0.85, "偏印": 0.75}
OPPOSE_COEF = {"七杀": 1.00, "正官": 0.90, "正财": 0.90, "偏财": 0.85,
               "伤官": 0.85, "食神": 0.80}

ZHI_HIT_FACTOR = {"冲": 0.55, "刑": 0.80, "合": 0.88, "害": 0.88,
                  "破": 0.92, "自刑": 0.85}
GAN_HIT_FACTOR = {"合": 0.75, "冲": 0.90}


def _structure_force(pillars, day_gan):
    """把四柱拆成「柱位 × 藏干层」的力，并计入干支刑冲合害的损伤。

    返回：
      contribs: [{slot, source, element, god, raw, eff, side, note}]
      force:    {五行: 结构力（含三合三会加成）}
      notes:    [命局层面的结构说明]
      branch_factor: [每柱地支的损伤系数]
    """
    notes = []
    n = len(pillars)
    branch_factor = [1.0] * n
    gan_factor = [1.0] * n

    # 地支两两关系 → 损伤系数（对称打折，冲最重）
    for i in range(n):
        for j in range(i + 1, n):
            a, b = pillars[i]["zhi"], pillars[j]["zhi"]
            kind = _zhi_kind(a, b)
            if not kind:
                continue
            f = ZHI_HIT_FACTOR[kind]
            branch_factor[i] *= f
            branch_factor[j] *= f
            notes.append({
                "kind": "地支" + kind,
                "slot": [_pillar_name(pillars[i], i), _pillar_name(pillars[j], j)],
                "detail": "%s%s 与 %s%s %s" % (
                    _pillar_name(pillars[i], i), a, _pillar_name(pillars[j], j), b,
                    {"冲": "相冲（力减 45%）", "合": "六合（合绊，力减 12%）",
                     "害": "相害（力减 12%）", "破": "相破（力减 8%）",
                     "刑": "相刑（力减 20%）", "自刑": "自刑（力减 15%）"}[kind]),
            })

    # 天干关系（合绊/相冲）
    for i in range(n):
        if i == 2:      # 日干是日主本身，不参与「合绊它干」
            continue
        for j in range(i + 1, n):
            if j == 2:
                continue
            kind = _gan_kind(pillars[i]["gan"], pillars[j]["gan"])
            if not kind:
                continue
            gan_factor[i] *= GAN_HIT_FACTOR[kind]
            gan_factor[j] *= GAN_HIT_FACTOR[kind]
            notes.append({
                "kind": "天干" + kind,
                "slot": [_pillar_name(pillars[i], i), _pillar_name(pillars[j], j)],
                "detail": "%s天干%s 与 %s天干%s %s" % (
                    _pillar_name(pillars[i], i), pillars[i]["gan"],
                    _pillar_name(pillars[j], j), pillars[j]["gan"],
                    "相合（合绊，力减 25%，是否化气另看）" if kind == "合"
                    else "相冲（力减 10%）"),
            })

    contribs = []
    force = {e: 0.0 for e in ELEMENTS}

    for idx, p in enumerate(pillars):
        name = _pillar_name(p, idx)
        gan = p["gan"]
        if idx != 2:
            god = ten_god_of(day_gan, gan)
            raw = GAN_POS_W.get(name, 0.06) * gan_factor[idx]
            coef = SUPPORT_COEF.get(god) or -OPPOSE_COEF.get(god, 0.8)
            eff = raw * abs(coef)
            side = "support" if coef > 0 else "oppose"
            contribs.append({"slot": name + "天干", "source": name + "干" + gan,
                             "element": ELEMENT_OF_GAN[gan], "god": god,
                             "raw": round(raw, 4), "eff": round(eff, 4),
                             "side": side, "factor": gan_factor[idx]})
            force[ELEMENT_OF_GAN[gan]] += raw

        zhi = p["zhi"]
        hidden = HIDE_GAN[zhi]
        ratios = HIDE_RATIO[len(hidden)]
        base = ZHI_POS_W.get(name, 0.10) * branch_factor[idx]
        for depth, (h, r) in enumerate(zip(hidden, ratios)):
            god = ten_god_of(day_gan, h)
            raw = base * r
            coef = SUPPORT_COEF.get(god) or -OPPOSE_COEF.get(god, 0.8)
            eff = raw * abs(coef)
            side = "support" if coef > 0 else "oppose"
            layer = ("本气", "中气", "余气")[depth] if len(hidden) > 1 else "本气"
            contribs.append({"slot": name + "支" + zhi, "source": "%s%s藏%s(%s)" % (
                                 name, zhi, h, layer),
                             "element": ELEMENT_OF_GAN[h], "god": god,
                             "raw": round(raw, 4), "eff": round(eff, 4),
                             "side": side, "factor": branch_factor[idx]})
            force[ELEMENT_OF_GAN[h]] += raw

    # 三合局 / 三会方：成局者得势（加结构力），并作为说明
    zhis = [p["zhi"] for p in pillars]
    zset = set(zhis)
    for group, el in ZHI_SAN_HE.items():
        if set(group).issubset(zset):
            force[el] += 0.08
            notes.append({"kind": "三合局", "slot": list(group),
                          "detail": "%s 三合%s局，%s气增（结构力 +0.08）" % (group, el, el)})
    for group, el in ZHI_SAN_HUI.items():
        if set(group).issubset(zset):
            force[el] += 0.10
            notes.append({"kind": "三会方", "slot": list(group),
                          "detail": "%s 三会%s方，%s气增（结构力 +0.10）" % (group, el, el)})
    for group, label in ZHI_XING.items():
        if set(group).issubset(zset):
            notes.append({"kind": "三刑", "slot": list(group),
                          "detail": "%s 全见，%s（结构动荡，已按支力打折计入）" % (group, label)})

    support = sum(c["eff"] for c in contribs if c["side"] == "support")
    oppose = sum(c["eff"] for c in contribs if c["side"] == "oppose")
    total = support + oppose
    return {
        "contribs": contribs,
        "force": {e: round(v, 4) for e, v in force.items()},
        "support": round(support, 4),
        "oppose": round(oppose, 4),
        "total": round(total, 4),
        "ratio": round(support / total, 4) if total else 0.0,
        "notes": notes,
        "branch_factor": [round(x, 3) for x in branch_factor],
        "gan_factor": [round(x, 3) for x in gan_factor],
    }


def _party_shares(day_el, force):
    """按结构力给出五党占比（比劫/印星/食伤/财星/官杀）。"""
    total = sum(force.values()) or 1.0
    shares = {"比劫": 0.0, "印星": 0.0, "食伤": 0.0, "财星": 0.0, "官杀": 0.0}
    for el, v in force.items():
        shares[party_of_element(day_el, el)] += v
    return {k: round(v / total, 4) for k, v in shares.items()}


def _de_ling_state(day_el, month_el):
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


# 旺衰分级阈值。
# 语义锚点：结构力在「五行均匀分布」下的期望同党占比是 2/5 = 0.40，
# 故中和带取 0.35–0.45；阈值经 400 例随机命盘校准，使五级分布大致为
# 身弱:偏弱:中和:偏强:身强 ≈ 28:12:22:15:20（接近传统抽样观感）。
STRENGTH_CUTS = (0.27, 0.35, 0.45, 0.57)   # 身弱|偏弱|中和|偏强|身强

STRENGTH_MODEL = (
    "结构力 = 柱位权重(年干.06/月干.07/时干.07；年支.10/月支.40/日支.18/时支.12)"
    " × 藏干分层(本气1.0/中气按 HIDE_RATIO) × 十神亲和(比肩1.00 劫财.95 正印.85 偏印.75 / "
    "七杀1.00 正官.90 正财.90 偏财.85 伤官.85 食神.80)，并按时支冲刑害合破打折；"
    "同党力/全部力 = ratio，阈值 %s" % (STRENGTH_CUTS,)
)


def strength(pillars, day_gan, profile=None):
    """旺衰 v3：结构力模型 + 得令/得地/得势分项 + 从格判定。"""
    day_el = ELEMENT_OF_GAN[day_gan]
    sf = _structure_force(pillars, day_gan)
    ratio = sf["ratio"]
    shares = _party_shares(day_el, sf["force"])

    month_zhi = pillars[1]["zhi"]
    month_el = ELEMENT_OF_ZHI[month_zhi]
    ling = _de_ling_state(day_el, month_el)

    # 得地：四支中的根（本/中/余气），并标记是否被刑冲合害损伤
    roots = []
    rooted_benqi = False
    for idx, p in enumerate(pillars):
        zhi = p["zhi"]
        hidden = HIDE_GAN[zhi]
        for depth, h in enumerate(hidden):
            el = ELEMENT_OF_GAN[h]
            if el == day_el or el == _sheng_of(day_el):
                quality = {0: "本气根", 1: "中气根", 2: "余气根"}.get(depth, "藏根")
                damaged = sf["branch_factor"][idx] < 0.95
                roots.append({
                    "pillar": _pillar_name(p, idx), "branch": zhi, "stem": h,
                    "god": ten_god_of(day_gan, h), "quality": quality,
                    "damaged": damaged,
                    "text": "%s%s藏%s（%s%s）" % (
                        _pillar_name(p, idx), zhi, h, quality,
                        "，受损" if damaged else ""),
                })
                if depth == 0:
                    rooted_benqi = True

    # 得势：天干（除日干）中的同党
    helpers = []
    for idx, p in enumerate(pillars):
        if idx == 2:
            continue
        god = ten_god_of(day_gan, p["gan"])
        if TEN_GOD_PARTY.get(god) in ("比劫", "印星"):
            helpers.append({"pillar": _pillar_name(p, idx), "gan": p["gan"], "god": god})

    # 分级
    c1, c2, c3, c4 = STRENGTH_CUTS
    if ratio >= c4:
        label = "身强"
    elif ratio >= c3:
        label = "偏强"
    elif ratio >= c2:
        label = "中和"
    elif ratio >= c1:
        label = "偏弱"
    else:
        label = "身弱"

    # 从格判定（结构条件，而非只看比例）
    special = None
    guan_tou = any(ten_god_of(day_gan, p["gan"]) in ("正官", "七杀")
                   for idx, p in enumerate(pillars) if idx != 2)
    yin_bi_tou = bool(helpers)
    if ratio <= 0.20 and not rooted_benqi and not yin_bi_tou:
        dom = max(("财星", "官杀", "食伤"), key=lambda k: shares[k])
        special = {
            "type": {"财星": "从财格", "官杀": "从杀格", "食伤": "从儿格"}[dom],
            "kind": "从弱",
            "reasons": ["同党结构力仅 %.1f%%" % (ratio * 100),
                        "四支本气无根、年/月/时干无比劫印星透出",
                        "最强之党为%s（%.1f%%）" % (dom, shares[dom] * 100)],
        }
    elif ratio >= 0.80 and not guan_tou and shares["官杀"] <= 0.06 and shares["财星"] <= 0.10:
        special = {
            "type": "从强格（专旺）",
            "kind": "从强",
            "reasons": ["同党结构力达 %.1f%%" % (ratio * 100),
                        "无官杀透干，官杀结构力 ≤6%",
                        "财星结构力 ≤10%"],
        }
    # 从弱还须「异党独旺」：最强之党需占结构力 38% 以上，否则仍按身弱正格论
    if special and special.get("kind") == "从弱":
        dom = max(("财星", "官杀", "食伤"), key=lambda k: shares[k])
        if shares[dom] < 0.38:
            special = None
        elif dom == "食伤" and shares["官杀"] > 0.20:
            # 从儿格须食伤独旺；官杀成势者属「食神制杀/伤官见官」，不立从格
            special = None

    # 置信度：离阈值越近越不确定
    cuts = list(STRENGTH_CUTS)
    margin = min(abs(ratio - c) for c in cuts)
    if margin >= 0.035:
        confidence = "高"
    elif margin >= 0.015:
        confidence = "中"
    else:
        confidence = "低"

    special_hints = []
    if special:
        special_hints.append("判定为%s：常规扶抑结论不适用，应顺其旺神取用。" % special["type"])
    elif ratio >= 0.72:
        special_hints.append("同党结构力 ≥72%，接近专旺，需人工复核是否立为从强格。")
    elif ratio <= 0.28:
        special_hints.append("同党结构力 ≤28%，接近从弱，需人工复核是否立为从格。")

    de_di_text = [r["text"] for r in roots]
    return {
        # 兼容 v2 的键
        "ratio": round(ratio, 4),
        "score": round(ratio, 4),
        "label": label,
        "same_party": {"total": sf["support"], "percent": round(ratio * 100, 1),
                       "elements": [day_el, _sheng_of(day_el)]},
        "other_party": {"total": sf["oppose"],
                        "percent": round((1 - ratio) * 100, 1)},
        "de_ling": {"month_zhi": month_zhi, "month_element": month_el,
                    "state": ling, "season": _season(month_zhi)},
        "de_di": de_di_text,
        "de_shi_heads": len(helpers),
        "special_hints": special_hints,
        "model": STRENGTH_MODEL,
        # v3 新增
        "version": 3,
        "confidence": confidence,
        "party_shares": shares,
        "force": sf["force"],
        "de_ling_detail": {
            "month_zhi": month_zhi, "month_element": month_el, "state": ling,
            "season": _season(month_zhi),
            "text": "日主%s生于%s月（月令%s，%s），得令状态：%s" % (
                day_el, month_zhi, month_el, _season(month_zhi), ling),
        },
        "de_di_detail": roots,
        "de_di_summary": ("有本气根（%d 处）" % sum(1 for r in roots if r["quality"] == "本气根")
                          if rooted_benqi else ("仅有中/余气根" if roots else "无根")),
        "de_shi_detail": helpers,
        "de_shi_summary": "天干同党 %d 个" % len(helpers),
        "structure_notes": sf["notes"],
        "contribs": sf["contribs"],
        "special": special,
        "caveat": "旺衰是加权模型：同党结构力 ratio=%.3f（阈值 %s）。" % (ratio, STRENGTH_CUTS),
    }


def _season(month_zhi):
    if month_zhi in "寅卯辰":
        return "春"
    if month_zhi in "巳午未":
        return "夏"
    if month_zhi in "申酉戌":
        return "秋"
    return "冬"


# ═══════════════════════════════════════════════════════════════════════════
# 1. 格局 v3（子平真诠取格 + 成败救应）
# ═══════════════════════════════════════════════════════════════════════════
GE_NAME_OF_GOD = {
    "正官": "正官格", "七杀": "七杀格", "正财": "正财格", "偏财": "偏财格",
    "食神": "食神格", "伤官": "伤官格", "正印": "正印格", "偏印": "偏印格",
}

SHUN_NI = {
    "正官格": "顺用（喜财生、印护）",
    "七杀格": "逆用（喜食制、印化）",
    "正财格": "顺用（喜食伤生、身旺任）",
    "偏财格": "顺用（喜食伤生、身旺任）",
    "正印格": "顺用（喜官杀生印、忌财破印）",
    "偏印格": "顺用（喜官杀生印、忌财破印）",
    "食神格": "顺用（喜财泄、身旺）",
    "伤官格": "逆用（喜印制、财泄）",
    "建禄格": "逆用（喜官杀制、财任、食伤泄）",
    "月劫格（阳刃格）": "逆用（喜官杀制刃）",
}

XIANG_SHEN = {
    "正官格": [("财星", "生官之源"), ("印星", "护官/化官")],
    "七杀格": [("食神", "制杀"), ("印星", "化杀")],
    "正财格": [("食伤", "生财之源"), ("官杀", "护财（制比劫）")],
    "偏财格": [("食伤", "生财之源"), ("官杀", "护财（制比劫）")],
    "正印格": [("官杀", "生印之源"), ("比劫", "护印（制财）")],
    "偏印格": [("官杀", "生印之源"), ("财星", "制枭")],
    "食神格": [("财星", "食神生财"), ("比劫", "帮身")],
    "伤官格": [("印星", "制伤护身"), ("财星", "伤官生财")],
    "建禄格": [("官杀", "制身成器"), ("财星", "禄旺任财"), ("食伤", "泄秀")],
    "月劫格（阳刃格）": [("官杀", "制刃"), ("食伤", "泄刃")],
}

# 规则条：(id, 十神组, 最低强度, 说明[, unless])
# 强度 rank：3=透干 / 2=月令本气 / 1=其他本气 / 0=仅藏支 / -1=无
# unless 是「否决神组」：若该组 rank≥1，则本条不成立（用于"官杀不见"类条件）。
GOOD_BAD_RULES = {
    "正官格": {
        "good": [
            ("caisheng", ["正财", "偏财"], 2, "财星生官：财能生官，官有源头"),
            ("yinhu", ["正印", "偏印"], 1, "官印相生：印透护官，贵气可承"),
        ],
        "bad": [
            ("shangguan", ["伤官"], 2, "伤官见官：伤官伤官星，为破格之忌"),
            ("hunza", ["七杀"], 1, "官杀混杂：正官七杀同见，清浊不分"),
        ],
        "rescue": [
            ("shangguan", ["正印", "偏印"], 1, "印透制伤护官"),
            ("hunza", ["食神", "伤官"], 2, "食伤制杀，去杀留官"),
        ],
    },
    "七杀格": {
        "good": [
            ("shizhi", ["食神"], 2, "食神制杀：以才艺/规则化解压力"),
            ("yinhua", ["正印", "偏印"], 1, "印星化杀：杀不攻身而转生扶"),
            ("rensha", ["劫财"], 0, "有比劫帮身，可承杀威（需兼顾旺衰）"),
        ],
        "bad": [
            ("caidang", ["正财", "偏财"], 2, "财党杀势：财生杀而无制化，攻身更急",
             ["食神", "伤官", "正印", "偏印"]),
            ("hunza", ["正官"], 1, "官杀混杂：需去留清楚"),
        ],
        "rescue": [
            ("caidang", ["食神"], 2, "食神制杀，杀被制则不党财"),
            ("caidang", ["正印", "偏印"], 1, "印星化杀，杀势转为生扶"),
            ("hunza", ["食神", "伤官"], 2, "食伤制杀，去杀留官"),
            ("hunza", ["正印", "偏印"], 1, "印星化杀，混杂之势得缓（煞印有情）"),
        ],
    },
    "正财格": {
        "good": [
            ("shishang", ["食神", "伤官"], 2, "食伤生财：财有源头，源源不绝"),
            ("guanhu", ["正官", "七杀"], 1, "官杀护财：制比劫以护财"),
        ],
        "bad": [
            ("bijie", ["比肩", "劫财"], 2, "比劫夺财：财被分夺"),
        ],
        "rescue": [
            ("bijie", ["正官", "七杀"], 1, "官杀制比劫，护财"),
            ("bijie", ["食神", "伤官"], 1, "食伤通关，比劫生食伤、食伤生财"),
        ],
    },
    "偏财格": {
        "good": [
            ("shishang", ["食神", "伤官"], 2, "食伤生财：才华化为财源"),
            ("guanhu", ["正官", "七杀"], 1, "官杀护财"),
        ],
        "bad": [
            ("bijie", ["比肩", "劫财"], 2, "比劫夺财：偏财尤忌比劫争夺"),
        ],
        "rescue": [
            ("bijie", ["正官", "七杀"], 1, "官杀制比劫"),
            ("bijie", ["食神", "伤官"], 1, "食伤通关"),
        ],
    },
    "正印格": {
        "good": [
            ("guansheng", ["正官", "七杀"], 1, "官杀生印：印有源头，贵气相生"),
        ],
        "bad": [
            ("caipo", ["正财", "偏财"], 2, "财星破印：财能坏印，学业/文书/长辈助力受损"),
        ],
        "rescue": [
            ("caipo", ["比肩", "劫财"], 1, "比劫制财护印"),
            ("caipo", ["正官", "七杀"], 1, "官杀通关：财生官、官生印"),
        ],
    },
    "偏印格": {
        "good": [
            ("guansheng", ["正官", "七杀"], 2, "官杀生印：偏印得官杀相生"),
            ("caizhi", ["正财", "偏财"], 1, "财星制枭：偏印过旺得财裁剪"),
        ],
        "bad": [
            ("xiaoshi", ["食神"], 2, "枭神夺食：偏印夺食神，思路多而执行受阻"),
        ],
        "rescue": [
            ("xiaoshi", ["正财", "偏财"], 1, "财星制枭，食神得护"),
        ],
    },
    "食神格": {
        "good": [
            ("cai", ["正财", "偏财"], 2, "食神生财：泄秀而获利"),
            ("zhisha", ["七杀"], 1, "食神制杀：以食制杀为贵"),
        ],
        "bad": [
            ("xiaoshi", ["偏印"], 2, "枭神夺食：偏印克食神",
             ["正官", "七杀"]),
        ],
        "rescue": [
            ("xiaoshi", ["正财", "偏财"], 1, "财星制枭护食"),
        ],
    },
    "伤官格": {
        "good": [
            ("peiyin", ["正印", "偏印"], 2, "伤官配印：聪明而知收敛"),
            ("shengcai", ["正财", "偏财"], 2, "伤官生财：才华化为资源"),
        ],
        "bad": [
            ("jianguan", ["正官"], 1, "伤官见官：传统主是非与规则冲突"),
        ],
        "rescue": [
            ("jianguan", ["正印", "偏印"], 1, "印透制伤，伤不犯官"),
            ("jianguan", ["正财", "偏财"], 1, "财通关：伤官生财、财生官"),
        ],
    },
    "建禄格": {
        "good": [
            ("guansha", ["正官", "七杀"], 2, "官杀制身：禄旺需官杀成器"),
            ("cai", ["正财", "偏财"], 2, "财星：禄旺任财"),
            ("shishang", ["食神", "伤官"], 2, "食伤泄秀：禄旺得泄为清"),
        ],
        "bad": [
            ("wuguan", ["比肩", "劫财"], 2, "比劫重而官杀不见：禄劫无制，争财破耗",
             ["正官", "七杀"]),
        ],
        "rescue": [
            ("wuguan", ["食神", "伤官"], 1, "食伤泄秀，比劫之气有去路"),
        ],
    },
    "月劫格（阳刃格）": {
        "good": [
            ("shazhi", ["七杀"], 2, "七杀制刃：杀刃相济，主魄力与承压"),
            ("guanzhi", ["正官"], 2, "官星制刃"),
        ],
        "bad": [
            ("wuzhi", ["比肩", "劫财"], 2, "刃重无制：比劫成群，争竞破耗",
             ["正官", "七杀"]),
        ],
        "rescue": [
            ("wuzhi", ["食神", "伤官"], 1, "食伤泄刃，刃气有去路"),
            ("wuzhi", ["正官", "七杀"], 1, "官杀制刃"),
        ],
    },
}

PATTERN_NOTE = (
    "取格口径（子平真诠）：月令藏干以「本气透干 → 中气透干 → 余气透干 → 本气不透取本气」为序；"
    "禄月/刃月单列建禄格、阳刃格；否格成败按「成格条件 / 破格因素 / 救应」逐条判定，"
    "月令被冲者另记损伤。"
)


def _god_structure(pillars, day_gan):
    """返回 (透干, 本气, 藏干) 三组 [(十神, 柱位)]。"""
    tou, ben, cang = [], [], []
    for idx, p in enumerate(pillars):
        name = _pillar_name(p, idx)
        if idx != 2:
            tou.append((ten_god_of(day_gan, p["gan"]), name))
        hidden = HIDE_GAN[p["zhi"]]
        for depth, h in enumerate(hidden):
            g = ten_god_of(day_gan, h)
            cang.append((g, name))
            if depth == 0:
                ben.append((g, name))
    return tou, ben, cang


def _god_rank(pillars, day_gan, gods):
    """某组十神在命局中的强度：3=透干, 2=月令本气, 1=其他本气, 0=仅藏, -1=无。"""
    tou, ben, cang = _god_structure(pillars, day_gan)
    want = set(gods)
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


def _format_members(hits):
    """[(十神, 柱位)] -> "七杀(年柱、月柱)"。"""
    order = {}
    for god, slot in hits:
        order.setdefault(god, [])
        if slot not in order[god]:
            order[god].append(slot)
    return ["%s(%s)" % (g, "、".join(s)) for g, s in order.items()]


def pattern(pillars, day_gan, st=None):
    """格局 v3：取格 + 顺逆用 + 相神 + 成败救应。"""
    month = pillars[1]
    mz = month["zhi"]
    hidden = HIDE_GAN[mz]
    ben_qi = hidden[0]
    month_god = ten_god_of(day_gan, ben_qi)

    # 月令藏干透干（年/月/时干；日干是日主本身，不算透出）
    transparent = []
    for depth, h in enumerate(hidden):
        for idx, p in enumerate(pillars):
            if idx == 2:
                continue
            if p["gan"] == h:
                transparent.append({
                    "gan": h, "god": ten_god_of(day_gan, h),
                    "pillar": _pillar_name(p, idx),
                    "layer": ("本气", "中气", "余气")[depth] if len(hidden) > 1 else "本气",
                })

    used_god = month_god
    used_stem = ben_qi
    take_method = "月令藏干皆不透，取本气 %s（%s）" % (ben_qi, month_god)

    if mz == LU_SHEN[day_gan]:
        name = "建禄格"
        used_god, used_stem = "比肩", ben_qi
        take_method = "月令%s为日主临官（禄）位" % mz
        category = "禄刃格"
    elif mz == YANG_REN[day_gan]:
        name = "月劫格（阳刃格）"
        used_god, used_stem = "劫财", ben_qi
        take_method = "月令%s为日主帝旺（阳刃）位" % mz
        category = "禄刃格"
    else:
        if mz in ("辰", "戌", "丑", "未"):
            # 杂气月：以透干为重（本气 → 中气 → 余气）
            pick = None
            for depth, h in enumerate(hidden):
                for tr in transparent:
                    if tr["gan"] == h:
                        pick = (depth, h, tr)
                        break
                if pick:
                    break
            if pick:
                depth, h, tr = pick
                used_god = tr["god"]
                used_stem = h
                take_method = "%s透干（%s%s，%s）取格" % (
                    tr["layer"], tr["pillar"], h, used_god)
        else:
            # 四生/四旺月：月令本气分明，直接以本气为格；中余气透出者作兼格参考
            used_god = month_god
            used_stem = ben_qi
            take_method = "月令%s本气%s（%s）取格；中余气透出者作兼格参考" % (
                mz, ben_qi, month_god)
            extra = [tr for tr in transparent if tr["gan"] != ben_qi]
            if extra:
                take_method += "（兼看%s）" % "、".join(
                    "%s透%s" % (tr["layer"], tr["god"]) for tr in extra)
        if used_god in ("比肩", "劫财"):
            name = "建禄格" if used_god == "比肩" else "月劫格（阳刃格）"
            category = "禄刃格"
        else:
            name = GE_NAME_OF_GOD[used_god]
            category = "正格"

    # 取格候选（供古典命例对照与解读说明用）：本气格 + 各透干十神格
    candidates = []
    if month_god in GE_NAME_OF_GOD:
        candidates.append(GE_NAME_OF_GOD[month_god])
    for tr in transparent:
        gname = GE_NAME_OF_GOD.get(tr["god"])
        if gname and gname not in candidates:
            candidates.append(gname)
    for idx, p in enumerate(pillars):
        if idx == 2:
            continue
        gname = GE_NAME_OF_GOD.get(ten_god_of(day_gan, p["gan"]))
        if gname and gname not in candidates:
            candidates.append(gname)

    # 月令损伤：只有「冲/刑/害」算损伤；三合六合属「合绊」不算破格（子平不以此判成败）
    month_damage = []
    if st:
        for note in st.get("structure_notes", []):
            kind = note["kind"]
            if not kind.startswith("地支") or "月柱" not in note.get("slot", []):
                continue
            if "冲" in kind or "刑" in kind or "害" in kind:
                month_damage.append(note["detail"])

    # 成败
    spec = GOOD_BAD_RULES.get(name, {"good": [], "bad": [], "rescue": []})
    good, bad = [], []

    for rid, gods, min_rank, desc in spec.get("good", []):
        rank, hits = _god_rank(pillars, day_gan, gods)
        if rank >= min_rank:
            good.append({"id": rid, "desc": desc, "rank": rank,
                         "severity": "hard",
                         "members": _format_members(hits)})
    for rule in spec.get("bad", []):
        rid, gods, min_rank, desc = rule[:4]
        unless = rule[4] if len(rule) > 4 else None
        if unless and _god_rank(pillars, day_gan, unless)[0] >= 1:
            continue
        rank, hits = _god_rank(pillars, day_gan, gods)
        if rank >= min_rank:
            bad.append({"id": rid, "desc": desc, "rank": rank,
                        "severity": "hard",
                        "members": _format_members(hits)})

    # 相神到位：子平以相神为成格之要，相神党透干/临月令即有成格之力
    PARTY_GODS = {
        "比劫": ["比肩", "劫财"], "印星": ["正印", "偏印"],
        "食伤": ["食神", "伤官"], "财星": ["正财", "偏财"],
        "官杀": ["正官", "七杀"], "食神": ["食神"], "伤官": ["伤官"],
        "财": ["正财", "偏财"], "官": ["正官", "七杀"], "印": ["正印", "偏印"],
    }
    seen_good = {g["id"] for g in good}
    for party, role in XIANG_SHEN.get(name, []):
        gods = PARTY_GODS.get(party, [party])
        rank, hits = _god_rank(pillars, day_gan, gods)
        gid = "xiangshen_" + party
        if rank >= 2 and gid not in seen_good:
            good.append({"id": gid, "desc": "相神到位：%s（%s）" % (party, role),
                         "rank": rank, "severity": "hard",
                         "members": _format_members(hits)})
            seen_good.add(gid)

    # 旺衰相关的动态条件：属「隐忧/助力」，不单独决定成败（子平成败以相神救应为主）
    if st:
        ratio = st["ratio"]
        if name in ("正官格", "正财格", "偏财格", "食神格", "建禄格") and ratio >= 0.53:
            good.append({"id": "shenwang", "desc": "日主偏强/身强，能任官财食",
                         "rank": 0, "severity": "soft",
                         "members": ["身强（ratio=%.2f）" % ratio]})
        if name in ("七杀格", "正印格", "偏印格") and ratio <= 0.47:
            good.append({"id": "shenruo", "desc": "日主偏弱，印比护身得力",
                         "rank": 0, "severity": "soft",
                         "members": ["身弱（ratio=%.2f）" % ratio]})
        if name in ("七杀格", "伤官格", "食神格") and ratio <= 0.37:
            bad.append({"id": "shenruo_shouke", "desc": "身弱而杀伤食重，攻泄交加",
                        "rank": 0, "severity": "soft",
                        "members": ["身弱（ratio=%.2f）" % ratio]})
        if name == "正官格" and ratio <= 0.39:
            bad.append({"id": "shenruo_guanzhong", "desc": "身弱官重，官变为压力",
                        "rank": 0, "severity": "soft",
                        "members": ["身弱（ratio=%.2f）" % ratio]})
        if month_damage:
            bad.append({"id": "yueling_shang", "desc": "月令受冲刑害：格局根基有隐忧（子平不以合判成败，冲刑害只减力不必然破格）",
                        "rank": 0, "severity": "soft",
                        "members": month_damage[:2]})

    # 救应：只在对应「病」出现时计；rank≥2（透干/月令本气）视为强力救应 → 病解
    rescue = []
    bad_ids = {b["id"] for b in bad}
    for bad_id, gods, min_rank, desc in spec.get("rescue", []):
        if bad_id not in bad_ids:
            continue
        rank, hits = _god_rank(pillars, day_gan, gods)
        if rank >= min_rank:
            rescue.append({"for": bad_id, "desc": desc, "rank": rank,
                           "members": _format_members(hits)})
    resolved = {r["for"] for r in rescue if r["rank"] >= 2}
    for b in bad:
        b["resolved"] = b["id"] in resolved
        b["severity"] = "soft" if b.get("severity") == "soft" else "hard"
    hard_bad = [b for b in bad if b["severity"] == "hard" and not b["resolved"]]
    soft_bad = [b for b in bad if b["severity"] == "soft"] + \
               [b for b in bad if b["severity"] == "hard" and b["resolved"]]

    if st and st.get("special"):
        status = "特殊格（%s）" % st["special"]["type"]
        status_note = "按从格/专旺论，不套正格成败；用神顺其旺神。"
    elif hard_bad and not good:
        status = "破格"
        status_note = "破格因素成立而未见成格条件，格局层次受损。"
    elif hard_bad and good:
        status = "成中有败"
        status_note = "成格条件与未解的破格因素并见，层次取决于两者轻重。"
    elif soft_bad and good:
        status = "成格"
        status_note = "成格条件成立；另有隐忧（旺衰/月令/已解破格），层次略降，不改变成格。"
    elif good:
        status = "成格"
        status_note = "成格条件成立，未见明显破格因素。"
    elif bad and rescue:
        status = "败中有救"
        status_note = "有破格因素，但有救应之神，需看救应是否有力。"
    else:
        status = "待定"
        status_note = "结构性条件不足，需结合大运与具体人事判断。"

    if hard_bad:
        confidence = "中"
    elif status == "成格" and not soft_bad:
        confidence = "高"
    elif soft_bad:
        confidence = "中"
    else:
        confidence = "低"

    hints = []
    for b in bad:
        hints.append("忌：%s（%s）" % (b["desc"], "、".join(b["members"]) or "—"))
    for r in rescue:
        hints.append("救：%s（%s）" % (r["desc"], "、".join(r["members"])))
    for g in good[:2]:
        hints.append("喜：%s" % g["desc"])

    note = "%s；%s。%s" % (take_method, status, status_note)
    if transparent:
        note += " 月令透干：%s。" % "、".join(
            "%s%s" % (t["layer"], t["gan"]) for t in transparent)

    return {
        # 兼容 v2 的键
        "month_zhi": mz, "month_ben_qi": ben_qi, "month_god": month_god,
        "used_god": used_god, "name": name, "basis": take_method,
        "transparent": transparent, "hints": hints, "note": note,
        # v3 新增
        "version": 3,
        "category": category,
        "used_stem": used_stem,
        "take_method": take_method,
        "shun_ni": SHUN_NI.get(name, ""),
        "xiang_shen": [{"party": p, "role": d} for p, d in XIANG_SHEN.get(name, [])],
        "status": status,
        "status_note": status_note,
        "good": good,
        "bad": bad,
        "rescue": rescue,
        "candidates": candidates,
        "month_damage": month_damage,
        "confidence": confidence,
        "model": PATTERN_NOTE,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 2. 喜用 v3（扶抑 / 调候 / 通关 / 病药 四法合参 + 仲裁）
# ═══════════════════════════════════════════════════════════════════════════
# 月支 → 温度基准（℃ 量纲的抽象值，仅用于寒暖比较）
SEASON_TEMP = {"子": -2.0, "丑": -1.4, "寅": -1.0, "卯": 0.0, "辰": 0.3,
               "巳": 1.0, "午": 2.0, "未": 1.3, "申": 0.4, "酉": -0.1,
               "戌": -0.4, "亥": -1.4}

ELEMENT_TO_GAN_TEXT = {"木": "甲乙", "火": "丙丁", "土": "戊己", "金": "庚辛", "水": "壬癸"}


def _element_name(el):
    return "%s（%s）" % (el, ELEMENT_TO_GAN_TEXT.get(el, ""))


def _shares_from_st(st, day_el):
    """取五党占比；v3 用结构力，v2 回退到五行总量。"""
    if st and "party_shares" in st:
        return dict(st["party_shares"])
    return {"比劫": 0.0, "印星": 0.0, "食伤": 0.0, "财星": 0.0, "官杀": 0.0}


def _temperature(month_zhi, st):
    """寒暖燥湿指数：正为燥热，负为寒湿。"""
    base = SEASON_TEMP.get(month_zhi, 0.0)
    force = (st or {}).get("force") or {}
    total = sum(force.values()) or 1.0
    fire = force.get("火", 0.0)
    water = force.get("水", 0.0)
    return round(base + 2.0 * (fire - water) / total, 3)


def _tiaohou(day_gan, month_zhi, st):
    """调候法：《穷通宝鉴》120 格表（日干×月支）取首选/辅佐，寒暖指数只定急缓。

    表来自 references/v3-rules-source.md（tiaohou_table.py，双源核对），
    寒暖指数只用于判断「调候是否为当务之急」，不再拿季节四选一硬套。
    """
    t = _temperature(month_zhi, st)
    if t <= -1.2:
        grade, temp_need, temp_text = "急需", "火", "寒湿偏重（指数 %.2f），暖局为急" % t
    elif t <= -0.6:
        grade, temp_need, temp_text = "需要", "火", "偏寒（指数 %.2f），喜火调候" % t
    elif t >= 1.2:
        grade, temp_need, temp_text = "急需", "水", "燥热偏重（指数 %.2f），润局为急" % t
    elif t >= 0.6:
        grade, temp_need, temp_text = "需要", "水", "偏燥（指数 %.2f），喜水调候" % t
    else:
        grade, temp_need, temp_text = "不急", None, "寒暖相对调和（指数 %.2f），调候不是主要矛盾" % t

    row = TIAOHOU.get((day_gan, month_zhi))
    if not row or not row.get("primary"):
        # 表外兜底：沿用寒暖判据
        return {
            "index": t, "grade": grade, "primary": temp_need, "secondary": None,
            "primary_gan": None, "secondary_gan": None, "note": "", "credibility": "低",
            "desc": temp_text, "table": False,
            "method": "调候指数 = 月令温度基准 + 2.0×(火-水)/总结构力；阈值 ±1.2 急需、±0.6 需要。",
        }

    pg = row["primary"]
    sg = (row.get("secondary") or "").strip() or None
    pel = ELEMENT_OF_GAN[pg]
    sel = ELEMENT_OF_GAN[sg] if sg else None
    note = row.get("note", "")
    cred = row.get("credibility", "中")
    aux = "辅 %s（%s）" % (sg, sel) if sg else "无辅佐"
    desc = "《穷通宝鉴》%s日生%s月：首用 %s（%s）、%s；%s。寒暖：%s" % (
        day_gan, month_zhi, pg, pel, aux, note, temp_text)
    return {
        "index": t,
        "grade": grade,
        "primary": pel,
        "secondary": sel,
        "primary_gan": pg,
        "secondary_gan": sg,
        "note": note,
        "credibility": cred,
        "desc": desc,
        "table": True,
        "method": ("调候按《穷通宝鉴》120 格（日干×月支）取首选/辅佐天干；"
                   "寒暖指数 = 月令温度基准 + 2.0×(火-水)/总结构力，"
                   "|指数|≥1.2 判「急需」、≥0.6 判「需要」，只用于定调候急缓。"),
    }


# 四法冲突时谁优先（数字越小越优先）
ARBITRATION_ORDER = ("special", "rescue", "tiaohou", "bingyao", "fuyi")


def yong_shen(day_gan, profile=None, st=None, ge=None, pillars=None):
    """喜用 v3：四法合参 + 仲裁 + 用神有力 + 大运喜忌角色。"""
    day_el = ELEMENT_OF_GAN[day_gan]
    yin = _sheng_of(day_el)
    bi = day_el
    shi = SHENG[day_el]
    cai = KE[day_el]
    guan = _ke_me(day_el)

    shares = _shares_from_st(st, day_el)
    label = (st or {}).get("label", "中和")
    ratio = (st or {}).get("ratio", 0.5)
    special = (st or {}).get("special")

    # ── 扶抑 ────────────────────────────────────────────────────────────
    avoid = []
    if special and special.get("kind") == "从强":
        useful = [bi, yin]
        avoid = [guan, cai]
        primary = [bi]
        secondary = [yin]
        fuyi_desc = "从强格：顺其旺势，喜比劫、印星，忌官杀逆旺、财星破旺。"
    elif special and special.get("kind") == "从弱":
        useful = [cai, guan, shi]
        avoid = [bi, yin]
        primary = [max((cai, guan, shi), key=lambda e: shares[
            {"财星": "财星", "官杀": "官杀", "食伤": "食伤"}[party_of_element(day_el, e)]])]
        secondary = [e for e in useful if e != primary[0]][:2]
        fuyi_desc = "从弱格：顺其弱势，喜财、官杀、食伤，忌印比帮身逆势。"
    elif label in ("身强", "偏强"):
        useful = [guan, shi, cai]
        avoid = [yin, bi]
        primary = [guan]
        secondary = [shi, cai]
        fuyi_desc = "身强/偏强：宜官杀制身、食伤泄秀、财星耗身；忌印比再加力。"
    elif label in ("身弱", "偏弱"):
        useful = [yin, bi]
        avoid = [shi, cai, guan]
        primary = [yin]
        secondary = [bi]
        fuyi_desc = "身弱/偏弱：宜印星生扶、比劫帮身；忌财官食伤耗克。"
    else:
        # 中和：先看调候与格局相神
        primary, secondary = [], []
        fuyi_desc = "中和：扶抑不是主要矛盾，取调候与格局相神为用。"

    # ── 调候 ────────────────────────────────────────────────────────────
    month_zhi = ((ge or {}).get("month_zhi")
                 or ((st or {}).get("de_ling") or {}).get("month_zhi")
                 or "子")
    th = _tiaohou(day_gan, month_zhi, st)

    # ── 通关 ────────────────────────────────────────────────────────────
    pairs = [
        ("官杀", "比劫", yin, "官杀克比劫，印星通关（官杀→印→身）"),
        ("财星", "印星", guan, "财星克印，官杀通关（财→官→印）"),
        ("食伤", "官杀", cai, "食伤克官杀，财星通关（食伤→财→官）"),
        ("比劫", "财星", shi, "比劫克财，食伤通关（比劫→食伤→财）"),
    ]
    tg = []
    for a, b, bridge, desc in pairs:
        if shares[a] >= 0.18 and shares[b] >= 0.18:
            weight = min(shares[a], shares[b])
            tg.append({"pair": [a, b], "bridge": bridge, "weight": round(weight, 3),
                       "desc": desc})
    tg.sort(key=lambda x: -x["weight"])
    tg = tg[:2]

    # ── 病药 ────────────────────────────────────────────────────────────
    bing = []
    if shares["比劫"] >= 0.38 and shares["财星"] >= 0.12:
        bing.append({"bing": "比劫过旺、争夺财星", "yao": [guan],
                     "desc": "比劫结构力 %.0f%%，财星受夺" % (shares["比劫"] * 100)})
    if shares["财星"] >= 0.32 and label in ("身弱", "偏弱"):
        bing.append({"bing": "财多身弱", "yao": [bi, yin],
                     "desc": "财星 %.0f%% 而日主偏弱，财重身轻" % (shares["财星"] * 100)})
    if shares["印星"] >= 0.35 and label in ("身强", "偏强"):
        bing.append({"bing": "印重身旺、气滞", "yao": [cai],
                     "desc": "印星 %.0f%% 而身强，需财裁印" % (shares["印星"] * 100)})
    if shares["食伤"] >= 0.35 and label in ("身弱", "偏弱"):
        bing.append({"bing": "食伤过旺、泄身太过", "yao": [yin],
                     "desc": "食伤 %.0f%% 而身弱" % (shares["食伤"] * 100)})
    if shares["官杀"] >= 0.35 and label in ("身弱", "偏弱"):
        bing.append({"bing": "官杀过旺、攻身", "yao": [yin, bi],
                     "desc": "官杀 %.0f%% 而身弱" % (shares["官杀"] * 100)})
    if th["grade"] == "急需":
        bing.append({"bing": "寒暖失衡",
                     "yao": [th["primary"]] if th["primary"] else [],
                     "desc": "寒暖指数 %.2f，调候为急：宜先取%s调温" % (
                         th["index"], _element_name(th["primary"]) if th["primary"] else "暖燥")})
    if len((st or {}).get("structure_notes", [])) >= 4:
        bing.append({"bing": "刑冲合害过多、局面动荡", "yao": [yin] if shares["官杀"] > shares["比劫"] else [shi],
                     "desc": "结构关系 %d 处，宜通关调和" % len((st or {}).get("structure_notes", []))})

    # ── 仲裁 ────────────────────────────────────────────────────────────
    pri = list(primary) if primary else []
    sec = list(secondary)
    reasons = []
    conflicts = []
    rule = ""

    rescue_elements = []
    if ge and ge.get("rescue"):
        for r in ge["rescue"]:
            for m in r.get("members", []):
                # members 形如 "正印(月柱)"，取十神名映射五行
                god = m.split("(")[0]
                if god in ("正印", "偏印"):
                    rescue_elements.append(yin)
                elif god in ("正官", "七杀"):
                    rescue_elements.append(guan)
                elif god in ("食神", "伤官"):
                    rescue_elements.append(shi)
                elif god in ("正财", "偏财"):
                    rescue_elements.append(cai)
                elif god in ("比肩", "劫财"):
                    rescue_elements.append(bi)

    if special:
        rule = "特殊格顺其旺神"
        reasons.append(fuyi_desc)
    elif ge and ge.get("status") == "破格" and rescue_elements:
        rule = "破格取救应"
        pri = _dedupe([rescue_elements[0]] + pri)
        reasons.append("格局破格，取救应之%s为急用。" % _element_name(rescue_elements[0]))
    elif th["grade"] == "急需" and th["primary"]:
        rule = "调候急需优先"
        if pri and pri[0] != th["primary"]:
            conflicts.append(
                "扶抑主用%s与调候急需%s冲突：寒暖失衡时以调候救急为先，扶抑次之。"
                % (_element_name(pri[0]), _element_name(th["primary"])))
        pri = _dedupe([th["primary"]] + pri)
        sec = _dedupe([th["secondary"]] + sec) if th["secondary"] else sec
        reasons.append(th["desc"])
    elif bing and bing[0]["yao"]:
        rule = "病药优先（%s）" % bing[0]["bing"]
        pri = _dedupe(bing[0]["yao"] + pri)
        reasons.append("命局之病：%s；取%s为药。" % (
            bing[0]["bing"], "、".join(_element_name(e) for e in bing[0]["yao"])))
    else:
        rule = "扶抑为主"
        reasons.append(fuyi_desc)

    if (th["primary"] and rule != "调候急需优先"
            and th["primary"] in avoid_elements(day_el, label, special)):
        conflicts.append("调候所需%s落在扶抑忌神（%s）中：寒暖与强弱判断相左，宜两法并看、降低单一结论的置信度。"
                        % (_element_name(th["primary"]), label))

    primary_out = _dedupe(pri)[:2] or ([th["primary"]] if th["primary"] else [])
    secondary_out = _dedupe(sec)[:3]
    useful_out = _dedupe(primary_out + secondary_out + [e for e in (th["primary"], th["secondary"]) if e])
    avoid_out = _dedupe(avoid)
    if th["primary"] and th["primary"] in useful_out:
        avoid_out = [e for e in avoid_out if e != th["primary"]]

    # ── 用神有力 ────────────────────────────────────────────────────────
    ysf = []
    for el in primary_out:
        info = _element_power(pillars or (st or {}).get("_pillars"), day_gan, el, shares)
        ysf.append(info)

    # ── 大运喜忌角色 ────────────────────────────────────────────────────
    roles = {e: "闲神" for e in ELEMENTS}
    p = primary_out[0] if primary_out else None
    if p:
        roles[p] = "用神"
        xi = _sheng_of(p)
        if xi != p:
            roles[xi] = "喜神"
        for e in secondary_out:
            if roles[e] == "闲神" and e != p:
                roles[e] = "喜神"
        g = _ke_me(p)
        if g != p and roles[g] == "闲神":
            roles[g] = "忌神"
        chou = _sheng_of(g)
        if roles[chou] == "闲神" and chou != p:
            roles[chou] = "仇神"
        for e in avoid_out:
            if roles[e] == "闲神":
                roles[e] = "忌神"

    return {
        # 兼容 v2 的键
        "useful_elements": useful_out,
        "avoid_elements": avoid_out,
        "primary_elements": primary_out,
        "secondary_elements": secondary_out,
        "reasons": reasons,
        "reason": "；".join(reasons),
        "tiaohou": th["desc"],
        "tiaohou_element": th["primary"],
        "conflict": "；".join(conflicts) if conflicts else "",
        "caveat": "喜用是四法合参的权衡结果，不是唯一答案；" + th["method"],
        # v3 新增
        "version": 3,
        "methods": {
            "fuyi": {"desc": fuyi_desc, "primary": _dedupe(pri), "label": label,
                     "ratio": ratio},
            "tiaohou": th,
            "tongguan": tg,
            "bingyao": bing,
        },
        "arbitration": {"rule": rule, "order": list(ARBITRATION_ORDER),
                        "reasons": reasons, "conflicts": conflicts},
        "shen_roles": roles,
        "yong_shen_force": ysf,
    }


def _dedupe(seq):
    out = []
    for x in seq:
        if x and x not in out:
            out.append(x)
    return out


def avoid_elements(day_el, label, special):
    yin = _sheng_of(day_el)
    bi = day_el
    shi = SHENG[day_el]
    cai = KE[day_el]
    guan = _ke_me(day_el)
    if special and special.get("kind") == "从强":
        return [guan, cai]
    if special and special.get("kind") == "从弱":
        return [bi, yin]
    if label in ("身强", "偏强"):
        return [yin, bi]
    if label in ("身弱", "偏弱"):
        return [shi, cai, guan]
    return []


def _element_power(pillars, day_gan, element, shares):
    """用神在某五行上的「有根/透干/受制」评估。"""
    if not pillars:
        return {"element": element, "status": "未知（缺少四柱）", "tokens": [],
                "share": shares.get(_party_key(day_gan, element), 0.0)}
    tou = []
    roots = []
    for idx, p in enumerate(pillars):
        name = _pillar_name(p, idx)
        if idx != 2 and ELEMENT_OF_GAN[p["gan"]] == element:
            tou.append("%s干%s" % (name, p["gan"]))
        for depth, h in enumerate(HIDE_GAN[p["zhi"]]):
            if ELEMENT_OF_GAN[h] == element:
                roots.append("%s%s藏%s%s" % (
                    name, p["zhi"], h,
                    {0: "（本气）", 1: "（中气）", 2: "（余气）"}.get(depth, "")))
    share = shares.get(_party_key(day_gan, element), 0.0)
    if tou and roots:
        status = "有力（透干且有根）"
    elif tou:
        status = "有透无根（需大运补根）"
    elif roots:
        status = "有根无透（有底气但难显）"
    else:
        status = "虚浮无根"
    return {"element": element, "status": status, "share": share,
            "tou": tou, "roots": roots,
            "tokens": tou + roots,
            "note": "该五行结构力占比 %.1f%%" % (share * 100)}


def _party_key(day_gan, element):
    day_el = ELEMENT_OF_GAN[day_gan]
    return party_of_element(day_el, element)


# ── 大运流年打分（v3：按用神角色加权）────────────────────────────────────
ROLE_WEIGHT = {"用神": 2.2, "喜神": 1.3, "仇神": -1.0, "忌神": -1.9, "闲神": 0.0}


def _weight_of(ys, element):
    roles = (ys or {}).get("shen_roles") or {}
    role = roles.get(element, "闲神")
    return ROLE_WEIGHT.get(role, 0.0), role


def flow_favorability(ys, ganzhi):
    """大运/流年「基调」打分：按用神/喜神/忌神角色对干支与藏干加权。"""
    gan, zhi = ganzhi[0], ganzhi[1]
    score = 0.0
    reasons = []
    w, role = _weight_of(ys, ELEMENT_OF_GAN[gan])
    if w:
        score += w
        reasons.append("天干%s=%s（%s，%+.1f）" % (gan, ELEMENT_OF_GAN[gan], role, w))
    hidden = HIDE_GAN[zhi]
    ratios = HIDE_RATIO[len(hidden)]
    for depth, (h, r) in enumerate(zip(hidden, ratios)):
        w, role = _weight_of(ys, ELEMENT_OF_GAN[h])
        base = 1.0 if depth == 0 else 0.3
        if w:
            score += w * base
            reasons.append("地支%s藏%s=%s（%s，%+.2f）" % (
                zhi, h, ELEMENT_OF_GAN[h], role, w * base))
    w, role = _weight_of(ys, ELEMENT_OF_ZHI[zhi])
    score = max(-4.0, min(4.0, score))
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
    return {"label": label, "score": round(score, 2), "reasons": reasons,
            "model": "用神×2.2 / 喜神×1.3 / 忌神×-1.9 / 仇神×-1.0；地支本气×1、中余气×0.3。"}


# ═══════════════════════════════════════════════════════════════════════════
# 3. 大运 / 流年 引动与应期（推测层）
# ═══════════════════════════════════════════════════════════════════════════
DOMAIN_OF_GOD = {
    "正官": ["事业/责任", "上级/名誉"],
    "七杀": ["压力/竞争", "健康/风险"],
    "正财": ["财务/稳定收入", "男命伴侣"],
    "偏财": ["投资/外财", "父辈/人脉"],
    "正印": ["学业/文书", "长辈/房产"],
    "偏印": ["专业/灵感", "偏门/宗教"],
    "食神": ["创作/享受", "子女/技艺"],
    "伤官": ["表达/变动", "技艺/子女"],
    "比肩": ["同辈/竞争", "自立/支出"],
    "劫财": ["合作/竞争", "破耗/变动"],
}

PALACE_DOMAIN = {
    "年柱": "祖辈/早年/外部环境",
    "月柱": "父母/事业/社会",
    "日柱": "自身/婚姻/健康",
    "时柱": "子女/晚年/下属",
}


def _role_of_element(ys, element):
    roles = (ys or {}).get("shen_roles") or {}
    return roles.get(element, "闲神")


def _element_of_branch(zhi):
    return ELEMENT_OF_ZHI[zhi]


def _activation_delta(ys, element, base, sign_note):
    """按某五行在喜忌中的角色给出引动分。"""
    role = _role_of_element(ys, element)
    if role == "用神":
        return base, role, sign_note
    if role == "喜神":
        return base * 0.6, role, sign_note
    if role == "忌神":
        return -base, role, sign_note
    if role == "仇神":
        return -base * 0.5, role, sign_note
    return 0.0, role, sign_note


def _pair_events(gan, zhi, other_gz, ys, label, tense):
    """流年/大运 与某柱（或彼此）的互动条目。"""
    gan_b, zhi_b = other_gz[0], other_gz[1]
    out = []
    same = (gan + zhi) == (gan_b + zhi_b)
    gk = _gan_kind(gan, gan_b)
    zk = _zhi_kind(zhi, zhi_b)

    if same:
        delta, role, _ = _activation_delta(ys, _element_of_branch(zhi), 0.5, "")
        out.append({"type": "伏吟", "target": label, "delta": -abs(delta) if delta else -0.5,
                    "detail": "%s与%s同干支%s：旧事重演、停滞或反复" % (tense, label, gan + zhi),
                    "role": role})
        return out

    if gk == "冲" and zk == "冲":
        delta, role, _ = _activation_delta(ys, _element_of_branch(zhi), 0.8, "")
        out.append({"type": "反吟（天克地冲）", "target": label,
                    "delta": -abs(delta or 0.8),
                    "detail": "%s与%s天克地冲：变动剧烈，宜谨慎" % (tense, label),
                    "role": role})
        return out

    # 地支
    if zk == "冲":
        delta, role, _ = _activation_delta(ys, _element_of_branch(zhi), 0.7, "")
        direction = "冲忌神/去病为吉" if delta > 0 else ("冲用神/喜神，动而生变" if delta < 0 else "中性变动")
        out.append({"type": "地支六冲", "target": label, "delta": delta,
                    "detail": "%s%s冲%s%s：%s" % (tense, zhi, label, zhi_b, direction),
                    "role": role})
    elif zk == "合":
        delta, role, _ = _activation_delta(ys, _element_of_branch(zhi), 0.45, "")
        out.append({"type": "地支六合", "target": label, "delta": -abs(delta or 0.3),
                    "detail": "%s%s合%s%s：合则牵绊/聚拢，%s被合动" % (tense, zhi, label, zhi_b,
                                                                     _element_of_branch(zhi)),
                    "role": role})
    elif zk in ("刑", "自刑"):
        out.append({"type": "地支相刑", "target": label, "delta": -0.3,
                    "detail": "%s%s与%s%s相刑：是非、内耗或旧疾" % (tense, zhi, label, zhi_b),
                    "role": _role_of_element(ys, _element_of_branch(zhi))})
    elif zk in ("害", "破"):
        out.append({"type": "地支" + zk, "target": label, "delta": -0.2,
                    "detail": "%s%s与%s%s相%s：暗中不顺" % (tense, zhi, label, zhi_b, zk),
                    "role": _role_of_element(ys, _element_of_branch(zhi))})

    half = HALF_COMBINE.get(zhi + zhi_b) or HALF_COMBINE.get(zhi_b + zhi)
    if half:
        delta, role, _ = _activation_delta(ys, half, 0.4, "")
        out.append({"type": "地支半合%s局" % half, "target": label, "delta": delta,
                    "detail": "%s%s与%s%s半合%s局：%s气被引动" % (tense, zhi, label, zhi_b, half, half),
                    "role": role})

    # 天干
    if gk == "合":
        delta, role, _ = _activation_delta(ys, _element_of_branch(zhi), 0.3, "")
        out.append({"type": "天干五合", "target": label, "delta": -abs(delta or 0.25),
                    "detail": "%s天干%s合%s天干%s：合绊，%s" % (
                        tense, gan, label, gan_b, "化气另看"),
                    "role": role})
    elif gk == "冲":
        out.append({"type": "天干相冲", "target": label, "delta": -0.2,
                    "detail": "%s天干%s冲%s天干%s" % (tense, gan, label, gan_b),
                    "role": _role_of_element(ys, ELEMENT_OF_GAN[gan])})
    return out


def _flow_theme(ys, gan, zhi, day_gan):
    """从干支十神给领域标签。"""
    gods = [ten_god_of(day_gan, gan)]
    zhi_ben = HIDE_GAN[zhi][0]
    gods.append(ten_god_of(day_gan, zhi_ben))
    themes = []
    for g in _dedupe(gods):
        for d in DOMAIN_OF_GOD.get(g, []):
            if d not in themes:
                themes.append(d)
    return gods, themes


def _confidence_from(base_score, act_score):
    if abs(base_score) >= 0.5 and abs(act_score) >= 0.5 and (base_score > 0) == (act_score > 0):
        return "高"
    if abs(base_score) >= 0.5 or abs(act_score) >= 0.5:
        return "中"
    return "低"


def dayun_timing(dy, pillars, ys, ge=None, st=None):
    """大运推测：基调 + 与命局的引动 + 领域 + 置信度。"""
    ganzhi = dy.get("ganzhi") or (dy.get("gan", "") + dy.get("zhi", ""))
    base = flow_favorability(ys, ganzhi)
    events = []
    for idx, p in enumerate(pillars):
        label = p.get("name") or PILLAR_NAMES[idx]
        events.extend(_pair_events(ganzhi[0], ganzhi[1], (p["gan"], p["zhi"]),
                                   ys, label, "大运"))
        if PALACE_DOMAIN.get(label):
            for e in events[-3:]:
                e.setdefault("palace", PALACE_DOMAIN[label])

    act = sum(e.get("delta", 0.0) for e in events)
    score = max(-4.0, min(4.0, base["score"] * 0.55 + act))
    label = ("喜" if score >= 1.6 else "偏喜" if score >= 0.5 else
             "中性" if score > -0.5 else "偏忌" if score > -1.6 else "忌")
    gods, themes = _flow_theme(ys, ganzhi[0], ganzhi[1], (pillars[2]["gan"] if pillars else ganzhi[0]))
    confidence = _confidence_from(base["score"], act)
    major = [e for e in events if abs(e.get("delta", 0)) >= 0.5]
    return {
        "ganzhi": ganzhi,
        "base": base,
        "events": events,
        "activation_score": round(act, 2),
        "score": round(score, 2),
        "label": label,
        "gods": gods,
        "themes": themes,
        "confidence": confidence,
        "major_events": major,
        "note": "大运基调分 %.2f，引动分 %+.2f；%s" % (
            base["score"], act,
            "引动与基调一致，方向较明确" if confidence == "高" else
            "引动与基调部分背离，宜看具体事件" if confidence == "中" else
            "基调与引动均弱，判断置信度低"),
    }


def liunian_timing(ly, dayun_list, pillars, ys, ge=None, st=None):
    """流年推测：基调 + 与原局/大运的引动 + 岁运并临 + 领域 + 应期。"""
    ganzhi = ly.get("ganzhi") or (ly.get("gan", "") + ly.get("zhi", ""))
    base = flow_favorability(ys, ganzhi)
    events = []
    for idx, p in enumerate(pillars):
        label = p.get("name") or PILLAR_NAMES[idx]
        events.extend(_pair_events(ganzhi[0], ganzhi[1], (p["gan"], p["zhi"]),
                                   ys, label, "流年"))

    # 找到所属大运
    dy = None
    for d in dayun_list or []:
        if d.get("start_year", 0) <= ly.get("year", 0) <= d.get("end_year", 0):
            dy = d
            break
    if dy:
        dy_gz = dy.get("ganzhi") or (dy.get("gan", "") + dy.get("zhi", ""))
        if dy_gz == ganzhi:
            direction = 1 if base["score"] > 0 else -1
            events.insert(0, {"type": "岁运并临", "target": "大运" + dy_gz,
                              "delta": 1.0 * direction,
                              "detail": "流年与大运同为%s：引动加倍，%s" % (
                                  dy_gz, "吉上加吉" if direction > 0 else "凶上加凶"),
                              "role": "岁运"})
        else:
            evs = _pair_events(ganzhi[0], ganzhi[1], (dy_gz[0], dy_gz[1]),
                               ys, "大运" + dy_gz, "流年")
            for e in evs:
                if e.get("type") in ("反吟（天克地冲）", "伏吟"):
                    e["delta"] *= 1.2
            events.extend(evs)

    act = sum(e.get("delta", 0.0) for e in events)
    score = max(-4.0, min(4.0, base["score"] * 0.5 + act))
    label = ("喜" if score >= 1.6 else "偏喜" if score >= 0.5 else
             "中性" if score > -0.5 else "偏忌" if score > -1.6 else "忌")
    gods, themes = _flow_theme(ys, ganzhi[0], ganzhi[1], (pillars[2]["gan"] if pillars else ganzhi[0]))
    major = [e for e in events if abs(e.get("delta", 0)) >= 0.5]
    confidence = _confidence_from(base["score"], act)

    # 应期：显著引动条目
    yingqi = []
    for e in major:
        yingqi.append("%s：%s（%+.1f）" % (e["type"], e["detail"], e["delta"]))
    if not yingqi and abs(act) >= 0.3:
        yingqi.append("轻微引动：%+.1f，多主小波动" % act)

    return {
        "ganzhi": ganzhi,
        "base": base,
        "events": events,
        "activation_score": round(act, 2),
        "score": round(score, 2),
        "label": label,
        "gods": gods,
        "themes": themes,
        "confidence": confidence,
        "major_events": major,
        "yingqi": yingqi,
        "dayun": dy.get("ganzhi") if dy else None,
        "note": "流年基调 %s，引动 %+.2f，置信度%s" % (base["label"], act, confidence),
    }


def annotate_flow(pillars, dayun_list, liunian, ys, ge=None, st=None):
    """给大运/流年补 timing（含引动、领域、置信度、应期）。

    同时写 v2 兼容字段 interactions（供旧渲染/测试复用）。
    """
    for dy in dayun_list or []:
        dy["timing"] = dayun_timing(dy, pillars, ys, ge, st)
        dy["interactions"] = ["%s：%s" % (e["type"], e["detail"])
                              for e in dy["timing"]["events"]
                              if abs(e.get("delta", 0)) >= 0.2][:6]
    for ly in liunian or []:
        ly["timing"] = liunian_timing(ly, dayun_list, pillars, ys, ge, st)
        ly["interactions"] = ["%s：%s" % (e["type"], e["detail"])
                              for e in ly["timing"]["events"]
                              if abs(e.get("delta", 0)) >= 0.2][:6]
    return liunian


# ═══════════════════════════════════════════════════════════════════════════
# 4. 编排入口
# ═══════════════════════════════════════════════════════════════════════════
def analyze(pillars, day_gan, profile=None):
    """一次算出 v3 的旺衰/格局/喜用（供 bazi.py 调用）。"""
    st = strength(pillars, day_gan, profile)
    ge = pattern(pillars, day_gan, st)
    ys = yong_shen(day_gan, profile, st, ge, pillars)
    return {"strength": st, "pattern": ge, "yong_shen": ys}
