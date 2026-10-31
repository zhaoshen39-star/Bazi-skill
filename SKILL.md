---
name: bazi
description: 八字排盘与命理分析：按节气精确计算四柱、藏干、十神、纳音、大运、流年，并做结构力旺衰、子平真诠取格与成败、扶抑/调候/通关/病药四法喜用、十神结构、神煞、大运流年引动与应期分析；自带“通俗版”输出层把结论翻成人话，“专题推测”层把分析落到婚恋/事业/财富/学业/健康/六亲/迁移/人际八个生活领域，另有“多术数层”并列小六壬/梅花易数/六爻纳甲/称骨/星座/生肖纳音/紫微斗数做交叉参考，以及“跨体系融合层”把八字、紫微、西洋/印度占星、数字学、民俗按九域聚合成一致与张力分析（不输出概率）。
whenToUse: 用户要排八字/看四柱、问大运流年、分析五行旺衰/格局/喜用、问婚恋/事业/财运/学业/健康/家人/迁移/人际等具体领域，或想按出生时间做性格与运势倾向分析时；用户嫌解释太术语、要“说人话”的总结与预测时；用户想要其它命理体系（求签/算卦/称骨/星座/紫微）或要“多体系印证”时；用户问“世界上公认比较准的命理学/跨体系融合”时。
---

# 八字排盘与分析

用脚本做**确定性排盘**，再按固定框架解读。排盘是历法计算，必须准确；解读是术数模型，必须透明、克制、可质疑。

## 一、先补齐输入

排盘至少需要：

| 输入 | 说明 | 缺失时 |
|---|---|---|
| 公历出生日期 | 年-月-日 | 必问；若用户给农历，用 `--lunar`（闰月加 `--leap`），或先换算公历 |
| 出生时间 | 尽量到分钟 | 必问；实在未知则加 `--time-unknown`：时柱会按假定 12:00 占位并标记不可靠，旺衰/喜用等含时柱的结论仅供参考 |
| 出生地 | 用于时区与经度 | 中国默认 `Asia/Shanghai`；要精确到真太阳时则问经度（常用城市经度见 `references/cities.md`） |
| 性别 | 决定大运顺逆 | 必问（不算大运时可省略，但结果价值大减） |

额外约定：

- 时间是**出生证明上记录的钟表时间**，不要自己先做夏令时或真太阳时换算，脚本会处理。
- 中国 1986–1991 年实行过夏令时：脚本用 IANA 时区数据自动扣除，输出里会写明。
- **境外出生**（非 UTC+8）或使用真太阳时时，脚本会自动分两个标尺：年/月柱与起运用「出生瞬间的北京时间（UTC+8）」，日/时柱用「本地标准时或真太阳时」。输出里的「前一节/后一节」已换算到排盘采用的时间，可直接对照。
- 出生在 23:00–23:59 属晚子时，日柱有两种流派：默认 `--sect 2`（日柱不换日、时干按次日）；`--sect 1`（日柱换次日）。脚本会同时给出两个流派的结果并警告，**要问用户或两家都给**。
- 出生在节气交节前后 30 分钟内，月柱/年柱对时间校正是敏感的；脚本会输出警告，务必向用户复核。

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

# 18) 奇门遁甲时家转盘（节气定局/九宫/九星八门八神/值符值使）
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male --qimen

# 19) 一屏人话摘要（≤400 字，适合直接回消息）
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male --focus-year 2026 --brief

