# -*- coding: utf-8 -*-
"""西洋占星 + 印度占星计算层回归测试（scripts/astrology.py）。

测试分三层：
1) 模块结构与确定性：API、输出字段、JSON 可序列化、同输入同输出；
2) 星历精度：用 tests/fixtures_astro.json 中 ephem 4.2.1 生成的地心视黄经/速度参考值，
   逐样本逐星比对（日月 ≤0.1°、行星 ≤0.3°），并校验恒星时、逆行标记与星座边界；
3) 占星计算：四轴几何（ASC 地平高度=0 且上升、MC 赤经=地方恒星时）、
   两种宫位制、相位几何、元素/模态/半球、月相、Vedic 岁差/27 宿/Lagna、
   渲染文本与 CLI（--astro）契约。

运行：python tests/verify_astrology.py   失败时非零退出。
"""
import json
import math
import os
import subprocess
import sys
import tempfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
CLI = os.path.join(ROOT, "scripts", "bazi.py")
FIXTURES = os.path.join(ROOT, "tests", "fixtures_astro.json")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import astrology as A  # noqa: E402

total = 0
failures = []


def check(name, ok, detail=""):
    global total
    total += 1
    if not ok:
        failures.append((name, detail))


def angdiff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def sign_index_of(lon):
    return int((lon % 360.0) // 30.0) % 12


def sign_cn_of(lon):
    return A.SIGN_CN[sign_index_of(lon)]


def section(title):
    print("【%s】" % title)


# ---------------------------------------------------------------------------
# 基准报告（经纬度齐全、时刻为 UTC 绝对时刻）
# ---------------------------------------------------------------------------
BASE_ARGS = ["--date", "2004-06-12", "--time", "10:00", "--sex", "male",
             "--longitude", "123.96", "--true-solar-time", "--focus-year", "2026"]
REPORT = {
    "input": {"date": "2004-06-12", "time": "10:00:00", "time_unknown": False,
              "zone": "Asia/Shanghai", "longitude": 123.96, "latitude": 30.0,
              "true_solar_time": True},
    "time": {"civil": "2004-06-12 10:00:00", "zone": "Asia/Shanghai",
             "utc_offset_hours": 8.0, "dst_hours": 0.0,
             "utc": "2004-06-12 02:00:00", "used": "2004-06-12 10:16:19",
             "used_kind": "tst", "longitude": 123.96},
}
CHART = A.chart_natal(REPORT)
DT_UTC = datetime(2004, 6, 12, 2, 0, 0)
JD_UT = A.julian_day(DT_UTC)
JD_TT = A.jd_tt(JD_UT)
EPS = A.obliquity_degrees(JD_TT)
RAMC = A.local_sidereal_degrees(JD_UT, 123.96)
ANGLE_RAW = A.angles(JD_UT, 123.96, 30.0)
PLANET_MAP = {p["key"]: p for p in CHART["planets"]}
PLANET_CATEGORY = {p["key"]: p["category"] for p in A.PLANETS}


def run_cli(*args):
    """运行 CLI 并收集输出。

    说明：在受限沙箱中（如 DSH 文件沙箱）子进程无法创建匿名管道，因此不能用
    ``capture_output=True``；这里改用临时文件重定向 stdout/stderr，兼容两种环境。
    """
    out_fd, out_path = tempfile.mkstemp(suffix=".out.txt")
    err_fd, err_path = tempfile.mkstemp(suffix=".err.txt")
    os.close(out_fd)
    os.close(err_fd)
    try:
        with open(out_path, "w", encoding="utf-8", errors="replace") as fout, \
                open(err_path, "w", encoding="utf-8", errors="replace") as ferr:
            proc = subprocess.run([PY, CLI] + list(args), stdout=fout, stderr=ferr,
                                  stdin=subprocess.DEVNULL, timeout=180)
        with open(out_path, "r", encoding="utf-8", errors="replace") as fh:
            stdout = fh.read()
        with open(err_path, "r", encoding="utf-8", errors="replace") as fh:
            stderr = fh.read()
        return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
    finally:
        for path in (out_path, err_path):
            try:
                os.remove(path)
            except OSError:
                pass



def cli_json(*args):
    r = run_cli(*(list(args) + ["--json"]))
    if r.returncode != 0:
        return None, r
    try:
        return json.loads(r.stdout), r
    except ValueError:
        return None, r


# ---------------------------------------------------------------------------
# 1. 模块常量与 API
# ---------------------------------------------------------------------------
def test_module_api():
    section("模块常量与 API")
    check("VERSION 非空字符串", isinstance(A.VERSION, str) and A.VERSION)
    check("MODEL 为说明字符串", isinstance(A.MODEL, str) and len(A.MODEL) > 50)
    check("chart_natal 可调用", callable(A.chart_natal))
    check("render_natal_text 可调用", callable(A.render_natal_text))
    check("LIMITS 至少 4 条", isinstance(A.LIMITS, list) and len(A.LIMITS) >= 4)
    joined = " ".join(A.LIMITS)
    check("LIMITS 说明低精度星历", "低精度" in joined or "星历" in joined)
    check("LIMITS 说明宫位制流派", "宫位制" in joined or "宫位" in joined)
    check("LIMITS 说明 Vedic 岁差近似", "岁差" in joined)
    check("LIMITS 声明占星不作事实预测", "预测" in joined or "命运" in joined)
    check("12 星座与中文名对齐", len(A.SIGNS) == 12 and len(A.SIGN_CN) == 12)
    check("十星定义完整", len(A.PLANETS) == 10
          and [p["key"] for p in A.PLANETS] == ["sun", "moon", "mercury", "venus",
                                               "mars", "jupiter", "saturn",
                                               "uranus", "neptune", "pluto"])
    check("相位 5 种且角度正确",
          [x[1] for x in A.ASPECTS] == [0, 60, 90, 120, 180] and len(A.ASPECTS) == 5)
    check("容许度符合需求（发光体8/个人星6/外行星5/角点6）",
          A.ASPECT_ORB == {"luminary": 8.0, "personal": 6.0, "outer": 5.0, "angle": 6.0})
    check("27 宿名单与宿主星序列", len(A.NAKSHATRAS) == 27 and len(A.NAKSHATRA_RULERS) == 9)


# ---------------------------------------------------------------------------
# 2. 输出结构与确定性
# ---------------------------------------------------------------------------
def test_structure():
    section("输出结构与确定性")
    for key in ("version", "method", "input", "planets", "angles", "houses",
                "aspects", "balance", "moon_phase", "vedic", "summary",
                "limits", "warnings"):
        check("chart 含字段 %s" % key, key in CHART)
    check("version 与常量一致", CHART.get("version") == A.VERSION)
    check("planets 为 10 项", len(CHART["planets"]) == 10)
    needed = ("key", "name", "en", "category", "lon", "sign", "sign_cn",
              "degree", "element", "modality", "retrograde", "speed", "house")
    check("planets 项字段完整",
          all(all(k in p for k in needed) for p in CHART["planets"]),
          "缺字段: %s" % [p["key"] for p in CHART["planets"] if not all(k in p for k in needed)])
    check("planets 顺序与 PLANETS 一致",
          [p["key"] for p in CHART["planets"]] == [p["key"] for p in A.PLANETS])
    check("黄经均在 [0,360)",
          all(0.0 <= p["lon"] < 360.0 for p in CHART["planets"]))
    check("degree 在星座内 [0,30)",
          all(0.0 <= p["degree"] < 30.0 for p in CHART["planets"]))
    check("sign_cn 与 lon 星座一致",
          all(p["sign_cn"] == sign_cn_of(p["lon"]) for p in CHART["planets"]))
    check("四轴齐全", set(CHART["angles"]) == {"asc", "mc", "desc", "ic"})
    check("四轴字段完整",
          all(all(k in b for k in ("key", "name", "en", "lon", "sign", "sign_cn", "degree"))
              for b in CHART["angles"].values()))
    houses = CHART["houses"]
    check("houses 顶层层级", houses.get("system") == "whole_sign"
          and len(houses.get("cusps") or []) == 12)
    systems = houses.get("systems") or {}
    check("houses.systems 含整宫制与 Placidus",
          "whole_sign" in systems and "placidus" in systems)
    check("两种宫位制宫头各 12 个",
          len(systems["whole_sign"]["cusps"]) == 12
          and len(systems["placidus"]["cusps"]) == 12)
    check("balance 三段齐全",
          set(CHART["balance"]) == {"elements", "modalities", "hemispheres"})
    check("moon_phase 字段齐全",
          all(k in CHART["moon_phase"] for k in ("phase", "angle", "illum", "phase8")))
    vedic = CHART["vedic"]
    check("vedic 字段齐全",
          all(k in vedic for k in ("ayanamsa", "ayanamsa_system", "sidereal_planets",
                                   "sun_sign", "moon_sign", "lagna", "nakshatra")))
    check("vedic.sidereal_planets 十星", len(vedic["sidereal_planets"]) == 10)
    check("summary 为中文摘要列表", isinstance(CHART["summary"], list)
          and len(CHART["summary"]) >= 10
          and all(isinstance(x, str) and x for x in CHART["summary"]))
    check("limits 与模块 LIMITS 一致", CHART["limits"] == A.LIMITS)
    check("warnings 为列表", isinstance(CHART["warnings"], list))
    check("经纬度齐全时无「纬度默认」警告",
          not any("纬度" in w for w in CHART["warnings"]))
    check("input 回显 UTC 绝对时刻", CHART["input"].get("utc") == "2004-06-12 02:00:00")
    check("input 回显时间来源", CHART["input"].get("time_source") == "report.time.utc")
    check("input 回显经纬度", CHART["input"].get("longitude") == 123.96
          and abs(CHART["input"].get("latitude", 0.0) - 30.0) < 1e-9
          and CHART["input"].get("latitude_default") is False)
    check("确定性：同输入两次结果一致", A.chart_natal(REPORT) == CHART)
    dumped = json.dumps(CHART, ensure_ascii=False)
    check("JSON 可序列化", isinstance(dumped, str) and len(dumped) > 1000)
    check("JSON 无 NaN/Infinity", "NaN" not in dumped and "Infinity" not in dumped)


# ---------------------------------------------------------------------------
# 3. 星历精度（ephem 参考夹具）
# ---------------------------------------------------------------------------
def fixture_report(sample):
    return {
        "input": {"date": sample["utc"][:10], "time": sample["utc"][11:],
                  "time_unknown": False, "zone": "UTC",
                  "longitude": sample["longitude"], "latitude": sample["latitude"]},
        "time": {"utc": sample["utc"], "utc_offset_hours": 0.0},
    }


def test_accuracy(samples):
    section("星历精度（对 ephem 夹具）")
    check("夹具数量 10~20 个", 10 <= len(samples) <= 20, "n=%d" % len(samples))
    retro_dates = [s["id"] for s in samples if s.get("retrograde")]
    check("夹具含 ≥3 个逆行星日期", len(retro_dates) >= 3, ",".join(retro_dates))
    check("夹具每样本含十星黄经与速度",
          all(len(s["planets"]) == 10 and all(k in s["planets"] for k in PLANET_MAP)
              for s in samples))
    worst = {k: 0.0 for k in PLANET_MAP}
    for sample in samples:
        chart = A.chart_natal(fixture_report(sample))
        by_key = {p["key"]: p for p in chart["planets"]}
        # 十星黄经
        for key, ref in sample["planets"].items():
            tol = 0.1 if key in ("sun", "moon") else 0.3
            err = angdiff(by_key[key]["lon"], ref["lon"])
            worst[key] = max(worst[key], err)
            check("%s 黄经精度 %s" % (sample["id"], key), err <= tol,
                  "err=%.5f° tol=%.1f°" % (err, tol))
        # 星座分类与参考黄经一致
        check("%s 星座分类一致" % sample["id"],
              all(sign_cn_of(ref["lon"]) == by_key[key]["sign_cn"]
                  for key, ref in sample["planets"].items()))
        # 逆行标记（跳过相站附近 |速度|<0.01°/日 的星，避免随误差翻转）
        robust = {k for k, v in sample["planets"].items()
                  if k not in ("sun", "moon") and abs(v["speed"]) >= 0.01}
        ref_retro = set(sample.get("retrograde") or []) & robust
        ours_retro = {p["key"] for p in chart["planets"] if p["retrograde"]} & robust
        check("%s 逆行标记一致" % sample["id"], ours_retro == ref_retro,
              "ours=%s ref=%s" % (sorted(ours_retro), sorted(ref_retro)))
        # 地方恒星时（ephem 视恒星时与均恒星时差 <0.005°）
        dt = datetime.strptime(sample["utc"], "%Y-%m-%d %H:%M:%S")
        sid = A.local_sidereal_degrees(A.julian_day(dt), sample["longitude"])
        check("%s 地方恒星时" % sample["id"], angdiff(sid, sample["sidereal_deg"]) <= 0.01,
              "ours=%.5f ref=%.5f" % (sid, sample["sidereal_deg"]))
        # 速度与参考一致（度/日）
        jd_tt_value = A.jd_tt(A.julian_day(dt))
        spd_ok = True
        spd_detail = []
        for key in ("mercury", "venus", "mars", "jupiter", "saturn"):
            ref_speed = sample["planets"][key]["speed"]
            ours = A.body_speed(key, jd_tt_value)
            if abs(ours - ref_speed) > 0.02:
                spd_ok = False
                spd_detail.append("%s %.4f vs %.4f" % (key, ours, ref_speed))
        check("%s 行星速度量值" % sample["id"], spd_ok, "; ".join(spd_detail))
    check("日月黄经最大误差 ≤0.1°", worst["sun"] <= 0.1 and worst["moon"] <= 0.1,
          "sun=%.5f moon=%.5f" % (worst["sun"], worst["moon"]))
    check("其它行星黄经最大误差 ≤0.3°",
          all(worst[k] <= 0.3 for k in worst if k not in ("sun", "moon")),
          ", ".join("%s=%.4f" % (k, v) for k, v in worst.items()))


# ---------------------------------------------------------------------------
# 4. 太阳星座边界与黄道分类
# ---------------------------------------------------------------------------
def test_sign_boundary(samples):
    section("星座边界")
    by_id = {s["id"]: s for s in samples}
    cases = [("s13", "双鱼座", 359.0, 360.0), ("s14", "白羊座", 0.0, 1.5),
             ("s15", "双子座", 89.0, 90.0), ("s16", "巨蟹座", 90.0, 91.5)]
    for sid, sign_cn, lo, hi in cases:
        if sid not in by_id:
            check("边界样本 %s 存在" % sid, False, "夹具缺失")
            continue
        ref_lon = by_id[sid]["planets"]["sun"]["lon"]
        check("边界样本 %s 参考黄经落在预期区间" % sid, lo <= ref_lon < hi,
              "ref=%.4f" % ref_lon)
        chart = A.chart_natal(fixture_report(by_id[sid]))
        sun = {p["key"]: p for p in chart["planets"]}["sun"]
        check("边界样本 %s 太阳落 %s" % (sid, sign_cn), sun["sign_cn"] == sign_cn,
              "实际 %s %.2f°" % (sun["sign_cn"], sun["degree"]))
    check("十二星座元素按火土风水循环",
          A.SIGN_ELEMENT == ["fire", "earth", "air", "water"] * 3)
    check("十二星座模态按基本固定变动循环",
          A.SIGN_MODALITY == ["cardinal", "fixed", "mutable"] * 4)


# ---------------------------------------------------------------------------
# 5. 速度与逆行
# ---------------------------------------------------------------------------
def test_speed_retrograde():
    section("速度与逆行")
    check("金星 2004-06-12 逆行", PLANET_MAP["venus"]["retrograde"] is True)
    check("金星速度为负", PLANET_MAP["venus"]["speed"] < 0)
    check("天王星 2004-06-12 逆行", PLANET_MAP["uranus"]["retrograde"] is True)
    check("太阳永不逆行", PLANET_MAP["sun"]["retrograde"] is False
          and PLANET_MAP["moon"]["retrograde"] is False)
    check("逆行集合 = {金星,天王星,海王星,冥王星}",
          {p["key"] for p in CHART["planets"] if p["retrograde"]}
          == {"venus", "uranus", "neptune", "pluto"})
    check("逆行标记与速度符号一致",
          all(p["retrograde"] == (p["speed"] < 0 and p["key"] not in ("sun", "moon"))
              for p in CHART["planets"]))
    check("太阳日速度约 1°/日", 0.9 <= PLANET_MAP["sun"]["speed"] <= 1.05,
          "%.4f" % PLANET_MAP["sun"]["speed"])
    check("月亮日速度约 12~14°/日", 11.0 <= PLANET_MAP["moon"]["speed"] <= 15.0,
          "%.4f" % PLANET_MAP["moon"]["speed"])
    check("水星日速度合理（-1.5~2.5）", -1.5 <= PLANET_MAP["mercury"]["speed"] <= 2.5)

    # body_speed 是中心差分（前后各 1 天），与夹具速度量值一致
    for sid, key in (("s05", "mercury"), ("s09", "saturn"), ("s17", "jupiter")):
        sample = next((s for s in FIXTURE_SAMPLES if s["id"] == sid), None)
        if not sample:
            check("速度样本 %s 存在" % sid, False)
            continue
        dt = datetime.strptime(sample["utc"], "%Y-%m-%d %H:%M:%S")
        ours = A.body_speed(key, A.jd_tt(A.julian_day(dt)))
        check("速度 %s/%s 与参考差 ≤0.02°/日" % (sid, key),
              abs(ours - sample["planets"][key]["speed"]) <= 0.02,
              "ours=%.4f ref=%.4f" % (ours, sample["planets"][key]["speed"]))


# ---------------------------------------------------------------------------
# 6. 相位
# ---------------------------------------------------------------------------
def test_aspects():
    section("相位")
    aspects = CHART["aspects"]
    check("aspects 非空（基准盘应有相位）", len(aspects) > 0)
    check("相位角度均为 0/60/90/120/180", all(a["angle"] in (0, 60, 90, 120, 180)
                                              for a in aspects))
    check("相位 orb 不超过容许度",
          all(a["orb"] <= a["orb_allowed"] + 1e-6 for a in aspects))
    check("相位 separation 与 angle 差 = orb",
          all(abs(abs(a["separation"] - a["angle"]) - a["orb"]) < 0.01 for a in aspects))
    check("相位 type_cn 与 type 对应",
          all({"conjunction": "合相", "sextile": "六合", "square": "刑相",
               "trine": "拱相", "opposition": "冲相"}[a["type"]] == a["type_cn"]
              for a in aspects))
    check("相位不含角点-角点组合",
          not any(a["a"] in ("asc", "mc", "desc", "ic")
                  and a["b"] in ("asc", "mc", "desc", "ic") for a in aspects))
    check("相位天体对不重复",
          len({tuple(sorted((a["a"], a["b"]))) for a in aspects}) == len(aspects))
    check("相位 a/b 均为已知天体",
          all(a["a"] in PLANET_MAP or a["a"] in A.ANGLE_BY_KEY for a in aspects)
          and all(a["b"] in PLANET_MAP or a["b"] in A.ANGLE_BY_KEY for a in aspects))
    check("容许度取双方类别平均值",
          all(abs(a["orb_allowed"] - A.aspect_orb_allowed(
              "angle" if a["a"] in A.ANGLE_BY_KEY else PLANET_CATEGORY[a["a"]],
              "angle" if a["b"] in A.ANGLE_BY_KEY else PLANET_CATEGORY[a["b"]])) < 1e-6
              for a in aspects))

    def pts(pairs):
        return [{"key": k, "name": k, "category": c, "lon": lon} for k, c, lon in pairs]

    def first(aspects_list):
        return aspects_list[0] if aspects_list else None

    case = first(A.find_aspects(pts([("sun", "luminary", 0.0),
                                     ("moon", "luminary", 90.0)]), []))
    check("相位单元：日月 90° 判为刑相",
          case is not None and case["type"] == "square" and case["orb"] < 1e-6)
    case = first(A.find_aspects(pts([("sun", "luminary", 0.0),
                                     ("moon", "luminary", 60.0)]), []))
    check("相位单元：日月 60° 判为六合", case is not None and case["type"] == "sextile")
    case = first(A.find_aspects(pts([("sun", "luminary", 0.0),
                                     ("moon", "luminary", 120.0)]), []))
    check("相位单元：日月 120° 判为拱相", case is not None and case["type"] == "trine")
    case = first(A.find_aspects(pts([("sun", "luminary", 0.0),
                                     ("moon", "luminary", 180.0)]), []))
    check("相位单元：日月 180° 判为冲相", case is not None and case["type"] == "opposition")
    case = first(A.find_aspects(pts([("sun", "luminary", 0.0),
                                     ("moon", "luminary", 7.0)]), []))
    check("相位单元：日月 7° 合相在容许度内",
          case is not None and case["type"] == "conjunction" and abs(case["orb"] - 7.0) < 1e-6)
    check("相位单元：日月 10° 超出合相容许度（无相位）",
          not A.find_aspects(pts([("sun", "luminary", 0.0),
                                  ("moon", "luminary", 10.0)]), []))
    check("相位单元：日月 100° 超出刑相容许度（无相位）",
          not A.find_aspects(pts([("sun", "luminary", 0.0),
                                  ("moon", "luminary", 100.0)]), []))
    case = first(A.find_aspects(pts([("jupiter", "outer", 0.0),
                                     ("saturn", "outer", 90.0)]), []))
    check("相位单元：外行星刑相容许度 5°",
          case is not None and abs(case["orb_allowed"] - 5.0) < 1e-6)
    case = first(A.find_aspects(pts([("sun", "luminary", 0.0),
                                     ("moon", "luminary", 90.0)]),
                                [{"key": "asc", "name": "上升点",
                                  "category": "angle", "lon": 0.0}]))
    check("相位单元：角点参与时容许度取平均（7°）",
          any(a["orb_allowed"] == 7.0 for a in
              A.find_aspects(pts([("sun", "luminary", 0.0)]),
                             [{"key": "asc", "name": "上升点",
                               "category": "angle", "lon": 90.0}])))
    check("相位单元：角点-角点不参与",
          not A.find_aspects([], [{"key": "asc", "name": "上升点",
                                   "category": "angle", "lon": 0.0},
                                  {"key": "mc", "name": "天顶",
                                   "category": "angle", "lon": 90.0}]))


# ---------------------------------------------------------------------------
# 7. 宫位
# ---------------------------------------------------------------------------
def test_houses():
    section("宫位")
    asc = CHART["angles"]["asc"]["lon"]
    ws = CHART["houses"]["systems"]["whole_sign"]["cusps"]
    first = int(asc // 30.0) * 30.0
    check("整宫制第 1 宫头 = ASC 所在星座 0°",
          angdiff(ws[0], first) <= 0.001, "ws[0]=%.4f first=%.4f" % (ws[0], first))
    check("整宫制每宫相隔 30°",
          all(angdiff(ws[i], (first + 30.0 * i) % 360.0) <= 0.001 for i in range(12)))
    asc_sign = sign_index_of(asc)
    check("house_of_sign：ASC 星座为第 1 宫", A.house_of_sign(asc_sign, asc_sign) == 1)
    check("house_of_sign：ASC 前一星座为第 12 宫",
          A.house_of_sign((asc_sign + 11) % 12, asc_sign) == 12)
    check("整宫制行星宫位与星座关系一致",
          all(p["house"] == A.house_of_sign(sign_index_of(p["lon"]), asc_sign)
              for p in CHART["planets"]))

    placidus = CHART["houses"]["systems"]["placidus"]
    check("Placidus 在 30°N 可用", placidus["available"] is True)
    pl = placidus["cusps"]
    mc = CHART["angles"]["mc"]["lon"]
    check("Placidus 第 1 宫头 = ASC", angdiff(pl[0], asc) <= 0.001)
    check("Placidus 第 10 宫头 = MC", angdiff(pl[9], mc) <= 0.001)
    check("Placidus 第 4 宫头 = MC+180", angdiff(pl[3], mc + 180.0) <= 0.001)
    check("Placidus 第 7 宫头 = ASC+180", angdiff(pl[6], asc + 180.0) <= 0.001)
    spans = []
    for i in range(12):
        span = (pl[(i + 1) % 12] - pl[i]) % 360.0
        spans.append(span)
    check("Placidus 宫头解卷绕后严格递增", all(s > 0.0 for s in spans),
          "spans=%s" % ["%.2f" % s for s in spans[:6]])
    check("Placidus 每宫跨度 <200°", all(s < 200.0 for s in spans))
    check("Placidus 宫头单调（几何顺序）",
          abs(sum(spans) - 360.0) < 1e-6)
    check("house_of_longitude：每个宫头落在对应宫",
          all(A.house_of_longitude(pl[i], pl) == i + 1 for i in range(12)))
    check("house_of_longitude：ASC 落第 1 宫",
          A.house_of_longitude(pl[0], pl) == 1)
    check("行星 Placidus 宫位在 1~12",
          all(1 <= p["house_placidus"] <= 12 for p in CHART["planets"]))
    check("两种宫位制并存且都可用", CHART["houses"]["system"] == "whole_sign"
          and len(CHART["houses"]["cusps"]) == 12)

    # 高纬退化回退
    high = dict(REPORT)
    high["input"] = dict(REPORT["input"])
    high["input"]["latitude"] = 80.0
    chart80 = A.chart_natal(high)
    pl80 = chart80["houses"]["systems"]["placidus"]
    check("高纬 80°N：Placidus 标记不可用", pl80["available"] is False)
    check("高纬 80°N：回退整宫制并给出警告",
          any("Placidus" in w for w in chart80["warnings"]))
    check("高纬 80°N：行星无 Placidus 宫位",
          all(p["house_placidus"] is None for p in chart80["planets"]))
    check("高纬 80°N：整宫制仍正确", angdiff(
        chart80["houses"]["cusps"][0], int(chart80["angles"]["asc"]["lon"] // 30) * 30.0) <= 0.001)


# ---------------------------------------------------------------------------
# 8. 四轴几何
# ---------------------------------------------------------------------------
def test_angles():
    section("四轴几何")
    asc = ANGLE_RAW["asc"]
    mc = ANGLE_RAW["mc"]
    check("DESC = ASC+180°", angdiff(ANGLE_RAW["desc"], asc + 180.0) < 1e-9)
    check("IC = MC+180°", angdiff(ANGLE_RAW["ic"], mc + 180.0) < 1e-9)
    check("ASC 与 MC 不同", angdiff(asc, mc) > 1e-6)
    check("黄赤交角在 23.2°~23.5°", 23.2 < EPS < 23.5, "eps=%.4f" % EPS)

    # MC：赤经应等于地方恒星时（RAMC）
    ra_mc, _ = A._ecl_to_equatorial(mc, EPS)
    check("MC 赤经 = 地方恒星时 RAMC", angdiff(ra_mc, RAMC) <= 1e-4,
          "ra=%.6f ramc=%.6f" % (ra_mc, RAMC))

    # ASC：该黄道点地平高度应为 0，且位于东方地平（正在升起）
    ra_asc, dec_asc = A._ecl_to_equatorial(asc, EPS)
    hour_angle = math.radians(RAMC - ra_asc)
    phi = math.radians(30.0)
    alt = math.degrees(math.asin(
        math.sin(phi) * math.sin(math.radians(dec_asc))
        + math.cos(phi) * math.cos(math.radians(dec_asc)) * math.cos(hour_angle)))
    check("ASC 地平高度 = 0°", abs(alt) <= 1e-6, "alt=%.2e" % alt)
    h_norm = ((RAMC - ra_asc + 180.0) % 360.0) - 180.0
    check("ASC 位于东方地平（时角为负，正在升起）", -180.0 < h_norm < 0.0,
          "H=%.2f" % h_norm)

    # 输出中的四轴与原始值一致
    check("输出 ASC 与几何一致",
          angdiff(CHART["angles"]["asc"]["lon"], asc) <= 0.001)
    check("输出 MC 与几何一致",
          angdiff(CHART["angles"]["mc"]["lon"], mc) <= 0.001)
    check("输出 ASC 星座为狮子座", CHART["angles"]["asc"]["sign_cn"] == "狮子座",
          "实际 %s" % CHART["angles"]["asc"]["sign_cn"])
    check("输出 MC 星座为金牛座", CHART["angles"]["mc"]["sign_cn"] == "金牛座")


# ---------------------------------------------------------------------------
# 9. Vedic（印度占星）
# ---------------------------------------------------------------------------
def test_vedic():
    section("Vedic 印度占星")
    ay2000 = A.ayanamsa(A.jd_tt(A.julian_day(datetime(2000, 1, 1, 12))))
    check("J2000 Lahiri ayanamsa ≈ 23.85°", abs(ay2000 - 23.85306) <= 0.01,
          "%.5f" % ay2000)
    ay1900 = A.ayanamsa(A.jd_tt(A.julian_day(datetime(1900, 1, 1, 12))))
    ay2025 = A.ayanamsa(A.jd_tt(A.julian_day(datetime(2025, 1, 1, 12))))
    check("ayanamsa 随时间递增", ay1900 < ay2000 < ay2025,
          "%.3f < %.3f < %.3f" % (ay1900, ay2000, ay2025))
    check("2025 ayanamsa 在 24.0°~24.4°", 24.0 < ay2025 < 24.4, "%.3f" % ay2025)
    check("输出 ayanamsa 与基准时刻一致",
          abs(CHART["vedic"]["ayanamsa"] - round(A.ayanamsa(JD_TT), 4)) <= 1e-4)
    check("ayanamsa_system 标注 Lahiri", "Lahiri" in CHART["vedic"]["ayanamsa_system"])

    sidereal_sun = A.sidereal_longitude(PLANET_MAP["sun"]["lon"], JD_TT)
    check("恒星黄经 = 回归黄经 − ayanamsa",
          angdiff(sidereal_sun, (PLANET_MAP["sun"]["lon"] - A.ayanamsa(JD_TT)) % 360) < 1e-6)
    check("Vedic 太阳星座一致",
          CHART["vedic"]["sun_sign"] == sign_cn_of(sidereal_sun),
          "%s vs %s" % (CHART["vedic"]["sun_sign"], sign_cn_of(sidereal_sun)))
    sidereal_moon = A.sidereal_longitude(PLANET_MAP["moon"]["lon"], JD_TT)
    check("Vedic 月亮星座一致",
          CHART["vedic"]["moon_sign"] == sign_cn_of(sidereal_moon))
    sidereal_asc = A.sidereal_longitude(CHART["angles"]["asc"]["lon"], JD_TT)
    check("Vedic Lagna 星座一致",
          CHART["vedic"]["lagna"]["sign_cn"] == sign_cn_of(sidereal_asc))
    check("Vedic 十星恒星黄经逐一自洽",
          all(angdiff(CHART["vedic"]["sidereal_planets"][p["key"]]["lon"],
                      A.sidereal_longitude(p["lon"], JD_TT)) <= 0.001
              for p in CHART["planets"]))

    nak0 = A.nakshatra_of(0.0)
    check("Nakshatra：黄经 0° 为 Ashwini 第 1 宿",
          nak0["index"] == 1 and nak0["name"] == "Ashwini")
    check("Nakshatra：Ashwini 宿主星 Ketu（计都）",
          nak0["ruler"] == "Ketu" and nak0["ruler_cn"] == "计都")
    check("Nakshatra：pada 从 1 开始", nak0["pada"] == 1)
    check("Nakshatra：13.5° 为 Bharani",
          A.nakshatra_of(13.5)["index"] == 2)
    check("Nakshatra：359.9° 为 Revati 第 27 宿",
          A.nakshatra_of(359.9)["index"] == 27
          and A.nakshatra_of(359.9)["name"] == "Revati")
    for lon, expected in ((0.1, 1), (3.5, 2), (6.8, 3), (10.1, 4)):
        check("Nakshatra：pada 边界 %.1f°→pada%d" % (lon, expected),
              A.nakshatra_of(lon)["pada"] == expected)
    span = 360.0 / 27.0
    indices_ok = all(A.nakshatra_of(i * span + 0.5)["index"] == i + 1 for i in range(27))
    check("Nakshatra：27 宿等分 13°20′ 全覆盖", indices_ok)
    rulers_ok = all(A.nakshatra_of(i * span + 0.5)["ruler"] == A.NAKSHATRA_RULERS[i % 9]
                    for i in range(27))
    check("Nakshatra：宿主星按 Vimshottari 序列循环", rulers_ok)
    padas_ok = all(A.nakshatra_of(i * span + off)["pada"] == pada
                   for i in range(27)
                   for off, pada in ((0.1, 1), (3.5, 2), (6.8, 3), (10.1, 4)))
    check("Nakshatra：每宿四 pada 均分 3°20′", padas_ok)
    moon_nak = A.nakshatra_of(sidereal_moon)
    check("Vedic 月亮 Nakshatra 与恒星黄经一致",
          CHART["vedic"]["nakshatra"]["name"] == moon_nak["name"]
          and CHART["vedic"]["nakshatra"]["pada"] == moon_nak["pada"]
          and CHART["vedic"]["nakshatra"]["ruler"] == moon_nak["ruler"])
    check("Vedic Nakshatra 字段合法",
          1 <= CHART["vedic"]["nakshatra"]["index"] <= 27
          and 1 <= CHART["vedic"]["nakshatra"]["pada"] <= 4
          and CHART["vedic"]["nakshatra"]["ruler_cn"])


# ---------------------------------------------------------------------------
# 10. 元素 / 模态 / 半球 / 月相
# ---------------------------------------------------------------------------
def test_balance_phase():
    section("元素·模态·半球·月相")
    bal = CHART["balance"]
    elements = bal["elements"]
    modalities = bal["modalities"]
    hemi = bal["hemispheres"]
    check("元素四类齐全且合计 10",
          set(elements) == {"fire", "earth", "air", "water"}
          and sum(elements.values()) == 10)
    check("模态三类齐全且合计 10",
          set(modalities) == {"cardinal", "fixed", "mutable"}
          and sum(modalities.values()) == 10)
    check("半球上下合计 10", hemi["above"] + hemi["below"] == 10)
    check("半球东西合计 10", hemi["east"] + hemi["west"] == 10)
    check("元素统计与星座一致", all(
        sum(1 for p in CHART["planets"] if p["element"] == key) == count
        for key, count in elements.items()))
    check("模态统计与星座一致", all(
        sum(1 for p in CHART["planets"] if p["modality"] == key) == count
        for key, count in modalities.items()))
    asc_sign = sign_index_of(CHART["angles"]["asc"]["lon"])
    check("balance_of 重算一致",
          A.balance_of(CHART["planets"], asc_sign) == bal)

    phases = {
        "新月": A.moon_phase(0.0, 0.0),
        "上弦月": A.moon_phase(0.0, 90.0),
        "满月": A.moon_phase(0.0, 180.0),
        "下弦月": A.moon_phase(0.0, 270.0),
    }
    check("月相：日月 0° 为新月", phases["新月"]["phase"] == "新月"
          and abs(phases["新月"]["illum"]) < 1e-9)
    check("月相：日月 90° 为上弦月", phases["上弦月"]["phase"] == "上弦月"
          and abs(phases["上弦月"]["illum"] - 0.5) < 1e-6)
    check("月相：日月 180° 为满月", phases["满月"]["phase"] == "满月"
          and abs(phases["满月"]["illum"] - 1.0) < 1e-6)
    check("月相：日月 270° 为下弦月", phases["下弦月"]["phase"] == "下弦月"
          and abs(phases["下弦月"]["illum"] - 0.5) < 1e-6)
    check("月相：黄经差归一化到 [0,360)",
          A.moon_phase(10.0, 5.0)["angle"] == 355.0)
    check("月相：照亮比公式 (1-cosΔλ)/2 自洽",
          all(abs(A.moon_phase(0.0, x)["illum"]
                  - round((1 - math.cos(math.radians(x))) / 2.0, 4)) < 1e-3
              for x in (0, 45, 90, 135, 180, 225, 270, 315)))
    phase = CHART["moon_phase"]
    check("输出月相照亮比在 [0,1]", 0.0 <= phase["illum"] <= 1.0)
    check("输出月相黄经差在 [0,360)", 0.0 <= phase["angle"] < 360.0)
    check("输出月相与低层函数一致",
          phase == A.moon_phase(PLANET_MAP["sun"]["lon"], PLANET_MAP["moon"]["lon"]))


# ---------------------------------------------------------------------------
# 11. 渲染文本
# ---------------------------------------------------------------------------
def test_render():
    section("中文渲染")
    try:
        text = A.render_natal_text(CHART)
    except Exception as exc:  # noqa: BLE001 - 渲染异常必须成为失败项
        text = ""
        check("render_natal_text 完整跑完（无 KeyError/异常）", False, repr(exc))
    else:
        check("render_natal_text 完整跑完（无 KeyError/异常）", True)
    for header in ("【西洋占星·本命盘】", "【十星落座】", "【四轴】",
                   "【宫位·整宫制】", "【宫位·Placidus 半弧法】", "【相位】",
                   "【元素·模态·半球】", "【月相】",
                   "【印度占星（Vedic / Lahiri）】", "【综合摘要】",
                   "【方法学与局限】"):
        check("渲染含段落 %s" % header, header in text)
    check("渲染含上升/天顶标签", "上升 ASC" in text and "天顶 MC" in text)
    check("渲染含十星中文名", all(p["name"] in text for p in CHART["planets"]))
    check("渲染含星座中文名", all(p["sign_cn"] in text for p in CHART["planets"]))
    check("渲染含逆行标记", "逆" in text and "+" in text)
    check("渲染含 12 宫宫头", all(("%2d宫" % i) in text for i in (1, 6, 12)))
    lines = text.split("\n")
    check("渲染为空行分隔的多行文本", len(lines) > 40, "lines=%d" % len(lines))
    check("渲染无残留占位符", "KeyError" not in text and "{" not in text.split("【")[0])
    # 高纬盘渲染（Placidus 回退段）
    high = json.loads(json.dumps(REPORT))
    high["input"]["latitude"] = 80.0
    high_text = A.render_natal_text(A.chart_natal(high))
    check("高纬盘渲染含回退说明", "高纬退化" in high_text)
    # 兜底盘渲染
    fallback_text = A.render_natal_text(A.chart_natal({}))
    check("缺失输入的兜底盘也能渲染", "【西洋占星·本命盘】" in fallback_text
          and len(fallback_text.split("\n")) > 30)


# ---------------------------------------------------------------------------
# 12. 鲁棒性
# ---------------------------------------------------------------------------
def test_robustness():
    section("鲁棒性与时间解析")
    empty = A.chart_natal({})
    check("空报告不崩溃且给出 10 星", len(empty["planets"]) == 10)
    check("空报告有兜底警告", any("兜底" in w for w in empty["warnings"]))
    check("空报告纬度默认标记", empty["input"]["latitude_default"] is True)
    check("空报告 vedic 仍存在（融合层依赖）", bool(empty.get("vedic")))

    used = A.chart_natal({"time": {"used": "2004-06-12 10:16:19", "used_kind": "tst"},
                          "input": {"longitude": 123.96}})
    check("仅有 time.used 时可用并标注来源",
          used["input"]["time_source"].startswith("report.time.used"))
    check("仅有 time.used 时警告真太阳时近似",
          any("真太阳时" in w for w in used["warnings"]))

    civil = A.chart_natal({"time": {"utc": "bad", "civil": "2004-06-12 10:00:00",
                                    "utc_offset_hours": 8.0},
                           "input": {"longitude": 123.96}})
    check("time.utc 非法时退回 civil−utc_offset",
          civil["input"]["time_source"] == "report.time.civil-utc_offset"
          and civil["input"]["utc"] == "2004-06-12 02:00:00")

    unknown = A.chart_natal({"input": {"date": "2004-06-12", "time": "10:00",
                                       "time_unknown": True, "longitude": 123.96},
                             "time": {"utc": "2004-06-12 02:00:00"}})
    check("time_unknown 时给出警告",
          any("时辰未知" in w for w in unknown["warnings"]))

    lon_norm = A.chart_natal({"input": {"longitude": 200.0},
                              "time": {"utc": "2004-06-12 02:00:00"}})
    check("经度超范围自动归一化到 (-180,180]",
          abs(lon_norm["input"]["longitude"] + 160.0) < 1e-9,
          "%.2f" % lon_norm["input"]["longitude"])

    polar = A.chart_natal({"input": {"longitude": 0.0, "latitude": -85.0},
                           "time": {"utc": "2004-06-12 02:00:00"}})
    check("南极高纬不崩溃", len(polar["planets"]) == 10
          and polar["houses"]["systems"]["placidus"]["available"] is False)
    check("极区盘 angles 仍在 [0,360)",
          all(0.0 <= b["lon"] < 360.0 for b in polar["angles"].values()))


# ---------------------------------------------------------------------------
# 13. CLI 契约（--astro / --json 的 report["astrology"]）
# ---------------------------------------------------------------------------
def test_cli():
    section("CLI 契约（--astro）")
    probe = run_cli("--help")
    supported = "--astro" in (probe.stdout or "") + (probe.stderr or "")
    if not supported:
        check("CLI 尚未接入 --astro（按约定跳过契约测试）", True, "skipped")
        return

    plain = run_cli(*BASE_ARGS)
    check("CLI 基准盘可运行（无 --astro）", plain.returncode == 0,
          (plain.stderr or "")[-300:])
    data, result = cli_json(*(BASE_ARGS + ["--astro"]))
    check("CLI --astro --json 返回码 0", result.returncode == 0,
          (result.stderr or "")[-300:])
    check("JSON 含 astrology 字段", isinstance(data, dict)
          and isinstance(data.get("astrology"), dict))
    if not isinstance(data, dict) or not isinstance(data.get("astrology"), dict):
        return
    astro = data["astrology"]
    check("CLI 输出十星", len(astro.get("planets") or []) == 10)
    check("CLI 输出 vedic（融合层依赖）", isinstance(astro.get("vedic"), dict)
          and bool(astro["vedic"]))
    check("CLI version 一致", astro.get("version") == A.VERSION)
    check("CLI 输出四轴", all(k in (astro.get("angles") or {})
                             for k in ("asc", "mc", "desc", "ic")))
    # 与直接调用 chart_natal 的数值应一致（同一 UTC 时刻/经度/默认纬度）
    same_report = {
        "input": {"date": data["input"].get("date"),
                  "time": data["input"].get("time"),
                  "zone": data["input"].get("zone"),
                  "longitude": data["input"].get("longitude")},
        "time": {"utc": data["time"].get("utc")},
    }
    direct = A.chart_natal(same_report)
    planet_pairs = {p["key"]: p for p in direct["planets"]}
    check("CLI 与直接调用十星黄经一致",
          all(angdiff(p["lon"], planet_pairs[p["key"]]["lon"]) <= 0.001
              for p in astro["planets"]))
    check("CLI 与直接调用 ASC 一致",
          angdiff(astro["angles"]["asc"]["lon"],
                  direct["angles"]["asc"]["lon"]) <= 0.001)
    text_run = run_cli(*(BASE_ARGS + ["--astro"]))
    check("CLI --astro 文本模式返回码 0", text_run.returncode == 0,
          (text_run.stderr or "")[-300:])
    check("CLI --astro 文本含西洋占星段", "【西洋占星·本命盘】" in (text_run.stdout or ""))
    check("CLI --astro 文本含印度占星段", "【印度占星" in (text_run.stdout or ""))
    base_data, _ = cli_json(*BASE_ARGS)
    check("未请求 --astro 时 JSON 不含 astrology 字段",
          isinstance(base_data, dict) and "astrology" not in base_data)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    if not os.path.exists(FIXTURES):
        print("缺少 %s：请先用 ephem 生成参考夹具" % FIXTURES)
        return 2
    with open(FIXTURES, encoding="utf-8") as fh:
        fixture_payload = json.load(fh)
    samples = fixture_payload.get("samples") or []
    global FIXTURE_SAMPLES
    FIXTURE_SAMPLES = samples

    test_module_api()
    test_structure()
    test_accuracy(samples)
    test_sign_boundary(samples)
    test_speed_retrograde()
    test_aspects()
    test_houses()
    test_angles()
    test_vedic()
    test_balance_phase()
    test_render()
    test_robustness()
    test_cli()

    print("西洋/印度占星层回归：%d 项" % total)
    if failures:
        print("失败 %d 项：" % len(failures))
        for name, detail in failures:
            print("  ✗ %s  %s" % (name, detail))
        return 1
    print("全部通过 ✓")
    return 0


FIXTURE_SAMPLES = []

if __name__ == "__main__":
    sys.exit(main())
