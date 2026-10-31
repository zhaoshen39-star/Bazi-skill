# -*- coding: utf-8 -*-
"""verify_qimen.py — 奇门遁甲（时家转盘 · 拆补法）层回归。

覆盖点
------
1. 模块与常量：版本/方法/免责、九星八门八神表、环宫序、二十四节气三元局数表、
   地支宫位表、驿马表。
2. 结构完整性：九宫齐全、宫名字/字段齐备、中五特殊处理。
3. 盘面规则自洽：三奇六仪各现一次、九星八门八神不重不漏、值符随时干、
   值使随时支、天盘干随星、八神阳顺阴逆、旬空与驿马落宫、地盘阳顺阴逆。
4. 三个已知时刻样例：定局/值符/值使/三奇六仪/星门神逐宫比对。
5. 退化输入：类型错误、缺字段、节气缺失降级、时辰不明提醒、纯序号四柱。
6. 文本渲染：标题/分区/九宫表宽度对齐/要点与局限齐全。
7. 纯标准库自检：AST 扫描 import、无网络调用、可编译、UTF-8。

用法：python tests\\verify_qimen.py（退出码 0 表示全部通过）
"""

import ast
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import chart  # noqa: E402
import qimen  # noqa: E402


# ---------------------------------------------------------------------------
# 断言框架
# ---------------------------------------------------------------------------

failures = []
total = 0


def check(name, ok, detail=""):
    global total
    total += 1
    if not ok:
        failures.append((name, detail))
        print("FAIL  %s%s" % (name, ("  ← " + str(detail)) if detail else ""))


def expect(name, got, want):
    check(name, got == want, "想要 %r，实得 %r" % (want, got))


def no_raise(name, fn, *args, **kwargs):
    """期望不抛异常，返回结果；抛了就记失败并返回 None。"""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - 测试需要兜住任何异常
        check(name, False, "%s: %s" % (type(exc).__name__, exc))
        return None


def raises(name, fn, exc_type, *args, **kwargs):
    """期望抛出指定异常（子类也算）。"""
    try:
        fn(*args, **kwargs)
    except exc_type:
        check(name, True)
        return
    except Exception as exc:  # noqa: BLE001
        check(name, False, "异常类型不符：%s: %s" % (type(exc).__name__, exc))
        return
    check(name, False, "没有抛出 %s" % exc_type.__name__)


# ---------------------------------------------------------------------------
# 构造输入
# ---------------------------------------------------------------------------

PILLAR_NAMES = ("年柱", "月柱", "日柱", "时柱")


def build_report(year, month, day, hour, minute):
    """用真实历法内核排四柱，再包成 build_report 风格的结构。"""
    c = chart.build(year, month, day, hour, minute, sex=1)
    used = "%04d-%02d-%02d %02d:%02d:00" % (year, month, day, hour, minute)
    return {
        "input": {"date": "%04d-%02d-%02d" % (year, month, day),
                  "time": "%02d:%02d" % (hour, minute), "sex": 1},
        "time": {"used": used, "cst": used, "utc": "", "standard": used},
        "chart": c,
    }


def synthetic(pillars, term="冬至", reliable=None, drop_qi=False):
    """手工四柱 + 手工节气，绕过历法，专门测排盘规则。"""
    rows = []
    for i, gz in enumerate(pillars):
        row = {"name": PILLAR_NAMES[i]}
        if gz is None:
            row["gan"] = ""
            row["zhi"] = ""
            row["ganzhi"] = ""
        elif isinstance(gz, int):
            row["index"] = gz
            row["gan"] = ""
            row["zhi"] = ""
            row["ganzhi"] = ""
        else:
            row["gan"] = gz[0]
            row["zhi"] = gz[1]
            row["ganzhi"] = gz
        rows.append(row)
    c = {"pillars": rows, "jieqi": {"scale": "CST(UTC+8)"}}
    if not drop_qi:
        c["jieqi"]["prev_qi"] = {"name": term} if term else None
    if reliable is not None:
        c["time_pillar_reliable"] = reliable
    return {"chart": c, "time": {"used": "2020-01-01 12:00:00"}}


def plates(z):
    """把九宫盘折成按宫数的 dict，便于比对。"""
    out = {"earth": {}, "heaven": {}, "heaven_ji": {}, "star": {}, "star_ji": {},
           "door": {}, "deity": {}, "kong": [], "ma": []}
    for p in z["palaces"]:
        g = p["gong"]
        out["earth"][g] = p["earth_stem"]
        out["heaven"][g] = p["heaven_stem"]
        out["heaven_ji"][g] = p["heaven_stem_ji"]
        out["star"][g] = p["star"]
        out["star_ji"][g] = p["star_ji"]
        out["door"][g] = p["door"]
        out["deity"][g] = p["deity"]
        if p["is_kong"]:
            out["kong"].append(g)
        if p["is_ma"]:
            out["ma"].append(g)
    return out


def ji(gong):
    """中五寄坤二。"""
    return 2 if gong == 5 else gong


# ---------------------------------------------------------------------------
# 一、模块与常量
# ---------------------------------------------------------------------------

print("\n== 一、模块与常量 ==")

check("模块可导入并暴露 chart_qimen", callable(getattr(qimen, "chart_qimen", None)))
check("模块可导入并暴露 render_qimen_text", callable(getattr(qimen, "render_qimen_text", None)))
expect("VERSION", qimen.VERSION, "v1")
check("METHOD 是足够长的字符串", isinstance(qimen.METHOD, str) and len(qimen.METHOD) >= 60)
check("METHOD 写明拆补法与转盘", "拆补" in qimen.METHOD and "转盘" in qimen.METHOD)
check("NOTE 免责声明含「不作吉凶」", "不作吉凶" in qimen.NOTE)
check("NOTE 点明流派众多", "流派" in qimen.NOTE)

expect("二十四节气数量", len(qimen.JIEQI_ORDER), 24)
expect("二十四节气首位是冬至", qimen.JIEQI_ORDER[0], "冬至")
expect("二十四节气末位是大雪", qimen.JIEQI_ORDER[-1], "大雪")
expect("二十四节气互不重复", len(set(qimen.JIEQI_ORDER)), 24)

