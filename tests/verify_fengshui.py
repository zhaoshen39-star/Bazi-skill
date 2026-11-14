# -*- coding: utf-8 -*-
"""风水适配层回归测试（verify_fengshui.py）。

运行：
    python tests/verify_fengshui.py

覆盖：
  A 命卦：男/女公式、余 0/余 5 规则、东四命/西四命、性别与年份校验；
  B 八宅：大游年歌八方吉凶、吉四凶四、命卦伏位、宅卦宅命相配；
  C 坐向解析：二十四山度数边界、山名/「X山Y向」/度数三种输入、对面山、替卦提示；
  D 玄空飞星：三元九运、九宫飞星 1–9 排列、阳顺阴逆、局型（旺山旺向/上山下水/单星）、九宫格；
  E 用神适配：shen_roles 优先、primary_elements 回退、无色值时空列表；
  F 组装与渲染：命卦/八宅/宅盘/楼层提示、缺性别降级、JSON 可序列化、文本字段无 None；
  G CLI：--fengshui / --sit / --json 契约与非法坐向退出码。
"""

import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable
CLI = os.path.join(ROOT, "scripts", "bazi.py")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import fengshui as fs  # noqa: E402

failures = []
total = 0


def check(name, ok, detail=""):
    global total
    total += 1
    if not ok:
        failures.append((name, detail))
        print("FAIL  %s%s" % (name, ("  ← " + str(detail)) if detail else ""))


def raises(fn, needle=""):
    try:
        fn()
    except SystemExit as exc:
        return needle in str(exc)
    except Exception:
        return False
    return False


def fake_report(year=2004, sex=1, roles=None, primary=None):
    ys = {}
    if roles is not None:
        ys["shen_roles"] = roles
    if primary is not None:
        ys["primary_elements"] = primary
    return {"chart": {"lunar": {"year": year}, "input": {"sex": sex}},
            "analysis": {"yong_shen": ys}}


# ---------------------------------------------------------------- A 命卦

mg = fs.ming_gua(1984, "male")
check("A1 1984 男 = 兑 7", mg["number"] == 7 and mg["gua"] == "兑", mg)
check("A2 1984 男 西四命", mg["type"] == "西四命" and mg["sex"] == "男")
mgf = fs.ming_gua(1984, "female")
check("A3 1984 女 = 艮 8", mgf["number"] == 8 and mgf["gua"] == "艮", mgf)
check("A4 2004 男 = 乾 6", fs.ming_gua(2004, 1)["gua"] == "乾")
check("A5 2004 女 = 离 9", fs.ming_gua(2004, 0)["gua"] == "离")
check("A6 离属东四命", fs.ming_gua(2004, 0)["type"] == "东四命")
check("A7 1990 男 = 坎 1", fs.ming_gua(1990, 1)["gua"] == "坎")
check("A8 1990 女 余5 寄艮", fs.ming_gua(1990, 0)["gua"] == "艮")
check("A9 1995 男 余5 寄坤", fs.ming_gua(1995, 1)["gua"] == "坤")
check("A10 2000 男 公式余1", fs.ming_gua(2000, 1)["number"] == 1)
check("A11 性别缺省报错", raises(lambda: fs.ming_gua(2000, None), "性别"))
check("A12 性别非法报错", raises(lambda: fs.ming_gua(2000, "x"), "性别"))
check("A13 女命卦公式 2005", fs.ming_gua(2005, "女")["number"] == 1)
check("A14 命卦含方位五行", fs.ming_gua(1984, 1)["direction"] == "西"
      and fs.ming_gua(1984, 1)["element"] == "金")

# ---------------------------------------------------------------- B 八宅

for g in fs.GUA_ROUND:
    pan = fs.zhai_pan(g)
    check("B1 伏位=命卦 %s" % g, pan["positions"][fs.GUA_ROUND.index(g)]["star"] == "伏位")
    check("B2 吉四凶四 %s" % g, len(pan["good"]) == 4 and len(pan["bad"]) == 4)
    check("B3 八方不重 %s" % g, len({p["gua"] for p in pan["positions"]}) == 8)

