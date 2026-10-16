# TRACE/type 7 与寄存器 ABI 来源审查

日期：2026-10-15。work_id：`A-app-trace-review-20261015-v1`。
任务：`DEEPEYE-IMPLEMENTATION-20261014/v1`；直属实施主会话
`01a13d7e-dcf1-7272-a738-a637dd62ff9d`，generation 2。

**结论：现有来源不足以冻结 TRACE payload 或寄存器位域。** 本次只增加
`integration/test_trace_payload.py` 的拒绝/重同步检查，不创建
`integration/trace_payload.py`，不改变 `wire.py`、公共 JSON/CSV 或其它机文件。
这些检查不能关闭 R03、B01 或任何产品卡；产品/实际链路/板测/系统验收仍为 `not_run`。

## 1. 审查基线与可复核证据

- 固定设计 commit：`1011259415a0916054eb580687612580bc1e5f09`。
- 实施 HEAD：`32dff0c4252b1e08dc54beee168fd3959bf822df`。
- 合同：`DEEPEYE-HUMAN-LOCK-20261014/revision1`。H01–H15 全部保留。
- requirements canonical JSON（UTF-8，`ensure_ascii=False`、`sort_keys=True`、
  `separators=(',', ':')`）SHA256：
  `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`。
- 根目录、实施目录及固定 Git blob 的合同字节相同。审查的九个输入文件均与实施
  HEAD blob 相同；其中五个设计文件也与上述固定设计 blob 相同。

证据目录是仓库根目录下
`.planning/deepeye-implementation-a/app-trace-review-20261015/`。
`source_manifest.json` 保存路径、完整 SHA256、行数、HEAD 和固定设计比较；
`sources/` 保存对应原字节。下列产品和设计行号均指该清单的源文件，后续修改需重新定位。
命令、工作目录、时间、退出码及 stdout/stderr 哈希见 `*.command.json`，原输出单独保存。

## 2. 已规定与未规定的边界

设计文件前缀为 `docs/competition/deepeye-2026/`；产品路径相对
`competition/deepeye/`。

|主题|已规定的来源与字段|不能从来源推出的内容|
|---|---|---|
|ABI 版本|`taskbook_final.md:116` 明确采用 ABI3，旧 v3 任务书的 ABI2 仅历史；`interface.json:3` 为 3|不能从 `taskbook_v3.md:114` 采用 version=2 或旧单轴控制|
|公共帧|最终任务书 `116`；`docs/interface.json:18–42`：A5 5A、`<2sBBBBHI`、12B header、CRC2、总开销14B、payload≤32B、总长≤46B、多字节小端|这个外层定义不确定 TRACE 内部的字节/位顺序|
|CRC|同上：CCITT-FALSE，poly=0x1021、init=0xffff、不反射、xorout=0，覆盖 version 至 payload 尾，CRC 小端；123456789→0x29b1|CRC 正确不代表 payload 有已接受的语义|
|TRACE 类型/预算|最终任务书 `125`：0x07，独立块/锚点/选择 tick/mask/padding 全计入≤32B；历史 v3 `124` 也是上限；`docs/interface.json:823–827` 仅 type/max/status|没有最小长度、字段表、offset、宽度、块样本数、RAW/Rice 标识或 codec 版本编码|
|编码算法约束|最终任务书 `108–112`；历史 v3 `106–110`：uint16 容器，独立绝对锚点、差分 ZigZag/Rice、按块选 k、有界 unary、不优于 RAW 时整块旁路；E=0 无损，E=1/2/4/8、Δ=2E+1、预测器用重建值更新、差分中间量至少17bit有符号|尚无量化舍入/半值/溢出/饱和精确规则、ZigZag 公式与作用域、k 的范围/编码、unary 上限及逃逸/拒绝规则、bit order、有效码位数/尾 padding 验证规则|
|时间、选择与 mask|最终任务书 `165`：128 个实际选择点，tick/mask 明示，非虚构100Hz连续曲线；历史 v3 `147`；最终任务书 `112` 要求未发区间显示 GAP/age|没有定义 header.tick 与 TRACE 内基准 tick 的关系、绝对/差分 tick 编码、单位/跨度/回绕、点序号与帧 seq 关系、mask 粒度/位序、缺失通道如何影响预测器|
|用途/预算|最终任务书 `145–165`：双线速、配置/重试互斥、逐窗与滑窗、TRACE 余量/离线；历史 v3 `137` 明确在配置/重传窗禁发 TRACE|当前六种名义窗口的检查不自动证明插入 TRACE 后仍有合法时隙；不得只以“剩余字节”替代空等/换向/完整滑窗计算|
|R03/B01 责任|最终任务书 `340–356`：A维护ABI，B/C独立互操作；B编码、C独立解码、A签收，100万样本多种E/RAW/块重启/饱和检查|B单方候选、A本地往返或负面帧测试均不是三机互操作签收|
|仿真合同|`simulation_contract_final.json:148–208` 定义业务字节账、拓扑、TELEM采样tick、摘要跨度与时效；`210–222` 禁止真值/未来等输入|该文件没有 TRACE codec/寄存器字段定义；TELEM 的最后采样 tick 语义不能未经确认移植为 TRACE 的 tick 语义|

