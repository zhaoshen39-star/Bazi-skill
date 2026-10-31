# -*- coding: utf-8 -*-
"""奇门遁甲（时家转盘）层。

设计原则
--------
- 纯标准库、不联网、不重算历法。四柱、节气、真太阳时等历法事实全部取自
  ``bazi.build_report()`` 的 ``report["chart"]``，本模块只做「定局 + 排盘」。
- 只在有 ``pillars`` 的前提下工作；缺字段时给出明确异常或降级并写入 ``limits``。
- 输出是「结构描述」，不做吉凶断言，不给用神、不判格局高低。
- 流派选择全部落在 ``limits`` 里，便于上层引用时不越界。

对外接口
--------
``chart_qimen(report) -> dict``
    输入 ``bazi.build_report()`` 的返回值（或直接传它的 ``chart`` 子 dict），
    返回九宫盘、定局、值符值使、旬空马星、summary/limits 等字段。

``render_qimen_text(data) -> str``
    把 ``chart_qimen()`` 的结果渲染成等宽中文文本，风格与 ``render_ziwei_text`` 一致。

输出 dict 主要字段
------------------
``version`` / ``method`` / ``note`` / ``school``
    版本、算法长说明、免责声明、流派开关快照。
``pillars`` / ``pillars_text``
    四柱（含 gan/zhi/ganzhi/index）。
``jieqi``
    当前节气（取自 report 的 ``prev_qi``，即交节后的当前二十四节气）、
    该节气在冬至序里的下标、下一节气。
``yuan``
    拆补法三元：``index`` 0/1/2、``name`` 上元/中元/下元、``fu_tou`` 符头日。
``dun`` / ``ju``
    阴阳遁（``is_yang``）、局数 1..9、``label`` 如 ``阴遁二局``。
``xun`` / ``zhifu`` / ``zhishi``
    时柱旬首、旬空；值符星及其本宫/落宫；值使门及其本宫/落宫。
``palaces``
    9 个宫 dict，按宫数 1..9 排列，每宫含宫名/卦/方位/地盘干/天盘干/九星/
    八门/八神/旬空/马星/是否中宫，以及中五寄坤二带来的 ``*_ji`` 附加字段。
``sanqi_liuyi``
    三奇六仪（地盘/天盘）分布与各自的干支列表。
``kong`` / ``ma``
    旬空支与旬空宫、驿马支与驿马宫。
``summary`` / ``limits``
    纯事实要点与流派/局限说明。
"""

import unicodedata

VERSION = "v1"

METHOD = (
    "时家转盘奇门：拆补法定局（二十四节气三元局数表 + 日柱符头定上中下元），"
    "冬至后阳遁、夏至后阴遁；地盘三奇六仪按宫数阳顺阴逆、戊起局数宫；"
    "天盘九星「值符随时干」整体转盘、中五寄坤二且天禽随天芮；"
    "八门「值使随时支」整体转盘；八神自值符所在宫起、阳顺阴逆；"
    "旬空取时柱旬空、驿马取时支三合。"
)

NOTE = (
    "奇门遁甲流派众多（拆补/置闰/均分/茅山，转盘/飞盘，中五寄坤二/寄艮八，"
    "八神用白虎玄武/勾陈朱雀等），本模块只实现上文所述的一种，且只描述结构、"
    "不作吉凶判断，不构成任何决策依据。"
)


# ---------------------------------------------------------------------------
# 基础常量
# ---------------------------------------------------------------------------

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"

# 二十四节气，以冬至为 0，与三元局数表同序；0..11 阳遁，12..23 阴遁。
JIEQI_ORDER = (
    "冬至", "小寒", "大寒", "立春", "雨水", "惊蛰",
    "春分", "清明", "谷雨", "立夏", "小满", "芒种",
    "夏至", "小暑", "大暑", "立秋", "处暑", "白露",
    "秋分", "寒露", "霜降", "立冬", "小雪", "大雪",
)

# 每一节气的（上元, 中元, 下元）局数，教科书三元局数表。
SAN_YUAN_JU = (
    (1, 7, 4), (2, 8, 5), (3, 9, 6), (8, 5, 2),
    (9, 6, 3), (1, 7, 4), (3, 9, 6), (4, 1, 7),
    (5, 2, 8), (4, 1, 7), (5, 2, 8), (6, 3, 9),
    (9, 3, 6), (8, 2, 5), (7, 1, 4), (2, 5, 8),
    (1, 4, 7), (9, 3, 6), (7, 1, 4), (6, 9, 3),
    (5, 8, 2), (6, 9, 3), (5, 8, 2), (4, 7, 1),
)

