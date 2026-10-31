# -*- coding: utf-8 -*-
"""排盘核心：公历时刻 -> 四柱、藏干、十神、纳音、长生、空亡、大运、流年。

历法内核使用随包内置的 `lunar_python`（MIT，6tail；其节气/朔望内核移植自
寿星天文历 sxwnl，节气时刻与官方历书通常在数秒至十余秒内一致）。

**时间标尺（重要）**：内置历法的节气表固定按中国标准时（UTC+8）解释。因此：
  * 年柱/月柱、大运方向与起运，必须用「出生瞬间折算到 UTC+8 的钟表时间」判定；
  * 日柱/时柱，用「出生地实际采用的本地钟表时间」（标准时，或真太阳时）；
  * 出生在其他时区时，两者不同，`build(..., cst=...)` 负责分开处理。

其他约定：
  * 年柱以「立春」交节时刻为界，而非正月初一；
  * 月柱以十二「节」为界（立春/惊蛰/清明/立夏/芒种/小暑/立秋/白露/寒露/立冬/大雪/小寒）；
  * 日柱按儒略日连续干支推算，与 2000-01-07 = 甲子日 的纪元一致；
  * 时柱用五鼠遁：时干 = (日干序号 % 5 * 2 + 时支序号) % 10；
  * 晚子时两种流派：sect=1 换日柱（23:00 起算次日），sect=2 不换日柱
    （但时干仍按次日起，即传统「夜子时」）。
"""

import os
import sys
from datetime import datetime

_VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

from lunar_python import Solar, Lunar  # noqa: E402
from lunar_python.util import LunarUtil  # noqa: E402

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
# 地支藏干比例：本气 / 中气 / 余气（分析权重用）
HIDE_RATIO = {1: (1.0,), 2: (0.7, 0.3), 3: (0.6, 0.25, 0.15)}
ELEMENT_OF_GAN = dict(LunarUtil.WU_XING_GAN)
ELEMENT_OF_ZHI = dict(LunarUtil.WU_XING_ZHI)
NAYIN = dict(LunarUtil.NAYIN)
SHI_SHEN = dict(LunarUtil.SHI_SHEN)
HIDE_GAN = {k: list(v) for k, v in LunarUtil.ZHI_HIDE_GAN.items()}

# 十二长生（地势）顺序与日干起点，与 lunar_python 内部表一致
CHANG_SHENG = ("长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养")
CHANG_SHENG_OFFSET = {
    "甲": 1, "丙": 10, "戊": 10, "庚": 7, "壬": 4,
    "乙": 6, "丁": 9, "己": 9, "辛": 0, "癸": 3,
}

PILLAR_NAMES = ("年柱", "月柱", "日柱", "时柱")
PILLAR_SOURCES = ("祖上/幼年", "父母/兄弟/青年", "自身/配偶", "子女/晚年")

