# 历史实验结果

数值取自原始实验与冻结提交复评。以下各节保留各自协议、场数与计分单位。JSON 保存未舍入数值和原汇总的 SHA-256。 [数据与出处](historical.json)

## Pokémon Showdown · 同批独立测试

6 个分层、5 个公开对手、96 对队伍。每个程序 1,920 场，每个 Agent 系统一次研究。胜 1，平 0.5，负 0。

| 系统 | 场数 | 得分率 | 相对 baseline（百分点） | 策略失败 | 达回合上限 |
| --- | --- | --- | --- | --- | --- |
| 原始启发式 | 1920 | 53.91% | 0.00 | 0 | 0 |
| GPT-6.1 Sol / Codex | 1920 | 89.27% | 35.36 | 0 | 0 |
| DeepSeek Flash / 官方 SDK | 1920 | 77.14% | 23.23 | 0 | 0 |
| DeepSeek Flash / Claude Code | 1920 | 71.35% | 17.45 | 0 | 0 |
| Qwen3.8-Max / Claude Code | 1920 | 65.89% | 11.98 | 0 | 2 |
| Qwen3.8-Max / Qwen Code | 1920 | 53.91% | 0.00 | 0 | 0 |

原汇总：`experiments/showdown-deepseek-claude-v1/summary.json`。

## Showdown · 同一提交按分层拆分

每个分层 320 场，同一系统的六行来自同一个程序。

| 分层 | 原始启发式 | GPT-6.1 Sol / Codex | DeepSeek Flash / 官方 SDK | DeepSeek Flash / Claude Code | Qwen3.8-Max / Claude Code | Qwen3.8-Max / Qwen Code |
| --- | --- | --- | --- | --- | --- | --- |
| ou-hidden-loadouts | 58.75% | 93.75% | 77.19% | 67.50% | 72.19% | 58.75% |
| ou-weather-cores | 58.75% | 95.00% | 74.38% | 73.75% | 63.44% | 58.75% |
| ou-hazards-pivot | 56.88% | 92.50% | 82.50% | 74.69% | 71.25% | 56.88% |
| ou-setup-denial | 58.13% | 89.69% | 78.44% | 78.12% | 71.56% | 58.13% |
| gen9-monotype | 42.50% | 77.19% | 75.31% | 62.81% | 54.69% | 42.50% |
| gen9-ubers | 48.44% | 87.50% | 75.00% | 71.25% | 62.19% | 48.44% |

原汇总：`experiments/showdown-deepseek-claude-v1/summary.json`。

## Showdown · 配对差值

同队伍对在各分层内重采样。区间描述这批对战带来的不确定性；系统间重复研究的方差未知。

| 对照 | 差值（百分点） | 95% 下界 | 95% 上界 |
| --- | --- | --- | --- |
| DeepSeek / Claude Code 相对 原始启发式 | 17.45 | 13.70 | 21.25 |
| DeepSeek / Claude Code 相对 DeepSeek Flash / 官方 SDK | -5.78 | -9.58 | -2.03 |
| DeepSeek / Claude Code 相对 GPT-6.1 Sol / Codex | -17.92 | -21.09 | -14.74 |
| DeepSeek / Claude Code 相对 Qwen3.8-Max / Qwen Code | 17.45 | 13.70 | 21.25 |
| DeepSeek / Claude Code 相对 Qwen3.8-Max / Claude Code | 5.47 | 1.77 | 9.06 |

原汇总：`experiments/showdown-deepseek-claude-v1/summary.json`。

## Showdown · 早期协议与迁移

每行是自己的配对测试。首轮开发集的 91.67% 与该行独立测试使用不同队伍和种子。

| 协议 | 场数 | 起点得分率 | 冻结程序得分率 | 启发式得分率 |
| --- | --- | --- | --- | --- |
| 固定开发集 | 768 | 25.65% | 66.67% | 69.40% |
| 轮换训练阵容 | 1152 | 74.13% | 79.86% | 69.01% |
| 中性提示 | 1152 | 68.75% | 87.67% | 68.75% |
| 旧提交迁移到扩充分布 | 360 | 53.33% | 43.33% | 53.33% |

原汇总：`experiments/showdown-pilot-v1/private/summary.json`、`experiments/showdown-generalization-v2/private/final/comparison.json`、`experiments/showdown-neutral-v3/private/final/comparison.json`、`research/showdown-effect-v1/comparison.json`。

## Showdown · 扩充分布的历次抽样

各批次使用当时的独立抽样或已冻结对照。相同程序可出现多次，这些行不计为新的 Agent 研究重复。

