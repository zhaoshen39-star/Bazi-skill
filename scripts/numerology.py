# -*- coding: utf-8 -*-
"""数字学（Numerology）层：毕达哥拉斯体系的数字计算与结构化解读。

设计原则
--------
1. 纯标准库、零新增运行时依赖；同一 ``(report, name, strokes, surname_len, as_of)``
   必得同一结果，输出可直接 ``json.dumps``。
2. 输入口径与八字排盘一致：出生日期/时间优先取 ``report["time"]["used"]``
   （排盘采用的标准时/真太阳时）；该字段缺失时回退 ``report["input"]["date"]``
   与 ``report["input"]["time"]``。真太阳时跨日或时区换算导致 used 与 civil 日期
   不同时，本层跟随 used（与日柱/时柱同一口径），并在 ``input.date_note`` 注明。
3. 归约规则固定（流派差异一律写进 ``limits``，不静默假设）：
   * 生命灵数：出生年月日逐位求和后归约（2004-06-12 → 2+0+0+4+0+6+1+2 = 15 → 6）；
   * 主数 11/22/33 全程保留：归约过程中只要出现 11/22/33 就停止，不再压成 2/4/6；
   * 生日数 = 「日」归约；态度数 = 「月 + 日」求和后归约；
   * 成熟数 = 生命灵数 + 表达数（表达数来自可用姓名），再归约；
   * 个人年 = 出生月 + 出生日 + 聚焦年（各分量先归约、保留主数）相加再归约；
     个人月/日 = 上一步数字 + 参考日期的月/日，再归约（常见简化算法）。
4. 姓名：
   * 拉丁字母按 A=1…Z=26 求和归约（任务约定；不是毕氏字母表
     A=1…I=9、J=1…R=9、S=1…Z=8），得到表达数 Expression、灵魂数 Soul Urge
     （元音）、人格数 Personality（辅音）；Y 仅当名字没有 A/E/I/O/U 时按元音处理。
   * 中文姓名不内置汉字笔画表：没有外部笔画数据时返回 ``name_supported: false``
     并说明；若调用方传入 ``strokes``（每个汉字笔画数）则按单姓/复姓通行的
     「姓名五格」（天格/人格/地格/外格/总格，含假成数）计算。
5. 九宫格（Lo Shu）采用常见布局：

       4 9 2
       3 5 7
       8 1 6

   出生日期中的 1–9 逐位落宫（0 不计），统计缺失、重复与 8 条连线
   （3 横 + 3 竖 + 2 斜）；连线名与解读是流行体系的一种对应。
6. 数字学属现代民俗/流行心理学，无学术预测效度；本层只提供结构化叙事参考，
   不构成对未来的承诺，也不替代医疗、法律、投资等专业意见。

对外接口
--------
``numerology(report, name=None, strokes=None, surname_len=1, as_of=None) -> dict``
    入参是 ``bazi.build_report()`` 的返回 dict（只读取 input/time/focus_year，
    不重算排盘）。``name`` 缺省时从 ``report["input"]["name"]`` 读取；
    ``as_of`` 是个人月/日的参考日期（date / "YYYY-MM-DD"），缺省取今天。
``render_numerology_text(data) -> str``
    把上面的 dict 渲染成中文文本（分段 + 九宫格 + 说明 + 局限）。
``main(argv)`` / ``python scripts/numerology.py ...``
    独立校验用的小 CLI；带 ``--json`` 输出结构化结果。
"""

from __future__ import annotations

import datetime

# ---------------------------------------------------------------------------
# 基础常量
# ---------------------------------------------------------------------------

VERSION = 3

#: 主数：归约过程中出现即保留，不再继续压成一位数。
MASTERS = (11, 22, 33)
MASTER_SET = frozenset(MASTERS)

MODEL = (
    "毕达哥拉斯数字学（Pythagorean numerology）：公历出生日期逐位求和归约、"
    "主数 11/22/33 全程保留、九宫格（Lo Shu）布局与拉丁字母 A=1…Z=26 姓名数字；"
    "纯规则、确定性计算，无随机、无联网。"
)

LIMITS = [
    "数字学属现代民俗/流行心理学，无学术预测效度。",
    "同一生日存在多种归约流派（逐位求和 / 年月日分别归约 / 主数是否在中间步骤保留），"
    "本层固定采用「逐位求和 + 主数 11/22/33 全程保留」；换流派会得到不同数字。",
    "姓名数字：拉丁名按 A=1…Z=26 直接求和（并非毕达哥拉斯字母表 "
    "A=1…I=9、J=1…R=9、S=1…Z=8），只是字符序号映射；中文姓名需外部笔画表，"
    "本模块不内置汉字笔画。",
    "九宫格（Lo Shu）的连线命名、「缺失/重复」解读属流行体系的一种说法，各派对应关系不一。",
    "个人年/月/日以上一步数字加参考日期的月/日归约，属常见简化算法；"
    "不同书籍的起算点（生日当天 / 元旦）不同。",
    "所有结果只作自我认识与叙事参考，不构成对未来的承诺，也不替代医疗、法律、投资等专业意见。",
]

