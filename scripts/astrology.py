# -*- coding: utf-8 -*-
"""西洋占星与印度占星计算层（astrology）：给八字排盘补一层「天体几何位置」的参考。

设计原则
--------
1. 纯标准库、零新增运行时依赖：只 import ``math`` / ``datetime``。星历用 Meeus《天文算法》
   的低精度解析公式，不依赖 ephem、swisseph 等星历库；同一输入必然得到同一输出。
2. 只做「坐标与规则可复现」的部分：十星地心视黄经（回归黄道）、上升/天顶/四轴、
   整宫制与 Placidus 宫位、相位、元素/模态/半球分布、月相；另附 Lahiri 岁差近似下的
   恒星黄道（Vedic）星座、Nakshatra、Lagna。
3. 输出结构化 dict（JSON 可序列化），另有 ``render_natal_text`` 渲染中文文本；
   所有流派差异与近似口径都写进 ``limits``，不假装精确、不把占星当事实预测。

对外接口
--------
``chart_natal(report) -> dict``
    入参是 ``bazi.build_report()`` 的返回 dict（读取其中确定的出生绝对时刻与经纬度），
    输出本命占星结构。也可传入只含 ``time.utc`` / ``input.longitude`` / ``input.latitude``
    的最小 dict，便于单测。
``render_natal_text(chart) -> str``
    把上面的 dict 渲染成中文文本（十星表 + 四轴 + 宫位 + 相位 + 分布 + 月相 + Vedic）。

时间口径
--------
星历按 **UTC 绝对时刻**（``report["time"]["utc"]``）计算，而不是按真太阳时的钟面读数：
真太阳时只是八字排盘的时间标尺，把它当 UT 反算会产生十几分钟的时差，上升点会错 4° 左右。
经度用于地方恒星时；纬度用于四轴与宫位。报告里没有纬度时默认北纬 30° 并在 limits 说明。

计算方法
--------
* 儒略日、ΔT 近似（Espenak–Meeus 分段多项式）、章动（低精度四项）、黄赤交角、GMST；
* 太阳：Meeus ch.25（含光行差与章动），精度约 0.01°；
* 月亮：Meeus ch.47 截断 ELP2000（59 项主表 + A1/A2 加法项 + 章动），精度约 0.02°；
* 行星：JPL/Meeus ch.31 近似轨道根数（1800–2050 适用），日心→地心、光行时迭代、
  周年光行差、黄经岁差旋转、章动，精度：内行星约 0.02°，外行星约 0.25°；
* 四轴：GMST + 地理经度 → RAMC，MC 为黄道与子午圈交点，ASC 为黄道与地平圈东交点；
* 宫位：整宫制（ASC 所在星座 0° 起每宫一星座）与 Placidus 半弧法（极区退化时回退整宫制）；
* 相位：0/60/90/120/180，容许度按发光体 8°、个人星 6°、外行星 5°、角点 6°；
* 月相：以日月黄经差分区，照亮比 illum = (1 − cos Δλ) / 2；
* Vedic：Lahiri（Chitrapaksha）岁差线性近似（J2000 ≈ 23.853°，约 0.01397°/年），
  恒星黄经 = 回归黄经 − ayanamsa；27 Nakshatra（每宿 13°20′，pada 3°20′，Vimshottari 宿主星）。
"""

from __future__ import annotations

import datetime
import math

# ---------------------------------------------------------------------------
# 版本、模型说明与局限
# ---------------------------------------------------------------------------

VERSION = "1.0.0"

MODEL = (
    "西洋占星与印度占星计算层：Meeus 低精度解析星历（太阳 ch.25 / 月亮 ch.47 / "
    "行星 JPL 近似根数＋光行时＋光行差＋章动）计算十星地心视黄经；回归黄道；"
    "四轴由 GMST＋经纬度求得；宫位提供整宫制与 Placidus 两种；另给出相位、"
    "元素/模态/半球分布、月相，以及 Lahiri 岁差近似的 Vedic 恒星黄道、Nakshatra 与 Lagna。"
)

LIMITS = [
    "低精度星历：本层为纯标准库解析近似，非法定历表。对 ephem/JPL 参考，"
    "太阳与月亮黄经误差约 ≤0.1°，行星 ≤0.3°；轨道根数 1800–2050 有效，"
    "超出此范围误差会增大（尤其木星、土星）。如需角分级精度请改用专业星历库。",
    "宫位制流派：默认展示整宫制（whole sign），同时给出 Placidus 半弧法结果；"
    "Placidus 在高纬（|纬度| ≳ 66.5°）退化，此时自动回退整宫制并在 warnings 注明。"
    "四轴与宫头依赖出生地纬度，精度受经纬度输入精度限制。",
    "Vedic 岁差为 Lahiri（Chitrapaksha）线性近似：J2000 = 23.853°，约 0.01397°/年，"
    "未含传统 ayanamsa 的周期项、地方拍拉值（如 True Chitra）与不同流派取值差异，"
    "恒星黄经误差约 0.01–0.05°；Nakshatra 采用 27 宿等分（每宿 13°20′）与 Vimshottari 宿主星。",
    "出生时间缺失或为「时辰未知」时按 12:00 兜底；报告无纬度时默认北纬 30°，"
    "上述情况都会在 warnings 中标注，四轴与宫位仅供参考。",
    "占星不作事实预测：本模块只输出天体几何位置与传统占星学归类，属于传统文化模型，"
    "不构成命运论断、医疗/法律/投资建议，也不能替代专业咨询。",
]

# ---------------------------------------------------------------------------
# 基础常量：星座、行星、角点、相位
# ---------------------------------------------------------------------------

SIGNS = [
    "aries", "taurus", "gemini", "cancer", "leo", "virgo",
    "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
]
SIGN_CN = [
    "白羊座", "金牛座", "双子座", "巨蟹座", "狮子座", "处女座",
    "天秤座", "天蝎座", "射手座", "摩羯座", "水瓶座", "双鱼座",
]
# 元素：火/土/风/水；模态：基本/固定/变动（按白羊座起循环）
SIGN_ELEMENT = ["fire", "earth", "air", "water"] * 3
SIGN_MODALITY = ["cardinal", "fixed", "mutable"] * 4
ELEMENT_CN = {"fire": "火", "earth": "土", "air": "风", "water": "水"}
MODALITY_CN = {"cardinal": "基本", "fixed": "固定", "mutable": "变动"}

#: 十星定义。category 用于相位容许度：luminary 发光体 / personal 个人星 / outer 外行星。
PLANETS = [
    {"key": "sun", "name": "太阳", "en": "Sun", "category": "luminary"},
    {"key": "moon", "name": "月亮", "en": "Moon", "category": "luminary"},
    {"key": "mercury", "name": "水星", "en": "Mercury", "category": "personal"},
    {"key": "venus", "name": "金星", "en": "Venus", "category": "personal"},
    {"key": "mars", "name": "火星", "en": "Mars", "category": "personal"},
    {"key": "jupiter", "name": "木星", "en": "Jupiter", "category": "outer"},
    {"key": "saturn", "name": "土星", "en": "Saturn", "category": "outer"},
    {"key": "uranus", "name": "天王星", "en": "Uranus", "category": "outer"},
    {"key": "neptune", "name": "海王星", "en": "Neptune", "category": "outer"},
    {"key": "pluto", "name": "冥王星", "en": "Pluto", "category": "outer"},
]

PLANET_BY_KEY = {p["key"]: p for p in PLANETS}

