# 执行与来源状态

正式任务COMP-20261013-DEEPEYE/v2。负责人B正式质量主会话，控制器路由gpt-6-astra/ultra；本轮融合判断、接口修正和验收决定均由该主会话作出。B第一轮由B桌面质量主会话完成，本正式会话只读复用，不把它改称本会话独立新写。人类新范围由A回传原控制器消息后升v2；本报告没有声称B亲自读回原群消息，也不发布私人成员标识。

|原件|精确可获取位置|本机核验|
|---|---|---|
|A最佳|[best.md](https://raw.githubusercontent.com/carolwjade/CarlandFPGA/1412d6d70985848fff1332479c98a8be54f15e87/docs/competition/deepeye-2026/round1/a/best.md)，同目录freeze.json|4640B，SHA256 d9716026589a298e4554d018c9478539cf9a2840458129e246e1134173911416；冻结时间2026-10-13T16:23:34.937482Z。已核best与freeze，不冒称本轮逐文件复核A全部候选|
|B最佳|[PR13](https://github.com/carolwjade/CarlandFPGA/pull/13)，head ec0675dfb2f1f86c6201b2d1e2ea27d3f5a04ff8；docs/competition/deepeye-2026/round1/b/PROJECT_TASKBOOK_DRAFT.md|32186B，SHA256 6088bb2de9e220f751f0623774f0cba91c0b88ba3fdcfcd0abf179ad483439c8；冻结16:12:22.122304Z。公共PR API读回head及17项manifest Git blob全符，见b_round1_hash_audit.json|
|C最佳|[best_proposal.md](https://raw.githubusercontent.com/carolwjade/CarlandFPGA/ab527e20eb7bc8a0cdeab0409943ec17510830fe/docs/competition/mine_plan_20261013/c/best_proposal.md)，同目录freeze_manifest.json|6085B，SHA256 5243500c579b3a24e097b2a1d41e038d09128b635648968f313a00bf0a1889af；冻结16:05:55.279944Z。公开commit可取，不依赖是否已有PR|

C清单六项中的best、event_progressive、npu_model、traditional_sparse、independent_review这五份Markdown原始字节hash一致。第六项budget_result.json公开Git blob为922B、26个LF，SHA256为7262a4843883dddac32dc0cafbee9f3f81cca2da8011bcac01d028d5a375d5da；将LF转换为CRLF后才等于freeze中的87fb5e57a7e24cfbbcedc0f28885d38a8ae349beb7e05e08bd90b68a24ea1f11。保留“原始不等、规范化后等”的两个事实，不改C原件，不把文本等价写成raw全部匹配。C原本首轮评分权重与用户研究权重不同，第二轮不重写首轮评分，也不按分数投票。

本轮实际工作：公开资料读取与本地原文复核、只读电脑枚举、Git blob及SHA核对、规划算术、文档写入与检查。项目训练、RTL仿真、综合、布局布线、PYNQ板测、传感器测试、NPU/GPU推理、采购、注册、驱动安装、服务变更均not_run。A的主机规格是A报告的实际枚举，不是B实测；已有384次BRAM测试不充当本项目新设计证明。

委派执行事实：

- child-a3172b404bcb47b5b17b23656e1eee76：DeepSeek Flash/max，v1只读平台来源核查completed。v2只复用其中经主会话重新读取的官方事实，不继承3.2的规则判断；未授权其选择架构或评分。
- child-77635b54628e4e0198ee30eabd02ba4c：DeepSeek Flash/max，v2只读字节、算术、交叉引用核查completed。确认帧合计和线速预算；发现G5/G7引用误标，已改为G5；v1帧总长/载荷口径已补清。日期摘要不是完整阶段卡，预算文档历史owner与新实施owner不冲突。子报告将原始速率写作乘8是其笔误，主会话独立复算为6400/8=800bps，仍超过300；未采用错误算式。
- 两项子任务均无写入、板卡或消息权限。第一轮两个早期取证子任务completed且已收持久结果，未把它们未封存的临时文件混入正式B第一轮。

本轮首次发送B原件给C、C原件位置给A均返回delivered=true，这只是传输结果；模型实际完成以原件、提交及上述主会话产物为准。新v2报告完成与否也以本目录封存清单为准，不以peer ACK作验收。

预算重算用 budget_check.py，仅执行Python有理数/文档检查，不调用硬件、模型、构建或外部服务。来源缓存位于本机项目.planning/competition-20261013/，公开sources.json保留URL和hash，私人控制器文件未加入提交。公开文档统一UTF-8 LF，冻结后Git blob必须逐项匹配。
