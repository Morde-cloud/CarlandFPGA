"""Exact revision59 R2 inputs. Changes require a new main-reviewed collector pin."""
TASK = 'DEEPEYE-IMPLEMENTATION-20261014'
WORK = 'B-G05-BOUNDED-COLLECTOR-20261026-59-v1'
MAIN = '01a13b55-095b-7461-8dd5-5476a130bd82'
CONTRACT = 'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
DESIGN = '1011259415a0916054eb580687612580bc1e5f09'
PROTOCOL_SHA = 'cc54438dff2107037b9d0bfa2ed8c434cee62d55416081023b41922d05f7ed9c'
GUARD_SHA = '1993f0b4d8d6c44d59642f9b2cfa1884c9ec814c7100ed560a734cf4b6c3562b'
SOURCES = {
 'fpga/control3d/deepeye_atomic_pwm.sv':'9dc8ecf96e59a2ae8467bda64572f62eb602d52db535733f236f64ff97c43428',
 'fpga/control3d/deepeye_pwm_coherent_capture.sv':'4baddfc31248c49000c00ac74bc2319cef6c9016c7df3f1822030c69cd82f456',
 'fpga/diagnostic/g05_capture/mapper/deepeye_g05_command_map.sv':'51f2ef228bf531e1476fd59e4068a2f1ad0b83110601104d3d1ad6764948beb4',
 'fpga/diagnostic/g05_capture/mapper/deepeye_g05_curvature_rom.svh':'d462859e6893cd90fb33ad9ddd481aaa7ee46937ba3d197431f81b602357a83c',
 'fpga/diagnostic/g05_capture/engine/deepeye_g05_capture_engine.sv':'6bc6db70e3c9e7d1e1f69846b2321ca561e5330c655d2e419cad64a6f7a15c2b',
 'fpga/diagnostic/g05_capture/axi/deepeye_g05_axi.sv':'e4016741b8d127c363b6b2ff691798869e0071336d392d3481a017eab2ff97af',
}
BUILD_FILES = {
 'fpga/diagnostic/g05_capture/build/build_g05.tcl':'6daddfcbbaf1e14f717aebcbb25e5299a5c82328a6dc9c3106de2094c5c451e8',
 'fpga/diagnostic/g05_capture/build/g05_ports.xdc':'111412cc8bd5de8e406b5426e50a8162c1e66ec07a10580d505a0c1500b54e6e',
 'fpga/diagnostic/g05_capture/build/g05_cdc.tcl':'92610b95270e267dbd5414f4e42af26cae37c35ce8aa4b8ba8f2c1b2e9371d3a',
 'fpga/diagnostic/g05_capture/build/README.md':'1aeba291f95edec7c808970024c1227ca3dde2b4c371355577c72e903c7c7acc',
 'tools/diagnostic/g05_capture/build/build_g05.py':'749a91e48da0d4597b6fa7cab1edf54334f4171a3ffcd67db3060a603a855061',
 'tools/diagnostic/g05_capture/build/hwh_guard.py':GUARD_SHA,
 'tools/diagnostic/g05_capture/build/owned_process.py':'1b8d34ce5758ec4bc0fbfd3518a27567e991039e52533c3a62652c5c9db10692',
 'tools/diagnostic/g05_capture/build/test_offline.py':'c49ffb394de182e49bd18237fcea5ccd6f18860ab2245569785ce7f79f171465',
}
UNKNOWN_PHYSICAL = ['external_output_propagation','input_flight_time','physical_cross_channel_skew']
LAUNCH_PINS = {
 'inputs/vendor_ddr_preset.xml':'73566a941b442804a9c6b0eb42385b6c1cb82f12e354c138f8868005b91c52ed',
 'inputs/windows_job.py':'3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3',
 'inputs/io_reference/candidate-pinmap.json':'4d1887278b2f84475997a323f1601258fddd4b0e5a1483de398f900847371093',
 'inputs/io_reference/candidate.xdc':'2877efc625c96b869b979ca8589518a066f61666868c0a9d73f5ac000628ac75',
 'inputs/board_repo/pynq-z2/A.0/board.xml':'a565dcb39737d551cbbbb73c0053b973c40bb3dce2274943370d3032c0fea9ae',
 'inputs/board_repo/pynq-z2/A.0/preset.xml':'18528f84aea4da503cdb3104f7706fabfb3b6ad09b78b25199cc316afa4c8cfe',
 'inputs/board_repo/pynq-z2/A.0/part0_pins.xml':'3c809473938e135a925b563b5371c8687ee05c4089376e7318c0c56524cc8a0f',
 'inputs/board_repo/pynq-z2/A.0/pynq_z2.jpg':'54b4bb2da4a38a647d3df030ec13fe63e427235980ce9ae1ca44ce9a91af4546',
}