# 20) 只看某一个专题域（love/career/wealth/study/health/family/move/people，可逗号多选）
<python> <skill>/scripts/bazi.py --date 1990-06-15 --time 12:00 --sex male --focus-year 2026 --topic love
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
- `--brief`：只输出一屏内的人话摘要（≤400 字，隐含 `--plain`，不输出技术版），适合快速回消息
- `--topic <域[,域]>`：只保留指定专题域（隐含 `--topics`），值域 love/career/wealth/study/health/family/move/people，支持逗号分隔与中文逗号
- `--divination`：追加「多术数交叉参考」（小六壬/梅花易数/六爻纳甲/称骨算命/西洋星座/生肖纳音/紫微斗数），给出各体系的起卦/落宫/卦象/骨重/宫星与断语，并汇总「多体系交叉参考」；与 `--json` 同用则报告里多一个 `divination` 字段（文本模式下附在最后）
- `--ziwei`：单独输出紫微斗数命盘（十二宫、主星、六吉六煞、年干四化、大限、要点与局限）；与 `--json` 同用则报告里多一个 `ziwei` 字段
- `--qimen`：输出奇门遁甲时家转盘（节气与日干支定局、阴阳遁、三奇六仪、九宫、九星八门八神、值符值使、旬空马星、要点与局限）；与 `--json` 同用则报告里多一个 `qimen` 字段
- `--fusion`：跨体系融合层：把八字、紫微、西洋占星、印度占星、数字学、民俗（小六壬/称骨/星座）各自的方向信号按九域聚合，输出「一致/多数/分歧/对立/单体系参考/信号相抵/证据不足」与整体一致度；缺体系标「证据不足」，不换算成概率；与 `--json` 同用则报告里多一个 `fusion` 字段（文本模式下融合段附在最后），可与 `--topics`/`--divination`/`--ziwei`/`--plain` 同用
- `--astro`：输出西洋本命占星盘（十行星黄经/星座/宫位/逆行、上升-天顶-下降-天底、Placidus 宫位、相位表、元素与星座形态平衡、月相）与印度占星（Lahiri 岁差、27 宿与宿主星、月亮星宿、上升），纯标准库内置 Meeus 系列算法；与 `--json` 同用则报告里多一个 `astrology` 字段
- `--numerology`：输出数字学分析（生命灵数/生日数/态度数/成熟数、九宫格与缺失-重复-连线、个人年/月/日、可选姓名分析），与 `--json` 同用则报告里多一个 `numerology` 字段
- `--name` / `--strokes` / `--surname-len`：数字学的姓名参数（拉丁名按 A=1…Z=26 直接求和；中文名需给笔画，如 `--strokes "7,6"`，复姓 `--surname-len 2`；缺笔画时优雅降级为 `name_supported=false`）

脚本失败时先看：Python 是否是运行时自带的；控制台乱码则设置 `$env:PYTHONIOENCODING="utf-8"`。

## 三、解读流程（按顺序，不要跳步）

1. **先核盘**。读输出的「输入与时间校正」和「四柱」：时间是否是标准时/真太阳时、处在哪个节气区间、日柱是否遇到子时流派问题。出现 `⚠` 警告时先处理警告，再解读。
2. **定日主与月令**。日主强弱先看脚本的结构力评分（柱位权重 × 藏干分层 × 刑冲合折损），再用「得令 / 得地 / 得势」三项复核（脚本已列出柱位、藏干层次与受损情况），不要只报一个标签；评分靠近分界线时脚本会给低置信度提示，此时应写「介于两档之间」。
3. **取格局**。按子平真诠：月令本气→中气→余气之透干优先，皆不透取月令本气；禄月/刃月单列。再看顺用/逆用、相神是否到位、成格条件与破格因素，给出「成格 / 成中有败 / 败中有救 / 破格 / 待定」并说明依据（`references/interpretation.md`、`references/v3-rules-source.md`）。
4. **定喜忌**。扶抑（旺衰）、调候（《穷通宝鉴》120 格表：日干×月支，寒暖指数只定急缓）、通关（两党对峙取桥）、病药（找最伤命局的一处）四法各自出结论，再按「特殊格 > 破格救应 > 调候急需 > 病药 > 扶抑」仲裁；四法冲突时**写明冲突**，不要硬给单一答案。同时看用神是否「有力（透干且有根）」，否则降级为「有根无透 / 有透无根 / 虚浮无根」。
5. **看十神结构**。哪一神最旺、有无典型组合：官印相生、杀印相生、食神制杀、食伤生财、伤官配印、比劫夺财、枭神夺食、财星破印等。脚本按「透干 > 半透 > 月令」自动识别并给出层级与成员柱位，**只列透干/月令级**；它只是结构提示，成格仍要看旺衰与破格因素。
6. **看大运流年**。表内「综合喜忌」＝基调分（用神角色加权：用神×2.2、喜神×1.3、忌神×-1.9、仇神×-1.0）×权重 ＋ 引动分（与命局的合冲刑害、伏吟、反吟、半合、岁运并临）。先看基调定大方向，再看引动定「哪一年因何动」：脚本给出领域标签（事业/财/感情/健康等）、置信度与应期提示（合待冲、冲待合、填实）。只讲结构与倾向，不编具体事件。
7. **神煞作辅参**。神煞次于五行旺衰与格局，不要用神煞下重结论。
8. **落到具体领域（用户问婚恋/工作/钱/学业/健康/家人/搬迁/人际时）**。跑 `--topics`，按「倾向 → 依据 → 有利年份 → 需留意年份 → 建议」讲；先给结论和时机，再解释一条最关键的依据即可，不要把八域全倒给用户——只讲他问的那一两域，其余一句带过。专题结论必须回指技术层（如「财星偏弱」对应财富域、「夫妻宫受冲」对应婚恋域），不能另起一套说法。
9. **跨体系融合（用户问「世界公认比较准的命理学」「多体系印证」「融合」时）**。跑 `--fusion`：先看 `systems` 里哪些体系可用（缺的标「证据不足」，不得当 0 分读），再看九域的一致/分歧，最后看时机与整体一致度。汇报时先讲「哪些领域多体系同向、哪些有张力」，再解释张力来源（共享先验 ≠ 独立验证）；不把「多体系一致」说成更准，不换算概率或准确率。

