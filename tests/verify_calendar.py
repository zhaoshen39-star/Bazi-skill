# -*- coding: utf-8 -*-
"""排盘历法层独立交叉验证（tests/verify_calendar.py）

设计原则
========
本脚本用**独立方法**交叉验证排盘历法层，不复读 chart.py / vendor 的实现逻辑：

1. 日柱：Fliegel–Van Flandern 儒略日公式 JDN 独立推算，配合脚本自身声明的锚点
   「2000-01-07 = 甲子日，JD 连续干支」推 60 甲子，与 chart.build 比对。
2. 时柱：五鼠遁「时干序 = (日干序 % 5 * 2 + 时支序) % 10」，
   时支序 = ((hour + 1) // 2) % 12；23 点子时按「次日日干起子时」处理。
3. 年柱/月柱：用 chart._year_jies(year) 取「节」的精确时刻，验证交节前 1 分钟与
   交节时刻的月柱不同、年柱仅在立春改变、月干符合五虎遁；
   另扫描 1900–2100 全部年份的 13 个节气点、12 节间隔与单调性，
   并用 lunar 节气表交叉核对，验证 24 节气相邻间隔。
4. 大运：独立按「阳年男 / 阴年女顺行，阴年男 / 阳年女逆行」判方向；
   由月柱干支按 60 循环 ±1..9 推大运序列；独立按节气时刻用
   「3 天 = 1 岁、1 天 = 4 个月、1 时辰（2 小时）= 10 天」换算起运岁数。
   舍入约定：vendor 的 Solar.subtractMinute 只取到分钟并丢弃秒（两端向下取整
   到分钟），换算余量全部整数向下取整（divmod），本脚本按同约定独立复算。
5. 真太阳时/时区：经度修正 = (经度 − 标准经线) * 4 分钟；均时差 NOAA 公式
   幅度 < 17 分钟；中国 1986–1991 夏令时回退 1 小时；zoneinfo 可用性。
6. 边界：23 时子时的 sect1/sect2 日柱差异、22:59 / 23:00 / 00:00 归属、
   闰日 2000-02-29、1900/2000/2100 闰年规则、1900/2100 端点日柱连续性。
7. 表完整性：藏干表、纳音表、十二长生表、十神表。

任务规格勘误（重要，非 scripts 逻辑错误）
========================================
任务书写「每年 12 个『节』间隔在 14.5~16.5 天」——该区间实际是 **24 个节气**
的相邻间隔（实测 14.71~15.73 天）；12 个「节」相隔约一个朔望月，实测约
29.2~31.6 天。本脚本按真实历法验证两者：24 节气间隔 ∈ [14.5, 16.5]，
12 节间隔 ∈ [29, 32]，并将其作为「规格笔误」标注，而非脚本 bug。

约定事项（流派差异，不做硬性 bug 判定）
======================================
* 23:00–23:59 出生：sect=1（晚子时换日）日柱算次日，sect=2（晚子时不换日）
  日柱仍算当日；两派的**时柱完全一致**，时干一律按「次日日干」起子时
  （传统夜子时法）。此为流派约定，与两派日柱定义均自洽，不算 bug。
* 起运岁数的「年/月/天/时辰」四舍五入：本脚本按 vendor 的截断取整约定复算，
  若换用四舍五入流派可能存在 ±1 岁差异，属约定差异。

结论
====
本次验证未发现 scripts/ 中的真实逻辑错误（各 section 均有说明）。
运行：  cd bazi-v3 && python tests\verify_calendar.py
"""

