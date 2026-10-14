# B双轴、控制权属和全链路预算提案

本文件为v5研究建议，待A/C共同冻结后进入新实施会话。不是已运行ABI；不得混用旧14B/32B候选。协议字节和字段是可调整选择，完整人类行为范围不可删。

## 1 坐标及动作

采用右手世界系+X右、+Y上、-Z为钻头前进；长度m、时间s。body_yaw_rate绕局部+Y，body_pitch_rate绕局部+X；正yaw使初始-Z朝-X，正pitch使初始-Z朝+Y。线格式角速度为有符号0.01度/s，速度为uint16的0.1mm/s。q用x,y,z,w四元数并归一化，增量在body侧右乘；不累计Euler角，不把pitch锁在水平面。HUD显示角度只是表示层。

初始候选速度≤50mm/s、双轴角速度各≤30度/s，约束合成角速度和加速度；转弯半径由速度/角速度决定，不能瞬间转向或侧移。钻头装饰自转不改变导航坐标；若自转改变占据体积，采用完整旋转包络或纳入物理子步。6个轴向起姿、穿越±90度pitch、连续组合转向、乱序和零速转向分别验收。

模式PC_DIRECT和FPGA_EXEC均是合法主线。单一动作仲裁器以session＋authority_epoch＋owner识别当前来源；状态机STOPPED→ARMING→ACTIVE→STOPPED。切换、复位或配置变更清理待执行旧命令，不能自动双源叠加。对当前有效会话的停止请求立即令速度/角速度归零；旧会话数据不能重新使能。碰撞评估器只给终局评估，不在每个候选动作上回传可行/不可行答案。

建议白名单明确：任务立方体尺度、进入/离开门及估计自身位姿是任务/自观测参数；障碍真坐标、真材料、世界种子和未来观测均禁止。若A合同对门/自身坐标有更窄解释，先修改白名单，不能自行放开障碍地图。

## 2 新ABI候选与长度

固定头32B：magic2、version1、type1、payload_len2、flags2、session8、frame_seq4、authority_epoch2、config_epoch2、sender_tick_us8；尾CRC32/ISO-HDLC4，共36B开销。CRC测试123456789应为0xcbf43926。多字节小端，payload≤512B；传感数组分片必须有完整obs_id和part/count，重组未全不当有效观测。

以太网UDP每包一帧、长度/CRC/类型/端序校核；UART实验把整帧COBS编码后加0终止，保守线字节上界n+floor(n/254)+2。CRC是差错检测，不作为访问授权或加密证明；接入控制由部署白名单负责。BOOT在STOPPED交换协议/槽表/传感profile/模型/单位哈希，schema不符拒绝启动。

|帧|payload及长度|频率候选|
|---|---|---:|
|OBS_IN / OBS_PL|obs4、sample_tick8、pose_id4、sensor_profile2、count2；64点各range2/signal1/quality1，共276B|各10Hz，注入与回程分别计|
|CMD3D|obs4、req4、yaw2、pitch2、speed2、ttl2、action1、controller1、policy_rev2、request_not_after8，共28B|20Hz|
|ACK3D/STATE|req4、obs4、applied_tick8、remaining2、yaw2、pitch2、speed2、phase1、quality1、faults2、capture_seq4，共32B|20Hz＋2Hz心跳|
|WORLD_APPLY|与CMD3D同28B，当前执行来源已由authority绑定|20Hz，AI/可信板桥→世界|
|SELF_POSE|pose_id4、last_applied_req4、sample_tick8、position12、quaternion16、velocity12、quality2、source2、cov_profile2、reserved2，共64B|20Hz，受噪声模型约束的自位姿→AI|
|PLAN_VIEW|≤256B的已生成局部路径/置信与展示字段，禁止含世界真值|≤5Hz，AI→观察UI，只出不回|

range按profile约定mm，signal/quality不是障碍类别；有效/近界/远界/饱和/unknown用明确码表。pose_id只引用可访问的自位姿观测，不藏障碍坐标。sample_tick与sender_tick分别表示观测和传输时间，不用发送时间伪造新鲜度。两路OBS都必须实际经过板卡路径对应；开启无损压缩只能减少实传，不在最坏预算里预支压缩比。

session建立后req单调递增；每次动作绑定最新可用obs，旧观测/过期拒绝；旧req不得覆盖新req。同键同payload只重报事务结果，不重apply、不刷新期限；同键不同payload拒绝。ACK动态重采当前状态和剩余TTL，首ACK丢失时也以首次发送时刻+原TTL封顶。request_not_after仅在同步误差有界时使用，无时钟保证则采用短保守租期并停；seq/epoch换代在停止握手完成，禁止回绕混认。