zq = fs.zhai_pan("乾")
dirs = {p["direction"]: p["star"] for p in zq["positions"]}
check("B4 乾命生气在西", dirs["西"] == "生气", dirs)
check("B5 乾命天医在东北", dirs["东北"] == "天医")
check("B6 乾命绝命在南", dirs["南"] == "绝命")
zk = fs.zhai_pan("坎")
dk = {p["direction"]: p["star"] for p in zk["positions"]}
check("B7 坎命生气在东南", dk["东南"] == "生气", dk)
check("B8 坎命天医在东", dk["东"] == "天医")
check("B9 坎命延年在南", dk["南"] == "延年")
zx = fs.zhai_pan("巽")
dx = {p["direction"]: p["star"] for p in zx["positions"]}
check("B10 巽命生气在北", dx["北"] == "生气", dx)
check("B11 巽命吉位都在东四宫", all(p["kind"] == "吉" for p in zx["good"])
      and all(p["gua"] in fs.EAST_GUA for p in zx["good"]))
pz = fs.zhai_pan("坎", zhai_gua="震")
check("B12 东四命配东四宅", pz["match"] == "宅命相配" and pz["zhai_type"] == "东四宅")
pz2 = fs.zhai_pan("坎", zhai_gua="乾")
check("B13 东四命配西四宅=不配", pz2["match"] == "宅命不配")
check("B14 八宅摘要含吉位", "吉位" in fs.zhai_pan("坤")["summary"])
check("B15 非法命卦报错", raises(lambda: fs.zhai_pan("中")))
check("B16 非法宅卦报错", raises(lambda: fs.zhai_pan("坎", zhai_gua="x")))

# ---------------------------------------------------------------- C 坐向

check("C1 0°=子", fs.shan_of_degree(0) == "子")
check("C2 7.4°=子", fs.shan_of_degree(7.4) == "子")
check("C3 7.5°=癸", fs.shan_of_degree(7.5) == "癸")
check("C4 90°=卯", fs.shan_of_degree(90) == "卯")
check("C5 180°=午", fs.shan_of_degree(180) == "午")
check("C6 270°=酉", fs.shan_of_degree(270) == "酉")
check("C7 337.5°=壬", fs.shan_of_degree(337.5) == "壬")
check("C8 352.5°=子", fs.shan_of_degree(352.5) == "子")
check("C9 子中心 0°", abs(fs.shan_center_deg("子") - 0.0) < 1e-9)
check("C10 午中心 180°", abs(fs.shan_center_deg("午") - 180.0) < 1e-9)
check("C11 乾中心 315°", abs(fs.shan_center_deg("乾") - 315.0) < 1e-9)
check("C12 子对面午", fs._opposite_shan("子") == "午")
check("C13 卯对面酉", fs._opposite_shan("卯") == "酉")
check("C14 乾对面巽", fs._opposite_shan("乾") == "巽")
p1 = fs.parse_sit("子山午向")
check("C15 子山午向", p1["shan"] == "子" and p1["facing_shan"] == "午" and p1["deg"] == 0.0)
p2 = fs.parse_sit("子")
check("C16 单山输入", p2["shan"] == "子" and p2["facing_shan"] == "午")
p3 = fs.parse_sit("180")
check("C17 度数输入无警告", p3["shan"] == "午" and not p3["warning"])
p4 = fs.parse_sit("172.5")
check("C18 边界度数给替卦提示", bool(p4["warning"]))

# ---------------------------------------------------------------- D 飞星

