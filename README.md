# bazi-skill · 八字命理分析与跨体系推测引擎

一个**纯标准库、零第三方依赖**的中文命理分析引擎（Python 3.12+），可作为 DSH skill 使用，也可以直接用命令行跑。

它不是"算命 App"：排盘用可验证的历法/天文算法，分析与推测部分遵循古典命理（子平真诠、穷通宝鉴、紫微斗数、奇门遁甲等）的规则体系，并**明确区分"可验证的"（排盘、星历）与"不可验证的"（旺衰强弱、格局成败、打分）**——所有打分都是内部刻度，不是概率。

## 能做什么

- **八字排盘**：真太阳时校正、节气边界、晚子时双流派、大运/流年/流月、神煞、干支关系
- **结构力旺衰**：柱位权重 × 藏干分层 × 十神亲和 × 刑冲合害折损，输出置信度与五党结构力
- **格局**：子平真诠取格（本气/中气/余气透干、四生四旺月本气为格、杂气透干优先）、顺逆用、相神、成败分级（severity/resolved）、救应、月令损伤
- **喜用**：扶抑 / 调候（《穷通宝鉴》120 格）/ 通关 / 病药 四法合参 + 仲裁，判用神力量（有力/有透无根/有根无透/虚浮）
- **大运流年**：基调（五行喜忌）+ 引动（伏吟/反吟/冲合刑害/岁运并临/半合），综合分与应期
- **通俗版输出**：`--brief` / `--plain`，把术语翻译成人话
- **专题推测八域**：婚恋 / 事业 / 财富 / 学业 / 健康 / 六亲 / 迁移 / 人际
- **多术数层**：小六壬、梅花易数、六爻纳甲（含断语层）、袁天罡称骨、紫微斗数（断语层：亮度/三方四正/13 格局三态/大限主题）、奇门遁甲（时家转盘拆补法）、西洋星座、生肖纳音
- **跨体系融合层**：西洋占星（截断 VSOP87 + Meeus 太阳 + ELP 月亮 + Placidus 宫位）、印度占星（Lahiri 近似 + 27 宿）、数字学（生命灵数/个人年）+ 九域共识/张力分析

## 快速开始

```bash
# 完整技术盘
python scripts/bazi.py --date 1990-06-15 --time 10:00 --sex male \
  --longitude 116.41 --latitude 39.90 --true-solar-time --focus-year 2026

# 人话摘要（≤400 字）
python scripts/bazi.py --date 1990-06-15 --time 10:00 --sex male --brief

# 只看婚恋与事业
python scripts/bazi.py --date 1990-06-15 --time 10:00 --sex male --topic love,career

# 多术数层 + 紫微 + 融合 + 占星 + 数字学
python scripts/bazi.py --date 1990-06-15 --time 10:00 --sex male \
  --divination --ziwei --fusion --astro --numerology --focus-year 2026

# JSON 输出（给程序用）
python scripts/bazi.py --date 1990-06-15 --time 10:00 --sex male --json
```

Windows 下如果控制台是 GBK，脚本会在启动时自动把标准输出切到 UTF-8。

## 测试

```bash
python tests/run_all.py
```

当前：**17 套件、5253 项检查全部通过**，包括：

| 套件 | 内容 |
|---|---|
| verify / verify_v2 / verify_v3 | 各层回归 |
| verify_calendar | 历法交叉验证（228 项） |
| verify_independent | 独立公式校验 |
| verify_astrology | 占星对 ephem 星历（468 项，太阳 0.005°、月亮 0.002°） |
| verify_ziwei | 紫微安星对 iztro（502 项） |
| verify_qimen | 奇门定局与排盘（2543 项） |
| verify_cases | 古典命例对照（64 例，与原文断语一致率 89.2%，仅作测量） |
| verify_plain / verify_topics / verify_divination / verify_fusion | 输出层与各术数 |

## 目录

```
SKILL.md              技能入口（DSH skill 格式）
scripts/bazi.py       命令行入口
scripts/chart.py      排盘内核（节气/干支/大运）
scripts/analysis_v3.py 结构力旺衰 + 格局 + 喜用 + 大运流年
scripts/analysis.py   旧版（v2）分析函数，供兼容测试
scripts/plain.py      通俗版输出层
scripts/topics.py     专题推测八域
scripts/divination.py 小六壬/梅花/六爻/称骨/星座/生肖
scripts/ziwei.py      紫微斗数（安星 + 断语层）
scripts/qimen.py      奇门遁甲（时家转盘）
scripts/astrology.py  西洋/印度占星
scripts/numerology.py 数字学
scripts/fusion.py     跨体系融合层
scripts/tiaohou_table.py / chenggu_table.py  穷通宝鉴调候表、称骨表
scripts/vendor/       内置 lunar_python（MIT，见 NOTICE.md）
references/           规则、方法学、数据源、输出契约等文档
tests/                回归测试与 fixture
```

## 边界与免责

- 排盘与星历**可以**被独立验证；旺衰/格局/喜用/打分**不可**验证，只能保证规则可复现。
- 命理学是文化传统，不是科学预测。本工具输出的是"按某套规则推演出的结构描述"，**不构成任何决策依据**。
- 同一命盘在不同流派下结论可能相反；本项目选择一种口径并把分歧写进文档（见 `references/`）。

## 许可

本项目代码采用 MIT 许可。内置的 `lunar_python`（6tail，MIT）见 `scripts/vendor/NOTICE.md` 与 `scripts/vendor/lunar-python-LICENSE.txt`。
