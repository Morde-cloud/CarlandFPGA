# A/B 联合实物展示：当前接口与证据

共同工作：`A-B-JOINT-UART-20261104-R01/v1`；父任务 `DEEPEYE-IMPLEMENTATION-20261014/v1`。同一真人要求B负责G3507、A负责FPGA和仿真，以实际排针UART联动两方向舵机和自转电机，只需大致对应转向/变速。B当前主会话保持 `01a18824-4172-74e2-a13f-f3e3d1e3ed99`。H01–H15/revision2固定commit `817b355887c14cfa9c5d830c8589684f994af082`，requirements SHA256 `2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d`。

## 当前真实状态

现场人类289已确认三线接线完成、无电池、仅两台电脑USB给板及元件供电，观察者在场。此前执行器断电事实已被这次USB-only供电陈述更新；真实舵机/VM电源端接法仍在核对。B没有打开COM9，没有UART/ARM/姿态/电机命令；290单独明确执行一次MCU SystemReset+run，无烧录。

`evidence/state278/READ.json`是本轮一次真实SWD读回，进程exit0。实际MAIN中的11048个已编程字节逐字匹配固定MTR4 HEX；ELF文件SHA `69c5c57e6f896b879bb41a73d4f114180e11a9f16a8894eae6b035893848841f`，目标签名`0x4d545234`、保存中位2088/1961。完整MAIN读回SHA `29db052f45357cb552bd74758a8c9e75cad1a263c0c7e0bfdf6806aac3c40ecb`，原始128KiB文件留在B恢复目录，不把它当ELF哈希。

278时的历史状态**不是READY**：连接后CPU halted、FC_FAULT=4、last_seq=0、armed=0、bus_status=255、双轴原始反馈FFFF/seen0、motor duty0/active0，两个原始RAM快照一致。连接前是否已经halted未知；新读取脚本没有调用run/reset/halt/program/write，保留调试连接可能改变CPU状态的边界。执行器断电时没有有效舵机回传；这是诊断读回成功，不是联动成功或物理零PWM/RPM测量。

随后290已按人类明确“现在开始联调”执行一次受控SystemReset+run（原日志见state290），CPU实际running；3.326s后仍FC_FAULT4/seq0/have_seq0/armed0/反馈FFFF/电机0，未发UART，tx_moves/sync均0。没有自动重复复位。接线完成不代表执行器有效供电；USB-only的实际电源端在核对。当前可准备绑定A新产品身份的DIAGNOSTIC_ONLY STOP/STATUS阶段，完整运动仍禁止。seq0不能跨MCU重启或其它writer继承，初始化1需明确当次唯一writer移交，不是猜序号。

## 接线与分工

两个USB各连原电脑。板间只接三根3.3V逻辑UART线：

|A的PYNQ-Z2|B的LP-MSPM0G3507|
|---|---|
|PMODA1 / Y18，TX|PB7 / UART1_RX|
|PMODA2 / Y19，RX|PB6 / UART1_TX|
|PMODA5，GND|GND|

PMODA6/12电源脚不接。PB7不能仍被XDS/电脑TX驱动，PB6/PB7的临时电脑UART线需隔离；SWD/USB可以保留，但实际随动期间B不反复连接SWD，连接可能暂停MCU。PMODA1/2与RPi GPIO2/3共享pad，不能另接HAT驱动。PA0/PA1是现有舵机总线，不接FPGA；PA12经TB6612驱动电机。

A133已核对当前产品：G05在0x43C00000/4KiB，TRACE在0x43C10000/4KiB，现有1Mbaud内部E4 UART和PMODB1/2/3 PWM及真实回采均保留。新第三`mcu_uart`为AXI UARTLite2.0、50MHz、1152008N1、同产品复位；base/range按新匹配HWH确定。待机PS100MHz不是当前产品100MHz设计。A唯一init owner完成新BIT/HWH/buildID/清单验证；B不操作PYNQ。旧独立UART镜像与硬编码0x43C00000适配器不加载本产品。