check("D1 1864 一运", fs.yun_of_year(1864) == 1)
check("D2 1904 三运", fs.yun_of_year(1904) == 3)
check("D3 2004 八运", fs.yun_of_year(2004) == 8)
check("D4 2023 八运", fs.yun_of_year(2023) == 8)
check("D5 2024 九运", fs.yun_of_year(2024) == 9)
check("D6 2043 九运", fs.yun_of_year(2043) == 9)
check("D7 2044 越界报错", raises(lambda: fs.yun_of_year(2044), "1864"))
fly9 = fs._fly(9)
check("D8 九运运盘入中 9", fly9["中"] == 9 and fly9["乾"] == 1 and fly9["巽"] == 8, fly9)
fly5 = fs._fly(5)
check("D9 五入中顺飞", fly5["乾"] == 6 and fly5["坎"] == 1 and fly5["巽"] == 4, fly5)
fly1r = fs._fly(1, forward=False)
check("D10 一入中逆飞", fly1r["乾"] == 9 and fly1r["巽"] == 2, fly1r)
zf = fs.feixing(2026, "子山午向")
check("D11 子山午向 九运", zf["yun"] == 9 and zf["yun_range"] == "2024–2043")
check("D12 局型旺山旺向", zf["ju"].startswith("旺山旺向"), zf["ju"])
check("D13 运盘坎5离4", zf["yun_pan"]["坎"] == 5 and zf["yun_pan"]["离"] == 4)
check("D14 山星到坐 9", zf["shan_pan"]["坎"] == 9 and zf["shan_pan"]["中"] == 5)
check("D15 向星到向 9", zf["xiang_pan"]["离"] == 9 and zf["xiang_pan"]["中"] == 4)
check("D16 宅卦=坐山宫", zf["zhai_gua"] == "坎")
zf2 = fs.feixing(2026, "午山子向")
check("D17 午山子向亦旺山旺向", zf2["ju"].startswith("旺山旺向"), zf2["ju"])
zf3 = fs.feixing(2026, "乾山巽向")
check("D18 乾山巽向上山下水", zf3["ju"] == "上山下水", zf3["ju"])
zf4 = fs.feixing(2026, "卯山酉向")
check("D19 卯山酉向旺山旺向", zf4["ju"].startswith("旺山旺向") and zf4["zhai_gua"] == "震")
for sit in ("子山午向", "卯山酉向", "乾山巽向", "坤山艮向"):
    z = fs.feixing(2026, sit)
    for key in ("yun_pan", "shan_pan", "xiang_pan"):
        if sorted(z[key].values()) != list(range(1, 10)):
            check("D20 九宫 1-9 唯一 %s/%s" % (sit, key), False, z[key])
            break
    else:
        check("D20 九宫 1-9 唯一 %s" % sit, True)
check("D21 九宫格 3x3 含中宫", len(zf["grid"]) == 3 and len(zf["grid"][1]) == 3
      and zf["grid"][1][1]["palace"] == "中")
check("D22 坐向警告透传", fs.feixing(2026, "172.5")["warning"] is not None)

# ---------------------------------------------------------------- E 用神适配

fr = fake_report(roles={"水": "用神", "金": "喜神", "木": "忌神", "火": "仇神", "土": "闲神"})
yh = fs.yong_shen_home(fr)
check("E1 用神=水", yh["useful"] == ["水"] and yh["pleasant"] == ["金"])
check("E2 忌仇=木火", set(yh["avoid"]) == {"木", "火"})
check("E3 水方位北", yh["useful_rows"][0]["direction"] == "北")
check("E4 水楼层 1、6", yh["useful_rows"][0]["floors"] == "1、6")
check("E5 金方位西/西北", "西" in yh["pleasant_rows"][0]["direction"])
fr2 = fake_report(primary=["水"], roles={})
yh2 = fs.yong_shen_home(fr2)
check("E6 回退 primary_elements", yh2["useful"] == ["水"])
yh3 = fs.yong_shen_home({"analysis": {}})
check("E7 空数据不抛错", yh3["useful"] == [] and yh3["useful_rows"] == [])
check("E8 五行表覆盖 5 行", all(k in fs.ELEMENT_HOME for k in "金木水火土"))
check("E9 楼层五行表自洽", fs.FLOOR_ELEMENT[1] == "水" and fs.FLOOR_ELEMENT[0] == "土")
check("E10 忌神也有落地项", yh["avoid_rows"][0]["direction"] != "")

