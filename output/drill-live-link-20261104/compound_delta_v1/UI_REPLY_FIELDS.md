The PS stdio response is one direct JSON object r. B does not add a result/data wrapper. A's own Host receipts may add their own wrapper; unwrap that actual envelope first. These compound fields apply to event=delta or delta_keepalive. Ordinary status/welcome/legacy STOP may contain only status.*.

| Meaning | Exact path | Unit / interpretation |
|---|---|---|
| Shared real command round | r.command_seq | Distinct from RPC request_id and UART status.seq |
| Shared run | r.run_id | Nonzero numeric wire run ID |
| Declared source | r.declared_source | PC_DIRECT / FPGA_OUTPUT / MANUAL |
| Accumulated yaw command | r.commanded_yaw_cd | centidegrees; positive left; /100 gives command degrees |
| Accumulated pitch command | r.commanded_pitch_cd | centidegrees; positive up; /100 gives command degrees |
| Accumulated speed command | r.commanded_speed_permille | normalized0..1000; /10 gives percent; not RPM |
| MCU-reported PWM command | r.commanded_pwm_permille | same as r.status.requested_duty_permille; OFF or250..750 |
| Yaw actual feedback | r.status.yaw_feedback.raw_position / age_ms / fresh | raw servo position and freshness at reply |
| Pitch actual feedback | r.status.pitch_feedback.raw_position / age_ms / fresh | raw servo position and freshness at reply |
| Health | r.status.armed / result_code / result / last_joho_error / servo_error_count | MCU response status |
| Original source deadline | r.compound_source_expires_ms | PS-session relative milliseconds; not PC QPC or UTC |
| Reply time | r.clock_ms | same PS-session relative clock |
| Measured motor RPM | r.measured_rpm | null; no tachometer measurement |

r.status.target_yaw_cd and target_pitch_cd are aliases of the accumulated command angles. Raw servo position is not centidegrees: do not divide it by100 or assume a4096-to360 calibration. Null/unavailable and stale feedback must remain marked accordingly. Freshness applies at reply capture and must not stay fresh forever if updates stop. UART ACK is not arrival; r.target_angles_are_commands and r.uart_ack_is_not_arrival preserve that distinction. Opcode7 renews the same command/run/source and never creates a new AI round or extends original source validity.

This map was inspected against runtime source9b064d9bd28ecc8ea77f8890252e4786966b792d, service54e08b9e95dfafb1ea939bb41d0bb131e719aba3aed764587cfb17d38f123c9d and compound_sessione349df1c50bbe1aa3d31868261a82f5ec45061a37f43bbf5f68098050950477d. It changes no runtime code or protocol. A162 actual deployment/import receipt is separate from future UART attach and motion acceptance. H01-H15/rev2 requirements2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d/fulloriginal29/bothH12 remain.
