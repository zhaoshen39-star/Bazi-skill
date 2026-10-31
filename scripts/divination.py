# -*- coding: utf-8 -*-
"""多术数层（divination）：八字之外的其它传统术数与流行占法，作为交叉参考。

设计原则
--------
1. 纯标准库、零新增运行时依赖；所有输入都取自 ``chart.build`` / ``bazi.build_report``
   已经算好的确定性数据（农历、四柱、日干、时支、性别），同一输入必然得到同一结果。
2. 只做「规则明确、可以写成表」的体系：小六壬、梅花易数（时间起卦）、六爻纳甲（时间起卦）、
   称骨算命、西洋星座、生肖/纳音/三元九运速览。紫微斗数在 ``ziwei.py``，若可导入则并入。
3. 每个体系都输出：结论 + 依据 + 局限；体系之间结论不一致时**并列呈现**，不强行统一，
   也不假装某个体系「更准」。
4. 这些都是传统文化模型与民俗占法，不同流派条文有异文；本模块只提供结构化推演与参考，
   不构成对未来的承诺，也不替代医疗、法律、投资等专业意见。

对外接口
--------
``build_divination(report) -> dict``
    入参是 ``bazi.build_report()`` 的返回 dict，输出各体系结果与交叉参考。
``render_divination_text(data) -> str``
    把上面的 dict 渲染成中文文本（表格 + 断语 + 说明）。
"""

from __future__ import annotations

import datetime

# ---------------------------------------------------------------------------
# 基础常量
# ---------------------------------------------------------------------------

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
ZHI_NUM = {z: i + 1 for i, z in enumerate(ZHI)}

ELEMENT_OF_GAN = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}
ELEMENT_OF_ZHI = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
    "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水",
}
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

MODEL = (
    "多术数层：小六壬、梅花易数、六爻纳甲、称骨算命、西洋星座、生肖纳音速览、"
    "紫微斗数（安星排盘）；各体系独立推演，结论并列参考，不做强行统一。"
)
LIMITS = [
    "各体系流派与条文有异文，本层取常见版本并在文中注明。",
    "梅花易数/六爻为「时间起卦」的通用做法，同一时刻起出的卦只代表那一问的象，不宜反复追问。",
    "紫微斗数按三合派安星规则排盘，只做结构识别与事实陈述，不作吉凶评级；流派差异（飞星/四化）另论。",
    "称骨、星座、小六壬属民俗/流行占法，参考价值有限，不宜当作决策依据。",
    "所有结果都不构成对未来的承诺，也不替代医疗、法律、投资等专业意见。",
]

WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]


# ---------------------------------------------------------------------------
# 通用取数
# ---------------------------------------------------------------------------

def _pillar_gz(report, idx):
    return report["chart"]["pillars"][idx]["ganzhi"]


def _year_ganzhi_of(lunar_year):
    """农历年 → 年干支（甲子=1984 起算）。"""
    return GAN[(lunar_year - 4) % 10] + ZHI[(lunar_year - 4) % 12]


def _context(report):
    """把各体系都要用的出生信息收拢成一份 ctx。"""
    chart = report["chart"]
    lunar = chart["lunar"]
    sex = chart.get("input", {}).get("sex", 1)
    shichen_zhi = chart["pillars"][3]["zhi"]
    lunar_year = int(lunar["year"])
    raw_month = int(lunar["month"])
    leap = raw_month < 0
    yz = _year_ganzhi_of(lunar_year)
    civil = report["time"]["civil"] if isinstance(report.get("time"), dict) else ""
    return {
        "lunar_year": lunar_year,
        "lunar_month": abs(raw_month),
        "leap": leap,
        "lunar_day": int(lunar["day"]),
        "lunar_text": lunar.get("text", ""),
        "lunar_month_cn": lunar.get("month_cn", ""),
        "lunar_day_cn": lunar.get("day_cn", ""),
        "leap_note": "农历月按盘面月份计；若出生在闰月，传统以「闰月前半月作本月、后半月作下月」处理，"
                     "本层未单独区分闰月，仅作提示。",
        "year_ganzhi": yz,
        "year_zhi_num": ZHI_NUM[yz[1]],
        "shichen_zhi": shichen_zhi,
        "shichen_num": ZHI_NUM[shichen_zhi],
        "day_gan": chart["day_gan"],
        "day_zhi": chart["day_zhi"],
        "sex": sex,
        "sex_text": "男" if sex == 1 else "女",
        "civil": civil,
        "pillars": [p["ganzhi"] for p in chart["pillars"]],
        "shengxiao": lunar.get("shengxiao", ""),
    }