#: 数字含义表：1–9 与主数 11/22/33。每类关键词 ≥2 条。
NUMBER_MEANINGS = {
    1: {
        "title": "1 · 开创者",
        "root": 1,
        "is_master": False,
        "personality": ["独立", "主动", "自我主张", "有主见"],
        "strengths": ["行动力", "领导力", "开拓精神"],
        "weaknesses": ["固执", "急躁", "不易服管"],
        "directions": ["创业", "管理", "自由职业", "销售"],
        "summary": "倾向于自己拿主意、先动手再调整；适合需要开疆拓土、独立拍板的场景。",
    },
    2: {
        "title": "2 · 协调者",
        "root": 2,
        "is_master": False,
        "personality": ["合作", "敏感", "体贴", "善于倾听"],
        "strengths": ["协调力", "共情力", "细节感"],
        "weaknesses": ["犹豫", "依赖", "容易受伤"],
        "directions": ["咨询", "教育", "合作型岗位", "护理"],
        "summary": "擅长把人和事撮合到一起，重视关系与平衡；独处时的情绪照顾同样重要。",
    },
    3: {
        "title": "3 · 表达者",
        "root": 3,
        "is_master": False,
        "personality": ["创意", "表达", "乐观", "社交"],
        "strengths": ["表现力", "想象力", "沟通"],
        "weaknesses": ["散漫", "浮夸", "情绪化"],
        "directions": ["写作", "设计", "传播", "表演"],
        "summary": "靠表达与创意获得能量，越能「说出来、做出来」越顺；需防虎头蛇尾。",
    },
    4: {
        "title": "4 · 建构者",
        "root": 4,
        "is_master": False,
        "personality": ["务实", "秩序", "稳定", "负责"],
        "strengths": ["执行力", "组织力", "耐心"],
        "weaknesses": ["死板", "保守", "抗拒变化"],
        "directions": ["工程", "财务", "运营", "制造"],
        "summary": "喜欢可验证、可重复的秩序，靠积累成事；给变化留一点缝隙会更省力。",
    },
    5: {
        "title": "5 · 自由者",
        "root": 5,
        "is_master": False,
        "personality": ["好奇", "变化", "冒险", "适应"],
        "strengths": ["应变力", "学习力", "交际"],
        "weaknesses": ["不安分", "怕束缚", "易冲动"],
        "directions": ["销售", "旅行", "媒体", "跨界项目"],
        "summary": "在变化与新鲜感里最有活力；把「自由」变成可执行的节奏，比一味求变更稳。",
    },
    6: {
        "title": "6 · 照顾者",
        "root": 6,
        "is_master": False,
        "personality": ["责任", "关爱", "家庭", "审美"],
        "strengths": ["责任感", "疗愈力", "审美力"],
        "weaknesses": ["过度付出", "控制", "挑剔"],
        "directions": ["医疗", "教育", "服务", "家居美业"],
        "summary": "天然愿意照顾身边人，也重视美感与秩序；先照顾好自己，付出才可持续。",
    },
    7: {
        "title": "7 · 探索者",
        "root": 7,
        "is_master": False,
        "personality": ["内省", "分析", "求知", "独处"],
        "strengths": ["分析力", "洞察力", "研究"],
        "weaknesses": ["多疑", "疏离", "想太多"],
        "directions": ["研究", "技术", "哲学", "专业顾问"],
        "summary": "需要独处与深度思考来充电，喜欢追问「为什么」；别让分析代替行动。",
    },
    8: {
        "title": "8 · 掌控者",
        "root": 8,
        "is_master": False,
        "personality": ["权力", "资源", "成就", "务实"],
        "strengths": ["统御力", "资源整合", "执行力"],
        "weaknesses": ["控制欲", "物质化", "压力大"],
        "directions": ["管理", "金融", "企业", "项目操盘"],
        "summary": "对结果与资源敏感，适合在现实世界做规模化的事；把掌控欲换成授权会更顺。",
    },
    9: {
        "title": "9 · 理想者",
        "root": 9,
        "is_master": False,
        "personality": ["博爱", "理想", "包容", "艺术"],
        "strengths": ["想象力", "同理心", "格局"],
        "weaknesses": ["空想", "情绪化", "界限感弱"],
        "directions": ["公益", "艺术", "教育", "人文"],
        "summary": "看得到更大的图景，愿意为理想与群体付出；需要把宏大愿望切成可做的小步。",
    },
    11: {
        "title": "11 · 启发者（主数）",
        "root": 2,
        "is_master": True,
        "personality": ["直觉", "灵感", "感召", "敏感"],
        "strengths": ["洞察力", "鼓舞力", "直觉判断"],
        "weaknesses": ["焦虑", "理想化", "能量不稳"],
        "directions": ["心理咨询", "教育", "创作", "灵性/公益"],
        "summary": "主数 11 是 2 的强化版：感受力与直觉被放大，适合启发与陪伴他人；先稳住自己的能量。",
    },
    22: {
        "title": "22 · 建造者（主数）",
        "root": 4,
        "is_master": True,
        "personality": ["愿景落地", "组织", "担当", "务实"],
        "strengths": ["规划力", "执行力", "资源整合"],
        "weaknesses": ["压力过载", "完美主义", "固执"],
        "directions": ["大型项目", "工程", "社会企业", "组织管理"],
        "summary": "主数 22 是 4 的强化版：能把抽象愿景拆成工程；注意别把「必须做成」变成自我压迫。",
    },
    33: {
        "title": "33 · 疗愈者（主数）",
        "root": 6,
        "is_master": True,
        "personality": ["奉献", "疗愈", "责任", "慈悲"],
        "strengths": ["共情力", "教导", "服务"],
        "weaknesses": ["过度承担", "牺牲自我", "控制"],
        "directions": ["医疗", "教育", "公益", "心理支持"],
        "summary": "主数 33 是 6 的强化版：以「照顾与教导」为底色；边界与自我照顾是长期课题。",
    },
}

# ---------------------------------------------------------------------------
# 九宫格（Lo Shu）
# ---------------------------------------------------------------------------

#: 洛书布局：行优先的三行三列，每格是「宫位数字」。
LO_SHU_LAYOUT = [[4, 9, 2], [3, 5, 7], [8, 1, 6]]

#: 数字 → (行, 列)（0 基），由 LO_SHU_LAYOUT 反推，写死便于校验。
LO_SHU_POS = {
    4: (0, 0), 9: (0, 1), 2: (0, 2),
    3: (1, 0), 5: (1, 1), 7: (1, 2),
    8: (2, 0), 1: (2, 1), 6: (2, 2),
}

#: 每宫（数字）的简要含义：后天八卦宫位 + 流行数字学的关键词。
LO_SHU_CELL_MEANINGS = {
    1: "坎宫（水）·独立/开创/事业",
    2: "坤宫（土）·合作/敏感/婚姻",
    3: "震宫（木）·表达/行动/家庭",
    4: "巽宫（木）·秩序/务实/财富",
    5: "中宫（土）·自由/变化/枢纽",
    6: "乾宫（金）·责任/权威/家庭",
    7: "兑宫（金）·内省/沟通/子女",
    8: "艮宫（土）·积累/执行/学业",
    9: "离宫（火）·理想/名声/艺术",
}

