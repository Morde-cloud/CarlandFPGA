# 可移植只读记录

`archive_records.py`把A公开原样事件转换为`deepeye.archival-display-record.v1` JSONL，供离线检查和后续接口准备。每条固定标记`authority=archival_read_only`、`live=false`、`may_drive=false`，不能直接交给实时Follower，不发送动作、不读取控制socket、不起监听、不打开COM/SSH/PYNQ。

`actual_pose`记录原生实际位置、四元数、速度、阶段、故障与已接受板回执。`sensor_source`只收公开四通道观测与原采样时刻，保留C3 null。`ai_candidate`保留真实建议与来源，`actual_pwm`分别记录请求命令、原始板捕获和原生接受后的实际速度/目标速度。`terminal`分别记录native STOP、board STOP与连接退出；不把native ACK当板ACK，也不把fault6或返回STOP当物理零输出测量。未知结果保留unknown，归档转换不重试它。

时刻原样保存：host QPC纳秒、native微秒、board单调纳秒属于三个显式不同clock domain。转换不比较跨域绝对值、不改成当前时刻、不通过复播归档取得实时授权。上下文中的operation/epoch/commit/clock名称由调用方声明，标为caller_declared；artifact SHA256由实际输入字节计算，Git提交绑定仍须交接清单独立验证。response SHA256核对的是不带换行的canonical JSON，不冒称保存了未公开的原始传输行。

只从明确指定的公开文件读取白名单字段；不导出隐藏几何、真图、控制token或任意原对象。支持`--format first-chain`、`phases`、`result`，分别对应835三类公开样本。调用方必须提供operation、epoch、证据commit以及三个clock名称。例如：

```powershell
python -B archive_records.py --input ACTUAL_PHASES.json --format phases `
  --operation-id A-GEN4-CONTINUOUS-BOARD-20261104-834-R01 `
  --world-epoch A-CONTINUOUS-WORLD-835-R01 `
  --evidence-commit 9821bbdf0f6e7bd8e156bc699156fb9f8371dba0 `
  --host-clock A835-host-QPC-ns --native-clock A835-native-usec `
  --board-clock A834-board-monotonic-ns
```

未来实时单向export需由A原有唯一控制者另行接入、声明真实源及其有效期；此模块的归档数据不能替代该接入。当前人类仅要求大致随动展示，实体限位/PWM和无人观察时不动作的边界不变；主项目H01–H15/revision2固定SHA `2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d`与两条H12验收不变。