当前 `docs/interface.json:44–822` 的 `frames` 有15种定长结构，没有 TRACE 结构；
`trace.status` 明确要求“B提供 codec payload，A接受后才能 ENABLE TRACE”。
`integration/wire.py:16–17` 的长度表不含7，`39–45` 拒绝未知/未冻结类型，
encode `55`、decode `67` 和流扫描 `114–118` 均经该检查。因此 type 7 目前在 CRC 检查前
被拒绝；这是既有保护行为，不是已实现的 TRACE decoder。
`docs/interface.json:963–976` 同时明确保留 TRACE、寄存器和 B/C 互操作等门，
`hardware_enable_eligible=false`。

## 3. 寄存器：地址清单不等于可执行 ABI

最终任务书 `167` 将 HWH 作为实际地址依据，沿用 0x00–0x5c，并增加 ABI3 寄存器；
历史 v3 `149` 给出旧名称列表。两处只规定上电未使能、STOP优先、clear_fault与enable
分离及必须匹配新 bit/HWH，不规定具体控制位号。现有 `docs/registers.csv` 共29个32bit行，
表头只有 `offset_hex,name,width_bits,implementation_status,authority`。
所有行的 authority 为 `matched_new_overlay_hwh_only`；该字符串不是已有 HWH 的证明。

|CSV行|地址及当前名称|当前状态/缺项|
|---|---|---|
|2–3|00 identification、04 abi_version|`not_run`；缺实际ID值/版本编码、RO及复位值|
|4–7|08 control、0c status、10 shadow_configuration、14 apply_request|`bitfields_pending_A_freeze`；缺位号、RW/RO/W1C/脉冲、握手、自清、STOP/enable/clear_fault交互|
|8–10|18 sample_rate、1c error_bound、20 profile|前二 `not_run`，profile `enum_pending_A_freeze`；缺单位/范围/寄存器枚举映射/生效边界/复位值|
|11–12|24 queue_status、28 overflow_merge|`bitfields_pending_A_freeze`；缺各队列字段、计数位宽/饱和/清零和丢弃/合并语义|
|13|2c reserved|`no_access`；不用于试写；尚无总线错误/读返回定义|
|14–17|30 applied_yaw、34 applied_speed、38 applied_request、3c session|38位域待冻结，其它 `not_run`；缺有符号扩展/有效位、request关联、原子捕获和复位/换session处理|
|18–21|40 sample_tick_word0、44 sample_tick_word1、48 capture_period0、4c capture_period1|`semantics_pending_A_freeze`；缺40/44是否高低字及读一致性、48/4c的通道归属/单位/宽度/锁存|
|22–25|50 capture_sequence、54 capture_quality、58 gain、5c measured_ratio|54位域待冻结，其它 `not_run`；缺三路捕获有效/故障映射、计数回绕、gain/ratio编码与无效值/标定依据|
|26–30|60 applied_pitch、64 pitch_capture_period、68 speed_capture_period、6c motion_profile_id、70 last_observed_sequence|6c枚举待冻结，其它 `not_run`；缺 signedness、tick单位、wire/profile映射、观察序号宽度/关联及复位值|