YUAN_NAMES = ("上元", "中元", "下元")

# 地盘三奇六仪的固定次序：六仪顺布、三奇逆布（乙丙丁 ⇒ 丁丙乙）。
STEM_ORDER = "戊己庚辛壬癸丁丙乙"

# 六甲的六仪：甲子戊、甲戌己、甲申庚、甲午辛、甲辰壬、甲寅癸。
XUN_YI = ("戊", "己", "庚", "辛", "壬", "癸")

# 八神（本模块统一用白虎/玄武，不区分阳遁的勾陈/朱雀）。
GOD_ORDER = ("值符", "腾蛇", "太阴", "六合", "白虎", "玄武", "九地", "九天")

# 九星、八门的本宫（按宫数 1..9；中五无门）。
STAR_BY_GONG = {
    1: "天蓬", 2: "天芮", 3: "天冲", 4: "天辅", 5: "天禽",
    6: "天心", 7: "天柱", 8: "天任", 9: "天英",
}
DOOR_BY_GONG = {
    1: "休门", 2: "死门", 3: "伤门", 4: "杜门",
    6: "开门", 7: "惊门", 8: "生门", 9: "景门",
}

GONG_NAME = {
    1: "坎一宫", 2: "坤二宫", 3: "震三宫", 4: "巽四宫", 5: "中五宫",
    6: "乾六宫", 7: "兑七宫", 8: "艮八宫", 9: "离九宫",
}
GONG_GUA = {1: "坎", 2: "坤", 3: "震", 4: "巽", 5: "中", 6: "乾", 7: "兑", 8: "艮", 9: "离"}
GONG_DIR = {
    1: "北", 2: "西南", 3: "东", 4: "东南", 5: "中",
    6: "西北", 7: "西", 8: "东北", 9: "南",
}

# 后天八卦环宫序（转盘用，顺时针）。中五不参与环：
# 巽四 → 离九 → 坤二 → 兑七 → 乾六 → 坎一 → 艮八 → 震三。
RING = (4, 9, 2, 7, 6, 1, 8, 3)
RING_POS = {g: i for i, g in enumerate(RING)}

# 中五寄坤二，落宫修正统一走这里。
JI_GONG = 2

# 地支所居之宫（四正宫各居一支，四维宫各居二支）。
ZHI_GONG = {
    "子": 1, "丑": 8, "寅": 8, "卯": 3, "辰": 4, "巳": 4,
    "午": 9, "未": 2, "申": 2, "酉": 7, "戌": 6, "亥": 6,
}

# 时支三合驿马。
YIMA = {
    "申": "寅", "子": "寅", "辰": "寅",
    "寅": "申", "午": "申", "戌": "申",
    "巳": "亥", "酉": "亥", "丑": "亥",
    "亥": "巳", "卯": "巳", "未": "巳",
}

# 九宫排版（洛书方位：上南下北），供文本渲染使用。
GRID = ((4, 9, 2), (3, 5, 7), (8, 1, 6))


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def _ganzhi_index(gan, zhi):
    """干支 → 六十甲子序号 0..59；无法识别返回 None。"""
    if not gan or not zhi or gan not in GAN or zhi not in ZHI:
        return None
    g = GAN.index(gan)
    z = ZHI.index(zhi)
    for i in range(60):
        if i % 10 == g and i % 12 == z:
            return i
    return None


def _pillar_index(pillar):
    """从单柱 dict 求六十甲子序号（兼容 gan/zhi、ganzhi、index 三种写法）。"""
    if not isinstance(pillar, dict):
        return None
    idx = pillar.get("index")
    if isinstance(idx, int) and 0 <= idx < 60:
        return idx
    got = _ganzhi_index(pillar.get("gan"), pillar.get("zhi"))
    if got is not None:
        return got
    ganzhi = pillar.get("ganzhi")
    if isinstance(ganzhi, str) and len(ganzhi) >= 2:
        return _ganzhi_index(ganzhi[0], ganzhi[1])
    return None


def _ring_index(gong):
    """宫数 → 环宫序号；中五按寄坤二折算。"""
    if gong == 5:
        gong = JI_GONG
    return RING_POS.get(gong)


def _ji_gong(gong):
    """中五寄坤二：把宫数折算到参与转盘的八宫之一。"""
    return JI_GONG if gong == 5 else gong


