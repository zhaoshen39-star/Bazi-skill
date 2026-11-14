"""风水适配层：命理侧适配 + 八宅/玄空宅盘（纯规则，可验算）。

设计边界（重要）：
- **可算部分**：命卦（生年+性别）、八宅游年（命卦定吉凶八方）、
  玄空飞星（元运+坐向的下卦盘）、八字用神 → 方位/颜色/楼层尾数/房间适配。
- **不在此模块**：外部峦头（路冲、水口、邻楼）、实地罗盘度数与磁偏、
  装修尺寸与户型比例——这些必须现场勘察，本模块只输出「结构+适配建议」。
- 只描述结构与倾向，不做「必发财/必出灾」式断言；所有条目都在 limits 里声明口径。

输入约定：
- build_fengshui(report, sit=None)
  - report：bazi.py 的 report（读农历年、性别、analysis.yong_shen）
  - sit：坐山，可为二十四山名（"子"/"子山午向"）或度数（"0"/"172.5"）；
         不给则只输出命理侧通用适配（命卦/八宅/用神落地建议）。
"""
from __future__ import annotations

import datetime as _dt
import re

VERSION = "1.0.0"

# ---------------------------------------------------------------- 基础表

# 后天八卦：卦 -> (方位, 五行, 洛书数, 颜色, 常见用途)
GUA_INFO = {
    "乾": ("西北", "金", 6, "白、银、金", "长辈位、办公桌、金属摆件"),
    "坎": ("北", "水", 1, "黑、蓝、灰", "卧室、书桌、水景"),
    "艮": ("东北", "土", 8, "黄、棕、米", "书房、储物、静坐"),
    "震": ("东", "木", 3, "青、绿", "书桌、绿植、学习区"),
    "巽": ("东南", "木", 4, "青、绿", "书桌、财位、通风"),
    "离": ("南", "火", 9, "红、紫、橙", "客厅、照明、展示"),
    "坤": ("西南", "土", 2, "黄、棕、米", "卧室、厨房"),
    "兑": ("西", "金", 7, "白、银、金", "子女房、金属、音响"),
}

# 后天八卦排行顺序（八宅游年歌按此顺时针排布，从命卦起）
GUA_ROUND = ["乾", "坎", "艮", "震", "巽", "离", "坤", "兑"]

# 大游年歌：命卦 -> 顺时针从命卦之后开始的 7 个卦位所配星
# 生=生气 天=天医 延=延年 绝=绝命 五=五鬼 六=六煞 祸=祸害；命卦本身为伏位
YUNIAN_SONG = {
    "乾": "六天五祸绝延生",
    "坎": "五天生延绝祸六",
    "艮": "六绝祸生延天五",
    "震": "延生祸绝五天六",
    "巽": "天五六祸生绝延",
    "离": "六五绝延祸生天",
    "坤": "天延绝生祸五六",
    "兑": "生祸延绝六五天",
}

STAR_CHAR = {"生": "生气", "天": "天医", "延": "延年", "绝": "绝命",
             "五": "五鬼", "六": "六煞", "祸": "祸害"}
GOOD_STARS = ("生气", "天医", "延年", "伏位")
BAD_STARS = ("绝命", "五鬼", "六煞", "祸害")

# 命卦：卦名（洛书数）—— 男五寄坤、女五寄艮
MING_GUA_NUM = {1: "坎", 2: "坤", 3: "震", 4: "巽", 5: "中", 6: "乾", 7: "兑", 8: "艮", 9: "离"}
EAST_GUA = ("坎", "震", "巽", "离")   # 东四命
WEST_GUA = ("坤", "兑", "乾", "艮")   # 西四命

# 二十四山：(山名, 起始度数, 元龙, 阴阳, 所在宫)
SHAN_TABLE = [
    ("子", 352.5, "天元", "阴", "坎"),
    ("癸", 7.5, "人元", "阴", "坎"),
    ("丑", 22.5, "地元", "阴", "艮"),
    ("艮", 37.5, "天元", "阳", "艮"),
    ("寅", 52.5, "人元", "阳", "艮"),
    ("甲", 67.5, "地元", "阳", "震"),
    ("卯", 82.5, "天元", "阴", "震"),
    ("乙", 97.5, "人元", "阴", "震"),
    ("辰", 112.5, "地元", "阴", "巽"),
    ("巽", 127.5, "天元", "阳", "巽"),
    ("巳", 142.5, "人元", "阳", "巽"),
    ("丙", 157.5, "地元", "阳", "离"),
    ("午", 172.5, "天元", "阴", "离"),
    ("丁", 187.5, "人元", "阴", "离"),
    ("未", 202.5, "地元", "阴", "坤"),
    ("坤", 217.5, "天元", "阳", "坤"),
    ("申", 232.5, "人元", "阳", "坤"),
    ("庚", 247.5, "地元", "阳", "兑"),
    ("酉", 262.5, "天元", "阴", "兑"),
    ("辛", 277.5, "人元", "阴", "兑"),
    ("戌", 292.5, "地元", "阴", "乾"),
    ("乾", 307.5, "天元", "阳", "乾"),
    ("亥", 322.5, "人元", "阳", "乾"),
    ("壬", 337.5, "地元", "阳", "坎"),
]
SHAN = {row[0]: {"start": row[1], "yuan": row[2], "yin_yang": row[3], "palace": row[4]}
        for row in SHAN_TABLE}
