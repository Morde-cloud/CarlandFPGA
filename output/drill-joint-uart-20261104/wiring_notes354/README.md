# FPGA 与 G3507 三线核对

由 A 汇总一次现场核对。现有 FPGA 和单片机程序保留；本说明不要求测量电压或进行精密校准。

| FPGA：丝印 PMODA 的 12 针接口 | G3507：按 GPIO 丝印找排针 | 信号方向 |
| --- | --- | --- |
| **1：Y18，当前 FPGA TX** | **PB7：当前 UART1 RX** | FPGA → 单片机 |
| **2：Y19，当前 FPGA RX** | **PB6：当前 UART1 TX** | 单片机 → FPGA |
| **5：GND** | **GND** | 两板共地 |

沿三根线逐根看实际两端，并确认插牢。FPGA 端先找 **PMODA** 字样及针脚编号；不根据电脑画面中的左右、板子 USB 朝向或照片镜像猜行列。PMODA 的 6、12 为电源位置，不用于本次三线连接。

G3507 端以 **PB6 / PB7** 这些 GPIO 名称为准。手册的默认功能旁注可能显示 SPI 等别名；本程序已经将这两个 GPIO 复用为 UART1。不要据默认 `UART_TX/UART_RX` 功能标签换到别的 GPIO，也不要接到云台使用的 PA0/PA1。

旧 PB6/PB7 ↔ XDS110 电脑串口信号跳线，已由现场人明确回复“已断开原串口两根跳线，只连 FPGA”。此项已经确认，无需重复询问。USB、SWD、复位连接保留；接线复核期间两边均不发送测试字节。

PMODA 的相关信号还与树莓派接口共享，现场确认同一信号上没有另外的设备。两板各自保留现有 USB 供电；本次 UART 只连接表内两根信号及一根地线。

## 核对依据与当前边界

- A 的本次真实路由报告确认：发送寄存器经过 OBUF 到 Y18，Y19 经过 IBUF 到接收同步寄存器。这是设计/路由证据，不能证明现场线已接通。
- G3507 固定 MTR4 配置为 UART1、PB6 TX / PB7 RX、115200 8N1；实际读回的复用与波特率寄存器一致。
- 最新单向实测：B 一次写入 8 个固定测试字节并读到发送完成状态，A 随后的实际读取为 0 字节。链路尚未通过；不重发该批字节，也不把结果写成 CRC、到位或电机速度验收。
- 现场三线端点/共地回执到达后，由 A/B 约定新的明确操作。保留旧失败、日志和原程序。

官方参考：[PYNQ-Z2 基础约束](https://github.com/Xilinx/PYNQ/blob/3.1.1/boards/Pynq-Z2/base/vivado/constraints/base.xdc)、[TUL 板卡接口图](https://www.tul.com.tw/images/PYNQ-Z2_PA_v2_pp_20201209_STD.pdf)、[TI LaunchPad 手册第 2.8 节、图 2-10](https://www.ti.com/lit/ug/slau873d/slau873d.pdf)、[Pmod 接口规范](https://digilent.com/reference/_media/reference/pmod/pmod-interface-specification-1_3_0.pdf)。实际板卡按丝印核对；本说明未推测 LaunchPad 的连接器编号和接头朝向。
