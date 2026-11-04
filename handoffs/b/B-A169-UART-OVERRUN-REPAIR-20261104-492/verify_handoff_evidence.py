"""Offline integrity/meaning check of recorded evidence; performs no device I/O."""
from pathlib import Path
import binascii
import hashlib
import io
import json
import struct
import tarfile


def verify(root):
    rawdir = root / 'evidence/raw'
    index = json.loads((rawdir / 'BUNDLE_INDEX.json').read_bytes())
    parts = []
    for row in index['parts']:
        data = (rawdir / row['path']).read_bytes()
        assert len(data) == row['size'] and hashlib.sha256(data).hexdigest() == row['sha256']
        parts.append(data)
    archive = b''.join(parts)
    assert hashlib.sha256(archive).hexdigest() == index['archive_sha256']
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        members = tar.getmembers()
        assert len(members) == index['member_count'] == len(index['members'])
        for member, row in zip(members, index['members']):
            assert member.isfile() and member.name == row['path']
            assert not member.name.startswith('/') and '..' not in Path(member.name).parts
            data = tar.extractfile(member).read()
            assert len(data) == row['size'] and hashlib.sha256(data).hexdigest() == row['sha256']
            assert member.name not in files
            files[member.name] = data

    def obj(name):
        return json.loads(files[name])

    req = '2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d'
    requirements = obj('contract/immutable_scope.json')['requirements']
    assert hashlib.sha256(json.dumps(requirements, ensure_ascii=False,
        sort_keys=True, separators=(',', ':')).encode()).hexdigest() == req
    tx, rx = {}, {}
    events = [json.loads(x) for x in files['A169/uart-events.original.jsonl'].splitlines()]
    for event in events:
        if event['event'] not in ('uart_write_intent', 'uart_reply_bytes'):
            continue
        is_tx = event['event'] == 'uart_write_intent'
        data = bytes.fromhex(event['frame_hex'] if is_tx else event['reply_hex'])
        assert len(data) == 32 and data[:3] == b'\xd3\x4c\x01'
        assert binascii.crc_hqx(data[:30], 65535) == int.from_bytes(data[30:], 'little')
        seq = struct.unpack_from('<I', data, 4)[0]
        bucket = tx if is_tx else rx
        assert seq not in bucket
        bucket[seq] = (event, data)
    assert sorted(tx) == list(range(15, 45)) and sorted(rx) == list(range(15, 44))
    for seq in rx:
        assert rx[seq][0]['request_hex'] == tx[seq][1].hex()
    assert tx[43][1][3] == 6 and tx[43][1][9] == 3
    assert struct.unpack_from('<IIH', tx[43][1], 20) == (6, 1793763859, 500)
    ack = rx[43][1]
    assert ack[8] == ack[9] == 0 and struct.unpack_from('<H', ack, 14)[0] == 0
    assert tx[44][1][3] == 3 and 44 not in rx
    assert any(e['event'] == 'uart_read_error_unknown' and '0x27' in e['error'] for e in events)
    assert obj('A169/sequence.original.json') == {'next_seq': 45}
    assert files['A169/binding.original.json'] == files['A169/consumed-transfer.original.json']
    ps = obj('A169/PS_READBACK_ACTUAL.json')
    assert ps['actors'] == [] and ps['lock']['acquire_returned'] and ps['lock']['release_returned']
    assert obj('A169/HOST_RETURNED.json')['exit_code'] == 2
    assert obj('A169/HOST_RESULT.json')['physical_follow']['transport_audit']['returncode'] == 1
    deployment = obj('deploy497/actual/DEPLOY.json')
    assert deployment['load_program_intents'] == deployment['load_program_returns'] == 1
    assert deployment['shutdown_returned'] and not deployment['cpu_halted_before_shutdown']
    assert deployment['MCU_READY'] and deployment['old_STOP44_ACK_unknown']
    assert deployment['image_sha256'] == 'ce40a45bd66a0a748bdfc203a7136134b4848e32ac7c9435af1a1f9f87f59ac2'
    assert deployment['PC_reply_gap_ticks'] == 1
    assert obj('deploy497/RUN497_PROCESS.json')['exit_code'] == 0
    for row in deployment['flash_readback']:
        data = files['deploy497/actual/flash-' + str(row['address']) + '.bin']
        assert len(data) == row['bytes']
        assert hashlib.sha256(data).hexdigest() == row['actual_sha256'] == row['expected_sha256']
    final = deployment['samples'][-1]
    assert final['state'] == 3 and final['preflight'] == 8 and not final['cpu_halted']
    assert final['armed'] == final['motor_duty'] == final['PWM_applied'] == 0
    assert final['last_seq'] == final['have_seq'] == final['tx_moves'] == 0
    assert all(deployment[k] == 0 for k in ('UART_RXDATA_reads', 'UART_TX_writes',
        'ARM_commands', 'DELTA_commands', 'MOTOR_commands'))
    source = obj('B/SOURCE496.json')
    assert source['source_commit'] == deployment['code_commit'] == '25eb8768b58c98460ad36678c7a79a66c9c3fea5'
    commands = obj('build496/COMMANDS.json')
    assert len(commands) == 14 and all(c['exit_code'] == 0 for c in commands)
    for i, command in enumerate(commands):
        assert hashlib.sha256(files['build496/%02d.stdout' % i]).hexdigest() == command['stdout_sha256']
        assert hashlib.sha256(files['build496/%02d.stderr' % i]).hexdigest() == command['stderr_sha256']
    assert b'checks=37' in files['build496/01.stdout']
    assert json.loads(files['build496/03.stdout'])['checks'] == 38
    fifo = obj('B/FIFO496.stdout.txt')
    assert fifo['cases'] == 3 and fifo['hardware_actions'] == 0 and fifo['model_not_physical_test']
    assert fifo['compiled_C_pacing_13ms_blackout']['reply_exact']
    assert fifo['compiled_C_pacing_13ms_blackout']['dropped'] == 0
    assert '0x27' in fifo['longer_blackout_still_raises_error']['error']
    native = obj('B/CHILD493_COMPLETED.json')
    assert native['status'] == 'completed' and native['terminal'] and not native['stale']
    transfer = obj('B/transfer499/B_TRANSFER.json')
    assert transfer['operation_id'] == 'A-GEN4-UART-ACTUATOR-20261104-1344-R01'
    assert transfer['last_seq'] == 44
    assert transfer['evidence_sha256'] == hashlib.sha256(files['B/MCU_OBSERVATION498.json']).hexdigest()
    observation = obj('B/MCU_OBSERVATION498.json')
    assert observation['A169_last_actual_wire_ACK'] == 43 and observation['persistent_next_seq'] == 45
    assert observation['tests']['physical_UART_fix_acceptance'] == 'not yet tested by A'
    return {'raw_members': len(files), 'CRC_frames_checked': 59, 'last_wire_ACK': 43,
        'STOP44_ACK_proven': False, 'allocated_highwater': 44, 'next_seq': 45,
        'single_deployment_verified': True, 'current_MCU_READY_OFF': True,
        'new_pacing_physical_UART_acceptance': 'pending_A',
        'hardware_actions_by_this_verifier': 0, 'formal_acceptance': 'not_run'}


if __name__ == '__main__':
    print(json.dumps(verify(Path(__file__).resolve().parent), sort_keys=True))
