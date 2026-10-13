# 矿脉深瞳 B 机第一轮独立研究交付

正式任务为 `COMP-20261013-DEEPEYE/v1`。板卡固定 PYNQ-Z2，11 月 4 日提交，实物按需求后续准备。当前只研究和规划，不实现、不烧板、不采购；尚未进入三机外部融合。

1. [五套完整候选与研究评分](CANDIDATES_FULL.md)：每案的完整系统、HX370 CPU/GPU/NPU职责、实体任务、数据、带宽/延迟、成本、验收与否决门，以及逐模块融合。
2. [完整项目计划书与阶段任务书](PROJECT_TASKBOOK_DRAFT.md)：G0至G8、分工与ownership建议、BOM、截止倒排、指标、板测准备和恢复。
3. [第一份独立五案比较](B_FIVE_CANDIDATES.md)：补齐正式派工细项前的独立思路与反例。早期封存仍保留，新的正式完整候选以第1项为准。
4. [来源与边界](SOURCES.md)、[证据审查](REVIEW_DECISION.md)、[预算脚本](budget_check.py)及[evidence](evidence/budget-result.json)。脚本只做规划算术，未做RTL/综合/实现/实板。

先行B桌面任务的材料保留在 `docs/project-plan/B/2026-10-13/`，并未覆盖。本文所在目录是收到A正式派工后的交付归属。A发来的原始任务不包含其他机器方案；B未读取A/C研究成果，只向A回执接收。封存后仅交A，等待A开启第二轮。

复算：`python -X utf8 docs/competition/deepeye-2026/round1/b/budget_check.py`。结果表明条件性4:1可满足部分平均预算，但RAW及部分半双工工况不可满足；不代表压缩率、时延或队列稳定已实测。
