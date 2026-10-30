# New115 main-owned IP packaging parameter correction

Task DEEPEYE-IMPLEMENTATION-20261014/v1; main01a18824-4172-74e2-a13f-f3e3d1e3ed99;
work B-DEEPEYE-IPX-PARAMETER-FIX-20261031-115. H01–H15 fixed requirements SHA
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804 unchanged.
Exclusive main writes only the existing builder98 build_functional50.tcl
expose_core_parameter procedure and new private115 review evidence. Prior99S
owner and actual111 processes are terminal; Host103 terminal,112packaging and
113privateproposal have separate ownership. Never edit failed111snapshot.

111 ACTUALLY invoked Vivado2026.1 and exited1 during TRACE IP packaging after
G05 package integrity. Nativevendor22.875s; outerfailed/terminationconfirmed.
Raw error is invalid command name ipx::add_parameter with ambiguous-command
suggestions. No BD synthesis/route/BIT-HWH result exists. This consumes the one
actualvendor allowance; no new vendor retry is started by115 or this decision.
Originalfailure/logs/closure/request/claim remain immutable.

Independent read of actual111 generated TRACE component.xml proves one
user parameter BUILD_ID (PARAM_VALUE.BUILD_ID, resolve=user) and one HDL/model
parameter BUILD_ID (MODELPARAM_VALUE.BUILD_ID, resolve=generated), both128-bit
bitString zero default. ActualgeneratedXGUI has an explicit
update_MODELPARAM_VALUE.BUILD_ID mapping from PARAM_VALUE.BUILD_ID. The source
helper wrongly queries genericget_parameters then falls back to nonexistent
genericadd_parameter, despite both objects already inferred by package_project.

Selected minimal correction: require exactly the existing inferred user and
HDL objects using ipx::get_user_parameters and ipx::get_hdl_parameters; require
BUILD_ID/128-bit scope, bitString/128 width and zero defaults. Preserve inferred
user-to-model/XGUI association; do not create or silently infer replacement
parameters, mutate HDL defaults, or hide API errors in catch. Existing later
CONFIG.BUILD_ID exact readback and same-run HWH/buildidentity gates remain.
All other Tcl/source/RTL/DDR/clock/reset/CDC/timing bytes are unchanged.

Primary vendor example consulted: Xilinx/PYNQ-DL resize/ip/run_ippack.tcl,
https://github.com/Xilinx/PYNQ-DL/blob/master/resize/ip/run_ippack.tcl . It uses
distinct user/HDL parameter object APIs. AMD webcommand pages were inaccessible;
do not claim a successful2026.1 help invocation. Actual local111 XML/XGUI is
the decisive current source evidence. Generic stub tests previously did not
establish vendor command availability; do not repeat them or call new stubs a
vendor pass.115 is static/offline correction, not actual packager qualification.

Before a further vendor operation, deliver exact111failure+115fix and ask A to
select a new bounded recovery scope, as the one actualvendor has now occurred.
Continue independent Host103 delivery and A33 input113 proposal meanwhile.
No board/productionRootBOOT/H12/all29/final100MHz/1pct100ms acceptance upgrade.