#: 四个角点（上升/天顶/下降/天底）。
ANGLES = [
    {"key": "asc", "name": "上升点", "en": "ASC"},
    {"key": "mc", "name": "天顶", "en": "MC"},
    {"key": "desc", "name": "下降点", "en": "DESC"},
    {"key": "ic", "name": "天底", "en": "IC"},
]
ANGLE_BY_KEY = {a["key"]: a for a in ANGLES}

#: 相位：(英文键, 角度, 中文名)
ASPECTS = [
    ("conjunction", 0, "合相"),
    ("sextile", 60, "六合"),
    ("square", 90, "刑相"),
    ("trine", 120, "拱相"),
    ("opposition", 180, "冲相"),
]

#: 相位容许度（度）；成对时取双方类别的平均值，角点参与时取 6° 与对方的平均值。
ASPECT_ORB = {"luminary": 8.0, "personal": 6.0, "outer": 5.0, "angle": 6.0}

# ---------------------------------------------------------------------------
# 数学与角度小工具
# ---------------------------------------------------------------------------


def _norm360(x):
    """归一化到 [0, 360)。"""
    return x % 360.0


def _sind(x):
    return math.sin(math.radians(x))


def _cosd(x):
    return math.cos(math.radians(x))


def _angdiff(a, b):
    """a-b 的带符号差，归一化到 (-180, 180]。"""
    d = (a - b) % 360.0
    if d > 180.0:
        d -= 360.0
    return d


def _angsep(a, b):
    """两个黄经的最小夹角 0..180。"""
    return abs(_angdiff(a, b))


# ---------------------------------------------------------------------------
# 时间：儒略日、ΔT、章动、黄赤交角、恒星时
# ---------------------------------------------------------------------------

_DEG = math.pi / 180.0


def julian_day(dt):
    """UTC ``datetime`` → 儒略日（UT）。带时区的输入会先转成 UTC。"""
    if dt.tzinfo is not None:
        dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    y, m = dt.year, dt.month
    day = (dt.day + dt.hour / 24.0 + dt.minute / 1440.0
           + (dt.second + dt.microsecond / 1e6) / 86400.0)
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + day + b - 1524.5


def delta_t_seconds(year):
    """ΔT = TT − UT，单位秒。Espenak–Meeus 分段多项式（1800–2150 分段，其余外推）。"""
    y = float(year)
    if y < 1800.0:
        t = y - 1800.0
        return (13.72 - 0.332447 * t + 0.0068612 * t ** 2 + 0.0041116 * t ** 3
                - 0.00037436 * t ** 4 + 0.0000121272 * t ** 5
                - 0.0000001699 * t ** 6 + 0.000000000875 * t ** 7)
    if y < 1860.0:
        t = y - 1800.0
        return (13.72 - 0.332447 * t + 0.0068612 * t ** 2 + 0.0041116 * t ** 3
                - 0.00037436 * t ** 4 + 0.0000121272 * t ** 5
                - 0.0000001699 * t ** 6 + 0.000000000875 * t ** 7)
    if y < 1900.0:
        t = y - 1860.0
        return (7.62 + 0.5737 * t - 0.251754 * t ** 2 + 0.01680668 * t ** 3
                - 0.0004473624 * t ** 4 + t ** 5 / 233174.0)
    if y < 1920.0:
        t = y - 1900.0
        return (-2.79 + 1.494119 * t - 0.0598939 * t ** 2 + 0.0061966 * t ** 3
                - 0.000197 * t ** 4)
    if y < 1941.0:
        t = y - 1920.0
        return 21.20 + 0.84493 * t - 0.076100 * t ** 2 + 0.0020936 * t ** 3
    if y < 1961.0:
        t = y - 1950.0
        return 29.07 + 0.407 * t - t ** 2 / 233.0 + t ** 3 / 2547.0
    if y < 1986.0:
        t = y - 1975.0
        return 45.45 + 1.067 * t - t ** 2 / 260.0 - t ** 3 / 718.0
    if y < 2005.0:
        t = y - 2000.0
        return (63.86 + 0.3345 * t - 0.060374 * t ** 2 + 0.0017275 * t ** 3
                + 0.000651814 * t ** 4 + 0.00002373599 * t ** 5)
    if y < 2050.0:
        t = y - 2000.0
        return 62.92 + 0.32217 * t + 0.005589 * t ** 2
    if y < 2150.0:
        return -20.0 + 32.0 * ((y - 1820.0) / 100.0) ** 2 - 0.5628 * (2150.0 - y)
    u = (y - 1820.0) / 100.0
    return -20.0 + 32.0 * u * u


def jd_tt(jd_ut):
    """UT 儒略日 → TT 儒略日（加 ΔT）。"""
    year = 2000.0 + (jd_ut - 2451545.0) / 365.25
    return jd_ut + delta_t_seconds(year) / 86400.0


def nutation(jd_tt_value):
    """低精度章动：返回 (Δψ, Δε)（度）。Meeus ch.22 简化式，精度约 0.5″。"""
    t = (jd_tt_value - 2451545.0) / 36525.0
    omega = 125.04452 - 1934.136261 * t
    l_sun = 280.4665 + 36000.7698 * t
    l_moon = 218.3165 + 481267.8813 * t
    d_psi = (-17.20 * _sind(omega) - 1.32 * _sind(2 * l_sun)
             - 0.23 * _sind(2 * l_moon) + 0.21 * _sind(2 * omega)) / 3600.0
    d_eps = (9.20 * _cosd(omega) + 0.57 * _cosd(2 * l_sun)
             + 0.10 * _cosd(2 * l_moon) - 0.09 * _cosd(2 * omega)) / 3600.0
    return d_psi, d_eps


def obliquity_degrees(jd_tt_value):
    """当日平黄赤交角（度）。Meeus 22.2。"""
    t = (jd_tt_value - 2451545.0) / 36525.0
    return (23.0 + 26.0 / 60.0 + 21.448 / 3600.0
            - (46.8150 * t + 0.00059 * t * t - 0.001813 * t ** 3) / 3600.0)


def gmst_degrees(jd_ut):
    """格林尼治平恒星时（度）。Meeus 12.4，输入为 UT。"""
    t = (jd_ut - 2451545.0) / 36525.0
    return _norm360(280.46061837 + 360.98564736629 * (jd_ut - 2451545.0)
                    + 0.000387933 * t * t - t ** 3 / 38710000.0)


def local_sidereal_degrees(jd_ut, longitude_east):
    """地方恒星时（度）= GMST + 东经。"""
    return _norm360(gmst_degrees(jd_ut) + longitude_east)


# ---------------------------------------------------------------------------
# 星历 1：太阳（Meeus ch.25）
# ---------------------------------------------------------------------------


def sun_longitude(jd_tt_value):
    """太阳地心视黄经（度，回归黄道当日春分点）。误差约 0.01°。"""
    t = (jd_tt_value - 2451545.0) / 36525.0
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    m = 357.52911 + 35999.05029 * t - 0.0001537 * t * t
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * _sind(m)
         + (0.019993 - 0.000101 * t) * _sind(2 * m)
         + 0.000289 * _sind(3 * m))
    true_lon = l0 + c
    # 视黄经：减去光行差（0.00569°）与「章动在主项上的投影」
    omega = 125.04 - 1934.136 * t
    return _norm360(true_lon - 0.00569 - 0.00478 * _sind(omega))


# ---------------------------------------------------------------------------
# 星历 2：月亮（Meeus ch.47 截断 ELP2000）
# ---------------------------------------------------------------------------