#: 8 条连线：名称、三格数字、类型、含义（流行体系的一种对应）。
LO_SHU_LINES = [
    {"name": "4-9-2", "numbers": [4, 9, 2], "type": "横", "position": "顶行",
     "meaning": "思考规划线：条理性、计划性与理念表达，三数齐全时偏「先想后做」。"},
    {"name": "3-5-7", "numbers": [3, 5, 7], "type": "横", "position": "中行",
     "meaning": "情绪平衡线：感受力、关系与体验的平衡，三数齐全时情绪流动较顺。"},
    {"name": "8-1-6", "numbers": [8, 1, 6], "type": "横", "position": "底行",
     "meaning": "务实行动线：落实、责任与执行力，三数齐全时更能把事做完。"},
    {"name": "4-3-8", "numbers": [4, 3, 8], "type": "竖", "position": "左列",
     "meaning": "秩序思考线：规则、体系化与稳健执行，三数齐全时偏「按部就班」。"},
    {"name": "9-5-1", "numbers": [9, 5, 1], "type": "竖", "position": "中列",
     "meaning": "意志执行线：目标感与意志力，三数齐全时更能顶住压力推进。"},
    {"name": "2-7-6", "numbers": [2, 7, 6], "type": "竖", "position": "右列",
     "meaning": "行动应变线：人际感受与灵活应对，三数齐全时较擅长处理关系。"},
    {"name": "4-5-6", "numbers": [4, 5, 6], "type": "斜", "position": "左上-右下",
     "meaning": "成就线：事业成就与稳定度，三数齐全时偏「能落地、能积累」。"},
    {"name": "2-5-8", "numbers": [2, 5, 8], "type": "斜", "position": "右上-左下",
     "meaning": "情感慈悲线：共情、直觉与人缘，三数齐全时更能感受他人。"},
]

#: 拉丁字母表：A=1 … Z=26（按任务约定，非毕氏字母表）。
LATIN_VALUES = {chr(ord("A") + i): i + 1 for i in range(26)}
STD_VOWELS = frozenset("AEIOU")

# ---------------------------------------------------------------------------
# 归约基础
# ---------------------------------------------------------------------------


def _digit_sum(n):
    """十进制逐位求和（对非负整数）。"""
    return sum(int(ch) for ch in str(int(n)))


def _reduce_chain(n):
    """把非负整数按「逐位求和」归约，返回 ``(结果, 链)``。

    主数 11/22/33 全程保留：链中一旦出现即停止，结果等于该主数。
    链包含起始值和每一步中间值，例如 15 → ``(6, [15, 6])``；
    29 → ``(11, [29, 11])``；1990 → ``(1, [1990, 19, 10, 1])``。
    """
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError("归约输入必须是整数，收到 %r" % (n,))
    if n < 0:
        raise ValueError("归约输入不能为负数：%r" % (n,))
    chain = [n]
    value = n
    while value > 9 and value not in MASTER_SET:
        value = _digit_sum(value)
        chain.append(value)
    return value, chain


def _reduce(n):
    """只要归约结果（保留主数）。"""
    return _reduce_chain(n)[0]


def _is_master(n):
    return int(n) in MASTER_SET


def _keywords(number, limit=4):
    """取数字含义表里的前几条关键词（personality + strengths）。"""
    item = NUMBER_MEANINGS[number]
    words = list(item["personality"][:2]) + list(item["strengths"][:2])
    if item["is_master"] and "主数" not in words:
        words.insert(0, "主数")
    return words[:limit]


def _number_entry(number, chain):
    """带含义的数字条目：life_path / birthday / attitude / maturity 通用。"""
    item = NUMBER_MEANINGS[number]
    return {
        "number": number,
        "is_master": bool(item["is_master"]),
        "root": item["root"],
        "chain": list(chain),
        "keywords": _keywords(number),
        "title": item["title"],
        "summary": item["summary"],
    }


def _chain_text(chain):
    return " → ".join(str(x) for x in chain)


def _digits_of_date(date_obj):
    """公历日期 → 8 位数字列表（YYYYMMDD 逐位，保留 0）。"""
    text = "%04d%02d%02d" % (date_obj.year, date_obj.month, date_obj.day)
    return [int(ch) for ch in text]


# ---------------------------------------------------------------------------
# 输入上下文（与八字排盘同一时间口径）
# ---------------------------------------------------------------------------


def _parse_datetime(value):
    """宽松解析日期/时间字符串或 datetime，失败返回 None。"""
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime(value.year, value.month, value.day)
    if not isinstance(value, str):
        return None
    text = value.strip().replace("T", " ")
    if not text:
        return None
    for fmt, size in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M", 16),
                      ("%Y-%m-%d", 10)):
        try:
            return datetime.datetime.strptime(text[:size], fmt)
        except ValueError:
            continue
    return None


def _parse_date(value, field="date"):
    """解析 date / datetime / "YYYY-MM-DD"；非法时抛 ValueError。"""
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        text = value.strip().replace("T", " ")[:10]
        try:
            return datetime.datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("%s 不是有效的公历日期：%r" % (field, value))
    raise ValueError("%s 不是有效的公历日期：%r" % (field, value))


def _input_context(report, as_of=None):
    """收拢数字学需要的输入：出生日期/时间（优先 used）、聚焦年、参考日期。"""
    if not isinstance(report, dict):
        raise TypeError("report 必须是 dict（bazi.build_report() 的返回值），收到 %r"
                        % type(report).__name__)
    inp = report.get("input") if isinstance(report.get("input"), dict) else {}
    t = report.get("time") if isinstance(report.get("time"), dict) else {}

    reference_date = _parse_date(as_of, "as_of") if as_of is not None \
        else datetime.date.today()

    civil_date = None
    if inp.get("date"):
        try:
            civil_date = _parse_date(inp["date"], "input.date")
        except ValueError:
            civil_date = None

    birth_dt = None
    date_source = ""
    used_text = t.get("used")
    if used_text:
        birth_dt = _parse_datetime(used_text)
        if birth_dt is not None:
            date_source = "time.used"
    if birth_dt is None and inp.get("date"):
        day = _parse_date(inp["date"], "input.date")
        time_text = inp.get("time") or "00:00:00"
        hh = mm = ss = 0
        parts = str(time_text).strip().split(":")
        try:
            hh = int(parts[0])
            mm = int(parts[1]) if len(parts) > 1 else 0
            ss = int(parts[2]) if len(parts) > 2 else 0
            birth_dt = datetime.datetime(day.year, day.month, day.day, hh, mm, ss)
            date_source = "input.date+input.time" if inp.get("time") else "input.date"
        except (ValueError, IndexError):
            raise ValueError("input.time 不是有效时间：%r" % (time_text,))
    if birth_dt is None:
        raise ValueError("report 缺少出生日期：需要 time.used 或 input.date")
    birth_date = birth_dt.date()

    # 聚焦年：优先 report["focus_year"]，其次 chart.liunian 的 is_focus，最后参考日期年份
    focus_year = report.get("focus_year")
    if focus_year in (None, ""):
        chart = report.get("chart") if isinstance(report.get("chart"), dict) else {}
        for item in chart.get("liunian") or []:
            if isinstance(item, dict) and item.get("is_focus"):
                focus_year = item.get("year")
                break
    if focus_year in (None, ""):
        focus_year = reference_date.year
    try:
        focus_year = int(focus_year)
    except (TypeError, ValueError):
        raise ValueError("focus_year 不是合法年份：%r" % (focus_year,))
    if not 1 <= focus_year <= 9999:
        raise ValueError("focus_year 需在 1–9999 之间：%r" % (focus_year,))

    date_note = ""
    if civil_date is not None and civil_date != birth_date:
        date_note = (
            "记录日期 %s 与排盘采用日期 %s 不同（真太阳时跨日或时区换算）；"
            "本层与八字排盘同口径，按排盘采用日期计算。"
            % (civil_date.isoformat(), birth_date.isoformat()))

    return {
        "birth_dt": birth_dt,
        "birth_date": birth_date,
        "birth_time": birth_dt.strftime("%H:%M:%S"),
        "civil_date": civil_date,
        "civil_time": str(inp.get("time") or ""),
        "used_time": birth_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "date_source": date_source,
        "time_label": t.get("used_label") or "",
        "used_kind": t.get("used_kind") or "",
        "date_note": date_note,
        "focus_year": focus_year,
        "reference_date": reference_date,
        "zone": inp.get("zone") or t.get("zone") or "",
        "sex": inp.get("sex"),
    }


