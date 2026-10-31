# -*- coding: utf-8 -*-
"""紫微斗数层（ziwei）：从八字排盘报告派生一张紫微斗数命盘（v1）。

设计原则
--------
1. 纯规则、纯标准库：命宫/身宫、宫干（五虎遁）、五行局（纳音）、紫微/天府安星、
   十四主星、六吉六煞、年干四化、大限，全部按三合派通行安星诀推算；无随机、
   无网络、无第三方依赖（只 import 标准库 unicodedata 用于排版对齐）。
2. 只读不改：输入是 bazi.build_report() 的返回值（主要是 report["chart"]），
   不重新解析公历/农历。紫微取「农历年」（正月初一为界，不是立春）定年干年支，
   农历日数取自 report["chart"]["lunar"]，时支取自四柱时支（排盘采用时间）。
3. 闰月按「前半月（≤15 日）算本月、后半月（>15 日）算下月」处理，并写进
   leap_note；与 iztro（fixLeap=true）的通行约定一致。
4. 只做有把握的内容：命主/身主用通行表。流派分歧（庚/壬干四化、闰月、晚子时、
   真太阳时跨日、时辰未知）一律列入 limits，不静默假设。
5. 断语层（v1 之上的增补，纯增补字段）同样只做「结构识别」：星曜亮度（庙旺利陷）取
   《紫微斗数全书》卷二文字表归一，三方四正按三合宫+对宫机械生成，格局只判
   「结构条件是否满足」（成/半/不成立），大限只给主题标签与置信度。所有条目都是
   盘面构成的描述，不给吉凶评分、不写事件预测、不把「庙旺」等同于「吉」。
6. 输出为可 JSON 序列化的 dict，供 CLI/文档层直接复用；render_ziwei_text 只负责
   排版，不增加推断。断语层字段为纯增补：原有键一个不改、不删。

对外接口
--------
chart_ziwei(report) -> dict        report = bazi.build_report() 的返回值
render_ziwei_text(ziwei) -> str    技术版中文文本（十二宫表、四化、大限、格局、局限）

输出 dict 主要字段
------------------
version / method / lunar{text,lunar_year,month,month_raw,leap,day,shichen,
shichen_zhi,shichen_index,leap_note} / year_gan / year_zhi / year_ganzhi /
sex / sex_label / yin_yang / direction / forward / start_age /
ming_gong{zhi,zhi_index,gan,ganzhi,nayin} / shen_gong{zhi,zhi_index,gan,ganzhi,
palace,offset} / wuxing_ju{num,name,element,nayin} / ziwei / tianfu /
ming_zhu / shen_zhu / palaces[12]{name,zhi,zhi_index,gong_gan,gong_ganzhi,
main_stars,ji_stars,sha_stars,other_stars,sihua,star_brightness,is_ming,is_shen,
sf_sz{sf,sf_zhi,sz,main_stars},daxian} /
daxian[12]{order,palace,zhi,gan,ganzhi,start_age,end_age,start_year,end_year} /
sihua[4]{star,hua,palace,zhi} / patterns[{name,level,palaces,stars,detail}] /
brightness{levels,table,source,unmarked_as_ping} / main_star_brightness[14]{star,
zhi,zhi_index,palace,level} / san_fang_si_zheng[12]{palace,zhi,san_fang[{name,zhi}],
dui_gong{name,zhi},main_stars} / daxian_flow[12]{order,palace,zhi,ganzhi,start_age,
end_age,start_year,end_year,themes,confidence,stars,sihua,basis} / summary[] /
limits[] / leap_note / note
"""

import unicodedata

VERSION = "v1"

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"

# 十二宫（从命宫起逆行排列，索引即「距命宫逆数宫数」）
PALACE_NAMES = ["命宫", "兄弟宫", "夫妻宫", "子女宫", "财帛宫", "疾厄宫",
                "迁移宫", "交友宫", "官禄宫", "田宅宫", "福德宫", "父母宫"]

# 六十甲子纳音：每两个干支共一名，共 30 名（索引 = 干支序号 // 2）
NAYIN_30 = ["海中金", "炉中火", "大林木", "路旁土", "剑锋金",
            "山头火", "涧下水", "城头土", "白蜡金", "杨柳木",
            "泉中水", "屋上土", "霹雳火", "松柏木", "长流水",
            "砂中金", "山下火", "平地木", "壁上土", "金箔金",
            "覆灯火", "天河水", "大驿土", "钗钏金", "桑柘木",
            "大溪水", "沙中土", "天上火", "石榴木", "大海水"]
# 纳音五行按「名序 % 15」循环（30 名 = 2 轮）
NAYIN_WUXING_15 = ["金", "火", "木", "土", "金",
                   "火", "水", "土", "金", "木",
                   "水", "土", "火", "木", "水"]

# 五行局：水二 / 木三 / 金四 / 土五 / 火六
WUXING_JU = {"水": 2, "木": 3, "金": 4, "土": 5, "火": 6}
JU_NAME = {2: "水二局", 3: "木三局", 4: "金四局", 5: "土五局", 6: "火六局"}

# 十四主星的安星偏移（紫微系自紫微起逆布；天府系自天府起顺布）
ZIWEI_SERIES = [("紫微", 0), ("天机", -1), ("太阳", -3),
                ("武曲", -4), ("天同", -5), ("廉贞", -8)]
TIANFU_SERIES = [("天府", 0), ("太阴", 1), ("贪狼", 2), ("巨门", 3),
                 ("天相", 4), ("天梁", 5), ("七杀", 6), ("破军", 10)]
MAIN_STARS = [s for s, _ in ZIWEI_SERIES] + [s for s, _ in TIANFU_SERIES]

# 年干四化（通行表）：(化禄, 化权, 化科, 化忌)
SIHUA = {
    "甲": (("廉贞", "禄"), ("破军", "权"), ("武曲", "科"), ("太阳", "忌")),
    "乙": (("天机", "禄"), ("天梁", "权"), ("紫微", "科"), ("太阴", "忌")),
    "丙": (("天同", "禄"), ("天机", "权"), ("文昌", "科"), ("廉贞", "忌")),
    "丁": (("太阴", "禄"), ("天同", "权"), ("天机", "科"), ("巨门", "忌")),
    "戊": (("贪狼", "禄"), ("太阴", "权"), ("右弼", "科"), ("天机", "忌")),
    "己": (("武曲", "禄"), ("贪狼", "权"), ("天梁", "科"), ("文曲", "忌")),
    "庚": (("太阳", "禄"), ("武曲", "权"), ("天府", "科"), ("天同", "忌")),
    "辛": (("巨门", "禄"), ("太阳", "权"), ("文曲", "科"), ("文昌", "忌")),
    "壬": (("天梁", "禄"), ("紫微", "权"), ("左辅", "科"), ("武曲", "忌")),
    "癸": (("破军", "禄"), ("巨门", "权"), ("太阴", "科"), ("贪狼", "忌")),
}

# 命主（按命宫地支）
MING_ZHU = {"子": "贪狼", "丑": "巨门", "寅": "禄存", "卯": "文曲",
            "辰": "廉贞", "巳": "武曲", "午": "破军", "未": "武曲",
            "申": "廉贞", "酉": "文曲", "戌": "禄存", "亥": "巨门"}
# 身主（按生年地支）
SHEN_ZHU = {"子": "火星", "丑": "天相", "寅": "天梁", "卯": "天同",
            "辰": "文昌", "巳": "天机", "午": "火星", "未": "天相",
            "申": "天梁", "酉": "天同", "戌": "文昌", "亥": "天机"}

# 禄存（按年干）；擎羊 = 禄存顺一宫，陀罗 = 禄存逆一宫
LU_CUN = {"甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
          "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子"}

# 天魁 / 天钺（按年干）
KUI_YUE = {"甲": ("丑", "未"), "乙": ("子", "申"), "丙": ("亥", "酉"),
           "丁": ("亥", "酉"), "戊": ("丑", "未"), "己": ("子", "申"),
           "庚": ("丑", "未"), "辛": ("午", "寅"), "壬": ("卯", "巳"),
           "癸": ("卯", "巳")}