#: (D, M, M', F, Σl 系数 ×1e-6 度)，Meeus Table 47.A 的主项（59 项）。
_MOON_TERMS = [
    (0, 0, 1, 0, 6288774), (2, 0, -1, 0, 1274027), (2, 0, 0, 0, 658314),
    (0, 0, 2, 0, 213618), (0, 1, 0, 0, -185116), (0, 0, 0, 2, -114332),
    (2, 0, -2, 0, 58793), (2, -1, -1, 0, 57066), (2, 0, 1, 0, 53322),
    (2, -1, 0, 0, 45758), (0, 1, -1, 0, -40923), (1, 0, 0, 0, -34720),
    (0, 1, 1, 0, -30383), (2, 0, 0, -2, 15327), (0, 0, 1, 2, -12528),
    (0, 0, 1, -2, 10980), (4, 0, -1, 0, 10675), (0, 0, 3, 0, 10034),
    (4, 0, -2, 0, 8548), (2, 1, -1, 0, -7888), (2, 1, 0, 0, -6766),
    (1, 0, -1, 0, -5163), (1, 1, 0, 0, 4987), (2, -1, 1, 0, 4036),
    (2, 0, 2, 0, 3994), (4, 0, 0, 0, 3861), (2, 0, -3, 0, 3665),
    (0, 1, -2, 0, -2689), (2, 0, -1, 2, -2602), (2, -1, -2, 0, 2390),
    (1, 0, 1, 0, -2348), (2, -2, 0, 0, 2236), (0, 1, 2, 0, -2120),
    (0, 2, 0, 0, -2069), (2, -2, -1, 0, 2048), (2, 0, 1, -2, -1773),
    (2, 0, 0, 2, -1595), (4, -1, -1, 0, 1215), (0, 0, 2, 2, -1110),
    (3, 0, -1, 0, -892), (2, 1, 1, 0, -810), (4, -1, -2, 0, 759),
    (0, 2, -1, 0, -713), (2, 2, -1, 0, -700), (2, 1, -2, 0, 691),
    (2, -1, 0, -2, 596), (4, 0, 1, 0, 549), (0, 0, 4, 0, 537),
    (4, -1, 0, 0, 520), (1, 0, -2, 0, -487), (2, 1, 0, -2, -399),
    (0, 0, 2, -2, -381), (1, 1, 1, 0, 351), (3, 0, -2, 0, -340),
    (4, 0, -3, 0, 330), (2, -1, 2, 0, 327), (0, 2, 1, 0, -323),
    (1, 1, -1, 0, 299), (2, 0, 3, 0, 294),
]


def moon_longitude(jd_tt_value):
    """月亮地心视黄经（度，回归黄道当日春分点）。误差约 0.02°。"""
    t = (jd_tt_value - 2451545.0) / 36525.0
    l_prime = (218.3164477 + 481267.88123421 * t - 0.0015786 * t * t
               + t ** 3 / 538841.0 - t ** 4 / 65194000.0)
    d = (297.8501921 + 445267.1114034 * t - 0.0018819 * t * t
         + t ** 3 / 545868.0 - t ** 4 / 113065000.0)
    m = (357.5291092 + 35999.0502909 * t - 0.0001536 * t * t
         + t ** 3 / 24490000.0)
    m_prime = (134.9633964 + 477198.8675055 * t + 0.0087414 * t * t
               + t ** 3 / 69699.0 - t ** 4 / 14712000.0)
    f = (93.2720950 + 483202.0175233 * t - 0.0036539 * t * t
         - t ** 3 / 3526000.0 + t ** 4 / 863310000.0)
    e = 1.0 - 0.002516 * t - 0.0000074 * t * t

    d_r, m_r, mp_r, f_r = d * _DEG, m * _DEG, m_prime * _DEG, f * _DEG
    sum_l = 0.0
    for cd, cm, cmp_, cf, coef in _MOON_TERMS:
        arg = cd * d_r + cm * m_r + cmp_ * mp_r + cf * f_r
        c = coef
        am = abs(cm)
        if am == 1:
            c *= e
        elif am == 2:
            c *= e * e
        sum_l += c * math.sin(arg)

    a1 = (119.75 + 131.849 * t) * _DEG
    a2 = (53.09 + 479264.290 * t) * _DEG
    sum_l += (3958.0 * math.sin(a1)
              + 1962.0 * math.sin((l_prime - f) * _DEG)
              + 318.0 * math.sin(a2))

    d_psi, _ = nutation(jd_tt_value)
    return _norm360(l_prime + sum_l / 1e6 + d_psi)


# ---------------------------------------------------------------------------
# 星历 3：行星（JPL/Meeus ch.31 近似轨道根数）
# ---------------------------------------------------------------------------

#: 每行 = (a, e, I, L, 近日点黄经ϖ, 升交点Ω) 在 J2000 黄道系；第二行为每儒略世纪变化率。
#: 来源：JPL 近似根数（Meeus ch.31 / E.M. Standish），适用 1800–2050。
_ELEMENTS = {
    "mercury": ((0.38709927, 0.20563593, 7.00497902, 252.25032350, 77.45779628, 48.33076593),
                (0.00000037, 0.00001906, -0.00594749, 149472.67411175, 0.16047689, -0.12534081)),
    "venus": ((0.72333566, 0.00677672, 3.39467605, 181.97909950, 131.60246718, 76.67984255),
              (0.00000390, -0.00004107, -0.00078890, 58517.81538729, 0.00268329, -0.27769418)),
    "earth": ((1.00000261, 0.01671123, -0.00001531, 100.46457166, 102.93768193, 0.0),
              (0.00000562, -0.00004392, -0.01294668, 35999.37244981, 0.32327364, 0.0)),
    "mars": ((1.52371034, 0.09339410, 1.84969142, -4.55343205, -23.94362959, 49.55953891),
             (0.00001847, 0.00007882, -0.00813131, 19140.30268499, 0.44441088, -0.29257343)),
    "jupiter": ((5.20288700, 0.04838624, 1.30439695, 34.39644051, 14.72847983, 100.47390909),
                (-0.00011607, -0.00013253, -0.00183714, 3034.74612775, 0.21252668, 0.20469106)),
    "saturn": ((9.53667594, 0.05386179, 2.48599187, 49.95424423, 92.59887831, 113.66242448),
               (-0.00125060, -0.00050991, 0.00193609, 1222.49362201, -0.41897216, -0.28867794)),
    "uranus": ((19.18916464, 0.04725744, 0.77263783, 313.23810451, 170.95427630, 74.01692503),
               (-0.00196176, -0.00004397, -0.00242939, 428.48202785, 0.40805281, 0.04240589)),
    "neptune": ((30.06992276, 0.00859048, 1.77004347, -55.12002969, 44.96476227, 131.78422574),
                (0.00026291, 0.00005105, 0.00035372, 218.45945325, -0.32241464, -0.00508664)),
    "pluto": ((39.48211675, 0.24882730, 17.14001206, 238.92903833, 224.06891629, 110.30393684),
              (-0.00031596, 0.00005170, 0.00004818, 145.20780515, -0.04062942, -0.01183482)),
}

#: 光行时：1 AU 的光行时（天）；光速（AU/天）
_LIGHT_TIME_PER_AU = 0.0057755183
_SPEED_OF_LIGHT_AU_DAY = 173.144632674