# ---------------------------------------------------------------------------
# 各数字计算
# ---------------------------------------------------------------------------


def _life_path(birth_date):
    """生命灵数：出生年月日逐位求和归约（主数保留）。"""
    digits = _digits_of_date(birth_date)
    raw_sum = sum(digits)
    number, chain = _reduce_chain(raw_sum)
    entry = _number_entry(number, chain)
    entry.update({
        "raw_sum": raw_sum,
        "digits": digits,
        "components": {
            "year": _reduce(birth_date.year),
            "month": _reduce(birth_date.month),
            "day": _reduce(birth_date.day),
        },
        "note": "逐位求和：%s = %s" % (
            "+".join(str(d) for d in digits), _chain_text(chain)),
    })
    return entry


def _birthday_number(birth_date):
    """生日数：出生「日」归约（29 → 11 这类主数保留）。"""
    day = birth_date.day
    number, chain = _reduce_chain(day)
    entry = _number_entry(number, chain)
    entry.update({"day": day, "note": "出生日 %s" % _chain_text(chain)})
    return entry


def _attitude_number(birth_date):
    """态度数：出生「月 + 日」求和归约。"""
    total = birth_date.month + birth_date.day
    number, chain = _reduce_chain(total)
    entry = _number_entry(number, chain)
    entry.update({
        "month": birth_date.month,
        "day": birth_date.day,
        "raw_sum": total,
        "note": "%d + %d = %s" % (
            birth_date.month, birth_date.day, _chain_text(chain)),
    })
    return entry


def _maturity_number(life_path, expression):
    """成熟数：生命灵数 + 表达数（无可用姓名时不可算）。"""
    if not expression or not expression.get("number"):
        return {
            "available": False,
            "number": None,
            "is_master": False,
            "root": None,
            "chain": [],
            "keywords": [],
            "title": "成熟数（不可算）",
            "summary": "",
            "note": "成熟数需要「表达数」，而表达数来自可计算的姓名（拉丁字母名）；"
                    "未提供可用姓名时不可算。",
        }
    total = life_path["number"] + expression["number"]
    number, chain = _reduce_chain(total)
    entry = _number_entry(number, chain)
    entry.update({
        "available": True,
        "note": "生命灵数 %d + 表达数 %d = %d → %s" % (
            life_path["number"], expression["number"], total, _chain_text(chain)),
    })
    return entry


def _personal_numbers(birth_date, focus_year, reference_date):
    """个人年/月/日：年 = 月+日+聚焦年；月/日 = 上一步 + 参考日期的月/日。"""
    m = _reduce(birth_date.month)
    d = _reduce(birth_date.day)
    y = _reduce(focus_year)
    year_num, year_chain = _reduce_chain(m + d + y)
    month_num, month_chain = _reduce_chain(year_num + reference_date.month)
    day_num, day_chain = _reduce_chain(month_num + reference_date.day)
    return {
        "year": year_num,
        "month": month_num,
        "day": day_num,
        "year_is_master": _is_master(year_num),
        "month_is_master": _is_master(month_num),
        "day_is_master": _is_master(day_num),
        "year_chain": year_chain,
        "month_chain": month_chain,
        "day_chain": day_chain,
        "year_keywords": _keywords(year_num),
        "month_keywords": _keywords(month_num),
        "day_keywords": _keywords(day_num),
        "year_title": NUMBER_MEANINGS[year_num]["title"],
        "month_title": NUMBER_MEANINGS[month_num]["title"],
        "day_title": NUMBER_MEANINGS[day_num]["title"],
        "components": {"month": m, "day": d, "year": y},
        "focus_year": focus_year,
        "reference_date": reference_date.isoformat(),
        "note": "个人年 = 出生月(%d) + 出生日(%d) + 聚焦年(%d) → %s；"
                "个人月 = 个人年 + 参考月(%d) → %s；"
                "个人日 = 个人月 + 参考日(%d) → %s。" % (
                    m, d, y, _chain_text(year_chain),
                    reference_date.month, _chain_text(month_chain),
                    reference_date.day, _chain_text(day_chain)),
    }


