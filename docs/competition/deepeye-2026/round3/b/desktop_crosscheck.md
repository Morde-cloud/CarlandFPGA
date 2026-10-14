# B桌面补充的定点核验与归档

COMP-20261013-DEEPEYE/v5；既有B COMP质量主完成本次核验。仅追加研究证据，不修改此前冻结件，不重复计为第二个P0，不启动产品。

实际读取桌面 `stress-curvature-counterexample.json`，1730字节，原始SHA256 `fa27657d8bd240e12826789fa70079407b702da6a96314cdfab32ca2e8bf7195`；原文件含CRCRLF，未改写它，也不拿规范化JSON的hash冒充原字节hash。其输入为A `74c854d74baf817beafcbd1d4d52a8dd4450bbca`。另读取桌面已完成的融合审计，原始SHA256 `5ab6aa17a45dec465b14ec616c27823cd2e4bb2da0c049f896290a514fea0079`；没有接管或重新执行桌面子代理。

本主重新计算两组数值，并直接读取同一A提交的任务书及执行JSON核对DAG。结果见[desktop_crosscheck.json](desktop_crosscheck.json)。这些是数学和文档检查，不是RTL、构建、板测或系统性能结果。

|角速码单位|v=0.002m/s时最小非零曲率|最小合法转弯速度|结论|
|---|---:|---:|---|
|0.1°/s|0.8726646259971648/m|0.003490658503988659m/s|超过STRESS最大速度；没有合法非零转向|
|0.001°/s|0.008726646259971648/m|0.00003490658503988659m/s|存在可表示转向，仍须每步检查合成曲率|

公式为 `omega=radians(unit)`、`kappa=omega/v`、`v_min=omega/0.5`。桌面数值均与独立计算一致，确认已有[R3-B01](corrections.md)而不是新增缺陷。统一int16、0.001°/s及FAST每轴±15000仍占2字节；合成限制 `hypot(yaw_code,pitch_code)*0.001*pi/180 <= actual_speed*0.5` 必须在量化后和加减速每个积分步检查，零速双轴为0。命令解码、capture/PWM分辨率、profile hash和向量必须同步。改善软件字段不能证明IO已能分辨；这些修复仍待A最终规范和实施证据。

桌面DAG补充经本主直接核对，29卡无环、未知依赖0。无环只证明顺序自洽，不能证明文件归属和新bit证据齐全。建议A在最终稿明确两项：

1. **G01启动输入和测试writer。** 原G01 dependencies为空，但运行验收需要A维护的 `project.godot`/导出配置；`simulator/tests/test_asset_contract.gd` 也要明确writer。建议A交最小工程骨架的精确commit、Godot补丁/模板/hash并拥有共同验收入口，B仅交已分配资产/world资源、资产清单与测试输入；A/B不可同时写同一测试。B可先制作资产，G01运行验收等待骨架输入齐全。原PR23已指出骨架前提，本次明确测试归属缺口。
2. **G05新增RTL后的构建门。** 原G05依赖B06，却继续增加control3d及三路回采RTL；前序B06结果不能证明新增RTL的时序和板上镜像。建议在G05内部固定顺序：新源码冻结→control3d仿真→对该新源码重跑B06同等构建/实现检查→生成配对bit/hwh及哈希→A按这一精确提交板测。保留实现后WNS≥0、TNS=0、关键未约束0、错误DRC0；不要把B06再反向依赖G05形成环。

G05构建证据至少关联源码commit、源/约束及工具版本、构建命令、时序/DRC报告、bit/hwh各自hash、板测request_hash/operation_id/tested_commit。退出标准包含明确拒绝“新源码配旧bit”“bit/hwh错配”“只给前序B06报告”的反例，再由A提供真实新镜像结果。这是验收规范建议，没有在本轮执行这些反例或上板。

本次队列消息中“桌面创建继任”与其较新状态存在时间差。现有桌面更新状态及最新本机人类常驻指令一致指定**既有B COMP质量主为唯一继任创建者，桌面观察核验而不重复创建**。因此保留当前AGENTS和提示，不按延迟消息改回旧归属。最终冻结源码commit/hash与明确START仍须齐全，queued不算实际承接。本轮未创建继任主或worker。

合同 `DEEPEYE-HUMAN-LOCK-20261014/revision1`、requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804` 和H01–H15全部保留。当前最优仍是[fusion_review.md](fusion_review.md)的模块融合，增加上述交付约束；不能把“模拟展示”改读为纯回放、可泄漏真图、无实际PC AI或删掉任一完整控制链路。终稿发布及唯一实板操作仍由A负责。