# ---------------------------------------------------------------- F 组装渲染

fr3 = fake_report()
d = fs.build_fengshui(fr3)
check("F1 命卦 2004 男乾", d["ming_gua"]["gua"] == "乾")
check("F2 未给坐向 zhai=None", d["zhai"] is None)
check("F3 未给坐向有说明", "坐向" in (d.get("note") or ""))
check("F4 未给坐向仍有八宅", d["bazhai"] is not None and len(d["bazhai"]["positions"]) == 8)
d2 = fs.build_fengshui(fake_report(roles={"水": "用神", "金": "喜神"}), sit="子山午向")
check("F5 给坐向排宅盘", d2["zhai"] is not None and d2["zhai"]["ju"].startswith("旺山旺向"))
check("F6 宅命判断（乾命+坎宅=不配）", d2["bazhai"]["match"] == "宅命不配")
check("F7 楼层提示", d2["floor_hint"].startswith("1、6"), d2["floor_hint"])
d3 = fs.build_fengshui(fake_report(sex=None))
check("F8 缺性别降级", d3["ming_gua"] is None and "性别" in d3["note"])
d4 = fs.build_fengshui(fake_report(year=1984, sex=0), sit="乾山巽向")
check("F9 1984 女艮命", d4["ming_gua"]["gua"] == "艮")
check("F10 乾山巽向宅盘", d4["zhai"]["ju"] == "上山下水")
try:
    json.dumps(d2, ensure_ascii=False)
    check("F11 JSON 可序列化", True)
except Exception as exc:  # pragma: no cover
    check("F11 JSON 可序列化", False, exc)
txt = fs.render_fengshui_text(d2)
check("F12 文本含各段", all(k in txt for k in ("【风水适配层】", "命卦：", "八宅吉位", "用神：", "宅盘：")))
check("F13 文本无 None", "None" not in txt)
check("F14 边界声明与版本", d2["version"] == fs.VERSION and len(d2["limits"]) >= 5
      and "八宅" in d2["model"] and "现场" in txt)
today = datetime.date.today().year
check("F15 宅盘用当前年元运", d2["zhai"]["calendar_year"] == today
      and d2["zhai"]["yun"] == fs.yun_of_year(today))
d6 = fs.build_fengshui(fake_report(), sit="子山午向", yun_year=2004)
check("F16 元运年份可覆盖", d6["zhai"]["calendar_year"] == 2004 and d6["zhai"]["yun"] == 8)
check("F17 命卦文本不重复「命命」", "命命" not in txt)


# ---------------------------------------------------------------- G CLI