def _grid_from_date(birth_date):
    """九宫格（Lo Shu）：出生日期 1–9 落宫，统计缺失/重复/8 条连线。"""
    digits = _digits_of_date(birth_date)
    # 键用字符串，保证 json.dumps → json.loads 往返结构完全相同
    counts = {str(n): digits.count(n) for n in range(1, 10)}
    cells = []
    for n in range(1, 10):
        row, col = LO_SHU_POS[n]
        cells.append({
            "number": n,
            "count": counts[str(n)],
            "present": counts[str(n)] > 0,
            "row": row,
            "col": col,
            "meaning": LO_SHU_CELL_MEANINGS[n],
        })
    missing = [n for n in range(1, 10) if counts[str(n)] == 0]
    repeats = [{"number": n, "count": counts[str(n)],
                "meaning": LO_SHU_CELL_MEANINGS[n]}
               for n in range(1, 10) if counts[str(n)] >= 2]
    lines = []
    for item in LO_SHU_LINES:
        lack = [n for n in item["numbers"] if counts[str(n)] == 0]
        lines.append({
            "name": item["name"],
            "numbers": list(item["numbers"]),
            "type": item["type"],
            "position": item["position"],
            "formed": not lack,
            "missing_numbers": lack,
            "meaning": item["meaning"],
        })
    return {
        "layout": [list(row) for row in LO_SHU_LAYOUT],
        "digits": digits,
        "cells": cells,
        "counts": counts,
        "missing": missing,
        "missing_detail": [{"number": n, "meaning": LO_SHU_CELL_MEANINGS[n]}
                           for n in missing],
        "repeats": repeats,
        "lines": lines,
        "formed_count": sum(1 for x in lines if x["formed"]),
        "total_lines": len(lines),
        "note": "出生日期逐位落宫（0 不计）；连线三格齐全才算成形。",
    }


# ---------------------------------------------------------------------------
# 姓名数字
# ---------------------------------------------------------------------------


def _parse_strokes(strokes):
    """把笔画数据解析成 int 列表：支持 list/tuple 或 "7,6"/"7 6"/"7、6"。"""
    if strokes is None:
        return None
    if isinstance(strokes, (list, tuple)):
        values = list(strokes)
    elif isinstance(strokes, str):
        text = strokes.strip()
        if not text:
            return []
        for sep in ("、", ",", "，", "/", "|"):
            text = text.replace(sep, " ")
        values = text.split()
    else:
        raise ValueError("strokes 需为整数列表或逗号分隔字符串：%r" % (strokes,))
    result = []
    for item in values:
        try:
            n = int(item)
        except (TypeError, ValueError):
            raise ValueError("strokes 含非整数项：%r" % (item,))
        if n <= 0:
            raise ValueError("笔画数必须为正整数：%r" % (item,))
        result.append(n)
    return result


def _normalize_81(n):
    """五格数理 1–81：超过 81 的按传统减 80 循环。"""
    return ((int(n) - 1) % 80) + 1


def _five_grid(strokes, surname_len=1):
    """姓名五格（天格/人格/地格/外格/总格），单姓/复姓通行算法含假成数。"""
    strokes = list(strokes)
    if surname_len not in (1, 2):
        raise ValueError("surname_len 只支持 1（单姓）或 2（复姓）：%r" % (surname_len,))
    if len(strokes) < 2:
        raise ValueError("姓名五格至少需要姓与名两个字的笔画：%r" % (strokes,))
    if surname_len >= len(strokes):
        raise ValueError("姓名字数与 surname_len 不匹配：%r / %d" % (strokes, surname_len))
    surname = strokes[:surname_len]
    given = strokes[surname_len:]
    tian = sum(surname) + 1 if surname_len == 1 else sum(surname)
    ren = surname[-1] + given[0]
    di = sum(given) + 1 if len(given) == 1 else sum(given)
    if surname_len == 1 and len(given) == 1:
        wai = 2
    elif surname_len == 1:
        wai = 1 + given[-1]
    elif len(given) == 1:
        wai = surname[0] + 1
    else:
        wai = surname[0] + given[-1]
    zong = sum(strokes)

    def item(label, raw):
        return {"label": label, "raw": raw, "number": _normalize_81(raw)}

    return {
        "available": True,
        "strokes": strokes,
        "surname_len": surname_len,
        "tian": item("天格", tian),
        "ren": item("人格", ren),
        "di": item("地格", di),
        "wai": item("外格", wai),
        "zong": item("总格", zong),
        "note": "按单姓/复姓通行「五格」算法（单姓天格 = 姓笔画 + 1、单名地格 = 名笔画 + 1 等假成数）；"
                "81 数理只做结构呈现，不评吉凶。",
    }


def _name_result_entry(label, total, chain, extra=None):
    """姓名数字条目：结果 + 归约链 + 关键词。"""
    number, chain = chain
    if number not in NUMBER_MEANINGS:
        # 例：只有辅音为 0 的名字（"A" 的人格数），无对应数字学含义
        entry = {
            "label": label,
            "number": number,
            "is_master": False,
            "root": None,
            "chain": list(chain),
            "total": total,
            "keywords": [],
            "title": "%s（无有效数字）" % label,
            "summary": "",
            "note": "该分项求和为 %d，没有对应的数字学结果。" % total,
        }
        if extra:
            entry.update(extra)
        return entry
    entry = {
        "label": label,
        "number": number,
        "is_master": _is_master(number),
        "root": NUMBER_MEANINGS[number]["root"],
        "chain": list(chain),
        "total": total,
        "keywords": _keywords(number),
        "title": NUMBER_MEANINGS[number]["title"],
        "summary": NUMBER_MEANINGS[number]["summary"],
    }
    if extra:
        entry.update(extra)
    return entry


def _name_analysis(name, strokes=None, surname_len=1):
    """姓名分析：拉丁名做表达/灵魂/人格数；中文名只做（外部笔画的）五格或降级说明。"""
    base = {
        "available": False,
        "provided": False,
        "name": None,
        "name_supported": None,
        "script": None,
        "note": "",
        "strokes": None,
        "letters": [],
        "expression": None,
        "soul_urge": None,
        "personality": None,
        "five_grid": None,
    }
    if name is None:
        base["note"] = "未提供姓名；生命灵数等基础项不依赖姓名，成熟数不可算。"
        return base
    if not isinstance(name, str):
        raise TypeError("name 必须是字符串：%r" % (name,))
    raw = name.strip()
    if not raw:
        base["note"] = "姓名为空字符串，按未提供处理；成熟数不可算。"
        return base
    base["provided"] = True
    base["name"] = raw

    has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in raw)
    letters = [ch for ch in raw if ch.isalpha()]
    ascii_letters = all(ord(ch) < 128 for ch in letters) and bool(letters)
    allowed_punct = set(" -'.")
    junk = [ch for ch in raw if not (ch.isalpha() or ch in allowed_punct or
                                     "\u4e00" <= ch <= "\u9fff")]

    if has_cjk:
        return _chinese_name_analysis(base, raw, strokes, surname_len)
    if not ascii_letters:
        base["script"] = "other"
        base["name_supported"] = False
        base["note"] = ("姓名中缺少可映射的拉丁字母（本模块按 A=1…Z=26 计算），"
                        "也未提供中文笔画数据；请提供拉丁字母名或 strokes 笔画。")
        return base
    if junk:
        base["script"] = "mixed"
        base["name_supported"] = False
        base["note"] = ("姓名含无法映射的字符 %r：拉丁字母名只允许字母、空格、连字符、"
                        "撇号、句点；中文名需外部笔画。" % ("".join(junk),))
        return base
    return _latin_name_analysis(base, raw)