还需统一 AXI 读写字节选通、未映射访问、跨字快照/CDC、影子配置提交与首生效采样、
soft reset/PL reset/失联后的状态。不得默认 word0/word1 是64bit tick的低高字，或
默认两个 capture_period 分别代表何通道。最终任务书 `140` 已规定三路原始捕获只留
PL寄存器/本地取证，CSV还需说明 high-count/edge-tick 的实际地址或其它明确取证入口。

已有 wire 枚举仍有效，例如 `docs/interface.json:832–839` 的
stopped=0、accepted=1、applied=2、captured=3、rejected=4 及 `956–961` 的 gain→倍数映射。
它们不自动规定 STATUS/control/gain 等寄存器的位域或复位值。HWH可定位地址/范围，
还需与同 commit 的 RTL、寄存器规范、bit/HWH及独立向量共同核对。

## 4. 本次实际读取的 B/C 来源与互操作缺项

证据目录的 `github_pr_inventory.*` 保存本次只读 PR清单；`b_pr23.*`、`c_pr25.*`
保存实际 head/body/file列表。清单未出现 B实施PR；不能据此判断 B未发布工作区的内容。
没有向任何同伴或会话发消息，也没有写PR反馈。

- B现有设计评析 [PR23](https://github.com/carolwjade/CarlandFPGA/pull/23)，head
  `01134f381f22bdda44fd3f6b5d9840b9de6bdb28`。实际读取的
  [fusion_review.md](https://github.com/carolwjade/CarlandFPGA/blob/01134f381f22bdda44fd3f6b5d9840b9de6bdb28/docs/competition/deepeye-2026/round3/b/fusion_review.md#L7)
  第7、12行保留独立块/RAW，明确不引入其旧36B新头，且旧64点观测profile不能混算。
  该文件是对旧A v4的融合评析，不能当作当前TRACE字节合同。
- C实施 [PR25](https://github.com/carolwjade/CarlandFPGA/pull/25)，本次读取 head
  `6e1624d0b0ae3f46adaded330f0bc23840ac9886`。实际读取
  [curve_input.py](https://github.com/carolwjade/CarlandFPGA/blob/6e1624d0b0ae3f46adaded330f0bc23840ac9886/competition/deepeye/ai_pc/model/curve_input.py#L1)。
  第1–12、25–30行明示这是C内部 `[1,8,128,1]` 输入构造器，不创造A wire字段；
  `338–365` 的 `CurveObservation` 只有 binding、uint64 sequence、四值、四bool valid；
  `374–415` 严格拒绝额外key。`207–228` 的13字段schema和 `649–667` 的窗口metadata
  均没有 acquisition_tick 字段。该代码不是独立 TRACE 二进制decoder。

因此必须由主会话向 B/C 确认以下可审阅内容后才能冻结：

1. **B→A：** 同一精确 commit 的 codec/payload 提案，逐字节/逐位布局、边界规则和原始向量；
   A确认它符合32B总负载和独立块/RAW/E约束后公布唯一候选。不要从旧36B头或64点profile移植字段。
2. **C→A/B：** 按该候选独立解码，不复用B编码器作为期望值；明确通道顺序、uint16到各模型
   物理量的反量化、来源/profile与预处理绑定，及缺失/饱和mask含义。FORCE曲线和sim_em摘要不得混用。
3. **选择点→C内部API：** 明确 `header.seq`（帧序号）、块/采样序号、C uint64 sequence
   及其 acquisition-index gap语义之间的映射。决定稀疏选择是选择点ordinal还是原采样index，
   防止把慢传128个选择点误作128个连续100Hz槽。C当前mapping拒绝新tick key，故需双方明确适配层
   和保存tick/时钟界的旁侧证据；不得静默丢弃采样时标或替换成接收时刻。
4. **双方→A：** 同一candidate哈希下，坏块后的下一块重启、重复/冲突/乱序、epoch/session切换、
   tick回绕和旧历史的处理；TRACE只能进入明确的曲线/离线通道，不旁路更新动作租期或实测来源。
5. **B/A寄存器：** B给RTL寄存器行为、CDC/快照和构建/匹配HWH候选，A决定公共规范；C只消费
   已合法在线返回的观测，不能用本地AXI queue或调试网补齐信息。

## 5. 交给主会话审查的推进方案（未冻结）

维持当前type7拒绝与全部硬门。下一份候选必须同时包含：

- TRACE语法表：每个字段的名字/offset/宽度/单位/取值/保留位、可变长度公式和上限。
  必须覆盖块重启、绝对锚点、通道/选择与mask、采样时间、codec/E/k/RAW判别、码位数与padding。
  是否采用逐通道块、通道交错、单点保底或切分，均由B提交字节账和独立可重启性依据后由A决定；
  本审查不为这些未决字段分配数值。
- Codec精确算法：重建闭环的每步整数规则、边界/饱和、ZigZag、Rice unary终止与最大长度、
  不可压缩块切RAW以及截断/多余bit/非法k/E/矛盾mask的确定拒绝行为。
- B编码/C独立回解的逐字节向量，含一个可手算的无损块、各E、RAW、0/65535/极跳、损坏/截断/
  长unary/padding/跨块恢复，以及100万样本误差验证。样本/编码payload/完整线帧分别计数。
- 最小保底payload也须给出明确长度，不假定32B必能容纳任意数量的四通道样本；超过上限时整块
  拒绝/切分/RAW的规则必须可解码且所有元数据计费。A再检查TRACE插入的实际窗口和任意滑窗。
- 补全寄存器规范、RTL/向量及匹配bit/HWH清单，再把候选和完整字节哈希纳入既有BOOT绑定流程。
  需主会话确认规范覆盖范围和layout/contract revision，不由工作会话静默改版本。

收到充分且被A接受的定义后，才为隔离 `trace_payload.py` 写独立正负向量，先观察真实 RED、
实现最小解析器再 GREEN；公共 wire接入和ENABLE仍由主会话另行集成/验收。
解析成功也不授予观测新鲜度、动作、真实采样或硬件资格。

## 6. 本轮负面测试和验证范围

`integration/test_trace_payload.py` 的6项检查覆盖：所有0–32B payload的encode/decode拒绝，
诊断开关不绕过，CRC正确type7仍拒绝，任意输入分块后恢复HELLO，超界声明长度不等待未知体，
旧ABI/坏CRC/重复magic和256次未知块保持存储有界。CRC由stdlib `binascii.crc_hqx` 独立生成。

从产品目录运行：

```powershell
python -B -X utf8 -m unittest integration.test_wire integration.test_trace_payload -v
```

本轮没有生产解析器变更；负面测试首次运行即通过的是既有隔离行为，不宣称parser的TDD RED/GREEN。
原wire套件11项、TRACE负面套件6项均通过（各退出0），最终按上述命令合跑17项通过、退出0。
额外 `mutation_probe.py` 在独立进程中
仅把模块内允许表临时设为 `[7]=32`，6项测试产生173处失败、退出1；这是真实负对照，
证明测试能抓住“未冻结就放行type7”的回归，未修改任何源文件。原始失败日志保留，不冒充产品故障。

仍缺：B当前已接受的TRACE/codec定义与向量、C独立二进制回解/时标适配证据、寄存器位域/复位/
CDC规范、匹配RTL/bit/HWH、TRACE实际调度/全R03状态集成和真实链路/板上证据。
本报告不改变这些缺项或29张产品卡的 `not_run`。