详细规则见：

- `references/calculation.md`：排盘约定、精度、可复算的参数（含节气/子时/真太阳时/大运起运），以及 v3 旺衰/格局/喜用/引动的完整权重表。
- `references/tables.md`：干支五行、藏干、十神、纳音、十二长生、神煞、合冲刑害表。
- `references/interpretation.md`：十神象义、格局成败、旺衰喜用、大运流年、表达边界。
- `references/v3-rules-source.md`：v3 规则的文献依据（子平真诠取格法、《穷通宝鉴》120 格调候表、大运流年引动与应期规则），带出处与可信度标注，便于核对与改参。
- `references/divination-tables.md`：多术数层的底表与出处（称骨四表与歌诀、小六壬六宫、梅花先天数与十八占、六爻纳甲/八宫世应/六亲六神、星座日期、紫微十四主星/四化/六吉六煞），附机读 Python 字面量与可信度分级；冲突版本并列保留。
- `references/fusion-systems.md`：跨体系融合层的方法论底稿——各体系定位与流派、三种「准确性」（计算精度/预测效度/跨体系一致性）的可验证性与证据清单（含 Carlson 1985 双盲、Dean & Kelly 2003 综述、巴纳姆效应）、三条硬约束（只输出一致/分歧、权重≠效度、缺体系不得当无信号），带出处与可信度标注。
- `references/cities.md`：常用城市经度与时区，供真太阳时校正。
- `references/cli-reference.md`：命令行参数全表、输出模式与 JSON 字段索引。
- `references/methodology.md`：方法学总览（历法→旺衰→格局→喜用→大运流年→通俗/专题/多术数/融合）。
- `references/output-contract.md`：`--json` 输出契约速查（分层字段与稳定性约定）。
- `references/output-style.md`：给用户写解读时的语气、结构与边界（含「不许说」清单）。
- `references/interpretation-flow.md`：从排盘到落地的解读流程（八步）与常见追问模板。
- `tests/verify.py`（42 项固定基准，节气锚点取自外部历书）、`tests/verify_independent.py`（24 项独立公式日/时柱交叉校验）、`tests/verify_relations.py`（13 项关系/格局单测）、`tests/verify_regressions.py`（22 项时区/农历/旺衰/输入回归）、`tests/verify_optimizations.py`（12 项岁运并临/反吟/流月日期/三柱旺衰）、`tests/verify_v2.py`（49 项十神结构/喜忌打分/神煞/干支关系/JSON 契约）、`tests/verify_v3.py`（94 项结构力旺衰/取格成败/四法仲裁/引动应期/CLI 契约/稳定性）、`tests/verify_plain.py`（45 项通俗版：结构完整/去术语/预测可读/CLI 契约/特殊格兼容）、`tests/verify_topics.py`（295 项专题层：八域结构/依据与窗口合法性/去噪/性别语义/特殊格/CLI 契约/确定性）、`tests/verify_calendar.py`（228 项排盘历法交叉验证：JDN 日柱、五鼠/五虎遁、节气边界、大运起运、真太阳时、子时/闰日边界）、`tests/verify_divination.py`（168 项多术数层：小六壬/梅花/六爻纳甲表与断语层/称骨四表与闰月/紫微十二宫/编排与 CLI 契约）、`tests/verify_ziwei.py`（502 项紫微斗数层：12 宫/主星/亮度/三方四正/格局三态/大限主题/iztro 交叉验证）、`tests/verify_fusion.py`（337 项跨体系融合层：体系可用性/九域投票/共识语义/张力/时机/退化/CLI 契约）、`tests/verify_astrology.py`（468 项西洋+印度占星：18 夹具对 PyEphem 星历精度（日月≤0.1°、行星≤0.3°）/星座边界/逆行/相位/宫位/四轴几何/Vedic/CLI 契约）、`tests/verify_numerology.py`（203 项数字学：归约与主数/九宫格/姓名/个人周期/CLI 契约）、`tests/verify_cases.py`（194 项古典命例对照：子平真诠 64 例的取格/顺逆/成败/用神对照，`--report-only` 作测量口径，当前一致率约 89%）、`tests/verify_qimen.py`（2543 项奇门遁甲：拆补定局/九宫/三奇六仪/九星八门八神/值符值使/旬空马星/六甲伏吟/CLI 契约）。十七套合计 **5253 项**，一键跑：`python tests/run_all.py`（全绿才退出 0）；任一失败都应视为基准被破坏。