def _latin_name_analysis(base, raw):
    """拉丁字母名：A=1…Z=26 求和归约，得到表达/灵魂/人格数。"""
    letters = [ch.upper() for ch in raw if ch.isalpha()]
    values = [LATIN_VALUES[ch] for ch in letters]
    total = sum(values)
    has_std_vowel = any(ch in STD_VOWELS for ch in letters)
    vowels = [ch for ch in letters if ch in STD_VOWELS or (ch == "Y" and not has_std_vowel)]
    consonants = [ch for ch in letters if ch not in vowels]
    vowel_sum = sum(LATIN_VALUES[ch] for ch in vowels)
    consonant_sum = sum(LATIN_VALUES[ch] for ch in consonants)

    base.update({
        "available": True,
        "name_supported": True,
        "script": "latin",
        "letters": [{"char": ch, "value": v} for ch, v in zip(letters, values)],
        "total": total,
        "expression": _name_result_entry(
            "表达数", total, _reduce_chain(total),
            {"vowel_rule": "Y 仅在无 A/E/I/O/U 时按元音处理"}),
        "soul_urge": _name_result_entry(
            "灵魂数", vowel_sum, _reduce_chain(vowel_sum),
            {"letters": "".join(vowels), "vowels": list(vowels)}),
        "personality": _name_result_entry(
            "人格数", consonant_sum, _reduce_chain(consonant_sum),
            {"letters": "".join(consonants), "consonants": list(consonants)}),
        "vowels_used": list(vowels),
        "consonants_used": list(consonants),
        "note": "拉丁字母按 A=1…Z=26 求和归约（任务约定，非毕氏字母表）；"
                "空格、连字符、撇号、句点不计。",
    })
    return base


def _chinese_name_analysis(base, raw, strokes, surname_len):
    """中文姓名：无笔画表则降级；有外部笔画则算五格。"""
    chars = [ch for ch in raw if "\u4e00" <= ch <= "\u9fff"]
    base["script"] = "chinese"
    base["chars"] = chars
    if len(chars) != len([ch for ch in raw if ch.isalpha()]):
        base["name_supported"] = False
        base["note"] = "中文姓名中混入非汉字字符，暂不支持；请只传汉字姓名。"
        return base
    if strokes is None:
        base["name_supported"] = False
        base["note"] = ("中文姓名需要外部笔画表：本模块不内置汉字笔画。"
                        "可通过 numerology(report, name=..., strokes=[每字笔画数]) "
                        "或 CLI 的 --strokes 传入；否则只计算不含姓名的数字学项目。")
        return base
    try:
        parsed = _parse_strokes(strokes)
        if len(parsed) != len(chars):
            raise ValueError("笔画数 %d 个与汉字数 %d 个不一致"
                             % (len(parsed), len(chars)))
        five = _five_grid(parsed, surname_len)
    except ValueError as exc:
        base["name_supported"] = False
        base["note"] = "笔画数据无效，无法计算五格：%s" % exc
        return base
    base.update({
        "available": True,
        "name_supported": True,
        "strokes": parsed,
        "five_grid": five,
        "note": "中文姓名按外部笔画数据计算「五格」（天格/人格/地格/外格/总格）；"
                "本模块不内置汉字笔画表，笔画准确性取决于调用方数据。",
    })
    return base


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------


def _number_brief(entry):
    """「6（责任与关爱）」这类短句。"""
    tag = "主数" if entry.get("is_master") else "常规数"
    return "%d（%s，%s）" % (entry["number"], tag, entry.get("title", ""))


def _summary_lines(life_path, birthday, attitude, maturity, personal, grid, name):
    lines = []
    lines.append("生命灵数 %s：%s" % (_number_brief(life_path),
                                     "、".join(life_path["keywords"])))
    lines.append("生日数 %s；态度数 %s。" % (
        _number_brief(birthday), _number_brief(attitude)))
    if maturity.get("available"):
        lines.append("成熟数 %s：%s" % (
            _number_brief(maturity), "、".join(maturity["keywords"])))
    else:
        lines.append("成熟数：不可算（需可计算的姓名，例如拉丁字母名）。")
    lines.append("个人周期（聚焦 %d，参考 %s）：个人年 %d、个人月 %d、个人日 %d。"
                 % (personal["focus_year"], personal["reference_date"],
                    personal["year"], personal["month"], personal["day"]))
    lines.append("九宫格：缺失 %s；重复 %s；成线 %d/%d。" % (
        "、".join(str(n) for n in grid["missing"]) or "无",
        "、".join("%d×%d" % (r["number"], r["count"]) for r in grid["repeats"]) or "无",
        grid["formed_count"], grid["total_lines"]))
    if name.get("provided"):
        if name.get("available"):
            how = "按拉丁字母计算" if name.get("script") == "latin" else "按外部笔画五格计算"
            lines.append("姓名：%s（%s）。" % (name["name"], how))
        else:
            lines.append("姓名：%s（name_supported = false，见 name.note）。" % name["name"])
    else:
        lines.append("姓名：未提供（基础项不依赖姓名）。")
    lines.append("以上数字只作性格与周期叙事参考；数字学属现代民俗/流行心理学，无学术预测效度。")
    return lines


# ---------------------------------------------------------------------------
# 对外主函数
# ---------------------------------------------------------------------------


