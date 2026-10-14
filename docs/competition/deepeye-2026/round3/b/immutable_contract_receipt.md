# B不可删改合同读回与交接补充

COMP-20261013-DEEPEYE/v5；B质量主会话实际完成。此文件追加于PR23，不回改此前冻结件。

合同 **DEEPEYE-HUMAN-LOCK-20261014/revision1**，固定提交 `f5989cd5defce561f9ba98e6b18fc2682945f0a2`：[正文](https://github.com/carolwjade/CarlandFPGA/blob/f5989cd5defce561f9ba98e6b18fc2682945f0a2/docs/competition/deepeye-2026/immutable_scope.md)、[JSON](https://github.com/carolwjade/CarlandFPGA/blob/f5989cd5defce561f9ba98e6b18fc2682945f0a2/docs/competition/deepeye-2026/immutable_scope.json)。独立将 requirements 数组按 `ensure_ascii=False, sort_keys=True, separators=(',', ':')` 转成紧凑UTF-8，共4680字节，SHA256与外部固定值一致：

`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`

实际下载并阅读MD、JSON和校验脚本；独立计算以及执行原脚本均通过。原始文件长度/哈希、逐项卡映射见[机器可读回执](immutable_contract_receipt.json)。脚本只核合同身份和卡映射；产品验收全部 `not_run`。

|条目|读回并接受的范围|状态|
|---|---|---|
|H01|完整可操作、游戏级3D建模/渲染/UI，不能用2D或预设动画替交|接受|
|H02|中央中空透明立方体仅边框，保留三维体积|接受|
|H03|钻具和障碍有完整实体体积及碰撞，不能只测钻尖|接受|
|H04|运行及暂停时均可旋转、切换自由视角|接受|
|H05|自由及随机摆放水层、硬岩等，编辑位置/方向/尺度和规定属性|接受|
|H06|自由选进入/离开面及合法位置，反馈非法或不可达情况|接受|
|H07|蓝入红出、等径且略大于钻具最大截面；整件正确穿越才成功|接受|
|H08|障碍初始布局对控制算法隐藏；无真图、种子、屏幕、精确碰撞oracle泄漏|接受|
|H09|依真实器件/探测技术资料约束的因果观测实时送板，假设与事实分列|接受|
|H10|依真实板观测在线调整三维路线与速度，安全停止不冒充任务完成|接受|
|H11|PC AI实际承担有证据的感知/建图/规划等核心决策|接受|
|H12|保留基于真实板观测的PC直控和回FPGA输出两种完整链路，独立留证|接受|
|H13|全部功能及信息隔离均为最终硬门，不因工时/预算/算力/奖项删减|接受|
|H14|跨机主会话、工作会话、子代理先读并核合同与固定hash，交接100%保留|接受|
|H15|仅同一人类的新明确指令可改合同；困难如实记录，不删除或伪造通过|接受|

表内是读回摘要，精确语义以固定来源的完整条款为准。已按本轮明确要求向本机根AGENTS追加引用/哈希/后续主与worker的强制读取要求，逐字节验证原内容是新文件的完整前缀；没有覆盖原技能、用户规则或既有改动，根AGENTS不进入公开PR。未来主、worker提示分别在[successor_main_prompt.md](successor_main_prompt.md)、[worker_prompt.md](worker_prompt.md)，当前均未启动。

本机融合建议仍是[完整评析](fusion_review.md)与[具体反例/标准](corrections.md)，针对已实际阅读的A v4 `74c854d74baf817beafcbd1d4d52a8dd4450bbca`，不冒称已核更晚终稿：

1. 保留A完整3D、四通道因果观测、真实DAC→ADC→PL和双控制模式；保留B独立块/RAW、时效、资产与捕获证据。不得用换技术主线删减H01–H15。
2. 先修STRESS双轴转弯量化冲突：0.1°/s在0.002m/s下最小非零曲率为0.872665/m，违反0.5/m。建议0.001°/s、int16及合成曲率检查，不加帧长；精确向量见原件。
3. 保留A槽表，采用仍新鲜的latest-completed结果，避免规划150ms超过141.667ms本窗余量而持续饥饿；旧obs年龄及命令TTL各自受限。
4. 三路真实IO捕获必须同一应用批次；34B反馈不要声称还装下未列入帧的原始周期计数。完整体积、初始重叠、旋转扫掠与蓝红门交截独立验证。
5. 原生20Hz传感检测与摘要链路后的AI检测距离分测；两控制模式分别按相同30布局×3次验收，保留不可观测负例和所有失败。
6. A现有AMD主站真实项目加速与并发渲染实测，不以存在性预检替代。资产与RTL可在确定公共接口后按互斥归属并行。

此前冻结件记载“合同原件尚未收到”是当时真实状态；本补充关闭该证据缺口，不回改历史。原冻结 `freeze.json` SHA256为 `e61fd84ec41e38dce5eb13e11f7ead8bfee3be70fa8537cf24535b2c8b940e9c`。新增文件另列 `freeze_contract_append.json`。

A当前终稿唯一writer为 `01a135f1-5a8f-7d71-b036-01b1f683499b`。本回执不授权旧A会话写文档或启动产品；也不创建B继任会话。既有B COMP质量主仅在A最终冻结源码commit/hash及明确START均到齐后，建立唯一 `DEEPEYE-IMPLEMENTATION-20261014/v1` 质量主并核实实际收到/启动，queued或传输ACK不等于交接完成。
