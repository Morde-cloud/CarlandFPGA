# A接入：实物展示随动

直接人类授权与最新取舍：近似方向/速度丰富演示即可；保持角度/PWM边界和失联停转，不要求精确复现或RPM闭环。本包不改变主项目H01–H15、initial-only或两H12。

Root已有唯一native.state读取后，把该次实际公共{native,host}加run_id/source送单独IO worker；Follower与源位于同QPC主机。不要新增第二nativeRPC客户端、不要把A绝对QPC直接当B时钟。参考四元数显式对应实物保存中位。只读已接受orientation_xyzw和实际speed_m_s；不读真图、不发回虚拟控制、不用yaw_q当角度、不用target或滑杆冒充实际速度。外设越界停止只影响实物显示。

当前MCU在B，通过J101/XDS110 COM9可做临时直连试验。最终排针路径要求MCU与A的FPGA实际连线，网络转发不能替代三根UART/地线。人类现说上电、无人观察、PB6/PB7未接或不确定，故本轮没有任何硬件动作。接线须现场断电核对，再观察小角度/短时低速试验；不要照抄历史序号297，须当次确认MTR4/当前boot与高水位。

现有MTR4 Python协议被逐字复制到baseline_mtr4（有MANIFEST），原目录/固件/零位/EEPROM未改。新Follower无独立背景续租；仅在源新鲜时每100ms续租，每500ms最多一帧变化的双轴目标，未知结果锁定且独立STOP只尝试一次。ACK不代表到位/RPM；已发送的有限舵机动作可继续完成。电机300ms租期不会被pose自动刷新，串行四次交换过慢会停机，实际并发须板间验收。

最终A用同一产品IP/时钟/复位/地址规划加入AXI UARTLite。现存库函数integrate_existing_bd.tcl只供“GP1空闲且引脚/地址已核对”的参考，不能盲用0x43C00000；当前产品时钟50/100MHz及现有地址/针脚由A核对。独立通信镜像会替换整PL，禁止为新增外设直接覆盖运行产品。重新生成匹配产品BIT/HWH，验证实际runtime metadata/UART/限位/失联，再执行新唯一operation；无旧板测继承。

既有准备针脚为PMODA1/Y18 TX→G3507PB7 RX、PMODA2/Y19 RX←PB6 TX、PMODA5GND，3.3V TTL1152008N1。不能与电脑XDS同时驱动PB7，也不把UT01约5V串口接FPGA。全部需要A确认当前无冲突；本包profile.hardware_confirmed仍false。

SessionClient复用直连MCU；SshClientAdapter只包装A已经打开并持有、keepalive=False的SshDisplayClient，让新Follower控制真实源有效性。这个包不在B打开SSH/板卡，不热插入当前A进程。独立33控制及真实C模拟器88UART帧/7姿态/多档PWM/最终OFF均为离线结果。实物连续跟随、PYNQ、实际产品callback、视频与正式验收仍未完成。