| 实验批次 | 程序 | 场数 | 得分率 |
| --- | --- | --- | --- |
| showdown-native-expanded-v1 | 原始启发式 | 1920 | 52.81% |
| showdown-native-expanded-v1 | DeepSeek Flash / 官方 SDK | 1920 | 76.77% |
| showdown-sol-native-v1 | 原始启发式 | 1920 | 56.56% |
| showdown-sol-native-v1 | GPT-6.1 Sol / Codex | 1920 | 89.58% |
| showdown-sol-native-v1 | DeepSeek Flash / 官方 SDK | 1920 | 74.84% |
| showdown-qwen-native-v1 | 原始启发式 | 1920 | 53.33% |
| showdown-qwen-native-v1 | DeepSeek Flash / 官方 SDK | 1920 | 75.99% |
| showdown-qwen-native-v1 | GPT-6.1 Sol / Codex | 1920 | 90.42% |
| showdown-qwen-native-v1 | Qwen3.8-Max / Qwen Code | 1920 | 53.33% |
| showdown-qwen-claude-v1 | 原始启发式 | 1920 | 53.91% |
| showdown-qwen-claude-v1 | DeepSeek Flash / 官方 SDK | 1920 | 77.14% |
| showdown-qwen-claude-v1 | GPT-6.1 Sol / Codex | 1920 | 89.27% |
| showdown-qwen-claude-v1 | Qwen3.8-Max / Qwen Code | 1920 | 53.91% |
| showdown-qwen-claude-v1 | Qwen3.8-Max / Claude Code | 1920 | 65.89% |

原汇总：`experiments/showdown-native-expanded-v1/summary.json`、`experiments/showdown-sol-native-v1/summary.json`、`experiments/showdown-qwen-native-v1/summary.json`、`experiments/showdown-qwen-claude-v1/summary.json`。

## Showdown · 简单策略对照

旧对手池和队伍配置的校准数据。

| 批次 | 策略 | 场数 | 得分率 |
| --- | --- | --- | --- |
| showdown-baselines-v1 | random | 96 | 27.08% |
| showdown-baselines-v1 | maxpower | 96 | 18.75% |
| showdown-baselines-v1 | damage | 96 | 47.92% |
| showdown-baselines-v1 | heuristic | 96 | 60.42% |
| showdown-baselines-v2 | random | 192 | 24.48% |
| showdown-baselines-v2 | maxpower | 192 | 29.17% |
| showdown-baselines-v2 | damage | 192 | 44.79% |
| showdown-baselines-v2 | heuristic | 192 | 66.67% |

原汇总：`runs/showdown-baselines-v1/summary.json`、`runs/showdown-baselines-v2/summary.json`。

## Celeste Classic · 固定入口

帧数越低越好。100m 宿主删除搜索用了 120 次试跑。其余四关的起点取自上游输入记录，最优性未知。

| 关卡 | 系统或对照 | 起点（帧） | 最终（帧） |
| --- | --- | --- | --- |
| 100m | 宿主删除搜索 | 94 | 67 |
| 100m | DeepSeek / research-008 | 67 | 67 |
| 300m | DeepSeek / 受限环境 v2 | 70 | 70 |
| 400m | DeepSeek / 受限环境 v2 | 64 | 64 |
| 600m | DeepSeek / 受限环境 v2 | 48 | 48 |
| 700m | DeepSeek / 受限环境 v2 | 46 | 46 |
| 300m | DeepSeek / 开发环境 v3 | 70 | 70 |
| 400m | DeepSeek / 开发环境 v3 | 64 | 64 |
| 600m | DeepSeek / 开发环境 v3 | 48 | 48 |
| 700m | DeepSeek / 开发环境 v3 | 46 | 46 |

原汇总：`runs/celeste-100m-demo/trial-0001/result.json`、`runs/celeste-100m-demo/summary.json`、`experiments/celeste-100m/deepseek-research-008/private/summary.json`、`experiments/celeste-suite-v2/results.json`、`experiments/celeste-suite-dev-v3/results.json`。

## 2048 · 独立测试

每局最多 2,000 步，相同随机流。

| 策略 | 局数 | 平均得分 | 失败局数 |
| --- | --- | --- | --- |
| 贪心 baseline | 128 | 3,088.59 | 0 |
| DeepSeek 冻结程序 | 128 | 33,666.22 | 0 |

原汇总：`experiments/2048-neutral-v1/private/final/comparison.json`。

## 2048 · 简单策略对照

同一次基线校准的随机、固定优先级和贪心策略。

| 策略 | 局数 | 平均得分 | 失败局数 |
| --- | --- | --- | --- |
| random | 128 | 1,135.94 | 0 |
| priority | 128 | 2,405.03 | 0 |
| greedy | 128 | 3,114.53 | 0 |