## 四、输出格式

**默认两层：先通俗、后技术。** 用户没要求技术细节时，只给通俗版；对方要依据、要细节、或自己懂八字，再展开技术版。

### 4.1 通俗版（默认先给这个）

- 生成方式：`--plain-only` 直接出文本；`--json --plain` 出结构化 `plain` 字段（脚本实现见 `scripts/plain.py`，规则数据驱动、可复算）。
- 固定顺序（缺一不可）：一句话 → 你是个什么样的人 → 你的长处 → 容易卡住的地方 → 钱和工作 → 感情 → 身体 → 现在走到哪 → 接下来几年怎么走 → 给你三条建议 → 名词翻译 → 说明。
- 语言规则：
  - 不甩术语。五行说「水/金/木/火/土」并跟一句生活化解释；十神说成「钱、工作、学习、表达、同辈」这类角色；「用神/忌神」说成「最需要的力量 / 容易添乱的力量」。
  - 不报内部数字（评分、占比、权重）。强弱只说「底子薄 / 均衡 / 能扛」。
  - 预测写成「会有什么感觉 + 适合做什么 + 避开什么」，一年 2–3 句；不写「必然/一定」，不报具体事件。
  - 每条建议要能落地（方向、平台、现金、身体），不写空话。
- 长度：正文 800–1500 字；「性格」「长处」「短板」各 3–5 条，超了压到 3 条。

### 4.2 技术版（对方要依据或要细节时再给）

按这个顺序：排盘（四柱+时间校正）→ 旺衰（三得复核+置信度）→ 格局与喜用（取格/成败/四法仲裁/用神力量/调候）→ 结构（十神组合、五行偏枯、合冲刑害）→ 大运流年（基调+引动+领域+应期）→ 倾向与建议 → 不确定性与免责。

### 4.3 用户明说「说人话 / 看不懂 / 通俗点」时

直接用 `--plain-only` 的正文照给，最多按语气微调；不要夹技术段。对方再追问依据时，只展开技术版对应的那一小节。

### 4.4 专题推测（用户问具体领域时）

- 生成方式：`--topics`（文本附在最后）或 `--json --topics`（取 `topics` 字段）；想直接发给人就用 `--plain-only --topics`。
- 八域：婚恋与伴侣、事业与职业方向、财富与赚钱方式、学业与考试、健康与体质、六亲与家庭、迁移与方位、人际与贵人。
- 每域固定给：倾向（顺/偏顺/中平/偏吃力）+ 置信度（高/中/低）→ 结论 → 依据 → 有利年份 → 需留意年份 → 建议 2–4 条。
- 用法规则：
  - 只回答用户问的域，其余一句带过；不要把八段全贴出去。
  - 先说结论和「哪几年」，再挑 1–2 条依据解释；年份只写到年，不编具体事件。
  - 有利年份里出现「动而不顺」标注的，要老实说「这年有动静但基调不利，宜谨慎」。
  - 健康域只说作息与方向、提醒就医，不作诊断；财运域不承诺收益。

### 4.5 多术数交叉参考（用户问「其它命理/星座/求签/算一卦」或要交叉印证时）

