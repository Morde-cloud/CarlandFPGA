# B对PR17精确v3的最终研究复核

COMP-20261013-DEEPEYE/v3；B质量主会话实际完成。只追加本文件，不改首轮、v2封存或A文件。本次审阅不授权实现、安装、采购或板测。

输入为[PR17发布head](https://github.com/carolwjade/CarlandFPGA/tree/1d4374fcc0f5ba1bf07b80d5e7f3487816af0143/docs/competition/deepeye-2026)的taskbook_v3.md：48500B，SHA256 `a9ea6bd2b61ac5be804f0a0a0f889be3dbad4b4a5d08082497e7070803ce14b8`。先读28b37470d58d7b28dbdddd093ec348a8dfa87cd3版，再逐项读最终差异。未重做PDF QA，也未核验发布包中所有其他文件。

已实际读回[A在PR16的反馈](https://github.com/carolwjade/CarlandFPGA/pull/16#issuecomment-6151725754)，其认可范围为B指定v1/v2研究字节和规划算术，不是产品或板测。B接受该范围，不把它延伸为A签收本v3评析。

## 已闭合范围

20卡为R4/B6/C5/A5。CONFIG_ACK独立返回实际配置，关联键含session/type/seq；本地queue从在线AI输入移除；GPIO独立捕获、电气反馈、PGA模拟回读及虚拟钻头分别表述。接受A统一14B固定开销。主控制窗144B、量程替代窗140B、配置窗200B、重试算术窗204B，在300baud 8N1与0.2s累计guard假设下分别占62.5%、60.833%、85.833%、87.5%。BOOT/BOOT_ACK各41B，82B握手只在停止阶段计费。算术正确不证明调度可实现或实测时延通过。

v3按A报告的最新真人UI原话采用3.2，保留ROCm与物理任务认定门未通过的事实；B本次没有直接读取那条真人UI原文。已再读同哈希官方指南的3.2要求，不以v2的3.3解释覆盖本版。量程调节保留为候选，不能把厂家器件文档当赛事认可或本项目实测。

## 剩余P0-1：缓存ACK会延长主机认定的租期

第7节一面规定完全相同请求重发原应答，一面以`receipt_monotonic + remaining_ttl - serial - USB_bound - clock_bound`计算有效期。首个ACK丢失时，主机无法仅靠“已见重复ACK不续期”排除缓存旧值。

可复算反例：PL在t=0首次应用，TTL=12s；t=0.1原ACK携剩余11.9s但丢失；t=8.1重发原ACK，32B在300baud下传1.066667s。主机t=9.166667收完，假设USB及同步合计界0.1s，按文中公式得到19.9s，而PL已在12s停止；若后续STATE/到期EVENT也丢失，主机可继续错误推进。这里是协议反例计算，不是产品仿真或板测。

最小修正：缓存事务判决以保证不再次应用，但每次发送ACK重新采样当前phase、capture、remaining，重新生成发送tick与CRC；不能字节级重放旧租期。主机另以该请求**首次发送**的单调时刻加原TTL作为保守截止上界，重试不修改该上界；无可信有效反馈只暂停。原请求过期后的重试返回stopped，不重新使能。B05/C05须覆盖首ACK丢失、延后重试、期间STATE/到期EVENT丢失、旧ACK迟到和当前停止反馈，不仅测试已收到ACK再次重复。

## 剩余P0-2：重试预算尚无第二个合法授权槽

新增grant规则规定每个TELEM bit15授权一个≤28B主请求槽，PC本槽发送后不得再发；每8秒只有一个TELEM，bit14仅授CONFIG。于是204B窗中额外的CONTROL28+ACK32虽然能放进线速预算，却没有第二个合法下行授权。不能由实现者自行突破已授权槽。

最小修正二选一，由A在R03冻结：一是BOOT绑定的retry profile让同一次grant明确预授权两个有界主请求槽，第二槽仅在超时后发送同键重试，配置禁用；槽起止、ACK截止、事件占用和无响应情况全部计费。二是重试只占下一8秒窗的唯一主请求槽，取消同窗204B说法，并重算相关故障路径的时延和截止规则。不要因字节总量未超300baud而推断仲裁已经闭合。

## 来源复查与执行边界

- [AMD官方ROCm7.14.1矩阵](https://rocm.docs.amd.com/en/docs-7.14.1/compatibility/compatibility-matrix.html)本次可见780M/gfx1103条目，但未检到8845型号；系列和iGPU列表不证明A整机、所用OS和项目图已支持。此前B v2对780M条目“未见”的结论不再作为本版依据，原封存保持。接受实际项目验证及受支持借机备选门。
- [Microchip DS21117B](https://ww1.microchip.com/downloads/aemDocuments/documents/MSLD/ProductDocuments/DataSheets/21117B.pdf)列SPI、2.5–5.5V供电及1/2/4/8等实际档位，支持候选电路思路；不证明接线、负载、校准、AI增益收益或赛事认定。
- 本机DeepSeek任务`child-60dc6aedd4484f1fa78e42c013dc474b`只核28b版字段和算术，已取得完成结果。主会话重新核最终版新增BOOT与grant，独立作上述判断；子结果中的A6“无先行词”提示不是阻塞，A6本来就是A首轮融合案。

研究复核结论：上述闭合项可以签收；两处P0在R03/B05/C05修订前，不签署最终接口通过。其他明确待验证的ROCm、规则认定及实物任务作为既有退出门保留，不新增无依据的否决项。所有RTL、模型、综合、实现、板卡和系统实测仍not_run。A可收尾本轮研究，B不以等待消息维持模型轮询。
