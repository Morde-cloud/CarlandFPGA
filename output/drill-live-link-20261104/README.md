# 实物钻头随动展示

用途是丰富演示：两轴大致随仿真钻头转向，自转电机随实际虚拟速度改变展示档位。默认500ms双轴同步目标，相同目标不重发；保留原MTR4固件、中位和限位。此包不控制虚拟路线、AI或运行中的速度滑杆，也不改主项目H01–H15。物理展示无需精确角度、RPM闭环或轨迹还原。

当前现场信息：人类确认已上电、暂时无人观察，PB6/PB7接线未确认。本轮没有打开COM、SWD，没有复位/烧录/舵机或电机动作。`hardware-profile.template.json`保持未确认。待有人现场观察且接线核对后，再进行小幅、有限时长实物试验。

核心入口：`FollowMapper(run_id, source, reference_xyzw)`、`Follower(client, mapper)`。输入是原NativeClient794/798的已接受公共状态，加上显式run_id/source：

```python
packet = dict(run_id=run_id, source=actual_mode, **original_native_client_sample)
follower.push(packet)
follower.tick()  # 一个独立IO线程，不能阻塞原渲染或板卡控制
```

参考四元数由调用方明确提供，表示实体保存中位对应的虚拟姿态。只映射相对+Z前向的偏航/俯仰；不复现实体平移、滚转或避障。yaw范围±90°、pitch为−45°～+68°，超范围明确停止此展示链路，不修改虚拟钻头。已发出的有限舵机动作可能继续完成；STOP不等于瞬间刹住舵机。

速度读取`speed_m_s`，不读取角速度yaw_q/pitch_q、目标速度或滑杆。默认0.25m/s对应最高展示档；0停机，正速度映射现有25%～75% PWM。可下调最大PWM（251..750‰）；25%运行最低值仍可能由小正速度产生。无RPM测量，PWM上限不是实测转速上限。

真实状态与Follower必须在同一QPC主机。A的原始绝对QPC不能直接送到B比较。短期B直连试验使用明确标为MANUAL的本地刺激；真实产品采用A已有唯一native.state读取之后的只读hook/单独IO worker，或经另行验证的跨机时钟桥。不要建立第二个原生RPC消费者。source字段只是审计声明，不凭此证明PC_DIRECT或FPGA_OUTPUT已经验收。

只有最新状态保留；默认最多每500ms更新一次变化的姿态、每100ms续租。原状态时效及实际grant独立校验，重复包不续新时效。续租只在源仍有效时执行；无独立背景心跳延长陈旧源。未知回包/超时锁定，独立STOP只尝试一次，旧动作不重放。MTR4电机租期300ms；串行姿态交换若过慢可能导致安全停机，实际并发延迟仍需实物验收。

`run_follow.py`默认dry-run，`manual_source.py`仅生成有限MANUAL测试输入。两者均无自动硬件启动：

```powershell
python -B manual_source.py --run-id local-demo --seconds 4 |
  python -B run_follow.py --run-id local-demo --operation unique-offline-id --source MANUAL --reference 0 0 0 1 --same-host-qpc --enable-motor
```

这是合成输入/dry-run，不是真实软件或实物随动验收。`--transport simulator --sim-exe <明确的motor_sim.exe>`运行真实C逻辑的假设备。serial模式另需显式COM9、当次观察/接线profile、当次MCU只读状态和新序号；不扫描端口、不猜历史序号297、不自动复位、刷固件或修改EEPROM。

`baseline_mtr4/`是独立复制且列有哈希的现有Python协议/串口代码和UART合并参考。原目录保持只读。历史文件头保留，不因此继承旧验收；父任务采用固定revision2 SHA `2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d`。

FPGA最终路径为A现有产品→PL UARTLite排针→G3507 PB7/PB6→云台/PA12电机。A须先核对当前产品的引脚、地址、时钟、复位和唯一负责人，再合并UART并重新生成匹配BIT/HWH。已有独立UART镜像会替换整个PL，不能直接覆盖正在运行的产品。PMODA1/Y18 TX→PB7 RX、PMODA2/Y19 RX←PB6 TX、PMODA5共地、3.3V TTL/1152008N1仅是既有准备方案，需A确认当前无冲突；XDS电脑和FPGA不能同时驱动PB7。B不操作A的FPGA。

`SessionClient`复用MCU协议；`SshClientAdapter`供A包装已打开、由A持有的SshDisplayClient，要求关闭其独立keepalive，让Follower的源有效性控制续租。源码准备、离线测试、既有MCU实测、PYNQ运行时、真实联动及正式产品验收分别记录，不混同。
