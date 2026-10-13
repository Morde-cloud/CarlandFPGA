# 矿脉深瞳方案的来源与适用边界

核查日期为北京时间 2026 年 10 月 13 日。外部材料是技术依据，不能替代本项目实测或最新人类要求。

| 编号 | 原始来源 | 支持的结论 | 不能据此声称 |
| --- | --- | --- | --- |
| S1 | [CCSDS 121.0 B 3](https://ccsds.org/Pubs/121x0b3.pdf) 与 [压缩算法说明](https://ccsds.org/Pubs/120x0g4.pdf) | 块自适应 Rice 编码、编码选项选择、无压缩选项提供可审查的技术参考 | 本项目已实现标准或任何数据都可压缩 4 倍 |
| S2 | [AMD Ryzen AI 模型部署](https://ryzenai.docs.amd.com/en/latest/modelrun.html) | ONNX Runtime 与 Vitis AI EP 部署；支持的子图在 NPU，其余可能在 CPU；设备代际影响部署参数 | 指定 CNN 已兼容、运行或加速 |
| S3 | [AMD 安装和 quicktest](https://ryzenai.docs.amd.com/en/latest/inst.html) 与 [版本说明](https://ryzenai.docs.amd.com/en/latest/relnotes.html) | 必须核对实际 NPU、驱动、SDK；quicktest 与 offload 日志是环境验证入口 | 任意 Ryzen CPU PC 都具有可用 NPU；quicktest 通过即业务模型通过 |
| S4 | [PYNQ 3.1 DMA 文档](https://pynq.readthedocs.io/en/v3.1/pynq_libraries/dma.html) | simple mode 支持、流事务以 TLAST 终止；缺少 TLAST 可使接收不完成 | 3.0.1 板端与新 Overlay 已兼容；这里须按实际版本验证 |
| S5 | [Equinor Volve 数据发布](https://www.equinor.com/energy/volve-data-sharing) | 真实油田数据可按发布许可用于学术研究，存在公开回放资料渠道 | 煤矿含水标签、前视响应或可直接训练本项目闭环模型 |
| S6 | [SLB xBolt G2 实际案例](https://www.slb.com/resource-library/case-study-with-navigation/dr/xboltg2-na-improves-signal-and-eliminates-logging-cs) | 特定泥浆脉冲工况中存在低速遥测和噪声影响，案例报告 0.5 到 2 bps 改善 | 所有煤矿链路都不足 300 bps；本实验 UART 就是井下调制解调器 |
| S7 | [AMD PYNQ Z2 板卡](https://www.amd.com/en/corporate/university-program/aup-boards/pynq-z2.html) 与 [TUL board.xml](https://raw.githubusercontent.com/Xilinx/XilinxBoardStore/master/boards/TUL/pynq-z2/A.0/board.xml) | 器件与板卡参考；设计目标候选 xc7z020clg400-1 | 尚未核实的 PCB 接线、I/O 复用或供电可以直接采用 |
| S8 | [Vivado 2026.1 UG949](https://docs.amd.com/r/zh-CN/ug949-vivado-design-methodology/%E5%A6%82%E4%BD%95%E4%BD%BF%E7%94%A8%E6%9C%AC%E6%8C%87%E5%8D%97) | 当前 2026.1 方法学资料入口；本项目按人类要求统一目标版本 | B 当前有可运行的 2026.1；或旧 2022.1 构建已通过新版验收 |
| S9 | [ESA SHyLoC 实现](https://www.esa.int/Enabling_Support/Space_Engineering_Technology/Microelectronics/SHyLoC_IP_Core) | 有可综合VHDL预测/Rice实现，并与软件生成的字节对照 | 其Virtex5指标就是Zynq-7020性能；无需检查许可即可复制IP |
| S10 | [Petrobras 3W](https://github.com/petrobras/3W) | 运营商发布异常检测数据，须区分真实、模拟与手绘来源 | 直接等同煤矿随钻或前视含水标签 |
| S11 | [AMD Vitis 压缩实测](https://xilinx.github.io/Vitis_Libraries/data_compression/2022.1/benchmark.html) | U200/Silesia有公开压缩比与吞吐测量，可借鉴同数据对照口径 | 旧版/大器件结果可以替代2026.1与PYNQ-Z2实测 |
| S12 | [安路竞赛公告](https://www.anlogic.com/support/university/competitions/eda/news1/42.html) | 协办企业原始公告列赛事时间，作品11月4日18:00截止 | AMD具体评分细则；最终提交平台后续修订已核实 |

上述页面于本轮实际打开或检索到原始内容；S7 同时在已读项目技能中作为器件依据。S8 的在线条目已核查，未对整本手册逐页审阅。关键设计必须再按所用 IP 版本定点核对。

赛事线索 [Gitee AMD 指南索引](https://gitee.com/Vickyiii/fpgachina26-amd) 的 raw 内容由 B 内部来源研究实际读取。其自述索引与转述，官方归属链未闭合，因此不作为已确认的官方评分依据；其中借机日期还存在两处不同版本。主官网读取出现超时/证书问题，未绕过校验。这里只把真实物理任务作为设计优先项，并向 A 集中索取正式版本。真人在本轮另已确认 PYNQ-Z2、所需实物可配置及11月4日提交，这些属于已确认需求。

## 本地输入

1. 用户提供的《选题初稿.txt》与架构截图。保留矿脉深瞳主题，删除“完美体现”、压缩必然翻倍、微秒级闭环等未经证明表述。
2. 用户提供的《矿脉深瞳项目计划书.pdf》，15 页，2026 年 10 月 3 日规划版。已提取全文并检查第 3 页架构图。其 240 bit/s、四通道 5 Hz、十周和四人编制均为旧方案输入；本次不视为真人已冻结指标。PDF 中要求使用 2022.1 的旧表述由最新真人“按 2026.1”覆盖。
3. B 机交接摘要、启动要求、两技能的 2026.10.13.3 客机角色与 AGENTS。A 是唯一板卡操作者；B 的 board_access=false。
4. [PR9](https://github.com/carolwjade/CarlandFPGA/pull/9) 于本轮读回为 OPEN，head 为 `692f58bce38ff81d03204e46faf3c3792c5ff8f2`。历史实测证据锚为 `7246b2e0af33840df5f077a725f441c9240740a2`。本轮没有重复基础板测。

原始附件与本机配置不复制到公开 PR。原始 GitHub 证据只按已核实边界引用；公开第三方数据须保留原许可，不能将可下载自动等同可再分发。
