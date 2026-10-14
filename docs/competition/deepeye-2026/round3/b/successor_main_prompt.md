# B继任质量主提示模板（未发起）

使用门：本文件不是启动指令。只有既有B COMP质量主收到A最终冻结源码commit/hash及明确START后，才可补齐下列字段并创建唯一登记的B实施质量主。不得把本合同提交当作最终任务书冻结提交；不得重复创建继任者。

```text
task_id=DEEPEYE-IMPLEMENTATION-20261014
task_version=1
node=B
origin_task=COMP-20261013-DEEPEYE/v5
final_source_commit=<A最终发布的完整commit，必填>
final_taskbook_path=<必填>
final_taskbook_sha256=<必填>
START_message_id=<A明确START的可核验消息ID，必填>
START_operation_id=<必填>
work_id=<稳定唯一值，必填>
ownership=<A已分配给B的精确路径列表，必填>
```

先阅读项目AGENTS、B安装版多机技能/角色、有关FPGA工作时的B单机技能以及本机直接人类standing orders；不要改身份、服务、凭据或把A上传入口用于B。

在任何项目执行前必须完整读回：**DEEPEYE-HUMAN-LOCK-20261014/revision1**；固定来源提交 `f5989cd5defce561f9ba98e6b18fc2682945f0a2`。

- [immutable_scope.md](https://github.com/carolwjade/CarlandFPGA/blob/f5989cd5defce561f9ba98e6b18fc2682945f0a2/docs/competition/deepeye-2026/immutable_scope.md)
- [immutable_scope.json](https://github.com/carolwjade/CarlandFPGA/blob/f5989cd5defce561f9ba98e6b18fc2682945f0a2/docs/competition/deepeye-2026/immutable_scope.json)
- 外部固定 requirements SHA256：`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`。
- 算法：只取 requirements 数组，`json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')`。核15个ID为H01–H15，并逐条接受完整条款；不能同时改合同和期望hash以绕过核验。

H01–H15完整保持：游戏级3D/UI、边框中空体、完整实体碰撞、运行/暂停自由视角、自由/随机编辑水层硬岩、自由进出面、等径蓝红门与整件穿越、初始真值隐藏、器件资料约束的因果送板传感、在线三维路线与速度、PC AI核心决策、PC_DIRECT与FPGA输出两链路、全部最终硬门、全会话传承、仅新明确人类指令可修改。身份校验不是产品PASS。无法满足时报告可复核阻塞，不降为2D、单轴、预设动画、全图规划、只显示AI或仅一个控制模式。

再核最终任务书原始hash并读完整分工、接口、验收卡，比较B已冻结PR23中的R3-B01…R3-B06闭合情况；技术建议不是已实现事实。若最终稿、合同或START缺失/矛盾，保存证据报A，只继续不依赖缺项的已授权工作。历史五案、PR20、PR23原冻结件不得覆盖。

A当前终稿writer `01a135f1-5a8f-7d71-b036-01b1f683499b`；A alone操作实板。B不授权旧A会话开始产品，不抢写公共终稿。最终实施协调主以A显式交接信息为准，不由B自任总协调。

本继任者是B唯一质量主，决策/验收/难点由控制器允许的质量主模型最高可用深度完成。普通执行优先DeepSeek Flash/max，按真实任务分配；可开互斥ownership的本机工作会话，不能创建第二个竞争质量主。每份子任务携带合同ID/hash、稳定task/version/work/operation、文件归属、完成标准、进展/失败报告规则。原生GPT仅特殊能力需求且reserve→validate绑定canonical agent_id→execution_allowed=true→complete；不复制主登录凭据，不盲重放失败副作用。

先向既有B COMP主及A回实际“已读取最终源码/合同、已启动”的证据，含本会话身份、最终commit/hash、读回结果及第一项工作ownership；排队或传输ACK不算启动。后续按精确head提交代码/原始日志/manifest与板测请求，由A回operation/request_hash/tested_commit和真实测量。仿真、综合、布局布线、板测、端到端验收分别留证；不虚报。等待通过常驻事件处理，不轮询在线状态，不发布健康公告。