- 生成方式：`--divination`（文本附在最后）或 `--json --divination`（取 `divination` 字段）；可与 `--plain-only`、`--topics` 同用；奇门遁甲单独用 `--qimen`。
- 体系：小六壬（当下问事落宫）、梅花易数（时间起卦：本卦/互卦/变卦/体用）、六爻纳甲（本卦/变卦/六亲/六神/世应；**断语层 v2**：月建旺衰×日辰作用×动变→每爻强度，六亲能量，用神状态，结构倾向（偏顺/中平/阻力偏大/用神偏弱/不明），简化应期）、称骨算命（骨重+歌诀，含闰月与男女歌诀）、西洋星座（太阳星座速览）、生肖·纳音·三元九运，以及紫微斗数（`scripts/ziwei.py` 随包：12 宫/主星/六吉六煞/四化/大限；也可单独 `--ziwei`）与奇门遁甲（`scripts/qimen.py`，`--qimen`：节气定局/九宫/九星八门八神/值符值使）。
- 六爻断语层读法：先看用神（问财=妻财、问功名=官鬼、问文书=父母、问子女出行=子孙、问朋友竞争=兄弟、问自身=世爻）；用神在场看强度、不在本卦标「伏藏」；再看忌神峰值与卦性（六冲/六合）；「偏顺/阻力偏大」是结构描述，**不是事件预测**。权重为工程近似（月建 1.0 基准 + 日辰 ±0.2 + 动爻 +0.15），不同师承取值有别。
- 用法规则：
  - 先说明各体系是**各自独立的模型，不是同一件事的多次验证**；结论不一致时并列说「不同侧面」，不排序、不挑顺耳的说。
  - 小六壬与六爻属于「当下问事」的取象，只代表起卦这一刻，不能替代长期判断；不要对同一问题反复起卦。
  - 称骨/星座/小六壬属民俗或流行占法，只能说「文化参考」，不能当决策依据；紫微与八字也要标明流派差异。
  - 不因为多个体系「都说不顺」就加重恐吓语气，也不因为「都说顺」就承诺结果。

### 4.6 跨体系融合（用户问「世界上公认比较准的命理学」或要多体系印证时）

- 生成方式：`--fusion`（文本附在最后）或 `--json --fusion`（取 `fusion` 字段）；可与 `--topics`、`--divination`、`--ziwei`、`--plain` 同用。
- 体系与权重（表达「信息量与可核对程度」，**不是效度**）：八字 1.0、紫微 0.9、西洋占星 0.9、印度占星 0.7、数字学 0.5、民俗 0.4；某个体系缺文件/缺输入时标「证据不足」，不得当 0 分。
- 九域：性格、事业、财富、感情、健康、家庭、迁移、学业、人际。每域给：方向信号（−2…+2）、等级（明显偏顺/偏顺/略偏顺/中平/略偏吃力/偏吃力/吃力）、共识标签（一致/多数/分歧/对立/单体系参考/信号相抵/证据不足）、逐体系票与依据。
- 时机：聚焦年的大运流年（八字）＋ 大限（紫微）＋ 个人年（数字学）＋ 当下落宫（民俗）聚合。
- 用法规则：
  - 先讲一致域（互相支持的材料），再讲张力域；张力是「信息不足或模型不同」，不要硬圆成一条结论。
  - 说明各体系共享历法/黄道/干支等先验，相关来自同源而非独立证据，**一致不等于验证**。
  - 不输出概率、准确率、百分比；权重不是效度排序；不因「多体系一致」就加确定性，也不因「都说差」而加重恐吓。
  - 缺体系时明确写「证据不足」，不用「中性」冒充「无信号」。

### 4.7 西洋/印度占星与数字学（用户明确要这两类体系时）

- 生成方式：`--astro`、`--numerology`（文本附在最后）；`--json` 同用则分别写入 `astrology`、`numerology` 字段；`--fusion` 会自动调用它们，无需重复指定。
- 西洋盘：上升/天顶决定宫位框架，太阳看外显风格、月亮看情绪需要、宫位看领域落点、相位看内部张力；讲「倾向与结构」，不逐个行星断事件。
- 印度盘：以恒星黄道（Lahiri 岁差）看月亮星宿与上升星座；27 宿给「性情与节律」，不做吉凶判决。
- 数字学：生命灵数=出生日期逐位求和归约（11/22/33 主数保留）、生日数=出生日、态度数=月+日、成熟数=生命灵数+表达数、个人年=出生月+日+聚焦年；九宫格看缺数/重数/连线。属现代民俗与流行心理学，只作「文化参考 + 自省提示」，不作预测。
- 共同边界：占星的天文计算精度（可复算、角秒级）只说明「盘算得准」，不说明「星盘与人生的对应」成立；不要用占星/数字学替代医学、法律、投资判断。