SHAN_NAMES = [row[0] for row in SHAN_TABLE]

# 九宫格在纸面上的位置（上排：巽 离 坤 / 中排：震 中 兑 / 下排：艮 坎 乾）
PALACE_GRID = [["巽", "离", "坤"], ["震", "中", "兑"], ["艮", "坎", "乾"]]
# 洛书飞序：中 → 乾 → 兑 → 艮 → 离 → 坎 → 坤 → 震 → 巽
FLY_ORDER = ["中", "乾", "兑", "艮", "离", "坎", "坤", "震", "巽"]

# 九运（2024–2043）为当前元运；其余运按 20 年一运
YUN_RANGES = [
    (1, 1864, 1883), (2, 1884, 1903), (3, 1904, 1923),
    (4, 1924, 1943), (5, 1944, 1963), (6, 1964, 1983),
    (7, 1984, 2003), (8, 2004, 2023), (9, 2024, 2043),
]

# 五行 → (方位, 颜色, 楼层尾数, 材质/元素, 适配房间, 忌)
ELEMENT_HOME = {
    "水": ("北", "黑、蓝、灰", "1、6", "水景、鱼缸、玻璃、蓝灰布艺",
           "卧室、书房（北侧）", "忌过度暖色与南向密闭小间"),
    "金": ("西、西北", "白、银、金属色", "4、9", "金属摆件、圆角家具、白色饰面",
           "书房、办公位（西/西北）", "忌过多明火与红色堆叠"),
    "木": ("东、东南", "青、绿", "3、8", "绿植、木饰面、棉麻",
           "书桌、学习区（东/东南）", "忌金属尖锐物过多压东方"),
    "火": ("南", "红、紫、橙", "2、7", "暖光、红紫布艺、灯饰",
           "客厅、照明主区（南）", "忌夏季高温与南向暴晒久坐"),
    "土": ("东北、西南、中", "黄、棕、米", "5、0", "陶土、石材、黄棕布艺",
           "书房、储物、静处（东北/西南）", "忌潮气与积水滞留"),
}

# 河图数 → 五行（楼层尾数推断）
FLOOR_ELEMENT = {1: "水", 6: "水", 2: "火", 7: "火", 3: "木", 8: "木",
                 4: "金", 9: "金", 5: "土", 0: "土"}

LIMITS = [
    "风水层只做「可算推演」：命卦、八宅游年、玄空飞星（下卦）、用神适配；"
    "不含外部峦头、实地罗盘磁偏、户型尺寸。",
    "八宅按《八宅明镜》大游年歌（东四命/西四命、八方吉凶），"
    "宅盘按坐山定宅卦，宅命相配只作结构参考。",
    "玄空飞星按三元九运下卦排盘（阳顺阴逆），运星与山/向星同盘呈现；"
    "不排替卦（坐向落在每山 3° 边界时会提示，实际以罗盘复测为准）。",
    "现实里的风水要现场看：外部形势、门路气口、楼层环境、装修尺寸均未纳入；"
    "本层结论是「结构倾向与适配建议」，不是吉凶断言。",
    "楼层尾数、颜色、方位属民俗推演，不构成健康/投资/婚姻建议。",
]

MODEL = ("风水层：命卦（生年+性别）→ 八宅游年；坐向 → 玄空飞星（下卦）；"
         "八字用神 → 方位/颜色/楼层/房间适配")


# ---------------------------------------------------------------- 工具

def _norm_deg(deg: float) -> float:
    deg = float(deg) % 360.0
    return deg


