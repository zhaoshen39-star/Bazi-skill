#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""古典命例对照验证 (task-8)。

读取 tests/fixtures_cases.json 中的古典命例，用 scripts/analysis_v3.py 的
pattern() / yong_shen() 重新计算，并**只对每例 asserted_fields 中列出的字段**
做对照断言。原文断语之外不作任何推断，不修改断言来迁就实现。

用法:
    python tests/verify_cases.py            # 对照并打印统计/不一致明细
    python tests/verify_cases.py --json     # 在统计后附带逐例计算结果 JSON（供文档引用）
    python tests/verify_cases.py --report-only  # 不一致时仍返回 0（只作测量，不作门禁）

退出码:
    0  结构检查通过，且可对照字段全部一致
    1  结构检查失败 / 计算异常 / 存在不一致
"""

import json
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
FIXTURE_PATH = os.path.join(ROOT, "tests", "fixtures_cases.json")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

try:
    import analysis_v3 as a3
except Exception as exc:  # pragma: no cover - 环境问题
    print("FATAL: 无法导入 scripts/analysis_v3.py: %s" % exc)
    raise SystemExit(1)

PILLAR_NAMES = ["年柱", "月柱", "日柱", "时柱"]
GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
VALID_ASSERTED = ("pattern", "shun_ni", "status_hint", "yong_shen_elements")

# 古法格名 -> v3 中可接受的格名集合（同义归并，不改变判定口径）
PATTERN_ALIASES = {
    "正官格": ("正官格",),
    "七杀格": ("七杀格", "偏官格"),
    "财格": ("正财格", "偏财格"),
    "印格": ("正印格", "偏印格"),
    "食神格": ("食神格",),
    "伤官格": ("伤官格",),
    "建禄格": ("建禄格",),
    "阳刃格": ("月劫格（阳刃格）", "阳刃格", "月劫格"),
}


def _load_fixtures():
    with open(FIXTURE_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _structural_errors(data):
    """返回结构问题列表；空列表表示结构通过。"""
    errs = []
    if not isinstance(data, dict):
        return ["fixtures 顶层必须是对象（含 meta / cases）"]
    cases = data.get("cases")
    if not isinstance(cases, list):
        return ["cases 必须是数组"]
    if len(cases) < 40:
        errs.append("命例数 %d < 40" % len(cases))
    seen = set()
    for i, case in enumerate(cases):
        tag = "cases[%d]" % i
        if not isinstance(case, dict):
            errs.append("%s 不是对象" % tag)
            continue
        cid = case.get("id")
        if not isinstance(cid, str) or not cid.strip():
            errs.append("%s 缺少 id" % tag)
        elif cid in seen:
            errs.append("%s id 重复: %s" % (tag, cid))
        else:
            seen.add(cid)
        for key in ("source", "quote"):
            if not isinstance(case.get(key), str) or not case.get(key, "").strip():
                errs.append("%s 缺少非空 %s" % (tag, key))
        pillars = case.get("pillars")
        if not isinstance(pillars, list) or len(pillars) != 4:
            errs.append("%s pillars 必须是 4 个干支" % tag)
        else:
            for gz in pillars:
                if (not isinstance(gz, str) or len(gz) != 2
                        or gz[0] not in GAN or gz[1] not in ZHI):
                    errs.append("%s 非法干支: %r" % (tag, gz))
        sex = case.get("sex")
        if sex not in (0, 1, None):
            errs.append("%s sex 只能是 0/1/null" % tag)
        expected = case.get("expected")
        if not isinstance(expected, dict):
            errs.append("%s expected 必须是对象" % tag)
            expected = {}
        fields = case.get("asserted_fields")
        if not isinstance(fields, list) or not fields:
            errs.append("%s asserted_fields 必须是非空数组" % tag)
            continue
        for field in fields:
            if field not in VALID_ASSERTED:
                errs.append("%s 不支持的断言字段: %r" % (tag, field))
            elif expected.get(field) is None:
                errs.append("%s 断言字段 %s 在 expected 中为 null" % (tag, field))
        if expected.get("pattern") is not None:
            if expected["pattern"] not in PATTERN_ALIASES:
                errs.append("%s 未知格名: %r" % (tag, expected["pattern"]))
        if expected.get("shun_ni") is not None:
            if expected["shun_ni"] not in ("顺用", "逆用"):
                errs.append("%s shun_ni 必须是 顺用/逆用" % tag)
        if expected.get("status_hint") is not None:
            if expected["status_hint"] not in ("成格", "成中有败", "败中有救", "破格"):
                errs.append("%s 非法 status_hint: %r" % (tag, expected["status_hint"]))
        if expected.get("yong_shen_elements") is not None:
            ys = expected["yong_shen_elements"]
            if (not isinstance(ys, list) or not ys
                    or any(e not in ("木", "火", "土", "金", "水") for e in ys)):
                errs.append("%s yong_shen_elements 必须是五行数组" % tag)
    return errs


def _compute(case):
    """按 analysis_v3 的公开调用约定计算一例。"""
    day_gan = case["pillars"][2][0]
    pillars = [
        {"gan": gz[0], "zhi": gz[1], "name": name}
        for gz, name in zip(case["pillars"], PILLAR_NAMES)
    ]
    strength = a3.strength(pillars, day_gan)
    pattern = a3.pattern(pillars, day_gan, strength)
    yong = a3.yong_shen(day_gan, None, strength, pattern, pillars)
    return {
        "day_gan": day_gan,
        "strength": strength,
        "pattern": pattern,
        "yong_shen": yong,
    }


def _check_field(field, expected, computed):
    """返回 (ok, actual_desc, detail)。actual_desc 用于打印与文档。"""
    pattern = computed["pattern"]
    if field == "pattern":
        actual = pattern.get("name")
        aliases = PATTERN_ALIASES.get(expected, (expected,))
        ok = actual in aliases
        why = "取格方式=%s 透干=%s" % (
            pattern.get("take_method"),
            [t.get("gan") for t in (pattern.get("transparent") or [])],
        )
        return ok, "%s（%s）" % (actual, why), None
    if field == "shun_ni":
        actual = pattern.get("shun_ni") or ""
        ok = actual.startswith(expected)
        return ok, actual or "（空）", None
    if field == "status_hint":
        actual = pattern.get("status")
        ok = actual == expected
        note = pattern.get("status_note") or ""
        return ok, "%s（%s）" % (actual, note), None
    if field == "yong_shen_elements":
        primary = computed["yong_shen"].get("primary_elements") or []
        missing = [e for e in expected if e not in primary]
        ok = not missing
        actual = "primary=%s secondary=%s 仲裁=%s" % (
            primary,
            computed["yong_shen"].get("secondary_elements"),
            (computed["yong_shen"].get("arbitration") or {}).get("rule"),
        )
        return ok, actual, None
    return False, "（未知字段）", None


def main(argv):
    report_only = "--report-only" in argv
    dump_json = "--json" in argv
    data = _load_fixtures()
    print("=== 古典命例对照：tests/fixtures_cases.json ===")
    print("fixtures 路径: %s" % FIXTURE_PATH)

    errors = _structural_errors(data)
    if errors:
        print("\n结构检查: FAIL (%d 项)" % len(errors))
        for err in errors:
            print("  - %s" % err)
        return 1
    cases = data["cases"]
    print("结构检查: OK（%d 例，id 唯一，字段齐全）" % len(cases))

    total = 0
    agree = 0
    mismatches = []
    anomalies = []
    field_stats = {field: [0, 0] for field in VALID_ASSERTED}  # field -> [可比, 一致]
    details = []

    for case in cases:
        cid = case["id"]
        fields = case["asserted_fields"]
        try:
            computed = _compute(case)
        except Exception:
            anomalies.append({
                "id": cid,
                "error": traceback.format_exc().strip().splitlines()[-1],
            })
            total += len(fields)
            for field in fields:
                field_stats[field][0] += 1
            continue
        expected = case["expected"]
        details.append({
            "id": cid,
            "pattern": computed["pattern"].get("name"),
            "shun_ni": (computed["pattern"].get("shun_ni") or "").split("（")[0],
            "status": computed["pattern"].get("status"),
            "primary_elements": computed["yong_shen"].get("primary_elements"),
            "secondary_elements": computed["yong_shen"].get("secondary_elements"),
            "arbitration": (computed["yong_shen"].get("arbitration") or {}).get("rule"),
            "confidence": computed["pattern"].get("confidence"),
        })
        for field in fields:
            total += 1
            field_stats[field][0] += 1
            ok, actual, _ = _check_field(field, expected[field], computed)
            if ok:
                agree += 1
                field_stats[field][1] += 1
            else:
                mismatches.append({
                    "id": cid,
                    "field": field,
                    "expected": expected[field],
                    "actual": actual,
                    "note": (expected.get("note") or ""),
                    "source": case.get("source", ""),
                })

    print("\n可对照字段: %d   一致: %d   不一致: %d" % (total, agree, total - agree))
    if total:
        print("一致率: %.1f%%" % (100.0 * agree / total))
    print("逐字段: " + "  ".join(
        "%s %d/%d" % (field, field_stats[field][1], field_stats[field][0])
        for field in VALID_ASSERTED if field_stats[field][0]
    ))

    if mismatches:
        print("\n--- 不一致明细（%d 处）---" % len(mismatches))
        for idx, item in enumerate(mismatches, 1):
            print("[%02d] %s / %s" % (idx, item["id"], item["field"]))
            print("     期望: %r" % (item["expected"],))
            print("     实际: %s" % item["actual"])
            print("     原文: %s" % item["note"])

    if anomalies:
        print("\n--- 计算异常（%d 例，未纳入对照）---" % len(anomalies))
        for item in anomalies:
            print("  - %s: %s" % (item["id"], item["error"]))

    if dump_json:
        print("\n--- 逐例计算结果（JSON）---")
        print(json.dumps(details, ensure_ascii=False, indent=1))
        if mismatches:
            print("\n--- 不一致 JSON ---")
            print(json.dumps(mismatches, ensure_ascii=False, indent=1))

    failed = bool(mismatches or anomalies)
    if failed and report_only:
        print("\n结论: 结构通过；存在 %d 处不一致（--report-only 模式，退出码 0）"
              % (len(mismatches) + len(anomalies)))
        return 0
    if failed:
        print("\n结论: FAIL（结构%s；不一致 %d 处，异常 %d 例）"
              % ("通过" if not errors else "失败", len(mismatches), len(anomalies)))
        return 1
    print("\n结论: PASS（所有可对照字段一致）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