## 五、表达边界（必须遵守）

- 八字是传统术数与民俗文化，**不是科学结论**。不要把旺衰、格局、喜用说成对未来的确定预测。
- 不断言寿命、疾病诊断、灾祸、官司结果、投资收益、婚姻必然成败；不使用恐吓性话术，不推销「改运」「化煞」服务。
- 涉及健康只谈传统五行对应与作息建议，并明确「不能替代就医」。
- 出生时间不确定时，明确列出哪些结论会随时辰改变（时柱、子女、晚年、部分大运细节）。
- 术数内部本就有流派差异（子时换日、真太阳时、起运法、旺衰权重）；给出选择并说明影响，而不是假装唯一正确。
- **通俗版不等于更确定**：翻成人话时同样不能加「必然/一定/注定」，预测仍要写成「倾向 + 建议」；通俗版可以省掉推导过程，但不能省掉不确定性提示（`plain.limits` 必须保留）。
- **多术数不等于更可信**：小六壬/梅花/六爻是三套不同的取象模型，不是同一结论的三次交叉验证；称骨、星座、小六壬只能当文化参考。体系间一致时可以说「几种说法倾向一致」，不能说「因此一定成立」；不一致时如实并列。紫微、八字都属传统术数，流派差异同样存在。
- **融合层不输出概率**：跨体系融合只给「一致/分歧/证据不足」与方向性等级；权重是信息量排序、不是效度；多体系一致不能升级为确定性结论，缺体系时如实写「证据不足」。西洋/印度占星的计算精度（星历可复算）只说明天文算得准，不说明星盘与人生的对应关系；占星预测效度的双盲实验为阴性（见 `references/fusion-systems.md`）。

## 六、JSON 契约（v3，可依赖）

`--json` 在 v2 字段之上新增（旧字段保留，向后兼容；v2 字段见各 `method` 说明）：

