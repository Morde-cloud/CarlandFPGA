# v5 B研究证据与完成边界

B注册质量主会话路由已只读核为gpt-6-astra/ultra、任务版本5。主会话完成不可变范围读回、模块融合、双轴/模式仲裁、碰撞/穿圈判据、链路选择与最终算术复核。

本轮两个DeepSeek Flash/max只读执行任务实际完成，并已通过child_wait取得持久结果：

- child-ed89e5718a90412b99d237ed7a37ab7c：Godot/Blender官方机制和限制取证。关键碰撞/渲染/导入能力由主会话独立读官方页及官方GitHub原文；不从子任务报告中的引擎发布日期差异推断实际安装版本，以主会话官方API标签为准。
- child-0e50aa88ada246029d867cdc82d27aa0：字段长度/COBS/UART/Ethernet算术。UART结果可复核；Ethernet结果漏了每包36B应用开销，主会话拒绝该数值并修正。子结果10876B/s应加62×36=2232B/s，板段为13108B/s；主会话再加入世界动作、自位姿、计划显示，完整系统为20818B/s。planning_checks.json记录修正，不隐藏原错误。

公开网络来源及本地原始字节哈希见sources.json。部分直接urllib访问403或超时，保留失败；Godot官方GitHub的4.7分支原文下载成功并已核hash；ST资料经web工具成功读取，但未取得原始PDF下载字节，不谎称下载哈希已验。Blender手册web接口曾失败，后来原站GET成功保存原字节。所有下载均资料读取，没有运行其代码。

研究独占路径docs/competition/deepeye-2026/reviews/v5/b/，新分支codex/b/comp-20261013-deepeye-v5-review；基于upstream/main 920ab357ee77f96b8751a593407eb329affc3dcb。根工作区存在其他任务修改，本轮未覆盖。之前v1/v2/v3和A公共文件未改。

v4精确源未收到，单列comparison_v4.md的输入缺项。当前最优建议及规划算术实际完成，精确v4对照尚未完成；queued/传输送达不代表A或C模型已经读取。正式实施、资产生成、引擎安装、RTL仿真、模型训练/推断、综合/实现、板卡和系统实测、采购、服务变更均not_run。