def shan_of_degree(deg: float) -> str:
    """度数 → 二十四山：以每山 15° 为界，向上取（0° 落在子山中央）。"""
    deg = _norm_deg(deg)
    # 子山中心在 0°，起点 352.5°
    shifted = (deg + 7.5) % 360.0
    idx = int(shifted // 15)  # 0..23，自 子 起顺时针
    return _shan_by_index(idx)


def _shan_by_index(idx: int) -> str:
    # SHAN_TABLE 以 子（352.5°）为首、顺时针排列，idx=0 即 子；直接复用同一份名单，
    # 避免「硬编码 order 与 SHAN_NAMES 双真相源」漂移。
    return SHAN_NAMES[idx % 24]


def shan_center_deg(name: str) -> float:
    row = SHAN[name]
    start = row["start"]
    # 每个山跨 15°，中心 = 起点 + 7.5°（子山起点 352.5 → 中心 0）
    return _norm_deg(start + 7.5)


def parse_sit(sit) -> dict:
    """解析坐山输入：二十四山名、'X山Y向' 文本、或度数。

    返回 {shan, deg, facing_shan, facing_deg, warning}
    """
    if sit is None:
        return {}
    raw = str(sit).strip()
    if not raw:
        return {}
    # 1) 度数
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*(?:°|度)?", raw)
    if m:
        deg = _norm_deg(float(m.group(1)))
        shan = shan_of_degree(deg)
        center = shan_center_deg(shan)
        off = abs(((deg - center + 180) % 360) - 180)
        warning = None
        if off > 4.5:  # 每山 15°，中心 ±7.5°；距中心 >4.5° 即贴近山界的 3° 替卦区
            warning = ("坐向 %.1f° 距 %s 山中心 %.1f°，已进入山界 3° 内的替卦区；"
                       "本模块只按下卦排盘，实际以罗盘复测为准。" % (deg, shan, off))
        return {"shan": shan, "deg": deg,
                "facing_shan": _opposite_shan(shan),
                "facing_deg": _norm_deg(deg + 180), "warning": warning}
    # 2) "子山午向" 形式
    m = re.fullmatch(r"([\u4e00-\u9fff])\s*山\s*([\u4e00-\u9fff])\s*向", raw)
    if m:
        sit_shan, face_shan = m.group(1), m.group(2)
        for s in (sit_shan, face_shan):
            if s not in SHAN:
                raise SystemExit("坐向里的「%s」不是二十四山之一（子癸丑艮寅甲卯乙辰巽巳丙午丁未坤申庚酉辛戌乾亥壬）" % s)
        deg = shan_center_deg(sit_shan)
        return {"shan": sit_shan, "deg": deg, "facing_shan": face_shan,
                "facing_deg": shan_center_deg(face_shan), "warning": None}
    # 3) 单个山名（只给坐山）
    if raw in SHAN:
        return {"shan": raw, "deg": shan_center_deg(raw),
                "facing_shan": _opposite_shan(raw),
                "facing_deg": shan_center_deg(_opposite_shan(raw)), "warning": None}
    raise SystemExit("无法解析坐向「%s」：可用二十四山名（如 子）、"
                     "「子山午向」，或度数（如 0 / 172.5）" % raw)


def _opposite_shan(shan: str) -> str:
    """坐山对面 180° 的山。"""
    return shan_of_degree(shan_center_deg(shan) + 180)


def ming_gua(year: int, sex) -> dict:
    """命卦：生年（以立春为界，调用方传入农历年）与性别 → 卦。

    男：(100 − 年后两位) ÷ 9 取余；女：(年后两位 − 4) ÷ 9 取余。
    余 0 按 9；余 5 时男寄坤、女寄艮。
    """
    if sex not in (1, 0, "1", "0", "male", "female", "m", "f", "男", "女"):
        raise SystemExit("算命卦需要性别：--sex male 或 female")
    is_male = str(sex).lower() in ("1", "male", "m", "男")
    y = int(year) % 100
    if is_male:
        num = (100 - y) % 9
    else:
        num = (y - 4) % 9
    if num == 0:
        num = 9
    gua = MING_GUA_NUM[num]
    if gua == "中":
        gua = "坤" if is_male else "艮"
    kind = "东四命" if gua in EAST_GUA else "西四命"
    return {"sex": "男" if is_male else "女", "year": int(year),
            "number": num, "gua": gua, "type": kind,
            "direction": GUA_INFO[gua][0], "element": GUA_INFO[gua][1]}


def zhai_pan(gua: str, zhai_gua: str | None = None) -> dict:
    """八宅游年盘：命卦 → 八方星（伏位/生气/天医/延年/绝命/五鬼/六煞/祸害）。

    zhai_gua 若给（宅卦，按坐山定），附加「宅命相配」判断。
    """
    if gua not in YUNIAN_SONG:
        raise SystemExit("命卦必须是八经卦之一：乾坎艮震巽离坤兑")
    song = YUNIAN_SONG[gua]
    start = GUA_ROUND.index(gua)
    pan = {gua: "伏位"}
    for k, ch in enumerate(song):
        pos = GUA_ROUND[(start + 1 + k) % 8]
        pan[pos] = STAR_CHAR[ch]
    order = []
    for g in GUA_ROUND:
        order.append({"gua": g, "direction": GUA_INFO[g][0], "element": GUA_INFO[g][1],
                      "star": pan[g], "kind": "吉" if pan[g] in GOOD_STARS else "凶"})
    result = {"ming_gua": gua, "type": "东四命" if gua in EAST_GUA else "西四命",
              "positions": order,
              "good": [p for p in order if p["kind"] == "吉"],
              "bad": [p for p in order if p["kind"] == "凶"],
              "summary": "%s（%s，%s）→ 吉位：%s；凶位：%s" % (
                  gua, GUA_INFO[gua][0], "东四命" if gua in EAST_GUA else "西四命",
                  "、".join("%s%s" % (p["direction"], p["star"]) for p in order if p["kind"] == "吉"),
                  "、".join("%s%s" % (p["direction"], p["star"]) for p in order if p["kind"] == "凶"))}
    if zhai_gua:
        if zhai_gua not in GUA_INFO:
            raise SystemExit("宅卦必须是八经卦之一")
        ming_east = gua in EAST_GUA
        zhai_east = zhai_gua in EAST_GUA
        result["zhai_gua"] = zhai_gua
        result["zhai_type"] = "东四宅" if zhai_east else "西四宅"
        result["match"] = "宅命相配" if ming_east == zhai_east else "宅命不配"
        result["match_note"] = ("东四命配东四宅、西四命配西四宅为「配」；"
                                "不配不必恐慌，可用吉位布置与常用房间弱化")
    return result


def _fly(center: int, forward: bool = True) -> dict:
    """九星飞布：center 入中，按洛书飞序顺/逆飞，返回 宫->星。"""
    if center not in range(1, 10):
        raise SystemExit("飞星入中数需为 1–9")
    seq = [5, 6, 7, 8, 9, 1, 2, 3, 4]
    idx = seq.index(center)
    out = {"中": center}  # 入中之星固定落中宫，其余按飞序展开
    for k, palace in enumerate(FLY_ORDER[1:], 1):
        step = k if forward else -k
        out[palace] = seq[(idx + step) % 9]
    return out


def yun_of_year(year: int) -> int:
    for num, start, end in YUN_RANGES:
        if start <= int(year) <= end:
            return num
    raise SystemExit("年份 %s 超出三元九运 1864–2043 范围" % year)


def _palace_of_shan(shan: str) -> str:
    return SHAN[shan]["palace"]


def feixing(year: int, sit) -> dict:
    """玄空飞星（下卦）：运盘 + 山盘 + 向盘 + 局型判断。"""
    parsed = parse_sit(sit)
    if not parsed:
        raise SystemExit("排玄空飞星需要坐向：--sit 子山午向 / --sit 0")
    yun = yun_of_year(year)
    yun_pan = _fly(yun)
    sit_shan = parsed["shan"]
    face_shan = parsed["facing_shan"]
    sit_palace = _palace_of_shan(sit_shan)
    face_palace = _palace_of_shan(face_shan)
    shan_star = yun_pan[sit_palace]
    xiang_star = yun_pan[face_palace]
    shan_forward = SHAN[sit_shan]["yin_yang"] == "阳"
    xiang_forward = SHAN[face_shan]["yin_yang"] == "阳"
    shan_pan = _fly(shan_star, shan_forward)
    xiang_pan = _fly(xiang_star, xiang_forward)
    # 局型判断
    if shan_pan[sit_palace] == yun and xiang_pan[face_palace] == yun:
        ju = "旺山旺向（到山到向）"
        ju_note = "当运星同时到坐山与向首，传统视为最有力的局；仍需峦头配合（有山有水才成形）。"
    elif shan_pan[face_palace] == yun and xiang_pan[sit_palace] == yun:
        ju = "上山下水"
        ju_note = "当运山星到向、向星到山，山向反局；传统视为力量错位，宜用门路与布置调整。"
    elif shan_pan[sit_palace] == yun or xiang_pan[face_palace] == yun:
        ju = "单星到位"
        ju_note = "当运星只到山或只到向之一，偏利人丁或偏利财，另一面需靠布置补。"
    elif shan_pan[face_palace] == yun or xiang_pan[sit_palace] == yun:
        ju = "单星反位"
        ju_note = "当运星落在对面宫位，力量错位，需以门路/常用房间调整。"
    else:
        ju = "一般局"
        ju_note = "当运星未直接到山或到向，按各宫山向组合与用途取舍。"
    q = lambda pal: (shan_pan[pal], xiang_pan[pal])
    grid = []
    for row in PALACE_GRID:
        cells = []
        for pal in row:
            s, x = q(pal)
            cells.append({"palace": pal,
                          "direction": GUA_INFO[pal][0] if pal in GUA_INFO else "中",
                          "yun": yun_pan[pal], "shan": s, "xiang": x,
                          "note": "当运" if (s == yun or x == yun) else ""})
        grid.append(cells)
    centers = {"palace": "中", "yun": yun_pan["中"],
               "shan": shan_pan["中"], "xiang": xiang_pan["中"]}
    return {
        "version": VERSION, "yun": yun, "yun_range": "%d–%d" % (
            [r for r in YUN_RANGES if r[0] == yun][0][1],
            [r for r in YUN_RANGES if r[0] == yun][0][2]),
        "sit": parsed, "yun_pan": yun_pan, "shan_pan": shan_pan, "xiang_pan": xiang_pan,
        "center": centers, "grid": grid, "ju": ju, "ju_note": ju_note,
        "zhai_gua": sit_palace, "warning": parsed.get("warning"),
    }


def yong_shen_home(report: dict) -> dict:
    """八字用神 → 方位/颜色/楼层/房间适配。"""
    ys = ((report.get("analysis") or {}).get("yong_shen") or {})
    roles = ys.get("shen_roles") or {}
    useful = [el for el, role in roles.items() if role == "用神"]
    pleasant = [el for el, role in roles.items() if role == "喜神"]
    avoid = [el for el, role in roles.items() if role in ("忌神", "仇神")]
    if not useful:
        useful = list(ys.get("primary_elements") or [])
        pleasant = [e for e in (ys.get("secondary_elements") or []) if e not in useful]
        avoid = list(ys.get("avoid_elements") or [])
    def pack(elements):
        rows = []
        for el in elements:
            info = ELEMENT_HOME.get(el)
            if not info:
                continue
            rows.append({"element": el, "direction": info[0], "colors": info[1],
                         "floors": info[2], "items": info[3], "rooms": info[4],
                         "avoid": info[5]})
        return rows
    return {"useful": useful, "pleasant": pleasant, "avoid": avoid,
            "useful_rows": pack(useful), "pleasant_rows": pack(pleasant),
            "avoid_rows": pack(avoid)}


# ---------------------------------------------------------------- 床位/书桌朝向

DIRECTION_TEXT = {
    "子": "北", "癸": "北偏东", "丑": "东北偏北", "艮": "东北",
    "寅": "东北偏东", "甲": "东偏北", "卯": "东", "乙": "东偏南",
    "辰": "东南偏东", "巽": "东南", "巳": "东南偏南", "丙": "南偏东",
    "午": "南", "丁": "南偏西", "未": "西南偏南", "坤": "西南",
    "申": "西南偏西", "庚": "西偏南", "酉": "西", "辛": "西偏北",
    "戌": "西北偏西", "乾": "西北", "亥": "西北偏北", "壬": "北偏西",
}


def _ang_diff(a: float, b: float) -> float:
    d = abs((float(a) - float(b)) % 360.0)
    return min(d, 360.0 - d)


_SEX_ALIASES = {"male": 1, "m": 1, "男": 1, "1": 1,
                "female": 0, "f": 0, "女": 0, "0": 0}


def _norm_sex(raw):
    """性别归一：1 男 / 0 女 / None 未知（兼容 male|female|男|女|"1"|"0"）。"""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return 1 if raw else 0
    if isinstance(raw, int):
        return 1 if raw == 1 else (0 if raw == 0 else None)
    return _SEX_ALIASES.get(str(raw).strip().lower())


def parse_orientation(value, label: str = "朝向") -> dict:
    """解析一个「朝向」输入（头朝/书桌面向）：度数、二十四山名或「X向」。

    与 parse_sit 的区别：这里不假设是坐山，只当方向用。
    """
    raw = str(value).strip()
    if not raw:
        raise SystemExit("%s 不能为空" % label)
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*(?:°|度)?", raw)
    if m:
        deg = _norm_deg(float(m.group(1)))
        shan = shan_of_degree(deg)
        off = _ang_diff(deg, shan_center_deg(shan))
        warn = None
        if off > 4.5:
            warn = ("度数 %.1f° 落在 %s 山界内但偏离中心 %.1f°，"
                    "摆床/书桌以山中心或现场罗盘复核更稳。" % (deg, shan, off))
        return {"shan": shan, "deg": deg, "text": DIRECTION_TEXT.get(shan, shan),
                "palace": _palace_of_shan(shan), "warning": warn}
    if raw in SHAN:
        return {"shan": raw, "deg": shan_center_deg(raw),
                "text": DIRECTION_TEXT.get(raw, raw),
                "palace": _palace_of_shan(raw), "warning": None}
    m = re.fullmatch(r"([\u4e00-\u9fff])\s*向", raw)
    if m and m.group(1) in SHAN:
        s = m.group(1)
        return {"shan": s, "deg": shan_center_deg(s),
                "text": DIRECTION_TEXT.get(s, s),
                "palace": _palace_of_shan(s), "warning": None}
    raise SystemExit("无法解析%s「%s」：可用二十四山名（如 庚）、「庚向」，或度数（如 250）"
                     % (label, raw))


def _cell_of_palace(data: dict, palace: str):
    zhai = data.get("zhai")
    if not zhai:
        return None
    for row in zhai.get("grid") or []:
        for cell in row:
            if cell.get("palace") == palace:
                return cell
    return None


def orientation_advice(value, data: dict, label: str = "床位头朝") -> dict:
    """评估一个朝向：八宅星位 + 玄空飞星宫位 + 与用神五行关系。

    结论口径：八宅定吉凶为主，飞星「当运」加一分，用神五行只作参考，不叠加成分数。
    """
    parsed = parse_orientation(value, label)
    palace = parsed["palace"]
    out = {"label": label, "input": str(value).strip(),
           "shan": parsed["shan"], "deg": round(parsed["deg"], 1),
           "text": parsed["text"], "palace": palace,
           "bazhai": None, "feixing": None, "element": None,
           "element_note": "", "verdict": "平", "notes": []}
    bz = data.get("bazhai") or {}
    for pos in bz.get("positions") or []:
        if pos.get("gua") == palace:
            out["bazhai"] = {"star": pos.get("star"), "kind": pos.get("kind")}
            out["element"] = pos.get("element")
            break
    cell = _cell_of_palace(data, palace)
    if cell:
        out["feixing"] = {"yun": cell.get("yun"), "shan": cell.get("shan"),
                          "xiang": cell.get("xiang"), "note": cell.get("note") or ""}
    # 结论：八宅为主
    if out["bazhai"]:
        if out["bazhai"]["kind"] == "吉":
            out["verdict"] = "吉（可用）"
        else:
            out["verdict"] = "凶（尽量避开）"
    # 与用神/喜神/忌神五行的关系（仅提示）
    yh = data.get("yong_shen_home") or {}
    if out["element"]:
        if out["element"] in (yh.get("useful") or []):
            out["element_note"] = "该方五行属%s，正是用神 → 同气加分" % out["element"]
        elif out["element"] in (yh.get("pleasant") or []):
            out["element_note"] = "该方五行属%s，是喜神 → 顺手" % out["element"]
        elif out["element"] in (yh.get("avoid") or []):
            out["element_note"] = "该方五行属%s，属忌仇 → 别久占" % out["element"]
    if out["feixing"] and out["feixing"].get("note"):
        out["notes"].append("该宫当运（%d 运），气旺" % ((data.get("zhai") or {}).get("yun") or 0))
    return out


def _layout_checklist(data: dict) -> list:
    """把吉位/避位 + 用神五行 + 床位结论收敛成可执行清单（不与分数叠加）。"""
    tips = []
    bz = data.get("bazhai") or {}
    if bz.get("good"):
        tips.append("吉位：%s → 主卧、书桌、床头靠这些方位优先。"
                    % "、".join("%s%s" % (p["direction"], p["star"]) for p in bz["good"]))
    if bz.get("bad"):
        tips.append("避位：%s → 放储物、走道、卫生间短时使用，别久坐久睡。"
                    % "、".join("%s%s" % (p["direction"], p["star"]) for p in bz["bad"]))
    lay = data.get("layout") or {}
    bed = lay.get("bed")
    if bed:
        note = ("；" + bed["element_note"]) if bed.get("element_note") else ""
        tips.append("床位（头朝 %s，%s %.1f°）：八宅 %s（%s）→ %s%s。"
                    % (bed["text"], bed["shan"], bed["deg"],
                       bed["bazhai"]["star"] if bed.get("bazhai") else "未知",
                       bed["bazhai"]["kind"] if bed.get("bazhai") else "未知",
                       bed["verdict"], note))
    desk = lay.get("desk")
    if desk:
        tips.append("书桌（面向 %s，%s %.1f°）：八宅 %s（%s）→ %s。"
                    % (desk["text"], desk["shan"], desk["deg"],
                       desk["bazhai"]["star"] if desk.get("bazhai") else "未知",
                       desk["bazhai"]["kind"] if desk.get("bazhai") else "未知",
                       desk["verdict"]))
    tips.extend([
        "床位物理三件：床头靠实墙（不靠窗/空柜/过道）、头下无梁、床对面不照镜子或电视。",
        "靠外墙（尤其西/北墙）加 5cm 以上软包床头板，床离墙留 2–3cm 缝隙通风，西晒加遮光隔热帘。",
        "侧窗不宜正对头肩：双层帘夜里拉严，冬天别留缝直吹；窗下别放书桌久坐。",
        "颜色/楼层：用神方位色系为主，楼层尾数参考用神行；忌仇五行只做点缀，别大面积。",
        "不做『必然旺/克』判断：吉位是倾向，采光、通风、噪音、动线优先于方位。",
    ])
    return tips


# ---------------------------------------------------------------- 组装

def build_fengshui(report: dict, sit=None, yun_year=None,
                   bed_head=None, desk_head=None) -> dict:
    """汇总风水层。sit 可选：给了就排宅盘，不给只出命理侧适配。

    yun_year：玄空元运用的公历年（默认当前年——看宅看的是「现在」的运，不是出生年的运），
    可显式覆盖（例如复盘旧宅）。
    """
    chart = report.get("chart") or {}
    lunar = chart.get("lunar") or {}
    year = lunar.get("year") or (report.get("input") or {}).get("year")
    ci = chart.get("input") or {}
    sex = _norm_sex(ci.get("sex"))
    if sex is None:
        sex = _norm_sex((report.get("input") or {}).get("sex"))
    data = {"version": VERSION, "model": MODEL, "limits": LIMITS,
            "input": {"year": year, "sex": sex, "sit": sit}}
    if year and sex is not None:
        mg = ming_gua(year, sex)
        data["ming_gua"] = mg
        data["bazhai"] = zhai_pan(mg["gua"])
    else:
        data["ming_gua"] = None
        data["bazhai"] = None
        data["note"] = "缺少出生年或性别，命卦/八宅无法排；请补 --sex male/female。"
    data["yong_shen_home"] = yong_shen_home(report)
    if sit:
        zh_year = int(yun_year or _dt.date.today().year)
        clamp_note = ""
        if zh_year < 1864 or zh_year > 2043:
            clamp_note = "玄空元运只覆盖 1864–2043，已按九运（2043）排盘"
            zh_year = 2043
        zh = feixing(zh_year, sit)
        if clamp_note:
            zh["warning"] = ("%s；%s" % (
                zh.get("warning") or "", clamp_note)).strip("；")
        zh["calendar_year"] = zh_year
        data["zhai"] = zh
        if data.get("bazhai"):
            zp = zhai_pan(data["bazhai"]["ming_gua"], zhai_gua=zh["zhai_gua"])
            data["bazhai"] = zp
    else:
        data["zhai"] = None
        data["note"] = (data.get("note") or "") + (
            "未给坐向（--sit），只输出命理侧适配（命卦/八宅/床位书桌朝向）；"
            "要排玄空飞星宅盘需要房子坐向。" )
    # 楼层尾数建议
    rows = (data.get("yong_shen_home") or {}).get("useful_rows") or []
    digits = []
    for r in rows:
        digits.extend([x.strip() for x in r["floors"].split("、")])
    data["floor_hint"] = "、".join(digits) + " 层（尾数）" if digits else ""
    # 床位/书桌朝向适配（只需命卦，不要求坐向）
    if bed_head or desk_head:
        layout = {"version": VERSION}
        layout["bed"] = orientation_advice(bed_head, data, "床位头朝") if bed_head else None
        layout["desk"] = orientation_advice(desk_head, data, "书桌朝向") if desk_head else None
        data["layout"] = layout
        layout["checklist"] = _layout_checklist(data)
    return data


# ---------------------------------------------------------------- 渲染

def render_fengshui_text(data: dict) -> str:
    lines = ["", "【风水适配层】%s" % data.get("model", "")]
    mg = data.get("ming_gua")
    if mg:
        lines.append("命卦：%s（%s，%s，%s，五行属%s）" % (
            mg["gua"], mg["number"], mg["direction"], mg["type"], mg["element"]))
    else:
        lines.append("命卦：无法确定（缺出生年/性别）")
    bz = data.get("bazhai")
    if bz:
        lines.append("八宅吉位：" + "、".join("%s%s" % (p["direction"], p["star"]) for p in bz["good"]))
        lines.append("八宅凶位：" + "、".join("%s%s" % (p["direction"], p["star"]) for p in bz["bad"]))
        if bz.get("match"):
            lines.append("宅命：%s（宅卦 %s，%s）" % (bz["match"], bz.get("zhai_gua"), bz.get("zhai_type")))
        lines.append("用法：主卧/书桌/办公位优先放在吉位；凶位放储物、走道、卫生间，少久坐。")
    yh = data.get("yong_shen_home") or {}
    if yh.get("useful"):
        lines.append("用神：%s；喜神：%s；忌仇：%s" % (
            "、".join(yh["useful"]) or "—", "、".join(yh["pleasant"]) or "—",
            "、".join(yh["avoid"]) or "—"))
        for r in yh["useful_rows"]:
            lines.append("  · %s（用神）：方位 %s；颜色 %s；楼层尾数 %s；材质 %s；房间 %s"
                         % (r["element"], r["direction"], r["colors"], r["floors"], r["items"], r["rooms"]))
        for r in yh["pleasant_rows"]:
            lines.append("  · %s（喜神）：方位 %s；颜色 %s；楼层尾数 %s" % (
                r["element"], r["direction"], r["colors"], r["floors"]))
        if data.get("floor_hint"):
            lines.append("楼层参考：优先 %s" % data["floor_hint"])
    zh = data.get("zhai")
    if zh:
        lines.append("宅盘：%s（%d 运 %s）；坐 %s %.1f° → 向 %s" % (
            zh["ju"], zh["yun"], zh["yun_range"], zh.get("sit", {}).get("shan", ""),
            zh.get("sit", {}).get("deg", 0) or 0, zh.get("sit", {}).get("facing_shan", "")))
        lines.append("  " + zh["ju_note"])
        lines.append("运盘：中%s 乾%s 兑%s 艮%s 离%s 坎%s 坤%s 震%s 巽%s" % tuple(
            [zh["yun_pan"][p] for p in ("中", "乾", "兑", "艮", "离", "坎", "坤", "震", "巽")]))
        lines.append("山盘：中%s 乾%s 兑%s 艮%s 离%s 坎%s 坤%s 震%s 巽%s" % tuple(
            [zh["shan_pan"][p] for p in ("中", "乾", "兑", "艮", "离", "坎", "坤", "震", "巽")]))
        lines.append("向盘：中%s 乾%s 兑%s 艮%s 离%s 坎%s 坤%s 震%s 巽%s" % tuple(
            [zh["xiang_pan"][p] for p in ("中", "乾", "兑", "艮", "离", "坎", "坤", "震", "巽")]))
        lines.append("九宫（山/向）：")
        for row in zh["grid"]:
            lines.append("  " + " | ".join("%s %d:山%d向%d%s" % (
                c["palace"], c["yun"], c["shan"], c["xiang"],
                "（当运）" if c["note"] else "") for c in row))
        if zh.get("warning"):
            lines.append("⚠ " + zh["warning"])
    elif data.get("note"):
        lines.append("说明：" + data["note"])
    lay = data.get("layout")
    if lay:
        lines.append("【床位/书桌朝向】")
        for key in ("bed", "desk"):
            it = lay.get(key)
            if not it:
                continue
            bits = ["%s：头朝/面向 %s（%s，%.1f°）→ 八宅 %s（%s）" % (
                it["label"], it["text"], it["shan"], it["deg"],
                (it.get("bazhai") or {}).get("star", "未知"),
                (it.get("bazhai") or {}).get("kind", "未知"))]
            if it.get("feixing"):
                fx = it["feixing"]
                bits.append("飞星 山%d/向%d%s" % (
                    fx.get("shan") or 0, fx.get("xiang") or 0,
                    "（当运）" if fx.get("note") else ""))
            bits.append("结论：%s" % it["verdict"])
            lines.append("  · " + "；".join(bits))
            if it.get("element_note"):
                lines.append("    " + it["element_note"])
        tips = lay.get("checklist") or []
        if tips:
            lines.append("【布局清单】")
            for i, tip in enumerate(tips, 1):
                lines.append("  %d. %s" % (i, tip))
    lines.append("说明：命卦/八宅/飞星为规则推演；峦头、罗盘实测、户型尺寸需现场，不能由本层替代。")
    return "\n".join(lines)