- `analysis.strength`：v2 键（`ratio/score/label/same_party/other_party/de_ling/de_di/de_shi_heads/special_hints`）＋ `version:3`、`confidence`、`party_shares{比劫,印星,食伤,财星,官杀}`、`force{五行:力}`、`de_ling_detail`、`de_di_detail[{text,quality,damaged}]`、`de_shi_detail`、`structure_notes[{kind,slot,detail}]`、`contribs[]`、`special{type,kind,reasons}`。
- `analysis.pattern`：v2 键 ＋ `version:3`、`category`、`used_stem`、`take_method`、`shun_ni`（顺用/逆用）、`xiang_shen[{party,role}]`、`status ∈ 成格 / 成中有败 / 败中有救 / 破格 / 待定 / 特殊格（…）`、`status_note`、`candidates[]`（本气格＋透干十神格，取格口径透明化）、`good[{id,desc,rank,severity,members}]`、`bad[{id,desc,rank,severity,resolved,members}]`、`rescue[{for,desc,rank,members}]`、`month_damage[{detail}]`、`confidence`；`severity=hard` 参与成败判定（相神/破格神类），`soft` 只作隐忧（旺衰/月令冲刑害），`resolved=true` 表示救应已达透干/月令本气强度、病解。
- `analysis.yong_shen`：v2 键 ＋ `version:3`、`methods{fuyi,tiaohou,tongguan[],bingyao[]}`、`arbitration{rule,order,reasons,conflicts}`、`shen_roles{五行: 用神|喜神|忌神|仇神|闲神}`、`yong_shen_force[{element,status,share,tou,roots,note}]`；`tiaohou` 文本来自《穷通宝鉴》120 格表（`tiaohou_element` 为表定首选五行）。
- `chart.dayun.list[].timing`、`chart.liunian[].timing`：`{ganzhi, base{label,score}, events[{type,detail,delta,slot}], activation_score, score, label, gods, themes, confidence, major_events, yingqi, note}`；`score ∈ [-4,4]`，`label` 同喜/偏喜/中性/偏忌/忌；`major_events` 为显著引动，`yingqi` 为应期提示。`favorability`（v2 基调分）仍保留。
- `method`：`version:3`、`strength_model`、`pattern_model`、`yong_shen_model`、`flow_favorability`、`flow_timing`、`wuxing_weights`、`disclaimer` 等口径说明。
- `plain`（仅 `--plain` / `--plain-only` 时出现）：`{version, one_line, profile[], strengths[], watchouts[], money_work[], relationship[], health[], current_decade, forecast[{year,ganzhi,level,confidence,what,do,avoid}], actions[], limits[], glossary[{term,plain}], model}`；`level ∈ 顺/偏顺/平稳/偏吃力/吃力`，`confidence ∈ 比较确定/中等把握/不太好说`。通俗版只由报告数据生成，不含硬编码个案。
- `topics`（仅 `--topics` 时出现）：`{version, model, limits[], topics[8], year_index[]}`；每个 topic = `{id ∈ love/career/wealth/study/health/family/move/people, title, summary, level, confidence, basis[{kind,detail}], windows[{year,ganzhi,kind ∈ 机遇/发力/波动/注意,note,score,label}], risks[], advice[]}`；`year_index[{year,ganzhi,label,score,domains[{domain,kind,note}]}]`。专题只做「结构定倾向 + 引动定应期」，年份来自 `chart.liunian[].timing`。
- `divination`（仅 `--divination` 时出现）：`{version:3, model, limits[], systems{xiaoliuren,meihua,liuyao,chenggu,zodiac,quick_view,ziwei}, available_count, cross{topics[5], note}}`；小六壬=`{steps[3], palace, luck, element, direction, image, verse, plain}`；梅花=`{ben_gua{name,upper,lower,dong_yao}, hu_gua, bian_gua, ti_yong{ti,use,relation,text}, input}`；六爻=`{version:"v2", ben_gua{name,gong,gong_element,kind,shi,ying}, bian_gua, dong_yao, yao[6]{name,gan_zhi,liuqin,liushen,shi_ying,dong,bian,zhi,yue_state,yue_score,day_score,day_notes[],strength,kong,bian_relation}, liuqin_count, questions, analysis{month_zhi,month_element,day_ganzhi,day_element,kong[],gua_type,liuqin_energy{六亲:{count,positions[],max,sum,dong}},yong_shen[{question,god,state,score,present}],judgement[{question,tendency,basis}],shi_ying,yingqi[{type,zhi[],detail}],caveat}}`；称骨=`{available, parts{year,month,day,hour}, weight, verse, verse_female, sex, leap, confidence, limits}`；星座=`{sign, element, trait}`；quick_view=`{shengxiao, year_ganzhi, nayin, jiumei}`；紫微=`{version, method, lunar{lunar_year,month,day,leap_note}, ming_gong{zhi,gan,ganzhi}, shen_gong{...}, wuxing_ju{num,name,element}, ziwei{zhi,palace}, tianfu{...}, ming_zhu, shen_zhu, palaces[12]{name,zhi,gong_ganzhi,main_stars,ji_stars,sha_stars,sihua,daxian}, daxian[12], sihua[4], patterns[], summary[], limits[]}`。
- `ziwei`（仅 `--ziwei` 时出现）：紫微斗数命盘对象，含断语层字段：`brightness{levels,table,source,unmarked_as_ping}`、`main_star_brightness[14]`、`san_fang_si_zheng[12]`、`daxian_flow[12]{order,palace,zhi,ganzhi,start_age,end_age,start_year,end_year,themes[],confidence,stars,sihua[],basis}`、`palaces[i]{...,star_brightness[],sf_sz{sf,sf_zhi,sz,main_stars}}`、`patterns[{name,level(成/半/不成立),palaces[],stars[],detail}]`（13 个标准格局全三态输出）、`limits[]`（7 条）。
- `qimen`（仅 `--qimen` 时出现）：`{version, method, input{四柱/节气/元}, ju{number, dun(阳遁/阴遁), yuan(上元/中元/下元), jieqi}, xunshou, zhifu, zhishi, palaces[9]{gong,gong_num,gan_di,gan_tian,star,door,god,kong,ma}, sanqi_liuyi{...}, summary[], limits[]}`；模块缺失时降级为 `{available:false, note}`，不影响其它层。
- `fusion`（仅 `--fusion` 时出现）：`{version:"v1", model, inputs{birth, focus_year, ...}, systems[{key ∈ bazi/ziwei/western/vedic/numerology/folk, name, weight, available, basis}], domains[9]{id, title, signal(-2…2), level, consensus, votes[{system, domain, signal, evidence}]}, tensions[{domain, detail}], timing{year, ganzhi, signal, level, votes}, overall{agreement(0…1 或 null), confidence(高/中/低), summary, systems_available, systems_total}, limits[]}`；`level ∈ 明显偏顺/偏顺/略偏顺/中平/略偏吃力/偏吃力/吃力/证据不足`，`consensus ∈ 一致/多数/分歧/对立/单体系参考/信号相抵/证据不足`（口径见 §4.6）。
- `astrology`（仅 `--astro` 或 `--fusion` 时出现）：`{version, method, input, planets[10]{key,name,lon,sign,sign_cn,degree,element,modality,retrograde,speed,house}, angles{asc,mc,desc,ic}, houses{system,cusps[12]}, aspects[{a,b,type,angle,orb}], balance{elements,modalities,hemispheres}, moon_phase{phase,angle,illum}, vedic{ayanamsa,sidereal_planets,nakshatra{name,index,pada,ruler,ruler_cn}}, summary[], limits[], warnings[]}`。
- `numerology`（仅 `--numerology`/带姓名参数/`--fusion` 时出现）：`{version:3, method, input, life_path{number,is_master,root,chain,keywords,title,summary}, birthday, attitude, maturity, personal{year,month,day,focus_year,reference_date,note}, grid{cells,missing,repeats,lines}, name{available,name_supported,expression,soul_urge,personality,five_grid,...}, summary[], limits[]}`。