## 3 推荐链路与预算口径

主线采用已有板卡以太网/PS DMA入口，独立端点和权限区分世界注入、板处理输出、PC动作。不是购买一个网口替代PL贡献；PL流程旁路时该条硬件验收失败。每包最大原帧548B，低于标准IPv4 UDP常见1472B负载上限；仍记录实际MTU，不依赖IP分片。

板卡段为OBS_IN10＋OBS_PL10＋CMD20＋ACK20＋心跳2，共62包/s。分机完整系统还包括WORLD_APPLY20、SELF_POSE20、PLAN_VIEW5，共107包/s；不能把这些腿当免费。以太网每包在完整应用帧（含36B）之外另加66B（无VLAN：IPv4/UDP28、以太头14、FCS4、preamble/SFD8、IFG12）。板段13108B/s，完整最坏模式20818B/s=166544bps；20%字节重传预留后199852.8bps，占双向合计1Mbps限速档19.98528%。PC_DIRECT可不走板卡动作往返，但保守上限仍按完整FPGA_EXEC计。实际ARP/BOOT/配置/诊断另计入令牌账，剩余容量不是免计费；队列等待/OS抖动另测，均值不能证明时延。

SELF_POSE来自可解释的自身测量/估计，不附任何障碍位置、碰撞法向或material_id；A/C须冻结自观测白名单和误差模型。它同时关联实际last_applied_req，避免PC仅按发送命令假定世界已动。PLAN_VIEW只呈现算法已经得到的地图/路线，不从观察者世界反灌算法。

115200/230400 UART只是板卡段备选和受限链路对照，其余世界通信仍在以太网单列。共享半双工9160B/s，另留20%字节重传；保守把换向次数也乘1.2，64×1.2×2ms=153.6ms/s。115200的占用110.78%不通过，230400为63.07%；full duplex按4470/4690B/s分别核算，不用共享线冒充双向满速。300baud8N1仅30B/s，一份最大OBS315B需10.5s，不可作该完整交互主线。弱链路展示仍保持全部3D/UI/编辑/体积碰撞，只将观测稀疏化、动作减速/停等并明确实验状态，不冒充正常主线通过。

## 4 时效、保护与必须执行的未来卡

候选观测10Hz，模型/规划20Hz复用带age的最新观测；无新观测不能假造新信息。租期初值250ms，控制50ms周期；age阈值、感知可见距离和安全速度联立冻结。停止距离条件至少为v×(观测最大age＋端到端延迟界＋制动时间界)+几何/模型误差≤已知自由空间余量；sensor未知不能作为自由空间。全盲方向无法证明安全时停或主动观察，不能调用碰撞oracle挑路。

FPGA_EXEC的yaw/pitch/speed通过实际IO编码并独立回采，capture_seq绑定req、mode、authority_epoch；PC_DIRECT由世界动作服务回报真实应用，不伪称板捕获。两模式均测试观测断流、进程崩溃、重复/乱序、错epoch、旧ACK、切模式中延迟包、过期重试及安全停止。断开FPGA执行反馈时该模式停；PC_DIRECT不需要FPGA动作ACK，但其依赖的PL观测失效时按age门停止。

可实施的IO候选为三路输出CLK/DATA/FRAME，经三根真实跳线进入三路独立输入；A确认Pmod针脚及3.3V电气连接后冻结XDC。本轮不给未经实板确认的针脚号。每个捕获帧24B：session8、authority_epoch2、req4、yaw2、pitch2、speed2、flags2、CRC16/CCITT-FALSE2；先按小端组成字节，每字节MSB先行，CPOL=0/CPHA=0、100kHz，192bit需1.92ms。CRC向量123456789=0x29b1。FRAME限定完整帧，接收端同步实际输入并只提交CRC/会话/epoch/req全部匹配的三量原子快照；不得从软件命令寄存器拼接捕获值。断开任一跳线、交换yaw/pitch编码、旧req重放、半帧复位必须失败；flags含STOP/VALID，超时输出停止且下游不保留上一速度。捕获证明数字执行信号确实经过IO，不宣称现实机械动作。内部租期仍由本地状态机执行，不能因一次旧捕获成功而无限续行。

新实施会话必须先冻结字节黄金、坐标/单位/符号向量、20万随机往返、百万样本数据处理、双轴PIO回采、单轴故障、授权切换、2小时满负载和最坏窗口/分位数；其中代码/仿真/综合/实现/实板证据分开。本轮只算规划，不运行以上产品测试。
