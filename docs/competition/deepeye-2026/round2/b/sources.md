# 原始来源与支持边界

检索日期2026-10-13 UTC（北京时间10月14日）。外部原文在本机研究缓存只读保存，公开仓库保存URL、原始字节hash及结论边界；不发布带签名下载地址、账号、成员ID或整份受限数据。详细元数据见 sources.json。

|来源|用于本轮的事实|不能据此宣称|
|---|---|---|
|[FPGA官方站](http://fpgachina.cn/) 下载中心文件25《2026选题指南AMD》，PDF原件950952B，SHA256 c6ad82acd4f7bdcd13bd412e232ed85d05f2a87dd5e2cdd04f9d219f88b569fc；[同hash取证镜像](https://raw.githubusercontent.com/nbstarhkc/Qian-Sai/main/sources/amd.pdf)|实际读取PDF22–25页的3.3：自主选题、板上输出、技能包、协作轨迹、工具版本边界，评分30/20/20/15/15；镜像只作同字节获取，权威来自官方原件|不把3.2的物理执行、ROCm门槛和权重套到已报名3.3；不认为数字孪生免除了板上验证|
|官方站文件18赛事通知，779290B，SHA256 c17611b45a66121cd93f421e7fdee50f1743b1eb0cb5d9f930c57578d480ef9f|已在本机渲染扫描第5页核对11月4日18时提交，内部留6小时缓冲|真人已确认报名资格，不再以旧报名截止反复询问或假称本轮代报名|
|[ROCm7.14.1兼容表](https://rocm.docs.amd.com/en/docs-7.14.1/compatibility/compatibility-matrix.html)|HX370与Max+395列入相应APU架构，OS/内核配置需成套；本次未找到8845支持项|不证明A的780M受该版本支持，不证明NPU、模型或整机已实测|
|[ROCm7.14.1发布说明](https://rocm.docs.amd.com/en/docs-7.14.1/about/release-notes.html)|PyTorch候选路径；ONNX Runtime1.23.2/MIGraphX2.16列表限定gfx950/gfx942|不能说Ryzen GPU已得到该ORT/MIGraphX组合支持|
|[ORT原厂ROCm EP说明](https://onnxruntime.ai/docs/execution-providers/ROCm-ExecutionProvider.html)|旧ROCm EP自ORT1.23移除，迁移路径须另查|不能沿用旧EP名称声称当前后端可用|
|[Ryzen AI1.8安装页](https://ryzenai.docs.amd.com/en/latest/inst.html)、[发布说明](https://ryzenai.docs.amd.com/en/latest/relnotes.html)|浏览时页面为1.8.0；Hawk Point列为支持家族；驱动最低32.0.203.280，.376列作生产驱动。quicktest明确预期Strix或更新器件|不能由A设备管理器OK或运行Strix例程推导Hawk Point模型可用；旧.240不满足该安装页门槛|
|[AMD7945HX规格](https://www.amd.com/en/products/processors/laptop/ryzen/7000-series/amd-ryzen-9-7945hx.html)、[ASUS M5406规格](https://www.asus.com/us/laptops/for-home/vivobook/asus-vivobook-s-14-oled-m5406/techspec/)|B CPU产品身份及M5406WA备选系列的HX370/内存等选项；实际B硬件来自本机只读CIM/nvidia-smi|ASUS系列选项不证明某销售SKU/现货/价格；7945HX不因Ryzen名称获得XDNA能力|
|[TUL PYNQ-Z2原厂规格](https://www.tul.com.tw/images/PYNQ-Z2_PA_v2_pp_20201209_STD.pdf)|Zynq7020资源、板上I/O与存储等基础|不可把5V模块直接接入3.3V逻辑，不用纸面资源代替布局布线|
|[MCP3208原厂数据手册](https://ww1.microchip.com/downloads/en/DeviceDoc/21298e.pdf)、[ADXL345原厂数据手册](https://www.analog.com/media/en/technical-documentation/data-sheets/adxl345.pdf)|SPI ADC12位、多通道与电源边界；加速度SPI及100Hz候选采样|ADC16位容器不是16位有效精度，反射/加速度不是煤矿含水测量；模块引脚还需原理图|
|[CCSDS121.0-B-3](https://public.ccsds.org/Pubs/121x0b3.pdf)|自适应Rice和无压缩模式提供可核验设计参考|本方案尚非标准兼容实现，无普适4:1或8:1保证|
|[Miskowicz原论文Send-On-Delta](https://pmc.ncbi.nlm.nih.gov/articles/PMC3865911/)|事件触发采样的动机和信号依赖性|不能保证任意信号下固定事件率或完整时间曲线误差界|
|[FORCE2020组织方发布](https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition)|井曲线岩性任务与另列的地震断层任务，可做按井切分的离线副证据|没有本项目含水预警真值，不能把两个任务标签互换；许可需按文件确认|
|[PYNQ官方DMA教程](https://discuss.pynq.io/t/tutorial-pynq-dma-part-1-hardware-design/3133)、[DMA文档](https://pynq.readthedocs.io/en/v2.7.0/pynq_libraries/dma.html)|Z2例子中的DMA/AXI/TLAST与独立验证组织方式可复用|旧教程版本不证明本届工具或现有镜像自动兼容|

本轮最新web读取中ASUS页面返回工具内部错误、ADXL345工具503、CCSDS网页工具不可达；本机早先HTTP取证已取得上述原始字节并留hash，不能把工具失败记为成功。MCP3208本轮HTTP成功取到739611B。价格未核查，因此configuration.md的金额只表示内部资源预留限额，不是市场报价或采购建议的价格事实。