def _heliocentric_xyz(name, t_cent):
    """日心黄道坐标（AU，J2000 黄道系）。name 用小写键；开普勒方程牛顿迭代。"""
    (a0, e0, i0, l0, w0, o0), (da, de, di, dl, dw, do) = _ELEMENTS[name]
    a = a0 + da * t_cent
    e = e0 + de * t_cent
    inc = (i0 + di * t_cent) * _DEG
    mean_lon = l0 + dl * t_cent
    peri = (w0 + dw * t_cent) * _DEG
    node = (o0 + do * t_cent) * _DEG

    mean_anomaly = (mean_lon * _DEG - peri)
    mean_anomaly = (mean_anomaly + math.pi) % (2.0 * math.pi) - math.pi
    ecc_anom = mean_anomaly + e * math.sin(mean_anomaly)
    for _ in range(60):
        delta = (ecc_anom - e * math.sin(ecc_anom) - mean_anomaly) / (1.0 - e * math.cos(ecc_anom))
        ecc_anom -= delta
        if abs(delta) < 1e-13:
            break

    xp = a * (math.cos(ecc_anom) - e)
    yp = a * math.sqrt(1.0 - e * e) * math.sin(ecc_anom)

    arg_peri = peri - node
    cw, sw = math.cos(arg_peri), math.sin(arg_peri)
    cn, sn = math.cos(node), math.sin(node)
    ci, si = math.cos(inc), math.sin(inc)
    x = (cw * cn - sw * sn * ci) * xp + (-sw * cn - cw * sn * ci) * yp
    y = (cw * sn + sw * cn * ci) * xp + (-sw * sn + cw * cn * ci) * yp
    z = (sw * si) * xp + (cw * si) * yp
    return x, y, z


def _precession_longitude(t_cent):
    """J2000 黄道系 → 当日黄道系的黄经岁差累积（度）。Meeus 21.5 简化。"""
    return 1.396971 * t_cent + 0.0003086 * t_cent * t_cent


def planet_longitude(key, jd_tt_value):
    """行星地心视黄经（度，回归黄道当日春分点），含光行时迭代、周年光行差、岁差、章动。"""
    t = (jd_tt_value - 2451545.0) / 36525.0
    earth = _heliocentric_xyz("earth", t)

    # 光行时迭代：行星在「光发出时刻」的位置
    tau = 0.0
    geo = earth
    for _ in range(3):
        tp = (jd_tt_value - tau - 2451545.0) / 36525.0
        planet = _heliocentric_xyz(key, tp)
        geo = (planet[0] - earth[0], planet[1] - earth[1], planet[2] - earth[2])
        dist = math.sqrt(geo[0] ** 2 + geo[1] ** 2 + geo[2] ** 2)
        tau = _LIGHT_TIME_PER_AU * dist
    gx, gy, gz = geo
    dist = math.sqrt(gx * gx + gy * gy + gz * gz)
    ux, uy, uz = gx / dist, gy / dist, gz / dist

    # 周年光行差：地球速度（AU/天）× 1/c，按矢量叠加到视方向
    half = 0.5
    e_plus = _heliocentric_xyz("earth", t + half / 36525.0)
    e_minus = _heliocentric_xyz("earth", t - half / 36525.0)
    vx = (e_plus[0] - e_minus[0]) / (2.0 * half)
    vy = (e_plus[1] - e_minus[1]) / (2.0 * half)
    vz = (e_plus[2] - e_minus[2]) / (2.0 * half)
    ux += vx / _SPEED_OF_LIGHT_AU_DAY
    uy += vy / _SPEED_OF_LIGHT_AU_DAY
    uz += vz / _SPEED_OF_LIGHT_AU_DAY

    lon = math.degrees(math.atan2(uy, ux))
    lon += _precession_longitude(t)
    d_psi, _ = nutation(jd_tt_value)
    return _norm360(lon + d_psi)


def body_longitude(key, jd_tt_value):
    """按行星键取地心视黄经：sun/moon 用专用公式，其余用近似根数。"""
    if key == "sun":
        return sun_longitude(jd_tt_value)
    if key == "moon":
        return moon_longitude(jd_tt_value)
    if key not in _ELEMENTS:
        raise KeyError("未知天体：%r" % (key,))
    return planet_longitude(key, jd_tt_value)


def body_longitudes(jd_tt_value):
    """十星地心视黄经 dict（key → 度）。"""
    return {p["key"]: body_longitude(p["key"], jd_tt_value) for p in PLANETS}


def body_speed(key, jd_tt_value, step=1.0):
    """黄经日速度（度/天），用前后各 ``step`` 天的中心差分；负值即逆行。"""
    before = body_longitude(key, jd_tt_value - step)
    after = body_longitude(key, jd_tt_value + step)
    return _angdiff(after, before) / (2.0 * step)


# ---------------------------------------------------------------------------
# 四轴与宫位
# ---------------------------------------------------------------------------


def mc_longitude(ramc_deg, obliquity_deg):
    """天顶黄经（度）：黄道与子午圈的交点。"""
    a = ramc_deg * _DEG
    e = obliquity_deg * _DEG
    return _norm360(math.degrees(math.atan2(math.sin(a), math.cos(a) * math.cos(e))))


def asc_longitude(ramc_deg, obliquity_deg, latitude_deg):
    """上升点黄经（度）：黄道与地平圈的东交点（几何校验：该点地平高度为 0 且在升起）。"""
    a = ramc_deg * _DEG
    e = obliquity_deg * _DEG
    p = latitude_deg * _DEG
    return _norm360(math.degrees(math.atan2(
        math.cos(a), -(math.sin(a) * math.cos(e) + math.tan(p) * math.sin(e)))))


def angles(jd_ut, longitude_east, latitude_deg):
    """四轴：返回 {asc, mc, desc, ic, ramc, obliquity}（黄经，度）。"""
    ramc = local_sidereal_degrees(jd_ut, longitude_east)
    eps = obliquity_degrees(jd_tt(jd_ut))
    asc = asc_longitude(ramc, eps, latitude_deg)
    mc = mc_longitude(ramc, eps)
    return {
        "ramc": ramc,
        "obliquity": eps,
        "asc": asc,
        "mc": mc,
        "desc": _norm360(asc + 180.0),
        "ic": _norm360(mc + 180.0),
    }


def _ecl_to_equatorial(lon_deg, obliquity_deg):
    """黄道坐标（纬度取 0）→ 赤道坐标 (α, δ)（度）。"""
    lam = lon_deg * _DEG
    eps = obliquity_deg * _DEG
    ra = math.degrees(math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam)))
    dec = math.degrees(math.asin(math.sin(eps) * math.sin(lam)))
    return ra, dec


def _ra_to_ecliptic(ra_deg, obliquity_deg):
    """赤经 → 黄道经度（黄纬取 0，度）。"""
    ra = ra_deg * _DEG
    eps = obliquity_deg * _DEG
    return _norm360(math.degrees(math.atan2(
        math.sin(ra), math.cos(ra) * math.cos(eps))))


