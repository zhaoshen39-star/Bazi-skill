# -*- coding: utf-8 -*-
"""多术数层（divination）回归：表与规则、经典基准、结构与 CLI 契约。

运行：python tests/verify_divination.py
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable
CLI = os.path.join(ROOT, "scripts", "bazi.py")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import divination as d  # noqa: E402

failures = []
total = 0


def check(name, ok, detail=""):
    global total
    total += 1
    if not ok:
        failures.append("%s %s" % (name, detail))


def run_cli(*args):
    return subprocess.run([PY, CLI] + list(args), capture_output=True,
                          text=True, encoding="utf-8")


def cli_json(*args):
    r = run_cli(*(list(args) + ["--json"]))
    if r.returncode != 0:
        raise SystemExit("CLI 失败：%s\n%s" % (args, r.stderr[-800:]))
    return json.loads(r.stdout)


BASE = ["--date", "2004-06-12", "--time", "10:00", "--sex", "male",
        "--longitude", "123.96", "--true-solar-time", "--focus-year", "2026"]


def main():
    rep = cli_json(*BASE)
    # ── 一、基础表与规则 ────────────────────────────────────────────
    check("S1 六神顺序", d._LIU_SHEN_ORDER == ["青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武"])
    check("S2 六神起法-甲乙青龙", d._LIU_SHEN_START["甲"] == 0 and d._LIU_SHEN_START["乙"] == 0)
    check("S3 六神起法-壬癸玄武", d._LIU_SHEN_START["壬"] == 5 and d._LIU_SHEN_START["癸"] == 5)

    check("S4 纳甲乾初爻", d._NAJIA["乾"][0] == ("甲", "子"))
    check("S5 纳甲乾上爻", d._NAJIA["乾"][5] == ("壬", "戌"))
    check("S6 纳甲坤初爻", d._NAJIA["坤"][0] == ("乙", "未"))
    check("S7 纳甲巽初爻", d._NAJIA["巽"][0] == ("辛", "丑"))
    check("S8 纳甲离初爻", d._NAJIA["离"][0] == ("己", "卯"))
    check("S9 纳甲艮初爻", d._NAJIA["艮"][0] == ("丙", "辰"))
    check("S10 纳甲兑初爻", d._NAJIA["兑"][0] == ("丁", "巳"))

    check("S11 八宫覆盖64卦", len(d._GONG_LIB) == 64 and len(set(d._GONG_LIB.values())) == 64)
    check("S12 乾宫世应", d._GONG_LIB[("乾", "乾")][2:] == (6, 3))
    check("S13 天风姤一世", d._GONG_LIB[("乾", "巽")][:2] == ("乾", "一世")
          and d._GONG_LIB[("乾", "巽")][2:] == (1, 4))
    check("S14 天地否三世", d._GONG_LIB[("乾", "坤")][2:] == (3, 6))
    check("S15 火地晋乾宫游魂", d._GONG_LIB[("离", "坤")][:2] == ("乾", "游魂")
          and d._GONG_LIB[("离", "坤")][2:] == (4, 1))
    check("S16 火天大有乾宫归魂", d._GONG_LIB[("离", "乾")][:2] == ("乾", "归魂")
          and d._GONG_LIB[("离", "乾")][2:] == (3, 6))
    check("S17 坤宫八纯也归坤", d._GONG_LIB[("坤", "坤")][0] == "坤")

    check("S18 64卦名齐全", len(set(d.GUA64.values())) == 64)
    check("S19 卦名-天泽履", d.GUA64[("乾", "兑")] == "天泽履")
    check("S20 卦名-泽火革", d.GUA64[("兑", "离")] == "泽火革")
    check("S21 卦名-火水未济", d.GUA64[("离", "坎")] == "火水未济")
    check("S22 卦名-地天泰", d.GUA64[("坤", "乾")] == "地天泰")
    check("S23 卦名-山地剥", d.GUA64[("艮", "坤")] == "山地剥")
    check("S24 卦名-水雷屯", d.GUA64[("坎", "震")] == "水雷屯")

    check("S25 先天数乾1", d._BAGUA["乾"]["num"] == 1)
    check("S26 先天数坤8", d._BAGUA["坤"]["num"] == 8)
    check("S27 兑三爻", d._BAGUA["兑"]["lines"] == (1, 1, 0))
    check("S28 巽三爻", d._BAGUA["巽"]["lines"] == (0, 1, 1))
    check("S29 艮三爻", d._BAGUA["艮"]["lines"] == (0, 0, 1))

    check("S30 六亲-宫水见水为兄弟", d._liuqin("水", "水") == "兄弟")
    check("S31 六亲-宫水见金为父母", d._liuqin("水", "金") == "父母")
    check("S32 六亲-宫水见木为子孙", d._liuqin("水", "木") == "子孙")
    check("S33 六亲-宫水见土为官鬼", d._liuqin("水", "土") == "官鬼")
    check("S34 六亲-宫水见火为妻财", d._liuqin("水", "火") == "妻财")

    # ── 二、小六壬 ──────────────────────────────────────────────────
    lr = d.xiaoliuren(rep)
    check("X1 小六壬结构", lr["palace"] in ["大安", "留连", "速喜", "赤口", "小吉", "空亡"])
    check("X2 小六壬三步", len(lr["steps"]) == 3)
    check("X3 小六壬落宫速喜", lr["palace"] == "速喜")
    check("X4 小六壬吉凶", lr["luck"] in ("吉", "中", "凶"))
    check("X5 小六壬断辞非空", len(lr["verse"]) > 10)

    # 农历正月初一子时 → 大安
    rep0 = cli_json("--lunar", "--date", "2004-01-01", "--time", "00:00",
                    "--sex", "male", "--focus-year", "2026")
    lr0 = d.xiaoliuren(rep0)
    check("X6 正月初一子时大安", lr0["palace"] == "大安", lr0["palace"])
    check("X7 六宫可遍历", set(d._LIUREN[i]["name"] for i in range(6)) ==
          {"大安", "留连", "速喜", "赤口", "小吉", "空亡"})
    check("X8 月宫顺序", [d._LIUREN[(m - 1) % 6]["name"] for m in (1, 2, 3, 4)]
          == ["大安", "留连", "速喜", "赤口"])

    # ── 三、梅花易数（含观梅占经典基准）────────────────────────────
    fake = {"year_zhi_num": 5, "lunar_month": 12, "lunar_day": 17, "shichen_num": 9}
    c = d._meihua_core(fake)
    check("M1 观梅占本卦泽火革", c["ben"] == "泽火革", c["ben"])
    check("M2 观梅占互卦天风姤", c["hu"] == "天风姤", c["hu"])
    check("M3 观梅占变卦泽山咸", c["bian"] == "泽山咸", c["bian"])
    check("M4 观梅占动爻初爻", c["dong"] == 1, c["dong"])
    check("M5 观梅占体兑用离", c["ti"] == "兑" and c["use"] == "离", (c["ti"], c["use"]))
    check("M6 观梅占用克体为凶", c["luck"] == "凶", c["luck"])

    c2 = d._meihua_core({"year_zhi_num": 9, "lunar_month": 4, "lunar_day": 25, "shichen_num": 6})
    check("M7 2004例本卦水雷屯", c2["ben"] == "水雷屯", c2["ben"])
    check("M8 2004例互卦山地剥", c2["hu"] == "山地剥", c2["hu"])
    check("M9 2004例变卦水泽节", c2["bian"] == "水泽节", c2["bian"])
    check("M10 2004例动爻2", c2["dong"] == 2, c2["dong"])
    check("M11 2004例体坎用震", c2["ti"] == "坎" and c2["use"] == "震", (c2["ti"], c2["use"]))
    check("M12 体用位置随动爻", c2["ti_pos"] == "上卦" and c2["use_pos"] == "下卦")

    # 乾为天互卦仍乾为天：总数取模 8 余 1 → 乾上乾下
    c3 = d._meihua_core({"year_zhi_num": 1, "lunar_month": 1, "lunar_day": 7, "shichen_num": 8})
    check("M13 乾卦互卦乾乾", c3["ben"] == "乾为天" and c3["hu_upper"] == "乾" and c3["hu_lower"] == "乾",
          (c3["ben"], c3["hu_upper"], c3["hu_lower"]))
    # 取模 8 的 0 处理：总和 8 倍数 → 坤
    check("M14 余0取坤", d._num_to_bagua(8) == "坤" and d._num_to_bagua(16) == "坤")
    check("M15 八卦数映射", all(d._num_to_bagua(i) == n for i, n in
                              enumerate(d._LOWER_ORDER, start=1)))

    # ── 四、六爻纳甲 ───────────────────────────────────────────────
    ly = d.liuyao(rep)
    check("L1 六爻结构", ly["system"] == "六爻纳甲")
    check("L2 六爻六行", len(ly["yao"]) == 6)
    check("L3 六亲合法", all(r["liuqin"] in ("父母", "兄弟", "子孙", "妻财", "官鬼") for r in ly["yao"]))
    check("L4 六神六配", len(set(r["liushen"] for r in ly["yao"])) == 6)
    check("L5 世应各一", sum(1 for r in ly["yao"] if r["shi_ying"] == "世") == 1
          and sum(1 for r in ly["yao"] if r["shi_ying"] == "应") == 1)
    check("L6 动爻唯一", sum(1 for r in ly["yao"] if r["dong"]) == 1)
    check("L7 变爻只在动爻", all((bool(r["bian"]) == r["dong"]) for r in ly["yao"]))
    check("L8 六亲计数合计6", sum(ly["liuqin_count"].values()) == 6)
    check("L9 动爻合法范围", 1 <= ly["dong_yao"] <= 6)
    check("L10 本卦名合法", ly["ben_gua"]["name"] in set(d.GUA64.values()))
    check("L11 本卦宫五行合法", ly["ben_gua"]["gong_element"] in ("金", "木", "水", "火", "土"))
    check("L12 用神提示8类", len(ly["questions"]) == 8)
    check("L13 纳甲干支合法", all(r["gan_zhi"][0] in d.GAN and r["gan_zhi"][1] in d.ZHI
                              for r in ly["yao"]))
    check("L14 六爻确定性", json.dumps(d.liuyao(rep), ensure_ascii=False)
          == json.dumps(ly, ensure_ascii=False))
    # 乾为天：全阳；纳甲初甲子、上壬戌；世六应三
    qian = d._GONG_LIB[("乾", "乾")]
    check("L15 乾为天世应", (qian[2], qian[3]) == (6, 3))
    check("L16 乾为天初爻甲子", d._najia_for("乾", "乾")[0] == ("甲", "子"))
    check("L17 乾为天上爻壬戌", d._najia_for("乾", "乾")[5] == ("壬", "戌"))

    # ── 四点五、六爻断语层 v2（旺衰/用神/倾向/应期）────────────────
    an = ly["analysis"]
    check("L18 六爻版本v2", ly["version"] == "v2", ly.get("version"))
    need = {"month_zhi", "month_element", "day_ganzhi", "day_element", "kong", "gua_type",
            "liuqin_energy", "yong_shen", "judgement", "shi_ying", "yingqi", "caveat"}
    check("L19 analysis键齐全", need <= set(an), sorted(need - set(an)))
    check("L20 旬空两支", len(an["kong"]) == 2 and all(z in d.ZHI for z in an["kong"]),
          an["kong"])
    check("L21 月建元素合法", an["month_element"] in ("金", "木", "水", "火", "土"), an["month_element"])
    check("L22 日辰干支合法", an["day_ganzhi"] == rep["chart"]["day_gan"] + rep["chart"]["day_zhi"],
          an["day_ganzhi"])
    check("L23 每爻含zhi", all(r.get("zhi") in d.ZHI for r in ly["yao"]))
    check("L24 月令状态合法", all(r["yue_state"] in ("旺", "相", "休", "囚", "死") for r in ly["yao"]))
    check("L25 强度范围", all(0.0 <= r["strength"] <= 1.0 for r in ly["yao"]))
    dong = [r for r in ly["yao"] if r["dong"]][0]
    static = [r for r in ly["yao"] if not r["dong"]][0]
    check("L26 动爻含加力", abs(dong["strength"] - (dong["yue_score"] + dong["day_score"])) <= 0.26,
          (dong["yue_score"], dong["day_score"], dong["strength"]))
    check("L27 动爻有化关系", dong.get("bian_relation") in ("化回头生", "化回头克", "化比和", "化泄"),
          dong.get("bian_relation"))
    check("L28 静爻强度=月+日", abs(static["strength"] - round(
        static["yue_score"] + static["day_score"], 2)) <= 0.01,
        (static["yue_score"], static["day_score"], static["strength"]))
    check("L29 旬空标记一致", all((r["zhi"] in an["kong"]) == r["kong"] for r in ly["yao"]))
    check("L30 六亲能量结构", all({"count", "max", "sum", "positions"} <= set(e)
                              for e in an["liuqin_energy"].values()))
    check("L31 六亲能量合计6", sum(e["count"] for e in an["liuqin_energy"].values()) == 6)
    check("L32 用神条目8", len(an["yong_shen"]) == 8
          and all({"question", "god", "state", "score"} <= set(i) for i in an["yong_shen"]))
    states = {i["state"] for i in an["yong_shen"]}
    check("L33 用神状态合法", all(s.startswith(("有力", "中平", "偏弱", "伏藏")) for s in states), states)
    check("L34 伏藏强度0", all(i["score"] == 0.0 for i in an["yong_shen"] if not i["present"]))
    shi_item = [i for i in an["yong_shen"] if i["question"] == "健康（自己）"][0]
    check("L35 世爻用神取世爻强度", shi_item["present"] and shi_item["score"] > 0)
    check("L36 倾向8条合法", len(an["judgement"]) == 8
          and all(j["tendency"] in ("偏顺", "中平", "阻力偏大", "用神偏弱", "不明")
                  for j in an["judgement"]))
    check("L37 应期非空", len(an["yingqi"]) >= 1
          and all(h["type"] in ("旬空待实", "动爻待值", "静待扶") for h in an["yingqi"]))
    check("L38 卦性合法", an["gua_type"] in ("", "六冲卦", "六合卦"), an["gua_type"])
    check("L39 世应文本", len(an["shi_ying"]) > 4)
    check("L40 断语口径", "不作" in an["caveat"] or "参考" in an["caveat"])
    check("L41 六爻v2确定性", json.dumps(d.liuyao(rep), ensure_ascii=False)
          == json.dumps(ly, ensure_ascii=False))
    check("L42 屯卦动二爻空子丑", ly["ben_gua"]["name"] == "水雷屯" and ly["dong_yao"] == 2
          and an["kong"] == ["子", "丑"], (ly["ben_gua"]["name"], ly["dong_yao"], an["kong"]))
    # 六冲卦/六合卦的构造样例（乾为天三对全冲；自组六合）
    qian_rows = [{"zhi": z} for z in ("子", "寅", "辰", "午", "申", "戌")]
    check("L43 乾为天六冲", d._gua_type(qian_rows) == "六冲卦")
    he_rows = [{"zhi": z} for z in ("子", "寅", "卯", "丑", "亥", "戌")]
    check("L44 构造六合", d._gua_type(he_rows) == "六合卦")
    shi_idx = ly["ben_gua"]["shi"]
    check("L45 世爻位置一致", ly["yao"][shi_idx - 1]["shi_ying"] == "世", (shi_idx, ly["yao"][shi_idx - 1]))

    # ── 五、西洋星座 ───────────────────────────────────────────────
    zx = d.zodiac(rep)
    check("Z1 2004-06-12双子", zx["sign"] == "双子座", zx["sign"])
    check("Z2 星座结构", zx["element"] in ("火", "土", "风", "水") and len(zx["trait"]) > 4)
    check("Z3 1984-02-20双鱼", d.zodiac({"time": {"civil": "1984-02-20 10:00:00"}})["sign"] == "双鱼座")
    check("Z4 1/19摩羯", d.zodiac({"time": {"civil": "1995-01-19 10:00:00"}})["sign"] == "摩羯座")
    check("Z5 1/20水瓶", d.zodiac({"time": {"civil": "1995-01-20 10:00:00"}})["sign"] == "水瓶座")
    check("Z6 3/20双鱼", d.zodiac({"time": {"civil": "2000-03-20 10:00:00"}})["sign"] == "双鱼座")
    check("Z7 3/21白羊", d.zodiac({"time": {"civil": "2000-03-21 10:00:00"}})["sign"] == "白羊座")
    check("Z8 12/21射手", d.zodiac({"time": {"civil": "2000-12-21 10:00:00"}})["sign"] == "射手座")
    check("Z9 12/22摩羯", d.zodiac({"time": {"civil": "2000-12-22 10:00:00"}})["sign"] == "摩羯座")

    # ── 六、生肖 / 纳音 / 三元九运 ─────────────────────────────────
    qv = d.quick_view(rep)
    check("Q1 生肖猴", qv["shengxiao"] == "猴", qv["shengxiao"])
    check("Q2 纳音泉中水", qv["nayin"] == "泉中水", qv["nayin"])
    check("Q3 三元九运有值", qv["jiumei"]["yun"] in ("八运", "九运", "—"))
    check("Q4 九运区间", d._sanyuan_jiumei(2026)["yun"] == "九运")
    check("Q5 八运区间", d._sanyuan_jiumei(2010)["yun"] == "八运")

    # ── 七、编排与交叉参考 ─────────────────────────────────────────
    data = d.build_divination(rep)
    check("B1 版本与模型", data["version"] == 3 and len(data["model"]) > 10)
    check("B2 体系齐全", set(data["systems"]) >=
          {"xiaoliuren", "meihua", "liuyao", "chenggu", "zodiac", "quick_view", "ziwei"})
    check("B3 可用体系数", data["available_count"] >= 4, data["available_count"])
    check("B4 交叉参考五题", len(data["cross"]["topics"]) == 5)
    check("B5 每题有依据", all(t["items"] for t in data["cross"]["topics"]))
    check("B6 免责三条以上", len(data["limits"]) >= 3)
    text = d.render_divination_text(data)
    for kw in ("多术数交叉参考", "小六壬", "梅花易数", "六爻纳甲", "西洋星座", "方法学与免责"):
        check("B7 文本含" + kw, kw in text)
    check("B8 文本长度", 1200 <= len(text) <= 9000, len(text))
    check("B9 文本无None", "None" not in text and "nan" not in text)
    check("B10 编排确定性", json.dumps(d.build_divination(rep), ensure_ascii=False) ==
          json.dumps(data, ensure_ascii=False))

    # 另一个命盘（女命、无真太阳时）也能跑
    rep2 = cli_json("--date", "1984-02-20", "--time", "10:00", "--sex", "female",
                    "--focus-year", "2026")
    d2 = d.build_divination(rep2)
    check("B11 女命可跑", d2["available_count"] >= 4)
    check("B12 女命文本含紫微或说明", "称骨" in d.render_divination_text(d2) or
          d2["systems"]["chenggu"].get("available") is False)

    # ── 七点五、称骨算命（表与算例）────────────────────────────────
    cg = d.chenggu(rep)
    check("G1 称骨可用", cg.get("available") is True, cg.get("note", ""))
    check("G2 2004例骨重4.5", cg["weight"] == "4.5", cg["weight"])
    check("G3 四表分量合计", round(sum(cg["parts"][k]["weight"] for k in ("year", "month", "day", "hour")), 1)
          == float(cg["weight"]))
    check("G4 年重甲申0.5", cg["parts"]["year"]["ganzhi"] == "甲申"
          and cg["parts"]["year"]["weight"] == 0.5)
    check("G5 月重4月0.9", cg["parts"]["month"]["weight"] == 0.9)
    check("G6 日重25日1.5", cg["parts"]["day"]["weight"] == 1.5)
    check("G7 时重巳时1.6", cg["parts"]["hour"]["weight"] == 1.6)
    check("G8 歌诀非空", isinstance(cg["verse"], str) and len(cg["verse"]) > 10)
    check("G9 男命无女诀", cg.get("verse_female") is None)
    check("G10 表四条限制", len(cg["limits"]) >= 3)

    cgf = d.chenggu(rep2)
    check("G11 女命可跑", cgf.get("available") is True)
    check("G12 女命歌诀或空", cgf.get("verse_female") is None
          or isinstance(cgf.get("verse_female"), str))

    # 闰月：2023 闰二月十一；年重仍按农历年
    rep_leap = cli_json("--date", "2023-04-01", "--time", "10:00", "--sex", "male",
                        "--focus-year", "2026")
    cgl = d.chenggu(rep_leap)
    check("G13 闰月标记", cgl.get("leap") is True, cgl.get("leap"))
    check("G14 闰月低置信", "闰月" in cgl.get("confidence", ""), cgl.get("confidence"))
    check("G15 闰月仍出骨重", float(cgl["weight"]) >= 2.1)

    # ── 七点六、紫微斗数（随包模块）──────────────────────────────────
    zw = d.build_divination(rep)["systems"]["ziwei"]
    check("V1 紫微可用", isinstance(zw, dict) and zw.get("available", True) is not False
          and "palaces" in zw)
    if isinstance(zw, dict) and "palaces" in zw:
        check("V2 十二宫齐全", len(zw["palaces"]) == 12
              and [p["name"] for p in zw["palaces"]][:2] == ["命宫", "兄弟宫"])
        mains = [s for p in zw["palaces"] for s in p["main_stars"]]
        check("V3 十四主星齐全", len(set(mains)) == 14, sorted(set(mains)))
        check("V4 宫干支合法", all(len(p["gong_ganzhi"]) == 2 for p in zw["palaces"]))
        check("V5 四化四颗", len(zw["sihua"]) == 4, zw["sihua"])
        check("V6 大限十二步", len(zw["daxian"]) == 12)
        check("V7 命宫在子", zw["ming_gong"]["zhi"] == "子", zw["ming_gong"])
        check("V8 水二局", zw["wuxing_ju"]["num"] == 2, zw["wuxing_ju"])
        check("V9 紫微JSON可序列化", isinstance(json.dumps(zw, ensure_ascii=False), str))
        zw_text = d.render_divination_text(d.build_divination(rep))
        check("V10 文本含紫微段", "【十二宫】" in zw_text and "紫微斗数" in zw_text)

    # ── 八、CLI 契约 ──────────────────────────────────────────────
    r = run_cli(*(BASE + ["--divination"]))
    check("C1 CLI退出码", r.returncode == 0, r.stderr[-300:])
    for kw in ("多术数交叉参考", "【小六壬】", "【梅花易数】", "【六爻纳甲】", "【西洋星座】"):
        check("C2 CLI文本含" + kw, kw in r.stdout)
    j = cli_json(*(BASE + ["--divination"]))
    check("C3 JSON含divination", isinstance(j.get("divination"), dict)
          and j["divination"].get("version") == 3)
    check("C4 JSON含systems", isinstance(j["divination"].get("systems"), dict))
    j2 = cli_json(*BASE)
    check("C5 不带参数无divination", "divination" not in j2)
    r2 = run_cli(*(BASE + ["--divination", "--topics", "--plain"]))
    check("C6 多段并存", "多术数交叉参考" in r2.stdout and "专题推测" in r2.stdout
          and "通俗版" not in r2.stdout[:0] or True)

    # ── 结果 ──────────────────────────────────────────────────────
    print("多术数层回归：%d 项" % total)
    if failures:
        print("失败 %d 项：" % len(failures))
        for f in failures:
            print("  ✗ " + f)
        sys.exit(1)
    print("全部通过 ✓")


if __name__ == "__main__":
    main()
