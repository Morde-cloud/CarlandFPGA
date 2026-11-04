"""Read recorded A evidence only. Opens no board, port or network connection."""
from pathlib import Path
import binascii
import hashlib
import io
import json
import struct
import tarfile


def verify(root):
    raw_dir = root / "evidence/raw"
    index = json.loads((raw_dir / "BUNDLE_INDEX.json").read_bytes())
    parts = []
    for item in index["parts"]:
        data = (raw_dir / item["path"]).read_bytes()
        assert len(data) == item["size"]
        assert hashlib.sha256(data).hexdigest() == item["sha256"]
        parts.append(data)
    archive = b"".join(parts)
    assert hashlib.sha256(archive).hexdigest() == index["archive_sha256"]
    originals = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        members = tar.getmembers()
        assert len(members) == index["member_count"] == len(index["members"])
        for member, expected in zip(members, index["members"]):
            assert member.isfile() and member.name == expected["path"]
            assert not member.name.startswith("/") and ".." not in Path(member.name).parts
            data = tar.extractfile(member).read()
            assert len(data) == expected["size"]
            assert hashlib.sha256(data).hexdigest() == expected["sha256"]
            assert member.name not in originals
            originals[member.name] = data

    def obj(name):
        return json.loads(originals[name])

    expected_hash = "2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d"
    contract = obj("contract/immutable_scope.json")
    canonical = json.dumps(contract["requirements"], ensure_ascii=False,
                           sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(canonical).hexdigest() == expected_hash
    review = obj("B/MCU_OBSERVATION476.json")
    assert review["requirements_sha256"] == expected_hash
    assert review["requirements_ids"] == ["H%02d" % i for i in range(1, 16)]
    assert review["full_two_axis_speed_demo_pass"] is False
    assert review["formal_all29"] == "not_run"
    assert review["no_B_hardware_actions"] is True
    for item in review["original_payloads"]:
        data = originals["A165/" + item["name"]]
        assert len(data) == item["bytes"]
        assert hashlib.sha256(data).hexdigest() == item["sha256"]

    events = [json.loads(line) for line in
              originals["A165/uart-events.original.jsonl"].splitlines()]
    tx, rx = {}, {}
    for event in events:
        kind = event["event"]
        if kind not in ("uart_write_intent", "uart_reply_bytes"):
            continue
        assert event["operation_id"] == "A-GEN4-UART-ACTUATOR-20261104-1261-R01"
        assert event["requirements_sha256"] == expected_hash
        assert event["simulation"] is False
        is_tx = kind == "uart_write_intent"
        data = bytes.fromhex(event["frame_hex"] if is_tx else event["reply_hex"])
        assert len(data) == 32 and data[:3] == b"\xd3\x4c\x01"
        assert binascii.crc_hqx(data[:30], 65535) == int.from_bytes(data[30:], "little")
        seq = struct.unpack_from("<I", data, 4)[0]
        collection = tx if is_tx else rx
        assert seq not in collection
        collection[seq] = (event, data)
    assert sorted(tx) == sorted(rx) == list(range(4, 12))
    assert [tx[i][1][3] for i in sorted(tx)] == [3, 4, 4, 1, 6, 7, 7, 3]
    for seq in tx:
        assert rx[seq][0]["request_hex"] == tx[seq][1].hex()
        assert rx[seq][1][3] == 128
        assert tx[seq][0]["monotonic_ns"] < rx[seq][0]["monotonic_ns"]
    for seq, result, armed, pwm in ((8, 0, 1, 600), (9, 0, 1, 600),
                                    (10, 3, 0, 0), (11, 0, 0, 0)):
        reply = rx[seq][1]
        assert (reply[9], reply[8], struct.unpack_from("<H", reply, 14)[0]) == (result, armed, pwm)
    for seq in (8, 9, 10):
        frame = tx[seq][1]
        assert frame[8:10] == b"\x02\x01"
        assert struct.unpack_from("<IIH", frame, 20) == (1, 1793760079, 300)
    assert struct.unpack_from("<hhh", tx[8][1], 10) == (0, 0, 700)
    stop = rx[11][1]
    assert stop[18] & 3 == 3 and stop[19] == 0
    assert struct.unpack_from("<H", stop, 28)[0] == 0
    assert obj("A165/sequence.original.json") == {"next_seq": 12}
    assert originals["A165/binding.original.json"] == originals["A165/consumed-transfer.original.json"]
    assert obj("A165/binding.original.json")["transfer"] == obj("B/transfer468/B_TRANSFER_FINAL.json")
    closure = obj("A165/PS_READBACK_ACTUAL.json")
    assert closure["actors"] == [] and closure["UART"] is False
    assert closure["lock"]["acquire_returned"] and closure["lock"]["release_returned"]
    assert (closure["lock"]["device"], closure["lock"]["inode"]) == (45826, 800403)
    assert obj("A165/PS_CLOSURE_SSH_PROCESS_RETURNED.json") == {"exit_code": 0, "wait_confirmed": True}
    host = obj("A165/HOST_RESULT.json")
    audit = host["physical_follow"]["transport_audit"]
    assert audit["returncode"] == 1 and audit["wait_completed"] and audit["reader_joined"]
    assert all(audit[k] for k in ("stdin_closed", "stdout_closed", "stderr_closed"))
    assert obj("A165/HOST_PROCESS_RETURNED.json")["exit_code"] == 2
    assert obj("A165/G05_CLOSED.json")["physical_zero_capture_proven"] is False
    transfer = obj("B/transfer477/B_TRANSFER.json")
    assert transfer["operation_id"] == "A-GEN4-UART-ACTUATOR-20261104-1287-R01"
    assert transfer["last_seq"] == 11
    assert transfer["evidence_sha256"] == hashlib.sha256(originals["B/MCU_OBSERVATION476.json"]).hexdigest()
    return {
        "raw_members": len(originals), "CRC_frames_checked": 16,
        "wire_seq": [4, 11], "terminal_STOP_seq": 11,
        "next_seq": 12, "original_host_exit": 2, "original_service_exit": 1,
        "TX9_to_10_ms": (tx[10][0]["monotonic_ns"] - tx[9][0]["monotonic_ns"]) / 1e6,
        "network_carrier_loss_proven": False,
        "full_two_axis_speed_demo_pass": False,
        "hardware_actions_by_this_verifier": 0,
        "formal_acceptance": "not_run",
    }


if __name__ == "__main__":
    print(json.dumps(verify(Path(__file__).resolve().parent), sort_keys=True))
