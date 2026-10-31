#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨体系融合层（fusion）：把多套命理/占法的信号映射到统一生活领域，做"一致性"与"张力"分析。

设计目标（见 references/fusion-systems.md）：
1. 各体系独立推演，不互相"验证"；融合层只做「同一张命盘、不同取象模型之间是否互相印证」的描述。
2. 每套体系对每个领域给一个 [-2, +2] 的方向性信号 + 一句依据；按体系权重加权，输出
   一致（多个体系同向）/ 分歧（体系之间对不上）/ 证据不足（该体系没有相关信号）。
3. 明确边界：没有任何体系通过双盲预测验证；天文学层面的精度 ≠ 预测效度；
   权重可配置，权重大小只表示"该体系在这类问题上给的信息量"，不是科学效度。

对外 API：
    build_fusion(report) -> dict
    render_fusion_text(data) -> str

可选依赖（全部 try/except，缺失时降级）：
    scripts/astrology.py   -> report["astro"]      （西洋 + 印度占星，天文星历）
    scripts/numerology.py  -> report["numerology"] （数字学）
    scripts/ziwei.py       -> report["ziwei"]      （紫微斗数）
    scripts/zinv...        -> 无
本模块自身只用标准库。
"""

from __future__ import annotations

import datetime

VERSION = "v1"

# ---------------------------------------------------------------- 领域与体系

DOMAINS = [
    ("personality", "性格与底色"),
    ("career", "事业与责任"),
    ("wealth", "财富与资源"),
    ("love", "感情与伴侣"),
    ("health", "健康与压力"),
    ("family", "家庭与六亲"),
    ("move", "迁移与出行"),
    ("study", "学习与专长"),
    ("people", "人际与合作"),
]
DOMAIN_TITLE = dict(DOMAINS)
DOMAIN_IDS = [d for d, _ in DOMAINS]

# 体系权重：表达"信息量与可核对程度"，不是预测效度。
# 八字/紫微：历法或安星规则完全确定，信息量高；西洋/印度占星：天文星历可精确复算；
# 数字学/民俗占法：符号归约或取象，信息量低，权重低。
WEIGHTS = {
    "bazi": 1.00,
    "ziwei": 0.90,
    "western": 0.90,
    "vedic": 0.70,
    "numerology": 0.50,
    "folk": 0.40,
}

SYSTEMS = [
    ("bazi", "八字（子平）", "历法 + 五行结构规则"),
    ("ziwei", "紫微斗数", "安星规则（三合派）"),
    ("western", "西洋本命占星", "天文星历（回归黄道）"),
    ("vedic", "印度占星（Jyotish）", "天文星历 + 岁差（sidereal）"),
    ("numerology", "数字学（Numerology）", "日期/姓名符号归约"),
    ("folk", "民俗占法（小六壬/梅花/称骨/星座）", "取象/随机抽取"),
]

MODEL = (
    "融合层：六类体系各自出信号，映射到 9 个生活领域；"
    "按「体系权重 × 信号强度」加权，给出领域方向、跨体系一致度与张力清单。"
    "权重表示信息量而非预测效度；不同体系是不同取象模型，独立成立不等于互相验证。"
)

LIMITS = [
    "融合层只是把不同体系的『取象』并排对照，不是把多体系叠加成确定性结论。",
    "没有任何命理/占星体系通过双盲对照实验的预测验证；天文计算精度不等于预测准确率。",
    "体系权重（八字 1.0 / 紫微 0.9 / 西洋 0.9 / 印度 0.7 / 数字学 0.5 / 民俗 0.4）是主观设定，可配置，不代表科学效度。",
    "跨体系领域映射是解释性约定（十神→事业、宫位→领域等），不是公认换算公式。",
    "领域信号只为 -2..+2 的方向描述，不构成吉凶承诺，也不替代医疗、法律、投资等专业意见。",
    "西洋与印度占星共享同一套星历与黄道（仅岁差不同），结果高度相关，权重已折价；不可当作两份独立证据。",
]

# 结论分级（供渲染与测试共用）
LEVEL_BANDS = [
    (1.20, "明显偏顺"),
    (0.55, "偏顺"),
    (0.15, "略偏顺"),
    (-0.15, "中平"),
    (-0.55, "略偏吃力"),
    (-1.20, "偏吃力"),
    (-99.0, "吃力"),
]


def _clamp(x, lo=-2.0, hi=2.0):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return 0.0
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def _get(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def _level(signal):
    for edge, label in LEVEL_BANDS:
        if signal >= edge:
            return label
    return "吃力"


def _fmt_sig(x):
    return "%+.2f" % _clamp(x)


def _vote(votes, system, domain, signal, evidence):
    if domain not in DOMAIN_IDS:
        return
    try:
        sig = _clamp(signal)
    except (TypeError, ValueError):
        return
    if abs(sig) < 0.01:
        return
    votes.append({
        "system": system,
        "domain": domain,
        "signal": round(sig, 3),
        "evidence": str(evidence or "").strip(),
    })


# ---------------------------------------------------------------- 八字信号

SHENSHA_DOMAIN = {
    "驿马": "move",
    "桃花": "love",
    "红鸾": "love",
    "天喜": "love",
    "华盖": "study",
    "文昌": "study",
    "天乙贵人": "career",
    "天德贵人": "family",
    "月德贵人": "family",
    "将星": "career",
    "羊刃": "health",
    "劫煞": "health",
    "灾煞": "health",
    "亡神": "health",
    "魁罡": "people",
    "金舆": "wealth",
    "禄神": "wealth",
}
SHENSHA_SIGNAL = {
    "驿马": 1.0,
    "桃花": 0.7,
    "红鸾": 0.8,
    "天喜": 0.8,
    "华盖": 0.5,
    "文昌": 0.9,
    "天乙贵人": 0.9,
    "天德贵人": 0.7,
    "月德贵人": 0.7,
    "将星": 0.6,
    "羊刃": -0.4,
    "劫煞": -0.7,
    "灾煞": -0.7,
    "亡神": -0.6,
    "魁罡": 0.3,
    "金舆": 0.5,
    "禄神": 0.8,
}

PATTERN_STATUS_SIGNAL = {
    "成格": 1.0,
    "成中有败": 0.5,
    "败中有救": 0.3,
    "破格": -1.2,
    "待定": 0.0,
}

COMBINATION_SIGNAL = {
    "官印相生": [("career", 0.8)],
    "杀印相生": [("career", 0.7)],
    "食神制杀": [("career", 0.6)],
    "伤官配印": [("career", 0.4), ("study", 0.3)],
    "食伤生财": [("wealth", 0.8)],
    "财官相生": [("career", 0.5), ("wealth", 0.5)],
    "枭神夺食": [("health", -0.6)],
    "伤官见官": [("career", -0.8)],
    "财星破印": [("study", -0.7)],
    "比劫夺财": [("wealth", -0.9)],
    "杀刃相济": [("career", 0.6)],
    "官杀混杂": [("career", -0.5)],
}

_STRENGTH_HEALTH = {
    "身强": (0.8, "日主偏旺、能扛事"),
    "偏强": (0.4, "日主偏旺、精力较足"),
    "中和": (0.0, "日主中和"),
    "偏弱": (-0.5, "日主偏弱、容易透支"),
    "身弱": (-1.0, "日主偏弱、需要养精蓄锐"),
}

_TOPIC_DOMAIN = {
    "love": "love",
    "career": "career",
    "wealth": "wealth",
    "study": "study",
    "health": "health",
    "family": "family",
    "move": "move",
    "people": "people",
}

_TOPIC_LEVEL_SIGNAL = {"偏顺": 0.7, "中平": 0.0, "偏吃力": -0.7}


def _bazi_votes(report, votes):
    a = report.get("analysis") or {}
    st = a.get("strength") or {}
    ge = a.get("pattern") or {}
    ss = a.get("shen_sha") or {}
    comb = a.get("combinations") or []
    shares = st.get("party_shares") or {}

    def share(party):
        try:
            v = float(shares.get(party, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0
        return v / 100.0 if v > 1.0 else v

    # 五党占比（基准 20%）
    for party, domains in (
        ("官杀", (("career", 1.0), ("health", -0.3))),
        ("财星", (("wealth", 1.0),)),
        ("印星", (("study", 1.0), ("family", 0.3))),
        ("食伤", (("career", 0.7), ("people", 0.4))),
        ("比劫", (("people", 0.8), ("personality", 0.6))),
    ):
        s = share(party)
        base = _clamp((s - 0.20) * 6.0, -1.4, 1.4)
        for dom, k in domains:
            _vote(votes, "bazi", dom, base * k, "八字：%s 占 %.1f%%" % (party, s * 100))

    # 日主强弱 → 健康/性格
    label = st.get("label") or ""
    if label in _STRENGTH_HEALTH:
        sig, why = _STRENGTH_HEALTH[label]
        _vote(votes, "bazi", "health", sig, "八字：%s（%s）" % (label, why))
        _vote(votes, "bazi", "personality", sig * 0.5, "八字：%s" % label)

    # 格局成败 → 事业
    status = ge.get("status") or ""
    for key, sig in PATTERN_STATUS_SIGNAL.items():
        if status == key or (key == "成格" and status.startswith("成格")):
            _vote(votes, "bazi", "career", sig,
                  "八字：%s%s（%s）" % (ge.get("name", ""), status, ge.get("status_note", "")))
            break

    # 十神组合
    for c in comb:
        name = c.get("name") if isinstance(c, dict) else ""
        for dom, sig in COMBINATION_SIGNAL.get(name, []):
            _vote(votes, "bazi", dom, sig, "八字：%s（%s）" % (name, c.get("level", "")))

    # 神煞
    for name, slots in (ss or {}).items():
        dom = SHENSHA_DOMAIN.get(name)
        sig = SHENSHA_SIGNAL.get(name)
        if not dom or not sig:
            continue
        _vote(votes, "bazi", dom, sig, "八字神煞：%s（%s）" % (name, "、".join(slots or [])[:24]))

    # 专题层（若已计算）提供更直接的分域信号
    topics = _get(report, "topics", "topics")
    if isinstance(topics, list):
        for t in topics:
            if not isinstance(t, dict):
                continue
            dom = _TOPIC_DOMAIN.get(t.get("id"))
            sig = _TOPIC_LEVEL_SIGNAL.get(t.get("level"))
            if dom and sig:
                _vote(votes, "bazi", dom, sig,
                      "八字专题：%s %s" % (t.get("title", ""), t.get("summary", "")[:36]))


# ---------------------------------------------------------------- 紫微信号

ZIWEI_PALACE_DOMAIN = {
    "命": "personality",
    "夫妻": "love",
    "官禄": "career",
    "财帛": "wealth",
    "疾厄": "health",
    "田宅": "family",
    "迁移": "move",
    "父母": "family",
    "兄弟": "people",
    "子女": "family",
    "交友": "people",
    "福德": "health",
}

# 吉星/辅星（多数落在 other_stars）的轻量信号
ZIWEI_OTHER_SIGNAL = {
    "禄存": 0.4, "天马": 0.5, "天魁": 0.3, "天钺": 0.3,
    "文昌": 0.4, "文曲": 0.4, "左辅": 0.3, "右弼": 0.3,
    "红鸾": 0.4, "天喜": 0.4,
}
ZIWEI_OTHER_DOMAIN = {
    "天马": "move", "禄存": "wealth", "红鸾": "love", "天喜": "love",
    "文昌": "study", "文曲": "study", "天魁": "career", "天钺": "career",
    "左辅": "people", "右弼": "people",
}

# 主星基调：正 = 能量顺、稳；负 = 张力/破耗
ZIWEI_STAR_SIGNAL = {
    "紫微": 0.9, "天机": 0.4, "太阳": 0.7, "武曲": 0.6, "天同": 0.6,
    "廉贞": -0.2, "天府": 0.9, "太阴": 0.5, "贪狼": 0.3, "巨门": -0.5,
    "天相": 0.6, "天梁": 0.7, "七杀": -0.3, "破军": -0.6,
}

# 凶星/煞星落到某宫，扣分
ZIWEI_SHA_SIGNAL = {
    "擎羊": -0.6, "陀罗": -0.6, "火星": -0.5, "铃星": -0.5,
    "地空": -0.5, "地劫": -0.5, "化忌": -0.8,
}

# 四化（禄权科忌）
ZIWEI_SIHUA_SIGNAL = {"禄": 0.8, "权": 0.6, "科": 0.6, "忌": -0.9}


def _ziwei_of(report):
    z = report.get("ziwei")
    if isinstance(z, dict) and z.get("palaces"):
        return z
    try:
        import ziwei as ziweimod  # type: ignore
        return ziweimod.chart_ziwei(report)
    except Exception:
        return None


def _bracket_stars(parts):
    out = []
    for p in parts or []:
        s = str(p)
        if "(" in s or "（" in s:
            s = s.split("(")[0].split("（")[0]
        s = s.strip()
        if s:
            out.append(s)
    return out


def _ziwei_votes(report, votes):
    z = _ziwei_of(report)
    if not z:
        return
    palaces = z.get("palaces") or []
    sihua = z.get("sihua") or []

    # 四化落宫
    hua_by_palace = {}
    for h in sihua:
        if not isinstance(h, dict):
            continue
        pn = h.get("palace") or ""
        hua_by_palace.setdefault(pn, []).append(h)

    for p in palaces:
        if not isinstance(p, dict):
            continue
        name = p.get("name") or ""
        base = name.replace("宫", "")
        dom = ZIWEI_PALACE_DOMAIN.get(base)
        if not dom:
            continue
        stars = _bracket_stars(p.get("main_stars"))
        sig = 0.0
        used = []
        for s in stars:
            if s in ZIWEI_STAR_SIGNAL:
                sig += ZIWEI_STAR_SIGNAL[s]
                used.append(s)
        for s in _bracket_stars(p.get("sha_stars")):
            if s in ZIWEI_SHA_SIGNAL:
                sig += ZIWEI_SHA_SIGNAL[s]
                used.append(s)
        for s in _bracket_stars(p.get("other_stars")):
            if s in ZIWEI_OTHER_SIGNAL:
                sig += ZIWEI_OTHER_SIGNAL[s] * 0.6
                od = ZIWEI_OTHER_DOMAIN.get(s)
                if od and od != dom:
                    _vote(votes, "ziwei", od, ZIWEI_OTHER_SIGNAL[s] * 0.5,
                          "紫微：%s宫 %s" % (base, s))
                used.append(s)
        for h in hua_by_palace.get(name, []):
            hv = ZIWEI_SIHUA_SIGNAL.get(h.get("hua") or "")
            if hv:
                sig += hv
                used.append("%s化%s" % (h.get("star", ""), h.get("hua", "")))
        if used:
            sig = _clamp(sig * 0.6, -1.5, 1.5)
            _vote(votes, "ziwei", dom, sig,
                  "紫微：%s宫 %s" % (base, "、".join(used[:4])))


# ---------------------------------------------------------------- 西洋/印度占星信号

ELEMENT_DOMAIN = {
    "火": ("career", 0.8),
    "土": ("wealth", 0.8),
    "风": ("study", 0.8),
    "水": ("love", 0.6),
    "fire": ("career", 0.8),
    "earth": ("wealth", 0.8),
    "air": ("study", 0.8),
    "water": ("love", 0.6),
}

HOUSE_DOMAIN = {
    1: "personality", 2: "wealth", 3: "study", 4: "family", 5: "love",
    6: "health", 7: "love", 8: "wealth", 9: "move", 10: "career",
    11: "people", 12: "health",
}

VEDIC_RULER_DOMAIN = {
    "太阳": "career", "Sun": "career",
    "月亮": "love", "Moon": "love",
    "火星": "health", "Mars": "health",
    "水星": "study", "Mercury": "study",
    "木星": "career", "Jupiter": "career",
    "金星": "love", "Venus": "love",
    "土星": "health", "Saturn": "health",
    "罗睺": "move", "Rahu": "move",
    "计都": "study", "Ketu": "study",
}

_SIGN_ELEMENT = {
    "白羊": "火", "狮子": "火", "射手": "火",
    "金牛": "土", "处女": "土", "摩羯": "土",
    "双子": "风", "天秤": "风", "水瓶": "风",
    "巨蟹": "水", "天蝎": "水", "双鱼": "水",
    "Aries": "火", "Leo": "火", "Sagittarius": "火",
    "Taurus": "土", "Virgo": "土", "Capricorn": "土",
    "Gemini": "风", "Libra": "风", "Aquarius": "风",
    "Cancer": "水", "Scorpio": "水", "Pisces": "水",
}


def _astro_of(report):
    # bazi.py 写入的键是 astrology；兼容旧键 astro 与懒重算
    for key in ("astrology", "astro"):
        a = report.get(key)
        if isinstance(a, dict) and a.get("planets"):
            return a
    try:
        import astrology as astromod  # type: ignore
        return astromod.chart_natal(report)
    except Exception:
        return None


def _sign_element(sign):
    s = str(sign or "")
    for k, v in _SIGN_ELEMENT.items():
        if k in s:
            return v
    return None


def _western_votes(report, votes):
    a = _astro_of(report)
    if not a:
        return

    # 元素平衡
    balance = a.get("balance") or {}
    elems = balance.get("elements") or {}
    total = 0.0
    for k, v in elems.items():
        try:
            total += max(0.0, float(v))
        except (TypeError, ValueError):
            pass
    if total > 0:
        for k, v in elems.items():
            try:
                share = max(0.0, float(v)) / total
            except (TypeError, ValueError):
                continue
            info = ELEMENT_DOMAIN.get(k)
            if not info:
                continue
            dom, k2 = info
            _vote(votes, "western", dom, _clamp((share - 0.25) * 4.0) * k2,
                  "西洋占星：%s元素占 %.0f%%" % (k, share * 100))

    # 日月上升元素
    for key, doms in (
        ("sun", (("personality", 0.8), ("career", 0.3))),
        ("moon", (("health", 0.5), ("love", 0.5))),
    ):
        p = None
        for pl in a.get("planets") or []:
            if not isinstance(pl, dict):
                continue
            pk = str(pl.get("key") or "").lower()
            pn = str(pl.get("name") or "")
            if pk == key or (key == "sun" and "太阳" in pn) or (key == "moon" and "月亮" in pn):
                p = pl
                break
        if not p:
            continue
        el = _sign_element(p.get("sign_cn") or p.get("sign"))
        info = ELEMENT_DOMAIN.get(el or "")
        if not info:
            continue
        for dom, k2 in doms:
            _vote(votes, "western", dom, 0.9 * k2,
                  "西洋占星：%s落%s（%s元素）" % (p.get("name", key), p.get("sign_cn", ""), el))

    angles = a.get("angles") or {}
    asc = angles.get("asc")
    if isinstance(asc, dict):
        el = _sign_element(asc.get("sign_cn") or asc.get("sign"))
        info = ELEMENT_DOMAIN.get(el or "")
        if info:
            _vote(votes, "western", "personality", 0.5,
                  "西洋占星：上升%s（%s元素）" % (asc.get("sign_cn", ""), el))

    # 宫位强调
    house_count = {}
    for pl in a.get("planets") or []:
        if not isinstance(pl, dict):
            continue
        h = pl.get("house")
        try:
            h = int(h)
        except (TypeError, ValueError):
            continue
        house_count[h] = house_count.get(h, 0) + 1
    for h, n in house_count.items():
        dom = HOUSE_DOMAIN.get(h)
        if dom and n >= 2:
            _vote(votes, "western", dom, _clamp(0.25 * n, 0.25, 0.8),
                  "西洋占星：%d 宫落 %d 颗星" % (h, n))

    # 相位和谐/张力
    hard = sum(1 for x in (a.get("aspects") or []) if isinstance(x, dict) and x.get("type") in ("刑", "冲", "square", "opposition"))
    soft = sum(1 for x in (a.get("aspects") or []) if isinstance(x, dict) and x.get("type") in ("三合", "六合", "trine", "sextile"))
    if hard + soft > 0:
        sig = _clamp((soft - hard) / float(hard + soft) * 1.2)
        _vote(votes, "western", "health", sig * 0.6,
              "西洋占星：和谐相位 %d / 张力相位 %d" % (soft, hard))

    # 印度占星
    vedic = a.get("vedic") or {}
    nk = vedic.get("nakshatra") or {}
    ruler = nk.get("ruler") or ""
    dom = VEDIC_RULER_DOMAIN.get(ruler)
    if dom:
        _vote(votes, "vedic", dom, 0.5,
              "印度占星：月亮宿 %s（宿主%s）" % (nk.get("name", ""), ruler))
    for key, dom in (("moon_sign", "love"), ("lagna", "personality")):
        s = vedic.get(key)
        sign = s.get("sign_cn") if isinstance(s, dict) else s
        el = _sign_element(sign)
        info = ELEMENT_DOMAIN.get(el or "")
        if info:
            _vote(votes, "vedic", dom, 0.4,
                  "印度占星：%s（%s元素）" % (sign, el))


# ---------------------------------------------------------------- 数字学信号

NUMBER_SIGNALS = {
    1: {"personality": 1.0, "career": 0.5, "people": -0.2},
    2: {"love": 0.8, "people": 0.7, "career": 0.2},
    3: {"people": 0.9, "study": 0.4, "personality": 0.3},
    4: {"wealth": 0.8, "career": 0.5, "health": -0.2},
    5: {"people": 0.5, "move": 0.9, "study": 0.2},
    6: {"family": 0.9, "love": 0.7, "health": 0.2},
    7: {"study": 1.0, "personality": 0.3, "health": -0.3},
    8: {"wealth": 1.0, "career": 0.7, "people": 0.2},
    9: {"people": 0.8, "love": 0.4, "family": 0.3},
    11: {"study": 0.9, "personality": 0.8, "people": 0.3},
    22: {"career": 0.9, "wealth": 0.8, "study": 0.3},
    33: {"family": 0.9, "love": 0.8, "people": 0.6},
}

PERSONAL_YEAR_SIGNAL = {
    1: 0.6, 2: 0.2, 3: 0.6, 4: 0.0, 5: -0.2,
    6: 0.4, 7: -0.3, 8: 0.5, 9: -0.2,
}


def _num_of(report):
    n = report.get("numerology")
    if isinstance(n, dict) and n.get("life_path"):
        return n
    try:
        import numerology as nummod  # type: ignore
        return nummod.numerology(report)
    except Exception:
        return None


def _numerology_votes(report, votes):
    n = _num_of(report)
    if not n:
        return
    lp = n.get("life_path") or {}
    try:
        num = int(lp.get("number"))
    except (TypeError, ValueError):
        num = None
    if num in NUMBER_SIGNALS:
        for dom, sig in NUMBER_SIGNALS[num].items():
            _vote(votes, "numerology", dom, sig,
                  "数字学：生命灵数 %d%s" % (num, "（主数）" if lp.get("is_master") else ""))
    by = n.get("birthday") or {}
    try:
        bnum = int(by.get("number"))
    except (TypeError, ValueError):
        bnum = None
    if bnum in (1, 2, 3, 4, 5, 6, 7, 8, 9):
        dom = {1: "personality", 2: "love", 3: "people", 4: "career",
               5: "move", 6: "family", 7: "study", 8: "wealth", 9: "people"}[bnum]
        _vote(votes, "numerology", dom, 0.2, "数字学：生日数 %d" % bnum)


# ---------------------------------------------------------------- 民俗占法信号

XIAOLIUREN_SIGNAL = {
    "大安": 0.8, "留连": -0.5, "速喜": 1.0, "赤口": -0.9, "小吉": 0.9, "空亡": -1.2,
}

TIYONG_SIGNAL = [
    ("体用比和", 1.0),
    ("用生体", 0.8),
    ("体生用", -0.3),
    ("体克用", 0.3),
    ("用克体", -0.9),
]

CHENGGU_BANDS = [(5.0, 1.0), (4.0, 0.5), (3.1, 0.0), (2.1, -0.6)]


def _folk_of(report):
    d = report.get("divination")
    if isinstance(d, dict) and isinstance(d.get("systems"), dict):
        return d
    try:
        import divination as divmod  # type: ignore
        return divmod.build_divination(report)
    except Exception:
        return None


def _folk_votes(report, votes):
    d = _folk_of(report) or {}
    systems = d.get("systems") if isinstance(d, dict) else None
    if not isinstance(systems, dict):
        return

    lr = systems.get("xiaoliuren") or {}
    if isinstance(lr, dict) and lr.get("available", True) is not False:
        pal = lr.get("palace") or ""
        sig = XIAOLIUREN_SIGNAL.get(pal)
        if sig is not None:
            _vote(votes, "folk", "move", sig * 0.8, "小六壬（当下问事）：%s" % pal)

    mh = systems.get("meihua") or {}
    if isinstance(mh, dict) and mh.get("available", True) is not False:
        rel = _get(mh, "ti_yong", "relation", default="") or ""
        for key, sig in TIYONG_SIGNAL:
            if key in rel:
                _vote(votes, "folk", "career", sig * 0.7, "梅花易数：%s" % rel)
                break

    cg = systems.get("chenggu") or {}
    if isinstance(cg, dict) and cg.get("available", True) is not False:
        try:
            w = float(cg.get("weight"))
        except (TypeError, ValueError):
            w = None
        if w is not None:
            sig = 0.0
            for edge, s in CHENGGU_BANDS:
                if w >= edge:
                    sig = s
                    break
            else:
                sig = -0.8
            _vote(votes, "folk", "wealth", sig * 0.7, "称骨：骨重 %.1f 两" % w)

    z = systems.get("zodiac") or {}
    if isinstance(z, dict) and z.get("available", True) is not False:
        el = _sign_element(z.get("element"))
        info = ELEMENT_DOMAIN.get(el or "")
        if info:
            _vote(votes, "folk", "personality", 0.3,
                  "星座：%s（%s元素）" % (z.get("sign", ""), el))


# ---------------------------------------------------------------- 时机信号

def _bazi_timing(report, tim_votes):
    liunian = _get(report, "chart", "liunian") or []
    focus = None
    for ly in liunian:
        if isinstance(ly, dict) and ly.get("is_focus"):
            focus = ly
            break
    if not focus:
        return None
    tim = focus.get("timing") or {}
    fav = focus.get("favorability") or {}
    sig = 0.0
    label = tim.get("label") or fav.get("label") or ""
    score = tim.get("score", fav.get("score", 0.0))
    try:
        score = float(score)
    except (TypeError, ValueError):
        score = 0.0
    sig = _clamp(score / 2.0, -1.5, 1.5)
    tim_votes.append({
        "system": "bazi",
        "signal": round(sig, 3),
        "evidence": "八字流年 %s %s（%s %+.2f）" % (focus.get("year", ""), focus.get("ganzhi", ""), label, score),
    })
    return {"year": focus.get("year"), "ganzhi": focus.get("ganzhi"), "label": label, "score": score}


def _birth_year(report):
    """从 report 里稳健地取出生年（input.date / chart.input.year / solar）。"""
    v = _get(report, "chart", "input", "year")
    if v:
        return v
    v = _get(report, "input", "year")
    if v:
        return v
    s = str(_get(report, "input", "date") or _get(report, "solar") or "")
    for i in range(0, max(0, len(s) - 4)):
        chunk = s[i:i + 4]
        if chunk.isdigit():
            y = int(chunk)
            if 1800 <= y <= 2200:
                return y
    return None


def _ziwei_timing(report, tim_votes):
    z = _ziwei_of(report)
    if not z:
        return None
    dx = z.get("daxian") or []
    if not dx:
        return None
    # 当前大限：虚岁 = 目标年 - 出生年 + 1，取覆盖该虚岁的宫
    cur = None
    birth_year = _birth_year(report)
    focus_year = None
    for ly in _get(report, "chart", "liunian") or []:
        if isinstance(ly, dict) and ly.get("is_focus"):
            focus_year = ly.get("year")
            break
    if focus_year is None:
        focus_year = datetime.date.today().year
    try:
        age = int(focus_year) - int(birth_year) + 1
    except (TypeError, ValueError):
        age = None
    if age is not None:
        for d in dx:
            if not isinstance(d, dict):
                continue
            try:
                if int(d.get("start_age", 0)) <= age <= int(d.get("end_age", 0)):
                    cur = d
                    break
            except (TypeError, ValueError):
                continue
    if not cur:
        cur = dx[0]
    base = (cur.get("palace") or "").replace("宫", "")
    stars = []
    others = []
    for p in z.get("palaces") or []:
        if isinstance(p, dict) and (p.get("name") or "") == (cur.get("palace") or ""):
            stars = _bracket_stars(p.get("main_stars"))
            others = _bracket_stars(p.get("other_stars"))
            break
    sig = 0.0
    for s in stars:
        sig += ZIWEI_STAR_SIGNAL.get(s, 0.0) * 0.3
    for s in others:
        sig += ZIWEI_OTHER_SIGNAL.get(s, 0.0) * 0.15
    names = stars[:3] + others[:2]
    tim_votes.append({
        "system": "ziwei",
        "signal": round(_clamp(sig, -1.0, 1.0), 3),
        "evidence": "紫微大限：%s宫（%s–%s 岁）%s" % (
            base, cur.get("start_age", ""), cur.get("end_age", ""),
            ("（" + "、".join(names) + "）") if names else "（空宫，借对宫看）"),
    })
    return cur


def _numerology_timing(report, tim_votes):
    n = _num_of(report)
    if not n:
        return None
    py = _get(n, "personal", "year")
    try:
        py = int(py)
    except (TypeError, ValueError):
        return None
    sig = PERSONAL_YEAR_SIGNAL.get(py, 0.0)
    tim_votes.append({
        "system": "numerology",
        "signal": round(sig, 3),
        "evidence": "数字学：个人年 %d" % py,
    })
    return py


def _folk_timing(report, tim_votes):
    d = _folk_of(report) or {}
    systems = d.get("systems") if isinstance(d, dict) else {}
    if not isinstance(systems, dict):
        return None
    lr = systems.get("xiaoliuren") or {}
    pal = lr.get("palace") if isinstance(lr, dict) else None
    if pal and pal in XIAOLIUREN_SIGNAL:
        tim_votes.append({
            "system": "folk",
            "signal": round(XIAOLIUREN_SIGNAL[pal] * 0.8, 3),
            "evidence": "小六壬（当下问事）：%s" % pal,
        })
        return pal
    return None


# ---------------------------------------------------------------- 聚合

def _consensus(sys_sigs, total):
    """sys_sigs: {system: mean_signal}. 返回 (agreement, spread, consensus 标签)."""
    vals = list(sys_sigs.values())
    if len(vals) < 2:
        return (None, None, "单体系参考")
    same = 0.0
    wsum = 0.0
    for s, v in sys_sigs.items():
        w = WEIGHTS.get(s, 0.5)
        wsum += w
        if total > 0 and v > 0:
            same += w
        elif total < 0 and v < 0:
            same += w
    agreement = same / wsum if wsum else 0.0
    import math
    mean = sum(vals) / float(len(vals))
    spread = math.sqrt(sum((v - mean) ** 2 for v in vals) / float(len(vals)))
    if agreement >= 0.75:
        tag = "一致"
    elif agreement >= 0.55:
        tag = "多数"
    elif agreement > 0.0:
        tag = "分歧"
    else:
        tag = "对立"
    return (round(agreement, 2), round(spread, 2), tag)


def _aggregate_domains(votes):
    by_domain = {d: [] for d in DOMAIN_IDS}
    for v in votes:
        by_domain.setdefault(v["domain"], []).append(v)

    out = []
    for dom in DOMAIN_IDS:
        vs = by_domain.get(dom, [])
        groups = {}
        for v in vs:
            groups.setdefault(v["system"], []).append(v)
        # 每个体系在该领域内取均值（同体系多票合并）
        sys_sigs = {}
        sys_evidence = {}
        for s, g in groups.items():
            mean = sum(x["signal"] for x in g) / float(len(g))
            if abs(mean) >= 0.15:
                sys_sigs[s] = mean
                sys_evidence[s] = [x["evidence"] for x in g[:3]]
        if not sys_sigs:
            if vs:
                out.append({
                    "id": dom, "title": DOMAIN_TITLE[dom], "signal": 0.0,
                    "level": "中平", "consensus": "信号相抵", "agreement": None,
                    "spread": None,
                    "votes": [{"system": v["system"], "signal": v["signal"], "evidence": v["evidence"]} for v in vs],
                    "note": "各体系信号方向互相抵消，读取为中平。",
                })
            else:
                out.append({
                    "id": dom, "title": DOMAIN_TITLE[dom], "signal": 0.0,
                    "level": "证据不足", "consensus": "证据不足", "agreement": None,
                    "spread": None, "votes": [],
                    "note": "该领域没有足够强的信号。",
                })
            continue
        wsum = sum(WEIGHTS.get(s, 0.5) for s in sys_sigs)
        total = sum(WEIGHTS.get(s, 0.5) * sig for s, sig in sys_sigs.items()) / wsum
        total = _clamp(total)
        agreement, spread, tag = _consensus(sys_sigs, total)
        out.append({
            "id": dom, "title": DOMAIN_TITLE[dom],
            "signal": round(total, 3), "level": _level(total),
            "consensus": tag, "agreement": agreement, "spread": spread,
            "votes": [{"system": v["system"], "signal": v["signal"], "evidence": v["evidence"]} for v in vs],
            "sys_signal": {s: round(x, 3) for s, x in sys_sigs.items()},
            "note": "",
        })
    return out


def _overall(domains):
    informative = [d for d in domains if d["consensus"] not in ("证据不足",)]
    if not informative:
        return {"agreement": None, "confidence": "低", "summary": "没有足够信号。"}
    agree = [d["agreement"] for d in informative if d["agreement"] is not None]
    mean_agree = sum(agree) / len(agree) if agree else 0.0
    if mean_agree >= 0.75:
        conf = "高"
    elif mean_agree >= 0.55:
        conf = "中"
    else:
        conf = "低"
    pos = [d["title"] for d in informative if d["signal"] >= 0.55]
    neg = [d["title"] for d in informative if d["signal"] <= -0.55]
    parts = []
    if pos:
        parts.append("偏顺的领域：" + "、".join(pos))
    if neg:
        parts.append("偏吃力的领域：" + "、".join(neg))
    if not parts:
        parts.append("各领域接近中平")
    summary = "；".join(parts) + "。跨体系平均一致度 %.2f。" % mean_agree
    return {"agreement": round(mean_agree, 2), "confidence": conf, "summary": summary}


def _tensions(domains):
    out = []
    for d in domains:
        if d["consensus"] in ("分歧", "对立") and len(d.get("sys_signal") or {}) >= 2:
            pieces = ["%s %s" % (k, _fmt_sig(v)) for k, v in sorted(d["sys_signal"].items())]
            out.append({
                "domain": d["id"], "title": d["title"],
                "detail": "%s：%s" % (d["title"], "；".join(pieces)),
            })
    return out


def build_fusion(report):
    """跨体系融合。report 至少要含 chart/analysis（八字），其余体系可缺。"""
    votes = []
    _bazi_votes(report, votes)
    _ziwei_votes(report, votes)
    _western_votes(report, votes)
    _numerology_votes(report, votes)
    _folk_votes(report, votes)

    domains = _aggregate_domains(votes)

    tim_votes = []
    year_info = _bazi_timing(report, tim_votes)
    _ziwei_timing(report, tim_votes)
    _numerology_timing(report, tim_votes)
    _folk_timing(report, tim_votes)

    timing = None
    if tim_votes:
        wsum = sum(WEIGHTS.get(v["system"], 0.5) for v in tim_votes)
        total = sum(WEIGHTS.get(v["system"], 0.5) * v["signal"] for v in tim_votes) / wsum if wsum else 0.0
        total = _clamp(total)
        labels = [v["signal"] for v in tim_votes]
        same = sum(1 for s in labels if s > 0) if total >= 0 else sum(1 for s in labels if s < 0)
        timing = {
            "year": (year_info or {}).get("year"),
            "ganzhi": (year_info or {}).get("ganzhi"),
            "signal": round(total, 3),
            "level": _level(total),
            "consensus": "一致" if len(labels) >= 2 and same == len(labels) else ("多数" if len(labels) >= 2 and same * 2 > len(labels) else "分歧"),
            "votes": tim_votes,
            "note": "时机信号只描述「当前周期是顺是逆」，不预测具体事件。",
        }

    systems = []
    astro_chart = _astro_of(report)
    for key, name, basis in SYSTEMS:
        if key == "bazi":
            avail = True
        elif key == "ziwei":
            avail = bool(_ziwei_of(report))
        elif key == "western":
            avail = bool(astro_chart)
        elif key == "vedic":
            avail = bool((astro_chart or {}).get("vedic"))
        elif key == "numerology":
            avail = bool(_num_of(report))
        else:
            avail = bool(_folk_of(report))
        systems.append({
            "key": key, "name": name, "weight": WEIGHTS[key],
            "available": avail, "basis": basis,
        })

    overall = _overall(domains)
    tensions = _tensions(domains)

    # 体系覆盖度
    avail_n = sum(1 for s in systems if s["available"])
    overall["systems_available"] = avail_n
    overall["systems_total"] = len(systems)

    return {
        "version": VERSION,
        "model": MODEL,
        "inputs": {
            "used_time": _get(report, "time", "used"),
            "date": _get(report, "input", "date") or _get(report, "solar"),
            "location": _get(report, "input", "city") or _get(report, "input", "longitude"),
        },
        "systems": systems,
        "domains": domains,
        "tensions": tensions,
        "timing": timing,
        "overall": overall,
        "limits": list(LIMITS),
    }


# ---------------------------------------------------------------- 渲染

def _system_label(data, key):
    for s in data.get("systems") or []:
        if s.get("key") == key:
            return s.get("name", key)
    return key


SYSTEM_SHORT = {
    "bazi": "八字", "ziwei": "紫微", "western": "西洋", "vedic": "印度",
    "numerology": "数字", "folk": "民俗",
}


def render_fusion_text(data):
    lines = []
    lines.append("═══ 跨体系融合（多模型对照） ═══")
    lines.append("")
    used = [s for s in data.get("systems") or [] if s.get("available")]
    lines.append("参与体系：%d / %d" % (len(used), len(data.get("systems") or [])))
    for s in data.get("systems") or []:
        mark = "✓" if s.get("available") else "—"
        lines.append("  %s %s  权重 %.2f  （%s）" % (mark, s.get("name", ""), s.get("weight", 0), s.get("basis", "")))
    lines.append("")
    ov = data.get("overall") or {}
    lines.append("【整体】一致度 %s，把握 %s" % (
        ("%.2f" % ov["agreement"]) if ov.get("agreement") is not None else "—",
        ov.get("confidence", "低")))
    lines.append("  " + (ov.get("summary") or ""))
    lines.append("")

    for d in data.get("domains") or []:
        if d.get("level") == "证据不足":
            continue
        lines.append("◆ %s：%s（signal %s，%s%s）" % (
            d.get("title", ""), d.get("level", ""), _fmt_sig(d.get("signal", 0.0)),
            d.get("consensus", ""),
            ("，一致度 %.2f" % d["agreement"]) if d.get("agreement") is not None else ""))
        for v in (d.get("votes") or [])[:6]:
            lines.append("    %s %s｜%s" % (SYSTEM_SHORT.get(v["system"], v["system"]), _fmt_sig(v["signal"]), v["evidence"]))
        lines.append("")

    tim = data.get("timing")
    if tim:
        lines.append("【时机】%s%s：%s（signal %s，%s）" % (
            ("%s " % tim.get("year", "")) if tim.get("year") else "",
            tim.get("ganzhi", ""), tim.get("level", ""), _fmt_sig(tim.get("signal", 0.0)),
            tim.get("consensus", "")))
        for v in (tim.get("votes") or [])[:5]:
            lines.append("    %s %s｜%s" % (SYSTEM_SHORT.get(v["system"], v["system"]), _fmt_sig(v["signal"]), v["evidence"]))
        lines.append("  " + (tim.get("note") or ""))
        lines.append("")

    ten = data.get("tensions") or []
    if ten:
        lines.append("【体系分歧】")
        for t in ten:
            lines.append("  · " + t.get("detail", ""))
        lines.append("  分歧不代表谁错，说明不同取象模型在该领域读法不同；以行为建议为主。")
        lines.append("")

    lines.append("【方法学与边界】")
    for s in data.get("limits") or []:
        lines.append("  · " + s)
    lines.append("")
    lines.append("说明：融合层是「多模型对照表」，不是多体系互相验证，也不构成吉凶承诺。")
    return "\n".join(lines)