def numerology(report, name=None, strokes=None, surname_len=1, as_of=None):
    """数字学主计算。

    参数
    ----
    report : dict
        ``bazi.build_report()`` 的返回值；读取 input / time / focus_year。
    name : str | None
        姓名。缺省时回退 ``report["input"]["name"]``。
    strokes : list[int] | str | None
        中文姓名的每个汉字笔画数（如 ``[7, 6]`` 或 ``"7,6"``）；拉丁名不需要。
    surname_len : int
        复姓传 2，默认单姓 1。
    as_of : date | str | None
        个人月/日的参考日期，默认今天。

    返回可 JSON 序列化的 dict（结构见模块 docstring 与 README）。
    """
    ctx = _input_context(report, as_of=as_of)
    inp = report.get("input") if isinstance(report.get("input"), dict) else {}

    if name is None:
        name = inp.get("name") if isinstance(inp.get("name"), str) else report.get("name")
    if strokes is None:
        strokes = inp.get("strokes")
        if strokes is None:
            strokes = report.get("name_strokes")

    life_path = _life_path(ctx["birth_date"])
    birthday = _birthday_number(ctx["birth_date"])
    attitude = _attitude_number(ctx["birth_date"])
    name_data = _name_analysis(name, strokes=strokes, surname_len=surname_len)
    expression = name_data.get("expression") if name_data.get("available") else None
    maturity = _maturity_number(life_path, expression)
    personal = _personal_numbers(ctx["birth_date"], ctx["focus_year"],
                                 ctx["reference_date"])
    grid = _grid_from_date(ctx["birth_date"])

    input_block = {
        "birth_date": ctx["birth_date"].isoformat(),
        "birth_time": ctx["birth_time"],
        "used_time": ctx["used_time"],
        "time_label": ctx["time_label"],
        "used_kind": ctx["used_kind"],
        "date_source": ctx["date_source"],
        "civil_date": ctx["civil_date"].isoformat() if ctx["civil_date"] else None,
        "civil_time": ctx["civil_time"],
        "date_note": ctx["date_note"],
        "focus_year": ctx["focus_year"],
        "reference_date": ctx["reference_date"].isoformat(),
        "name": name if isinstance(name, str) and name.strip() else None,
        "sex": ctx["sex"],
        "zone": ctx["zone"],
        "calendar": "公历（Gregorian）",
        "time_scale": "与八字排盘一致：优先 report[\"time\"][\"used\"]"
                      "（标准时/真太阳时）",
    }

    summary = _summary_lines(life_path, birthday, attitude, maturity, personal,
                             grid, name_data)

    return {
        "version": VERSION,
        "method": MODEL,
        "input": input_block,
        "life_path": life_path,
        "birthday": birthday,
        "attitude": attitude,
        "maturity": maturity,
        "personal": personal,
        "grid": grid,
        "name": name_data,
        "summary": summary,
        "limits": list(LIMITS),
    }


# ---------------------------------------------------------------------------
# 文本渲染
# ---------------------------------------------------------------------------


def _render_grid(grid):
    """把九宫格渲染成等距三行（缺数标「缺」）。"""
    lines = []
    cells = {c["number"]: c for c in grid["cells"]}
    for row in grid["layout"]:
        parts = []
        for n in row:
            count = cells[n]["count"]
            parts.append(("%d×%d" % (n, count)) if count else ("%d缺" % n))
        lines.append("    " + "    ".join(parts))
    return lines


def render_numerology_text(data):
    """把 ``numerology()`` 的结果渲染成中文文本。"""
    if not isinstance(data, dict):
        raise TypeError("render_numerology_text 需要 numerology() 返回的 dict")
    lines = []
    lines.append("══════════════ 数字学（Numerology）·毕达哥拉斯体系 ══════════════")
    inp = data.get("input") or {}
    lines.append("出生（排盘口径）：%s %s　%s" % (
        inp.get("birth_date", ""), inp.get("birth_time", ""),
        inp.get("time_label") or ""))
    lines.append("聚焦年：%s　参考日期：%s　历法：%s" % (
        inp.get("focus_year", ""), inp.get("reference_date", ""),
        inp.get("calendar", "")))
    if inp.get("date_note"):
        lines.append("注：" + inp["date_note"])
    lines.append("")

    lp = data["life_path"]
    lines.append("【生命灵数 Life Path】%d%s" % (
        lp["number"], "（主数，不归约）" if lp["is_master"] else "（常规数）"))
    lines.append("  归约链：" + _chain_text(lp["chain"]) + "（逐位求和 %d）" % lp["raw_sum"])
    lines.append("  关键词：" + "、".join(lp["keywords"]))
    lines.append("  解读：" + lp["summary"])
    lines.append("")

    bd = data["birthday"]
    lines.append("【生日数 Birthday】%d%s" % (
        bd["number"], "（主数）" if bd["is_master"] else ""))
    lines.append("  归约链：" + _chain_text(bd["chain"]) + "（出生日 %d）" % bd["day"])
    lines.append("  关键词：" + "、".join(bd["keywords"]))
    lines.append("")

    at = data["attitude"]
    lines.append("【态度数 Attitude】%d%s" % (
        at["number"], "（主数）" if at["is_master"] else ""))
    lines.append("  归约链：" + _chain_text(at["chain"]) + "（月 + 日 = %d）" % at["raw_sum"])
    lines.append("  关键词：" + "、".join(at["keywords"]))
    lines.append("")

    mt = data.get("maturity") or {}
    if mt.get("available"):
        lines.append("【成熟数 Maturity】%d%s" % (
            mt["number"], "（主数）" if mt["is_master"] else ""))
        lines.append("  归约链：" + _chain_text(mt["chain"]))
        lines.append("  关键词：" + "、".join(mt["keywords"]))
    else:
        lines.append("【成熟数 Maturity】不可算")
        lines.append("  " + (mt.get("note") or "需要可计算的姓名。"))
    lines.append("")

    ps = data["personal"]
    lines.append("【个人周期 Personal Year/Month/Day】")
    lines.append("  个人年 %d%s　个人月 %d%s　个人日 %d%s" % (
        ps["year"], "（主数）" if ps.get("year_is_master") else "",
        ps["month"], "（主数）" if ps.get("month_is_master") else "",
        ps["day"], "（主数）" if ps.get("day_is_master") else ""))
    lines.append("  聚焦年 %d　参考日期 %s" % (ps["focus_year"], ps["reference_date"]))
    lines.append("  " + (ps.get("note") or ""))
    lines.append("")

    grid = data["grid"]
    lines.append("【九宫格 Lo Shu】布局（数字×出现次数，缺数标「缺」）：")
    lines.extend(_render_grid(grid))
    lines.append("  缺失数字：" + ("、".join(str(n) for n in grid["missing"]) or "无"))
    lines.append("  重复数字：" + ("、".join(
        "%d（%d 次）" % (r["number"], r["count"]) for r in grid["repeats"]) or "无"))
    formed = [ln for ln in grid["lines"] if ln["formed"]]
    if formed:
        lines.append("  成线（%d/%d）：" % (grid["formed_count"], grid["total_lines"]))
        for ln in formed:
            lines.append("    · %s（%s·%s）：%s" % (
                ln["name"], ln["type"], ln["position"], ln["meaning"]))
    else:
        lines.append("  成线（0/%d）：无" % grid["total_lines"])
    lines.append("")

    nm = data.get("name") or {}
    lines.append("【姓名分析】")
    if not nm.get("provided"):
        lines.append("  未提供姓名；生命灵数等基础项不依赖姓名，成熟数不可算。")
    elif nm.get("script") == "latin" and nm.get("available"):
        lines.append("  %s（拉丁字母 A=1…Z=26，共 %d）" % (nm["name"], nm["total"]))
        for key, label in (("expression", "表达数"), ("soul_urge", "灵魂数"),
                           ("personality", "人格数")):
            entry = nm[key]
            extra = ""
            if key == "soul_urge":
                extra = "，元音 %s" % ("".join(nm.get("vowels_used") or []))
            if key == "personality":
                extra = "，辅音 %s" % ("".join(nm.get("consonants_used") or []))
            lines.append("  %s %d（%s%s）：归约 %s；关键词 %s" % (
                label, entry["number"], entry["title"], extra,
                _chain_text(entry["chain"]), "、".join(entry["keywords"])))
        lines.append("  注：" + nm["note"])
    elif nm.get("available") and nm.get("five_grid"):
        five = nm["five_grid"]
        lines.append("  %s（中文，外部笔画 %s）" % (
            nm["name"], "、".join(str(x) for x in nm["strokes"])))
        for key, label in (("tian", "天格"), ("ren", "人格"), ("di", "地格"),
                           ("wai", "外格"), ("zong", "总格")):
            item = five[key]
            lines.append("  %s：%d（数理 %d）" % (label, item["raw"], item["number"]))
        lines.append("  注：" + five["note"])
    else:
        lines.append("  %s：name_supported = false" % nm.get("name", ""))
        lines.append("  " + (nm.get("note") or ""))
    lines.append("")

    lines.append("【小结】")
    for item in data.get("summary") or []:
        lines.append("  · " + item)
    lines.append("")
    lines.append("【方法学与免责】")
    lines.append("  " + (data.get("method") or MODEL))
    for item in data.get("limits") or LIMITS:
        lines.append("  · " + item)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 独立校验 CLI（完整 CLI 由 bazi.py 接入）
