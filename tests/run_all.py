# -*- coding: utf-8 -*-
"""一键跑全部回归测试。

用法：
    python tests/run_all.py          # 跑全部，末行给汇总
    python tests/run_all.py -v       # 顺带打印每个套件最后几行

退出码：全部通过 0，否则 1。新增套件请登记到 SUITES。
第三项为额外参数（可选），如 ["--report-only"]。
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SUITES = [
    ("verify.py", "排盘固定基准", []),
    ("verify_independent.py", "独立公式交叉校验", []),
    ("verify_relations.py", "关系/格局单测", []),
    ("verify_regressions.py", "时区/农历/回归", []),
    ("verify_optimizations.py", "岁运并临/反吟/流月", []),
    ("verify_v2.py", "十神结构/喜忌/JSON", []),
    ("verify_v3.py", "结构力旺衰/取格成败/四法仲裁", []),
    ("verify_plain.py", "通俗版输出层", []),
    ("verify_topics.py", "专题推测八域", []),
    ("verify_calendar.py", "排盘历法交叉验证", []),
    ("verify_divination.py", "多术数层", []),
    ("verify_ziwei.py", "紫微斗数层", []),
    ("verify_fusion.py", "跨体系融合层", []),
    ("verify_astrology.py", "西洋/印度占星层", []),
    ("verify_numerology.py", "数字学层", []),
    ("verify_cases.py", "古典命例对照（测量口径）", ["--report-only"]),
    ("verify_qimen.py", "奇门遁甲层", []),
]

_COUNT_PATTERNS = [
    re.compile(r"([0-9]+)\s*项"),
    re.compile(r"([0-9]+)\s*checks"),
    re.compile(r"通过\s*([0-9]+)\s*/\s*[0-9]+"),
    re.compile(r"共\s*([0-9]+)"),
    re.compile(r"可对照字段:\s*([0-9]+)"),
]
_PASS_MARKS = ("全部通过", "全部一致", "ALL PASS", "结构通过")


def _count(out):
    for pat in _COUNT_PATTERNS:
        m = pat.search(out)
        if m:
            return int(m.group(1))
    return 0


def main(argv):
    verbose = "-v" in argv or "--verbose" in argv
    total = 0
    failed = []
    missing = []
    for name, label, extra in SUITES:
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            missing.append(name)
            print("  --  %-26s 跳过（文件不存在）" % name)
            continue
        r = subprocess.run([sys.executable, path] + extra, capture_output=True,
                           text=True, encoding="utf-8", timeout=600)
        out = (r.stdout or "") + (r.stderr or "")
        n = _count(out)
        passed = r.returncode == 0 and any(m in out for m in _PASS_MARKS)
        total += n
        status = "OK" if passed else "FAIL"
        if not passed:
            failed.append(name)
        print("  %-4s %-26s %4d 项  %s" % (status, name, n, label))
        if verbose or not passed:
            tail = [ln for ln in out.strip().splitlines() if ln.strip()][-6:]
            for ln in tail:
                print("        " + ln)
    print()
    print("合计 %d 项；失败套件：%s；缺失套件：%s"
          % (total, ", ".join(failed) or "无", ", ".join(missing) or "无"))
    if failed:
        print("结果：FAIL")
        return 1
    print("结果：ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
