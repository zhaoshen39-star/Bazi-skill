## 二、运行脚本

先取运行时 Python，再调用本技能目录下的脚本（`SKILL.md` 所在目录即技能根目录，脚本在 `scripts/`）。

```powershell
# 1) 先调用 load_workspace_dependencies，拿到返回的 python 可执行文件路径
# 2) 基础排盘（文本）
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male

# 3) 高精度：真太阳时（推荐在有出生地经度时使用）
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male `
    --longitude 116.4 --true-solar-time

# 4) 结构化输出，便于二次处理
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male --json

# 5) 附带聚焦年的流月
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male --focus-year 2026 --liuyue --json

# 6) 通俗版正文（人话）：结论 / 性格 / 钱与工作 / 感情 / 健康 / 近几年 / 建议
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male --plain-only

# 7) 通俗版 + 技术版一起输出（正文在前，技术附在后）
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male --plain

# 8) 通俗版结构化数据（JSON 里多一个 plain 字段）
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male --json --plain

# 9) 专题推测：婚恋 / 事业 / 财富 / 学业 / 健康 / 六亲 / 迁移 / 人际 八域
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male --focus-year 2026 --topics

# 10) 通俗版 + 专题推测（先人话再分领域，适合直接发给用户）
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male --focus-year 2026 --plain-only --topics

# 11) 多术数交叉参考：小六壬 / 梅花易数 / 六爻纳甲 / 称骨 / 星座 / 生肖纳音 / 紫微斗数
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male --focus-year 2026 --divination

# 12) 多术数结构化数据（JSON 里多一个 divination 字段）
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male --json --divination

# 13) 单独输出紫微斗数命盘（十二宫/主星/六吉六煞/四化/大限）
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male --ziwei

# 14) 跨体系融合：八字 + 紫微 + 西洋/印度占星 + 数字学 + 民俗（九域一致与张力）
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male `
    --longitude 116.4 --true-solar-time --fusion

# 15) 融合层结构化数据（JSON 里多一个 fusion 字段）
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male `
    --longitude 116.4 --true-solar-time --json --fusion

# 16) 西洋 + 印度占星本命盘（十行星/宫位/相位/元素平衡/月相/27 宿/上升）
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male `
    --longitude 116.4 --true-solar-time --astro

# 17) 数字学（生命灵数/生日数/九宫格/个人年，可加姓名）
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male `
    --focus-year 2026 --numerology --name "John Smith"
```

参数速查：

- `--date YYYY-MM-DD`、`--time HH:MM[:SS]`：记录的钟表时间
- `--lunar` / `--leap`：`--date` 视为农历；闰月再加 `--leap`
- `--sex male|female`（或 `m/f/男/女`）：算大运必需
- `--zone`：IANA 时区，默认 `Asia/Shanghai`
- `--longitude`：东经为正、西经为负，取值 [-180, 180]；配合 `--true-solar-time` 使用
- `--latitude`：北纬为正、南纬为负，取值 [-90, 90]；占星上升/宫位用，缺省按 30°N 并在输出中提示（`latitude_default`）
- `--sect 1|2`：晚子时流派，默认 2
- `--qiyun-sect 1|2`：起运计算法，默认 2（按分钟，较细）
- `--dayun-count N`：大运轮数，默认 9（须 ≥1）
- `--time-unknown`：时辰未知，标记时柱不可靠（旺衰/喜用含时柱成分，仅供参考）
- `--focus-year`：流年聚焦年，默认当前年
- `--liuyue`：附带聚焦年的流月（文本与 `--json` 都输出，含节气日期区间）
- `--json`：输出完整结构（时间校正、四柱、藏干、十神、大运、流年、五行、旺衰、格局、喜用、**十神结构、神煞、合冲刑害、大运/流年喜忌打分**、警告、方法学）
- `--plain` / `--plain-only`：通俗版输出层（见 §四）；`--plain` 在文本模式下「通俗在前、技术在后」，`--plain-only` 只出通俗版；与 `--json` 同用则报告里多一个 `plain` 字段
- `--topics`：追加「专题推测」八域（婚恋/事业/财富/学业/健康/六亲/迁移/人际），每个领域给倾向、依据、有利年份、需留意年份、建议与置信度；与 `--json` 同用则报告里多一个 `topics` 字段（文本模式下专题段附在最后）
- `--divination`：追加「多术数交叉参考」（小六壬/梅花易数/六爻纳甲/称骨算命/西洋星座/生肖纳音/紫微斗数），给出各体系的起卦/落宫/卦象/骨重/宫星与断语，并汇总「多体系交叉参考」；与 `--json` 同用则报告里多一个 `divination` 字段（文本模式下附在最后）
- `--ziwei`：单独输出紫微斗数命盘（十二宫、主星、六吉六煞、年干四化、大限、要点与局限）；与 `--json` 同用则报告里多一个 `ziwei` 字段
- `--fusion`：跨体系融合层：把八字、紫微、西洋占星、印度占星、数字学、民俗（小六壬/称骨/星座）各自的方向信号按九域聚合，输出「一致/多数/分歧/对立/单体系参考/信号相抵/证据不足」与整体一致度；缺体系标「证据不足」，不换算成概率；与 `--json` 同用则报告里多一个 `fusion` 字段（文本模式下融合段附在最后），可与 `--topics`/`--divination`/`--ziwei`/`--plain` 同用
- `--astro`：输出西洋本命占星盘（十行星黄经/星座/宫位/逆行、上升-天顶-下降-天底、Placidus 宫位、相位表、元素与星座形态平衡、月相）与印度占星（Lahiri 岁差、27 宿与宿主星、月亮星宿、上升），纯标准库内置 Meeus 系列算法；与 `--json` 同用则报告里多一个 `astrology` 字段
- `--numerology`：输出数字学分析（生命灵数/生日数/态度数/成熟数、九宫格与缺失-重复-连线、个人年/月/日、可选姓名分析），与 `--json` 同用则报告里多一个 `numerology` 字段
- `--name` / `--strokes` / `--surname-len`：数字学的姓名参数（拉丁名按 A=1…Z=26 直接求和；中文名需给笔画，如 `--strokes "7,6"`，复姓 `--surname-len 2`；缺笔画时优雅降级为 `name_supported=false`）

脚本失败时先看：Python 是否是运行时自带的。**编码不用管**：输出被管道/重定向捕获时脚本自动切 UTF-8，人直接在 GBK 终端里跑时保留本地编码并替换不可编码字符（`✓`/`─` 不再抛 `UnicodeEncodeError`），不需要再手动设 `PYTHONIOENCODING`。