原汇总：`runs/2048-baselines-v1/comparison.json`。

## 2048 · 同批预算复测

人工参考使用 C++ 封装；原 Agent 接口只公开支持 JavaScript。超限局记零。阈值参考 126/128 局触及步数上限。

| 策略 | 局数 | 平均得分 | 失败局数 |
| --- | --- | --- | --- |
| upstream_raw | 128 | 0.00 | 128 |
| upstream_parallel | 128 | 0.00 | 128 |
| upstream_guarded | 128 | 8,739.62 | 0 |
| upstream_guarded_threshold | 128 | 45,291.47 | 0 |
| deepseek_frozen | 128 | 33,929.06 | 0 |
| deepseek_no_guards | 128 | 5,319.12 | 92 |

原汇总：`research/2048-upstream-comparison/stable-rerun/comparison.json`。

## shapez · 固定地图

每格为 60 秒正确交付数。延长预算沿用前轮工作；官方 Harness 轮从原 baseline 重启。未提交方案不计分。

| 运行 | 切割 | 染色 | 堆叠 |
| --- | --- | --- | --- |
| 原始 baseline | 23 | 14 | 11 |
| shapez-neutral-v1 | 23 | 14 | 11 |
| shapez-neutral-v2 | 23 | 14 | 11 |
| shapez-extended-v1 | 84 | 15 | 11 |
| shapez-native-v1 | 85 | 38 | 11 |

原汇总：`experiments/shapez-neutral-v1/private/summary.json`、`experiments/shapez-neutral-v2/private/summary.json`、`experiments/shapez-extended-v1/private/summary.json`、`experiments/shapez-native-v1/private/summary.json`。

## shapez · 未提交方案与人工对照

这些复评说明已发现的可行解；正式提交仍按上表计分。

| 产物 | 任务 | 复评交付数 |
| --- | --- | --- |
| 早期未提交切割 | cut_rotate | 70 |
| 宿主缩短切割路径 | cut_rotate | 73 |
| 后续未提交切割 | cut_rotate | 84 |
| 未提交堆叠布局 | stack | 12 |

原汇总：`research/shapez-unsubmitted-v1/result.json`、`research/shapez-optimality-check-v1/evaluation/result.json`、`research/shapez-unsubmitted-v2/result.json`、`research/shapez-stack-audit-v1/counterfactual/result.json`。

## Mindustry · 基础生产 v2

回放修复后用原提交重评，每种蓝图每图独立重评五次，按四图平均。

| 产品 | 地图数 | 原始 baseline | DeepSeek 冻结蓝图 |
| --- | --- | --- | --- |
| copper | 4 | 40 | 342 |
| graphite | 4 | 18.25 | 153.75 |
| silicon | 4 | 21.25 | 96 |

原汇总：`research/mindustry-replay-fix-v2/reevaluation/summary.json`。

## Mindustry · 基础生产逐图复评

对应上一表的 12 张地图。

| 地图 | 产品 | 原始 baseline | DeepSeek 冻结蓝图 |
| --- | --- | --- | --- |
| copper-choke | copper | 40 | 386 |
| copper-long | copper | 39 | 376 |
| copper-near | copper | 41 | 436 |
| copper-sparse | copper | 40 | 170 |
| graphite-choke | graphite | 18 | 180 |
| graphite-long | graphite | 18 | 175 |
| graphite-near | graphite | 19 | 184 |
| graphite-sparse | graphite | 18 | 76 |
| silicon-choke | silicon | 21 | 96 |
| silicon-long | silicon | 21 | 93 |
| silicon-near | silicon | 22 | 99 |
| silicon-sparse | silicon | 21 | 96 |

原汇总：`research/mindustry-replay-fix-v2/reevaluation/summary.json`。

## Mindustry · 中断运行

用户报告额度用尽，日志没有记录明确的额度错误。这一轮单列。

| 系统 | 地图数 | 提交与起点逐字节相同 | 独立最终评测数 |
| --- | --- | --- | --- |
| Qwen3.8-Max / Claude Code | 12 | 是 | 12 |

原汇总：`runs/mindustry-qwen-claude-v2/execution-audit.json`。

## Mindustry · 复杂生产 v3

复杂链只完成人工可行性验收。每个布局三次改变 JSON 排列顺序，并逐次核对回放，模型调用为零。

| 任务 | 原始 baseline | 人工双线布局 |
| --- | --- | --- |
| plastanium-bio-oil | 61 | 122 |
| blast-compound | 51 | 102 |
| surge-alloy | 18 | 36 |

原汇总：`research/mindustry-complex-production-v3/acceptance/acceptance.json`。