# ---------------------------------------------------------------------------


def _build_cli_report(args, birth_date, birth_time):
    """把 CLI 参数拼成一个最小 report（字段形状与 bazi.build_report 一致）。"""
    used_dt = datetime.datetime.combine(birth_date, birth_time)
    used_label = "标准时"
    use_convert = (args.zone != "Asia/Shanghai" or args.longitude is not None
                   or args.true_solar_time)
    if use_convert:
        try:
            import bazi  # 延迟导入：避免与 bazi.py 的集成互相循环
        except Exception as exc:  # pragma: no cover - bazi.py 一定存在
            raise SystemExit("无法导入 bazi.py 做时间换算：%s" % exc)
        try:
            converted = bazi.resolve_time(
                birth_date.year, birth_date.month, birth_date.day,
                birth_time.hour, birth_time.minute, birth_time.second,
                args.zone, args.longitude, args.true_solar_time)
        except SystemExit as exc:  # argparse 风格错误信息
            raise SystemExit(str(exc))
        used_dt = converted["used_dt"]
        used_label = converted["used_label"]
    return {
        "input": {
            "date": birth_date.isoformat(),
            "time": birth_time.strftime("%H:%M:%S"),
            "time_unknown": False,
            "sex": args.sex,
            "zone": args.zone,
            "longitude": args.longitude,
            "true_solar_time": bool(args.true_solar_time),
            "name": args.name,
        },
        "time": {
            "civil": datetime.datetime.combine(birth_date, birth_time).strftime(
                "%Y-%m-%d %H:%M:%S"),
            "used": used_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "used_label": used_label,
            "used_kind": "tst" if args.true_solar_time else "standard",
            "zone": args.zone,
        },
        "focus_year": args.focus_year or datetime.date.today().year,
    }


def main(argv=None):
    """独立校验 CLI：``python scripts/numerology.py --date 2004-06-12 ...``。"""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        prog="numerology.py",
        description="数字学（毕达哥拉斯体系）独立校验 CLI；完整 CLI 由 bazi.py 接入。")
    parser.add_argument("--date", required=True, help="出生公历日期 YYYY-MM-DD")
    parser.add_argument("--time", default="12:00:00", help="出生时间 HH:MM 或 HH:MM:SS")
    parser.add_argument("--sex", default=None, help="male/female（仅回填，不影响数字）")
    parser.add_argument("--name", default=None, help="姓名：拉丁字母名或中文名（配 --strokes）")
    parser.add_argument("--strokes", default=None,
                        help="中文姓名笔画，如 \"7,6\"；需与汉字数一致")
    parser.add_argument("--surname-len", type=int, default=1, help="复姓传 2，默认单姓 1")
    parser.add_argument("--focus-year", type=int, default=None, help="聚焦年（个人周期）")
    parser.add_argument("--as-of", default=None, help="个人月/日的参考日期 YYYY-MM-DD")
    parser.add_argument("--zone", default="Asia/Shanghai", help="IANA 时区（默认 Asia/Shanghai）")
    parser.add_argument("--longitude", type=float, default=None,
                        help="出生地经度（配合 --true-solar-time）")
    parser.add_argument("--true-solar-time", action="store_true", help="按真太阳时换算")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    try:
        birth_date = datetime.date.fromisoformat(args.date)
    except ValueError:
        parser.error("--date 格式应为 YYYY-MM-DD，例如 2004-06-12")
    try:
        birth_time = datetime.time.fromisoformat(args.time)
    except ValueError:
        parser.error("--time 格式应为 HH:MM 或 HH:MM:SS，例如 10:00")
    try:
        report = _build_cli_report(args, birth_date, birth_time)
        data = numerology(report, strokes=args.strokes,
                          surname_len=args.surname_len, as_of=args.as_of)
    except (ValueError, TypeError) as exc:
        parser.error(str(exc))

    sys.stdout.reconfigure(encoding="utf-8")
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(render_numerology_text(data))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