## 七、方法学一句话版

年柱以**立春交节时刻**为界，月柱以**十二节**为界，日柱按**儒略日连续干支**（2000-01-07 = 甲子日）推算，时柱用**五鼠遁**；节气时刻来自随包内置的寿星天文历系内核（与官方口径通常相差数十秒内）。旺衰用**结构力模型**：柱位权重（月支 0.40、日支 0.18、年支 0.10、时支 0.12、天干 0.06–0.07）× 藏干本/中/余气分层 × 十神亲和，再按刑冲合害折损、三合三会加成，全部权重写在 `references/calculation.md`。格局按子平真诠取格并判成败救应；喜用按扶抑/调候（《穷通宝鉴》120 格）/通关/病药四法合参并仲裁；大运流年是「基调分（用神角色加权）＋ 引动分（合冲刑害、伏吟、反吟、岁运并临）」的规则打分，给领域与置信度、应期提示，只表倾向，不是事件预测。**通俗版**是这套结果的翻译层（`scripts/plain.py`）：五行/十神换成生活语言、数字换成「薄/均衡/能扛」，预测换成「感觉+适合+避开」，不改变任何技术结论。**专题层**（`scripts/topics.py`）把同一套结果按八域重组：命局结构（十神配置、宫位、旺衰调候）定倾向，大运流年引动定应期，每域给依据与置信度、有利/留意年份、可执行建议；它是同一批数据的另一种切法，不新增预测源。**多术数层**（`scripts/divination.py`，紫微另见 `scripts/ziwei.py`）另起几套独立模型：小六壬按农历月日时数宫、梅花易数按先天数时间起卦（本卦/互卦/变卦/体用生克）、六爻纳甲按八宫纳甲起六亲六神世应（断语层再把月建旺衰、日辰作用、动变折算成爻强度与用神状态，只给结构倾向）、称骨按四表骨重、星座按太阳日期区间；奇门遁甲（`scripts/qimen.py`）按节气与日干支拆补定局、排九宫九星八门八神——它们与八字**不是同一套推导**，只做并列参考，不说「互相验证」，更不叠加成确定性结论。**跨体系融合层**（`scripts/fusion.py`）不新增断语：八字/紫微/西洋占星/印度占星（`scripts/astrology.py`，内置 Meeus-VSOP87 截断算法，无星历文件依赖；可复算精度约角秒级，但天文精度≠预测效度）/数字学（`scripts/numerology.py`）/民俗各自出票，按九域聚合成方向信号与共识标签，按「信息量权重」加权取均值，缺体系标「证据不足」；体系间相关多来自共享先验，因此「一致」只作材料、「分歧」即信息不足，不换算概率、不作验证（论证见 `references/fusion-systems.md`）。
