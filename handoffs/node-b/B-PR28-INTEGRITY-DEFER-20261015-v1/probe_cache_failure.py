"""Offline review probe: cached runtime corruption before any work is sent."""
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from fpga_mesh.app_server import pin_codex_bundle
from fpga_mesh.gateway import AppServerGateway, GatewayConfig
from tests.test_app_gateway import RecordingRouter, message

async def main():
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp)
        source=base/'desktop'
        source.mkdir()
        (source/'codex.exe').write_bytes(b'fake-offline-executable')
        (source/'codex-code-mode-host.exe').write_bytes(b'fake-offline-host')
        binary=pin_codex_bundle(source/'codex.exe',base/'cache')
        (binary.parent/'codex-code-mode-host.exe').write_bytes(b'corrupt')
        starts=[]
        def factory():
            starts.append('pin-attempt')
            pin_codex_bundle(source/'codex.exe',base/'cache')
            raise AssertionError('Corrupt cache unexpectedly accepted')
        router=RecordingRouter()
        config=GatewayConfig(node_id='A',role='astra',model='offline-unused',provider='openai',reasoning_effort='medium',cwd=str(base),codex_home=str(base/'unused-home'))
        gateway=AppServerGateway(config,client_factory=factory,session_router=router,startup_retry_delays=())
        observations=[]
        for index in (1,2):
            msg=replace(message(),message_id=f'offline-cache-{index}')
            try:
                await gateway.handle(msg)
            except RuntimeError as exc:
                observations.append({'message_id':msg.message_id,'error_class':type(exc).__name__,'safe_to_retry':getattr(exc,'safe_to_retry',False),'ledger_status':router.result(msg.message_id)['status']})
        await gateway.close()
        result={'scope':'offline fake bundle; no executable/model/service invoked','client_factory_attempts':len(starts),'turn_requests_sent':0,'observations':observations}
        print(json.dumps(result,indent=2))
        assert len(observations)==2 and all(x['ledger_status']=='failed' and not x['safe_to_retry'] for x in observations)

asyncio.run(main())
