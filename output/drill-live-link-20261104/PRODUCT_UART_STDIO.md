# PC 随动与板端 UART 的已有流接缝

真实PYNQ MMIO与`RootLoadedProduct/ProductUartService`位于PYNQ PS；Godot/唯一NativeClient与Follower位于A电脑。两端绝对QPC/monotonic不相等，PC原状态不能交给PS的默认`make_follower()`。PC使用已有`SshDisplayClient(..., keepalive=False)`和`SshClientAdapter`，Follower只在同PC上校验真实原快照；有限角度/速度命令经A已有受信SSH流传输，板间最后一段仍是真实FPGA排针UART。

A板端真实Root先核当前产品、typed binding、HWH、B序号scope并`attach`。随后同一个唯一UART IO actor调用：

```python
from product_uart_stdio import serve_loaded_product
code = serve_loaded_product(service, existing_stdin, existing_stdout)
```

模块不建立SSH/网络/listener/子进程，不加载Overlay、不改时钟、不开新Native RPC。A可把同一个`ExistingStreamSession.dispatch()`接到已有受信dispatcher，避免逐MMIO字节跨SSH往返。Root仍是唯一实际产品初始化者；首次握手的`event=ready`仅兼容旧SSH客户端的传输握手，实际`service_event=uart_connected`、`mcu_feedback_ready_observed`、`actuator_READY_authorized`分别保留。DIAGNOSTIC_ONLY仍仅STATUS/STOP。

每个远程JSON原`session/request_id/expires_ms`直接交给原MTR4 session校验，不新建SessionClient请求或延长截止时间。PS只比较自己的相对毫秒；PC已有SSH客户端依据ready.clock_ms和本地经过时间产生截止。没有后台keepalive，PC Follower只在实际源新鲜时请求续租。

STOP/EOF共用同一个真实设备STOP证据。重复RPC STOP仅回传缓存的原设备seq/状态/clock_ms，另标`rpc_stop_result_reused`、`original_stop_request_id`和`device_command_replayed=false`，RPC request_id用于本次传输关联，不冒称新UART动作或新测量。错误/EOF锁定，不刷新原观测时刻，也不以归档数据或JSON布尔值授予硬件权限。

一次会话选择该流后，不再混用本地便利方法产生另一套request_id；A仍可调用终态`stop()`。真实SSH/PYNQ/HWH/FPGA-MCU连续联动需要A实际执行，本模块的假流测试只验证命令和时钟边界。H01–H15/rev2固定requirements SHA `2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d`保留。