## MTR4 协议与宿主程序

完整32B命令/回包表及19个源文件精确哈希见`MTR4_PROTOCOL_AUDIT.md`和`MTR4_PROTOCOL_SOURCE_PINS.json`。基本字段：D3 4C、version1、opcode、uint32LE seq、source；最后2字节为前30字节CRC16-CCITT-FALSE的LE值。source=1PC_DIRECT/2FPGA_OUTPUT/3MANUAL，仅来源声明，不是认证。

|操作|参数及意义|
|---|---|
|1 ARM|只有READY+新鲜双轴回传才可继续；绑定source；不会替代执行器试验|
|2 POSE|yaw int16LE，−9000..9000 centideg；pitch −4500..6800；有限move100..1000ms，默认500ms，双轴一次同步帧|
|3 STOP|解除武装/电机OFF；不取消已经发出的有限舵机动作|
|4 STATUS|消耗新seq；错误/陈旧请求会进入停机处理，不能盲探|
|5 MOTOR|0OFF或250..750‰；独立lease100..500ms，默认300ms；没有RPM反馈|

回包seq是请求echo，协议没有boot nonce或当前高水位查询。不要用历史296/297、seq1或binary-search猜序号。POSE不刷新电机租期，STATUS也不刷新；keepalive100ms仅在真实源新鲜时续租。未知/超时锁定，不自动rearm或重放。

本包`mtr4_reference/`逐字复制原MTR4的实际C/generated/ELF/HEX/map等19文件，含原始构建清单与复制清单。旧`motor_control.h`/`PROTOCOL.md`/`pc.codec.Command`仍有±15deg/300‰旧注释或请求限制，不当当前MTR4接口。当前编码复用已交`output/drill-live-link-20261104/baseline_mtr4/fpga_link/session.py::encode`及`motor_runtime/variable_session.py::encode_motor`；`pc.codec`只复用CRC/回包解码。

原构建清单的candidate/mcu_flashed=false记录的是原编译时刻，不追改历史；本次目标实读证据单列。构建recipe保留原路径和SDK依赖，用作审查，不要求A安装MCU工具链或执行它。MCU固件、EEPROM/零位/限位本轮未改。

同主机Follower沿用source768f887664812b82790cb1c2488a0c1d9db9eed5的显式参考四元数、实际`speed_m_s`与500ms latest-only姿态。A现有唯一NativeClient读取后的原快照送独立IOworker，不增加控制RPC消费者，不用target/slider/yaw_q冒充实际状态。跨机原绝对QPC不直接比较。ARRIVED/fault/STOP/失效使实体独立停；归档JSON不作为live输入。

A134所需新`product_uart_service.py`另在明确独占路径并行实现，等待精确提交；它只绑定已经加载且身份/HWH/BOOT/build真实核对的产品、拒绝G05/TRACE地址重叠，初始motor禁用，无背景独立续租。不能以profile/dict构造自证硬件权限。

## 下一步顺序

1. 三线/共地/XDS隔离已由人类289回执完成；继续核对USB-only时舵机和TB6612 VM实际供电。
2. 明确舵机供电与归中空间后，B新operation处理MCU初始化/必要恢复，回传真实READY、当前last_seq、ARMfalse、motorOFF和原始证据。启动固件可能自动归中，不能称为被动读取。
3. B发唯一UART writer与序号移交；A新产品服务先一次STATUS/STOP，回传原始帧/CRC/新序号。禁止双writer或猜seq。
4. 有人观察的小角度有限姿态、低PWM短时试验，确认方向/限位与实际停止，再接本轮真实软件快照。PC直连试验不是最终FPGA排针链路证明。
5. 完整实物联动/FPGA链路/各模式和原29最终验收分别记录。既有33离线controls、真实C模拟器88UART/7pose、归档10controls、A软件/板样本审阅均不代替本阶段实物验收。