# 火星 / 铃星起子时宫位（按生年地支三合）：(火星起宫, 铃星起宫)
HUO_LING = {"寅": ("丑", "卯"), "午": ("丑", "卯"), "戌": ("丑", "卯"),
            "申": ("寅", "戌"), "子": ("寅", "戌"), "辰": ("寅", "戌"),
            "巳": ("卯", "戌"), "酉": ("卯", "戌"), "丑": ("卯", "戌"),
            "亥": ("酉", "戌"), "卯": ("酉", "戌"), "未": ("酉", "戌")}

# 天马（按生年地支三合，只落四马地）
TIAN_MA = {"寅": "申", "午": "申", "戌": "申",
           "申": "寅", "子": "寅", "辰": "寅",
           "巳": "亥", "酉": "亥", "丑": "亥",
           "亥": "巳", "卯": "巳", "未": "巳"}

# ---------------------------------------------------------------- 断语层数据表
#
# 所有断语层内容都是「结构识别」：亮度、三方四正、格局、大限主题都只描述盘面
# 构成，不给吉凶评分、不作事件预测。数据表若与他派不同，一律写进 limits 说明。

# 庙旺利陷七级（由强到弱）：庙 > 旺 > 得地 > 利 > 平 > 不 > 陷
BRIGHTNESS_LEVELS = ["庙", "旺", "得地", "利", "平", "不", "陷"]

# 十四主星 × 十二地支亮度表，列序按 ZHI（子丑寅卯辰巳午未申酉戌亥）。
# 来源：《紫微斗数全书》卷二「一命宫」十四节原词（庙/旺/利益/和平/不得地/陷），
# 归一为 庙/旺/得地/利/平/不/陷。原书未标状态的 9 格（见 BRIGHTNESS_UNMARKED）
# 本层按「平」处理，不臆造庙旺。
BRIGHTNESS = {
    "紫微": ["平", "庙", "旺", "平", "得地", "旺", "庙", "庙", "旺", "平", "得地", "旺"],
    "天机": ["庙", "陷", "得地", "旺", "利", "平", "庙", "陷", "得地", "旺", "利", "平"],
    "太阳": ["陷", "陷", "旺", "庙", "旺", "旺", "旺", "得地", "得地", "平", "陷", "陷"],
    "武曲": ["旺", "庙", "得地", "利", "庙", "平", "旺", "庙", "得地", "利", "庙", "平"],
    "天同": ["旺", "不", "利", "平", "平", "庙", "陷", "不", "旺", "平", "平", "庙"],
    "廉贞": ["平", "利", "平", "平", "利", "陷", "平", "利", "庙", "平", "利", "陷"],
    "天府": ["平", "庙", "庙", "庙", "庙", "得地", "平", "庙", "得地", "旺", "庙", "得地"],
    "太阴": ["庙", "庙", "庙", "陷", "陷", "陷", "陷", "利", "利", "庙", "庙", "庙"],
    "贪狼": ["旺", "庙", "平", "利", "庙", "陷", "旺", "庙", "平", "利", "庙", "陷"],
    "巨门": ["旺", "不", "庙", "庙", "平", "旺", "旺", "不", "庙", "庙", "平", "旺"],
    "天相": ["庙", "庙", "庙", "陷", "得地", "得地", "庙", "得地", "庙", "陷", "得地", "得地"],
    "天梁": ["庙", "庙", "庙", "庙", "庙", "平", "庙", "庙", "陷", "得地", "庙", "平"],
    "七杀": ["旺", "庙", "庙", "旺", "庙", "平", "旺", "庙", "庙", "旺", "庙", "平"],
    "破军": ["庙", "旺", "得地", "陷", "旺", "平", "庙", "旺", "得地", "陷", "旺", "平"],
}

# 原书未标状态、本层按「平」归一的 9 格（星曜+地支）
BRIGHTNESS_UNMARKED = ["紫微子", "紫微卯", "紫微酉", "天府子", "天府午",
                       "天梁巳", "天梁亥", "破军巳", "破军亥"]

BRIGHTNESS_SOURCE = ("《紫微斗数全书》卷二「一命宫」十四主星宫支文字表，"
                     "归并为庙/旺/得地/利/平/不/陷七级；原书未标 9 格按「平」处理。"
                     "亮度只是结构标签，不等于吉凶。")

# 格局判定三态：成=结构条件满足；半=部分满足；不成立=不满足（仍输出，便于核对）
PATTERN_LEVELS = ["成", "半", "不成立"]

# 标准格局清单（本层只做可机械判定的单一口径，顺序即输出顺序）
STANDARD_PATTERNS = ["紫府同宫", "紫府朝垣", "府相朝垣", "机月同梁",
                     "日月同宫", "日月反背", "杀破狼", "命无正曜",
                     "刑囚夹印", "羊陀夹忌", "火铃夹命", "禄马交驰",
                     "双禄交流"]

# 大限主题标签词表（只描述结构主题，不含吉凶）
THEME_TAGS = ["自我", "感情", "家庭", "事业", "财务", "健康",
              "人际", "迁移", "学业", "内在"]

# 宫位 → 主题（大限命宫所落本命宫位）
PALACE_THEMES = {"命宫": ["自我"], "兄弟宫": ["人际"], "夫妻宫": ["感情"],
                 "子女宫": ["家庭"], "财帛宫": ["财务"], "疾厄宫": ["健康"],
                 "迁移宫": ["迁移"], "交友宫": ["人际"], "官禄宫": ["事业"],
                 "田宅宫": ["家庭"], "福德宫": ["内在"], "父母宫": ["家庭"]}

# 十四主星 → 主题标签（只取盘面结构上最直接的一个主题）
STAR_THEME_TAGS = {"紫微": ["自我"], "天机": ["事业"], "太阳": ["事业"],
                   "武曲": ["财务"], "天同": ["内在"], "廉贞": ["事业"],
                   "天府": ["财务"], "太阴": ["财务"], "贪狼": ["人际"],
                   "巨门": ["学业"], "天相": ["事业"], "天梁": ["学业"],
                   "七杀": ["事业"], "破军": ["事业"]}

# 四化 → 主题标签（禄=资源、权=主导、科=名声、忌=课题，均按结构映射）
HUA_THEME_TAGS = {"禄": "财务", "权": "事业", "科": "学业", "忌": "内在"}


def _brightness_of(star, zhi_idx):
    """取某主星落某地支的亮度等级；非主星返回空串。"""
    row = BRIGHTNESS.get(star)
    if row is None:
        return ""
    return row[zhi_idx % 12]


METHOD = ("紫微斗数（三合派安星）：命宫＝寅宫起正月顺数至生月，再起子时逆数至生时；"
          "身宫＝生月宫起子时顺数至生时；十二宫自命宫起逆行排定；宫干用五虎遁；"
          "五行局取命宫干支纳音（水二/木三/金四/土五/火六）；紫微按农历日数与局数"
          "「商数宫前走」推定，天府与紫微对称；十四主星按紫微系逆布、天府系顺布安放；"
          "六吉六煞、禄存天马、年干四化按通行诀安星；大限阳男阴女顺行、阴男阳女逆行，"
          "起运岁数＝局数、每宫十年（虚岁）。")

NOTE = ("紫微斗数与八字是两套独立的推命体系：本层只按安星规则排盘，不作两盘合参、"
        "不下吉凶断语；进阶内容（流年/流月/小限/四化飞星/星曜亮度）不在 v1 范围。")


# ---------------------------------------------------------------- 基础工具

def _nayin_of(gan, zhi):
    """干支 → (纳音名, 五行, 局数)。六十甲子序号由干支奇偶同余唯一确定。"""
    gi, zi = GAN.index(gan), ZHI.index(zhi)
    for i in range(60):
        if i % 10 == gi and i % 12 == zi:
            pair = i // 2
            name = NAYIN_30[pair]
            wuxing = NAYIN_WUXING_15[pair % 15]
            return name, wuxing, WUXING_JU[wuxing]
    raise ValueError("非法干支：%s%s" % (gan, zhi))