def cli(args, expect_zero=True):
    p = subprocess.run([PY, CLI] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return p


base = ["--date", "2004-06-12", "--time", "10:00", "--sex", "male"]
p = cli(base + ["--json", "--fengshui"])
ok = p.returncode == 0
data = {}
if ok:
    try:
        data = json.loads(p.stdout)
    except Exception:
        ok = False
check("G1 --json --fengshui 可解析", ok, p.stderr[-300:] if not ok else "")
fsd = data.get("fengshui") or {}
check("G2 JSON fengshui.version", fsd.get("version") == fs.VERSION)
check("G3 JSON 命卦乾", (fsd.get("ming_gua") or {}).get("gua") == "乾")
p2 = cli(base + ["--json", "--sit", "子山午向"])
d5 = json.loads(p2.stdout) if p2.returncode == 0 else {}
check("G4 --sit 隐含风水", (d5.get("fengshui") or {}).get("zhai") is not None)
check("G5 --sit 排旺山旺向", ((d5.get("fengshui") or {}).get("zhai") or {}).get("ju", "").startswith("旺山旺向"))
p3 = cli(base + ["--fengshui"])
check("G6 文本含标题", p3.returncode == 0 and "【风水适配层】" in p3.stdout)
check("G7 文本含用神建议", p3.returncode == 0 and "用神：" in p3.stdout)
p4 = cli(base + ["--json", "--sit", "abc"])
check("G8 非法坐向非零退出", p4.returncode != 0, p4.stderr[-200:])
p5 = cli(base + ["--json", "--fengshui", "--sit", "0"])
check("G9 度数坐向生效", (json.loads(p5.stdout)["fengshui"]["zhai"]["sit"]["shan"]) == "子")
p6 = cli(base + ["--json"])
check("G10 默认不含风水", "fengshui" not in json.loads(p6.stdout))

# ---------------------------------------------------------------- H 床位/书桌朝向

roles_bed = {"水": "用神", "金": "喜神", "木": "忌神", "土": "忌神", "火": "仇神"}
rep_bed = fake_report(roles=roles_bed)

o = fs.parse_orientation("250")
check("H1 250° → 庚/兑宫", o["shan"] == "庚" and o["palace"] == "兑", o)
check("H2 方位文字", o["text"] == "西偏南")
o2 = fs.parse_orientation("庚")
check("H3 山名输入等价", o2["shan"] == "庚" and abs(o2["deg"] - 255.0) < 1e-6)
check("H4 非法朝向报错", raises(lambda: fs.parse_orientation("东"), "无法解析"),
      "东 不是二十四山，应报错")

data_bed = fs.build_fengshui(rep_bed, bed_head="250")
bed = (data_bed.get("layout") or {}).get("bed") or {}
check("H5 床位落八宅生气(吉)", (bed.get("bazhai") or {}).get("star") == "生气"
      and "吉" in bed.get("verdict", ""), bed.get("verdict"))
check("H6 250° 属金=喜神提示", "喜神" in bed.get("element_note", ""), bed.get("element_note"))
data_desk = fs.build_fengshui(rep_bed, desk_head="90")
desk = (data_desk.get("layout") or {}).get("desk") or {}
check("H7 书桌朝东=五鬼(凶)", (desk.get("bazhai") or {}).get("star") == "五鬼"
      and "凶" in desk.get("verdict", ""), desk.get("verdict"))
check("H8 无坐向也能判床位（飞星为空）", bed.get("feixing") is None and bed.get("bazhai"))
tips = (data_bed.get("layout") or {}).get("checklist") or []
check("H9 布局清单非空且含吉位/避位", len(tips) >= 5 and any("吉位" in t for t in tips)
      and any("避位" in t for t in tips), len(tips))
check("H10 清单含物理项（床头靠实墙）", any("床头靠实墙" in t for t in tips))

rep_sit_report = fake_report(roles=roles_bed)
data_z = fs.build_fengshui(rep_sit_report, sit="庚山甲向", bed_head="250")
fe = ((data_z.get("layout") or {}).get("bed") or {}).get("feixing") or {}
check("H11 有坐向时带飞星 山4/向9", fe.get("shan") == 4 and fe.get("xiang") == 9, fe)
txt = fs.render_fengshui_text(data_z)
check("H12 渲染含床位段", "【床位/书桌朝向】" in txt and "床位头朝" in txt)
check("H13 渲染含布局清单", "【布局清单】" in txt and "床头靠实墙" in txt)
check("H14 渲染无 None", "None" not in txt)

pb = cli(base + ["--json", "--fengshui", "--bed-head", "250"])
db = json.loads(pb.stdout) if pb.returncode == 0 else {}
check("H15 CLI --bed-head 生效", (((db.get("fengshui") or {}).get("layout") or {}).get("bed")
                                  or {}).get("shan") == "庚")
pt = cli(base + ["--fengshui", "--bed-head", "250", "--desk-head", "90"])
check("H16 CLI 文本含书桌段", pt.returncode == 0 and "书桌" in pt.stdout)
check("H17 CLI 非法朝向非零退出", cli(base + ["--fengshui", "--bed-head", "xx"]).returncode != 0)

# ---------------------------------------------------------------- G2. 玄空飞星 gold
# 用八运/九运的经典局核对「顺飞/逆飞」：坐宫山星、向宫向星必须落到正确数字。
GOLD = [
    (2010, "子山午向", "旺山旺向", "坎", 8, "离", 8),
    (2010, "午山子向", "旺山旺向", "离", 8, "坎", 8),
    (2010, "乾山巽向", "上山下水", "乾", 1, "巽", 6),
    (2010, "卯山酉向", "旺山旺向", "震", 8, "兑", 8),
    (2030, "子山午向", "旺山旺向", "坎", 9, "离", 9),
    (2030, "午山子向", "旺山旺向", "离", 9, "坎", 9),
    (2030, "乾山巽向", "上山下水", "乾", 2, "巽", 7),
    (2030, "卯山酉向", "旺山旺向", "震", 9, "兑", 9),
]
for _year, _sit, _ju, _sp, _sv, _xp, _xv in GOLD:
    _r = fs.feixing(_year, _sit)
    _tag = "%d 运 %s" % (_r["yun"], _sit)
    check("G2 %s 局型=%s" % (_tag, _ju), _ju in _r["ju"], _r["ju"])
    check("G2 %s 坐宫%s 山星=%d" % (_tag, _sp, _sv),
          (_r["shan_pan"].get(_sp) == _sv), _r["shan_pan"].get(_sp))
    check("G2 %s 向宫%s 向星=%d" % (_tag, _xp, _xv),
          (_r["xiang_pan"].get(_xp) == _xv), _r["xiang_pan"].get(_xp))

# ---------------------------------------------------------------- 本轮修复锁定
for _c in (1, 5, 9):
    _fly = fs._fly(_c)
    check("F18 _fly(%d) 入中之星固定落中宫" % _c, _fly.get("中") == _c, _fly.get("中"))
_p = fs.parse_sit("5")
check("F19 山界 3° 内给替卦提示", bool(_p.get("warning")) and ("替卦区" in _p["warning"]), _p.get("warning"))

# ---------------------------------------------------------------- 二轮清理锁定
_off = fs.parse_orientation("250")
check("F20 偏离山中心 >4.5° 给复核提示",
      bool(_off.get("warning")) and ("偏离" in _off["warning"]), _off.get("warning"))
check("F21 山中心附近不提示", fs.parse_orientation("255").get("warning") is None,
      fs.parse_orientation("255").get("warning"))
check("F22 性别归一 male/0/未知",
      (fs._norm_sex("male"), fs._norm_sex("0"), fs._norm_sex("?")) == (1, 0, None),
      (fs._norm_sex("male"), fs._norm_sex("0"), fs._norm_sex("?")))
_rep_min = {"chart": {"lunar": {"year": 2004}, "input": {"sex": 1}},
            "analysis": {"yong_shen": {"shen_roles": {"水": "用神"}}}}
_clamp = fs.build_fengshui(_rep_min, sit="子山午向", yun_year=2050)
check("F23 元运超界回落到九运并给 warning",
      _clamp["zhai"]["calendar_year"] == 2043 and "2043" in (_clamp["zhai"].get("warning") or ""),
      _clamp["zhai"].get("warning"))
_no_sit = fs.build_fengshui(_rep_min, bed_head="250")
check("F24 未给坐向时 note 说明含床位/书桌", "床位书桌朝向" in (_no_sit.get("note") or ""),
      _no_sit.get("note"))

# ---------------------------------------------------------------- 汇总


print("")
if failures:
    print("verify_fengshui: %d/%d 失败" % (len(failures), total))
    for name, detail in failures:
        print("  - %s %s" % (name, detail))
    sys.exit(1)
print("verify_fengshui: 全部通过 %d 项 ✅" % total)
