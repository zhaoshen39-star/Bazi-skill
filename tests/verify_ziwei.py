# -*- coding: utf-8 -*-
"""紫微斗数层回归测试（verify_ziwei.py）。

运行：
    python tests/verify_ziwei.py

覆盖：
  1. 结构完整性（字段、农历、命身宫、宫干支五虎遁、十二宫顺序）；
  2. 安星规则（十四主星各一次、紫微系/天府系相对位置、六吉六煞、四化落宫）；
  3. 大限（局数起运、每宫十年、方向、年份区间、覆盖十二宫）；
  4. 闰月两半、缺性别、缺时辰、晚子时等边界不崩且写明局限；
  5. 三个手算基准（2004-06-12 男 / 1984-02-20 女 / 1995-01-20 男，10:00＝巳时），
     期望值按安星诀手推写死；
  6. 五个 iztro（npm 独立实现，v2.6.3）实测基准，逐宫比对主星与四化。
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

import chart  # noqa: E402
import ziwei  # noqa: E402

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
MAIN14 = ["紫微", "天机", "太阳", "武曲", "天同", "廉贞",
          "天府", "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "破军"]
JI6 = ["左辅", "右弼", "文昌", "文曲", "天魁", "天钺"]
SHA6 = ["擎羊", "陀罗", "火星", "铃星", "地空", "地劫"]
PALACE_NAMES = ["命宫", "兄弟宫", "夫妻宫", "子女宫", "财帛宫", "疾厄宫",
                "迁移宫", "交友宫", "官禄宫", "田宅宫", "福德宫", "父母宫"]
JU_NUM = {"水二局": 2, "木三局": 3, "金四局": 4, "土五局": 5, "火六局": 6}

failures = []
total = 0


def check(name, ok, detail=""):
    """与其余 verify_*.py 相同的断言风格。"""
    global total
    total += 1
    if not ok:
        failures.append((name, detail))
        print("FAIL  %s%s" % (name, ("  ← " + str(detail)) if detail else ""))


def make_ziwei(y, m, d, h, sex=1):
    """直接调内核建盘，返回 (chart, 紫微层 dict)。"""
    c = chart.build(y, m, d, h, 0, sex=sex)
    rep = {"chart": c}
    if sex in (0, 1):
        rep["input"] = {"sex": "male" if sex == 1 else "female"}
    return c, ziwei.chart_ziwei(rep)


def parse_stars(text):
    """'子天机 丑紫微破军' → {'子': ['天机'], '丑': ['紫微', '破军']}。"""
    out = {}
    for token in text.split():
        zhi, rest = token[0], token[1:]
        out[zhi] = [rest[i:i + 2] for i in range(0, len(rest), 2)]
    return out


def stars_of(z):
    """把盘中主星整理为 {地支: [星]}（空宫不出现）。"""
    return {p["zhi"]: list(p["main_stars"]) for p in z["palaces"] if p["main_stars"]}


def hua_of(z):
    return {i["star"]: i["hua"] for i in z["sihua"]}


def pattern_of(z, name):
    """按格局名取条目；不存在返回 None。"""
    for item in z.get("patterns") or []:
        if item.get("name") == name:
            return item
    return None


def pattern_level(z, name):
    item = pattern_of(z, name)
    return item.get("level") if item else None


def gong_gan_expected(year_gan, zhi):
    """五虎遁：寅宫起「甲丙戊庚壬」中与年干相配者，顺排十二宫。"""
    yin_gan = (GAN.index(year_gan) % 5) * 2 + 2
    return GAN[(yin_gan + (ZHI.index(zhi) - 2) % 12) % 10]


# ---------------------------------------------------------------- 预生成命盘
# 2004 甲申年（阳年男，顺行）；1984 甲子年（阳年女，逆行）；
# 1995 农历仍是 1994 甲戌年（阳年男，顺行）；1975 乙卯年（阴年，男女方向相反）；
# 2022 壬寅年（四化含左辅化科，检验辅星四化）；闰月两半用 2004 闰二月。
C2004, Z2004 = make_ziwei(2004, 6, 12, 10, 1)
C1984, Z1984 = make_ziwei(1984, 2, 20, 10, 0)
C1995, Z1995 = make_ziwei(1995, 1, 20, 10, 1)
C1975F, Z1975F = make_ziwei(1975, 5, 5, 10, 0)
C1975M, Z1975M = make_ziwei(1975, 5, 5, 10, 1)
C2022, Z2022 = make_ziwei(2022, 5, 5, 10, 1)
CLEAP_A, ZLEAP_A = make_ziwei(2004, 3, 25, 10, 1)   # 闰二月初五
CLEAP_B, ZLEAP_B = make_ziwei(2004, 4, 14, 10, 1)   # 闰二月廿五
CNOSEX, ZNOSEX = make_ziwei(2004, 6, 12, 10, None)
CLATE, ZLATE = make_ziwei(2004, 6, 12, 23, 1)

ALL = [("2004", Z2004), ("1984", Z1984), ("1995", Z1995),
       ("1975F", Z1975F), ("1975M", Z1975M), ("2022", Z2022),
       ("闰月前", ZLEAP_A), ("闰月后", ZLEAP_B)]


# ================================================================ 一、结构
print("\n== 一、结构完整性 ==")

check("version=v1", Z2004.get("version") == "v1", Z2004.get("version"))
check("method 说明含紫微斗数", isinstance(Z2004.get("method"), str)
      and "紫微" in Z2004["method"])

LUN_KEYS = {"text", "lunar_year", "month", "month_raw", "leap", "day",
            "leap_note", "shichen", "shichen_zhi", "shichen_index"}
check("lunar 字段齐全", LUN_KEYS <= set(Z2004["lunar"]),
      sorted(LUN_KEYS - set(Z2004["lunar"])))

CHART_OF = {"2004": C2004, "1984": C1984, "1995": C1995,
            "1975F": C1975F, "1975M": C1975M, "2022": C2022,
            "闰月前": CLEAP_A, "闰月后": CLEAP_B}
for tag, z in ALL:
    c = CHART_OF[tag]
    check("%s 农历年月日与内核 chart.lunar 一致" % tag,
          (z["lunar"]["lunar_year"], z["lunar"]["month_raw"], z["lunar"]["day"])
          == (c["lunar"]["year"], abs(c["lunar"]["month"]), c["lunar"]["day"]),
          ((z["lunar"]["lunar_year"], z["lunar"]["month_raw"], z["lunar"]["day"]),
           (c["lunar"]["year"], c["lunar"]["month"], c["lunar"]["day"])))
check("2004 农历=二〇〇四年四月廿五", Z2004["lunar"]["text"] == "二〇〇四年四月廿五",
      Z2004["lunar"]["text"])
check("2004 农历年 2004 / 4 月 / 25 日",
      (Z2004["lunar"]["lunar_year"], Z2004["lunar"]["month"], Z2004["lunar"]["day"])
      == (2004, 4, 25))
check("2004 非闰月", Z2004["lunar"]["leap"] is False)
check("2004 时支=巳（chart.pillars[3].zhi 同源）",
      Z2004["lunar"]["shichen_zhi"] == C2004["pillars"][3]["zhi"] == "巳",
      Z2004["lunar"]["shichen_zhi"])
check("2004 时支序号=5", Z2004["lunar"]["shichen_index"] == 5)
check("2004 农历年干支=甲申（正月初一为界，非立春）",
      Z2004["year_ganzhi"] == "甲申", Z2004["year_ganzhi"])
check("2004 年干=甲", Z2004["year_gan"] == "甲")
check("2004 阳年", Z2004["yin_yang"] == "阳年")
check("1995-01-20 农历年=1994（跨公历年）", Z1995["lunar"]["lunar_year"] == 1994)
check("1995-01-20 农历年干=甲（甲戌）", Z1995["year_ganzhi"] == "甲戌",
      Z1995["year_ganzhi"])

# 命宫/身宫字段自洽
check("2004 命宫=子", Z2004["ming_gong"]["zhi"] == "子", Z2004["ming_gong"])
check("2004 命宫 zhi_index 与 zhi 一致",
      Z2004["ming_gong"]["zhi_index"] == ZHI.index(Z2004["ming_gong"]["zhi"]))
check("2004 命宫干支=丙子", Z2004["ming_gong"]["ganzhi"] == "丙子")
check("2004 命宫纳音=涧下水", Z2004["ming_gong"]["nayin"] == "涧下水")
check("2004 身宫=戌（夫妻宫）",
      Z2004["shen_gong"]["zhi"] == "戌"
      and Z2004["shen_gong"]["palace"] == "夫妻宫")
check("2004 身宫 offset=10", Z2004["shen_gong"]["offset"] == 10)
check("2004 身宫干支=甲戌", Z2004["shen_gong"]["ganzhi"] == "甲戌")

# 十二宫：数量、地支齐全、宫名顺序（自命宫起逆行）
for tag, z in ALL:
    zhis = [p["zhi"] for p in z["palaces"]]
    check("%s 十二宫齐全且地支不重复" % tag,
          len(z["palaces"]) == 12 and sorted(zhis) == sorted(ZHI), zhis)
check("2004 首宫为命宫", Z2004["palaces"][0]["name"] == "命宫")
check("十二宫宫名自命宫起逆行（兄弟→父母）",
      [p["name"] for p in Z2004["palaces"]] == PALACE_NAMES,
      [p["name"] for p in Z2004["palaces"]])
check("命宫旗标 is_ming 只出现一次",
      sum(1 for p in Z2004["palaces"] if p["is_ming"]) == 1)
check("身宫旗标 is_shen 只出现一次",
      sum(1 for p in Z2004["palaces"] if p["is_shen"]) == 1)

# 宫干五虎遁：甲年寅宫起丙寅
bad = [(p["zhi"], p["gong_gan"]) for p in Z2004["palaces"]
       if p["gong_gan"] != gong_gan_expected(Z2004["year_gan"], p["zhi"])]
check("2004 十二宫宫干合五虎遁", not bad, bad)
bad = [(p["zhi"], p["gong_gan"]) for p in Z1984["palaces"]
       if p["gong_gan"] != gong_gan_expected(Z1984["year_gan"], p["zhi"])]
check("1984 十二宫宫干合五虎遁", not bad, bad)
check("2022 壬年寅宫=壬寅（壬年五虎遁起壬寅）",
      [p for p in Z2022["palaces"] if p["zhi"] == "寅"][0]["gong_ganzhi"] == "壬寅")

# 命宫 - 生时 关系：命宫=寅起正月顺数至生月、再起子时逆数至生时；身宫=生月宫起子时顺数
hour_ok, shen_ok, shichen_ok = True, True, True
for h in range(24):
    _, z = make_ziwei(2004, 6, 12, h, 1)
    hi = ziwei._hour_index({"input": {"hour": h}})
    ming = ZHI.index(z["ming_gong"]["zhi"])
    shen = ZHI.index(z["shen_gong"]["zhi"])
    month_eff = z["lunar"]["month"]
    if z["lunar"]["shichen_zhi"] != ZHI[((h + 1) // 2) % 12]:
        shichen_ok = False
    if ming != (2 + month_eff - 1 - hi) % 12:
        hour_ok = False
    if (shen - ming) % 12 != (2 * hi) % 12:
        shen_ok = False
check("24 小时时支映射正确", shichen_ok)
check("命宫=寅起正月顺数至生月、起子时逆数至生时（24 小时全验）", hour_ok)
check("身宫自命宫顺数 2×时序号（24 小时全验）", shen_ok)
check("身宫在十二宫中的位置标签正确",
      Z2004["shen_gong"]["palace"] == PALACE_NAMES[(ZHI.index(Z2004["ming_gong"]["zhi"])
                                                   - ZHI.index(Z2004["shen_gong"]["zhi"])) % 12],
      Z2004["shen_gong"]["palace"])


# ================================================================ 二、安星
print("\n== 二、安星规则 ==")

for tag, z in ALL:
    mains = [s for p in z["palaces"] for s in p["main_stars"]]
    check("%s 十四主星各出现一次" % tag,
          sorted(mains) == sorted(MAIN14), mains)
    jis = [s for p in z["palaces"] for s in p["ji_stars"]]
    check("%s 六吉星各出现一次" % tag, sorted(jis) == sorted(JI6), jis)
    shas = [s for p in z["palaces"] for s in p["sha_stars"]]
    check("%s 六煞星各出现一次" % tag, sorted(shas) == sorted(SHA6), shas)
    check("%s 主星/吉星/煞星互不混淆" % tag,
          not (set(s for p in z["palaces"] for s in p["main_stars"]) & set(JI6 + SHA6)))

# 五行局
for tag, z in ALL:
    ju = z["wuxing_ju"]
    check("%s 五行局合法（水二/木三/金四/土五/火六）" % tag,
          ju["name"] in JU_NUM and JU_NUM[ju["name"]] == ju["num"], ju)
    check("%s 五行局=命宫纳音五行（%s→%s）" % (tag, ju["nayin"], ju["name"]),
          ju["nayin"] == z["ming_gong"]["nayin"]
          and ju["element"] == ju["name"][0], (ju["nayin"], ju["name"]))
check("2004 命宫纳音涧下水 → 水二局", Z2004["wuxing_ju"]["name"] == "水二局")
check("1984 命宫纳音剑锋金 → 金四局", Z1984["wuxing_ju"]["name"] == "金四局")
check("1995 命宫纳音剑锋金 → 金四局", Z1995["wuxing_ju"]["name"] == "金四局")
check("1975 命宫纳音屋上土 → 土五局", Z1975M["wuxing_ju"]["name"] == "土五局")
check("2022 命宫纳音桑柘木 → 木三局", Z2022["wuxing_ju"]["name"] == "木三局")

# 紫微 / 天府 对称关系
for tag, z in ALL:
    zw = ZHI.index(z["ziwei"]["zhi"])
    tf = ZHI.index(z["tianfu"]["zhi"])
    check("%s 天府与紫微对称（4-紫微）" % tag, tf == (4 - zw) % 12, (zw, tf))

# 紫微系逆布 / 天府系顺布：相对紫微、天府的宫位偏移
ZIWEI_OFF = {"紫微": 0, "天机": -1, "太阳": -3, "武曲": -4, "天同": -5, "廉贞": -8}
TIANFU_OFF = {"天府": 0, "太阴": 1, "贪狼": 2, "巨门": 3, "天相": 4,
              "天梁": 5, "七杀": 6, "破军": 10}
for tag, z in ALL:
    pos = {s: ZHI.index(p["zhi"]) for p in z["palaces"] for s in p["main_stars"]}
    zw = ZHI.index(z["ziwei"]["zhi"])
    tf = ZHI.index(z["tianfu"]["zhi"])
    bad = [(s, (pos[s] - zw) % 12) for s, off in ZIWEI_OFF.items()
           if (pos[s] - zw) % 12 != off % 12]
    bad += [(s, (pos[s] - tf) % 12) for s, off in TIANFU_OFF.items()
            if (pos[s] - tf) % 12 != off % 12]
    check("%s 紫微系/天府系相对位置合规" % tag, not bad, bad)

# 紫微定位：以 2004 盘（日 25、水二局）为例，独立按「商数宫前走」手推
check("2004 紫微在丑宫（日25/水二局，商13、余数补1）",
      Z2004["ziwei"]["zhi"] == "丑", Z2004["ziwei"]["zhi"])
check("2004 紫微落父母宫、天府落田宅宫",
      Z2004["ziwei"]["palace"] == "父母宫" and Z2004["tianfu"]["palace"] == "田宅宫")
check("主星所在宫与 palaces 记录一致（无孤立主星）",
      set(stars_of(Z2004)) == {p["zhi"] for p in Z2004["palaces"] if p["main_stars"]})

# 六吉六煞位置口诀（以 2004 甲申年巳时为例）
JZ_2004 = {p["zhi"]: p["ji_stars"] for p in Z2004["palaces"] if p["ji_stars"]}
SZ_2004 = {p["zhi"]: p["sha_stars"] for p in Z2004["palaces"] if p["sha_stars"]}
check("2004 左辅右弼在未（4 月：辰+3 / 戌-3）",
      "左辅" in JZ_2004.get("未", []) and "右弼" in JZ_2004.get("未", []), JZ_2004)
check("2004 文昌在巳、文曲在酉（戌起子逆 / 辰起子顺）",
      "文昌" in JZ_2004.get("巳", []) and "文曲" in JZ_2004.get("酉", []), JZ_2004)
check("2004 天魁丑、天钺未（甲戊庚牛羊）",
      "天魁" in JZ_2004.get("丑", []) and "天钺" in JZ_2004.get("未", []), JZ_2004)
check("2004 擎羊卯、陀罗丑（甲禄在寅，羊+1 陀-1）",
      "擎羊" in SZ_2004.get("卯", []) and "陀罗" in SZ_2004.get("丑", []), SZ_2004)
check("2004 火星未、铃星卯（申子辰：火寅起、铃戌起，+巳时5）",
      "火星" in SZ_2004.get("未", []) and "铃星" in SZ_2004.get("卯", []), SZ_2004)
check("2004 地空午、地劫辰（亥-时 / 亥+时）",
      "地空" in SZ_2004.get("午", []) and "地劫" in SZ_2004.get("辰", []), SZ_2004)

# 四化
check("年干四化恰好 4 颗", len(Z2004["sihua"]) == 4, Z2004["sihua"])
for tag, z in ALL:
    hs = [i["star"] for i in z["sihua"]]
    check("%s 四化星互不相同" % tag, len(set(hs)) == 4, hs)
    check("%s 四化化曜=禄权科忌" % tag,
          set(i["hua"] for i in z["sihua"]) == {"禄", "权", "科", "忌"},
          z["sihua"])
    all_stars = set()
    for p in z["palaces"]:
        all_stars |= set(p["main_stars"]) | set(p["ji_stars"]) | set(
            p["sha_stars"]) | set(p.get("other_stars") or [])
    check("%s 四化星都在盘上" % tag, all(i["star"] in all_stars for i in z["sihua"]),
          [i["star"] for i in z["sihua"] if i["star"] not in all_stars])
    ok = True
    for p in z["palaces"]:
        for i in p["sihua"]:
            if not any(h["star"] == i["star"] and h["hua"] == i["hua"]
                       and h["zhi"] == p["zhi"] for h in z["sihua"]):
                ok = False
    check("%s 各宫 sihua 与顶层 sihua 一致" % tag, ok)

check("2004 甲年四化=廉破武阳",
      hua_of(Z2004) == {"廉贞": "禄", "破军": "权", "武曲": "科", "太阳": "忌"},
      hua_of(Z2004))
check("2004 廉贞化禄落交友宫（巳）",
      [i for i in Z2004["sihua"] if i["star"] == "廉贞"]
      == [{"star": "廉贞", "hua": "禄", "palace": "交友宫", "zhi": "巳"}],
      [i for i in Z2004["sihua"] if i["star"] == "廉贞"])
check("2004 太阳化忌落夫妻宫（戌=身宫）",
      [i for i in Z2004["sihua"] if i["star"] == "太阳"][0]["palace"] == "夫妻宫")
check("1975 乙年四化=机梁紫阴",
      hua_of(Z1975M) == {"天机": "禄", "天梁": "权", "紫微": "科", "太阴": "忌"},
      hua_of(Z1975M))
check("2022 壬年四化=梁紫左武（左辅化科）",
      hua_of(Z2022) == {"天梁": "禄", "紫微": "权", "左辅": "科", "武曲": "忌"},
      hua_of(Z2022))

# 四化表（十干）逐项校验：硬编码期望，防止常量被改坏
SIHUA_EXPECT = {
    "甲": {"廉贞": "禄", "破军": "权", "武曲": "科", "太阳": "忌"},
    "乙": {"天机": "禄", "天梁": "权", "紫微": "科", "太阴": "忌"},
    "丙": {"天同": "禄", "天机": "权", "文昌": "科", "廉贞": "忌"},
    "丁": {"太阴": "禄", "天同": "权", "天机": "科", "巨门": "忌"},
    "戊": {"贪狼": "禄", "太阴": "权", "右弼": "科", "天机": "忌"},
    "己": {"武曲": "禄", "贪狼": "权", "天梁": "科", "文曲": "忌"},
    "庚": {"太阳": "禄", "武曲": "权", "天府": "科", "天同": "忌"},
    "辛": {"巨门": "禄", "太阳": "权", "文曲": "科", "文昌": "忌"},
    "壬": {"天梁": "禄", "紫微": "权", "左辅": "科", "武曲": "忌"},
    "癸": {"破军": "禄", "巨门": "权", "太阴": "科", "贪狼": "忌"},
}
for gan, expect in SIHUA_EXPECT.items():
    check("四化表 %s 干正确" % gan, dict(ziwei.SIHUA[gan]) == expect,
          dict(ziwei.SIHUA[gan]))

# 命主 / 身主
check("2004 命主贪狼（命宫在子）、身主天梁（申年）",
      (Z2004["ming_zhu"], Z2004["shen_zhu"]) == ("贪狼", "天梁"))
check("1984 命主文曲（命宫在酉）、身主火星（子年）",
      (Z1984["ming_zhu"], Z1984["shen_zhu"]) == ("文曲", "火星"))
check("1995 命主廉贞（命宫在申）、身主文昌（戌年）",
      (Z1995["ming_zhu"], Z1995["shen_zhu"]) == ("廉贞", "文昌"))

# 格局（只做结构识别，抽查可解释标签）
check("1984 紫微七杀在财帛宫 → 杀破狼结构", any("杀破狼" in p["name"] for p in Z1984["patterns"]),
      Z1984["patterns"])
check("2004 命宫三方四正机月同梁", any("机月同梁" in p["name"] for p in Z2004["patterns"]),
      Z2004["patterns"])


# ================================================================ 三、大限
print("\n== 三、大限 ==")

for tag, z in ALL:
    check("%s 大限 12 条" % tag, len(z["daxian"]) == 12, len(z["daxian"]))
    ds = z["daxian"]
    check("%s 大限岁数连续、每限十年" % tag,
          all(ds[i]["start_age"] == ds[i - 1]["end_age"] + 1 for i in range(1, 12))
          and all(d["end_age"] - d["start_age"] == 9 for d in ds),
          [(d["start_age"], d["end_age"]) for d in ds])
    check("%s 首限起运岁=局数" % tag, ds[0]["start_age"] == z["wuxing_ju"]["num"])
    check("%s 大限年份区间自洽" % tag,
          all(d["start_year"] == z["lunar"]["lunar_year"] + d["start_age"] - 1
              and d["end_year"] == d["start_year"] + 9 for d in ds),
          [(d["start_year"], d["end_year"]) for d in ds])
    check("%s 大限覆盖十二宫各一次" % tag,
          sorted(d["zhi"] for d in ds) == sorted(ZHI), [d["zhi"] for d in ds])
    check("%s 首限即命宫" % tag, ds[0]["palace"] == "命宫" and ds[0]["zhi"] == z["ming_gong"]["zhi"])
    fwd = z["forward"]
    step = 1 if fwd else -1
    ok = all(ZHI.index(ds[i]["zhi"]) == (ZHI.index(ds[i - 1]["zhi"]) + step) % 12
             for i in range(1, 12))
    check("%s 大限宫位%s连续" % (tag, "顺行" if fwd else "逆行"), ok)
    by_zhi = {p["zhi"]: p for p in z["palaces"]}
    ok = all(by_zhi[d["zhi"]]["daxian"]["start_age"] == d["start_age"]
             and by_zhi[d["zhi"]]["daxian"]["end_age"] == d["end_age"]
             and by_zhi[d["zhi"]]["daxian"]["order"] == d["order"] for d in ds)
    check("%s palaces[].daxian 与顶层 daxian 一致" % tag, ok)

check("2004 阳年男 → 顺行", Z2004["direction"] == "顺行" and Z2004["forward"] is True)
check("2004 首限丙子 2–11 岁（2005–2014）",
      [(d["palace"], d["ganzhi"], d["start_age"], d["end_age"],
        d["start_year"], d["end_year"]) for d in Z2004["daxian"][:1]]
      == [("命宫", "丙子", 2, 11, 2005, 2014)], Z2004["daxian"][0])
check("2004 末限兄弟宫 乙亥 112–121 岁（2115–2124）",
      [(d["palace"], d["ganzhi"], d["start_age"], d["end_age"],
        d["start_year"], d["end_year"]) for d in Z2004["daxian"][-1:]]
      == [("兄弟宫", "乙亥", 112, 121, 2115, 2124)], Z2004["daxian"][-1])
check("1984 阳年女 → 逆行", Z1984["direction"] == "逆行")
check("1975 阴年女 → 顺行", Z1975F["direction"] == "顺行")
check("1975 阴年男 → 逆行", Z1975M["direction"] == "逆行")
check("1984 首限命宫癸酉 4–13 岁", Z1984["daxian"][0]["ganzhi"] == "癸酉"
      and Z1984["daxian"][0]["start_age"] == 4)
check("1995 首限命宫壬申 4–13 岁", Z1995["daxian"][0]["ganzhi"] == "壬申"
      and Z1995["daxian"][0]["start_age"] == 4)


# ================================================================ 四、手算基准
print("\n== 四、手算基准（按安星诀手推）==")

# 2004-06-12 10:00 男（公历）→ 农历 2004-04-25 巳时，甲申年
# 命宫 = (寅2 + 月4-1 - 时5) % 12 = 0 → 子
# 命宫干：甲年寅宫起丙 → 子 = 丙子；丙子纳音涧下水 → 水二局
# 紫微：日25、局2，25%2=1 取补数1 → (25+1)/2=13；13%12=1 → 寅前1宫=丑
check("手算 2004 命宫在子", Z2004["ming_gong"]["zhi"] == "子")
check("手算 2004 丙子纳音→水二局", Z2004["wuxing_ju"]["name"] == "水二局")
check("手算 2004 紫微在丑", Z2004["ziwei"]["zhi"] == "丑")
check("手算 2004 身宫 = 月4宫+时5 = 戌", Z2004["shen_gong"]["zhi"] == "戌")

# 1984-02-20 10:00 女 → 农历 1984-01-19 巳时，甲子年
# 命宫 = (2 + 1-1 - 5) % 12 = -3 → 9 = 酉
# 甲年寅起丙 → 酉 = (2+(9-2))%10=9 癸 → 癸酉剑锋金 → 金四局
# 紫微：日19/局4，19%4=3 取补数1 → (19+1)/4=5 → 寅后5-1=巳
check("手算 1984 命宫在酉", Z1984["ming_gong"]["zhi"] == "酉")
check("手算 1984 癸酉纳音→金四局", Z1984["wuxing_ju"]["name"] == "金四局")
check("手算 1984 紫微在巳", Z1984["ziwei"]["zhi"] == "巳")
check("手算 1984 阳女大限逆行、4 岁起", Z1984["direction"] == "逆行"
      and Z1984["daxian"][0]["start_age"] == 4)

# 1995-01-20 10:00 男 → 农历 1994-12-20 巳时，农历年 1994 甲戌
# 命宫 = (2 + 12-1 - 5) % 12 = 8 → 申
# 甲年寅起丙 → 申 = (2+(8-2))%10=8 壬 → 壬申剑锋金 → 金四局
# 紫微：日20/局4，20%4=0 补数0 → 20/4=5 → 寅后5-1=午
check("手算 1995 农历年=1994 甲戌", Z1995["year_ganzhi"] == "甲戌")
check("手算 1995 命宫在申", Z1995["ming_gong"]["zhi"] == "申")
check("手算 1995 壬申纳音→金四局", Z1995["wuxing_ju"]["name"] == "金四局")
check("手算 1995 紫微在午", Z1995["ziwei"]["zhi"] == "午")


# ================================================================ 五、iztro 基准
print("\n== 五、iztro 独立实现比对基准 ==")

# 基准数据来自 npm iztro 2.6.3（astro.bySolar + fixLeap=true）实测输出，
# 与本层实现逐宫一致；四化表在庚干化科上有流派差异，此处取本层口径（天府化科），
# 不含庚年基准。
IZTRO_BASELINES = [
    dict(label="2004-06-12 10:00 男", args=(2004, 6, 12, 10, 1),
         lunar="二〇〇四年四月廿五", ming="子", shen="戌", ju="水二局",
         ziwei="丑", tianfu="卯", ming_zhu="贪狼", shen_zhu="天梁",
         stars=parse_stars("子天机 丑紫微破军 卯天府 辰太阴 巳廉贞贪狼 午巨门 未天相 "
                           "申天同天梁 酉武曲七杀 戌太阳"),
         sihua={"廉贞": "禄", "破军": "权", "武曲": "科", "太阳": "忌"},
         dx0=("命宫", "丙子", 2, 11, 2005, 2014)),
    dict(label="1984-02-20 10:00 女", args=(1984, 2, 20, 10, 0),
         lunar="一九八四年正月十九", ming="酉", shen="未", ju="金四局",
         ziwei="巳", tianfu="亥", ming_zhu="文曲", shen_zhu="火星",
         stars=parse_stars("寅太阳巨门 卯天相 辰天机天梁 巳紫微七杀 酉廉贞破军 "
                           "亥天府 子天同太阴 丑武曲贪狼"),
         sihua={"廉贞": "禄", "破军": "权", "武曲": "科", "太阳": "忌"},
         dx0=("命宫", "癸酉", 4, 13, 1987, 1996)),
    dict(label="1995-01-20 10:00 男", args=(1995, 1, 20, 10, 1),
         lunar="一九九四年腊月二十", ming="申", shen="午", ju="金四局",
         ziwei="午", tianfu="戌", ming_zhu="廉贞", shen_zhu="文昌",
         stars=parse_stars("寅武曲天相 卯太阳天梁 辰七杀 巳天机 午紫微 申破军 "
                           "戌廉贞天府 亥太阴 子贪狼 丑天同巨门"),
         sihua={"廉贞": "禄", "破军": "权", "武曲": "科", "太阳": "忌"},
         dx0=("命宫", "壬申", 4, 13, 1997, 2006)),
    dict(label="1975-05-05 10:00 女", args=(1975, 5, 5, 10, 0),
         lunar="一九七五年三月廿四", ming="亥", shen="酉", ju="土五局",
         ziwei="巳", tianfu="亥", ming_zhu="巨门", shen_zhu="天同",
         stars=parse_stars("寅太阳巨门 卯天相 辰天机天梁 巳紫微七杀 酉廉贞破军 "
                           "亥天府 子天同太阴 丑武曲贪狼"),
         sihua={"天机": "禄", "天梁": "权", "紫微": "科", "太阴": "忌"},
         dx0=("命宫", "丁亥", 5, 14, 1979, 1988)),
    dict(label="2022-05-05 10:00 男", args=(2022, 5, 5, 10, 1),
         lunar="二〇二二年四月初五", ming="子", shen="戌", ju="木三局",
         ziwei="寅", tianfu="寅", ming_zhu="贪狼", shen_zhu="天梁",
         stars=parse_stars("寅紫微天府 卯太阴 辰贪狼 巳巨门 午廉贞天相 未天梁 "
                           "申七杀 酉天同 戌武曲 亥太阳 子破军 丑天机"),
         sihua={"天梁": "禄", "紫微": "权", "左辅": "科", "武曲": "忌"},
         dx0=("命宫", "壬子", 3, 12, 2024, 2033)),
]

PRESET = {b["label"]: make_ziwei(*b["args"])[1] for b in IZTRO_BASELINES}
for b in IZTRO_BASELINES:
    z = PRESET[b["label"]]
    tag = b["label"]
    check("%s iztro 农历一致" % tag, z["lunar"]["text"] == b["lunar"],
          z["lunar"]["text"])
    check("%s iztro 命宫一致" % tag, z["ming_gong"]["zhi"] == b["ming"], z["ming_gong"]["zhi"])
    check("%s iztro 身宫一致" % tag, z["shen_gong"]["zhi"] == b["shen"], z["shen_gong"]["zhi"])
    check("%s iztro 五行局一致" % tag, z["wuxing_ju"]["name"] == b["ju"],
          z["wuxing_ju"]["name"])
    check("%s iztro 命主/身主一致" % tag,
          (z["ming_zhu"], z["shen_zhu"]) == (b["ming_zhu"], b["shen_zhu"]),
          (z["ming_zhu"], z["shen_zhu"]))
    check("%s iztro 紫微/天府一致" % tag,
          (z["ziwei"]["zhi"], z["tianfu"]["zhi"]) == (b["ziwei"], b["tianfu"]),
          (z["ziwei"]["zhi"], z["tianfu"]["zhi"]))
    got = {k: sorted(v) for k, v in stars_of(z).items()}
    want = {k: sorted(v) for k, v in b["stars"].items()}
    check("%s iztro 十四主星落宫一致" % tag, got == want,
          {k: (got.get(k), want.get(k)) for k in set(got) | set(want)
           if got.get(k) != want.get(k)})
    check("%s iztro 四化落宫一致" % tag, hua_of(z) == b["sihua"], hua_of(z))
    d = z["daxian"][0]
    check("%s iztro 首限一致" % tag,
          (d["palace"], d["ganzhi"], d["start_age"], d["end_age"],
           d["start_year"], d["end_year"]) == b["dx0"],
          (d["palace"], d["ganzhi"], d["start_age"], d["end_age"],
           d["start_year"], d["end_year"]))

# 晚子时基准（亦与 iztro timeIndex=12 核对过）：2004-06-12 23:00 男
check("晚子时 2004-06-12 23:00 命巳身巳（与 iztro 一致）",
      (ZLATE["ming_gong"]["zhi"], ZLATE["shen_gong"]["zhi"]) == ("巳", "巳"),
      (ZLATE["ming_gong"]["zhi"], ZLATE["shen_gong"]["zhi"]))
check("晚子时 2004-06-12 23:00 木三局、紫微子、天府辰",
      ZLATE["wuxing_ju"]["name"] == "木三局" and ZLATE["ziwei"]["zhi"] == "子"
      and ZLATE["tianfu"]["zhi"] == "辰")
check("晚子时写明流派局限", any("晚子时" in l for l in ZLATE["limits"]), ZLATE["limits"])


# ================================================================ 六、边界与健壮性
print("\n== 六、边界与健壮性 ==")

# 闰月：闰二月前半月按 2 月、后半月按 3 月
check("闰月前半月识别 leap=True", ZLEAP_A["lunar"]["leap"] is True)
check("闰月前半月安星月=2", ZLEAP_A["lunar"]["month"] == 2, ZLEAP_A["lunar"])
check("闰月前半月说明含「闰」与「本月」",
      "闰" in ZLEAP_A["leap_note"] and "本月" in ZLEAP_A["leap_note"],
      ZLEAP_A["leap_note"])
check("闰月前半月命宫=戌（月2、时5 → 2+1-5=-2→10）",
      ZLEAP_A["ming_gong"]["zhi"] == "戌", ZLEAP_A["ming_gong"]["zhi"])
check("闰月后半月安星月=3", ZLEAP_B["lunar"]["month"] == 3, ZLEAP_B["lunar"])
check("闰月后半月说明含「闰」与「下月」",
      "闰" in ZLEAP_B["leap_note"] and "下月" in ZLEAP_B["leap_note"],
      ZLEAP_B["leap_note"])
check("闰月后半月命宫=亥（月3 → 2+2-5=-1→11）",
      ZLEAP_B["ming_gong"]["zhi"] == "亥", ZLEAP_B["ming_gong"]["zhi"])
check("闰月两半相差一宫（各按本月/下月安星）",
      (ZHI.index(ZLEAP_B["ming_gong"]["zhi"])
       - ZHI.index(ZLEAP_A["ming_gong"]["zhi"])) % 12 == 1)

# 缺性别：不排大限，写明局限
check("缺性别时 daxian 为空", ZNOSEX["daxian"] == [], ZNOSEX["daxian"])
check("缺性别时十二宫仍齐全", len(ZNOSEX["palaces"]) == 12)
check("缺性别时 limits 写明依赖性别",
      any("性别" in l for l in ZNOSEX["limits"]), ZNOSEX["limits"])
check("缺性别时命宫/五行局仍可算",
      ZNOSEX["ming_gong"]["zhi"] == "子" and ZNOSEX["wuxing_ju"]["name"] == "水二局")

# 缺时辰：由 report.input.time_unknown 触发
c_unknown = chart.build(2004, 6, 12, 10, 0, sex=1)
c_unknown["time_pillar_reliable"] = False
z_unknown = ziwei.chart_ziwei({"chart": c_unknown,
                               "input": {"sex": "male", "time_unknown": True}})
check("缺时辰仍能出盘（结构完整）", len(z_unknown["palaces"]) == 12)
check("缺时辰 limits 写明时辰未知",
      any("时辰" in l for l in z_unknown["limits"]), z_unknown["limits"])

# 确定性 / JSON 可序列化
_, z_again = make_ziwei(2004, 6, 12, 10, 1)
check("同输入两次结果完全相同", z_again == Z2004)
try:
    dumped = json.dumps(Z2004, ensure_ascii=False)
    json.loads(dumped)
    check("输出 dict 可 JSON 序列化", True)
except (TypeError, ValueError) as exc:  # pragma: no cover
    check("输出 dict 可 JSON 序列化", False, exc)

# 渲染
text = ziwei.render_ziwei_text(Z2004)
check("渲染文本为 str 且非空", isinstance(text, str) and len(text) > 200)
check("渲染含标题与命身宫/五行局",
      "紫微斗数层" in text and "命宫" in text and "水二局" in text)
check("渲染含十二宫全部宫名", all(name in text for name in PALACE_NAMES))
check("渲染含四化/大限/格局/说明段落",
      all(seg in text for seg in ("【年干四化】", "【大限】",
                                  "【格局与结构】", "【说明与局限】")))
check("渲染含闰月说明", "闰月说明" in text)
check("渲染无 Python 原始值泄漏（None/True/False）",
      "None" not in text and "True" not in text and "False" not in text)
check("渲染十二宫表每行含宫名与宫干支",
      all(("%s" % ZHI[ZHI.index(p["zhi"])]) in text for p in Z2004["palaces"]))
text_nosex = ziwei.render_ziwei_text(ZNOSEX)
check("缺性别渲染可出（提示未排大限）",
      isinstance(text_nosex, str) and "性别" in text_nosex)

# CLI 接入（--ziwei / --json ziwei 字段）
proc = subprocess.run([PY, CLI, "--date", "2004-06-12", "--time", "10:00",
                       "--sex", "male", "--ziwei"],
                      capture_output=True, text=True, encoding="utf-8")
check("CLI --ziwei 文本输出成功", proc.returncode == 0
      and "紫微斗数层" in (proc.stdout or ""), (proc.returncode, proc.stderr[-300:]))
proc = subprocess.run([PY, CLI, "--date", "2004-06-12", "--time", "10:00",
                       "--sex", "male", "--ziwei", "--json"],
                      capture_output=True, text=True, encoding="utf-8")
cli_ok, cli_z = False, None
if proc.returncode == 0:
    try:
        cli_z = json.loads(proc.stdout)["ziwei"]
        cli_ok = True
    except (ValueError, KeyError):
        cli_ok = False
check("CLI --json 写出 ziwei 字段", cli_ok, (proc.returncode, proc.stderr[-300:]))
check("CLI ziwei 十二宫齐全且命宫子",
      bool(cli_z) and len(cli_z["palaces"]) == 12
      and cli_z["ming_gong"]["zhi"] == "子")
proc = subprocess.run([PY, CLI, "--date", "2004-06-12", "--time", "10:00",
                       "--sex", "male", "--time-unknown", "--ziwei", "--json"],
                      capture_output=True, text=True, encoding="utf-8")
unknown_ok = False
if proc.returncode == 0:
    try:
        zz = json.loads(proc.stdout)["ziwei"]
        unknown_ok = any("时辰" in l for l in zz["limits"])
    except (ValueError, KeyError):
        unknown_ok = False
check("CLI --time-unknown 紫微盘写明时辰局限", unknown_ok)


# ================================================================ 七、断语层
print("\n== 七、断语层（亮度 / 三方四正 / 格局 / 大限主题）==")

LEVELS = ["庙", "旺", "得地", "利", "平", "不", "陷"]

# --- 7.1 亮度数据表完整性 ---
check("BRIGHTNESS 恰含十四主星", set(ziwei.BRIGHTNESS) == set(MAIN14),
      sorted(set(MAIN14) - set(ziwei.BRIGHTNESS)))
check("亮度七级定义正确", ziwei.BRIGHTNESS_LEVELS == LEVELS,
      ziwei.BRIGHTNESS_LEVELS)
for star in MAIN14:
    row = ziwei.BRIGHTNESS.get(star) or []
    check("亮度表 %s 覆盖十二地支且取值合法" % star,
          len(row) == 12 and all(lv in LEVELS for lv in row), row)

seen_levels = set()
for row in ziwei.BRIGHTNESS.values():
    seen_levels.update(row)
check("亮度表七级都实际出现", set(LEVELS) <= seen_levels, sorted(seen_levels))
check("原书未标 9 格按「平」归一",
      sorted(ziwei.BRIGHTNESS_UNMARKED) == sorted(
          ["紫微子", "紫微卯", "紫微酉", "天府子", "天府午",
           "天梁巳", "天梁亥", "破军巳", "破军亥"]),
      ziwei.BRIGHTNESS_UNMARKED)

PINNED_BRIGHTNESS = [("紫微", "丑", "庙"), ("紫微", "子", "平"), ("天机", "子", "庙"),
                     ("天机", "丑", "陷"), ("太阳", "卯", "庙"), ("太阳", "子", "陷"),
                     ("武曲", "丑", "庙"), ("天同", "午", "陷"), ("廉贞", "申", "庙"),
                     ("廉贞", "巳", "陷"), ("天府", "寅", "庙"), ("天府", "子", "平"),
                     ("太阴", "亥", "庙"), ("太阴", "卯", "陷"), ("贪狼", "巳", "陷"),
                     ("巨门", "丑", "不"), ("天相", "卯", "陷"), ("天梁", "申", "陷"),
                     ("七杀", "丑", "庙"), ("破军", "子", "庙")]
for star, zhi, level in PINNED_BRIGHTNESS:
    got = ziwei.BRIGHTNESS[star][ZHI.index(zhi)]
    check("亮度基准 %s在%s=%s" % (star, zhi, level), got == level, got)

check("brightness 顶层结构齐全",
      {"levels", "table", "source", "unmarked_as_ping"} <= set(Z2004["brightness"]))
check("brightness.table 为 14×12 全表",
      set(Z2004["brightness"]["table"]) == set(MAIN14)
      and all(len(v) == 12 and set(v) == set(ZHI)
              for v in Z2004["brightness"]["table"].values()))
check("brightness.source 说明来源",
      "全书" in Z2004["brightness"]["source"])

# --- 7.2 每宫亮度与全盘汇总 ---
for tag, z in [("2004", Z2004), ("1984", Z1984), ("2022", Z2022),
               ("闰月前", ZLEAP_A), ("无性别", ZNOSEX)]:
    ok, bad = True, None
    for p in z["palaces"]:
        items = p.get("star_brightness") or []
        if [i["star"] for i in items] != list(p["main_stars"]):
            ok, bad = False, p["name"]
    check("%s 每宫 star_brightness 与主星一一对应" % tag, ok, bad)
    check("%s 每宫 star_brightness 等级合法" % tag,
          all(i["level"] in LEVELS for p in z["palaces"]
              for i in (p.get("star_brightness") or [])))

check("main_star_brightness 恰 14 条",
      len(Z2004["main_star_brightness"]) == 14)
check("main_star_brightness 覆盖十四主星",
      sorted(i["star"] for i in Z2004["main_star_brightness"]) == sorted(MAIN14))
check("main_star_brightness 等级合法",
      all(i["level"] in LEVELS for i in Z2004["main_star_brightness"]))
check("main_star_brightness 星曜确实落在所标地支",
      all(i["star"] in stars_of(Z2004).get(i["zhi"], [])
          for i in Z2004["main_star_brightness"]))
check("main_star_brightness 宫位名与命宫相对位置一致",
      all(i["palace"] == PALACE_NAMES[(Z2004["ming_gong"]["zhi_index"]
                                       - i["zhi_index"]) % 12]
          for i in Z2004["main_star_brightness"]))
for star, zhi, level in [("天机", "子", "庙"), ("太阳", "戌", "陷"),
                         ("太阴", "辰", "陷"), ("武曲", "酉", "利"),
                         ("紫微", "丑", "庙")]:
    item = [i for i in Z2004["main_star_brightness"] if i["star"] == star][0]
    check("2004 盘 %s在%s亮度=%s" % (star, zhi, level),
          item["zhi"] == zhi and item["level"] == level, item)

# --- 7.3 三方四正几何 ---
for tag, z in ALL + [("无性别", ZNOSEX), ("晚子时", ZLATE)]:
    names_ok, dist_ok, bad = True, True, None
    for n, p in enumerate(z["palaces"]):
        sf_sz = p["sf_sz"]
        want_sf = [PALACE_NAMES[(n + 4) % 12], PALACE_NAMES[(n + 8) % 12]]
        want_sz = PALACE_NAMES[(n + 6) % 12]
        if sf_sz["sf"] != want_sf or sf_sz["sz"]["name"] != want_sz:
            names_ok, bad = False, p["name"]
        base = ZHI.index(p["zhi"])
        if sorted(sf_sz["sf_zhi"]) != sorted([ZHI[(base + 4) % 12],
                                              ZHI[(base + 8) % 12]]):
            dist_ok = False
        if sf_sz["sz"]["zhi"] != ZHI[(base + 6) % 12]:
            dist_ok = False
    check("%s 每宫三方四正宫名几何正确" % tag, names_ok, bad)
    check("%s 每宫三方地支相隔 4/8 宫、对宫相隔 6 宫" % tag, dist_ok)

for tag, z in [("2004", Z2004), ("1984", Z1984), ("2022", Z2022)]:
    sf_sz = z["palaces"][0]["sf_sz"]
    check("%s 命宫三方为财帛宫/官禄宫、对宫迁移宫" % tag,
          sf_sz["sf"] == ["财帛宫", "官禄宫"]
          and sf_sz["sz"]["name"] == "迁移宫")
check("2004 命宫三方四正地支=申/辰/午",
      Z2004["palaces"][0]["sf_sz"]["sf_zhi"] == ["申", "辰"]
      and Z2004["palaces"][0]["sf_sz"]["sz"]["zhi"] == "午")


def _sfz_stars(z, n):
    """本宫 + 三方 + 对宫的主星列表（按宫序拼接）。"""
    return (list(z["palaces"][n]["main_stars"])
            + list(z["palaces"][(n + 4) % 12]["main_stars"])
            + list(z["palaces"][(n + 8) % 12]["main_stars"])
            + list(z["palaces"][(n + 6) % 12]["main_stars"]))


for tag, z in [("2004", Z2004), ("1984", Z1984), ("闰月后", ZLEAP_B)]:
    check("%s 每宫 sf_sz.main_stars 合本宫与三方对宫主星" % tag,
          all(sorted(p["sf_sz"]["main_stars"]) == sorted(_sfz_stars(z, n))
              for n, p in enumerate(z["palaces"])))
check("san_fang_si_zheng 恰 12 条且顺序同十二宫",
      [i["palace"] for i in Z2004["san_fang_si_zheng"]] == PALACE_NAMES)
check("san_fang_si_zheng 每条含两个三方宫+一个对宫",
      all(len(i["san_fang"]) == 2 and set(i["dui_gong"]) == {"name", "zhi"}
          for i in Z2004["san_fang_si_zheng"]))
check("san_fang_si_zheng 与 palaces.sf_sz 一致",
      all(i["san_fang"][0]["name"] == p["sf_sz"]["sf"][0]
          and i["dui_gong"]["name"] == p["sf_sz"]["sz"]["name"]
          for i, p in zip(Z2004["san_fang_si_zheng"], Z2004["palaces"])))

# --- 7.4 格局识别 ---
check("PATTERN_LEVELS 三态正确", ziwei.PATTERN_LEVELS == ["成", "半", "不成立"])
check("STANDARD_PATTERNS 含 13 个标准格局", len(ziwei.STANDARD_PATTERNS) == 13)
PATTERN_KEYS = {"name", "level", "palaces", "stars", "detail"}
for tag, z in [("2004", Z2004), ("1984", Z1984), ("2022", Z2022)]:
    check("%s patterns 条目字段齐全且等级合法" % tag,
          bool(z["patterns"])
          and all(PATTERN_KEYS <= set(i) and i["level"] in ziwei.PATTERN_LEVELS
                  for i in z["patterns"]))
    check("%s patterns 含全部 13 个标准格局" % tag,
          all(pattern_of(z, name) is not None for name in ziwei.STANDARD_PATTERNS))

PINNED_PATTERNS = {
    "2004": (Z2004, {"机月同梁": "成", "杀破狼": "不成立", "日月反背": "成",
                     "日月同宫": "不成立", "紫府同宫": "不成立", "禄马交驰": "成",
                     "羊陀夹忌": "不成立", "双禄交流": "不成立",
                     "火铃夹命": "不成立", "命无正曜": "不成立",
                     "刑囚夹印": "不成立"}),
    "1984": (Z1984, {"杀破狼": "成", "机月同梁": "不成立", "日月反背": "不成立",
                     "紫府朝垣": "半", "府相朝垣": "半", "羊陀夹忌": "成",
                     "禄马交驰": "成", "紫府同宫": "不成立"}),
    "2022": (Z2022, {"杀破狼": "成", "紫府同宫": "成", "羊陀夹忌": "半",
                     "机月同梁": "不成立"}),
}
for tag, (z, expect) in PINNED_PATTERNS.items():
    for name, level in expect.items():
        got = pattern_level(z, name)
        check("%s 盘格局 %s=%s" % (tag, name, level), got == level, got)

check("1984 杀破狼落宫含命宫",
      "命宫" in (pattern_of(Z1984, "杀破狼") or {}).get("palaces", []))
check("2004 机月同梁落宫=命宫/财帛宫/官禄宫",
      (pattern_of(Z2004, "机月同梁") or {}).get("palaces")
      == ["命宫", "财帛宫", "官禄宫"],
      (pattern_of(Z2004, "机月同梁") or {}).get("palaces"))
check("2004 禄马交驰落宫=福德宫",
      (pattern_of(Z2004, "禄马交驰") or {}).get("palaces") == ["福德宫"])
check("成/半 格局的 detail 非空",
      all(i["detail"] for z in (Z2004, Z1984, Z2022) for i in z["patterns"]
          if i["level"] in ("成", "半")))
check("2004 盘无「命宫无主星」标签（命宫有天机）",
      pattern_of(Z2004, "命宫无主星") is None)
check("1984 盘化禄入命/化权入命 均成立",
      pattern_level(Z1984, "化禄入命") == "成"
      and pattern_level(Z1984, "化权入命") == "成")

# --- 7.5 大限主题标签 ---
check("daxian_flow 恰 12 条", len(Z2004["daxian_flow"]) == 12)
check("daxian_flow 顺序 1..12",
      [i["order"] for i in Z2004["daxian_flow"]] == list(range(1, 13)))
check("daxian_flow 与 daxian 宫位/干支/年份一致",
      [(i["palace"], i["zhi"], i["ganzhi"], i["start_age"], i["end_age"],
        i["start_year"], i["end_year"]) for i in Z2004["daxian_flow"]]
      == [(d["palace"], d["zhi"], d["ganzhi"], d["start_age"], d["end_age"],
           d["start_year"], d["end_year"]) for d in Z2004["daxian"]])
check("daxian_flow themes 全部在词表内",
      all(t in ziwei.THEME_TAGS for i in Z2004["daxian_flow"]
          for t in i["themes"]))
check("daxian_flow 每条主题非空且去重且不超过 4 个",
      all(0 < len(i["themes"]) <= 4 and len(i["themes"]) == len(set(i["themes"]))
          for i in Z2004["daxian_flow"]))
check("daxian_flow confidence 只取 高/中/低",
      all(i["confidence"] in ("高", "中", "低")
          for z in (Z2004, Z1984, Z2022, ZLATE) for i in z["daxian_flow"]))
check("daxian_flow basis 非空且以大限命宫起头",
      all(i["basis"].startswith("大限命宫") and len(i["basis"]) > 10
          for i in Z2004["daxian_flow"]))
check("daxian_flow stars.ming = 大限命宫主星",
      all(i["stars"]["ming"]
          == Z2004["palaces"][PALACE_NAMES.index(i["palace"])]["main_stars"]
          for i in Z2004["daxian_flow"]))
check("daxian_flow sihua 条目均为合法四化",
      all(i["hua"] in "禄权科忌" and isinstance(i["star"], str)
          for z in (Z2004, Z1984) for f in z["daxian_flow"] for i in f["sihua"]))
check("2004 首限主题含 自我/事业/学业",
      {"自我", "事业", "学业"} <= set(Z2004["daxian_flow"][0]["themes"]),
      Z2004["daxian_flow"][0]["themes"])
check("2004 首限 confidence=高", Z2004["daxian_flow"][0]["confidence"] == "高")
check("1984 首限主题含 事业/迁移（杀破狼结构）",
      {"事业", "迁移"} <= set(Z1984["daxian_flow"][0]["themes"]),
      Z1984["daxian_flow"][0]["themes"])
check("1984 首限四化含 廉贞化禄/破军化权/武曲化科",
      sorted("%s化%s" % (i["star"], i["hua"])
             for i in Z1984["daxian_flow"][0]["sihua"])
      == ["廉贞化禄", "武曲化科", "破军化权"],
      Z1984["daxian_flow"][0]["sihua"])
check("2022 首限主题含 事业/迁移",
      {"事业", "迁移"} <= set(Z2022["daxian_flow"][0]["themes"]))
check("缺性别盘 daxian_flow 为空", ZNOSEX["daxian_flow"] == [])
check("晚子时盘 daxian_flow 仍 12 条", len(ZLATE["daxian_flow"]) == 12)
check("daxian_flow 无吉凶评分字段",
      all(not ({"score", "luck", "rating", "吉凶"} & set(i))
          for i in Z2004["daxian_flow"]))

# --- 7.6 序列化 / 渲染 / CLI / 文案口径 ---
try:
    dumped9 = json.dumps(Z2004, ensure_ascii=False)
    check("含断语层的输出可 JSON 序列化",
          isinstance(json.loads(dumped9), dict))
except (TypeError, ValueError) as exc:  # pragma: no cover
    check("含断语层的输出可 JSON 序列化", False, exc)

text2 = ziwei.render_ziwei_text(Z2004)
for seg in ("【主星亮度】", "【三方四正】", "【大限主题】"):
    check("渲染含断语层段落 %s" % seg, seg in text2)
check("渲染格局标注三态等级", "机月同梁（成）" in text2 and "不成立" in text2)
check("渲染无 Python 原始值泄漏（None/True/False）",
      "None" not in text2 and "True" not in text2 and "False" not in text2)
sec_bright = text2.split("【主星亮度】")[1].split("【")[0]
bright_lines = [ln for ln in sec_bright.splitlines() if ln.startswith("  ")]
check("渲染主星亮度恰 14 行", len(bright_lines) == 14, len(bright_lines))
sec_sf = text2.split("【三方四正】")[1].split("【")[0]
sf_lines = [ln for ln in sec_sf.splitlines() if ln.startswith("  ")]
check("渲染三方四正恰 12 行", len(sf_lines) == 12, len(sf_lines))
check("渲染大限主题 12 行", text2.count("可信度") == 12)
text_nosex2 = ziwei.render_ziwei_text(ZNOSEX)
check("缺性别渲染提示大限主题无法确定",
      "大限主题无法确定" in text_nosex2)
check("缺性别渲染仍有主星亮度与三方四正",
      "【主星亮度】" in text_nosex2 and "【三方四正】" in text_nosex2)
check("summary 含断语层口径说明",
      any("结构识别" in s for s in Z2004["summary"]))
check("summary 含十四主星亮度分布",
      any("亮度分布" in s for s in Z2004["summary"]))
check("limits 注明亮度表来源与未标 9 格",
      any("全书" in l and "9 格" in l for l in Z2004["limits"]))
check("limits 注明格局只做结构条件判定",
      any("格局" in l and "结构条件" in l for l in Z2004["limits"]))
check("limits 注明三方四正未做夹宫借星",
      any("三方四正" in l and "夹宫" in l for l in Z2004["limits"]))
check("limits 注明大限 confidence 不代表吉凶",
      any("confidence" in l and "吉凶" in l for l in Z2004["limits"]))

proc = subprocess.run([PY, CLI, "--date", "2004-06-12", "--time", "10:00",
                       "--sex", "male", "--ziwei", "--json"],
                      capture_output=True, text=True, encoding="utf-8")
cli9_ok = False
if proc.returncode == 0:
    try:
        cj = json.loads(proc.stdout)["ziwei"]
        cli9_ok = (len(cj["brightness"]["table"]) == 14
                   and len(cj["daxian_flow"]) == 12
                   and all("level" in p for p in cj["patterns"])
                   and "star_brightness" in cj["palaces"][0])
    except (ValueError, KeyError, TypeError):
        cli9_ok = False
check("CLI --json 紫微盘含断语层字段", cli9_ok)
proc = subprocess.run([PY, CLI, "--date", "2004-06-12", "--time", "10:00",
                       "--sex", "male", "--ziwei"],
                      capture_output=True, text=True, encoding="utf-8")
check("CLI --ziwei 文本含断语层段落",
      proc.returncode == 0 and "【主星亮度】" in (proc.stdout or ""))


# ================================================================ 统计
print("\n" + "=" * 60)
if failures:
    print("失败 %d / %d 项：" % (len(failures), total))
    for name, detail in failures:
        print("  - %s  ← %s" % (name, detail))
    print("verify_ziwei: FAIL")
    sys.exit(1)
print("verify_ziwei: 全部通过 %d 项 ✅" % total)
sys.exit(0)
