# Exact request, status and G05 I/O counts

The published A999 decode_request has independent status-request cap4; G05SessionV2 has cumulative status-read cap64, including reads hidden inside methods. B186's table confused these; source190 explicitly corrects the statement here and preserves the original frozen file and manifest bytes. The main is responsible for this correction, not the failed workers.

Successful-path source accounting, excluding any new B132 bracket reads:

| Method | Actual G05 MMIO | Cumulative status-read charges |
| --- | --- | --- |
| factory | magic/layout/status/fault=4 |0 (before session) |
| init | stage_identity15 + begin5 + fullidentity13 + live_status2 =35 |4 |
| one apply, L_i>=1 eligible polls | fullidentity13 + stage_command9 + commit6 +2L_i + latch5 + snapshot38 + release5 =76+2L_i |9+L_i |
| independent status | fullidentity13+status/fault2=15 |1 |
| successful close(stop=true) | stopwrite1+status/fault2=3 |1 |
| close(stop=false) |0 |0 |

Let K=G05 commands, L=sum eligible polls (L>=K), S=independent status requests, Z=0/1 for successful explicit STOP close. Then I_G05=39+76K+2L+15S+3Z; P_status=4+9K+L+S+Z. The4factory reads are included in cumulative raw receipts. G05Port's _count charges every actual _io, not the number of Python calls. Source-read/OS/file/log work and TRACE access are different costs; these equations are neither time bounds nor hung-MMIO guarantees. Unknown/failure retains original partial evidence and does not authorize cleanup/STOP replay.

Existing maximal protocol sequence fits10 messages: init1 + TRACE2 + apply2 + status4 + close1. K2/L2/S4/Z1 gives status29/IO258; cumulative status64 allows L37 and IO328. Original conservative init gate102+76K+2P with K2/P64 gives382, covering its4statuses+STOP allowance. Do not reinterpret P as only eligible polls.

Hypothetical K16/L16/S4/Z1 gives status169/G05IO1350. A prospective P256/S4/Z1 envelope permits L<=103 and I_G05<=1524; selected G05IO2048 leaves524 accesses before that policy cap, but any new B132 full bracket costs must be derived and charged rather than assumed free. The old conservative guard at K16/P256 is1830. None of these requests is valid in unchanged commands<=2/session<=2/P64 protocol; all are source-only candidates, not tests or measurements.

Keep K_G05, N_TRACE, K_AI and N_STEP independent. Current adapter reserves one original association per genuine AI invocation; repeated STEPs do not create new observations, new AI RESULTs, TTL renewal or physical capture. A new16-observation/16AI plan must revise all source/capture limits and preserve actual original fresh associations. Several100ms STEPs per command remain subject to the existing nonoverlap/Root/age/health/actor/command/session/final-CAS fences and original maxcommand1000ms demo selection; FAST3000ms hardware TTL does not override that limit.