def _gong_gan(year_gan_idx, zhi_idx):
    """五虎遁：寅宫干 = (年干序号 % 5) * 2 + 2，其余宫位顺排。

    注意 12 地支与 10 天干不同步，子/丑宫要按「绕一圈」取干，故先对 12 取模。
    """
    yin_gan = (year_gan_idx % 5) * 2 + 2  # 甲己之年丙作首
    return (yin_gan + (zhi_idx - 2) % 12) % 10


def _ziwei_zhi(day, ju):
    """紫微星落宫（地支索引）。

    诀：以五行局数除农历日数，不足则补至可整除（补数 add）；商数自寅宫前进
    (商-1) 宫；add 为偶数顺行 add 宫、为奇数逆行 add 宫。
    """
    add = 0
    rest = day % ju
    if rest:
        add = ju - rest
    quotient = (day + add) // ju
    base = (2 + quotient - 1) % 12  # 自寅宫（索引 2）前进 商-1 宫
    if add % 2 == 0:
        return (base + add) % 12
    return (base - add) % 12


def _tianfu_zhi(ziwei_zhi):
    """天府与紫微以「寅申一线」对称：天府索引 = (4 - 紫微索引) % 12。"""
    return (4 - ziwei_zhi) % 12


def _hour_index(chart):
    """取生时时辰序号（子=0 … 亥=11）。优先用四柱时支，保证与排盘层一致。"""
    pillars = chart.get("pillars") or []
    if len(pillars) >= 4:
        zhi = (pillars[3] or {}).get("zhi")
        if zhi in ZHI:
            return ZHI.index(zhi)
    hour = (chart.get("input") or {}).get("hour")
    if hour is None:
        raise ValueError("报告缺少时支/小时，无法排紫微盘（时辰不可省）")
    return ((int(hour) + 1) // 2) % 12


def _lunar_info(chart):
    """读农历信息并按闰月规则折算安星用的月数。"""
    lun = chart.get("lunar") or {}
    if not lun:
        raise ValueError("报告缺少 chart.lunar（农历信息），无法排紫微盘")
    raw_month = int(lun.get("month") or 1)
    leap = raw_month < 0
    month = abs(raw_month)
    day = int(lun.get("day") or 1)
    lunar_year = int(lun.get("year") or 0)
    if lunar_year <= 0:
        raise ValueError("报告 chart.lunar.year 非法，无法排紫微盘")

    month_eff, leap_note = month, "非闰月，直接按农历%d月安星。" % month
    if leap:
        if day <= 15:
            leap_note = ("闰%d月%d日，闰月前半月（≤15 日）按本月（%d月）安星。"
                         % (month, day, month))
        else:
            month_eff = month + 1
            extra = ""
            if month_eff > 12:
                month_eff = 1
                extra = "（闰十二月后半月按次年正月处理）"
            leap_note = ("闰%d月%d日，闰月后半月（>15 日）按下月（%d月）安星%s。"
                         % (month, day, month_eff, extra))
    return {
        "text": lun.get("text"),
        "lunar_year": lunar_year,
        "month": month_eff,
        "month_raw": month,
        "leap": leap,
        "day": day,
        "leap_note": leap_note,
    }


def _sex_of(report, chart):
    """性别：0 女 / 1 男 / None 未提供。兼容 report.input.sex 的字符串写法。"""
    sex = (chart.get("input") or {}).get("sex")
    if sex in (0, 1):
        return sex
    raw = (report.get("input") or {}).get("sex")
    if isinstance(raw, str):
        return {"male": 1, "m": 1, "男": 1, "female": 0, "f": 0, "女": 0}.get(raw.lower())
    if isinstance(raw, int) and raw in (0, 1):
        return raw
    return None


def _place_stars(ziwei_zhi, month_eff, hour_idx, year_gan, year_zhi):
    """安星：返回 {main/ji/sha/other: {地支索引: [星名…]}, tianfu: 索引}。"""
    main, ji, sha, other = {}, {}, {}, {}

    def put(bucket, star, zhi):
        bucket.setdefault(zhi % 12, []).append(star)

    for star, offset in ZIWEI_SERIES:
        put(main, star, ziwei_zhi + offset)
    tianfu = _tianfu_zhi(ziwei_zhi)
    for star, offset in TIANFU_SERIES:
        put(main, star, tianfu + offset)

    # 六吉：左辅/右弼（按月）、文昌/文曲（按时）、天魁/天钺（按年干）
    put(ji, "左辅", 4 + (month_eff - 1))      # 辰宫起正月顺数
    put(ji, "右弼", 10 - (month_eff - 1))     # 戌宫起正月逆数
    put(ji, "文昌", 10 - hour_idx)            # 戌宫起子时逆数
    put(ji, "文曲", 4 + hour_idx)             # 辰宫起子时顺数
    kui, yue = KUI_YUE[year_gan]
    put(ji, "天魁", ZHI.index(kui))
    put(ji, "天钺", ZHI.index(yue))

    # 六煞：擎羊/陀罗（夹禄存）、火星/铃星（年支三合起子时）、地空/地劫（按时）
    lu = ZHI.index(LU_CUN[year_gan])
    put(sha, "擎羊", lu + 1)
    put(sha, "陀罗", lu - 1)
    huo_base, ling_base = HUO_LING[year_zhi]
    put(sha, "火星", ZHI.index(huo_base) + hour_idx)
    put(sha, "铃星", ZHI.index(ling_base) + hour_idx)
    put(sha, "地空", 11 - hour_idx)
    put(sha, "地劫", 11 + hour_idx)

    # 常用辅星（可选层）：禄存、天马
    put(other, "禄存", lu)
    put(other, "天马", ZHI.index(TIAN_MA[year_zhi]))

    return {"main": main, "ji": ji, "sha": sha, "other": other, "tianfu": tianfu}


# ---------------------------------------------------------------- 主入口

def chart_ziwei(report):
    """从 bazi.build_report() 的返回值排紫微斗数命盘，返回 dict（JSON 可序列化）。"""
    if not isinstance(report, dict):
        raise TypeError("chart_ziwei 需要 bazi.build_report() 返回的 dict")
    chart = report.get("chart") if "chart" in report else report
    if not isinstance(chart, dict) or "pillars" not in chart:
        raise ValueError("report 缺少 chart（排盘结果），无法排紫微盘")

    lunar = _lunar_info(chart)
    hour_idx = _hour_index(chart)
    sex = _sex_of(report, chart)

    lunar_year = lunar["lunar_year"]
    year_gan_idx = (lunar_year - 4) % 10
    year_zhi_idx = (lunar_year - 4) % 12
    year_gan, year_zhi = GAN[year_gan_idx], ZHI[year_zhi_idx]
    month_eff, day = lunar["month"], lunar["day"]

    # 命宫 / 身宫：寅宫起正月顺数至生月，再起子时逆数（命）/ 顺数（身）至生时
    ming = (2 + (month_eff - 1) - hour_idx) % 12
    shen = (2 + (month_eff - 1) + hour_idx) % 12
    ming_gan_idx = _gong_gan(year_gan_idx, ming)
    ming_gan = GAN[ming_gan_idx]
    ming_nayin, ming_wuxing, ju = _nayin_of(ming_gan, ZHI[ming])
    shen_gan_idx = _gong_gan(year_gan_idx, shen)

    # 紫微 / 天府
    ziwei = _ziwei_zhi(day, ju)
    stars = _place_stars(ziwei, month_eff, hour_idx, year_gan, year_zhi)
    tianfu = stars["tianfu"]

    # 星曜位置索引（主星/六吉/六煞/禄存天马统一按地支索引），供四化/格局/大限使用
    star_pos = {}
    for bucket in (stars["main"], stars["ji"], stars["sha"], stars["other"]):
        for zhi_idx, lst in bucket.items():
            for star in lst:
                star_pos[star] = zhi_idx

    # 年干四化 → 星曜化气
    hua_of_star = {star: hua for star, hua in SIHUA[year_gan]}

    # 大限方向：阳男阴女顺行、阴男阳女逆行；起运虚岁 = 局数
    yang = year_gan_idx % 2 == 0
    sex_label = {1: "男", 0: "女", None: "未提供"}[sex]
    forward = None
    if sex is not None:
        forward = (yang and sex == 1) or ((not yang) and sex == 0)
    direction = None
    if forward is not None:
        direction = "顺行" if forward else "逆行"

    # 逐宫装配
    palaces = []
    main_by_zhi = stars["main"]
    for n, name in enumerate(PALACE_NAMES):
        zhi = (ming - n) % 12
        gan_idx = _gong_gan(year_gan_idx, zhi)
        gz = GAN[gan_idx] + ZHI[zhi]
        main_stars = list(main_by_zhi.get(zhi, []))
        ji_stars = list(stars["ji"].get(zhi, []))
        sha_stars = list(stars["sha"].get(zhi, []))
        other_stars = list(stars["other"].get(zhi, []))
        palace_hua = [{"star": s, "hua": hua_of_star[s]}
                      for s in main_stars + ji_stars if s in hua_of_star]
        # 本宫主星亮度（庙旺利陷，结构标签而非吉凶评分）
        star_brightness = [{"star": s, "level": _brightness_of(s, zhi)}
                           for s in main_stars]
        daxian = None
        if forward is not None:
            order = (12 - n) % 12 if forward else n
            start_age = ju + 10 * order
            daxian = {
                "order": order + 1,
                "start_age": start_age,
                "end_age": start_age + 9,
                "start_year": lunar_year + start_age - 1,
                "end_year": lunar_year + start_age + 8,
            }
        palaces.append({
            "name": name,
            "zhi": ZHI[zhi],
            "zhi_index": zhi,
            "gong_gan": GAN[gan_idx],
            "gong_ganzhi": gz,
            "main_stars": main_stars,
            "ji_stars": ji_stars,
            "sha_stars": sha_stars,
            "other_stars": other_stars,
            "sihua": palace_hua,
            "star_brightness": star_brightness,
            "is_ming": n == 0,
            "is_shen": zhi == shen,
            "daxian": daxian,
        })

    # 三方四正：任一宫的三方＝三合宫（相隔四宫/八宫），对宫＝相隔六宫；
    # 这里只做机械几何展开，未做夹宫/借星/流曜。
    for n, palace in enumerate(palaces):
        sf = [palaces[(n + 4) % 12], palaces[(n + 8) % 12]]
        sz = palaces[(n + 6) % 12]
        palace["sf_sz"] = {
            "sf": [p["name"] for p in sf],
            "sf_zhi": [p["zhi"] for p in sf],
            "sz": {"name": sz["name"], "zhi": sz["zhi"]},
            "main_stars": list(palace["main_stars"])
                          + [s for p in sf for s in p["main_stars"]]
                          + list(sz["main_stars"]),
        }

    san_fang_si_zheng = []
    for n, palace in enumerate(palaces):
        sf = [palaces[(n + 4) % 12], palaces[(n + 8) % 12]]
        sz = palaces[(n + 6) % 12]
        san_fang_si_zheng.append({
            "palace": palace["name"],
            "zhi": palace["zhi"],
            "san_fang": [{"name": p["name"], "zhi": p["zhi"]} for p in sf],
            "dui_gong": {"name": sz["name"], "zhi": sz["zhi"]},
            "main_stars": [s for p in [palace] + sf + [sz] for s in p["main_stars"]],
        })

    # 全盘主星亮度汇总（14 主星按固定顺序）
    main_star_brightness = []
    for star in MAIN_STARS:
        zhi_idx = star_pos.get(star)
        if zhi_idx is None:
            continue
        main_star_brightness.append({
            "star": star,
            "zhi": ZHI[zhi_idx],
            "zhi_index": zhi_idx,
            "palace": PALACE_NAMES[(ming - zhi_idx) % 12],
            "level": _brightness_of(star, zhi_idx),
        })

    brightness_table = {star: dict(zip(ZHI, row))
                        for star, row in BRIGHTNESS.items()}
    brightness = {
        "levels": list(BRIGHTNESS_LEVELS),
        "table": brightness_table,
        "source": BRIGHTNESS_SOURCE,
        "unmarked_as_ping": list(BRIGHTNESS_UNMARKED),
    }

    # 大限表（按起运先后排序）
    daxian_list = []
    if forward is not None:
        for order in range(12):
            zhi = (ming + order) % 12 if forward else (ming - order) % 12
            n = (ming - zhi) % 12
            gan_idx = _gong_gan(year_gan_idx, zhi)
            start_age = ju + 10 * order
            daxian_list.append({
                "order": order + 1,
                "palace": PALACE_NAMES[n],
                "zhi": ZHI[zhi],
                "gan": GAN[gan_idx],
                "ganzhi": GAN[gan_idx] + ZHI[zhi],
                "start_age": start_age,
                "end_age": start_age + 9,
                "start_year": lunar_year + start_age - 1,
                "end_year": lunar_year + start_age + 8,
            })

    # 四化落宫
    sihua_list = []
    star_zhi = {}
    for zhi, lst in main_by_zhi.items():
        for star in lst:
            star_zhi[star] = zhi
    for zhi, lst in stars["ji"].items():
        for star in lst:
            star_zhi[star] = zhi
    missing_hua = []
    for star, hua in SIHUA[year_gan]:
        if star not in star_zhi:
            missing_hua.append(star)
            continue
        zhi = star_zhi[star]
        n = (ming - zhi) % 12
        sihua_list.append({"star": star, "hua": hua,
                           "palace": PALACE_NAMES[n], "zhi": ZHI[zhi]})

    # 大限主题标签（大限命宫 + 三方四正 + 四化，机械映射；不含吉凶）
    daxian_flow = _daxian_flow(daxian_list, palaces, hua_of_star, star_pos)

    # 格局（只做结构识别，三态输出）
    patterns = _patterns({
        "ming": ming, "shen": shen, "ziwei": ziwei, "tianfu": tianfu,
        "main_by_zhi": main_by_zhi, "sihua_list": sihua_list,
        "star_pos": star_pos, "hua_of_star": hua_of_star,
    })
    # 要点 / 局限
    summary = _summary(lunar, ming, ming_gan, ming_nayin, ju, shen, year_gan,
                       year_zhi, ziwei, tianfu, sihua_list, direction, ju, sex,
                       hour_idx)
    limits = _limits(chart, sex, missing_hua, report)

    # 断语层：summary 增补（亮度分布 + 结构识别口径说明）
    level_counts = {}
    for palace in palaces:
        for item in palace["star_brightness"]:
            level_counts[item["level"]] = level_counts.get(item["level"], 0) + 1
    summary.append("十四主星亮度分布：" + "、".join(
        "%s %d" % (lv, level_counts.get(lv, 0)) for lv in BRIGHTNESS_LEVELS) + "。")
    summary.append("断语层：亮度/三方四正/格局/大限主题均为结构识别，只描述盘面构成，"
                   "不给吉凶评分、不作事件预测。")

    delta = (shen - ming) % 12
    return {
        "version": VERSION,
        "method": METHOD,
        "lunar": dict(lunar, shichen=ZHI[hour_idx] + "时",
                      shichen_zhi=ZHI[hour_idx], shichen_index=hour_idx),
        "year_gan": year_gan,
        "year_zhi": year_zhi,
        "year_ganzhi": year_gan + year_zhi,
        "sex": sex,
        "sex_label": sex_label,
        "yin_yang": "阳年" if yang else "阴年",
        "direction": direction,
        "forward": forward,
        "start_age": ju,
        "ming_gong": {"zhi": ZHI[ming], "zhi_index": ming, "gan": ming_gan,
                      "ganzhi": ming_gan + ZHI[ming], "nayin": ming_nayin},
        "shen_gong": {"zhi": ZHI[shen], "zhi_index": shen, "gan": GAN[shen_gan_idx],
                      "ganzhi": GAN[shen_gan_idx] + ZHI[shen],
                      "palace": PALACE_NAMES[(ming - shen) % 12],
                      "offset": delta},
        "wuxing_ju": {"num": ju, "name": JU_NAME[ju],
                      "element": ming_wuxing, "nayin": ming_nayin},
        "ziwei": {"zhi": ZHI[ziwei], "zhi_index": ziwei,
                  "palace": PALACE_NAMES[(ming - ziwei) % 12]},
        "tianfu": {"zhi": ZHI[tianfu], "zhi_index": tianfu,
                   "palace": PALACE_NAMES[(ming - tianfu) % 12]},
        "ming_zhu": MING_ZHU[ZHI[ming]],
        "shen_zhu": SHEN_ZHU[year_zhi],
        "palaces": palaces,
        "daxian": daxian_list,
        "sihua": sihua_list,
        "patterns": patterns,
        "brightness": brightness,
        "main_star_brightness": main_star_brightness,
        "san_fang_si_zheng": san_fang_si_zheng,
        "daxian_flow": daxian_flow,
        "summary": summary,
        "limits": limits,
        "leap_note": lunar["leap_note"],
        "note": NOTE,
    }


def _pattern(name, level, palaces, stars, detail):
    """生成一条统一样式的格局条目：三态 + 落宫 + 涉及星曜 + 结构依据。"""
    return {"name": name, "level": level, "palaces": list(palaces),
            "stars": list(stars), "detail": detail}


def _patterns(ctx):
    """格局识别：只做可机械判定的结构条件（成/半/不成立），不作吉凶评级。

    命宫三方四正按地支索引相隔 0/4/6/8 宫展开（含命宫本身）。「成」=条件完整
    满足；「半」=部分满足（三星缺一、双星只见一、夹拱只见一边）；「不成立」=不
    满足，仍输出以便核对。判不了的强弱/破格细则不展开，写进 limits。
    """
    ming = ctx["ming"]
    shen = ctx["shen"]
    ziwei = ctx["ziwei"]
    tianfu = ctx["tianfu"]
    main_by_zhi = ctx["main_by_zhi"]
    sihua_list = ctx["sihua_list"]
    star_pos = ctx["star_pos"]
    hua_of_star = ctx["hua_of_star"]

    out = []
    ming_stars = list(main_by_zhi.get(ming, []))
    sanfang_zhi = [(ming + k) % 12 for k in (0, 4, 6, 8)]
    sanfang_stars = set()
    for zhi_idx in sanfang_zhi:
        sanfang_stars.update(main_by_zhi.get(zhi_idx, []))

    def pname(zhi_idx):
        return PALACE_NAMES[(ming - zhi_idx) % 12]

    def in_sfz(zhi_idx):
        return ((zhi_idx - ming) % 12) in (0, 4, 6, 8)

    def zhi_of(star):
        return star_pos.get(star)

    def star_of_hua(hua):
        for star, value in hua_of_star.items():
            if value == hua:
                return star
        return None

    def near_ming(star):
        """星曜是否落在命宫的左/右邻宫（夹宫）。"""
        zhi_idx = zhi_of(star)
        if zhi_idx is None:
            return False
        return ((zhi_idx - ming) % 12) in (1, 11)

    # 1. 紫府同宫
    if ziwei == tianfu:
        out.append(_pattern("紫府同宫", "成", [pname(ziwei)], ["紫微", "天府"],
                            "紫微、天府同坐%s宫，结构上为「主导＋资源」同宫组合。"
                            % ZHI[ziwei]))
    else:
        out.append(_pattern("紫府同宫", "不成立", [], ["紫微", "天府"],
                            "紫微在%s宫、天府在%s宫，两星未同宫。"
                            % (ZHI[ziwei], ZHI[tianfu])))

    # 2. 紫府朝垣：紫微、天府皆朝命宫三方四正
    hit = [pname(z) for z in (ziwei, tianfu) if in_sfz(z)]
    if len(hit) == 2:
        out.append(_pattern("紫府朝垣", "成", hit, ["紫微", "天府"],
                            "紫微、天府皆落命宫三方四正（%s）。" % "、".join(hit)))
    elif len(hit) == 1:
        out.append(_pattern("紫府朝垣", "半", hit, ["紫微", "天府"],
                            "紫微、天府仅 %s 落命宫三方四正，另一星不在。" % hit[0]))
    else:
        out.append(_pattern("紫府朝垣", "不成立", [], ["紫微", "天府"],
                            "紫微在%s宫、天府在%s宫，皆不在命宫三方四正。"
                            % (ZHI[ziwei], ZHI[tianfu])))

    # 3. 府相朝垣：天府、天相（天府顺四宫）皆朝命宫三方四正
    xiang = (tianfu + 4) % 12
    hit = [pname(z) for z in (tianfu, xiang) if in_sfz(z)]
    if len(hit) == 2:
        out.append(_pattern("府相朝垣", "成", hit, ["天府", "天相"],
                            "天府在%s、天相在%s，皆落命宫三方四正。"
                            % (ZHI[tianfu], ZHI[xiang])))
    elif len(hit) == 1:
        out.append(_pattern("府相朝垣", "半", hit, ["天府", "天相"],
                            "天府、天相仅 %s 落命宫三方四正。" % hit[0]))
    else:
        out.append(_pattern("府相朝垣", "不成立", [], ["天府", "天相"],
                            "天府在%s、天相在%s，皆不在命宫三方四正。"
                            % (ZHI[tianfu], ZHI[xiang])))

    # 4. 机月同梁：天机/太阴/天同/天梁 会命宫三方四正
    need = {"天机", "太阴", "天同", "天梁"}
    have = [s for s in MAIN_STARS if s in need and s in sanfang_stars]
    have_palaces = []
    for star in have:
        zhi_idx = zhi_of(star)
        if zhi_idx is not None and pname(zhi_idx) not in have_palaces:
            have_palaces.append(pname(zhi_idx))
    if len(have) == 4:
        out.append(_pattern("机月同梁", "成", have_palaces, have,
                            "天机、太阴、天同、天梁四星皆会命宫三方四正。"))
    elif len(have) == 3:
        out.append(_pattern("机月同梁", "半", have_palaces, have,
                            "机月同梁只见三星（%s）。" % "、".join(have)))
    else:
        out.append(_pattern("机月同梁", "不成立", have_palaces, have,
                            "命宫三方四正仅见机月同梁中的 %d 星。" % len(have)))

    # 5. 日月同宫：太阳、太阴同宫
    sun_z, moon_z = zhi_of("太阳"), zhi_of("太阴")
    if sun_z is not None and sun_z == moon_z:
        level = "成" if in_sfz(sun_z) else "半"
        detail = ("太阳、太阴同坐%s宫%s。"
                  % (ZHI[sun_z], "且落命宫三方四正" if in_sfz(sun_z)
                     else "，但不在命宫三方四正"))
        out.append(_pattern("日月同宫", level, [pname(sun_z)], ["太阳", "太阴"], detail))
    else:
        out.append(_pattern("日月同宫", "不成立", [], ["太阳", "太阴"],
                            "太阳在%s宫、太阴在%s宫，未同宫。"
                            % (ZHI[sun_z] if sun_z is not None else "?",
                               ZHI[moon_z] if moon_z is not None else "?")))

    # 6. 日月反背：太阳、太阴皆落陷
    sun_lv = _brightness_of("太阳", sun_z) if sun_z is not None else ""
    moon_lv = _brightness_of("太阴", moon_z) if moon_z is not None else ""
    down = (sun_lv == "陷") + (moon_lv == "陷")
    if down == 2:
        out.append(_pattern("日月反背", "成", [pname(sun_z), pname(moon_z)],
                            ["太阳", "太阴"],
                            "太阳在%s（%s）、太阴在%s（%s），两星皆陷，属日月反背结构。"
                            % (ZHI[sun_z], sun_lv, ZHI[moon_z], moon_lv)))
    elif down == 1:
        out.append(_pattern("日月反背", "半", [], ["太阳", "太阴"],
                            "太阳（%s）、太阴（%s）仅一星落陷。" % (sun_lv, moon_lv)))
    else:
        out.append(_pattern("日月反背", "不成立", [], ["太阳", "太阴"],
                            "太阳（%s）、太阴（%s）皆未落陷。" % (sun_lv, moon_lv)))

    # 7. 杀破狼：七杀/破军/贪狼 会命宫三方四正
    need = ["七杀", "破军", "贪狼"]
    have = [s for s in need if s in sanfang_stars]
    have_palaces = []
    for star in have:
        zhi_idx = zhi_of(star)
        if zhi_idx is not None and pname(zhi_idx) not in have_palaces:
            have_palaces.append(pname(zhi_idx))
    if len(have) == 3:
        out.append(_pattern("杀破狼", "成", have_palaces, have,
                            "七杀、破军、贪狼三星皆会命宫三方四正。"))
    elif len(have) == 2:
        out.append(_pattern("杀破狼", "半", have_palaces, have,
                            "杀破狼只见两星（%s）。" % "、".join(have)))
    else:
        out.append(_pattern("杀破狼", "不成立", have_palaces, have,
                            "命宫三方四正仅见杀破狼中的 %d 星。" % len(have)))

    # 8. 命无正曜
    if ming_stars:
        out.append(_pattern("命无正曜", "不成立", [PALACE_NAMES[0]], [],
                            "命宫有主星（%s），非空宫。" % "、".join(ming_stars)))
    else:
        out.append(_pattern("命无正曜", "成", [PALACE_NAMES[0]], [],
                            "命宫无十四主星，需借对宫（迁移宫）主星参看。"))

    # 9. 刑囚夹印：天相坐命，擎羊/陀罗与廉贞分夹命宫两邻
    xing = [s for s in ("擎羊", "陀罗") if near_ming(s)]
    qiu = near_ming("廉贞")
    if xiang != ming:
        out.append(_pattern("刑囚夹印", "不成立", [],
                            ["天相", "廉贞", "擎羊", "陀罗"],
                            "天相在%s宫，未坐命宫（命宫在%s），无「夹印」结构。"
                            % (ZHI[xiang], ZHI[ming])))
    elif xing and qiu:
        out.append(_pattern("刑囚夹印", "成",
                            [pname((ming + 11) % 12), pname((ming + 1) % 12)],
                            ["天相"] + xing + ["廉贞"],
                            "天相坐命%s宫，邻宫见%s与廉贞，构成刑囚夹印。"
                            % (ZHI[ming], "、".join(xing))))
    elif xing or qiu:
        out.append(_pattern("刑囚夹印", "半", [], ["天相"] + xing + ["廉贞"],
                            "天相坐命，但邻宫只见到%s，夹拱不完整。"
                            % ("、".join(xing + (["廉贞"] if qiu else [])))))
    else:
        out.append(_pattern("刑囚夹印", "不成立", [], ["天相", "廉贞", "擎羊", "陀罗"],
                            "天相坐命，但命宫两邻宫无擎羊/陀罗与廉贞，未成夹印。"))

    # 10. 羊陀夹忌：化忌星落禄存宫（被擎羊、陀罗左右夹）
    ji_star = star_of_hua("忌")
    ji_z = zhi_of(ji_star) if ji_star else None
    lu_z = zhi_of("禄存")
    yang_z, tuo_z = zhi_of("擎羊"), zhi_of("陀罗")
    if ji_z is None or lu_z is None:
        out.append(_pattern("羊陀夹忌", "不成立", [], [ji_star or "化忌星", "禄存"],
                            "化忌星或禄存未定位，无法判定。"))
    elif ji_z == lu_z:
        out.append(_pattern("羊陀夹忌", "成", [pname(ji_z)],
                            [ji_star, "擎羊", "陀罗", "禄存"],
                            "化忌星%s与禄存同在%s宫，被擎羊（%s）、陀罗（%s）左右夹。"
                            % (ji_star, ZHI[lu_z], ZHI[yang_z], ZHI[tuo_z])))
    elif ji_z in (yang_z, tuo_z):
        out.append(_pattern("羊陀夹忌", "半", [pname(ji_z)],
                            [ji_star, "擎羊", "陀罗", "禄存"],
                            "化忌星%s与擎羊/陀罗同宫于%s，但未落禄存宫（%s）。"
                            % (ji_star, ZHI[ji_z], ZHI[lu_z])))
    else:
        out.append(_pattern("羊陀夹忌", "不成立", [pname(ji_z)],
                            [ji_star, "擎羊", "陀罗", "禄存"],
                            "化忌星%s在%s宫，既不落禄存宫（%s）也未与羊陀同宫。"
                            % (ji_star, ZHI[ji_z], ZHI[lu_z])))

    # 11. 火铃夹命：火星、铃星分夹命宫两邻
    huo, ling = near_ming("火星"), near_ming("铃星")
    if huo and ling:
        out.append(_pattern("火铃夹命", "成", [pname(ming)], ["火星", "铃星"],
                            "火星、铃星分居命宫两邻宫，构成火铃夹命。"))
    elif huo or ling:
        out.append(_pattern("火铃夹命", "半", [pname(ming)], ["火星", "铃星"],
                            "命宫邻宫只见%s，另一星不在。" % ("火星" if huo else "铃星")))
    else:
        out.append(_pattern("火铃夹命", "不成立", [pname(ming)], ["火星", "铃星"],
                            "命宫两邻宫无火星、铃星，未成夹命。"))

    # 12. 禄马交驰：禄存与天马同宫/同会命宫三方四正
    ma_z = zhi_of("天马")
    if lu_z is not None and ma_z is not None and lu_z == ma_z:
        out.append(_pattern("禄马交驰", "成", [pname(lu_z)], ["禄存", "天马"],
                            "禄存与天马同坐%s宫，属禄马交驰结构。" % ZHI[lu_z]))
    elif lu_z is not None and ma_z is not None and in_sfz(lu_z) and in_sfz(ma_z):
        out.append(_pattern("禄马交驰", "半", [pname(lu_z), pname(ma_z)], ["禄存", "天马"],
                            "禄存在%s、天马在%s，皆落命宫三方四正但未同宫。"
                            % (ZHI[lu_z], ZHI[ma_z])))
    else:
        out.append(_pattern("禄马交驰", "不成立", [], ["禄存", "天马"],
                            "禄存在%s、天马在%s，未同宫也未同会命宫三方四正。"
                            % (ZHI[lu_z] if lu_z is not None else "?",
                               ZHI[ma_z] if ma_z is not None else "?")))

    # 13. 双禄交流：化禄星与禄存同宫/同会命宫三方四正
    hua_lu_star = star_of_hua("禄")
    hl_z = zhi_of(hua_lu_star) if hua_lu_star else None
    if hl_z is not None and lu_z is not None and hl_z == lu_z:
        out.append(_pattern("双禄交流", "成", [pname(hl_z)],
                            [hua_lu_star, "禄存"],
                            "化禄星%s与禄存同坐%s宫，构成双禄交流。" % (hua_lu_star, ZHI[hl_z])))
    elif hl_z is not None and lu_z is not None and in_sfz(hl_z) and in_sfz(lu_z):
        out.append(_pattern("双禄交流", "半", [pname(hl_z), pname(lu_z)],
                            [hua_lu_star, "禄存"],
                            "化禄星%s在%s、禄存在%s，皆落命宫三方四正但未同宫。"
                            % (hua_lu_star, ZHI[hl_z], ZHI[lu_z])))
    else:
        out.append(_pattern("双禄交流", "不成立", [], [hua_lu_star or "化禄星", "禄存"],
                            "化禄星%s在%s、禄存在%s，未同宫也未同会命宫三方四正。"
                            % (hua_lu_star, ZHI[hl_z] if hl_z is not None else "?",
                               ZHI[lu_z] if lu_z is not None else "?")))

    # 以下为 v1 就有的描述性标签：实际成立时才输出（level 固定为「成」）
    if "紫微" in ming_stars:
        out.append(_pattern("紫微守命", "成", ["命宫"], ["紫微"],
                            "紫微坐命宫，结构上重主导与体面，需辅曜配合。"))
    if not ming_stars:
        out.append(_pattern("命宫无主星", "成", ["命宫"], [],
                            "命宫空宫，需借对宫（迁移宫）主星参看，方向更受环境牵引。"))
    if shen == ming:
        out.append(_pattern("身命同宫", "成", ["命宫"], [],
                            "身宫与命宫同宫，主观意志与人生落实方向一致。"))
    cai_zhi = (ming - 4) % 12  # 财帛宫
    if "武曲" in main_by_zhi.get(cai_zhi, []):
        out.append(_pattern("武曲守财", "成", ["财帛宫"], ["武曲"],
                            "武曲坐财帛宫，结构上重实际与现金流。"))
    for item in sihua_list:
        if item["palace"] == "命宫":
            out.append(_pattern("化%s入命" % item["hua"], "成", ["命宫"],
                                [item["star"]],
                                "%s化%s坐命宫，为该盘显性结构主题之一。"
                                % (item["star"], item["hua"])))
    return out


def _daxian_flow(daxian_list, palaces, hua_of_star, star_pos):
    """十二大限的结构主题标签（不含吉凶、不给事件预测）。

    themes 由四层机械映射叠加：大限命宫所落本命宫位的主题 → 大限命宫主星主题 →
    大限命宫三方四正的星系结构（杀破狼/机月同梁/昌曲）→ 三方四正所落四化。
    confidence 只反映盘面信息完整度（大限命宫与三方四正的主星数量），不代表吉凶。
    """
    if not daxian_list:
        return []
    ming_zhi = palaces[0]["zhi_index"]
    by_zhi = {palace["zhi_index"]: palace for palace in palaces}
    out = []
    for decade in daxian_list:
        zhi = ZHI.index(decade["zhi"])
        n = (ming_zhi - zhi) % 12
        sf_zhi = [(zhi + k) % 12 for k in (0, 4, 6, 8)]
        ming_main = list(by_zhi[zhi].get("main_stars", []))
        sf_main = []
        for zhi_idx in sf_zhi:
            for star in by_zhi[zhi_idx].get("main_stars", []):
                if star not in sf_main:
                    sf_main.append(star)
        ji_stars = []
        for zhi_idx in sf_zhi:
            ji_stars.extend(by_zhi[zhi_idx].get("ji_stars", []))
        themes = []

        def add(theme):
            if theme in THEME_TAGS and theme not in themes:
                themes.append(theme)

        for theme in PALACE_THEMES.get(PALACE_NAMES[n], []):
            add(theme)
        for star in ming_main:
            for theme in STAR_THEME_TAGS.get(star, []):
                add(theme)
        if {"七杀", "破军", "贪狼"} <= set(sf_main):
            add("事业")
            add("迁移")
        if {"天机", "太阴", "天同", "天梁"} <= set(sf_main):
            add("学业")
        if "文昌" in ji_stars or "文曲" in ji_stars:
            add("学业")
        sihua_here = []
        for star, hua in hua_of_star.items():
            zhi_idx = star_pos.get(star)
            if zhi_idx is None or ((zhi_idx - zhi) % 12) not in (0, 4, 6, 8):
                continue
            sihua_here.append({"star": star, "hua": hua})
            add(HUA_THEME_TAGS[hua])

        sf_other_main = sum(1 for z in sf_zhi[1:] if by_zhi[z].get("main_stars"))
        if ming_main and sf_other_main >= 2:
            confidence = "高"
        elif ming_main or sf_other_main >= 2:
            confidence = "中"
        else:
            confidence = "低"

        parts = ["大限命宫落本命 %s（%s）" % (PALACE_NAMES[n], decade["ganzhi"]),
                 "主星%s" % ("、".join(ming_main) if ming_main else "空宫"),
                 "三方四正主星%s" % ("、".join(sf_main) if sf_main else "无")]
        if sihua_here:
            parts.append("四化见" + "、".join("%s化%s" % (x["star"], x["hua"])
                                             for x in sihua_here))
        out.append({
            "order": decade["order"],
            "palace": decade["palace"],
            "zhi": decade["zhi"],
            "ganzhi": decade["ganzhi"],
            "start_age": decade["start_age"],
            "end_age": decade["end_age"],
            "start_year": decade["start_year"],
            "end_year": decade["end_year"],
            "themes": themes[:4],
            "confidence": confidence,
            "stars": {"ming": ming_main, "san_fang_si_zheng": sf_main},
            "sihua": sihua_here,
            "basis": "；".join(parts) + "。",
        })
    return out


def _summary(lunar, ming, ming_gan, ming_nayin, ju, shen, year_gan, year_zhi,
             ziwei, tianfu, sihua_list, direction, start_age, sex, hour_idx):
    """要点摘要（纯事实陈述，由结构直接推出）。"""
    items = []
    items.append("农历 %d 年 %d 月 %d 日 %s时（农历年干支 %s%s，属%s）。"
                 % (lunar["lunar_year"], lunar["month"], lunar["day"],
                    ZHI[hour_idx], year_gan, year_zhi,
                    "阳年" if GAN.index(year_gan) % 2 == 0 else "阴年"))
    items.append("命宫在%s（宫干%s，纳音%s → %s）；身宫在%s（自命宫顺数 %d 宫）。"
                 % (ZHI[ming], ming_gan, ming_nayin, JU_NAME[ju],
                    PALACE_NAMES[(ming - shen) % 12], (shen - ming) % 12))
    items.append("紫微在%s宫、天府在%s宫；命主%s、身主%s。"
                 % (ZHI[ziwei], ZHI[tianfu], MING_ZHU[ZHI[ming]], SHEN_ZHU[year_zhi]))
    if direction:
        items.append("大限%s（%s%s），%d 虚岁起运，每宫十年。"
                     % (direction, "阳" if GAN.index(year_gan) % 2 == 0 else "阴",
                        {1: "男", 0: "女"}.get(sex, ""), start_age))
    else:
        items.append("未提供性别，无法判定大限顺逆与起运宫，故未排大限。")
    if sihua_list:
        items.append("年干%s四化：%s。" % (
            year_gan, "；".join("%s化%s（%s）" % (i["star"], i["hua"], i["palace"])
                               for i in sihua_list)))
    return items


def _limits(chart, sex, missing_hua, report):
    """已知不确定点：全部写明，不静默假设。"""
    limits = []
    if sex is None:
        limits.append("未提供性别：大限方向（阳男阴女顺行、阴男阳女逆行）依赖性别，"
                      "本层未排大限；请补充性别后重排。")
    if chart.get("time_pillar_reliable") is False or (report.get("input") or {}).get("time_unknown"):
        limits.append("出生时辰未知：命宫、身宫、时系星曜（文昌文曲、地空地劫、火星铃星）"
                      "与大限全部随时辰移动，本盘按假定时辰排出，只可作结构示范。")
    hour = (chart.get("input") or {}).get("hour")
    if hour == 23:
        limits.append("晚子时（23:00–23:59）：本层沿用排盘采用时间即当日农历日（「晚子时算当日」，"
                      "与 iztro 默认 dayDivide=current 一致）；另有「晚子时算次日」流派，"
                      "会影响紫微/天府与全部主星位置。")
    solar_used = str(chart.get("solar") or "")[:10]
    solar_disp = str(chart.get("solar_display") or "")[:10]
    if solar_used and solar_disp and solar_used != solar_disp:
        limits.append("农历日期取「标准时」显示（%s），时支取「排盘采用时间」（%s）："
                      "真太阳时跨日时两者不同源，紫微的日数需人工复核。"
                      % (solar_disp, solar_used))
    if missing_hua:
        limits.append("年干四化中的 %s 未在本盘找到落宫，已跳过（请核对安星）。"
                      % "、".join(missing_hua))
    limits.append("四化用通行表（甲廉破武阳…癸破巨阴贪）；庚干化科有「天府／太阴」两说"
                  "（本层取天府）、壬干化科有「左辅／天梁」两说（本层取左辅），"
                  "与 iztro 等实现的取法可能不同。")
    limits.append("命主/身主取通行表；流年/流月/小限、四化飞星、星曜互涉与吉凶评断不在本层范围；"
                  "已实现的断语层（亮度/三方四正/格局/大限主题）只做结构识别。")
    limits.append("庙旺利陷取《紫微斗数全书》卷二「一命宫」十四主星宫支文字表，"
                  "归并为庙/旺/得地/利/平/不/陷七级；原书未标的 9 格（紫微子卯酉、"
                  "天府子午、天梁巳亥、破军巳亥）本层按「平」处理，不臆造庙旺。"
                  "亮度是结构标签，不等于吉凶；他派六级/七级表可能不同。")
    limits.append("三方四正只按「三合宫（相隔四宫/八宫）＋对宫（相隔六宫）」机械展开，"
                  "未做夹宫、借星、流曜、破格等进阶判读。")
    limits.append("格局只回答「结构条件是否满足」（成/半/不成立），同一格局在各派另有"
                  "强弱、破格、同宫/会照/夹拱等细则，本层只取可机械判定的单一口径。")
    limits.append("大限主题由大限命宫宫位名、主星、三方四正、四化机械映射，"
                  "confidence 只反映盘面信息完整度，不代表吉凶或事件概率。")
    limits.append("闰月按「≤15 日算本月、>15 日算下月」；部分流派「闰月整月算本月」或「整月算下月」，"
                  "结果会差一个月的安星。")
    return limits


# ---------------------------------------------------------------- 渲染

def _width(text):
    """等宽显示宽度：中日韩全角字符按 2 计。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
               for ch in str(text))


def _pad(text, width):
    text = str(text)
    return text + " " * max(0, width - _width(text))


def _stars_cell(lst):
    return "、".join(lst) if lst else "—"


def render_ziwei_text(z):
    """把 chart_ziwei() 的 dict 渲染为技术版中文文本。"""
    if not isinstance(z, dict) or "palaces" not in z:
        raise ValueError("render_ziwei_text 需要 chart_ziwei() 返回的 dict")

    lun = z.get("lunar") or {}
    mg = z.get("ming_gong") or {}
    sg = z.get("shen_gong") or {}
    ju = z.get("wuxing_ju") or {}
    lines = []

    lines.append("紫微斗数层（%s）｜三合派安星法" % z.get("version", VERSION))
    lunar_text = lun.get("text") or ("%s年%s月%s日"
                                     % (lun.get("lunar_year"), lun.get("month"),
                                        lun.get("day")))
    lines.append("农历：%s %s（%s）"
                 % (lunar_text, lun.get("shichen", ""), z.get("sex_label", "未提供")))
    lines.append("年干支：%s（%s）　命宫：%s（%s，纳音%s → %s）"
                 % (z.get("year_ganzhi", "?"), z.get("yin_yang", "?"),
                    mg.get("zhi", "?"), mg.get("ganzhi", "?"),
                    mg.get("nayin", "?"), ju.get("name", "?")))
    lines.append("身宫：%s　紫微：%s宫　天府：%s宫　命主：%s　身主：%s"
                 % (sg.get("palace", "?"), (z.get("ziwei") or {}).get("zhi", "?"),
                    (z.get("tianfu") or {}).get("zhi", "?"),
                    z.get("ming_zhu", "?"), z.get("shen_zhu", "?")))
    if z.get("direction"):
        lines.append("大限：%s%s，%d 虚岁起运（%s）"
                     % (z.get("yin_yang", ""), z["direction"], z.get("start_age", 0),
                        z.get("sex_label", "")))
    else:
        lines.append("大限：未提供性别，未排大限")
    if z.get("leap_note"):
        lines.append("闰月说明：%s" % z["leap_note"])

    if z.get("summary"):
        lines.append("")
        lines.append("【要点】")
        for item in z["summary"]:
            lines.append("· %s" % item)

    lines.append("")
    lines.append("【十二宫】")
    widths = (8, 8, 18, 14, 14, 12)
    header = ("宫名", "宫干支", "主星", "六吉", "六煞", "四化")
    lines.append("".join(_pad(h, w) for h, w in zip(header, widths)).rstrip())
    lines.append("─" * 60)
    for p in z["palaces"]:
        sihua = "、".join("%s化%s" % (i["star"], i["hua"]) for i in p.get("sihua") or [])
        cells = (p.get("name", "?"), p.get("gong_ganzhi", "?"),
                 _stars_cell(p.get("main_stars") or []),
                 _stars_cell(p.get("ji_stars") or []),
                 _stars_cell(p.get("sha_stars") or []),
                 sihua or "—")
        line = "".join(_pad(c, w) for c, w in zip(cells, widths)).rstrip()
        marks = []
        if p.get("is_ming"):
            marks.append("命")
        if p.get("is_shen"):
            marks.append("身")
        if marks:
            line += "　← " + "/".join(marks) + "宫"
        lines.append(line)

    if z.get("main_star_brightness"):
        lines.append("")
        lines.append("【主星亮度】（庙旺利陷为结构标签，非吉凶评分）")
        for item in z["main_star_brightness"]:
            lines.append("  %s　%s宫（%s）%s"
                         % (_pad(item["star"], 4), item["zhi"],
                            item["palace"], item["level"]))

    if z.get("san_fang_si_zheng"):
        lines.append("")
        lines.append("【三方四正】（三合宫＋对宫，机械展开）")
        for item in z["san_fang_si_zheng"]:
            sf = "、".join("%s（%s）" % (x["name"], x["zhi"]) for x in item["san_fang"])
            lines.append("  %s（%s）：三方 %s；对宫 %s（%s）"
                         % (_pad(item["palace"], 6), item["zhi"], sf,
                            item["dui_gong"]["name"], item["dui_gong"]["zhi"]))

    if z.get("sihua"):
        lines.append("")
        lines.append("【年干四化】")
        lines.append("　".join("%s化%s → %s（%s）"
                               % (i["star"], i["hua"], i["palace"], i["zhi"])
                               for i in z["sihua"]))

    lines.append("")
    lines.append("【大限】（虚岁；每限十年）")
    if z.get("daxian"):
        for d in z["daxian"]:
            lines.append("  第 %2d 限　%2d–%2d 岁　%4d–%4d　%s（%s）"
                         % (d["order"], d["start_age"], d["end_age"],
                            d["start_year"], d["end_year"],
                            d["palace"], d["ganzhi"]))
    else:
        lines.append("  （未提供性别，大限方向无法确定，故未排。）")

    lines.append("")
    lines.append("【大限主题】（结构主题标签，不含吉凶）")
    if z.get("daxian_flow"):
        for item in z["daxian_flow"]:
            themes = "、".join(item["themes"]) if item["themes"] else "（无）"
            lines.append("  第 %2d 限　%2d–%2d 岁　%s：%s｜可信度 %s"
                         % (item["order"], item["start_age"], item["end_age"],
                            item["palace"], themes, item["confidence"]))
    else:
        lines.append("  （未提供性别，大限主题无法确定。）")

    if z.get("patterns"):
        lines.append("")
        lines.append("【格局与结构】（成/半/不成立均为结构条件判定）")
        for item in z["patterns"]:
            level = item.get("level")
            if level:
                lines.append("· %s（%s）：%s" % (item["name"], level, item["detail"]))
            else:
                lines.append("· %s：%s" % (item["name"], item["detail"]))

    if z.get("limits"):
        lines.append("")
        lines.append("【说明与局限】")
        for item in z["limits"]:
            lines.append("· %s" % item)

    if z.get("note"):
        lines.append("")
        lines.append(z["note"])

    return "\n".join(lines)
