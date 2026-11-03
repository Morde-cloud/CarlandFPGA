# 已加载联合产品的 UART 服务

`product_uart_service.py`服务A134/A135的新产品接口。它复用原MTR4编码、`VariableDisplaySession`、`SequenceJournal`、`UartLite`和`Follower`，不修改baseline/MCU固件/零位/EEPROM。模块导入不打开PYNQ、串口、SSH、MMIO或线程，没有Overlay、下载、PS时钟或MCU复位入口。A原有唯一产品init负责人仍负责下载匹配BIT/HWH和实际CSR/BOOT/build/PS时钟验证。

入口：`ProductUartService.attach(root, profile, transfer, absolute_state_dir)`。`root`必须为A现有负责人实现的`RootLoadedProduct`能力对象，JSON/profile中的“已验证”布尔值不授予权限。Python对象本身并非密码学认证；信任根仍是A已授权原负责人及它的真实读取/交接核验代码。

## A应实现的唯一Root接口

- `simulation: bool`，真实A必须False；离线假MMIO测试必须True。
- `read_current() -> ProductBinding`，调用A已有实际只读身份路径。绑定字段为`operation_id/request_hash/boot_id/build_id/bit_sha256/hwh_sha256/mapping_sha256/fclk_hz`、`g05/trace/uart`描述及`product_clock_net/product_reset_net`。G05/TRACE描述为`IpDescriptor(name,vlnv,phys_addr,addr_range)`。UART为`UartDescriptor`，额外含`clock_hz/baud/data_bits/parity/stop_bits/clock_net/reset_net`。不要只返回一份静态profile副本。
- `read_hwh_bytes() -> bytes`，返回当前匹配产品实际HWH原字节，服务核SHA256并解析MODULE/PARAMETER/PORT/MEMRANGE。
- `authorize_transfer(profile, BTransfer) -> None`，用当前真实人类布线/无XDS并驱与B认证回执核验操作、MCU观察/独占writer/序号及scope；拒绝时抛异常。不能由读取JSON的`ready=true`自动实现。
- `authorize_motor(profile, transfer) -> None`，在现场供电/方向/低速观察等已确认之后独立显式授权；拒绝时抛异常。
- `open_uart_mmio(binding)`，再次核当前操作/BOOT/TRACE build后，仅映射已加载的那个UART并返回有`read/write`方法的MMIO对象。服务不提供真实MMIO工厂，不猜G05/TRACE身份寄存器偏移。

`Profile(expected_binding, run_id, source)`的expected约束应来自A固定构建/部署清单，不应仅复制未知当前产品自证。服务反复调用真实`read_current()`，任何读取失败/身份变化即锁定；恢复为相同值也不自动复用。A必须为每次新load采用新operation/BOOT绑定，禁止同operation偷偷重载。

UART必须是独立`mcu_uart`、`xilinx.com:ip:axi_uartlite:2.0`、50MHz、115200/8N1、与产品相同clock/reset。base/range来自当前HWH与实际描述且完全一致，允许真实4KiB等range，不强制64KiB。拒绝重叠G05 `0x43C00000/0x1000`或TRACE `0x43C10000/0x1000`。现有内部E4串口/PWM不接管。服务不自动清FIFO，初始化发现非空/错误/非TXempty时拒绝，保留未知现场。

## B序号交接与两种scope

`BTransfer(operation_id, transfer_id, mcu_observation_id, last_seq, evidence_sha256, scope)`只记录B观察及移交。MTR4没有wire boot nonce，`mcu_observation_id`不是虚构的硬件UUID；A Root须核验B当前原始证据和全过程供电/唯一writer连续性。不得沿用旧296/297，不猜序号，不用STATUS探测高水位，也不自动reset或重放。

- `DIAGNOSTIC_ONLY`：仅允许connect的STOP/STATUS、显式`status()`和末端`stop()`；禁ARM/pose/motor/Follower。合法DISARMED诊断回包保留原result3，不提升为READY。当前FAULT/halted等原始观察不能当运动移交。
- `MOTION_READY`：除B真实READY/OFF/unarmed与新序号交接，connect后的实际fresh/healthy双轴反馈也必须通过。电机仍默认禁用。`enable_motor()`只调用Root独立授权并开permission，不发送电机命令；创建Follower还需显式`motor_enabled=True`。

`connection.event='uart_connected'`与`mcu_feedback_ready_observed`、`actuator_READY_authorized`分列。UART有回包不等于舵机可动，更不等于到位/RPM/物理零输出或正式验收。

使用Root为本物理UART指定的同一长期state目录。稳定`mcu_uart.owner.lock`用内核独占锁跨operation防并发，不删除锁文件/破锁。新operation目录、B证据一次性消费记录、绑定与durable序号journal在任何UART写前独占落盘；崩溃/未知保留原记录，自动重连/续旧journal被拒绝。即使换operation，同一B evidence hash也不得重复消费。重新移交需B新的真实观察与A显式核验。

## 同主机随动

连接只发STOP/STATUS，无ARM。A把现有唯一`NativeClient.state()`得到的已接受快照交自己的单独IO worker；worker调用`service.make_follower(reference_xyzw, ...)`再`push/tick`，源与Follower在同一QPC主机。source取真实`PC_DIRECT/FPGA_OUTPUT/MANUAL`，run_id绑定实际本轮。只读实际四元数/`speed_m_s`及phase/fault/STOP，不用target/sliders/yaw_q冒充。没有新RPC消费者或独立后台keepalive；归档schema不能当live输入。

未知/过期末端STOP合并为一次可审计尝试，初始化STOP不抑制未来末端STOP，正常motor0 OFF也不冒充永久终态。baseline内部异常尾部、service、Follower及close复用同一终态STOP结果，不重复发送。若loaded身份变化，服务不向可能已经重载为其它IP的旧地址写STOP，而是记录失败并保持锁定。所有UART发送前意图及原回包记录fsync；原电机短租期仍是失联后的独立边界。STOP不能取消已发出的有限舵机运动，ACK不是到位。

测试仅新机制假Root/MMIO/HWH，不能证明A真实HWH/PYNQ parser/新build/串口线或实物随动。主合同H01–H15/revision2固定SHA `2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d`保留，实际两H12和原29正式验收另列。