import os
import random
import sys
import time
from datetime import date, datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
for _p in (os.path.join(SKILL, "scripts"), os.path.join(SKILL, "scripts", "vendor")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import chart                                      # noqa: E402
import bazi                                       # noqa: E402
from lunar_python import Solar                    # noqa: E402
from lunar_python.util import LunarUtil           # noqa: E402

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
JIA_ZI = [GAN[i % 10] + ZHI[i % 12] for i in range(60)]
ZONE = "Asia/Shanghai"
JDN_ANCHOR = 2451551           # 2000-01-07 的 JDN，当日为甲子日（chart.py 声明锚点）
JDN_ANCHOR_DATE = (2000, 1, 7)
GAN_YANG = "甲丙戊庚壬"
JIE_NAMES = ["立春", "惊蛰", "清明", "立夏", "芒种", "小暑",
             "立秋", "白露", "寒露", "立冬", "大雪", "小寒", "立春"]

CHECKS = 0
FAILS = []


# ---------------------------------------------------------------------------
# 基础断言设施
# ---------------------------------------------------------------------------
def check(name, ok, detail=""):
    global CHECKS
    CHECKS += 1
    if ok:
        print("PASS  " + name)
    else:
        msg = name if not detail else "%s  ->  %s" % (name, detail)
        print("FAIL  " + msg)
        FAILS.append(msg)


# ---------------------------------------------------------------------------
# 独立算法与工具
# ---------------------------------------------------------------------------
def jdn(y, m, d):
    """Fliegel–Van Flandern 儒略日公式（公历，返回整数 JDN）。"""
    a = (14 - m) // 12
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    return d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045


def gz_from_jdn(j):
    idx = (j - JDN_ANCHOR) % 60
    return JIA_ZI[idx]


def day_gz(y, m, d):
    """由 JDN + 锚点独立推日柱。"""
    return gz_from_jdn(jdn(y, m, d))


def month_len(y, m):
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    return (date(ny, nm, 1) - date(y, m, 1)).days


def parse_dt(value):
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    raise ValueError("无法解析时间: %r" % value)


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def build(y, m, d, h=12, mi=0, s=0, **kw):
    return chart.build(y, m, d, h, mi, s, **kw)


def pillars(r):
    return [p["ganzhi"] for p in r["pillars"]]


def trunc_minute(dt):
    return dt.replace(second=0, microsecond=0)


def is_leap(y):
    return (y % 4 == 0 and y % 100 != 0) or y % 400 == 0


def add_years(dt, years):
    """等价于 vendor Solar.nextYear：2 月 29 日在非闰年夹到 28 日。"""
    y = dt.year + years
    d = dt.day
    if dt.month == 2 and d == 29 and not is_leap(y):
        d = 28
    return dt.replace(year=y, day=d)


def add_months(dt, months):
    """等价于 vendor Solar.nextMonth：目标月天数不足时夹到月末。"""
    total = dt.month - 1 + months
    y = dt.year + total // 12
    m = total % 12 + 1
    return dt.replace(year=y, month=m, day=min(dt.day, month_len(y, m)))


def date_seq(y, m, d, n):
    d0 = date(y, m, d)
    return [(d0 + timedelta(days=i)).timetuple()[:3] for i in range(n)]


def time_pillar_by_wushu(day_cycle, hour):
    """五鼠遁独立推算时柱。day_cycle 为「该日（未过 23 点）日柱」在 60 甲子中的序号。

    23 点属于次日子时，时干按次日日干起（sect1/sect2 时干一致）。
    """
    zhi_i = ((hour + 1) // 2) % 12
    dgan_i = ((day_cycle + (1 if hour == 23 else 0)) % 60) % 10
    gan_i = ((dgan_i % 5) * 2 + zhi_i) % 10
    return GAN[gan_i] + ZHI[zhi_i]


# ===========================================================================
# 1. 日柱
# ===========================================================================
def section_day_pillar():
    print("\n== 1. 日柱：JDN 独立推算 vs chart.build ==")
    j2000, j1900, j2100 = jdn(2000, 1, 7), jdn(1900, 1, 1), jdn(2100, 12, 31)
    check("1.0 JDN 公式常量（2000-01-07=2451551 / 1900-01-01=2415021 / 2100-12-31=2488434）",
          (j2000, j1900, j2100) == (2451551, 2415021, 2488434),
          "jdn(2000-01-07)=%d jdn(1900-01-01)=%d jdn(2100-12-31)=%d" % (j2000, j1900, j2100))

    anchors = [
        ((1900, 1, 1), "甲戌"),
        ((1949, 10, 1), "甲子"),
        ((2000, 1, 7), "甲子"),
        ((2008, 8, 8), "庚辰"),
        ((2024, 2, 10), "甲辰"),
    ]
    for (y, m, d), exp in anchors:
        got = build(y, m, d, 12, 0, 0, sect=2, sex=None)["pillars"][2]["ganzhi"]
        ind = day_gz(y, m, d)
        check("1.%d 日柱锚点 %04d-%02d-%02d = %s" % (y, y, m, d, exp),
              got == exp and ind == exp,
              "chart.build=%s 独立JDN=%s 期望=%s" % (got, ind, exp))

    rng = random.Random(20261028)
    dates = []
    while len(dates) < 500:
        y = rng.randint(1900, 2100)
        m = rng.randint(1, 12)
        dates.append((y, m, rng.randint(1, month_len(y, m)),
                      rng.randint(0, 22), rng.randint(0, 59)))  # 避开 23 点

    for b in range(10):
        batch = dates[b * 50:(b + 1) * 50]
        bad = []
        for (y, m, d, h, mi) in batch:
            got = build(y, m, d, h, mi, 0, sect=2, sex=None)["pillars"][2]["ganzhi"]
            exp = day_gz(y, m, d)
            if got != exp and len(bad) < 3:
                bad.append("%04d-%02d-%02d %02d:%02d 期望=%s 实际=%s" % (y, m, d, h, mi, exp, got))
        check("1.%d 随机日期批次 %d（1900–2100，%d 个）日柱一致"
              % (10 + b, b + 1, len(batch)),
              not bad, "；".join(bad))

    bad = []
    for (y, m, d, h, mi) in dates[:12]:
        s1 = build(y, m, d, h, mi, 0, sect=1, sex=None)["pillars"][2]["ganzhi"]
        s2 = build(y, m, d, h, mi, 0, sect=2, sex=None)["pillars"][2]["ganzhi"]
        exp = day_gz(y, m, d)
        if s1 != s2 or s2 != exp:
            bad.append("%04d-%02d-%02d %02d:%02d sect1=%s sect2=%s 期望=%s"
                       % (y, m, d, h, mi, s1, s2, exp))
    check("1.20 sect=1 与 sect=2 在非 23 点时对日柱一致（12 个样本）", not bad, "；".join(bad[:3]))


# ===========================================================================
# 2. 时柱
# ===========================================================================
def section_time_pillar():
    print("\n== 2. 时柱：五鼠遁独立推算 vs chart.build ==")
    test_dates = [(1900, 1, 1), (1988, 6, 1), (2000, 1, 7),
                  (2024, 2, 4), (2050, 7, 15), (2100, 12, 31)]
    for (y, m, d) in test_dates:
        cyc = JIA_ZI.index(day_gz(y, m, d))
        bad_zhi, bad_gan = [], []
        for h in range(24):
            got = build(y, m, d, h, 0, 0, sect=2, sex=None)["pillars"][3]["ganzhi"]
            exp = time_pillar_by_wushu(cyc, h)
            if got[1] != exp[1] and len(bad_zhi) < 3:
                bad_zhi.append("%02d 时 期望支=%s 实际=%s" % (h, exp[1], got[1]))
            if got[0] != exp[0] and len(bad_gan) < 3:
                bad_gan.append("%02d 时 期望干=%s 实际=%s" % (h, exp[0], got[0]))
        check("2 时柱-时支 %04d-%02d-%02d 全部 24 时辰" % (y, m, d), not bad_zhi,
              "；".join(bad_zhi))
        check("2 时柱-时干 %04d-%02d-%02d 五鼠遁 24 时辰" % (y, m, d), not bad_gan,
              "；".join(bad_gan))

    for (y, m, d) in test_dates[:4]:
        cyc = JIA_ZI.index(day_gz(y, m, d))
        exp = time_pillar_by_wushu(cyc, 23)
        r1 = build(y, m, d, 23, 0, 0, sect=1, sex=None)["pillars"][3]["ganzhi"]
        r2 = build(y, m, d, 23, 0, 0, sect=2, sex=None)["pillars"][3]["ganzhi"]
        check("2 时柱 23:00 子时 %04d-%02d-%02d 两派一致且按次日干起" % (y, m, d),
              r1 == exp and r2 == exp, "sect1=%s sect2=%s 期望=%s" % (r1, r2, exp))


# ===========================================================================
# 3. 年柱 / 月柱 / 节气
# ===========================================================================
def section_year_month_jieqi():
    print("\n== 3. 年柱/月柱与节气 ==")
    # 3.1 交节边界：交节前 1 分钟 vs 交节时刻；年柱仅立春变；月干五虎遁
    for y in (1900, 2000, 2024):
        jies = [(n, parse_dt(t)) for (n, t) in chart._year_jies(y)]
        year_gan_i = (y - 4) % 10
        prev_year_gan_i = (y - 1 - 4) % 10
        base = (year_gan_i % 5) * 2 + 2          # 五虎遁：寅月天干序号
        exp_year_gz = GAN[year_gan_i] + ZHI[(y - 4) % 12]
        exp_prev_year_gz = GAN[prev_year_gan_i] + ZHI[(y - 1 - 4) % 12]
        for i, (name, t) in enumerate(jies[:12]):
            before = t - timedelta(minutes=1)
            pb = build(before.year, before.month, before.day,
                       before.hour, before.minute, before.second, sect=2, sex=None)
            pa = build(t.year, t.month, t.day, t.hour, t.minute, t.second, sect=2, sex=None)
            m_before, m_at = pillars(pb)[1], pillars(pa)[1]
            y_before, y_at = pillars(pb)[0], pillars(pa)[0]
            exp_zhi = ZHI[(2 + i) % 12]
            exp_gan = GAN[(base + i) % 10]
            ok = (m_at[0] == exp_gan and m_at[1] == exp_zhi and m_before != m_at)
            if i == 0:
                ok = ok and y_at == exp_year_gz and y_before == exp_prev_year_gz
            else:
                ok = ok and y_at == exp_year_gz and y_before == exp_year_gz
            check("3.1 %04d %s（%s）交节前后：月柱 %s→%s 年柱 %s→%s"
                  % (y, name, t.strftime("%m-%d %H:%M:%S"), m_before, m_at, y_before, y_at),
                  ok, "期望月柱=%s 期望年柱=%s" % (exp_gan + exp_zhi, exp_year_gz))

    # 3.2 1900–2100 全扫描：_year_jies 结构与单调性
    bad_count, bad_order, bad_mono, bad_cont, bad_interval = [], [], [], [], []
    intervals = []
    prev_last = None
    for y in range(1900, 2101):
        js = chart._year_jies(y)
        if len(js) != 13:
            bad_count.append("y=%d len=%d" % (y, len(js)))
            continue
        names = [n for (n, _) in js]
        times = [parse_dt(t) for (_, t) in js]
        if names != JIE_NAMES:
            bad_order.append("y=%d names=%s" % (y, names))
        if times != sorted(times):
            bad_mono.append("y=%d" % y)
        if prev_last is not None and times[0] != prev_last:
            bad_cont.append("y=%d 立春 %s != 上年末 %s" % (y, times[0], prev_last))
        prev_last = times[-1]
        for a, b in zip(times[:11], times[1:12]):
            gap = (b - a).total_seconds() / 86400.0
            intervals.append(gap)
            if not (29.0 <= gap <= 32.0):
                bad_interval.append("y=%d 节间隔=%.3f 天" % (y, gap))

    check("3.2 1900–2100 每年 13 个节气点且名称顺序固定", not bad_count and not bad_order,
          "；".join(bad_count[:3] + bad_order[:3]))
    check("3.3 1900–2100 每年节气时刻严格单调递增", not bad_mono, "；".join(bad_mono[:3]))
    check("3.4 年界连续（上年末立春 == 次年初立春）", not bad_cont, "；".join(bad_cont[:3]))
    check("3.5 12 个「节」相邻间隔在 29~32 天（实测 %.2f~%.2f 天）"
          % (min(intervals), max(intervals)),
          not bad_interval, "；".join(bad_interval[:3]))

    # 3.6 24 节气相邻间隔 14.5~16.5 天（lunar 节气表独立来源）
    for y in (1900, 1950, 1988, 2000, 2024, 2050, 2100):
        try:
            tb = Solar.fromYmd(y, 6, 1).getLunar().getJieQiTable()
            ts = sorted(parse_dt(s.toYmdHms()) for s in tb.values())
            gaps = [(b - a).total_seconds() / 86400.0 for a, b in zip(ts, ts[1:])]
            ok = bool(gaps) and all(14.5 <= g <= 16.5 for g in gaps)
            check("3.6 %d 年 24 节气相邻间隔 ∈ [14.5, 16.5] 天（实测 %.3f~%.3f）"
                  % (y, min(gaps), max(gaps)), ok,
                  "越界=%s" % [round(g, 3) for g in gaps if not (14.5 <= g <= 16.5)][:3])
        except Exception as e:  # pragma: no cover
            check("3.6 %d 年 24 节气相邻间隔" % y, False, "取节气表异常: %r" % e)

    # 3.7 _year_jies 与 lunar 节气表交叉核对（用 (名称,时间) 列表避免别名覆盖）
    alias = {"DA_XUE": "大雪", "DONG_ZHI": "冬至", "XIAO_HAN": "小寒", "DA_HAN": "大寒",
             "LI_CHUN": "立春", "YU_SHUI": "雨水", "JING_ZHE": "惊蛰"}
    for y in (1900, 2000, 2100):
        tb = Solar.fromYmd(y, 6, 1).getLunar().getJieQiTable()
        table_pairs = [(alias.get(k, k), parse_dt(v.toYmdHms())) for (k, v) in tb.items()]
        missing = []
        for (name, ts) in chart._year_jies(y):
            t = parse_dt(ts)
            if not any(n == name and t == tt for (n, tt) in table_pairs):
                missing.append("%s@%s" % (name, ts))
        check("3.7 %d 年 _year_jies 与 lunar 节气表逐项一致（13 个节）" % y,
              not missing, "缺失=%s" % missing[:3])


# ===========================================================================
# 4. 大运
# ===========================================================================
def jie_points_around(year):
    pts = {}
    for yy in (year - 1, year):
        for (name, ts) in chart._year_jies(yy):
            pts[parse_dt(ts)] = name
    return sorted(pts.items())


def qiyun_expected(birth, forward):
    """独立按节气时刻 + sect=2 换算规则推起运（年,月,天,时辰）与交运公历时刻。

    舍入：两端的秒一律丢弃（对齐 vendor Solar.subtractMinute 只取分钟），
    差值分钟数对 4320 分/360 分/12 分做整数向下取整。
    """
    pts = jie_points_around(birth.year)
    prev_jie = None
    next_jie = None
    for t, _name in pts:
        if t <= birth:
            prev_jie = t
        elif next_jie is None:
            next_jie = t
    if prev_jie is None or next_jie is None:
        return None, None
    start_jie, end_jie = (birth, next_jie) if forward else (prev_jie, birth)
    minutes = int((trunc_minute(end_jie) - trunc_minute(start_jie)).total_seconds() // 60)
    years, rem = divmod(minutes, 4320)        # 4320 分 = 3 天 = 1 岁
    months, rem = divmod(rem, 360)            # 360 分 = 6 小时 = 1 个月
    days, rem = divmod(rem, 12)               # 12 分 = 1 天（虚日）
    hours = rem * 2                           # 余 1 分 ≈ 2 小时（时辰数）
    start = add_years(birth, years)
    start = add_months(start, months)
    start = start + timedelta(days=days)
    start = start + timedelta(hours=hours)
    return (years, months, days, hours), start


DAYUN_CASES = [
    # (出生公历, sex(1=男/0=女), 期望年柱, 期望方向)  —— 覆盖阳男/阳女/阴男/阴女
    ((1990, 6, 15, 11, 0, 0), 1, "庚午", True),    # 阳年男 → 顺行
    ((1990, 6, 15, 11, 0, 0), 0, "庚午", False),   # 阳年女 → 逆行
    ((1985, 3, 3, 8, 0, 0), 1, "乙丑", False),     # 阴年男 → 逆行
    ((1986, 8, 8, 20, 0, 0), 0, "丙寅", False),    # 阳年女 → 逆行
    ((1990, 1, 15, 10, 0, 0), 1, "己巳", False),   # 立春前出生（年柱按上一年）阴年男 → 逆行
    ((1992, 11, 2, 2, 0, 0), 1, "壬申", True),     # 阳年男 → 顺行
    ((2000, 12, 31, 23, 0, 0), 1, "庚辰", True),   # 23 时出生，阳年男 → 顺行
    ((1955, 7, 7, 6, 30, 0), 0, "乙未", True),     # 阴年女 → 顺行
    ((2024, 2, 4, 16, 27, 7), 1, "甲辰", True),    # 恰好交立春时刻，阳年男 → 顺行
    ((2024, 2, 4, 16, 27, 7), 0, "甲辰", False),   # 恰好交立春时刻，阳年女 → 逆行
]


def section_dayun():
    print("\n== 4. 大运方向 / 干支 / 起运换算 ==")
    for ci, ((y, m, d, h, mi, s), sex, exp_year, exp_forward) in enumerate(DAYUN_CASES):
        tag = "%04d-%02d-%02d %02d:%02d:%02d %s" % (
            y, m, d, h, mi, s, "男" if sex == 1 else "女")
        r = chart.build(y, m, d, h, mi, s, sex=sex)
        ps = pillars(r)
        yp = ps[0]
        check("4.1.%d 年柱 %s = %s" % (ci + 1, tag, exp_year), yp == exp_year,
              "实际=%s 期望=%s" % (yp, exp_year))

        yang = yp[0] in GAN_YANG
        exp_fwd = (yang and sex == 1) or ((not yang) and sex == 0)
        dy = r["dayun"]
        check("4.2.%d 大运方向 %s（%s年%s）顺行" % (
            ci + 1, tag, "阳" if yang else "阴", "男" if sex == 1 else "女"),
            dy["forward"] == exp_fwd and exp_fwd == exp_forward,
            "chart.forward=%s 独立推算=%s 期望=%s" % (dy["forward"], exp_fwd, exp_forward))

        lst = dy["list"]
        month_gz = ps[1]
        mci = JIA_ZI.index(month_gz)
        exp_seq = [JIA_ZI[(mci + (k if exp_fwd else -k)) % 60] for k in range(1, 10)]
        got_seq = [it["ganzhi"] for it in lst]
        check("4.3.%d 大运干支序列（月柱 %s ±1..9，%s行）"
              % (ci + 1, month_gz, "顺" if exp_fwd else "逆"),
              got_seq == exp_seq, "期望=%s 实际=%s" % (exp_seq, got_seq))

        birth_cst_year = y
        start_solar = parse_dt(dy["start"]["solar"])
        bad = []
        if len(lst) != 9:
            bad.append("步数=%d 期望 9" % len(lst))
        prev_end = None
        for k, it in enumerate(lst, 1):
            if it["end_year"] - it["start_year"] != 9:
                bad.append("第%d步跨年=%d" % (k, it["end_year"] - it["start_year"]))
            if it["end_age"] - it["start_age"] != 9:
                bad.append("第%d步跨龄=%d" % (k, it["end_age"] - it["start_age"]))
            if it["start_age"] != it["start_year"] - birth_cst_year + 1:
                bad.append("第%d步 start_age=%d 期望=%d"
                           % (k, it["start_age"], it["start_year"] - birth_cst_year + 1))
            if prev_end is not None and it["start_year"] != prev_end + 1:
                bad.append("第%d步 start_year=%d 期望=%d"
                           % (k, it["start_year"], prev_end + 1))
            if not bad and k == 1 and it["start_year"] != start_solar.year:
                bad.append("首步 start_year=%d != 交运年 %d"
                           % (it["start_year"], start_solar.year))
            prev_end = it["end_year"]
        check("4.4.%d 大运结构：9 步连续、每步 10 年、start_age/end_age 与出生年自洽"
              % (ci + 1), not bad, "；".join(bad[:3]))

        bad = []
        for k, it in enumerate(lst):
            jy = parse_dt(it["jiaoyun"])
            if jy.year != it["start_year"]:
                bad.append("第%d步 jiaoyun年=%d start_year=%d"
                           % (k + 1, jy.year, it["start_year"]))
            if (jy.year - start_solar.year) != 10 * k:
                bad.append("第%d步 jiaoyun 与起运年差 %d 年" % (k + 1, jy.year - start_solar.year))
            if k > 0 and (jy.month, jy.day) != (start_solar.month, start_solar.day):
                bad.append("第%d步 jiaoyun 月日=%02d-%02d 期望 %02d-%02d"
                           % (k + 1, jy.month, jy.day, start_solar.month, start_solar.day))
        check("4.5.%d 交运日期 jiaoyun = 起运时刻 + 10*(i−1) 年且落在对应 start_year"
              % (ci + 1), not bad, "；".join(bad[:3]))

        birth = datetime(y, m, d, h, mi, s)
        exp_tuple, exp_start = qiyun_expected(birth, exp_fwd)
        got_tuple = (dy["start"]["year"], dy["start"]["month"],
                     dy["start"]["day"], dy["start"]["hour"])
        got_start = parse_dt(dy["start"]["solar"])
        ok = exp_tuple is not None and got_tuple == exp_tuple \
            and trunc_minute(got_start) == trunc_minute(exp_start)
        check("4.6.%d 起运换算（3 天=1 岁，1 天=4 个月，1 时辰=10 天）%s"
              % (ci + 1, tag), ok,
              "chart=%s @%s 独立=%s @%s"
              % (got_tuple, dy["start"]["solar"], exp_tuple, exp_start))


# ===========================================================================
# 5. 真太阳时 / 时区
# ===========================================================================
def section_true_solar():
    print("\n== 5. 真太阳时 / 时区 / 均时差 ==")
    rt = bazi.resolve_time(2000, 1, 7, 12, 0, 0, ZONE, None, False)
    check("5.1 Asia/Shanghai 2000-01-07 12:00 标准时解析",
          fnum(rt["utc_offset_hours"]) == 8.0 and fnum(rt["dst_hours"]) == 0.0
          and fnum(rt["standard_offset_hours"]) == 8.0 and rt["used_kind"] == "standard"
          and parse_dt(rt["used"]) == datetime(2000, 1, 7, 12, 0)
          and parse_dt(rt["standard"]) == datetime(2000, 1, 7, 12, 0),
          "used=%r standard=%r offset=%r" % (rt.get("used"), rt.get("standard"),
                                             rt.get("utc_offset_hours")))

    rtz = bazi.resolve_time(2000, 1, 7, 12, 0, 0, "UTC", None, False)
    check("5.2 UTC 时区：cst = 本地 + 8 小时",
          fnum(rtz["utc_offset_hours"]) == 0.0 and rtz["cst_dt"] == datetime(2000, 1, 7, 20, 0),
          "cst=%r" % (rtz.get("cst"),))

    rtn = bazi.resolve_time(2000, 1, 7, 0, 0, 0, "America/New_York", None, False)
    check("5.3 America/New_York 2000-01-07 00:00 → cst 13:00",
          fnum(rtn["utc_offset_hours"]) == -5.0 and rtn["cst_dt"] == datetime(2000, 1, 7, 13, 0),
          "offset=%r cst=%r" % (rtn.get("utc_offset_hours"), rtn.get("cst")))

    bad = []
    for (zone, args) in (("UTC", (2000, 1, 7, 12, 0)), ("America/New_York", (2000, 1, 7, 0, 0)),
                         ("Asia/Shanghai", (2000, 1, 7, 12, 0)), ("Europe/London", (2000, 7, 1, 12, 0))):
        rt2 = bazi.resolve_time(args[0], args[1], args[2], args[3], args[4], 0, zone, None, False)
        exp = rt2["utc_dt"].replace(tzinfo=None) + timedelta(hours=8)
        if rt2["cst_dt"] != exp:
            bad.append("%s: cst=%s 期望=%s" % (zone, rt2["cst_dt"], exp))
    check("5.4 cst = utc + 8 小时（多时区）", not bad, "；".join(bad))

    # 中国夏令时 1986–1991
    for y in range(1986, 1992):
        rt3 = bazi.resolve_time(y, 7, 1, 12, 0, 0, ZONE, None, False)
        ok = (fnum(rt3["utc_offset_hours"]) == 9.0 and fnum(rt3["dst_hours"]) == 1.0
              and fnum(rt3["standard_offset_hours"]) == 8.0
              and parse_dt(rt3["used"]) == datetime(y, 7, 1, 11, 0)
              and parse_dt(rt3["standard"]) == datetime(y, 7, 1, 11, 0))
        check("5.5.%d 中国夏令时 %d-07-01 12:00 回退 1 小时为 11:00 标准时" % (y, y), ok,
              "offset=%r dst=%r standard=%r used=%r"
              % (rt3.get("utc_offset_hours"), rt3.get("dst_hours"),
                 rt3.get("standard_offset_hours"), rt3.get("used")))

    for y in (1985, 1992):
        rt4 = bazi.resolve_time(y, 7, 1, 12, 0, 0, ZONE, None, False)
        check("5.6.%d 中国非夏令时年份 %d-07-01 12:00 保持原时间" % (y, y),
              fnum(rt4["utc_offset_hours"]) == 8.0 and fnum(rt4["dst_hours"]) == 0.0
              and parse_dt(rt4["used"]) == datetime(y, 7, 1, 12, 0),
              "offset=%r dst=%r used=%r"
              % (rt4.get("utc_offset_hours"), rt4.get("dst_hours"), rt4.get("used")))

    rt5 = bazi.resolve_time(1986, 1, 15, 12, 0, 0, ZONE, None, False)
    check("5.7 1986-01-15 冬令时 offset=8 且无 DST",
          fnum(rt5["utc_offset_hours"]) == 8.0 and fnum(rt5["dst_hours"]) == 0.0
          and parse_dt(rt5["used"]) == datetime(1986, 1, 15, 12, 0),
          "offset=%r dst=%r" % (rt5.get("utc_offset_hours"), rt5.get("dst_hours")))

    rt6 = bazi.resolve_time(1988, 6, 1, 12, 0, 0, ZONE, None, False)
    check("5.8 DST 期间记录附 dst_note 说明", "夏令时" in (rt6.get("dst_note") or ""),
          "dst_note=%r" % (rt6.get("dst_note"),))

    rt7 = bazi.resolve_time(1988, 4, 17, 2, 0, 0, ZONE, None, False)
    check("5.9 夏令时拨快缺口（1988-04-17 02:00）产生警告",
          any("跳过" in w for w in rt7["warnings"]), "warnings=%s" % rt7["warnings"])
    rt8 = bazi.resolve_time(1988, 9, 11, 1, 0, 0, ZONE, None, False)
    check("5.10 夏令时回拨重叠（1988-09-11 01:00）产生歧义警告",
          any("歧义" in w for w in rt8["warnings"]), "warnings=%s" % rt8["warnings"])

    try:
        bazi.resolve_time(2000, 1, 1, 0, 0, 0, "Not/AZone", None, False)
        bad_zone = "未抛 SystemExit"
    except SystemExit as e:
        bad_zone = "" if "时区" in str(e) else "SystemExit 信息=%r" % str(e)
    check("5.11 未知时区抛 SystemExit（含提示）", not bad_zone, bad_zone)

    try:
        bazi.resolve_time(2000, 1, 1, 0, 0, 0, ZONE, None, True)
        miss_lon = "未抛 SystemExit"
    except SystemExit as e:
        miss_lon = "" if ("经度" in str(e) or "longitude" in str(e).lower()) else "信息=%r" % str(e)
    check("5.12 真太阳时缺经度抛 SystemExit", not miss_lon, miss_lon)

    # 经度修正 = (经度 − 120) * 4 分钟
    for i, lon in enumerate((75.0, 87.5, 100.0, 116.4, 120.0, 121.5, 135.0)):
        rtl = bazi.resolve_time(2000, 1, 7, 12, 0, 0, ZONE, lon, True)
        exp = round((lon - 120.0) * 4.0, 2)
        got = rtl.get("lon_correction_minutes")
        check("5.13.%d 经度修正 lon=%s° 期望 %s 分" % (i + 1, lon, exp),
              got is not None and abs(got - exp) <= 0.011
              and fnum(rtl["longitude"]) == lon,
              "实际=%r 期望=%r" % (got, exp))

    rtt = bazi.resolve_time(2000, 1, 7, 12, 0, 0, ZONE, 116.4, True)
    exp_dt = parse_dt(rtt["standard"]) + timedelta(
        minutes=rtt["lon_correction_minutes"] + rtt["equation_of_time_minutes"])
    check("5.14 真太阳时 = 标准时 + 经度修正 + 均时差",
          abs((rtt["used_dt"] - exp_dt).total_seconds()) < 1.5,
          "used=%s 期望≈%s" % (rtt["used_dt"], exp_dt))

    rtt2 = bazi.resolve_time(2000, 1, 7, 12, 0, 0, ZONE, 121.5, True)
    check("5.15 真太阳时 2000-01-07 12:00 lon=121.5° ≈ 12:00:37.8",
          abs((rtt2["used_dt"] - datetime(2000, 1, 7, 12, 0, 37, 800000)).total_seconds()) < 2.0,
          "used=%s" % rtt2["used_dt"])

    rtt3 = bazi.resolve_time(1988, 6, 1, 12, 0, 0, ZONE, 116.4, True)
    check("5.16 真太阳时 1988-06-01 12:00（DST）lon=116.4° ≈ 10:48:04",
          abs((rtt3["used_dt"] - datetime(1988, 6, 1, 10, 48, 4, 200000)).total_seconds()) < 2.0,
          "used=%s" % rtt3["used_dt"])

    base = datetime(2024, 1, 1)
    vals = [bazi.equation_of_time(base + timedelta(days=i)) for i in range(366)]
    check("5.17 均时差全年幅度 < 17 分钟", max(abs(v) for v in vals) < 17.0,
          "max=%.2f min=%.2f" % (max(vals), min(vals)))
    check("5.18 均时差极大值 ≈ +16.38 分（11-01）", abs(vals[305] - 16.38) < 0.2,
          "实际=%.3f" % vals[305])
    check("5.19 均时差极小值 ≈ −14.26 分（02-14）", abs(vals[44] + 14.26) < 0.2,
          "实际=%.3f" % vals[44])
    for (mo, d) in ((4, 16), (6, 15), (9, 2), (12, 25)):
        off = (datetime(2024, mo, d) - base).days
        check("5.20 均时差过零点 %02d-%02d |eot|<2 分" % (mo, d), abs(vals[off]) < 2.0,
              "eot=%.2f" % vals[off])

    try:
        from zoneinfo import ZoneInfo
        z = ZoneInfo(ZONE)
        zone_ok = z.key == ZONE
    except Exception as e:  # pragma: no cover
        zone_ok = False
        z = e
    check("5.21 zoneinfo / tzdata 可用（Asia/Shanghai）", zone_ok, "异常=%r" % (z,))


# ===========================================================================
# 6. 边界
# ===========================================================================
def check_day_chain(label, dates):
    bad = []
    prev_idx = None
    for (y, m, d) in dates:
        got = build(y, m, d, 12, 0, 0, sex=None)["pillars"][2]["ganzhi"]
        exp = day_gz(y, m, d)
        if got != exp:
            bad.append("%04d-%02d-%02d chart=%s 独立=%s" % (y, m, d, got, exp))
        idx = JIA_ZI.index(got) if got in JIA_ZI else -1
        if prev_idx is not None and idx != (prev_idx + 1) % 60:
            bad.append("%04d-%02d-%02d 与上一日日柱不连续" % (y, m, d))
        prev_idx = idx
    check(label, not bad, "；".join(bad[:3]))


def section_boundary():
    print("\n== 6. 边界：23 时子时 / 闰日 / 端点 ==")
    for (y, m, d) in ((2000, 1, 7), (1990, 6, 15), (2024, 2, 4)):
        nxt = date(y, m, d) + timedelta(days=1)
        exp_next = day_gz(nxt.year, nxt.month, nxt.day)
        exp_cur = day_gz(y, m, d)
        r1 = build(y, m, d, 23, 30, 0, sect=1, sex=None)
        r2 = build(y, m, d, 23, 30, 0, sect=2, sex=None)
        d1 = r1["pillars"][2]["ganzhi"]
        d2 = r2["pillars"][2]["ganzhi"]
        check("6.1 %04d-%02d-%02d 23:30：sect1 日柱进次日（%s）/ sect2 仍当日（%s）"
              % (y, m, d, exp_next, exp_cur),
              d1 == exp_next and d2 == exp_cur and d1 != d2,
              "sect1=%s sect2=%s 独立次日=%s 当%s" % (d1, d2, exp_next, exp_cur))
        exp_t = time_pillar_by_wushu(JIA_ZI.index(exp_cur), 23)
        t1 = r1["pillars"][3]["ganzhi"]
        t2 = r2["pillars"][3]["ganzhi"]
        check("6.2 %04d-%02d-%02d 23:30：两派时柱一致（按次日干起子时）" % (y, m, d),
              t1 == exp_t and t2 == exp_t, "sect1=%s sect2=%s 期望=%s" % (t1, t2, exp_t))

    for (y, m, d) in ((2000, 1, 7), (1990, 6, 15)):
        exp_cur = day_gz(y, m, d)
        a = build(y, m, d, 22, 59, 0, sect=2, sex=None)
        b = build(y, m, d, 23, 0, 0, sect=2, sex=None)
        c = build(y, m, d, 0, 0, 0, sect=2, sex=None)
        ok = (a["pillars"][2]["ganzhi"] == exp_cur and b["pillars"][2]["ganzhi"] == exp_cur
              and c["pillars"][2]["ganzhi"] == exp_cur
              and a["pillars"][3]["zhi"] == "亥" and b["pillars"][3]["zhi"] == "子"
              and c["pillars"][3]["zhi"] == "子")
        check("6.3 %04d-%02d-%02d 22:59(亥)/23:00(子)/00:00(子) 归属与日柱" % (y, m, d),
              ok, "22:59=%s 23:00=%s 00:00=%s"
              % (a["pillars"][2]["ganzhi"] + a["pillars"][3]["ganzhi"],
                 b["pillars"][2]["ganzhi"] + b["pillars"][3]["ganzhi"],
                 c["pillars"][2]["ganzhi"] + c["pillars"][3]["ganzhi"]))

    r0 = build(2000, 1, 7, 0, 0, 0, sect=2, sex=None)
    check("6.4 2000-01-07 00:00 时柱为甲子（日柱甲子，五鼠遁）",
          r0["pillars"][3]["ganzhi"] == "甲子" and r0["pillars"][2]["ganzhi"] == "甲子",
          "日柱=%s 时柱=%s" % (r0["pillars"][2]["ganzhi"], r0["pillars"][3]["ganzhi"]))

    nxt = date(2000, 1, 8)
    check("6.5 2000-01-07 23:30(sect1) 日柱 == 次日 2000-01-08 12:00 日柱",
          build(2000, 1, 7, 23, 30, 0, sect=1, sex=None)["pillars"][2]["ganzhi"]
          == build(nxt.year, nxt.month, nxt.day, 12, 0, 0, sex=None)["pillars"][2]["ganzhi"])

    check_day_chain("6.6 2000-02-28→02-29→03-01 日柱连续（2000 闰年）", date_seq(2000, 2, 28, 3))
    check_day_chain("6.7 1900-02-28→03-01 日柱连续（1900 非闰年，无 02-29）",
                    [(1900, 2, 28), (1900, 3, 1)])
    check_day_chain("6.8 2100-02-28→03-01 日柱连续（2100 非闰年，无 02-29）",
                    [(2100, 2, 28), (2100, 3, 1)])
    check_day_chain("6.9 1899-12-31→1900-01-01 日柱连续", [(1899, 12, 31), (1900, 1, 1)])
    check_day_chain("6.10 2100-12-31→2101-01-01 日柱连续", [(2100, 12, 31), (2101, 1, 1)])
    check_day_chain("6.11 1900-01-01..1900-01-15 日柱连续且与 JDN 一致", date_seq(1900, 1, 1, 15))
    check_day_chain("6.12 2100-12-15..2100-12-31 日柱连续且与 JDN 一致", date_seq(2100, 12, 15, 17))

    for (y, m) in ((1900, 2), (2100, 2)):
        try:
            build(y, m, 29, 12, 0, 0, sex=None)
            invalid_msg = "未抛异常"
        except ValueError as e:
            invalid_msg = "" if "day is out of range" in str(e) else "异常信息=%r" % str(e)
        check("6.13 %d-02-29 非法（%d 非闰年）抛 ValueError" % (y, y), not invalid_msg, invalid_msg)

    check("6.14 2000-02-29 合法（2000 闰年）日柱与 JDN 一致",
          build(2000, 2, 29, 12, 0, 0, sex=None)["pillars"][2]["ganzhi"] == day_gz(2000, 2, 29),
          "实际=%s 期望=%s" % (build(2000, 2, 29, 12, 0, 0, sex=None)["pillars"][2]["ganzhi"],
                               day_gz(2000, 2, 29)))


# ===========================================================================
# 7. 表完整性
# ===========================================================================
EXP_CHANG_SHENG = {"甲": "亥", "乙": "午", "丙": "寅", "丁": "酉", "戊": "寅",
                   "己": "酉", "庚": "巳", "辛": "子", "壬": "申", "癸": "卯"}


def section_tables():
    print("\n== 7. 表完整性：藏干 / 纳音 / 十二长生 / 十神 ==")
    for br in ZHI:
        vals = chart.HIDE_GAN.get(br, [])
        ok = (1 <= len(vals) <= 3 and len(set(vals)) == len(vals)
              and all(g in GAN for g in vals))
        if vals:
            ok = ok and chart.ELEMENT_OF_GAN[vals[0]] == chart.ELEMENT_OF_ZHI[br]
            ok = ok and len(chart.HIDE_RATIO.get(len(vals), ())) == len(vals)
        check("7.1 藏干 %s（%s），本气唯一且五行与地支一致"
              % (br, "、".join(vals)), ok,
              "藏干=%s 本气五行=%s 地支五行=%s"
              % (vals, chart.ELEMENT_OF_GAN.get(vals[0]) if vals else None,
                 chart.ELEMENT_OF_ZHI.get(br)))

    check("7.2 藏干表 12 支齐全且与 LunarUtil.ZHI_HIDE_GAN 一致",
          set(chart.HIDE_GAN) == set(ZHI)
          and all(list(chart.HIDE_GAN[k]) == list(LunarUtil.ZHI_HIDE_GAN[k]) for k in ZHI))

    check("7.3 纳音表 60 甲子全覆盖无重复",
          len(chart.NAYIN) == 60 and set(chart.NAYIN) == set(JIA_ZI),
          "len=%d 缺=%s" % (len(chart.NAYIN), sorted(set(JIA_ZI) - set(chart.NAYIN))[:3]))
    from collections import Counter
    cnt = Counter(chart.NAYIN.values())
    check("7.4 纳音共 30 个名称、每个恰好出现 2 次",
          len(cnt) == 30 and all(v == 2 for v in cnt.values()),
          "名称数=%d 次数分布=%s" % (len(cnt), sorted(set(cnt.values()))))
    check("7.5 纳音名称均为 3 字（如 海中金）",
          all(isinstance(v, str) and len(v) == 3 for v in chart.NAYIN.values()),
          "异常=%s" % [v for v in chart.NAYIN.values() if len(v) != 3][:3])
    pair_ok = all(chart.NAYIN[JIA_ZI[2 * i]] == chart.NAYIN[JIA_ZI[2 * i + 1]]
                  for i in range(30))
    known = {"甲子": "海中金", "丙寅": "炉中火", "戊辰": "大林木",
             "庚午": "路旁土", "壬申": "剑锋金"}
    check("7.6 纳音以 60 甲子两两成对且已知样例正确",
          pair_ok and all(chart.NAYIN[k] == v for k, v in known.items()),
          "样例=%s" % {k: chart.NAYIN.get(k) for k in known})

    for g in GAN:
        states = {z: chart._jishi(g, z) for z in ZHI}
        ok = set(states.values()) == set(chart.CHANG_SHENG) and len(states) == 12
        ok = ok and states[EXP_CHANG_SHENG[g]] == chart.CHANG_SHENG[0]
        check("7.7 十二长生 %s 干在 12 支双射且长生在 %s"
              % (g, EXP_CHANG_SHENG[g]), ok,
              "长生=%s 状态集=%d" % (EXP_CHANG_SHENG[g], len(set(states.values()))))

    exp_keys = {g1 + g2 for g1 in GAN for g2 in GAN}
    check("7.8 十神表 10×10=100 组合齐全",
          len(chart.SHI_SHEN) == 100 and set(chart.SHI_SHEN) == exp_keys,
          "len=%d 缺=%s" % (len(chart.SHI_SHEN), sorted(exp_keys - set(chart.SHI_SHEN))[:3]))
    ten_gods = {"比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"}
    check("7.9 十神取值均在十神名称集合内",
          set(chart.SHI_SHEN.values()) <= ten_gods
          and {"比肩", "正官"} <= set(chart.SHI_SHEN.values()),
          "取值=%s" % sorted(set(chart.SHI_SHEN.values())))


# ===========================================================================
# main
# ===========================================================================
def main():
    t0 = time.time()
    section_day_pillar()
    section_time_pillar()
    section_year_month_jieqi()
    section_dayun()
    section_true_solar()
    section_boundary()
    section_tables()
    elapsed = time.time() - t0

    print("\n" + "=" * 72)
    if FAILS:
        print("失败明细（%d 项）：" % len(FAILS))
        for f in FAILS:
            print("  ! " + f)
        print("FAILED: %d/%d checks failed  （耗时 %.2fs）" % (len(FAILS), CHECKS, elapsed))
        return 1
    print("ALL PASS (%d checks)" % CHECKS)
    print("耗时 %.2fs" % elapsed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