def _time_text(value):
    """取 report["time"] 里的时间字符串，缺失时返回空串。"""
    if isinstance(value, str):
        return value
    return ""


def _term_index(name):
    """节气名 → 冬至序下标 0..23；认不出返回 None。"""
    if not isinstance(name, str):
        return None
    name = name.strip()
    if name in JIEQI_ORDER:
        return JIEQI_ORDER.index(name)
    # 兼容「霜降（气）」之类带后缀的写法
    head = name[:2]
    if head in JIEQI_ORDER:
        return JIEQI_ORDER.index(head)
    return None


def _earth_plate(ju, is_yang):
    """地盘三奇六仪：戊起局数宫，阳遁宫数顺行、阴遁宫数逆行（含中五）。"""
    plate = {}
    for k, stem in enumerate(STEM_ORDER):
        if is_yang:
            gong = (ju - 1 + k) % 9 + 1
        else:
            gong = (ju - 1 - k) % 9 + 1
        plate[gong] = stem
    return plate


def _xun_info(hour_index):
    """时柱 → 旬首、六仪、旬空。"""
    if hour_index is None:
        return {}
    xun = hour_index // 10
    head_index = xun * 10
    head_zhi = head_index % 12
    return {
        "index": xun,
        "head": "甲" + ZHI[head_zhi],
        "head_zhi": head_zhi,
        "yi": XUN_YI[xun],
        "kong": [ZHI[(head_zhi + 10) % 12], ZHI[(head_zhi + 11) % 12]],
    }