def whole_sign_cusps(asc_lon):
    """整宫制宫头：从 ASC 所在星座 0° 起，每宫一个星座（12 个黄经）。"""
    first = int(_norm360(asc_lon) // 30.0) * 30.0
    return [_norm360(first + 30.0 * i) for i in range(12)]


def _semi_diurnal_arc(dec_deg, latitude_deg):
    """天体周日半弧（度）；地平圈无交点（极昼/极夜）时返回 None。"""
    x = -math.tan(latitude_deg * _DEG) * math.tan(dec_deg * _DEG)
    if x >= 1.0:
        return 0.0      # 恒显：半弧取 0（退化）
    if x <= -1.0:
        return None     # 恒隐/无解：Placidus 退化
    return math.degrees(math.acos(x))


def placidus_cusps(ramc_deg, obliquity_deg, latitude_deg):
    """Placidus 宫头（半弧法，返回 12 个黄经，从第 1 宫起）。

    11/12 宫头把「子午圈→上升点」的周日半弧三等分，2/3 宫头把
    「天底→上升点」的夜间半弧三等分；用不动点迭代求黄道交点。
    极区（|纬度| ≳ 66.5°，半弧无解）返回 None。
    """
    lat = float(latitude_deg)
    if abs(lat) > 66.5:
        return None
    eps = float(obliquity_deg)
    ramc = _norm360(ramc_deg)

    asc = asc_longitude(ramc, eps, lat)
    mc = mc_longitude(ramc, eps)
    cusps = {1: asc, 4: _norm360(mc + 180.0), 7: _norm360(asc + 180.0), 10: mc}

    # 每个中间宫头：分数 f 与方向 kind（d=从 MC 向上升点的周日弧，n=从 IC 向上升点的夜间弧）
    for cusp, kind, frac in ((11, "d", 1.0 / 3.0), (12, "d", 2.0 / 3.0),
                             (2, "n", 2.0 / 3.0), (3, "n", 1.0 / 3.0)):
        lam = _ra_to_ecliptic(ramc, eps)  # 初值：MC 黄经
        for _ in range(80):
            _, dec = _ecl_to_equatorial(lam, eps)
            ha = _semi_diurnal_arc(dec, lat)
            if ha is None:
                return None
            if kind == "d":
                ra = ramc + ha * frac
            else:
                ra = ramc - 180.0 - (180.0 - ha) * frac
            new_lam = _ra_to_ecliptic(ra, eps)
            delta = _angdiff(new_lam, lam)
            lam = new_lam
            if abs(delta) < 1e-10:
                break
        else:
            return None
        cusps[cusp] = _norm360(lam)

    cusps[5] = _norm360(cusps[11] + 180.0)
    cusps[6] = _norm360(cusps[12] + 180.0)
    cusps[8] = _norm360(cusps[2] + 180.0)
    cusps[9] = _norm360(cusps[3] + 180.0)

    # 单调性自检：解卷绕后应严格递增且每宫跨度 < 200°（极端纬度可能失败）
    seq = [cusps[i] for i in range(1, 13)] + [cusps[1] + 360.0]
    prev = seq[0]
    for value in seq[1:]:
        cur = value
        while cur <= prev:
            cur += 360.0
        if cur - prev > 200.0:
            return None
        prev = cur
    return [cusps[i] for i in range(1, 13)]


def house_of_longitude(lon_deg, cusps):
    """按宫头列表（从第 1 宫起，12 个黄经）求某黄经落在第几宫。"""
    lon = _norm360(lon_deg)
    for i in range(12):
        start = cusps[i]
        span = _norm360(cusps[(i + 1) % 12] - start)
        if span <= 0.0:
            continue
        offset = _norm360(lon - start)
        if offset < span:
            return i + 1
    return 1


def house_of_sign(sign_index, asc_sign_index):
    """整宫制：某星座落在第几宫（sign_index/asc_sign_index 为 0..11）。"""
    return (int(sign_index) - int(asc_sign_index)) % 12 + 1


# ---------------------------------------------------------------------------
# 相位、分布、月相
# ---------------------------------------------------------------------------


def aspect_orb_allowed(category_a, category_b):
    """成对容许度：取双方类别容许度的平均值。"""
    return (ASPECT_ORB.get(category_a, 5.0) + ASPECT_ORB.get(category_b, 5.0)) / 2.0


def find_aspects(planets, angles):
    """求相位。planets/angles 为含 key/name/category/lon 的列表。

    角点与行星、行星与行星参与相位；角点之间（如 ASC-MC）不参与。
    每个天体对只取最接近的一个相位（按 0/60/90/120/180 顺序匹配第一个）。
    """
    points = []
    for p in planets:
        points.append({"key": p["key"], "name": p["name"],
                       "category": p["category"], "lon": p["lon"]})
    for a in angles:
        points.append({"key": a["key"], "name": a["name"],
                       "category": "angle", "lon": a["lon"]})

    found = []
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            pa, pb = points[i], points[j]
            if pa["category"] == "angle" and pb["category"] == "angle":
                continue
            allowed = aspect_orb_allowed(pa["category"], pb["category"])
            separation = _angsep(pa["lon"], pb["lon"])
            for type_key, exact, type_cn in ASPECTS:
                orb = abs(separation - exact)
                if orb <= allowed:
                    found.append({
                        "a": pa["key"],
                        "b": pb["key"],
                        "type": type_key,
                        "type_cn": type_cn,
                        "angle": exact,
                        "separation": round(separation, 3),
                        "orb": round(orb, 3),
                        "orb_allowed": round(allowed, 3),
                    })
                    break
    return found


def balance_of(planets, asc_sign_index):
    """元素 / 模态 / 半球分布（按十星的星座与整宫制宫位统计）。"""
    elements = {"fire": 0, "earth": 0, "air": 0, "water": 0}
    modalities = {"cardinal": 0, "fixed": 0, "mutable": 0}
    hemispheres = {"above": 0, "below": 0, "east": 0, "west": 0}
    for p in planets:
        sign_index = int(p["lon"] // 30.0) % 12
        elements[SIGN_ELEMENT[sign_index]] += 1
        modalities[SIGN_MODALITY[sign_index]] += 1
        house = house_of_sign(sign_index, asc_sign_index)
        if house >= 7:
            hemispheres["above"] += 1
        else:
            hemispheres["below"] += 1
        if house in (10, 11, 12, 1, 2, 3):
            hemispheres["east"] += 1
        else:
            hemispheres["west"] += 1
    return {"elements": elements, "modalities": modalities, "hemispheres": hemispheres}


def moon_phase(sun_lon, moon_lon):
    """月相：以日月黄经差（0–360）分区，照亮比 illum=(1−cosΔλ)/2。"""
    angle = _norm360(moon_lon - sun_lon)
    illum = (1.0 - _cosd(angle)) / 2.0
    if angle < 45.0 or angle >= 315.0:
        phase = "新月"
    elif angle < 135.0:
        phase = "上弦月"
    elif angle < 225.0:
        phase = "满月"
    else:
        phase = "下弦月"
    if angle < 22.5 or angle >= 337.5:
        phase8 = "新月"
    elif angle < 67.5:
        phase8 = "娥眉月"
    elif angle < 112.5:
        phase8 = "上弦月"
    elif angle < 157.5:
        phase8 = "盈凸月"
    elif angle < 202.5:
        phase8 = "满月"
    elif angle < 247.5:
        phase8 = "亏凸月"
    elif angle < 292.5:
        phase8 = "下弦月"
    else:
        phase8 = "残月"
    return {"phase": phase, "angle": round(angle, 3),
            "illum": round(illum, 4), "phase8": phase8}


# ---------------------------------------------------------------------------
# Vedic（印度占星）层
# ---------------------------------------------------------------------------

#: Lahiri（Chitrapaksha）岁差近似：J2000 值 + 每世纪速率（与黄经总岁差同量级）。
AYANAMSA_J2000 = 23.85306
AYANAMSA_RATE_PER_CENTURY = 1.396971

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishtha", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]
#: Vimshottari 宿主星序列（27 宿循环 3 遍）。
NAKSHATRA_RULERS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu",
                    "Jupiter", "Saturn", "Mercury"]
NAKSHATRA_RULER_CN = {
    "Ketu": "计都", "Venus": "金星", "Sun": "太阳", "Moon": "月亮",
    "Mars": "火星", "Rahu": "罗睺", "Jupiter": "木星",
    "Saturn": "土星", "Mercury": "水星",
}

NAKSHATRA_SPAN = 360.0 / 27.0          # 13°20′
NAKSHATRA_PADA_SPAN = NAKSHATRA_SPAN / 4.0  # 3°20′


def ayanamsa(jd_tt_value):
    """Lahiri 岁差（度）：回归黄经 − 恒星黄经。J2000 ≈ 23.853°。"""
    t = (jd_tt_value - 2451545.0) / 36525.0
    return AYANAMSA_J2000 + AYANAMSA_RATE_PER_CENTURY * t + 0.0003086 * t * t


def sidereal_longitude(tropical_lon, jd_tt_value):
    """回归黄经 → 恒星黄经（度）。"""
    return _norm360(tropical_lon - ayanamsa(jd_tt_value))


def nakshatra_of(sidereal_lon):
    """恒星黄经 → (第几宿 1–27, 宿名, pada 1–4, 宿主星英文, 宿主星中文)。"""
    lon = _norm360(sidereal_lon)
    index = int(lon // NAKSHATRA_SPAN)
    index = min(index, 26)
    pada = int((lon - index * NAKSHATRA_SPAN) // NAKSHATRA_PADA_SPAN) + 1
    pada = min(pada, 4)
    ruler = NAKSHATRA_RULERS[index % 9]
    return {
        "index": index + 1,
        "name": NAKSHATRAS[index],
        "pada": pada,
        "ruler": ruler,
        "ruler_cn": NAKSHATRA_RULER_CN[ruler],
        "degree_in_nakshatra": round(lon - index * NAKSHATRA_SPAN, 4),
    }


# ---------------------------------------------------------------------------
# 报告解析
# ---------------------------------------------------------------------------

_TIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M",
]


def _parse_datetime(text):
    """把 "YYYY-MM-DD HH:MM[:SS]" / ISO8601 解析为 naive datetime（失败返回 None）。"""
    if not text:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    try:
        dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError:
        pass
    for fmt in _TIME_FORMATS:
        try:
            return datetime.datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _resolve_moment(report):
    """从 report 解析出生绝对时刻（UTC）与来源说明。"""
    report = report or {}
    time_info = report.get("time") or {}
    input_info = report.get("input") or {}

    # 1) 首选：time.utc（bazi.build_report 给出的绝对 UTC 时刻）
    dt = _parse_datetime(time_info.get("utc"))
    if dt is not None:
        return dt, "report.time.utc"

    # 2) 次选：time.civil（当地钟表时间）− UTC 偏移
    civil = _parse_datetime(time_info.get("civil"))
    if civil is None:
        date_text = input_info.get("date")
        clock_text = input_info.get("time") or "12:00"
        if date_text:
            civil = _parse_datetime("%s %s" % (date_text, clock_text))
            if civil is not None and not input_info.get("time"):
                civil = civil.replace(hour=12, minute=0, second=0)
    if civil is not None:
        offset = time_info.get("utc_offset_hours")
        if offset is None:
            offset = ((time_info.get("standard_offset_hours") or 0.0)
                      + (time_info.get("dst_hours") or 0.0))
        try:
            offset = float(offset)
        except (TypeError, ValueError):
            offset = 0.0
        return civil - datetime.timedelta(hours=offset), "report.time.civil-utc_offset"

    # 3) 兜底：time.used（多为当地真太阳时，只能粗略当地方时用）
    used = _parse_datetime(time_info.get("used"))
    if used is not None:
        note = "true_solar" if time_info.get("used_kind") == "tst" else "local"
        return used, "report.time.used(%s)" % note

    # 4) 完全没有时间信息：按 2000-01-01 12:00 UTC 兜底
    return datetime.datetime(2000, 1, 1, 12, 0, 0), "fallback(2000-01-01 12:00 UTC)"


def _resolve_place(report):
    """从 report 解析经度（东正）与纬度（北正），返回 (lon, lat, lat_default)。"""
    report = report or {}
    time_info = report.get("time") or {}
    input_info = report.get("input") or {}

    lon = input_info.get("longitude")
    if lon is None:
        lon = time_info.get("longitude")
    try:
        lon = float(lon) if lon is not None else 0.0
    except (TypeError, ValueError):
        lon = 0.0
    if lon < -180.0 or lon > 180.0:
        lon = ((lon + 180.0) % 360.0) - 180.0

    lat = input_info.get("latitude")
    if lat is None:
        lat = input_info.get("lat")
    if lat is None:
        lat = time_info.get("latitude")
    lat_default = False
    if lat is None:
        lat = 30.0
        lat_default = True
    try:
        lat = float(lat)
    except (TypeError, ValueError):
        lat = 30.0
        lat_default = True
    lat = max(-89.9, min(89.9, lat))
    return lon, lat, lat_default


# ---------------------------------------------------------------------------
# 主入口：chart_natal
# ---------------------------------------------------------------------------


def _sign_block(lon):
    """黄经 → 星座信息 dict。"""
    index = int(_norm360(lon) // 30.0) % 12
    return {
        "sign": SIGNS[index],
        "sign_cn": SIGN_CN[index],
        "sign_index": index,
        "sign_degree": round(_norm360(lon) - 30.0 * index, 3),
        "element": SIGN_ELEMENT[index],
        "modality": SIGN_MODALITY[index],
    }


def chart_natal(report):
    """本命占星盘（JSON 可序列化、同输入同输出）。

    参数
    ----
    report : dict
        ``bazi.build_report()`` 的返回，或任意含 ``time.utc``（UTC 绝对时刻）、
        ``input.longitude``、``input.latitude`` 的 dict。

    返回
    ----
    dict
        含 version/method/input/planets/angles/houses/aspects/balance/
        moon_phase/vedic/summary/limits/warnings 等键，见模块 docstring。
    """
    dt_utc, time_source = _resolve_moment(report)
    longitude, latitude, lat_default = _resolve_place(report)
    report = report or {}
    input_info = report.get("input") or {}
    time_info = report.get("time") or {}

    warnings = []
    if lat_default:
        warnings.append("报告未提供纬度，按北纬 30° 默认计算四轴与宫位（参考值，精度有限）。")
    if time_source.startswith("fallback"):
        warnings.append("报告缺少可用出生时刻，按 2000-01-01 12:00 UTC 兜底。")
    elif time_source.startswith("report.time.used"):
        warnings.append("报告缺少 time.utc，改用 time.used 近似（真太阳时与 UT 有十几分钟差异，四轴略偏）。")
    if time_info.get("time_unknown") or input_info.get("time_unknown"):
        warnings.append("原始输入标注「时辰未知」，出生时刻按报告所给值计算，四轴/宫位仅供粗略参考。")

    jd_ut = julian_day(dt_utc)
    jd_tt_value = jd_tt(jd_ut)

    raw_lons = body_longitudes(jd_tt_value)
    raw_speeds = {p["key"]: body_speed(p["key"], jd_tt_value) for p in PLANETS}

    angle_data = angles(jd_ut, longitude, latitude)
    asc = angle_data["asc"]
    asc_sign_index = int(_norm360(asc) // 30.0) % 12

    # 整宫制宫头
    ws_cusps = whole_sign_cusps(asc)

    # Placidus 宫头（高纬退化时回退）
    mars_ramc = angle_data["ramc"]
    eps = angle_data["obliquity"]
    pl_cusps = placidus_cusps(mars_ramc, eps, latitude)
    placidus_available = pl_cusps is not None
    if not placidus_available:
        warnings.append("Placidus 宫位在高纬退化（|纬度|>66.5° 或半弧无解），已回退整宫制。")
        pl_cusps = list(ws_cusps)

    # 十星
    planets = []
    for p in PLANETS:
        lon = raw_lons[p["key"]]
        speed = raw_speeds[p["key"]]
        sign_block = _sign_block(lon)
        house_ws = house_of_sign(sign_block["sign_index"], asc_sign_index)
        house_pl = house_of_longitude(lon, pl_cusps)
        planets.append({
            "key": p["key"],
            "name": p["name"],
            "en": p["en"],
            "category": p["category"],
            "lon": round(_norm360(lon), 4),
            "sign": sign_block["sign"],
            "sign_cn": sign_block["sign_cn"],
            "degree": sign_block["sign_degree"],
            "element": sign_block["element"],
            "modality": sign_block["modality"],
            "retrograde": bool(speed < 0.0 and p["key"] not in ("sun", "moon")),
            "speed": round(speed, 4),
            "house": house_ws,
            "house_placidus": house_pl if placidus_available else None,
        })

    # 四轴
    angle_points = []
    angle_output = {}
    for a in ANGLES:
        lon = angle_data[a["key"]]
        angle_block = _sign_block(lon)
        angle_output[a["key"]] = {
            "key": a["key"],
            "name": a["name"],
            "en": a["en"],
            "lon": round(lon, 4),
            "sign": angle_block["sign"],
            "sign_cn": angle_block["sign_cn"],
            "degree": angle_block["sign_degree"],
        }
        angle_points.append({"key": a["key"], "name": a["name"],
                             "category": "angle", "lon": lon})

    # 宫位（两种制度并列）
    house_systems = {
        "whole_sign": {
            "system": "whole_sign",
            "system_cn": "整宫制",
            "available": True,
            "cusps": [round(c, 4) for c in ws_cusps],
        },
        "placidus": {
            "system": "placidus",
            "system_cn": "Placidus 半弧法",
            "available": placidus_available,
            "cusps": [round(c, 4) for c in pl_cusps],
        },
    }

    # 相位（用未取整的黄经算，保证几何精度）
    aspect_planets = [{"key": p["key"], "name": p["name"],
                       "category": p["category"], "lon": raw_lons[p["key"]]} for p in PLANETS]
    aspects = find_aspects(aspect_planets, angle_points)

    # 元素 / 模态 / 半球
    balance = balance_of(planets, asc_sign_index)

    # 月相
    phase = moon_phase(raw_lons["sun"], raw_lons["moon"])

    # Vedic
    ay = ayanamsa(jd_tt_value)
    sidereal = {p["key"]: sidereal_longitude(raw_lons[p["key"]], jd_tt_value) for p in PLANETS}
    sidereal_planets = {}
    for p in PLANETS:
        slon = sidereal[p["key"]]
        block = _sign_block(slon)
        nak = nakshatra_of(slon)
        sidereal_planets[p["key"]] = {
            "key": p["key"],
            "name": p["name"],
            "lon": round(slon, 4),
            "sign": block["sign"],
            "sign_cn": block["sign_cn"],
            "degree": block["sign_degree"],
            "nakshatra": nak["name"],
            "pada": nak["pada"],
            "nakshatra_ruler": nak["ruler"],
            "nakshatra_ruler_cn": nak["ruler_cn"],
        }
    sidereal_asc = sidereal_longitude(asc, jd_tt_value)
    lagna_block = _sign_block(sidereal_asc)
    moon_nak = nakshatra_of(sidereal["moon"])
    vedic = {
        "ayanamsa": round(ay, 4),
        "ayanamsa_system": "Lahiri (Chitrapaksha) 线性近似",
        "sidereal_planets": sidereal_planets,
        "sun_sign": _sign_block(sidereal["sun"])["sign_cn"],
        "moon_sign": _sign_block(sidereal["moon"])["sign_cn"],
        "lagna": {
            "lon": round(sidereal_asc, 4),
            "sign": lagna_block["sign"],
            "sign_cn": lagna_block["sign_cn"],
            "degree": lagna_block["sign_degree"],
        },
        "nakshatra": {
            "name": moon_nak["name"],
            "index": moon_nak["index"],
            "pada": moon_nak["pada"],
            "ruler": moon_nak["ruler"],
            "ruler_cn": moon_nak["ruler_cn"],
            "degree_in_nakshatra": moon_nak["degree_in_nakshatra"],
        },
    }

    # 摘要
    summary = _build_summary(planets, angle_output, phase, vedic, balance)

    input_echo = {
        "date": input_info.get("date"),
        "time": input_info.get("time"),
        "time_unknown": bool(input_info.get("time_unknown") or time_info.get("time_unknown")),
        "zone": input_info.get("zone") or time_info.get("zone"),
        "longitude": round(longitude, 4),
        "latitude": round(latitude, 4),
        "latitude_default": lat_default,
        "utc": dt_utc.strftime("%Y-%m-%d %H:%M:%S"),
        "time_source": time_source,
    }

    return {
        "version": VERSION,
        "method": MODEL,
        "input": input_echo,
        "planets": planets,
        "angles": angle_output,
        "houses": {
            "system": "whole_sign",
            "system_cn": "整宫制",
            "cusps": [round(c, 4) for c in ws_cusps],
            "systems": house_systems,
        },
        "aspects": aspects,
        "balance": balance,
        "moon_phase": phase,
        "vedic": vedic,
        "summary": summary,
        "limits": list(LIMITS),
        "warnings": warnings,
    }


def _build_summary(planets, angle_output, phase, vedic, balance):
    """中文摘要：十星落座落宫、四轴、元素/模态主导、月相、Vedic 三要素。"""
    lines = []
    for p in planets:
        retro = "逆行" if p["retrograde"] else "顺行"
        lines.append("%s落%s %.2f°，第 %d 宫，%s（%.2f°/日）"
                     % (p["name"], p["sign_cn"], p["degree"], p["house"], retro, p["speed"]))
    asc = angle_output["asc"]
    mc = angle_output["mc"]
    lines.append("上升点 %s %.2f°，天顶 %s %.2f°"
                 % (asc["sign_cn"], asc["degree"], mc["sign_cn"], mc["degree"]))

    def _dominant(counter, cn_map):
        best = max(counter.items(), key=lambda kv: (kv[1], kv[0]))
        return "%s %d 颗" % (cn_map[best[0]], best[1])

    lines.append("元素分布：%s；模态分布：%s"
                 % (_dominant(balance["elements"], ELEMENT_CN),
                    _dominant(balance["modalities"], MODALITY_CN)))
    lines.append("半球分布：地平线上 %d / 下 %d；东 %d / 西 %d"
                 % (balance["hemispheres"]["above"], balance["hemispheres"]["below"],
                    balance["hemispheres"]["east"], balance["hemispheres"]["west"]))
    lines.append("月相：%s（日月黄经差 %.1f°，照亮比 %.2f）"
                 % (phase["phase"], phase["angle"], phase["illum"]))
    lines.append("Vedic（Lahiri）：太阳 %s，月亮 %s，Lagna %s；月亮宿 %s 第 %d pada，宿主星 %s"
                 % (vedic["sun_sign"], vedic["moon_sign"],
                    vedic["lagna"]["sign_cn"], vedic["nakshatra"]["name"],
                    vedic["nakshatra"]["pada"], vedic["nakshatra"]["ruler_cn"]))
    return lines


# ---------------------------------------------------------------------------
# 文本渲染
# ---------------------------------------------------------------------------


def _fmt_lon(block):
    """星座块格式化：兼容 planets/angles 的 ``degree`` 与宫头 _sign_block 的 ``sign_degree``。"""
    if "degree" in block:
        degree = block["degree"]
    elif "sign_degree" in block:
        degree = block["sign_degree"]
    else:
        degree = _norm360(block.get("lon", 0.0)) % 30.0
    return "%s %.2f°" % (block["sign_cn"], degree)


def render_natal_text(chart):
    """把 ``chart_natal`` 的结果渲染成中文文本（十星表 + 四轴 + 宫位 + 相位 + 分布 + Vedic）。"""
    lines = []
    lines.append("【西洋占星·本命盘】")
    inp = chart.get("input") or {}
    lines.append("  出生：%s %s（%s）　UTC：%s　东经 %.2f°　北纬 %.2f°"
                 % (inp.get("date") or "?", inp.get("time") or "?",
                    inp.get("zone") or "?", inp.get("utc") or "?",
                    inp.get("longitude") or 0.0, inp.get("latitude") or 0.0))
    lines.append("  黄道：回归黄道（tropical，当日春分点）；星历：Meeus 低精度解析星历")
    lines.append("")

    lines.append("【十星落座】")
    lines.append("  行星      黄经        星座度数      宫位   逆行  速度")
    for p in chart.get("planets") or []:
        lines.append("  %-4s %8.2f°  %-9s %5.2f°   第%2d宫  %-2s  %+.2f°/日"
                     % (p["name"], p["lon"], p["sign_cn"], p["degree"],
                        p["house"], "逆" if p["retrograde"] else "顺", p["speed"]))
    lines.append("")

    ang = chart.get("angles") or {}
    lines.append("【四轴】")
    for key, label in (("asc", "上升 ASC"), ("mc", "天顶 MC"),
                       ("desc", "下降 DESC"), ("ic", "天底 IC")):
        block = ang.get(key)
        if block:
            lines.append("  %s：%s" % (label, _fmt_lon(block)))
    lines.append("")

    houses = chart.get("houses") or {}
    systems = houses.get("systems") or {}
    lines.append("【宫位·整宫制】")
    ws = systems.get("whole_sign") or {"cusps": houses.get("cusps") or []}
    ws_cusps = ws.get("cusps") or []
    for i in range(0, len(ws_cusps), 4):
        part = []
        for j in range(i, min(i + 4, len(ws_cusps))):
            block = _sign_from_lon(ws_cusps[j])
            part.append("%2d宫 %s" % (j + 1, _fmt_lon(block)))
        lines.append("  " + "　".join(part))
    pl = systems.get("placidus") or {}
    if pl.get("available"):
        lines.append("【宫位·Placidus 半弧法】")
        pl_cusps = pl.get("cusps") or []
        for i in range(0, len(pl_cusps), 4):
            part = []
            for j in range(i, min(i + 4, len(pl_cusps))):
                block = _sign_from_lon(pl_cusps[j])
                part.append("%2d宫 %s" % (j + 1, _fmt_lon(block)))
            lines.append("  " + "　".join(part))
    else:
        lines.append("【宫位·Placidus】高纬退化，已回退整宫制")
    lines.append("")

    aspects = chart.get("aspects") or []
    lines.append("【相位】（容许度：发光体 8° / 个人星 6° / 外行星 5° / 角点 6°）")
    names = {}
    for p in chart.get("planets") or []:
        names[p["key"]] = p["name"]
    for a in chart.get("angles") or {}:
        names[a] = chart["angles"][a]["en"]
    if aspects:
        for asp in aspects:
            lines.append("  %s %s %s（%.1f°，容许度 %.2f°）"
                         % (names.get(asp["a"], asp["a"]), asp["type_cn"],
                            names.get(asp["b"], asp["b"]), asp["separation"], asp["orb"]))
    else:
        lines.append("  （本盘无容许度内相位）")
    lines.append("")

    bal = chart.get("balance") or {}
    elements = bal.get("elements") or {}
    modalities = bal.get("modalities") or {}
    hemi = bal.get("hemispheres") or {}
    lines.append("【元素·模态·半球】")
    lines.append("  元素：火 %d / 土 %d / 风 %d / 水 %d"
                 % (elements.get("fire", 0), elements.get("earth", 0),
                    elements.get("air", 0), elements.get("water", 0)))
    lines.append("  模态：基本 %d / 固定 %d / 变动 %d"
                 % (modalities.get("cardinal", 0), modalities.get("fixed", 0),
                    modalities.get("mutable", 0)))
    lines.append("  半球：地平线上 %d / 下 %d；东 %d / 西 %d"
                 % (hemi.get("above", 0), hemi.get("below", 0),
                    hemi.get("east", 0), hemi.get("west", 0)))
    lines.append("")

    phase = chart.get("moon_phase") or {}
    lines.append("【月相】%s（日月黄经差 %.1f°，照亮比 %.2f，细分：%s）"
                 % (phase.get("phase", "?"), phase.get("angle", 0.0),
                    phase.get("illum", 0.0), phase.get("phase8", "?")))
    lines.append("")

    vedic = chart.get("vedic") or {}
    lines.append("【印度占星（Vedic / Lahiri）】")
    lines.append("  Ayanamsa（岁差）：%.4f°（%s）"
                 % (vedic.get("ayanamsa", 0.0), vedic.get("ayanamsa_system", "")))
    lines.append("  太阳星座：%s　月亮星座：%s　Lagna：%s"
                 % (vedic.get("sun_sign", "?"), vedic.get("moon_sign", "?"),
                    (vedic.get("lagna") or {}).get("sign_cn", "?")))
    nak = vedic.get("nakshatra") or {}
    lines.append("  月亮 Nakshatra：%s（第 %s 宿）pada %s，宿主星 %s"
                 % (nak.get("name", "?"), nak.get("index", "?"),
                    nak.get("pada", "?"), nak.get("ruler_cn", "?")))
    lines.append("")

    lines.append("【综合摘要】")
    for item in chart.get("summary") or []:
        lines.append("  · " + item)
    lines.append("")
    lines.append("【方法学与局限】")
    lines.append("  " + str(chart.get("method") or MODEL))
    for item in chart.get("limits") or LIMITS:
        lines.append("  · " + item)
    for item in chart.get("warnings") or []:
        lines.append("  ! " + item)
    return "\n".join(lines)


def _sign_from_lon(lon):
    """黄经 → {sign, sign_cn, degree}（供渲染宫头用）。"""
    return _sign_block(lon)


# ---------------------------------------------------------------------------
# 便捷自检：python scripts/astrology.py --date YYYY-MM-DD --time HH:MM
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    date_text = "2004-06-12"
    time_text = "10:00"
    lon_text = "123.96"
    lat_text = "30.0"
    for i, item in enumerate(args):
        if item == "--date" and i + 1 < len(args):
            date_text = args[i + 1]
        elif item == "--time" and i + 1 < len(args):
            time_text = args[i + 1]
        elif item == "--longitude" and i + 1 < len(args):
            lon_text = args[i + 1]
        elif item == "--latitude" and i + 1 < len(args):
            lat_text = args[i + 1]
    demo_report = {
        "input": {
            "date": date_text,
            "time": time_text,
            "time_unknown": False,
            "zone": "UTC",
            "longitude": float(lon_text),
            "latitude": float(lat_text),
        },
        "time": {
            "utc": "%s %s:00" % (date_text, time_text),
            "civil": "%s %s:00" % (date_text, time_text),
            "utc_offset_hours": 0.0,
        },
    }
    demo_chart = chart_natal(demo_report)
    if "--json" in args:
        import json
        print(json.dumps(demo_chart, ensure_ascii=False, indent=2))
    else:
        print(render_natal_text(demo_chart))