def _parse_civil(text):
    try:
        return datetime.datetime.strptime(text[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, KeyError):
        return None


# ---------------------------------------------------------------------------
# 一、小六壬
# ---------------------------------------------------------------------------
# 六宫顺序固定：大安 → 留连 → 速喜 → 赤口 → 小吉 → 空亡。
# 断辞为常见通行本；五行、方位各本有异文，统一标注「常见版本」。
_LIUREN = [
    {
        "name": "大安",
        "luck": "吉",
        "element": "木",
        "direction": "东",
        "image": "身不动、事安稳",
        "verse": "大安事事昌，求谋在东方；失物去不远，宅舍保安康。"
                 "行人身未动，病者主无妨；将军回田野，仔细更推详。",
        "plain": "局面偏静、偏稳：适合守成、按部就班，不宜硬闯；想办的事多半要等一等、稳稳推进。",
    },
    {
        "name": "留连",
        "luck": "中",
        "element": "土",
        "direction": "南（一说北）",
        "image": "事有牵绊、反复拖延",
        "verse": "留连事难成，求谋日未明；官事只宜缓，去者未回程。"
                 "失物南方见，急讨方称心；更须防口舌，人口且平平。",
        "plain": "事情容易拖、容易反复，进度不如预期；急也急不来，先处理牵绊与口舌，再谈推进。",
    },
    {
        "name": "速喜",
        "luck": "吉",
        "element": "火",
        "direction": "南",
        "image": "喜讯将至、动而快",
        "verse": "速喜喜来临，求财向南行；失物申未午，逢人路上寻。"
                 "官事有福德，病者无祸侵；田宅六畜吉，行人有信音。",
        "plain": "偏向好消息、快消息：适合主动出击、争取机会；答复、回音、进展来的速度会快一些。",
    },
    {
        "name": "赤口",
        "luck": "凶",
        "element": "金",
        "direction": "西",
        "image": "口舌是非、争执惊扰",
        "verse": "赤口主口舌，官非切要防；失物急去寻，行人有惊慌。"
                 "鸡犬多作怪，病者出西方；更须防咒诅，恐怕染瘟殃。",
        "plain": "口舌、是非、争执偏多：说话留余地，合同条款看清，别去凑热闹、别硬碰硬。",
    },
    {
        "name": "小吉",
        "luck": "吉",
        "element": "木（一说水）",
        "direction": "东（一说北）",
        "image": "小有和合、有人帮忙",
        "verse": "小吉最吉昌，路上好商量；阴人来报喜，失物在坤方。"
                 "行人立便至，交易甚是强；凡事皆和合，病者叩穹苍。",
        "plain": "偏顺、偏和合：适合谈合作、找人帮忙、谈钱谈条件；小事容易成，贵人多半是身边人。",
    },
    {
        "name": "空亡",
        "luck": "凶",
        "element": "土",
        "direction": "中央",
        "image": "落空、虚耗、没有下文",
        "verse": "空亡事不祥，阴人多乖张；求财无利益，行人有灾殃。"
                 "失物寻不见，官事有刑伤；病人逢暗鬼，析解可安康。",
        "plain": "容易落空：承诺、机会、钱款都可能「看着有、落不到手」；适合收尾止损，不宜新起大项目。",
    },
]


def xiaoliuren(report):
    """小六壬：月从大安起正月，顺数至生月；日从此宫起初一；时从此宫起子时。"""
    ctx = _context(report)
    month, day, hour = ctx["lunar_month"], ctx["lunar_day"], ctx["shichen_num"]
    i_month = (month - 1) % 6
    i_day = (i_month + day - 1) % 6
    i_hour = (i_day + hour - 1) % 6
    p = _LIUREN[i_hour]
    return {
        "system": "小六壬",
        "version": "v1",
        "input": {
            "lunar_text": ctx["lunar_text"],
            "month": month, "day": day,
            "shichen": ctx["shichen_zhi"] + "时",
        },
        "steps": [
            "正月起大安，顺数至%d月 → %s" % (month, _LIUREN[i_month]["name"]),
            "从%s起初一，顺数至%d日 → %s" % (_LIUREN[i_month]["name"], day, _LIUREN[i_day]["name"]),
            "从%s起子时，顺数至%s时 → %s" % (_LIUREN[i_day]["name"], ctx["shichen_zhi"], p["name"]),
        ],
        "palace": p["name"],
        "luck": p["luck"],
        "element": p["element"],
        "direction": p["direction"],
        "image": p["image"],
        "verse": p["verse"],
        "plain": p["plain"],
        "note": "六宫五行与方位各本有异文（如留连属土/属水、小吉属木/属水），断辞取通行本。",
        "limits": ["小六壬多用于「当下问事」，对长期格局参考价值有限。"],
    }


# ---------------------------------------------------------------------------
# 二、梅花易数（时间起卦）
# ---------------------------------------------------------------------------
# 先天八卦数：乾1 兑2 离3 震4 巽5 坎6 艮7 坤8；lines 为该卦三爻（初爻→上爻）的阴阳，1=阳。
_BAGUA = {
    "乾": {"num": 1, "lines": (1, 1, 1), "element": "金", "nature": "天", "image": "健"},
    "兑": {"num": 2, "lines": (1, 1, 0), "element": "金", "nature": "泽", "image": "悦"},
    "离": {"num": 3, "lines": (1, 0, 1), "element": "火", "nature": "火", "image": "丽"},
    "震": {"num": 4, "lines": (1, 0, 0), "element": "木", "nature": "雷", "image": "动"},
    "巽": {"num": 5, "lines": (0, 1, 1), "element": "木", "nature": "风", "image": "入"},
    "坎": {"num": 6, "lines": (0, 1, 0), "element": "水", "nature": "水", "image": "陷"},
    "艮": {"num": 7, "lines": (0, 0, 1), "element": "土", "nature": "山", "image": "止"},
    "坤": {"num": 8, "lines": (0, 0, 0), "element": "土", "nature": "地", "image": "顺"},
}
_NUM2BAGUA = {v["num"]: k for k, v in _BAGUA.items()}

_LOWER_ORDER = ["乾", "兑", "离", "震", "巽", "坎", "艮", "坤"]
_GUA64_ROWS = {
    "乾": ["乾为天", "天泽履", "天火同人", "天雷无妄", "天风姤", "天水讼", "天山遁", "天地否"],
    "兑": ["泽天夬", "兑为泽", "泽火革", "泽雷随", "泽风大过", "泽水困", "泽山咸", "泽地萃"],
    "离": ["火天大有", "火泽睽", "离为火", "火雷噬嗑", "火风鼎", "火水未济", "火山旅", "火地晋"],
    "震": ["雷天大壮", "雷泽归妹", "雷火丰", "震为雷", "雷风恒", "雷水解", "雷山小过", "雷地豫"],
    "巽": ["风天小畜", "风泽中孚", "风火家人", "风雷益", "巽为风", "风水涣", "风山渐", "风地观"],
    "坎": ["水天需", "水泽节", "水火既济", "水雷屯", "水风井", "坎为水", "水山蹇", "水地比"],
    "艮": ["山天大畜", "山泽损", "山火贲", "山雷颐", "山风蛊", "山水蒙", "艮为山", "山地剥"],
    "坤": ["地天泰", "地泽临", "地火明夷", "地雷复", "地风升", "地水师", "地山谦", "坤为地"],
}
GUA64 = {(u, l): name for u, row in _GUA64_ROWS.items() for l, name in zip(_LOWER_ORDER, row)}

# 八卦宫（八纯卦）五行，六爻纳甲用
_GONG_ELEMENT = {
    "乾": "金", "兑": "金", "离": "火", "震": "木",
    "巽": "木", "坎": "水", "艮": "土", "坤": "土",
}


def _num_to_bagua(n):
    return _NUM2BAGUA[((n - 1) % 8) + 1]


def _lines_of(upper, lower):
    """返回六爻（初爻→上爻）的阴阳列表。"""
    return list(_BAGUA[lower]["lines"]) + list(_BAGUA[upper]["lines"])


def _bagua_of(lines3):
    t = tuple(lines3)
    for name, info in _BAGUA.items():
        if info["lines"] == t:
            return name
    raise ValueError("不是合法卦爻：%r" % (lines3,))


def _hexagram_name(upper, lower):
    return GUA64[(upper, lower)]


def _relation(ti, yong):
    """体用五行生克 → (吉凶, 说明)。ti=体, yong=用。"""
    if ti == yong:
        return "吉", "体用比和：事顺，彼此差不多，宜合作。"
    if SHENG[ti] == yong:
        return "小凶", "体生用：你有付出、有消耗，事情能成但费力。"
    if SHENG[yong] == ti:
        return "大吉", "用生体：有人帮你、有外力进来，事顺。"
    if KE[ti] == yong:
        return "吉", "体克用：你能拿下，但要动手去争，过程偏累。"
    if KE[yong] == ti:
        return "凶", "用克体：外面压着你，容易受阻、被人拿捏。"
    return "中", "体用关系不明。"


def _meihua_core(ctx):
    total1 = ctx["year_zhi_num"] + ctx["lunar_month"] + ctx["lunar_day"]
    total2 = total1 + ctx["shichen_num"]
    upper = _num_to_bagua(total1)
    lower = _num_to_bagua(total2)
    dong = ((total2 - 1) % 6) + 1
    lines = _lines_of(upper, lower)
    # 互卦：下互取本卦二三四爻，上互取三四五爻
    hu_lower = _bagua_of(lines[1:4])
    hu_upper = _bagua_of(lines[2:5])
    # 变卦：动爻取反
    bian = list(lines)
    bian[dong - 1] = 1 - bian[dong - 1]
    bian_lower = _bagua_of(bian[0:3])
    bian_upper = _bagua_of(bian[3:6])
    # 体用：动爻所在卦为用，另一卦为体
    if dong <= 3:
        use_part, ti_part = lower, upper
        ti_pos, use_pos = "上卦", "下卦"
    else:
        use_part, ti_part = upper, lower
        ti_pos, use_pos = "下卦", "上卦"
    luck, relation_text = _relation(_BAGUA[ti_part]["element"], _BAGUA[use_part]["element"])
    return {
        "upper": upper, "lower": lower, "dong": dong,
        "lines": lines,
        "ben": _hexagram_name(upper, lower),
        "hu_upper": hu_upper, "hu_lower": hu_lower,
        "hu": _hexagram_name(hu_upper, hu_lower),
        "bian_upper": bian_upper, "bian_lower": bian_lower,
        "bian": _hexagram_name(bian_upper, bian_lower),
        "ti": ti_part, "use": use_part, "ti_pos": ti_pos, "use_pos": use_pos,
        "ti_element": _BAGUA[ti_part]["element"],
        "use_element": _BAGUA[use_part]["element"],
        "luck": luck, "relation_text": relation_text,
        "numbers": {
            "year_zhi_num": ctx["year_zhi_num"], "month": ctx["lunar_month"],
            "day": ctx["lunar_day"], "hour_num": ctx["shichen_num"],
            "sum1": total1, "sum2": total2,
        },
    }


def meihua(report):
    """梅花易数（时间起卦）：年支数+月+日为上卦，再加时支数为下卦，总数取动爻。"""
    ctx = _context(report)
    c = _meihua_core(ctx)
    return {
        "system": "梅花易数",
        "version": "v1",
        "input": {
            "lunar_text": ctx["lunar_text"], "shichen": ctx["shichen_zhi"] + "时",
            "numbers": c["numbers"],
        },
        "ben_gua": {
            "name": c["ben"], "upper": c["upper"], "lower": c["lower"],
            "upper_element": _BAGUA[c["upper"]]["element"],
            "lower_element": _BAGUA[c["lower"]]["element"],
            "dong_yao": c["dong"],
        },
        "hu_gua": {"name": c["hu"], "upper": c["hu_upper"], "lower": c["hu_lower"]},
        "bian_gua": {"name": c["bian"], "upper": c["bian_upper"], "lower": c["bian_lower"]},
        "ti_yong": {
            "ti": c["ti"], "ti_pos": c["ti_pos"], "ti_element": c["ti_element"],
            "use": c["use"], "use_pos": c["use_pos"], "use_element": c["use_element"],
            "relation": c["luck"], "text": c["relation_text"],
        },
        "plain": "本卦「%s」，动第%d爻，变卦「%s」；体%s（%s）对用%s（%s）：%s" % (
            c["ben"], c["dong"], c["bian"],
            c["ti"], c["ti_element"], c["use"], c["use_element"], c["relation_text"],
        ),
        "note": "梅花易数「时间起卦」为通用起法；年用农历年支数，月、日用农历数，时用时辰序数。",
        "limits": ["梅花重在「象」与一问答一卦，同一问题不宜反复起卦。"],
    }


# ---------------------------------------------------------------------------
# 三、六爻纳甲（时间起卦）
# ---------------------------------------------------------------------------
# 纳甲表：每卦六爻（初→上）的 (天干, 地支)
_NAJIA = {
    "乾": [("甲", "子"), ("甲", "寅"), ("甲", "辰"), ("壬", "午"), ("壬", "申"), ("壬", "戌")],
    "坎": [("戊", "寅"), ("戊", "辰"), ("戊", "午"), ("戊", "申"), ("戊", "戌"), ("戊", "子")],
    "艮": [("丙", "辰"), ("丙", "午"), ("丙", "申"), ("丙", "戌"), ("丙", "子"), ("丙", "寅")],
    "震": [("庚", "子"), ("庚", "寅"), ("庚", "辰"), ("庚", "午"), ("庚", "申"), ("庚", "戌")],
    "巽": [("辛", "丑"), ("辛", "亥"), ("辛", "酉"), ("辛", "未"), ("辛", "巳"), ("辛", "卯")],
    "离": [("己", "卯"), ("己", "丑"), ("己", "亥"), ("己", "酉"), ("己", "未"), ("己", "巳")],
    "坤": [("乙", "未"), ("乙", "巳"), ("乙", "卯"), ("癸", "丑"), ("癸", "亥"), ("癸", "酉")],
    "兑": [("丁", "巳"), ("丁", "卯"), ("丁", "丑"), ("丁", "亥"), ("丁", "酉"), ("丁", "未")],
}
_PURE_LINES = {k: list(v["lines"]) * 2 for k, v in _BAGUA.items()}
_SHI_YING = {
    "八纯": (6, 3), "一世": (1, 4), "二世": (2, 5), "三世": (3, 6),
    "四世": (4, 1), "五世": (5, 2), "游魂": (4, 1), "归魂": (3, 6),
}
_LIU_SHEN_ORDER = ["青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武"]
_LIU_SHEN_START = {
    "甲": 0, "乙": 0, "丙": 1, "丁": 1, "戊": 2,
    "己": 3, "庚": 4, "辛": 4, "壬": 5, "癸": 5,
}
_YAO_NAMES = ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"]

# ---- 六爻断语层（v2）：用神 / 旺衰 / 动变 / 应期 ----
# 只做「规则能写死」的推演：月建日辰对爻的旺衰、用神取用、六亲能量、简化应期。
# 不做吉凶断言、不预测具体事件；结论一律标注为「结构倾向」。
_LIU_HE_PAIRS = ("子丑", "寅亥", "卯戌", "辰酉", "巳申", "午未")
_LIU_CHONG_PAIRS = ("子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥")
_LIU_HE = {}
_LIU_CHONG = {}
for _p in _LIU_HE_PAIRS:
    _LIU_HE[_p[0]] = _p[1]
    _LIU_HE[_p[1]] = _p[0]
for _p in _LIU_CHONG_PAIRS:
    _LIU_CHONG[_p[0]] = _p[1]
    _LIU_CHONG[_p[1]] = _p[0]
_SAN_HE_OF = {}
for _trio, _el in (("申子辰", "水"), ("寅午戌", "火"), ("巳酉丑", "金"), ("亥卯未", "木")):
    for _z in _trio:
        _SAN_HE_OF[_z] = (_trio, _el, tuple(x for x in _trio if x != _z))

_JIAZI = [GAN[i % 10] + ZHI[i % 12] for i in range(60)]
_JIAZI_INDEX = {gz: i for i, gz in enumerate(_JIAZI)}

# 六亲互克：用神 → 忌神（六爻传统取法）
_LIUQIN_YONG_JI = {
    "妻财": "兄弟", "官鬼": "子孙", "父母": "妻财", "子孙": "父母", "兄弟": "官鬼",
}


def _xunkong(day_gan, day_zhi):
    """旬空：返回该日所属旬中缺的两个地支。"""
    i = _JIAZI_INDEX.get(day_gan + day_zhi)
    if i is None:
        return []
    start = i - (i % 10)
    covered = {ZHI[(start + j) % 12] for j in range(10)}
    return [z for z in ZHI if z not in covered]


def _month_state(month_el, yao_el):
    """月建对爻的旺衰：旺/相/休/囚/死。"""
    if month_el == yao_el:
        return "旺", 1.00
    if SHENG[month_el] == yao_el:
        return "相", 0.85
    if SHENG[yao_el] == month_el:
        return "休", 0.60
    if KE[yao_el] == month_el:
        return "囚", 0.45
    if KE[month_el] == yao_el:
        return "死", 0.30
    return "?", 0.50


def _day_effect(day_el, day_zhi, yao_el, yao_zhi):
    """日辰对爻的作用：生扶/克伤/比和/冲合。返回 (分值, 说明列表)。"""
    score = 0.0
    notes = []
    if day_el == yao_el:
        score += 0.15
        notes.append("日辰比和+0.15")
    elif SHENG[day_el] == yao_el:
        score += 0.20
        notes.append("日辰生扶+0.20")
    elif KE[day_el] == yao_el:
        score -= 0.20
        notes.append("日辰克伤-0.20")
    elif KE[yao_el] == day_el:
        score -= 0.05
        notes.append("我克日辰(泄)-0.05")
    elif SHENG[yao_el] == day_el:
        score -= 0.05
        notes.append("我生日辰(泄)-0.05")
    if _LIU_CHONG.get(day_zhi) == yao_zhi:
        score -= 0.15
        notes.append("日辰冲爻-0.15")
    if _LIU_HE.get(day_zhi) == yao_zhi:
        score += 0.05
        notes.append("日辰合爻+0.05")
    trio = _SAN_HE_OF.get(day_zhi)
    if trio and yao_zhi in trio[2]:
        score += 0.05
        notes.append("日辰半合+0.05")
    return score, notes


def _gua_type(yao):
    """六冲卦 / 六合卦：初四、二五、三上三对爻的地支是否全冲或全合。"""
    pairs = ((0, 3), (1, 4), (2, 5))
    chong = all(_LIU_CHONG.get(yao[i]["zhi"]) == yao[j]["zhi"] for i, j in pairs)
    he = all(_LIU_HE.get(yao[i]["zhi"]) == yao[j]["zhi"] for i, j in pairs)
    if chong:
        return "六冲卦"
    if he:
        return "六合卦"
    return ""


def _yao_analysis(yao, ctx, gong_element):
    """给每一爻补：月令状态、日辰作用、综合强度、旬空。"""
    month_el = ELEMENT_OF_ZHI[ctx["pillars"][1][1]]
    day_el = ELEMENT_OF_GAN[ctx["day_gan"]]
    day_zhi = ctx["day_zhi"]
    kong = _xunkong(ctx["day_gan"], day_zhi)
    for row in yao:
        state, base = _month_state(month_el, row["element"])
        dscore, dnotes = _day_effect(day_el, day_zhi, row["element"], row["zhi"])
        strength = base + dscore
        if row["dong"]:
            strength += 0.15
        strength = max(0.0, min(1.0, round(strength, 2)))
        row["yue_state"] = state
        row["yue_score"] = base
        row["day_score"] = round(dscore, 2)
        row["day_notes"] = dnotes
        row["strength"] = strength
        row["kong"] = row["zhi"] in kong
        if row["dong"] and row["bian"]:
            bian_zhi = row["bian"][1]
            bian_el = ELEMENT_OF_ZHI[bian_zhi]
            if SHENG[bian_el] == row["element"]:
                row["bian_relation"] = "化回头生"
                row["strength"] = min(1.0, round(row["strength"] + 0.10, 2))
            elif KE[bian_el] == row["element"]:
                row["bian_relation"] = "化回头克"
                row["strength"] = max(0.0, round(row["strength"] - 0.15, 2))
            elif bian_el == row["element"]:
                row["bian_relation"] = "化比和"
            else:
                row["bian_relation"] = "化泄"
    return kong


def _liuqin_energy(yao):
    energy = {}
    for row in yao:
        god = row["liuqin"]
        e = energy.setdefault(god, {"count": 0, "positions": [], "max": 0.0, "sum": 0.0, "dong": 0})
        e["count"] += 1
        e["positions"].append(row["pos"])
        e["sum"] += row["strength"]
        e["max"] = max(e["max"], row["strength"])
        if row["dong"]:
            e["dong"] += 1
    for god, e in energy.items():
        e["avg"] = round(e["sum"] / e["count"], 2)
        e["reliable"] = e["max"] >= 0.55
    return energy


def _pick_yong_shen(questions, energy, yao, shi_pos):
    """按所问之事取用神，并给出该用神在本卦的旺衰状态。"""
    out = []
    for q, god in questions.items():
        if god.startswith("世爻"):
            target = yao[shi_pos - 1]
            score = target["strength"]
            present = True
        else:
            score = energy.get(god, {}).get("max", 0.0)
            present = god in energy
            target = next((r for r in yao if r["liuqin"] == god), None)
        if present and score >= 0.68:
            state = "有力"
        elif present and score >= 0.50:
            state = "中平"
        elif present:
            state = "偏弱"
        else:
            state = "伏藏（本卦不见，需看伏神）"
        out.append({
            "question": q, "god": god, "present": present,
            "score": round(score, 2), "state": state,
            "yao": target["name"] if target else None,
            "dong": bool(target and target["dong"]),
        })
    return out


def _yingqi(yao, yong_rows, kong):
    """简化应期：空待出空/冲实、动待值日/逢合、冲待合或值。只给地支线索。"""
    hints = []
    for row in yong_rows:
        zhi = row["zhi"]
        if zhi in kong:
            alt = _LIU_CHONG.get(zhi, "")
            hints.append({
                "type": "旬空待实", "zhi": [zhi] + ([alt] if alt else []),
                "detail": "%s旬空：逢%s值日或%s冲实之期应" % (row["name"], zhi, alt or "冲"),
            })
        if row["dong"]:
            h = _LIU_HE.get(zhi)
            hints.append({
                "type": "动爻待值", "zhi": [zhi] + ([h] if h else []),
                "detail": "%s发动：值%s日或逢%s合之期应" % (row["name"], zhi, h or "合"),
            })
    if not hints:
        hints.append({"type": "静待扶", "zhi": [], "detail": "用神安静：待月建日辰生扶之期，应期偏晚。"})
    return hints


def _judgement(yong_list, energy):
    """把用神旺衰翻译成「结构倾向」——只作参考，不作预测。"""
    rows = []
    for item in yong_list:
        god = item["god"]
        if not item["present"]:
            rows.append({"question": item["question"], "tendency": "不明", "basis": "用神伏藏，本卦不见"})
            continue
        ji = "官鬼" if god.startswith("世爻") else _LIUQIN_YONG_JI.get(god, "")
        ji_score = energy.get(ji, {}).get("max", 0.0)
        score = item["score"]
        if score < 0.45:
            tend = "用神偏弱"
            basis = "用神%s %.2f 力弱，事倍功半" % (god, score)
        elif ji_score - score >= 0.15:
            tend = "阻力偏大"
            basis = "忌神%s %.2f 旺于用神%s %.2f" % (ji or "无", ji_score, god, score)
        elif score - 0.6 * ji_score >= 0.18:
            tend = "偏顺"
            basis = "用神%s %.2f 得势，忌神%s %.2f" % (god, score, ji or "无", ji_score)
        else:
            tend = "中平"
            basis = "用神%s %.2f，忌神%s %.2f" % (god, score, ji or "无", ji_score)
        rows.append({"question": item["question"], "tendency": tend, "basis": basis})
    return rows


def _flip(lines, idxs):
    out = list(lines)
    for i in idxs:
        out[i] = 1 - out[i]
    return out


def _gong_library():
    """生成八宫六十四卦：{(上卦, 下卦): (宫, 卦名, 世, 应)}。"""
    lib = {}
    for gong in _LOWER_ORDER:
        pure = _PURE_LINES[gong]
        seq = [
            ("八纯", pure),
            ("一世", _flip(pure, [0])),
            ("二世", _flip(pure, [0, 1])),
            ("三世", _flip(pure, [0, 1, 2])),
            ("四世", _flip(pure, [0, 1, 2, 3])),
            ("五世", _flip(pure, [0, 1, 2, 3, 4])),
        ]
        wushi = seq[-1][1]
        youhun = _flip(wushi, [3])
        guihun = _flip(youhun, [0, 1, 2])
        seq.append(("游魂", youhun))
        seq.append(("归魂", guihun))
        for kind, lines in seq:
            upper = _bagua_of(lines[3:6])
            lower = _bagua_of(lines[0:3])
            shi, ying = _SHI_YING[kind]
            lib[(upper, lower)] = (gong, kind, shi, ying)
    return lib


_GONG_LIB = _gong_library()


def _liuqin(gong_element, yao_element):
    if gong_element == yao_element:
        return "兄弟"
    if SHENG[yao_element] == gong_element:
        return "父母"
    if SHENG[gong_element] == yao_element:
        return "子孙"
    if KE[yao_element] == gong_element:
        return "官鬼"
    if KE[gong_element] == yao_element:
        return "妻财"
    return "?"


def _najia_for(upper, lower):
    """六爻纳甲：下卦用内卦三爻，上卦用外卦三爻。"""
    rows = []
    for i in range(3):
        gan, zhi = _NAJIA[lower][i]
        rows.append((gan, zhi))
    for i in range(3, 6):
        gan, zhi = _NAJIA[upper][i]
        rows.append((gan, zhi))
    return rows


def _usc_questions():
    return {
        "财运/收入": "妻财",
        "工作/升迁/考试功名": "官鬼",
        "学业/文书/合同/房子": "父母",
        "子女/出行/项目产出": "子孙",
        "感情（男）": "妻财",
        "感情（女）": "官鬼",
        "健康（自己）": "世爻（兼看官鬼）",
        "朋友/竞争/合作": "兄弟",
    }


def liuyao(report):
    """六爻纳甲：按时间起卦（同梅花取数），排本卦、变卦、六亲、六神、世应与用神提示。"""
    ctx = _context(report)
    c = _meihua_core(ctx)
    upper, lower, dong = c["upper"], c["lower"], c["dong"]
    gong, kind, shi, ying = _GONG_LIB[(upper, lower)]
    gong_element = _GONG_ELEMENT[gong]
    najia = _najia_for(upper, lower)
    bian_lines = list(c["lines"])
    bian_lines[dong - 1] = 1 - bian_lines[dong - 1]
    bu_upper, bu_lower = _bagua_of(bian_lines[3:6]), _bagua_of(bian_lines[0:3])
    bian_najia = _najia_for(bu_upper, bu_lower)
    start = _LIU_SHEN_START[ctx["day_gan"]]
    yao = []
    for i in range(6):
        gan, zhi = najia[i]
        el = ELEMENT_OF_ZHI[zhi]
        yao.append({
            "pos": i + 1,
            "name": _YAO_NAMES[i],
            "gan_zhi": gan + zhi,
            "zhi": zhi,
            "element": el,
            "liuqin": _liuqin(gong_element, el),
            "liushen": _LIU_SHEN_ORDER[(start + i) % 6],
            "shi_ying": "世" if i + 1 == shi else ("应" if i + 1 == ying else ""),
            "dong": (i + 1 == dong),
            "bian": (lambda g, z: g + z)(*bian_najia[i]) if (i + 1 == dong) else "",
        })
    kong = _yao_analysis(yao, ctx, gong_element)
    energy = _liuqin_energy(yao)
    questions = _usc_questions()
    yong_list = _pick_yong_shen(questions, energy, yao, shi)
    yong_rows = [row for row in yao if row["liuqin"] in {item["god"] for item in yong_list}]
    shi_el = yao[shi - 1]["element"]
    ying_el = yao[ying - 1]["element"]
    if shi_el == ying_el:
        shi_ying_rel = "世应比和：双方力量相当，事在人为。"
    elif SHENG[shi_el] == ying_el:
        shi_ying_rel = "世生应：我方付出多、对方受益，主动者吃亏。"
    elif SHENG[ying_el] == shi_el:
        shi_ying_rel = "应生世：对方助力大，事较顺。"
    elif KE[shi_el] == ying_el:
        shi_ying_rel = "世克应：我能压住局面，但要动手争。"
    elif KE[ying_el] == shi_el:
        shi_ying_rel = "应克世：外部阻力大，易被拿捏。"
    else:
        shi_ying_rel = "世应关系不明。"
    counts = {}
    for row in yao:
        counts[row["liuqin"]] = counts.get(row["liuqin"], 0) + 1
    return {
        "system": "六爻纳甲",
        "version": "v2",
        "input": {
            "lunar_text": ctx["lunar_text"], "shichen": ctx["shichen_zhi"] + "时",
            "day_gan": ctx["day_gan"], "day_zhi": ctx["day_zhi"],
            "month_zhi": ctx["pillars"][1][1], "year_zhi": ctx["pillars"][0][1],
        },
        "ben_gua": {
            "name": c["ben"], "upper": upper, "lower": lower,
            "gong": gong + "宫", "gong_element": gong_element, "kind": kind,
            "shi": shi, "ying": ying,
        },
        "bian_gua": {"name": _hexagram_name(bu_upper, bu_lower), "upper": bu_upper, "lower": bu_lower},
        "dong_yao": dong,
        "yao": yao,
        "liuqin_count": counts,
        "questions": questions,
        "analysis": {
            "month_zhi": ctx["pillars"][1][1],
            "month_element": ELEMENT_OF_ZHI[ctx["pillars"][1][1]],
            "day_ganzhi": ctx["day_gan"] + ctx["day_zhi"],
            "day_element": ELEMENT_OF_GAN[ctx["day_gan"]],
            "kong": kong,
            "gua_type": _gua_type(yao),
            "liuqin_energy": energy,
            "yong_shen": yong_list,
            "judgement": _judgement(yong_list, energy),
            "shi_ying": shi_ying_rel,
            "yingqi": _yingqi(yao, yong_rows, kong),
            "caveat": "旺衰按「月建为主、日辰为辅」的通行取法计算；只给结构倾向，不作事件预测。",
        },
        "note": "六爻以「用神旺衰 + 日月建 + 动变」断事；本层给出排卦、用神、旺衰与简化应期，"
                "结论为结构倾向，具体吉凶需结合所问之事与实际情境。",
        "limits": ["起卦方式本层用时间起卦；传统六爻更常用铜钱摇卦，取数法不同则卦不同。",
                   "旺衰权重为工程近似（月建1.0基准 + 日辰±0.2 + 动爻+0.15），不同师承取值有别。"],
    }


# ---------------------------------------------------------------------------
# 四、称骨算命（数据表在 chenggu_table.py，由 references/divination-tables.md 生成）
# ---------------------------------------------------------------------------

def chenggu(report):
    """称骨算命：骨重 = 年干支 + 农历月 + 农历日 + 时辰 四表重量之和。"""
    ctx = _context(report)
    try:
        from chenggu_table import (CHENGGU_YEAR, CHENGGU_MONTH, CHENGGU_DAY, CHENGGU_HOUR,
                                   CHENGGU_VERSES, CHENGGU_VERSES_FEMALE, LIMITS as _chenggu_limits)
    except Exception:
        return {
            "system": "称骨算命",
            "version": "v1",
            "available": False,
            "note": "称骨表数据尚未收入（数据文件 chenggu_table.py 缺失）。",
        }
    yez = _year_ganzhi_of(ctx["lunar_year"])
    sex = ctx.get("sex")
    is_male, is_female = sex == 1, sex == 0
    w_year = CHENGGU_YEAR.get(yez)
    w_month = CHENGGU_MONTH.get(ctx["lunar_month"])
    w_day = CHENGGU_DAY.get(ctx["lunar_day"])
    w_hour = CHENGGU_HOUR.get(ctx["shichen_zhi"])
    missing = [k for k, v in (("年", w_year), ("月", w_month), ("日", w_day), ("时", w_hour)) if v is None]
    if missing:
        return {
            "system": "称骨算命", "version": "v1", "available": False,
            "note": "称骨表缺项：%s" % "、".join(missing),
        }
    total = round(w_year + w_month + w_day + w_hour, 1)
    key = "%.1f" % total
    verse = CHENGGU_VERSES.get(key) if isinstance(CHENGGU_VERSES, dict) else None
    female_verse = CHENGGU_VERSES_FEMALE.get(key) if isinstance(CHENGGU_VERSES_FEMALE, dict) else None
    return {
        "system": "称骨算命",
        "version": "v1",
        "available": True,
        "input": {
            "lunar_text": ctx["lunar_text"], "year_ganzhi": yez,
            "shichen": ctx["shichen_zhi"] + "时",
        },
        "parts": {
            "year": {"ganzhi": yez, "weight": w_year},
            "month": {"month": ctx["lunar_month"], "weight": w_month},
            "day": {"day": ctx["lunar_day"], "weight": w_day},
            "hour": {"shichen": ctx["shichen_zhi"] + "时", "weight": w_hour},
        },
        "weight": key,
        "verse": verse,
        "verse_female": female_verse if (is_female and female_verse) else None,
        "sex": "女" if is_female else ("男" if is_male else None),
        "leap": bool(ctx.get("leap")),
        "confidence": "低（闰月按本月计）" if ctx.get("leap") else "中（民俗通行本，歌诀有异文）",
        "note": "称骨为袁天罡传说的民俗骨重法，各版本歌诀有异文，仅供文化参考。",
        "limits": list(_chenggu_limits),
    }


# ---------------------------------------------------------------------------
# 五、西洋星座
# ---------------------------------------------------------------------------
# 日期区间按通行「太阳星座」划分；真实交界按太阳黄经 15° 刻度，交界日可能差一天。
_ZODIAC = [
    ("摩羯", "12-22", "01-19", "土", "务实、能扛、目标感强、偏保守"),
    ("水瓶", "01-20", "02-18", "风", "独立、想法多、重朋友、疏离感"),
    ("双鱼", "02-19", "03-20", "水", "共情、敏感、想象丰富、易心软"),
    ("白羊", "03-21", "04-19", "火", "直接、行动快、争强、缺耐心"),
    ("金牛", "04-20", "05-20", "土", "稳、重安全感、慢热、固执"),
    ("双子", "05-21", "06-21", "风", "灵活、好奇、话多、专注难久"),
    ("巨蟹", "06-22", "07-22", "水", "顾家、念旧、敏感、防御心强"),
    ("狮子", "07-23", "08-22", "火", "自信、爱面子、有领导欲、要尊重"),
    ("处女", "08-23", "09-22", "土", "细致、挑剔、重秩序、易焦虑"),
    ("天秤", "09-23", "10-23", "风", "讲平衡、重关系、犹豫、审美强"),
    ("天蝎", "10-24", "11-22", "水", "专注、深刻、控制欲、爱恨分明"),
    ("射手", "11-23", "12-21", "火", "乐观、爱自由、直率、粗心"),
]


def _zodiac_of(dt):
    md = (dt.month, dt.day)
    for name, start, end, element, trait in _ZODIAC:
        sm, sd = map(int, start.split("-"))
        em, ed = map(int, end.split("-"))
        if sm > em:  # 跨年（摩羯）
            if md >= (sm, sd) or md <= (em, ed):
                return name, element, trait
        elif (sm, sd) <= md <= (em, ed):
            return name, element, trait
    return "摩羯", "土", "务实、能扛、目标感强、偏保守"


def zodiac(report):
    """西洋太阳星座（按出生公历日期）。"""
    civil = None
    if isinstance(report.get("time"), dict):
        civil = report["time"].get("civil")
    if not civil and "chart" in report:
        civil = _context(report)["civil"]
    dt = _parse_civil(civil)
    if dt is None:
        return {"system": "西洋星座", "version": "v1", "available": False, "note": "无法解析出生日期。"}
    name, element, trait = _zodiac_of(dt)
    return {
        "system": "西洋星座",
        "version": "v1",
        "available": True,
        "sign": name + "座",
        "element": element,
        "trait": trait,
        "birth": dt.strftime("%Y-%m-%d"),
        "note": "按通行太阳星座日期区间划分；真实交界以太阳黄经为准，交界日可能相差一天。"
                "西洋占星完整解盘还需月亮、上升与宫位，本层只给太阳星座速览。",
        "limits": ["太阳星座只是西洋占星的一小部分，不能代表完整星盘。"],
    }


# ---------------------------------------------------------------------------
# 六、生肖 / 纳音 / 三元九运 速览
# ---------------------------------------------------------------------------

def _nayin_of(ganzhi):
    try:
        from chart import NAYIN  # type: ignore
        return NAYIN.get(ganzhi, "")
    except Exception:
        return ""


def _sanyuan_jiumei(year):
    """三元九运：2004–2023 八运（八白艮土），2024–2043 九运（九紫离火）。"""
    if 2004 <= year <= 2023:
        return {"yun": "八运", "element": "土", "range": "2004–2023",
                "note": "八白艮土运：地产、基建、实业为象。"}
    if 2024 <= year <= 2043:
        return {"yun": "九运", "element": "火", "range": "2024–2043",
                "note": "九紫离火运：文化、科技、能源、内容为象（流行说法，属玄学，不是经济预测）。"}
    return {"yun": "—", "element": "—", "range": "—", "note": "不在 2004–2043 区间。"}


def quick_view(report):
    """生肖 / 年柱纳音 / 三元九运速览。"""
    ctx = _context(report)
    year_gz = ctx["pillars"][0]
    now_year = datetime.date.today().year
    return {
        "system": "生肖·纳音·三元九运",
        "version": "v1",
        "shengxiao": ctx["shengxiao"] or ZHI[ZHI_NUM[year_gz[1]] % 12],
        "year_ganzhi": year_gz,
        "nayin": _nayin_of(year_gz),
        "jiumei": _sanyuan_jiumei(now_year),
        "note": "生肖按农历年支；纳音取年柱；三元九运为玄学时间周期说法。",
        "limits": ["三元九运与生肖属相都不描述个人命运，仅作文化背景。"],
    }


# ---------------------------------------------------------------------------
# 七、多术数交叉参考
# ---------------------------------------------------------------------------

def _bazi_keywords(report):
    """从八字 v3 分析里提炼 5 个主题的关键词，供交叉参考。"""
    a = report.get("analysis", {})
    st = a.get("strength") or {}
    ge = a.get("pattern") or {}
    ys = a.get("yong_shen") or {}
    roles = ys.get("shen_roles") or {}
    shares = st.get("party_shares") or {}
    useful = [k for k, v in roles.items() if v in ("用神", "喜神")]
    heavy = [k for k, v in shares.items() if isinstance(v, (int, float)) and v >= 0.30]
    day_zhi = report["chart"]["day_zhi"]
    ri_rel = [r for r in (a.get("relations") or []) if "日柱" in r]
    return {
        "strength": st.get("label", ""),
        "pattern": ge.get("name", ""),
        "status": ge.get("status", ""),
        "useful": useful,
        "heavy": heavy,
        "shares": shares,
        "roles": roles,
        "tiaohou": (((ys.get("methods") or {}).get("tiaohou") or {}).get("primary", "")),
        "force": ys.get("yong_shen_force") or [],
        "xiang_shen": ge.get("xiang_shen") or [],
        "day_zhi": day_zhi,
        "ri_rel": ri_rel,
    }


def _ri_rel_text(rels):
    """把「地支半合火：月柱午与日柱戌半合」这类关系串压成口语短句。"""
    out = []
    for r in rels or []:
        if "：" in r:
            kind, rest = r.split("：", 1)
            kind = kind.replace("地支", "").replace("天干", "天干").strip()
            out.append("%s（%s）" % (rest.strip(), kind) if kind else rest.strip())
        else:
            out.append(r)
    return "；".join(out)


def cross_reference(report, systems):
    """把各体系的说法按主题并列，给出「一致点」与「张力点」。"""
    bz = _bazi_keywords(report)
    shares = bz["shares"]
    topics = []

    def pct(name):
        v = shares.get(name)
        return ("%.1f%%" % (v * 100)) if isinstance(v, (int, float)) else ""

    def add(topic, items, consensus, tension=""):
        topics.append({"topic": topic, "items": items, "consensus": consensus, "tension": tension})

    # 性格
    items = []
    if bz["strength"]:
        items.append(("八字", "日主%s%s、%s，%s" % (
            report["chart"]["day_gan"],
            report["chart"].get("day_gan_wuxing", ""), bz["strength"], bz["pattern"])))
    if "zodiac" in systems and systems["zodiac"].get("available"):
        items.append(("星座", systems["zodiac"]["sign"] + "：" + systems["zodiac"]["trait"]))
    if "ziwei" in systems and systems["ziwei"].get("patterns"):
        cand = [p for p in systems["ziwei"]["patterns"]
                if isinstance(p, dict) and p.get("level") == "成"] or \
               [p for p in systems["ziwei"]["patterns"] if isinstance(p, dict)]
        names = [p.get("name") for p in cand[:2]]
        items.append(("紫微", "；".join(n for n in names if n)))
    if bz["strength"] in ("身弱", "偏弱"):
        consensus = "八字看「底子薄、要借力」，与星座说的外显风格可以并存：一个讲能量结构，一个讲表达方式。"
    elif bz["strength"] in ("身强", "偏强"):
        consensus = "八字看「底子足、能自己扛」，与星座说的外显风格方向一致。"
    else:
        consensus = "八字看「底子较均衡」，性格更受环境与选择影响。"
    add("性格与底色", items, consensus, "星座讲外显风格，八字讲能量结构，不必对号入座。")

    # 财运
    items = []
    if shares:
        items.append(("八字", "财星%s，比劫%s，喜用%s" % (
            pct("财星"), pct("比劫"), "、".join(bz["useful"]) or "（见喜用节）")))
    if "chenggu" in systems and systems["chenggu"].get("available"):
        items.append(("称骨", "骨重%s 两" % systems["chenggu"]["weight"]))
    if "xiaoliuren" in systems:
        items.append(("小六壬（当下问事）", systems["xiaoliuren"]["palace"] + "：" + systems["xiaoliuren"]["image"]))
    if isinstance(shares.get("财星"), (int, float)) and shares.get("财星", 0) >= 0.30 \
            and bz["strength"] in ("身弱", "偏弱"):
        cons = "八字是「财重身弱」的盘子：看得见的机会多，但承接力有限——重现金流与平台，忌杠杆和担保。"
    elif bz["strength"] in ("身强", "偏强"):
        cons = "八字身能任财，赚钱靠主动经营；仍忌把身家压进单一标的。"
    else:
        cons = "求财宜稳、合规、可持续；不碰不懂的杠杆。"
    add("钱与收入", items, cons)

    # 事业
    items = []
    if bz["pattern"]:
        xs = "、".join("%s（%s）" % (x.get("party"), x.get("role")) for x in bz["xiang_shen"][:2]) or "—"
        items.append(("八字", "%s，%s；相神：%s" % (bz["pattern"], bz["status"] or "成败待细看", xs)))
    if "meihua" in systems:
        items.append(("梅花", systems["meihua"]["plain"]))
    if "ziwei" in systems and systems["ziwei"].get("palaces"):
        for p in systems["ziwei"]["palaces"]:
            if p.get("name") == "官禄宫" and p.get("main_stars"):
                items.append(("紫微", "官禄宫%s：%s" % (p["zhi"], "、".join(p["main_stars"]))))
                break
    add("事业与选择", items, "事业宜走「正规路径 + 借力合作」：先把平台与资格坐实，再谈独立单干。")

    # 感情
    items = []
    if bz["day_zhi"]:
        rel = _ri_rel_text(bz["ri_rel"]) or "无合冲刑害"
        items.append(("八字", "夫妻宫（日支%s）：%s" % (bz["day_zhi"], rel)))
    if "zodiac" in systems and systems["zodiac"].get("available"):
        items.append(("星座", systems["zodiac"]["sign"] + "，元素：" + systems["zodiac"]["element"]))
    if "ziwei" in systems and (systems["ziwei"].get("ming_gong") or {}).get("zhi"):
        zw = systems["ziwei"]
        spouses = [p for p in (zw.get("palaces") or []) if p.get("name") == "夫妻宫"]
        sp = spouses[0] if spouses else {}
        sp_main = "、".join(sp.get("main_stars") or []) or "无主星"
        items.append(("紫微", "命宫在%s；夫妻宫%s（%s）" % (
            zw["ming_gong"]["zhi"], sp.get("zhi", "?"), sp_main)))
    add("感情与关系", items, "感情上宜慢、宜说清边界：先在稳定与承诺对等上对齐，再谈推进。")

    # 节奏
    items = []
    if "xiaoliuren" in systems:
        items.append(("小六壬", systems["xiaoliuren"]["palace"] + "（" + systems["xiaoliuren"]["luck"] + "）"))
    if "liuyao" in systems:
        items.append(("六爻", "本卦%s" % systems["liuyao"]["ben_gua"]["name"]))
    if "meihua" in systems:
        items.append(("梅花", "体用：" + systems["meihua"]["ti_yong"]["relation"]))
    add("近期节奏（问事参考）", items,
        "小六壬与六爻都偏「当下问事」，只能代表起卦这一刻的象，不能替代长期判断。")

    return {"topics": topics, "note": "不同体系结论不一致时并列，不强行统一；传统术数不构成命运承诺。"}


# ---------------------------------------------------------------------------
# 编排
# ---------------------------------------------------------------------------

def _safe(fn, report):
    try:
        return fn(report)
    except Exception as exc:  # 单个体系失败不影响其他体系
        return {"system": fn.__name__, "available": False,
                "note": "本体系计算出错：%s: %s" % (type(exc).__name__, exc)}


def _ziwei_system(report):
    try:
        import ziwei  # type: ignore
        return ziwei.chart_ziwei(report)
    except Exception as exc:
        return {"system": "紫微斗数", "available": False,
                "note": "紫微层未启用：%s" % exc}


def build_divination(report):
    """把各术数体系跑一遍并汇总成交叉参考。"""
    systems = {
        "xiaoliuren": _safe(xiaoliuren, report),
        "meihua": _safe(meihua, report),
        "liuyao": _safe(liuyao, report),
        "chenggu": _safe(chenggu, report),
        "zodiac": _safe(zodiac, report),
        "quick_view": _safe(quick_view, report),
        "ziwei": _ziwei_system(report),
    }
    available = {k: v for k, v in systems.items() if isinstance(v, dict) and v.get("available", True) is not False}
    cross = cross_reference(report, systems)
    return {
        "version": 3,
        "model": MODEL,
        "limits": LIMITS,
        "systems": systems,
        "available_count": sum(1 for v in systems.values() if isinstance(v, dict) and v.get("available", True) is not False),
        "cross": cross,
    }


# ---------------------------------------------------------------------------
# 文本渲染
# ---------------------------------------------------------------------------

def _table(header, rows):
    cols = list(zip(*([header] + rows)))
    widths = [max(len(str(c)) for c in col) for col in cols]
    out = []
    for r in [header] + rows:
        out.append("  " + "  ".join(str(c).ljust(w) for c, w in zip(r, widths)))
    return out


def render_divination_text(data):
    """把 build_divination() 的结果渲染成中文文本。"""
    lines = []
    lines.append("══════════════ 多术数交叉参考 ══════════════")
    lines.append("说明：以下各体系独立推演，结论并列参考；不同体系不一致时以「可能性的不同侧面」看待，不强行统一。")
    lines.append("")
    s = data.get("systems", {})

    lr = s.get("xiaoliuren")
    if isinstance(lr, dict) and lr.get("available", True) is not False:
        lines.append("【小六壬】（%s，%s）" % (lr["input"]["lunar_text"], lr["input"]["shichen"]))
        for step in lr["steps"]:
            lines.append("  · " + step)
        lines.append("  落宫：%s（%s，%s，%s）——%s" % (
            lr["palace"], lr["luck"], lr["element"], lr["direction"], lr["image"]))
        lines.append("  断辞：" + lr["verse"])
        lines.append("  白话：" + lr["plain"])
        lines.append("  注：" + lr["note"])
        lines.append("")

    mh = s.get("meihua")
    if isinstance(mh, dict) and mh.get("available", True) is not False:
        lines.append("【梅花易数】（时间起卦）")
        lines.append("  起卦：年支%d + 月%d + 日%d = %d → 上卦%s；再加时支%d = %d → 下卦%s；总数取动爻 = 第%d爻。" % (
            mh["input"]["numbers"]["year_zhi_num"], mh["input"]["numbers"]["month"],
            mh["input"]["numbers"]["day"], mh["input"]["numbers"]["sum1"],
            mh["ben_gua"]["upper"], mh["input"]["numbers"]["hour_num"],
            mh["input"]["numbers"]["sum2"], mh["ben_gua"]["lower"], mh["ben_gua"]["dong_yao"]))
        lines.append("  本卦：%s（%s上%s下）　互卦：%s　变卦：%s" % (
            mh["ben_gua"]["name"], mh["ben_gua"]["upper"], mh["ben_gua"]["lower"],
            mh["hu_gua"]["name"], mh["bian_gua"]["name"]))
        lines.append("  体用：%s%s（%s）　用卦：%s%s（%s）→ %s：%s" % (
            mh["ti_yong"]["ti_pos"], mh["ti_yong"]["ti"], mh["ti_yong"]["ti_element"],
            mh["ti_yong"]["use_pos"], mh["ti_yong"]["use"], mh["ti_yong"]["use_element"],
            mh["ti_yong"]["relation"], mh["ti_yong"]["text"]))
        lines.append("  注：" + mh["note"])
        lines.append("")

    ly = s.get("liuyao")
    if isinstance(ly, dict) and ly.get("available", True) is not False:
        lines.append("【六爻纳甲】（时间起卦）")
        bg = ly["ben_gua"]
        lines.append("  本卦：%s（%s，%s，%s世%s应）　变卦：%s　动爻：第%d爻" % (
            bg["name"], bg["gong"], bg["gong_element"], bg["shi"], bg["ying"],
            ly["bian_gua"]["name"], ly["dong_yao"]))
        rows = []
        for row in reversed(ly["yao"]):
            rows.append([row["name"], row["gan_zhi"], row["liuqin"], row["liushen"],
                         row["shi_ying"], "动" if row["dong"] else "", row["bian"]])
        header = ["六亲", "纳甲", "六亲", "六神", "世应", "动", "变爻"]
        header[0] = "爻位"
        lines.extend(_table(header, rows))
        counts = "、".join("%s×%d" % (k, v) for k, v in ly["liuqin_count"].items())
        lines.append("  六亲分布：" + counts)
        an = ly.get("analysis") or {}
        if an:
            lines.append("  月建：%s（%s）　日辰：%s（%s）　旬空：%s" % (
                an["month_zhi"], an["month_element"], an["day_ganzhi"], an["day_element"],
                "、".join(an["kong"]) or "无"))
            states = "　".join("%s:%s %.2f" % (r["name"], r["yue_state"], r["strength"])
                              for r in ly["yao"])
            lines.append("  爻强度（初→上）：" + states)
            eng = "、".join("%s %.2f×%d" % (god, e["max"], e["count"])
                           for god, e in sorted(an["liuqin_energy"].items(), key=lambda kv: -kv[1]["max"]))
            lines.append("  六亲能量（峰值×爻数）：" + eng)
            if an.get("gua_type"):
                lines.append("  卦性：" + an["gua_type"])
            lines.append("  世应：" + an["shi_ying"])
            lines.append("  用神（按所问之事取用）：")
            for item in an["yong_shen"]:
                lines.append("    %s → %s（%s，强度 %.2f）" % (
                    item["question"], item["god"], item["state"], item["score"]))
            lines.append("  结构倾向（参考，非吉凶断语）：")
            for row in an["judgement"]:
                lines.append("    %s：%s（%s）" % (row["question"], row["tendency"], row["basis"]))
            for hint in an["yingqi"][:3]:
                lines.append("  应期线索：" + hint["detail"])
            lines.append("  断语口径：" + an["caveat"])
        lines.append("  注：" + ly["note"])
        lines.append("")

    cg = s.get("chenggu")
    if isinstance(cg, dict) and cg.get("available"):
        lines.append("【称骨算命】（%s %s）" % (cg["input"]["lunar_text"], cg["input"]["shichen"]))
        parts = cg["parts"]
        lines.append("  年 %s %.1f 两　月 %d月 %.1f 两　日 %d日 %.1f 两　时 %s %.1f 两" % (
            parts["year"]["ganzhi"], parts["year"]["weight"],
            parts["month"]["month"], parts["month"]["weight"],
            parts["day"]["day"], parts["day"]["weight"],
            parts["hour"]["shichen"], parts["hour"]["weight"]))
        lines.append("  合计骨重：%s 两" % cg["weight"])
        if cg.get("verse"):
            lines.append("  歌诀（男命通行本）：" + str(cg["verse"]).replace("\n", "\n  "))
        if cg.get("verse_female"):
            lines.append("  歌诀（女命传本）：" + str(cg["verse_female"]).replace("\n", "\n  "))
        lines.append("  置信度：" + cg.get("confidence", "中"))
        if cg.get("limits"):
            lines.append("  说明：" + cg["limits"][0])
        lines.append("")

    zx = s.get("zodiac")
    if isinstance(zx, dict) and zx.get("available"):
        lines.append("【西洋星座】%s　元素：%s" % (zx["sign"], zx["element"]))
        lines.append("  常见特质：" + zx["trait"])
        lines.append("  注：" + zx["note"])
        lines.append("")

    qv = s.get("quick_view")
    if isinstance(qv, dict) and qv.get("available", True) is not False:
        lines.append("【生肖·纳音·三元九运】")
        lines.append("  生肖：%s　年柱：%s　纳音：%s" % (qv["shengxiao"], qv["year_ganzhi"], qv["nayin"]))
        lines.append("  当前时间周期：%s（%s，%s）%s" % (
            qv["jiumei"]["yun"], qv["jiumei"]["range"], qv["jiumei"]["element"], qv["jiumei"]["note"]))
        lines.append("")

    zw = s.get("ziwei")
    if isinstance(zw, dict) and zw.get("available", True) is not False:
        try:
            import ziwei  # type: ignore
            lines.append(ziwei.render_ziwei_text(zw))
            lines.append("")
        except Exception as exc:
            lines.append("【紫微斗数】渲染失败：%s" % exc)
            lines.append("")

    cross = data.get("cross") or {}
    if cross.get("topics"):
        lines.append("【多体系交叉参考】")
        for t in cross["topics"]:
            lines.append("  ◆ " + t["topic"])
            for sys_name, text in t["items"]:
                lines.append("    · %s：%s" % (sys_name, text))
            if t.get("consensus"):
                lines.append("    一致点：" + t["consensus"])
            if t.get("tension"):
                lines.append("    张力点：" + t["tension"])
        lines.append("")

    lines.append("【方法学与免责】")
    lines.append("  " + data.get("model", MODEL))
    for item in data.get("limits", LIMITS):
        lines.append("  · " + item)
    return "\n".join(lines)
