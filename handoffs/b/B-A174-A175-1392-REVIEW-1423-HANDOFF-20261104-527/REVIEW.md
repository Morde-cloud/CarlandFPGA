# Actual1392 review and new1423 documentary handoff

B independently checked426 original CRC frames:213TX302..514 match213ACK,
all result0. Startup op8 seq304 stored preset880 with target0/OFF. The Host
records its1s ready gate; the first physical compound was307/+850/PWM675,
without double-adding the preset. These are recorded targets and raw feedback,
not a precision arrival or RPM claim.

Common49/seq513 actually executed PWM625. Request intent to its ACK took
505.323458ms despite source validity11369ms, crossing the old500ms RPC window.
The PS then issued one STOP514 with matching ACK/unarmed/PWM0/fresh97/197ms/
errors0; global next515. Never replay513. Host2/serviceSSH1/workerNO_REPLAY are
preserved. The service did exit/wait/join/close streams, and PS actors were
empty with original45826:800403 flock released. G05 STOP121 COMPLETE/exit0;
only the183MB stream tail was supplied and hashed. Old unknown44 stays unknown.

A176 supplied two Root-derived sources, not a B firmware change. Independent
native528 review and main review found no new blocking issue in the narrow
diff: actual PC SshDisplayClient fixes one RPC window from min(original source
remaining, existing IO timeout); keepers never increase original source expiry.
The PS removes its artificial1000ms RPC ceiling, retaining before/after
min(request,source), CRC/sequence/source guards, .3s UART read,500ms wire lease
and the existing MCU1ms reply pacer. Exact source bytes are in the raw bundle.
A's RED/GREEN fixture logs and full52-file/7-pin stage were not supplied; B
does not claim independent test reproduction or complete-stage verification.

New1423 canonical1189B request/preimage, child manifest and closed1392 chain
were independently verified. Documentary observation529 explicitly uses
original physical ACK514 bytes, not a new live CPU/SWD measurement. Latest human
immediate return524 superseded the earlier, late-arriving A174 maintenance
window; B did not reoccupy the hardware. No B flash/reset/STOP/ARM/op8/op6 or
fixture was executed. Historical507 deployment/SDK evidence remains historical.
Unique transfer530 is delivered for1423, last514/next515; consumed509 is not
reused. A retains normal actual idle/empty/error-free UART and fresh OFF status
checks before motion, and is the sole current hardware owner.

A174/A175/A176 arrived before B's one successful Tailscale rebind. Afterwards
A/B HMAC endpoints returned200 but one tailnet ping timed out; the rebind is
not claimed to have caused prior delivery or to prove long-term stability.
The original B service instance/config/credentials/queues were retained.

H01–H15/rev2 fixed requirements SHA256
2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d,
bothH12/full29/fullroute remain incomplete where unmet. Newrun must use the
human995 layout/algorithm/parameters with live sensing/FPGA/PC AI/admission;
old trajectories or action tables must not drive it. This is evidence review
and handoff, not full product acceptance.
