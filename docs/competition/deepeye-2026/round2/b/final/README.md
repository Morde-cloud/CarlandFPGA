# B 跟进交付：最终基线与开发任务

2026-10-14，`COMP-20261013-DEEPEYE/v3`，工作项 `B-group-followup-20261014`。本次依据原飞书群的 A/C 定稿公告，实际下载其固定提交的正文和任务清单，再与 B 已完成外评对齐。此前五案、第二轮评析和失败反例保持原样。

- 全项目正文以 [A 的 v3 修订1](https://github.com/carolwjade/CarlandFPGA/blob/2c424a9780d69b01fc0e5ea9db963ed86cfb9dde/docs/competition/deepeye-2026/taskbook_v3.md)及其 [15页 PDF](https://github.com/carolwjade/CarlandFPGA/blob/2c424a9780d69b01fc0e5ea9db963ed86cfb9dde/docs/competition/deepeye-2026/deepeye_taskbook_v3.pdf)为当前协调基线。
- [B 任务书补充](B_TASKBOOK.md)：模块取舍、六张 B 任务卡、接口交接条件、依赖和失败处理。
- [B 可机读任务](b_tasks.json)逐项映射 A 的20卡 DAG；[A 原始任务清单](a_execution_baseline.json)保留实际下载字节。
- [来源审计](source_audit.json)记录 A/C 精确提交、字节哈希、可匹配的发布清单；不公开群成员标识或私有消息全文。
- [文档验收结果](validation.json)由 `python -X utf8 docs/competition/deepeye-2026/round2/b/final/verify_plan.py` 产生。它只核对文档、依赖和历史保全，不运行产品仿真或板卡。

本补充是 B 的规划交付，不代替 A 的公共接口文件，不称三机联合签署、R03 已完成或项目实测通过。下一步在 A 冻结 R03 接口/向量并登记具体工作归属后，从 B01 开始；只有 A 操作物理板。