# 命宫/身宫公式使用的月序表（1=寅 … 12=丑），与 lunar_python 一致
_MONTH_ZHI = ("", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑")


def _jishi(day_gan, zhi):
    """某一日干在给定地支的十二长生（地势）。"""
    zhi_index = ZHI.index(zhi)
    day_index = GAN.index(day_gan)
    index = CHANG_SHENG_OFFSET[day_gan] + (zhi_index if day_index % 2 == 0 else -zhi_index)
    return CHANG_SHENG[index % 12]


def _ganzhi(gan, zhi):
    return gan + zhi


def _shishen(day_gan, gan):
    if gan == day_gan:
        return "比肩"
    return SHI_SHEN[day_gan + gan]


def _pillar(day_gan, gan, zhi, is_day=False):
    hidden = HIDE_GAN[zhi]
    return {
        "gan": gan,
        "zhi": zhi,
        "ganzhi": _ganzhi(gan, zhi),
        "wuxing_gan": ELEMENT_OF_GAN[gan],
        "wuxing_zhi": ELEMENT_OF_ZHI[zhi],
        "shishen_gan": "日主" if is_day else _shishen(day_gan, gan),
        "canggan": hidden,
        "canggan_shishen": [_shishen(day_gan, h) for h in hidden],
        "nayin": NAYIN[_ganzhi(gan, zhi)],
        "dishi": _jishi(day_gan, zhi),
    }


def _liunian_ganzhi(year):
    """流年干支（以立春为界的一年）。1984 = 甲子。"""
    index = (year - 4) % 60
    return GAN[index % 10] + ZHI[index % 12]


def _gan_from_formula(year_gan, offset):
    """命宫/身宫共用的天干推算式（与 lunar_python 一致，offset 为 1..12）。"""
    gi = (GAN.index(year_gan) + 1) * 2 + offset
    while gi > 10:
        gi -= 10
    return GAN[gi - 1]


def _taiyuan(month_gan, month_zhi):
    gi = (GAN.index(month_gan) + 1) % 10
    zi = (ZHI.index(month_zhi) + 3) % 12
    gz = GAN[gi] + ZHI[zi]
    return {"ganzhi": gz, "nayin": NAYIN[gz]}


def _minggong(year_gan, month_zhi, time_zhi):
    mi = _MONTH_ZHI.index(month_zhi)
    ti = _MONTH_ZHI.index(time_zhi)
    offset = mi + ti
    offset = 26 - offset if offset >= 14 else 14 - offset
    gz = _gan_from_formula(year_gan, offset) + _MONTH_ZHI[offset]
    return {"ganzhi": gz, "nayin": NAYIN[gz]}


def _shengong(year_gan, month_zhi, time_zhi):
    mi = _MONTH_ZHI.index(month_zhi)
    ti = ZHI.index(time_zhi)
    offset = mi + ti
    if offset > 12:
        offset -= 12
    gz = _gan_from_formula(year_gan, offset) + _MONTH_ZHI[offset]
    return {"ganzhi": gz, "nayin": NAYIN[gz]}


def build(year, month, day, hour, minute, second=0, sect=2, sex=1,
          dayun_count=9, qiyun_sect=2, focus_year=None, cst=None, display=None):
    """排盘。

    year..second 为「排盘采用的本地时间」（标准时或真太阳时），用于日柱/时柱；
    cst 为同一出生瞬间折算到北京时间（UTC+8）的钟表时间，用于年柱/月柱、
    大运方向与起运（因为节气表以 UTC+8 为标尺）。cst=None 表示二者相同。
    display 为「用于显示农历/节气文本」的本地时间（通常是标准时）；默认同 used。
    """
    solar_used = Solar.fromYmdHms(year, month, day, hour, minute, second)
    lunar_used = solar_used.getLunar()
    ec_used = lunar_used.getEightChar()
    ec_used.setSect(sect)

    if display is None:
        solar_display, lunar_display = solar_used, lunar_used
    else:
        solar_display = Solar.fromYmdHms(display.year, display.month, display.day,
                                         display.hour, display.minute, display.second)
        lunar_display = solar_display.getLunar()

    if cst is None:
        solar_cst, lunar_cst = solar_used, lunar_used
    else:
        solar_cst = Solar.fromYmdHms(cst.year, cst.month, cst.day,
                                     cst.hour, cst.minute, cst.second)
        lunar_cst = solar_cst.getLunar()
    ec_cst = lunar_cst.getEightChar()
    ec_cst.setSect(sect)

    year_gan, year_zhi = ec_cst.getYearGan(), ec_cst.getYearZhi()
    month_gan, month_zhi = ec_cst.getMonthGan(), ec_cst.getMonthZhi()
    day_gan, day_zhi = ec_used.getDayGan(), ec_used.getDayZhi()
    time_gan, time_zhi = ec_used.getTimeGan(), ec_used.getTimeZhi()

    gans = [year_gan, month_gan, day_gan, time_gan]
    zhis = [year_zhi, month_zhi, day_zhi, time_zhi]

    xun = [ec_cst.getYearXun(), ec_cst.getMonthXun(),
           ec_used.getDayXun(), ec_used.getTimeXun()]
    xunkong = [ec_cst.getYearXunKong(), ec_cst.getMonthXunKong(),
               ec_used.getDayXunKong(), ec_used.getTimeXunKong()]

    pillars = []
    for i in range(4):
        p = _pillar(day_gan, gans[i], zhis[i], is_day=(i == 2))
        p["name"] = PILLAR_NAMES[i]
        p["xiang"] = PILLAR_SOURCES[i]
        p["xun"] = xun[i]
        p["xunkong"] = xunkong[i]
        pillars.append(p)

    result = {
        "input": {
            "year": year, "month": month, "day": day,
            "hour": hour, "minute": minute, "second": second,
            "sect": sect, "sex": sex,
        },
        "solar": solar_used.toYmdHms(),
        "solar_display": solar_display.toYmdHms(),
        "solar_cst": solar_cst.toYmdHms(),
        "time_scales": {
            "used": "本地排盘时间（标准时或真太阳时）",
            "cst": "北京时间 UTC+8（用于年/月柱与起运）",
        },
        "lunar": {
            "text": lunar_display.toString(),
            "year": lunar_display.getYear(),
            "month": lunar_display.getMonth(),          # 负数表示闰月
            "day": lunar_display.getDay(),
            "month_cn": lunar_display.getMonthInChinese(),
            "day_cn": lunar_display.getDayInChinese(),
            "shengxiao": lunar_cst.getYearShengXiaoExact(),
        },
        "pillars": pillars,
        "day_gan": day_gan,
        "day_zhi": day_zhi,
        "day_gan_wuxing": ELEMENT_OF_GAN[day_gan],
        "taiyuan": _taiyuan(month_gan, month_zhi),
        "minggong": _minggong(year_gan, month_zhi, time_zhi),
        "shengong": _shengong(year_gan, month_zhi, time_zhi),
        "jieqi": _jieqi_context(
            lunar_cst, cst if cst is not None else datetime(year, month, day, hour, minute, second)),
    }

    # 大运 / 流年：方向与起运基于 UTC+8 标尺（ec_cst）
    if sex in (0, 1):
        yun = ec_cst.getYun(sex, qiyun_sect)
        start_solar = yun.getStartSolar()
        dayun = []
        for dy in yun.getDaYun(dayun_count + 1):
            if dy.getIndex() < 1:
                continue
            jiaoyun = start_solar.nextYear(10 * (dy.getIndex() - 1))
            dayun.append({
                "index": dy.getIndex(),
                "ganzhi": dy.getGanZhi(),
                "gan": dy.getGanZhi()[0],
                "zhi": dy.getGanZhi()[1],
                "shishen_gan": _shishen(day_gan, dy.getGanZhi()[0]),
                "shishen_zhi": [_shishen(day_gan, h) for h in HIDE_GAN[dy.getGanZhi()[1]]],
                "start_year": dy.getStartYear(),
                "end_year": dy.getEndYear(),
                "start_age": dy.getStartAge(),
                "end_age": dy.getEndAge(),
                "jiaoyun": jiaoyun.toYmdHms(),
            })
        result["dayun"] = {
            "forward": yun.isForward(),
            "start": {
                "year": yun.getStartYear(),
                "month": yun.getStartMonth(),
                "day": yun.getStartDay(),
                "hour": yun.getStartHour(),
                "text": "%d年%d个月%d天%d小时" % (
                    yun.getStartYear(), yun.getStartMonth(),
                    yun.getStartDay(), yun.getStartHour()),
                "solar": start_solar.toYmdHms(),
            },
            "list": dayun,
            "scale_note": "起运与交运时刻按北京时间（UTC+8）表示",
        }

    if focus_year is None:
        focus_year = 2026
    lns = _liunian_focus(day_gan, focus_year)
    if "dayun" in result:
        for ly in lns:
            ly["dayun_ganzhi"] = None
            for dy in result["dayun"]["list"]:
                if dy["start_year"] <= ly["year"] <= dy["end_year"]:
                    ly["dayun_ganzhi"] = dy["ganzhi"]
                    break
    result["liunian"] = lns
    return result


def _jieqi_context(lunar, cst_dt):
    """出生时刻前后的「节」与「气」。时刻均为北京时间（UTC+8）标尺。"""
    cur = "%04d-%02d-%02d %02d:%02d:%02d" % (
        cst_dt.year, cst_dt.month, cst_dt.day,
        cst_dt.hour, cst_dt.minute, cst_dt.second)
    prev_jie = lunar.getPrevJie()
    next_jie = lunar.getNextJie()
    prev_qi = lunar.getPrevJieQi()
    next_qi = lunar.getNextJieQi()
    return {
        "scale": "CST(UTC+8)",
        "prev_jie": {"name": prev_jie.getName(), "time": prev_jie.getSolar().toYmdHms()}
        if prev_jie else None,
        "next_jie": {"name": next_jie.getName(), "time": next_jie.getSolar().toYmdHms()}
        if next_jie else None,
        "prev_qi": {"name": prev_qi.getName(), "time": prev_qi.getSolar().toYmdHms()}
        if prev_qi else None,
        "next_qi": {"name": next_qi.getName(), "time": next_qi.getSolar().toYmdHms()}
        if next_qi else None,
        "now": cur,
    }


def _liunian_focus(day_gan, focus_year, span=6):
    years = []
    for y in range(focus_year - span, focus_year + span + 1):
        gz = _liunian_ganzhi(y)
        gan, zhi = gz[0], gz[1]
        years.append({
            "year": y,
            "ganzhi": gz,
            "shishen_gan": _shishen(day_gan, gan),
            "shishen_zhi": [_shishen(day_gan, h) for h in HIDE_GAN[zhi]],
            "is_focus": y == focus_year,
        })
    return years


def _year_jies(year):
    """某一流年的 12 个「节」时刻（立春起，含次年立春作为丑月终点），共 13 个。"""
    out = []
    cur = Solar.fromYmd(year, 2, 1)
    for _ in range(13):
        jq = cur.getLunar().getNextJie()
        out.append((jq.getName(), jq.getSolar().toYmdHms()))
        s = jq.getSolar()
        cur = Solar.fromYmdHms(s.getYear(), s.getMonth(), s.getDay(), 12, 0, 0).next(1)
    return out


def liuyue(day_gan, year):
    """某一流年的流月（以节气为界，寅月起），附带每月的节气区间。"""
    out = []
    year_gan = _liunian_ganzhi(year)[0]
    base = (GAN.index(year_gan) % 5) * 2 + 2  # 五虎遁：寅月天干
    month_zhi = ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"]
    try:
        jies = _year_jies(year)
    except Exception:
        jies = None
    for i, zhi in enumerate(month_zhi):
        gan = GAN[(base + i) % 10]
        item = {
            "index": i + 1,
            "ganzhi": gan + zhi,
            "shishen_gan": _shishen(day_gan, gan),
            "shishen_zhi": [_shishen(day_gan, h) for h in HIDE_GAN[zhi]],
        }
        if jies and len(jies) > i + 1:
            item["start_jie"] = jies[i][0]
            item["start"] = jies[i][1]
            item["end"] = jies[i + 1][1]
        out.append(item)
    return out


def lunar_to_solar(year, month, day, hour=0, minute=0, second=0):
    """农历 -> 公历。month 为负表示闰月；返回 (y, m, d, h, mi, s)。"""
    lunar = Lunar.fromYmdHms(year, month, day, hour, minute, second)
    solar = lunar.getSolar()
    return (solar.getYear(), solar.getMonth(), solar.getDay(),
            solar.getHour(), solar.getMinute(), solar.getSecond())
