# 第三方组件说明（vendor）

本目录内的 `lunar_python/` 是第三方开源库的**原样副本**，仅供本技能离线运行，未做修改。

| 项目 | 内容 |
|---|---|
| 库 | lunar-python |
| 版本 | 1.4.8 |
| 上游 | https://github.com/6tail/lunar-python |
| 作者 | 6tail |
| 许可证 | MIT（见同目录 `lunar-python-LICENSE.txt`） |
| 用途 | 公历/农历互转、节气时刻、四柱干支、大运流年 |

## 为什么内置

- 技能需要在**无网络、无 pip 安装**的环境直接可用；
- 版本固定，保证排盘结果可复现，不受后续上游变更影响；
- 纯 Python、无第三方依赖，随运行时自带的 Python 即可运行。

## 关于节气精度

lunar-python 的节气/朔望计算移植自**寿星天文历（sxwnl，许剑伟）**体系。实测与官方历书
口径（紫金山天文台/香港天文台）通常在数十秒内一致，例如：

- 2024 立春：官方 16:26:53，本库给出 16:27:07（差 14 秒）。

对绝大多数出生时间而言，这一差异不影响四柱判定；只有出生时刻落在交节前后一分钟内才可能
影响月柱，技能脚本会对此类边界给出警告（见 `references/calculation.md`）。

## 更新方式

```
python -m pip download lunar-python==<version> --no-deps -d tmp
# 解包 wheel 后，将 lunar_python/ 覆盖本目录，并同步更新 dist-info 中的 LICENSE
```

更新后务必运行 `python tests/verify.py`（42 项基准）与 `python tests/verify_regressions.py`（22 项回归），确认全部通过。