def _yuan_of(day_index):
    """拆补法三元：以符头日（甲/己）为界，五日一元。

    等价于 ``(day_index // 5) % 3``；符头支属子午卯酉为上元、
    寅申巳亥为中元、辰戌丑未为下元。
    """
    if day_index is None:
        return None, None, None
    offset = day_index % 5
    head = day_index - offset
    yuan = (day_index // 5) % 3
    return yuan, YUAN_NAMES[yuan], GAN[head % 10] + ZHI[head % 12]


# ---------------------------------------------------------------------------
# 排盘
# ---------------------------------------------------------------------------

def _palaces(earth, stars, doors, gods, kong_gong, ma_gong):
    """把各盘拼成 9 个宫 dict。"""
    out = []
    for gong in range(1, 10):
        star, star_ji = stars.get(gong, ("", ""))
        door = doors.get(gong, "")
        god = gods.get(gong, "")
        heaven, heaven_ji = earth["heaven"].get(gong, ("", ""))
        out.append({
            "gong": gong,
            "name": GONG_NAME[gong],
            "gua": GONG_GUA[gong],
            "direction": GONG_DIR[gong],
            "is_center": gong == 5,
            "earth_stem": earth["earth"].get(gong, ""),
            "heaven_stem": heaven,
            "heaven_stem_ji": heaven_ji,
            "star": star,
            "star_ji": star_ji,
            "door": door,
            "deity": god,
            "is_kong": gong in kong_gong,
            "is_ma": gong == ma_gong,
        })
    return out


def chart_qimen(report):
    """排时家转盘奇门盘。

    ``report`` 为 ``bazi.build_report()`` 的返回值，或其 ``chart`` 子 dict。
    """
    if not isinstance(report, dict):
        raise TypeError("chart_qimen 需要 bazi.build_report() 返回的 dict")
    chart = report.get("chart") if "chart" in report else report
    if not isinstance(chart, dict):
        raise ValueError("report 缺少 chart（排盘结果），无法起奇门局")
    pillars = chart.get("pillars")
    if not isinstance(pillars, (list, tuple)) or len(pillars) < 4:
        raise ValueError("report 缺少 chart['pillars']（四柱），无法起奇门局")

    limits = []

    # ---- 四柱 -------------------------------------------------------------
    pillar_rows = []
    indexes = []
    for i, pillar in enumerate(list(pillars)[:4]):
        name = pillar.get("name") if isinstance(pillar, dict) else None
        row = {
            "name": name or ("年柱", "月柱", "日柱", "时柱")[i],
            "ganzhi": _time_text(pillar.get("ganzhi")) if isinstance(pillar, dict) else "",
            "gan": _time_text(pillar.get("gan")) if isinstance(pillar, dict) else "",
            "zhi": _time_text(pillar.get("zhi")) if isinstance(pillar, dict) else "",
            "index": _pillar_index(pillar),
        }
        if not row["ganzhi"] and row["gan"] and row["zhi"]:
            row["ganzhi"] = row["gan"] + row["zhi"]
        pillar_rows.append(row)
        indexes.append(row["index"])

    day_index, hour_index = indexes[2], indexes[3]
    if day_index is None or hour_index is None:
        raise ValueError("四柱缺少可识别的干支，无法起奇门局")

    hour_gan = pillar_rows[3]["gan"] or pillar_rows[3]["ganzhi"][:1]
    hour_zhi = pillar_rows[3]["zhi"] or pillar_rows[3]["ganzhi"][1:2]
    day_gan = pillar_rows[2]["gan"] or pillar_rows[2]["ganzhi"][:1]
    day_zhi = pillar_rows[2]["zhi"] or pillar_rows[2]["ganzhi"][1:2]
    # 只给了六十甲子序号（没有 gan/zhi/ganzhi）时，从序号还原干支。
    if not hour_gan:
        hour_gan = GAN[hour_index % 10]
        pillar_rows[3]["gan"] = hour_gan
    if not hour_zhi:
        hour_zhi = ZHI[hour_index % 12]
        pillar_rows[3]["zhi"] = hour_zhi
    if not pillar_rows[3]["ganzhi"]:
        pillar_rows[3]["ganzhi"] = hour_gan + hour_zhi
    if not day_gan:
        day_gan = GAN[day_index % 10]
        pillar_rows[2]["gan"] = day_gan
    if not day_zhi:
        day_zhi = ZHI[day_index % 12]
        pillar_rows[2]["zhi"] = day_zhi
    if not pillar_rows[2]["ganzhi"]:
        pillar_rows[2]["ganzhi"] = day_gan + day_zhi

    # ---- 节气 / 三元 / 阴阳遁 / 局数 --------------------------------------
    jieqi_block = chart.get("jieqi") if isinstance(chart.get("jieqi"), dict) else {}
    prev_qi = jieqi_block.get("prev_qi") if isinstance(jieqi_block.get("prev_qi"), dict) else {}
    term_name = prev_qi.get("name")
    term_index = _term_index(term_name)

    yuan_index, yuan_name, fu_tou = _yuan_of(day_index)

    if term_index is None:
        is_yang = True
        ju = 1
        term_name = term_name if isinstance(term_name, str) else "未知"
        limits.append(
            "report 未提供可识别的当前节气（chart['jieqi']['prev_qi']），"
            "局数退回阳遁一局，仅保证结构完整，不可作为实际起局结果。"
        )
    else:
        is_yang = term_index < 12
        ju = SAN_YUAN_JU[term_index][yuan_index]

    dun_label = ("阳遁" if is_yang else "阴遁") + "%s局" % "一二三四五六七八九"[ju - 1]

    # ---- 地盘 -------------------------------------------------------------
    earth_map = _earth_plate(ju, is_yang)

    # ---- 旬首 / 六仪 -------------------------------------------------------
    xun = _xun_info(hour_index)
    xun_yi = xun["yi"]
    xun_yi_gong = next(g for g, s in earth_map.items() if s == xun_yi)

    # 时干所居：甲不现于地盘，以旬首六仪代之（六甲时天盘伏吟）。
    if hour_gan == "甲":
        hour_gan_gong = xun_yi_gong
        hour_gan_note = "时干为甲，依六甲遁仪以时旬首六仪「%s」代时干" % xun_yi
    else:
        found = [g for g, s in earth_map.items() if s == hour_gan]
        hour_gan_gong = found[0] if found else xun_yi_gong
        hour_gan_note = ""

    # ---- 值符（九星） ------------------------------------------------------
    zhifu_star = STAR_BY_GONG[xun_yi_gong]
    zhifu_home_gong = _ji_gong(xun_yi_gong)
    hour_gan_ring = _ring_index(_ji_gong(hour_gan_gong))
    zhifu_home_ring = _ring_index(zhifu_home_gong)
    star_shift = (zhifu_home_ring - hour_gan_ring) % 8

    star_map = {}      # 宫 -> (主星, 寄星)
    heaven_map = {}    # 宫 -> (天盘干, 寄天盘干)
    for gong in RING:
        home_ring = RING_POS[gong]
        dest_ring = (home_ring - star_shift) % 8
        dest_gong = RING[dest_ring]
        star_map[dest_gong] = (STAR_BY_GONG[gong], "")
        heaven_map[dest_gong] = (earth_map[gong], "")
    # 中五寄坤二：天禽与中宫地盘干随天芮飞。
    qin_ring = (RING_POS[JI_GONG] - star_shift) % 8
    qin_gong = RING[qin_ring]
    star_map[qin_gong] = (star_map[qin_gong][0], "天禽")
    heaven_map[qin_gong] = (heaven_map[qin_gong][0], earth_map[5])
    zhifu_land_gong = qin_gong if zhifu_star == "天禽" else next(
        g for g in RING if star_map[g][0] == zhifu_star
    )
    # 值符星落宫恒等于时干所居（中五寄坤二后）。
    if zhifu_land_gong != _ji_gong(hour_gan_gong):
        limits.append("值符落宫与「值符随时干」自检不一致，请复核输入四柱。")

    # ---- 值使（八门） ------------------------------------------------------
    zhishi_door = DOOR_BY_GONG[_ji_gong(xun_yi_gong)]
    zhishi_home_gong = _ji_gong(xun_yi_gong)
    offset_zhi = (ZHI.index(hour_zhi) - xun["head_zhi"]) % 12
    direction = 1 if is_yang else -1
    zhishi_gong = (xun_yi_gong - 1 + offset_zhi * direction) % 9 + 1
    zhishi_ring = _ring_index(_ji_gong(zhishi_gong))
    door_shift = (RING_POS[_ji_gong(zhishi_home_gong)] - zhishi_ring) % 8

    door_map = {}
    for gong in RING:
        home_ring = RING_POS[gong]
        dest_gong = RING[(home_ring - door_shift) % 8]
        door_map[dest_gong] = DOOR_BY_GONG[gong]

    # ---- 八神 -------------------------------------------------------------
    god_map = {}
    for k, god in enumerate(GOD_ORDER):
        dest_gong = RING[(hour_gan_ring + k * direction) % 8]
        god_map[dest_gong] = god

    # ---- 旬空 / 驿马 -------------------------------------------------------
    kong_zhi = list(xun.get("kong") or [])
    kong_gong = sorted({ZHI_GONG[z] for z in kong_zhi if z in ZHI_GONG})
    ma_zhi = YIMA.get(hour_zhi, "")
    ma_gong = ZHI_GONG.get(ma_zhi) if ma_zhi else None

    earth = {"earth": earth_map, "heaven": heaven_map}
    palaces = _palaces(earth, star_map, door_map, god_map, kong_gong, ma_gong)

    # ---- 三奇六仪分布 -----------------------------------------------------
    sanqi = "乙丙丁"
    liuyi = "戊己庚辛壬癸"
    earth_pos = {s: g for g, s in earth_map.items()}
    heaven_pos = {}
    for g in RING:
        main, ji = heaven_map.get(g, ("", ""))
        if main:
            heaven_pos[main] = g
        if ji:
            heaven_pos[ji] = g
    sanqi_liuyi = {
        "sanqi": list(sanqi),
        "liuyi": list(liuyi),
        "earth": {s: {"gong": earth_pos[s], "name": GONG_NAME[earth_pos[s]]} for s in sanqi + liuyi},
        "heaven": {s: {"gong": heaven_pos[s], "name": GONG_NAME[heaven_pos[s]]} for s in sanqi + liuyi},
        "zhong_gong_earth_stem": earth_map[5],
        "zhong_gong_ji_gong": qin_gong,
    }

    # ---- 文本与说明 --------------------------------------------------------
    time_block = report.get("time") if isinstance(report.get("time"), dict) else {}
    used_time = _time_text(time_block.get("used"))

    if chart.get("time_pillar_reliable") is False:
        limits.append("输入为时辰不明，四柱中的时柱为假定值，本盘只能视为结构示例。")

    limits.extend([
        "定局采用拆补法（符头三元 + 当前节气局数表），未采用置闰法、均分法、"
        "茅山法，也未处理「超神接气」的置闰修正。",
        "阴阳遁以冬至、夏至为界（冬至→芒种阳遁，夏至→大雪阴遁）。",
        "中五寄坤二：中宫地盘干不重复计入坤二地盘，但天禽与中宫地盘干随天芮飞至同宫，"
        "故该宫天盘出现两只干（heaven_stem / heaven_stem_ji）。",
        "九星、八门均为转盘整体旋转（按后天八卦环宫序），不做飞盘、不入中五。",
        "八神统一用「白虎/玄武」，未按阴遁改用「勾陈/朱雀」，也未使用太常、"
        "天符等九神体系。",
        "旬空取时柱旬空并按支宫折算；若按日柱旬空或按宫位飞布，结果会不同。",
        "驿马取时支三合驿马（申子辰马在寅、寅午戌马在申、巳酉丑马在亥、亥卯未马在巳）。",
        "节气取自 report 的当前节气（prev_qi），不处理交节瞬间的秒级边界；"
        "时柱以 report 的 time.used 为准，不另做真太阳时校正。",
        "只做结构描述：不给格局吉凶、不给用神、不给断语与应期。",
    ])

    summary = _summary(
        pillar_rows=pillar_rows,
        term_name=term_name,
        yuan_name=yuan_name,
        fu_tou=fu_tou,
        dun_label=dun_label,
        ju=ju,
        xun=xun,
        zhifu_star=zhifu_star,
        zhifu_home_gong=zhifu_home_gong,
        zhifu_land_gong=zhifu_land_gong,
        zhishi_door=zhishi_door,
        zhishi_home_gong=zhishi_home_gong,
        zhishi_gong=_ji_gong(zhishi_gong),
        offset_zhi=offset_zhi,
        is_yang=is_yang,
        earth_map=earth_map,
        star_map=star_map,
        door_map=door_map,
        god_map=god_map,
        kong_zhi=kong_zhi,
        kong_gong=kong_gong,
        ma_zhi=ma_zhi,
        ma_gong=ma_gong,
        hour_gan_note=hour_gan_note,
        used_time=used_time,
        qin_gong=qin_gong,
    )

    return {
        "version": VERSION,
        "method": METHOD,
        "note": NOTE,
        "school": {
            "定局": "拆补法",
            "体系": "时家转盘",
            "中五": "寄坤二，天禽随天芮",
            "八神": "白虎/玄武",
            "阴阳遁界": "冬至/夏至",
            "旬空": "时柱旬空",
            "驿马": "时支三合",
        },
        "pillars": pillar_rows,
        "pillars_text": " ".join(r["ganzhi"] for r in pillar_rows),
        "time": {
            "used": used_time,
            "utc": _time_text(time_block.get("utc")),
            "reliable": chart.get("time_pillar_reliable") is not False,
        },
        "jieqi": {
            "name": term_name,
            "index": term_index,
            "prev_jie": (jieqi_block.get("prev_jie") or {}).get("name") if isinstance(jieqi_block.get("prev_jie"), dict) else None,
            "next_jie": (jieqi_block.get("next_jie") or {}).get("name") if isinstance(jieqi_block.get("next_jie"), dict) else None,
        },
        "yuan": {
            "index": yuan_index,
            "name": yuan_name,
            "fu_tou": fu_tou,
            "day_index": day_index,
        },
        "dun": {
            "is_yang": is_yang,
            "yin_yang": "阳遁" if is_yang else "阴遁",
            "ju": ju,
            "label": dun_label,
        },
        "ju": ju,
        "xun": xun,
        "zhifu": {
            "xun_yi": xun_yi,
            "earth_gong": xun_yi_gong,
            "earth_gong_name": GONG_NAME[xun_yi_gong],
            "home_gong": zhifu_home_gong,
            "star": zhifu_star,
            "land_gong": zhifu_land_gong,
            "land_gong_name": GONG_NAME[zhifu_land_gong],
            "star_landed": zhifu_star,
        },
        "zhishi": {
            "door": zhishi_door,
            "home_gong": zhishi_home_gong,
            "gong": _ji_gong(zhishi_gong),
            "gong_name": GONG_NAME[_ji_gong(zhishi_gong)],
            "raw_gong": zhishi_gong,
            "zhi_offset": offset_zhi,
        },
        "hour": {
            "ganzhi": pillar_rows[3]["ganzhi"],
            "gan": hour_gan,
            "zhi": hour_zhi,
            "index": hour_index,
            "gan_gong": hour_gan_gong,
            "gan_gong_name": GONG_NAME[hour_gan_gong],
            "zhi_gong": ZHI_GONG.get(hour_zhi),
        },
        "day": {
            "ganzhi": pillar_rows[2]["ganzhi"],
            "gan": day_gan,
            "zhi": day_zhi,
            "index": day_index,
        },
        "kong": {"zhi": kong_zhi, "gong": kong_gong, "gong_names": [GONG_NAME[g] for g in kong_gong]},
        "ma": {"zhi": ma_zhi, "gong": ma_gong, "gong_name": GONG_NAME.get(ma_gong) if ma_gong else ""},
        "palaces": palaces,
        "sanqi_liuyi": sanqi_liuyi,
        "summary": summary,
        "limits": limits,
    }


def _summary(**kw):
    """生成纯事实要点。"""
    out = []
    out.append(
        "四柱 %s；日柱符头 %s，属%s；当前节气 %s。"
        % (
            " ".join(r["ganzhi"] for r in kw["pillar_rows"]),
            kw["fu_tou"] or "—",
            kw["yuan_name"] or "—",
            kw["term_name"] or "—",
        )
    )
    out.append("起局：%s（%s）。" % (kw["dun_label"], "阳遁顺行" if kw["is_yang"] else "阴遁逆行"))
    out.append(
        "时柱 %s，旬首 %s（%s），旬空 %s。"
        % (
            kw["pillar_rows"][3]["ganzhi"],
            kw["xun"]["head"],
            kw["xun"]["yi"],
            "".join(kw["kong_zhi"]),
        )
    )
    out.append(
        "值符：%s（本宫%s）随时干落%s。"
        % (kw["zhifu_star"], GONG_NAME[kw["zhifu_home_gong"]], GONG_NAME[kw["zhifu_land_gong"]])
    )
    out.append(
        "值使：%s（本宫%s）随时支落%s（时支距旬首 %d 位，%s）。"
        % (
            kw["zhishi_door"],
            GONG_NAME[kw["zhishi_home_gong"]],
            GONG_NAME[kw["zhishi_gong"]],
            kw["offset_zhi"],
            "顺推" if kw["is_yang"] else "逆推",
        )
    )
    out.append("地盘三奇六仪：" + "、".join(
        "%s%s" % (GONG_NAME[g], kw["earth_map"][g]) for g in range(1, 10)
    ) + "。")
    out.append("九星：" + "、".join(
        "%s%s" % (GONG_NAME[g], kw["star_map"][g][0]) for g in RING
    ) + "；天禽寄「%s」。" % GONG_NAME[kw["qin_gong"]])
    out.append("八门：" + "、".join(
        "%s%s" % (GONG_NAME[g], kw["door_map"][g]) for g in RING
    ) + "。")
    out.append("八神：" + "、".join(
        "%s%s" % (GONG_NAME[g], kw["god_map"][g]) for g in RING
    ) + "。")
    out.append("旬空宫：%s；驿马 %s 居%s。" % (
        "、".join(GONG_NAME[g] for g in kw["kong_gong"]),
        kw["ma_zhi"],
        GONG_NAME.get(kw["ma_gong"], "—"),
    ))
    if kw.get("hour_gan_note"):
        out.append(kw["hour_gan_note"] + "。")
    if kw.get("used_time"):
        out.append("起局时间（report.time.used）：%s。" % kw["used_time"])
    return out


# ---------------------------------------------------------------------------
# 文本渲染
# ---------------------------------------------------------------------------

def _width(text):
    """中英混排显示宽度。"""
    total = 0
    for ch in text:
        total += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return total


def _pad(text, width, align="left"):
    """按显示宽度补空格。"""
    gap = max(0, width - _width(text))
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


def _cell_lines(palace, inner=20):
    """单个宫的 5 行文本。"""
    if palace.get("is_center"):
        head = palace["name"]
        l1 = head
        l2 = "（中五寄坤二）"
        l3 = ""
        l4 = "地盘 %s" % (palace.get("earth_stem") or "—")
        l5 = "·"
    else:
        l1 = palace["name"]
        star = palace.get("star") or "—"
        if palace.get("star_ji"):
            star = star + "+" + palace["star_ji"]
        l2 = "%s · %s" % (star, palace.get("door") or "—")
        l3 = palace.get("deity") or "—"
        heaven = palace.get("heaven_stem") or "—"
        if palace.get("heaven_stem_ji"):
            heaven = heaven + "+" + palace["heaven_stem_ji"]
        l4 = "天盘 %s · 地盘 %s" % (heaven, palace.get("earth_stem") or "—")
        flags = []
        if palace.get("is_kong"):
            flags.append("旬空")
        if palace.get("is_ma"):
            flags.append("驿马")
        l5 = " ".join(flags) if flags else "·"
    raw = (l1, l2, l3, l4, l5)
    return [_pad(t, inner) for t in raw]


def render_qimen_text(data):
    """渲染奇门盘为等宽中文文本。"""
    if not isinstance(data, dict) or "palaces" not in data:
        raise ValueError("render_qimen_text 需要 chart_qimen() 返回的 dict")

    lines = []
    lines.append("奇门遁甲层（%s）｜时家转盘 · 拆补法 · 中五寄坤二" % data.get("version", VERSION))
    lines.append("─" * 64)

    # 要点
    dun = data.get("dun") or {}
    yuan = data.get("yuan") or {}
    xun = data.get("xun") or {}
    zhifu = data.get("zhifu") or {}
    zhishi = data.get("zhishi") or {}
    hour = data.get("hour") or {}
    terms = data.get("jieqi") or {}
    lines.append("【要点】")
    lines.append("· 四柱：%s" % (data.get("pillars_text") or "—"))
    lines.append("· 定局：%s（%s · 符头%s · 节气%s）" % (
        dun.get("label", "—"),
        yuan.get("name") or "—",
        yuan.get("fu_tou") or "—",
        terms.get("name") or "—",
    ))
    lines.append("· 旬首：%s（%s），旬空 %s" % (
        xun.get("head", "—"),
        xun.get("yi", "—"),
        "".join(xun.get("kong") or []) or "—",
    ))
    lines.append("· 值符：%s（本宫 %s）→ %s" % (
        zhifu.get("star", "—"),
        zhifu.get("earth_gong_name", "—"),
        zhifu.get("land_gong_name", "—"),
    ))
    lines.append("· 值使：%s（本宫 %s）→ %s" % (
        zhishi.get("door", "—"),
        GONG_NAME.get(zhishi.get("home_gong") or 0, "—"),
        zhishi.get("gong_name", "—"),
    ))
    lines.append("· 时柱：%s，时干 %s 居 %s；时支 %s 居 %s" % (
        hour.get("ganzhi", "—"),
        hour.get("gan", "—"),
        hour.get("gan_gong_name", "—"),
        hour.get("zhi", "—"),
        GONG_NAME.get(hour.get("zhi_gong") or 0, "—"),
    ))
    kong = data.get("kong") or {}
    ma = data.get("ma") or {}
    lines.append("· 旬空宫：%s；驿马：%s %s" % (
        "、".join(kong.get("gong_names") or []) or "—",
        ma.get("zhi") or "—",
        ma.get("gong_name") or "",
    ))
    used = (data.get("time") or {}).get("used")
    if used:
        lines.append("· 起局时间：%s" % used)
    lines.append("")

    # 九宫
    lines.append("【九宫】（上南下北，左东右西；天盘干+地盘干，天禽随天芮）")
    cells = {}
    for palace in data["palaces"]:
        cells[palace["gong"]] = _cell_lines(palace)
    inner = 20
    border = "+" + "+".join(["-" * inner] * 3) + "+"
    for row in GRID:
        lines.append(border)
        for k in range(5):
            lines.append("|" + "|".join(cells[g][k] if g in cells else _pad("", inner) for g in row) + "|")
    lines.append(border)
    lines.append("")

    # 三奇六仪
    sanqi = data.get("sanqi_liuyi") or {}
    lines.append("【三奇六仪】")
    earth = sanqi.get("earth") or {}
    heaven = sanqi.get("heaven") or {}
    if earth:
        lines.append("· 地盘：" + " ".join(
            "%s%s" % (stem, (earth.get(stem) or {}).get("name", "—")) for stem in "乙丙丁戊己庚辛壬癸"
        ))
    if heaven:
        lines.append("· 天盘：" + " ".join(
            "%s%s" % (stem, (heaven.get(stem) or {}).get("name", "—")) for stem in "乙丙丁戊己庚辛壬癸"
        ))
    if sanqi.get("zhong_gong_earth_stem"):
        lines.append("· 中宫地盘干 %s 随天禽寄%s" % (
            sanqi["zhong_gong_earth_stem"],
            GONG_NAME.get(sanqi.get("zhong_gong_ji_gong") or 0, "—"),
        ))
    lines.append("")

    # 结构要点
    lines.append("【结构要点】")
    for item in data.get("summary") or []:
        lines.append("· " + item)
    lines.append("")

    # 局限
    lines.append("【说明与局限】")
    lines.append("· " + (data.get("note") or NOTE))
    for item in data.get("limits") or []:
        lines.append("· " + item)
    return "\n".join(lines)