expect("三元局数表 24 行", len(qimen.SAN_YUAN_JU), 24)
check("三元局数表每行 3 个数", all(len(row) == 3 for row in qimen.SAN_YUAN_JU))
check("三元局数表取值 1..9", all(1 <= n <= 9 for row in qimen.SAN_YUAN_JU for n in row))
check("三元局数表每行三数互异", all(len(set(row)) == 3 for row in qimen.SAN_YUAN_JU))
expect("冬至三元局数", qimen.SAN_YUAN_JU[0], (1, 7, 4))
expect("芒种三元局数", qimen.SAN_YUAN_JU[11], (6, 3, 9))
expect("夏至三元局数（转阴遁）", qimen.SAN_YUAN_JU[12], (9, 3, 6))
expect("霜降三元局数", qimen.SAN_YUAN_JU[20], (5, 8, 2))
expect("大雪三元局数", qimen.SAN_YUAN_JU[23], (4, 7, 1))

expect("九星表 9 项", len(qimen.STAR_BY_GONG), 9)
expect("九星表 9 个不同名字", len(set(qimen.STAR_BY_GONG.values())), 9)
expect("坎一宫天蓬", qimen.STAR_BY_GONG[1], "天蓬")
expect("中五宫天禽", qimen.STAR_BY_GONG[5], "天禽")
expect("离九宫天英", qimen.STAR_BY_GONG[9], "天英")

expect("八门表 8 项（中五无门）", len(qimen.DOOR_BY_GONG), 8)
expect("八门 8 个不同名字", len(set(qimen.DOOR_BY_GONG.values())), 8)
expect("中五没有八门", 5 in qimen.DOOR_BY_GONG, False)
expect("兑七宫惊门", qimen.DOOR_BY_GONG[7], "惊门")
expect("艮八宫生门", qimen.DOOR_BY_GONG[8], "生门")

expect("八神 8 位", len(qimen.GOD_ORDER), 8)
expect("八神互不重复", len(set(qimen.GOD_ORDER)), 8)
expect("八神首位值符", qimen.GOD_ORDER[0], "值符")
expect("八神末位九天", qimen.GOD_ORDER[-1], "九天")
expect("八神用腾蛇", qimen.GOD_ORDER[1], "腾蛇")
check("八神统一白虎玄武", "白虎" in qimen.GOD_ORDER and "玄武" in qimen.GOD_ORDER)
check("八神未混入勾陈朱雀", "勾陈" not in qimen.GOD_ORDER and "朱雀" not in qimen.GOD_ORDER)

expect("环宫序 8 宫", len(qimen.RING), 8)
expect("环宫序不含中五", 5 in qimen.RING, False)
expect("环宫序互不重复", len(set(qimen.RING)), 8)
expect("环宫序自巽四起", qimen.RING[0], 4)
expect("环宫序第二为离九", qimen.RING[1], 9)
expect("环宫序索引一致", [qimen.RING_POS[g] for g in qimen.RING], list(range(8)))

expect("中五寄坤二常量", qimen.JI_GONG, 2)
expect("地支宫位表 12 项", len(qimen.ZHI_GONG), 12)
check("地支宫位取值 1..9", all(1 <= g <= 9 for g in qimen.ZHI_GONG.values()))
expect("子居坎一", qimen.ZHI_GONG["子"], 1)
expect("午居离九", qimen.ZHI_GONG["午"], 9)
expect("戌亥同乾六", (qimen.ZHI_GONG["戌"], qimen.ZHI_GONG["亥"]), (6, 6))
expect("驿马表 12 项", len(qimen.YIMA), 12)
expect("申子辰马在寅", [qimen.YIMA["申"], qimen.YIMA["子"], qimen.YIMA["辰"]], ["寅"] * 3)
expect("寅午戌马在申", [qimen.YIMA["寅"], qimen.YIMA["午"], qimen.YIMA["戌"]], ["申"] * 3)
expect("巳酉丑马在亥", [qimen.YIMA["巳"], qimen.YIMA["酉"], qimen.YIMA["丑"]], ["亥"] * 3)
expect("亥卯未马在巳", [qimen.YIMA["亥"], qimen.YIMA["卯"], qimen.YIMA["未"]], ["巳"] * 3)

expect("地盘干排序", qimen.STEM_ORDER, "戊己庚辛壬癸丁丙乙")
expect("六仪顺序", qimen.XUN_YI, ("戊", "己", "庚", "辛", "壬", "癸"))
expect("六仪在前三奇在后", qimen.STEM_ORDER[:6], "".join(qimen.XUN_YI))
expect("三奇逆布为丁丙乙", qimen.STEM_ORDER[6:], "丁丙乙")
expect("九宫排版 GRID", qimen.GRID, ((4, 9, 2), (3, 5, 7), (8, 1, 6)))


# ---------------------------------------------------------------------------
# 二、内部工具的确定性（定局三要素）
# ---------------------------------------------------------------------------

print("\n== 二、定局三要素 ==")

for day_index in range(60):
    yuan, name, fu_tou = qimen._yuan_of(day_index)
    check("符头三元 day_index=%d" % day_index,
          yuan == (day_index // 5) % 3 and name == qimen.YUAN_NAMES[yuan],
          (yuan, name))
    head = day_index - day_index % 5
    check("符头干支 day_index=%d" % day_index,
          fu_tou == qimen.GAN[head % 10] + qimen.ZHI[head % 12], fu_tou)
    heads = ("子", "午", "卯", "酉")
    want = 0 if qimen.ZHI[head % 12] in heads else (
        1 if qimen.ZHI[head % 12] in ("寅", "申", "巳", "亥") else 2)
    expect("符头支定元 day_index=%d" % day_index, yuan, want)

for index in range(60):
    info = qimen._xun_info(index)
    expect("旬首序号 index=%d" % index, info["index"], index // 10)
    expect("旬首干支 index=%d" % index, info["head"],
           "甲" + qimen.ZHI[(index // 10) * 10 % 12])
    expect("旬首六仪 index=%d" % index, info["yi"], qimen.XUN_YI[index // 10])
    expect("旬空两位 index=%d" % index, len(info["kong"]), 2)

check("_term_index 认霜降", qimen._term_index("霜降") == 20)
check("_term_index 认带后缀节气", qimen._term_index("霜降（气）") == 20)
check("_term_index 认不出返回 None", qimen._term_index("无此节气") is None)
check("_term_index 非字符串返回 None", qimen._term_index(None) is None)

# 地盘：阳遁顺宫数、阴遁逆宫数，戊必在局数宫。
for ju in range(1, 10):
    yang = qimen._earth_plate(ju, True)
    yin = qimen._earth_plate(ju, False)
    expect("阳遁%d局戊在%d宫" % (ju, ju), yang[ju], "戊")
    expect("阴遁%d局戊在%d宫" % (ju, ju), yin[ju], "戊")
    expect("阳遁%d局九干齐" % ju, sorted(yang.values()), sorted(qimen.STEM_ORDER))
    expect("阴遁%d局九干齐" % ju, sorted(yin.values()), sorted(qimen.STEM_ORDER))
    seq = [yang[(ju - 1 + k) % 9 + 1] for k in range(9)]
    expect("阳遁%d局顺布" % ju, "".join(seq), qimen.STEM_ORDER)
    seq = [yin[(ju - 1 - k) % 9 + 1] for k in range(9)]
    expect("阴遁%d局逆布" % ju, "".join(seq), qimen.STEM_ORDER)

for gong in range(1, 10):
    check("_ji_gong 寄坤二 gong=%d" % gong, qimen._ji_gong(gong) == ji(gong))
for gong in (1, 2, 3, 4, 6, 7, 8, 9):
    check("_ring_index gong=%d" % gong, qimen._ring_index(gong) == qimen.RING_POS[gong])
expect("_ring_index 中五按坤二算", qimen._ring_index(5), qimen.RING_POS[2])


# ---------------------------------------------------------------------------
# 三、结构完整性 + 盘面规则自洽
# ---------------------------------------------------------------------------

print("\n== 三、结构完整性 ==")

REQUIRED_TOP = (
    "version", "method", "note", "school", "pillars", "pillars_text", "time",
    "jieqi", "yuan", "dun", "ju", "xun", "zhifu", "zhishi", "hour", "day",
    "kong", "ma", "palaces", "sanqi_liuyi", "summary", "limits",
)
REQUIRED_PALACE = (
    "gong", "name", "gua", "direction", "is_center", "earth_stem",
    "heaven_stem", "heaven_stem_ji", "star", "star_ji", "door", "deity",
    "is_kong", "is_ma",
)


def chart_rules(z, tag):
    """对一张盘做结构 + 规则自洽检查。"""
    def nm(text):
        return "%s %s" % (tag, text)

    def eq(text, got, want):
        expect(nm(text), got, want)

    check(nm("是 dict"), isinstance(z, dict), type(z))
    for key in REQUIRED_TOP:
        check(nm("顶层字段 %s" % key), key in z)

    eq("版本", z["version"], qimen.VERSION)
    check(nm("method 文本"), isinstance(z["method"], str) and len(z["method"]) > 40)
    check(nm("note 文本"), isinstance(z["note"], str) and "不作吉凶" in z["note"])
    check(nm("school 快照"), isinstance(z["school"], dict) and z["school"].get("定局") == "拆补法")

    eq("四柱 4 行", len(z["pillars"]), 4)
    eq("四柱文本", z["pillars_text"], " ".join(r["ganzhi"] for r in z["pillars"]))
    check(nm("时柱可靠标记"), isinstance(z["time"]["reliable"], bool))

    palaces = z["palaces"]
    eq("九宫 9 项", len(palaces), 9)
    eq("宫数 1..9", [p["gong"] for p in palaces], list(range(1, 10)))
    eq("宫名", [p["name"] for p in palaces], [qimen.GONG_NAME[g] for g in range(1, 10)])
    eq("卦名", [p["gua"] for p in palaces], [qimen.GONG_GUA[g] for g in range(1, 10)])
    eq("方位", [p["direction"] for p in palaces], [qimen.GONG_DIR[g] for g in range(1, 10)])
    for p in palaces:
        for key in REQUIRED_PALACE:
            check(nm("宫 %d 字段 %s" % (p["gong"], key)), key in p)
        check(nm("宫 %d is_center" % p["gong"]), p["is_center"] == (p["gong"] == 5))

    pl = plates(z)
    earth, heaven, doors, gods = pl["earth"], pl["heaven"], pl["door"], pl["deity"]
    stars, star_ji = pl["star"], pl["star_ji"]

    # --- 三奇六仪：地盘、天盘各九干各一次 ---
    eq("地盘九干各一次", sorted(earth.values()), sorted(qimen.STEM_ORDER))
    heaven_all = [v for g, v in heaven.items() if v] + [v for v in pl["heaven_ji"].values() if v]
    eq("天盘九干各一次", sorted(heaven_all), sorted(qimen.STEM_ORDER))
    eq("坎一宫有地盘干", earth[1] in qimen.STEM_ORDER, True)
    eq("中五宫有地盘干", earth[5] in qimen.STEM_ORDER, True)
    check(nm("三奇六仪结构"), isinstance(z["sanqi_liuyi"], dict))
    for stem in qimen.STEM_ORDER:
        want_earth = [g for g, s in earth.items() if s == stem]
        got_earth = z["sanqi_liuyi"]["earth"][stem]["gong"]
        check(nm("三奇六仪 地盘 %s" % stem), want_earth == [got_earth], (got_earth, want_earth))
        want_heaven = ([g for g, s in heaven.items() if s == stem] +
                       [g for g, s in pl["heaven_ji"].items() if s == stem])
        got_heaven = z["sanqi_liuyi"]["heaven"][stem]["gong"]
        check(nm("三奇六仪 天盘 %s" % stem),
              want_heaven == [got_heaven], (got_heaven, want_heaven))
    eq("中宫地盘干快照", z["sanqi_liuyi"]["zhong_gong_earth_stem"], earth[5])

    # --- 九星：8 主星不重不漏，天禽寄于天芮落宫 ---
    ring = list(qimen.RING)
    eq("八宫主星互不重复", len(set(stars[g] for g in ring)), 8)
    eq("八宫主星不含天禽", "天禽" in [stars[g] for g in ring], False)
    eq("八宫主星集合", sorted(stars[g] for g in ring),
       sorted(v for k, v in qimen.STAR_BY_GONG.items() if k != 5))
    qin = [g for g in ring if star_ji[g]]
    eq("天禽寄宫唯一", len(qin), 1)
    if qin:
        eq("天禽寄星", star_ji[qin[0]], "天禽")
    eq("中五无星", stars[5], "")
    eq("中五无寄星", star_ji[5], "")
    for g in ring:
        check(nm("宫 %d 有主星" % g), stars[g] in qimen.STAR_BY_GONG.values())

    # --- 八门：8 门不重不漏，中五无门 ---
    eq("八宫八门互不重复", len(set(doors[g] for g in ring)), 8)
    eq("八宫八门集合", sorted(doors[g] for g in ring), sorted(qimen.DOOR_BY_GONG.values()))
    eq("中五无门", doors[5], "")

    # --- 八神：8 神不重不漏，中五无神 ---
    eq("八宫八神互不重复", len(set(gods[g] for g in ring)), 8)
    eq("八宫八神集合", sorted(gods[g] for g in ring), sorted(qimen.GOD_ORDER))
    eq("中五无八神", gods[5], "")

    # --- 天盘干随星：某宫天盘干 = 该宫主星本宫的地盘干 ---
    home_of_star = {v: k for k, v in qimen.STAR_BY_GONG.items()}
    for g in ring:
        star = stars[g]
        check(nm("天盘干随星 %d" % g), heaven[g] == earth[home_of_star[star]], (heaven[g], star))
    if qin:
        eq("天盘寄干取自中宫", pl["heaven_ji"][qin[0]], earth[5])
        eq("中宫地盘干随天禽寄宫", z["sanqi_liuyi"]["zhong_gong_ji_gong"], qin[0])

    # --- 值符：六仪地盘宫之星 + 随时干 ---
    xun_yi_gong = z["zhifu"]["earth_gong"]
    eq("值符六仪宫正确",
       earth[xun_yi_gong], z["zhifu"]["xun_yi"])
    eq("值符六仪与旬首一致", z["zhifu"]["xun_yi"], z["xun"]["yi"])
    eq("值符星取本宫九星", z["zhifu"]["star"], qimen.STAR_BY_GONG[xun_yi_gong])
    eq("值符本宫寄坤二", z["zhifu"]["home_gong"], ji(xun_yi_gong))
    eq("值符落宫名", z["zhifu"]["land_gong_name"], qimen.GONG_NAME[z["zhifu"]["land_gong"]])
    check(nm("值符星确实在该宫"),
          stars[z["zhifu"]["land_gong"]] == z["zhifu"]["star"] or
          star_ji[z["zhifu"]["land_gong"]] == z["zhifu"]["star"],
          (stars[z["zhifu"]["land_gong"]], star_ji[z["zhifu"]["land_gong"]]))
    eq("值符随时干（落时干宫）", z["zhifu"]["land_gong"], ji(z["hour"]["gan_gong"]))
    eq("值符星落宫与输出一致", z["zhifu"]["star_landed"], z["zhifu"]["star"])

    # --- 值使：六仪本宫门 + 随时支 ---
    offset_zhi = z["zhishi"]["zhi_offset"]
    expect(nm("值使时支偏移"), offset_zhi,
           (qimen.ZHI.index(z["hour"]["zhi"]) - z["xun"]["head_zhi"]) % 12)
    direction = 1 if z["dun"]["is_yang"] else -1
    raw = (xun_yi_gong - 1 + offset_zhi * direction) % 9 + 1
    eq("值使飞宫公式", z["zhishi"]["raw_gong"], raw)
    eq("值使落宫", z["zhishi"]["gong"], ji(raw))
    eq("值使落宫名", z["zhishi"]["gong_name"], qimen.GONG_NAME[ji(raw)])
    eq("值使门取本宫八门", z["zhishi"]["door"], qimen.DOOR_BY_GONG[ji(xun_yi_gong)])
    eq("值使本宫", z["zhishi"]["home_gong"], ji(xun_yi_gong))
    eq("值使门确实落该宫", doors[z["zhishi"]["gong"]], z["zhishi"]["door"])

    # --- 九星、八门整体转盘一致性 ---
    star_shift = (qimen.RING_POS[ji(xun_yi_gong)] - qimen.RING_POS[z["zhifu"]["land_gong"]]) % 8
    door_shift = (qimen.RING_POS[z["zhishi"]["home_gong"]] -
                  qimen.RING_POS[z["zhishi"]["gong"]]) % 8
    for g in ring:
        want_star = qimen.STAR_BY_GONG[qimen.RING[(qimen.RING_POS[g] + star_shift) % 8]]
        want_door = qimen.DOOR_BY_GONG[qimen.RING[(qimen.RING_POS[g] + door_shift) % 8]]
        check(nm("转盘九星 %d" % g), stars[g] == want_star, (stars[g], want_star))
        check(nm("转盘八门 %d" % g), doors[g] == want_door, (doors[g], want_door))
    qin_want = qimen.RING[(qimen.RING_POS[2] - star_shift) % 8]
    if qin:
        eq("天禽随天芮落宫", qin[0], qin_want)

    # --- 八神：自值符宫起，阳顺阴逆 ---
    start = qimen.RING_POS[ji(z["hour"]["gan_gong"])]
    for k, god in enumerate(qimen.GOD_ORDER):
        dest = qimen.RING[(start + k * direction) % 8]
        check(nm("八神次序 %d" % k), gods[dest] == god, (gods[dest], god))

    # --- 旬空 / 驿马 ---
    kong_zhi = z["kong"]["zhi"]
    eq("旬空两支", len(kong_zhi), 2)
    eq("旬空取自旬首", kong_zhi, z["xun"]["kong"])
    eq("旬空宫", z["kong"]["gong"], sorted({qimen.ZHI_GONG[zhi] for zhi in kong_zhi}))
    eq("旬空宫名", z["kong"]["gong_names"], [qimen.GONG_NAME[g] for g in z["kong"]["gong"]])
    eq("旬空宫标记", sorted(pl["kong"]), z["kong"]["gong"])
    eq("驿马支", z["ma"]["zhi"], qimen.YIMA[z["hour"]["zhi"]])
    eq("驿马宫", z["ma"]["gong"], qimen.ZHI_GONG[z["ma"]["zhi"]])
    eq("驿马宫标记", pl["ma"], [z["ma"]["gong"]])

    # --- 定局 ---
    term_index = z["jieqi"]["index"]
    eq("局数", z["ju"], z["dun"]["ju"])
    check(nm("局数 1..9"), 1 <= z["ju"] <= 9)
    eq("阴阳遁标记", z["dun"]["yin_yang"], "阳遁" if z["dun"]["is_yang"] else "阴遁")
    eq("定局标签", z["dun"]["label"],
       ("阳遁" if z["dun"]["is_yang"] else "阴遁") + "一二三四五六七八九"[z["ju"] - 1] + "局")
    eq("三元名", z["yuan"]["name"], qimen.YUAN_NAMES[z["yuan"]["index"]])
    eq("符头", z["yuan"]["fu_tou"],
       qimen.GAN[(z["day"]["index"] - z["day"]["index"] % 5) % 10] +
       qimen.ZHI[(z["day"]["index"] - z["day"]["index"] % 5) % 12])
    eq("三元序号", z["yuan"]["index"], (z["day"]["index"] // 5) % 3)
    if term_index is not None:
        eq("阴阳遁由节气决定", z["dun"]["is_yang"], term_index < 12)
        eq("局数由三元局数表决定", z["ju"], qimen.SAN_YUAN_JU[term_index][z["yuan"]["index"]])
        eq("节气下标", term_index, qimen.JIEQI_ORDER.index(z["jieqi"]["name"]))

    # --- summary / limits ---
    check(nm("summary 是非空文本列表"),
          isinstance(z["summary"], list) and z["summary"] and
          all(isinstance(s, str) and s for s in z["summary"]))
    check(nm("limits 是非空文本列表"),
          isinstance(z["limits"], list) and len(z["limits"]) >= 6 and
          all(isinstance(s, str) and s for s in z["limits"]))
    check(nm("limits 保留拆补法说明"), any("拆补" in s for s in z["limits"]))
    check(nm("limits 保留置闰法说明"), any("置闰" in s for s in z["limits"]))
    check(nm("limits 保留中五寄坤二"),
          any("中五" in s and "坤二" in s for s in z["limits"]))
    check(nm("limits 声明不做吉凶"), any("不作吉凶" in s or "吉凶" in s for s in z["limits"]))
    check(nm("summary 提到值符"), any("值符" in s for s in z["summary"]))
    check(nm("summary 提到值使"), any("值使" in s for s in z["summary"]))
    check(nm("summary 提到旬空"), any("旬空" in s for s in z["summary"]))


# 三张真实盘 + 两张手工盘
CASES = [
    ("2026-10-31 14:10", build_report(2026, 10, 31, 14, 10)),
    ("2024-06-01 09:30", build_report(2024, 6, 1, 9, 30)),
    ("2004-06-12 10:16", build_report(2004, 6, 12, 10, 16)),
]

REAL = []
CHARTS = {}
for label, report in CASES:
    z = no_raise("%s 起局成功" % label, qimen.chart_qimen, report)
    if z is None:
        continue
    REAL.append((label, z))
    CHARTS[label] = z
    print("\n== 四、规则自洽（%s）==" % label)
    chart_rules(z, label)

# 六甲时 + 中五值符（阳遁一局，旬首甲辰壬落中五）：天盘伏吟、天禽为值符。
SYN_A = synthetic(["甲子", "丙子", "甲子", "甲辰"], term="冬至")
z_a = no_raise("阳遁中五值符起局", qimen.chart_qimen, SYN_A)
if z_a is not None:
    print("\n== 四、规则自洽（阳遁一局 · 六甲时）==")
    chart_rules(z_a, "阳遁一局")

# 六甲时 + 中五值符（阴遁九局，旬首甲辰壬落中五）
SYN_B = synthetic(["甲子", "丙子", "甲子", "甲辰"], term="夏至")
z_b = no_raise("阴遁中五值符起局", qimen.chart_qimen, SYN_B)
if z_b is not None:
    print("\n== 四、规则自洽（阴遁九局 · 六甲时）==")
    chart_rules(z_b, "阴遁九局")

# 普通盘：时干乙，旬空戌亥同宫（乾六）
SYN_C = synthetic(["甲子", "丙子", "甲子", "乙丑"], term="冬至")
z_c = no_raise("普通手工盘起局", qimen.chart_qimen, SYN_C)
if z_c is not None:
    print("\n== 四、规则自洽（阳遁一局 · 时干乙）==")
    chart_rules(z_c, "阳遁一局乙丑")


# ---------------------------------------------------------------------------
# 五、三个已知时刻样例
# ---------------------------------------------------------------------------

print("\n== 五、已知样例 ==")

SAMPLES = [
    {
        "label": "样例1 2026-10-31 14:10",
        "key": "2026-10-31 14:10",
        "pillars": "丙午 戊戌 戊寅 己未",
        "term": "霜降", "term_index": 20, "yuan": "下元", "fu_tou": "甲戌",
        "dun": "阴遁二局", "is_yang": False, "ju": 2,
        "xun": "甲寅", "yi": "癸", "kong": ["子", "丑"], "kong_gong": [1, 8],
        "zhifu": ("天心", 6, 1), "zhishi": ("开门", 6, 1, 5),
        "earth": {1: "己", 2: "戊", 3: "乙", 4: "丙", 5: "丁", 6: "癸", 7: "壬", 8: "辛", 9: "庚"},
        "heaven": {1: "癸", 2: "庚", 3: "辛", 4: "乙", 6: "壬", 7: "戊", 8: "己", 9: "丙"},
        "heaven_ji": {7: "丁"},
        "star": {1: "天心", 2: "天英", 3: "天任", 4: "天冲", 6: "天柱", 7: "天芮", 8: "天蓬", 9: "天辅"},
        "star_ji": {7: "天禽"},
        "door": {1: "开门", 2: "景门", 3: "生门", 4: "伤门", 6: "惊门", 7: "死门", 8: "休门", 9: "杜门"},
        "deity": {1: "值符", 2: "六合", 3: "九地", 4: "玄武", 6: "腾蛇", 7: "太阴", 8: "九天", 9: "白虎"},
        "ma": ("巳", 4),
    },
    {
        "label": "样例2 2024-06-01 09:30",
        "key": "2024-06-01 09:30",
        "pillars": "甲辰 己巳 丙申 癸巳",
        "term": "小满", "term_index": 10, "yuan": "上元", "fu_tou": "甲午",
        "dun": "阳遁五局", "is_yang": True, "ju": 5,
        "xun": "甲申", "yi": "庚", "kong": ["午", "未"], "kong_gong": [2, 9],
        "zhifu": ("天柱", 7, 1), "zhishi": ("惊门", 7, 7, 9),
        "earth": {1: "癸", 2: "丁", 3: "丙", 4: "乙", 5: "戊", 6: "己", 7: "庚", 8: "辛", 9: "壬"},
        "heaven": {1: "庚", 2: "乙", 3: "癸", 4: "辛", 6: "丁", 7: "壬", 8: "己", 9: "丙"},
        "heaven_ji": {6: "戊"},
        "star": {1: "天柱", 2: "天辅", 3: "天蓬", 4: "天任", 6: "天芮", 7: "天英", 8: "天心", 9: "天冲"},
        "star_ji": {6: "天禽"},
        "door": {1: "休门", 2: "死门", 3: "伤门", 4: "杜门", 6: "开门", 7: "惊门", 8: "生门", 9: "景门"},
        "deity": {1: "值符", 2: "玄武", 3: "太阴", 4: "六合", 6: "九天", 7: "九地", 8: "腾蛇", 9: "白虎"},
        "ma": ("亥", 6),
    },
    {
        "label": "样例3 2004-06-12 10:16",
        "key": "2004-06-12 10:16",
        "pillars": "甲申 庚午 壬戌 乙巳",
        "term": "芒种", "term_index": 11, "yuan": "下元", "fu_tou": "己未",
        "dun": "阳遁九局", "is_yang": True, "ju": 9,
        "xun": "甲辰", "yi": "壬", "kong": ["寅", "卯"], "kong_gong": [3, 8],
        "zhifu": ("天辅", 4, 8), "zhishi": ("杜门", 4, 2, 1),
        "earth": {1: "己", 2: "庚", 3: "辛", 4: "壬", 5: "癸", 6: "丁", 7: "丙", 8: "乙", 9: "戊"},
        "heaven": {1: "辛", 2: "丁", 3: "戊", 4: "庚", 6: "乙", 7: "己", 8: "壬", 9: "丙"},
        "heaven_ji": {4: "癸"},
        "star": {1: "天冲", 2: "天心", 3: "天英", 4: "天芮", 6: "天任", 7: "天蓬", 8: "天辅", 9: "天柱"},
        "star_ji": {4: "天禽"},
        "door": {1: "惊门", 2: "杜门", 3: "休门", 4: "生门", 6: "死门", 7: "景门", 8: "开门", 9: "伤门"},
        "deity": {1: "九天", 2: "白虎", 3: "腾蛇", 4: "太阴", 6: "九地", 7: "玄武", 8: "值符", 9: "六合"},
        "ma": ("亥", 6),
    },
]

for sample in SAMPLES:
    label = sample["label"]
    z = CHARTS.get(sample["key"])
    check(label + " 有排盘结果", z is not None)
    if z is None:
        continue
    pl = plates(z)
    expect(label + " 四柱", z["pillars_text"], sample["pillars"])
    expect(label + " 节气", z["jieqi"]["name"], sample["term"])
    expect(label + " 节气下标", z["jieqi"]["index"], sample["term_index"])
    expect(label + " 三元", z["yuan"]["name"], sample["yuan"])
    expect(label + " 符头", z["yuan"]["fu_tou"], sample["fu_tou"])
    expect(label + " 阴阳遁", z["dun"]["is_yang"], sample["is_yang"])
    expect(label + " 局数", z["ju"], sample["ju"])
    expect(label + " 定局标签", z["dun"]["label"], sample["dun"])
    expect(label + " 旬首", z["xun"]["head"], sample["xun"])
    expect(label + " 旬首六仪", z["xun"]["yi"], sample["yi"])
    expect(label + " 旬空支", z["kong"]["zhi"], sample["kong"])
    expect(label + " 旬空宫", z["kong"]["gong"], sample["kong_gong"])
    expect(label + " 值符星", z["zhifu"]["star"], sample["zhifu"][0])
    expect(label + " 值符本宫", z["zhifu"]["earth_gong"], sample["zhifu"][1])
    expect(label + " 值符落宫", z["zhifu"]["land_gong"], sample["zhifu"][2])
    expect(label + " 值使门", z["zhishi"]["door"], sample["zhishi"][0])
    expect(label + " 值使本宫", z["zhishi"]["home_gong"], sample["zhishi"][1])
    expect(label + " 值使落宫", z["zhishi"]["gong"], sample["zhishi"][2])
    expect(label + " 值使时支偏移", z["zhishi"]["zhi_offset"], sample["zhishi"][3])
    expect(label + " 地盘三奇六仪", pl["earth"], sample["earth"])
    expect(label + " 天盘干", dict((g, pl["heaven"][g]) for g in qimen.RING), sample["heaven"])
    expect(label + " 天盘寄干", dict((g, v) for g, v in pl["heaven_ji"].items() if v),
           sample["heaven_ji"])
    expect(label + " 九星", dict((g, pl["star"][g]) for g in qimen.RING), sample["star"])
    expect(label + " 天禽寄宫", dict((g, v) for g, v in pl["star_ji"].items() if v),
           sample["star_ji"])
    expect(label + " 八门", dict((g, pl["door"][g]) for g in qimen.RING), sample["door"])
    expect(label + " 八神", dict((g, pl["deity"][g]) for g in qimen.RING), sample["deity"])
    expect(label + " 驿马", (z["ma"]["zhi"], z["ma"]["gong"]), sample["ma"])
    expect(label + " 值符之宫即时干宫", z["zhifu"]["land_gong"], ji(z["hour"]["gan_gong"]))


# 手工盘逐项核对（六甲时伏吟 / 中五值符 / 天禽随天芮 / 旬空同宫折叠）
if z_a is not None:
    pl_a = plates(z_a)
    expect("六甲时阳遁 局数", z_a["ju"], 1)
    expect("六甲时阳遁 阴阳遁", z_a["dun"]["is_yang"], True)
    expect("六甲时阳遁 值符星为天禽", z_a["zhifu"]["star"], "天禽")
    expect("六甲时阳遁 六仪落中五", z_a["zhifu"]["earth_gong"], 5)
    expect("六甲时阳遁 值符寄坤二", z_a["zhifu"]["land_gong"], 2)
    expect("六甲时阳遁 值使门为死门", z_a["zhishi"]["door"], "死门")
    expect("六甲时阳遁 值使落坤二", z_a["zhishi"]["gong"], 2)
    expect("六甲时阳遁 九星伏吟",
           dict((g, pl_a["star"][g]) for g in qimen.RING),
           dict((g, qimen.STAR_BY_GONG[g]) for g in qimen.RING))
    expect("六甲时阳遁 八门伏吟",
           dict((g, pl_a["door"][g]) for g in qimen.RING),
           dict((g, qimen.DOOR_BY_GONG[g]) for g in qimen.RING))
    expect("六甲时阳遁 天盘干伏吟",
           dict((g, pl_a["heaven"][g]) for g in qimen.RING),
           dict((g, pl_a["earth"][g]) for g in qimen.RING))
    expect("六甲时阳遁 天禽寄坤二", pl_a["star_ji"][2], "天禽")
    expect("六甲时阳遁 寄天盘干为中宫壬", pl_a["heaven_ji"][2], "壬")
    expect("六甲时阳遁 八神自坤二起",
           [pl_a["deity"][qimen.RING[(2 + k) % 8]] for k in range(8)],
           list(qimen.GOD_ORDER))

if z_b is not None:
    pl_b = plates(z_b)
    expect("六甲时阴遁 局数", z_b["ju"], 9)
    expect("六甲时阴遁 阴阳遁", z_b["dun"]["is_yang"], False)
    expect("六甲时阴遁 值符星为天禽", z_b["zhifu"]["star"], "天禽")
    expect("六甲时阴遁 值使门为死门", z_b["zhishi"]["door"], "死门")
    expect("六甲时阴遁 值符落坤二", z_b["zhifu"]["land_gong"], 2)
    expect("六甲时阴遁 八神自坤二逆布",
           [pl_b["deity"][qimen.RING[(2 - k) % 8]] for k in range(8)],
           list(qimen.GOD_ORDER))

if z_c is not None:
    pl_c = plates(z_c)
    expect("手工盘 时干乙居离九", z_c["hour"]["gan_gong"], 9)
    expect("手工盘 值符随时干落离九", z_c["zhifu"]["land_gong"], 9)
    expect("手工盘 值符星天蓬", z_c["zhifu"]["star"], "天蓬")
    expect("手工盘 旬空戌亥同宫折叠", z_c["kong"]["gong"], [6])
    expect("手工盘 驿马丑命在亥", (z_c["ma"]["zhi"], z_c["ma"]["gong"]), ("亥", 6))


# ---------------------------------------------------------------------------
# 六、退化输入与兼容性
# ---------------------------------------------------------------------------

print("\n== 六、退化输入与兼容性 ==")

raises("非 dict 输入抛 TypeError", qimen.chart_qimen, TypeError, None)
raises("字符串输入抛 TypeError", qimen.chart_qimen, TypeError, "2026-10-31")
raises("列表输入抛 TypeError", qimen.chart_qimen, TypeError, [1, 2, 3])
raises("缺 chart 抛 ValueError", qimen.chart_qimen, ValueError, {})
raises("chart 非 dict 抛 ValueError", qimen.chart_qimen, ValueError, {"chart": "x"})
raises("缺 pillars 抛 ValueError", qimen.chart_qimen, ValueError, {"chart": {}})
raises("pillars 非序列抛 ValueError", qimen.chart_qimen, ValueError, {"pillars": 42})
raises("pillars 不足 4 柱抛 ValueError", qimen.chart_qimen, ValueError,
       {"pillars": [{"gan": "甲", "zhi": "子"}] * 3})
raises("四柱干支不可识别抛 ValueError", qimen.chart_qimen, ValueError,
       {"pillars": [{"gan": "甲", "zhi": "子"}, {"gan": "甲", "zhi": "子"},
                    {"gan": "甲", "zhi": "子"}, {"gan": "X", "zhi": "Y"}]})

# 直接传 chart 子 dict（不带 report 外壳）
bare = no_raise("直接传 chart 子 dict 可排盘", qimen.chart_qimen, CASES[0][1]["chart"])
check("直接传 chart 子 dict 结果一致",
      bare is not None and bare["dun"]["label"] == REAL[0][1]["dun"]["label"])

# 四柱只给六十甲子序号
seq_only = {"pillars": [{"index": 0}, {"index": 12}, {"index": 14}, {"index": 55}],
            "jieqi": {"prev_qi": {"name": "霜降"}}}
z_seq = no_raise("四柱仅给序号也能排盘", qimen.chart_qimen, seq_only)
check("四柱仅给序号时柱还原", z_seq is not None and z_seq["hour"]["ganzhi"] == "己未")
check("四柱仅给序号日柱还原", z_seq is not None and z_seq["day"]["ganzhi"] == "戊寅")

# 四柱只给 ganzhi 字符串
gz_only = {"pillars": [{"ganzhi": gz} for gz in ("丙午", "戊戌", "戊寅", "己未")],
           "jieqi": {"prev_qi": {"name": "霜降"}}}
z_gz = no_raise("四柱仅给 ganzhi 也能排盘", qimen.chart_qimen, gz_only)
check("四柱仅给 ganzhi 结果一致",
      z_gz is not None and z_gz["dun"]["label"] == "阴遁二局")

# 节气缺失：降级阳遁一局并写入 limits
for label, report in (
        ("缺少 prev_qi", {"pillars": [{"gan": "甲", "zhi": "子"}, {"gan": "丙", "zhi": "子"},
                                      {"gan": "甲", "zhi": "子"}, {"gan": "乙", "zhi": "丑"}],
                          "jieqi": {}}),
        ("prev_qi 为 None", {"pillars": [{"gan": "甲", "zhi": "子"}, {"gan": "丙", "zhi": "子"},
                                         {"gan": "甲", "zhi": "子"}, {"gan": "乙", "zhi": "丑"}],
                             "jieqi": {"prev_qi": None}}),
        ("节气名不可识别", {"pillars": [{"gan": "甲", "zhi": "子"}, {"gan": "丙", "zhi": "子"},
                                        {"gan": "甲", "zhi": "子"}, {"gan": "乙", "zhi": "丑"}],
                            "jieqi": {"prev_qi": {"name": "不存在节"}}}),
):
    z = no_raise("%s 时降级起局" % label, qimen.chart_qimen, report)
    if z is None:
        continue
    expect("%s 降级阳遁一局" % label, z["dun"]["label"], "阳遁一局")
    check("%s 降级写入 limits" % label,
          any("阳遁一局" in s for s in z["limits"]), z["limits"])

# 缺少 jieqi 整个字段
no_qi = {"pillars": [{"gan": "甲", "zhi": "子"}, {"gan": "丙", "zhi": "子"},
                     {"gan": "甲", "zhi": "子"}, {"gan": "乙", "zhi": "丑"}]}
z_no_qi = no_raise("完全缺 jieqi 也能降级起局", qimen.chart_qimen, no_qi)
check("完全缺 jieqi 时 jieqi.index 为 None",
      z_no_qi is not None and z_no_qi["jieqi"]["index"] is None)

# 时辰不明
z_unreliable = no_raise("时辰不明也能起局", qimen.chart_qimen,
                        synthetic(["甲子", "丙子", "甲子", "乙丑"], reliable=False))
check("时辰不明时 reliable=False", z_unreliable is not None and z_unreliable["time"]["reliable"] is False)
check("时辰不明写入 limits", z_unreliable is not None and
      any("时辰不明" in s for s in z_unreliable["limits"]))

# 幂等：同一输入两次结果完全一致
z1 = qimen.chart_qimen(CASES[0][1])
z2 = qimen.chart_qimen(CASES[0][1])
check("同一输入两次结果一致",
      json.dumps(z1, sort_keys=True, ensure_ascii=False) ==
      json.dumps(z2, sort_keys=True, ensure_ascii=False))

# 不修改输入
snapshot = json.dumps(CASES[0][1], sort_keys=True, ensure_ascii=False)
qimen.chart_qimen(CASES[0][1])
check("排盘不修改输入 report", snapshot == json.dumps(CASES[0][1], sort_keys=True, ensure_ascii=False))


# ---------------------------------------------------------------------------
# 七、文本渲染
# ---------------------------------------------------------------------------

print("\n== 七、文本渲染 ==")

raises("渲染非 dict 抛 ValueError", qimen.render_qimen_text, ValueError, None)
raises("渲染缺 palaces 抛 ValueError", qimen.render_qimen_text, ValueError, {})

text_of = {}
for label, z in REAL:
    try:
        text_of[label] = qimen.render_qimen_text(z)
    except Exception as exc:  # noqa: BLE001
        check("%s 渲染成功" % label, False, "%s: %s" % (type(exc).__name__, exc))

check("三张盘都能渲染", len(text_of) == len(REAL))

SAMPLE_BY_KEY = dict((s["key"], s) for s in SAMPLES)

for key, sample in SAMPLE_BY_KEY.items():
    label = sample["label"]
    text = text_of.get(key)
    check("%s 有渲染结果" % label, text is not None)
    if text is None:
        continue
    lines = text.splitlines()
    check("%s 渲染非空" % label, len(lines) > 20)
    check("%s 首行含模块名与版本" % label,
          lines[0].startswith("奇门遁甲层") and qimen.VERSION in lines[0], lines[0])
    check("%s 首行点明时家转盘" % label, "转盘" in lines[0] and "拆补" in lines[0])
    for section in ("【要点】", "【九宫】", "【三奇六仪】", "【结构要点】", "【说明与局限】"):
        check("%s 含分区%s" % (label, section), section in text)
    check("%s 九宫名齐全" % label,
          all(qimen.GONG_NAME[g] in text for g in range(1, 10)))
    check("%s 八星齐全" % label,
          all(star in text for star in qimen.STAR_BY_GONG.values() if star != "天禽"))
    check("%s 八门齐全" % label,
          all(door in text for door in qimen.DOOR_BY_GONG.values()))
    check("%s 八神齐全" % label, all(god in text for god in qimen.GOD_ORDER))
    check("%s 含定局标签" % label, sample["dun"] in text, sample["dun"])
    check("%s 含四柱文本" % label, sample["pillars"] in text, sample["pillars"])
    check("%s 无制表符" % label, "\t" not in text)
    check("%s 结尾无多余空白行" % label,
          text.rstrip() == text and lines[-1].strip() != "")
    summary = (CHARTS.get(key) or {}).get("summary") or []
    check("%s summary 逐条渲染" % label,
          bool(summary) and all(item in text for item in summary))

    # 表格：所有 '|' 行显示宽度一致，'+' 行同为 3 格
    bar_lines = [ln for ln in lines if ln.startswith("|")]
    border_lines = [ln for ln in lines if ln.startswith("+")]
    widths = {qimen._width(ln) for ln in bar_lines}
    check("%s 表格每行等宽" % label, len(widths) == 1, widths)
    border_widths = {qimen._width(ln) for ln in border_lines}
    check("%s 边框行等宽" % label, len(border_widths) == 1, border_widths)
    check("%s 边框与内容同宽" % label, widths and border_widths and
          widths == border_widths, (widths, border_widths))
    check("%s 表格 15 行内容" % label, len(bar_lines) == 15, len(bar_lines))
    check("%s 中五标注寄坤二" % label, "（中五寄坤二）" in text)
    check("%s 每宫都有天盘/地盘标注" % label,
          text.count("地盘") >= 10 and text.count("天盘") >= 9)
    check("%s limits 逐条渲染" % label,
          all(item in text for item in (CHARTS.get(key) or {}).get("limits") or []))

# 手工盘的渲染也要覆盖中五值符（双星同宫）
if z_a is not None:
    text_a = no_raise("中五值符盘渲染", qimen.render_qimen_text, z_a)
    check("中五值符盘渲染含天芮+天禽", text_a is not None and "天芮+天禽" in text_a)
    check("中五值符盘渲染含寄干", text_a is not None and "己+壬" in text_a)

# _width / _pad 基本正确性
expect("_width ASCII", qimen._width("abc"), 3)
expect("_width 汉字", qimen._width("甲子"), 4)
expect("_width 混排", qimen._width("甲1"), 3)
expect("_pad 补到 10", qimen._width(qimen._pad("甲", 10)), 10)
expect("_pad 超长不截断", qimen._pad("甲乙丙丁戊", 4), "甲乙丙丁戊")


# ---------------------------------------------------------------------------
# 八、纯标准库与可编译性
# ---------------------------------------------------------------------------

print("\n== 八、纯标准库自检 ==")

MODULE_PATH = os.path.join(ROOT, "scripts", "qimen.py")
check("模块文件存在", os.path.exists(MODULE_PATH), MODULE_PATH)
source = ""
try:
    with open(MODULE_PATH, "rb") as fh:
        raw = fh.read()
    source = raw.decode("utf-8")
    check("模块文件为 UTF-8", True)
except Exception as exc:  # noqa: BLE001
    check("模块文件为 UTF-8", False, exc)

if source:
    try:
        tree = ast.parse(source)
        check("模块可解析", True)
    except SyntaxError as exc:
        tree = None
        check("模块可解析", False, exc)
    try:
        compile(source, MODULE_PATH, "exec")
        check("模块可编译", True)
    except SyntaxError as exc:
        check("模块可编译", False, exc)

    mods = set()
    for node in ast.walk(tree) if tree else ():
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                mods.add("." * node.level + (node.module or ""))
            else:
                mods.add((node.module or "").split(".")[0])
    stdlib = set(getattr(sys, "stdlib_module_names", ())) | {""}
    check("只依赖标准库", mods <= stdlib, mods)
    check("依赖仅 unicodedata", mods == {"unicodedata"}, mods)

    for bad in ("requests", "urllib", "http://", "https://", "socket",
                "subprocess", "eval(", "exec("):
        check("模块不含 %s" % bad, bad not in source)
    check("模块声明 coding", "coding" in source.splitlines()[0])
    check("模块 docstring 说明接口", "chart_qimen" in source and "render_qimen_text" in source)


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------

print("\n" + "=" * 62)
if failures:
    print("失败 %d / %d 项：" % (len(failures), total))
    for name, detail in failures:
        print("  - %s  ← %s" % (name, detail))
    print("奇门回归：%d 项，FAIL" % total)
    print("verify_qimen: FAIL")
    sys.exit(1)

print("奇门回归：%d 项" % total)
print("verify_qimen: 全部通过 %d 项 ✓" % total)
sys.exit(0)
