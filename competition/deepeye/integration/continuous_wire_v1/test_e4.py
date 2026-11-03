"""Independent synthetic E4 controls; never source/transport/board acceptance.

Manual count1 RAW payload and bitwise CRC derive from Root791's register ABI
and golden layout, not e4.py's encoder (there is none). Golden decode supplies
the server's declared record; reconstructed values/quality/ledger assertions
are independently specified. Contract rev2 H01-H15 requirements SHA256
2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d.
"""
import copy
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import struct
import threading
import unittest

from . import adapter as a
from .e4 import E4Stream
from competition.deepeye.golden.codec.trace_candidate import decode_payload


BINDING = a.Binding('synthetic-e4', a.LONG_TTL_BUILD, 'a'*64, 791)


def raw(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def crc(data):
    """Independent polynomial long division, CCITT-FALSE; no binascii."""
    remainder = 65535
    for byte in data:
        remainder ^= byte << 8
        for _ in range(8):
            remainder = ((remainder << 1) ^ (0x1021 if remainder & 0x8000 else 0)) & 65535
    return remainder


def frame(lane, value, source_seq, adc, em, q, session=791):
    valid = value is not None
    held = valid and em < adc
    age = (adc-em)*1000
    long_age = held and age > 65535
    quality = (lane | (4 if valid else 0) | (8 if q & (16 << lane) else 0)
               | (16 if held else 0) | (32 if q & 4096 else 0) | (64 if long_age else 0))
    payload = struct.pack('<BBBBBIIQ', 2, 8, quality, 1, 16 if valid else 0,
                          session, source_seq, adc*1000)
    if held:
        payload += struct.pack('<Q', em*1000) if long_age else struct.pack('<H', age)
    if valid:
        payload += struct.pack('<H', value)
    body = struct.pack('<2sBBBBHI', b'\xa5\x5a', 3, 0xe4, len(payload), 1,
                       4*(source_seq-1)+lane+1, adc*1000) + payload
    return body + struct.pack('<H', crc(body[2:]))


def fixture(*, seq=1, source=1, adc=100, em=None, counts=None, q=None,
            tag=1, result_base=501, rx_base=9001):
    if em is None:
        em = adc
    if counts is None:
        counts = [0, 4095, 2084, None]
    counts = list(counts)
    if q is None:
        q = sum(1 << i for i, value in enumerate(counts) if value is not None)
    request = dict(abi=a.ABI, op='sense', request_seq=seq, source_seq=source,
                   adc_tick_ms=adc, em_tick_ms=em, counts=counts, quality=q,
                   source_digest='b'*64)
    frames = [frame(i, value, source, adc, em, q) for i, value in enumerate(counts)]
    rows = []
    cursor = rx_base
    for i, packet in enumerate(frames):
        rows.append(dict(id=result_base+i+1, error=0, bytes=len(packet), refusal=0,
                         rx_before=cursor, rx_end=cursor+len(packet)))
        cursor += len(packet)
    result = dict(wire_hex=b''.join(frames).hex(),
                  decoded=[decode_payload(b'\x01'+p[13:-2], dict(session=791, config_epoch=1, e=0)) for p in frames],
                  result_rows=rows, tag=tag, source_digest=request['source_digest'],
                  source_seq=source, correlation='FOUR_FRAME_CRC_SOURCE_CONSISTENT',
                  quality=q, adc_tick_ms=adc, em_tick_ms=em)
    ticket = a.Ticket(seq, 'sense', raw(request)+b'\n')
    reply = a.DetachedReply('sense', seq, raw(result), hashlib.sha256(ticket.raw[:-1]).hexdigest(), 'c'*64, None)
    return ticket, reply


def changed_result(reply, change):
    result = reply.result
    change(result)
    return replace(reply, result_raw=raw(result))


def changed_request(ticket, reply, change):
    request = json.loads(ticket.raw)
    change(request)
    ticket = replace(ticket, raw=raw(request)+b'\n')
    return ticket, replace(reply, request_sha256=hashlib.sha256(ticket.raw[:-1]).hexdigest())


def changed_frame(reply, change, lane=0, recalc=True):
    def edit(result):
        rows = result['result_rows']
        packets = []
        wire = bytes.fromhex(result['wire_hex'])
        offset = 0
        for row in rows:
            packets.append(bytearray(wire[offset:offset+row['bytes']]))
            offset += row['bytes']
        change(packets[lane])
        if recalc:
            packets[lane][-2:] = struct.pack('<H', crc(packets[lane][2:-2]))
        result['wire_hex'] = b''.join(packets).hex()
    return changed_result(reply, edit)


class Controls(unittest.TestCase):
    def reject(self, ticket, reply, stream=None):
        stream = stream or E4Stream(BINDING)
        with self.assertRaises(a.ProtocolError):
            stream.accept(ticket, reply)
        self.assertTrue(stream.poisoned)
        with self.assertRaises(a.ProtocolError):
            stream.accept(*fixture())

    def test_manual_crc_known_check_and_fresh_ledger(self):
        self.assertEqual(crc(b'123456789'), 0x29b1)
        ticket, reply = fixture()
        observation = E4Stream(BINDING).accept(ticket, reply)
        self.assertEqual(observation.counts, (0, 4095, 2084, None))
        self.assertEqual((observation.source_seq, observation.adc_tick_ms, observation.em_tick_ms), (1,100,100))
        self.assertEqual(observation.source_digest, 'b'*64)
        self.assertEqual(observation.authority, 'none')
        self.assertEqual(observation.request_sha256, hashlib.sha256(ticket.raw[:-1]).hexdigest())
        self.assertEqual(observation.wire_sha256, hashlib.sha256(bytes.fromhex(reply.result['wire_hex'])).hexdigest())
        ledger = observation.ledger
        self.assertEqual((ledger['wire_bytes'],ledger['selected_raw_bytes'],ledger['code_bytes'],ledger['significant_bits'],ledger['value_count']), (146,6,6,48,3))
        self.assertEqual(ledger['lossless_e'], 0)
        self.assertIs(ledger['compression_ratio_claimed'], False)
        self.assertEqual([x['frame_bytes'] for x in ledger['frames']], [37,37,37,35])
        self.assertEqual([x['stored_code_bytes'] for x in ledger['frames']], [2,2,2,0])
        ledger['frames'][0]['frame_bytes'] = -1
        self.assertEqual(observation.ledger['frames'][0]['frame_bytes'], 37)
        with self.assertRaises(FrozenInstanceError):
            observation.authority = 'motion'

    def test_held_short_long_missing_fault_saturation(self):
        cases = [dict(adc=100,em=99),dict(adc=200,em=1),
                 dict(counts=[None]*4,q=4096),dict(counts=[0,1,4095,2048],q=255)]
        for case in cases:
            with self.subTest(case=case):
                ticket, reply = fixture(**case)
                observation = E4Stream(BINDING).accept(ticket, reply)
                self.assertEqual(list(observation.counts), json.loads(ticket.raw)['counts'])
                self.assertEqual(observation.quality, json.loads(ticket.raw)['quality'])
                self.assertEqual(observation.ledger['code_bytes'], sum(v is not None for v in observation.counts)*2)

    def test_crc_header_payload_tampering(self):
        # Offsets are the wire ABI, with fresh CRC to isolate semantic checks.
        edits = {'magic':(0,0),'version':(2,2),'type':(3,7),'length':(4,22),
                 'view':(5,2),'frame_seq':(6,9),'header_tick':(8,1),
                 'revision':(12,1),'channel':(14,5),'index':(21,2),
                 'payload_tick':(25,1),'session':(17,99),'value':(33,1),
                 'reserved':(14,132),'significant_bits':(16,15),
                 'E':(13,9),'count':(15,2),'RAW_k':(13,24)}
        for label,(offset,value) in edits.items():
            with self.subTest(label=label):
                ticket, reply = fixture()
                self.reject(ticket, changed_frame(reply, lambda p: p.__setitem__(offset,value)))
        ticket, reply = fixture()
        self.reject(ticket, changed_frame(reply, lambda p:p.__setitem__(-1,p[-1]^1), recalc=False))
        ticket, reply = fixture(adc=100,em=99)
        self.reject(ticket, changed_frame(reply, lambda p:p.__setitem__(33,p[33]^1)))

    def test_padding_extra_bytes_and_server_decoded_tamper(self):
        ticket, reply = fixture()
        self.reject(ticket, changed_result(reply, lambda r:r.__setitem__('wire_hex',r['wire_hex']+'00')))
        for field,value in [('value',7),('valid',False),('held',True),('source_fault',True),('saturated',True),('source_tick_ms',99999)]:
            with self.subTest(field=field):
                self.reject(ticket, changed_result(reply, lambda r:r['decoded'][0]['points'][0].__setitem__(field,value)))
        self.reject(ticket, changed_result(reply,lambda r:r['decoded'][0]['ledger'].__setitem__('stored_code_bytes',0)))
        self.reject(ticket, changed_result(reply,lambda r:r['decoded'][0]['points'][0].__setitem__('value',False)))

    def test_result_row_fields_bounds_and_intra_batch_gaps(self):
        for field,value in [('id',True),('id',0),('id',a.U32+1),('error',1),('refusal',1),('bytes',13),('bytes',64),('rx_before',-1),('rx_end',a.U32+1)]:
            with self.subTest(field=field,value=value):
                ticket, reply = fixture()
                self.reject(ticket,changed_result(reply,lambda r:r['result_rows'][0].__setitem__(field,value)))
        for field in ('id','rx_before','rx_end'):
            ticket, reply = fixture()
            self.reject(ticket,changed_result(reply,lambda r:r['result_rows'][1].__setitem__(field,r['result_rows'][1][field]+1)))

    def test_request_correlation_shape_quality_and_limits(self):
        for field,value in [('source_seq',0),('source_seq',16384),('source_seq',True),
                            ('adc_tick_ms',a.U32//1000+1),('adc_tick_ms',-1),
                            ('em_tick_ms',101),('em_tick_ms',-1),('counts',[0,1,4096,None]),
                            ('counts',[True,1,2,None]),('quality',15),('quality',0x1007),
                            ('source_digest','A'*64),('quality',0x807),('quality',0x87)]:
            with self.subTest(field=field,value=value):
                ticket,reply=fixture()
                self.reject(*changed_request(ticket,reply,lambda r:r.__setitem__(field,value)))
        ticket,reply=fixture()
        for changed in [replace(reply,request_seq=2),replace(reply,request_sha256='d'*64),
                        replace(reply,op='apply'),replace(reply,authority='motion'),
                        replace(reply,response_sha256='bad')]:
            self.reject(ticket,changed)

    def test_monotonic_cursors_replay_tags_and_no_64_sample_cap(self):
        stream=E4Stream(BINDING)
        rx=12345
        for n in range(1,76):
            ticket,reply=fixture(seq=2*n,source=n,adc=100+n,tag=100+n,result_base=600+4*(n-1),rx_base=rx)
            observation=stream.accept(ticket,reply)
            self.assertEqual(observation.source_seq,n)
            rx+=146
        self.assertFalse(stream.poisoned)
        self.reject(ticket,reply,stream)
        for kwargs in [dict(tag=5),dict(result_base=506),dict(rx_base=9148),dict(em=100),dict(adc=99),dict(source=1)]:
            with self.subTest(kwargs=kwargs):
                stream=E4Stream(BINDING)
                stream.accept(*fixture(tag=5))
                options=dict(seq=2,source=2,adc=101,tag=6,result_base=505,rx_base=9147)
                options.update(kwargs)
                self.reject(*fixture(**options),stream=stream)

    def test_natural_maxima_and_no_counter_wrap(self):
        ticket,reply=fixture(seq=a.U32,source=16383,adc=a.U32//1000,tag=a.U32,
                             result_base=a.U32-4,rx_base=a.U32-146)
        observation=E4Stream(BINDING).accept(ticket,reply)
        self.assertEqual(observation.source_seq,16383)
        ticket,reply=fixture(result_base=a.U32-3)
        self.reject(ticket,reply)
        ticket,reply=fixture(rx_base=a.U32-145)
        self.reject(ticket,reply)

    def test_detached_request_reply_and_single_thread_owner(self):
        ticket,reply=fixture()
        ticket_before,reply_before=ticket.raw,reply.result_raw
        snapshot=reply.result
        snapshot['wire_hex']='bad'
        stream=E4Stream(BINDING)
        observation=stream.accept(ticket,reply)
        self.assertEqual(ticket.raw,ticket_before)
        self.assertEqual(reply.result_raw,reply_before)
        self.assertEqual(observation.counts,(0,4095,2084,None))
        errors=[]
        def foreign():
            try:
                stream.accept(*fixture(seq=2,source=2,adc=101,tag=2,result_base=505,rx_base=9147))
            except a.ProtocolError as error:
                errors.append(str(error))
        thread=threading.Thread(target=foreign)
        thread.start();thread.join()
        self.assertEqual(errors,['SINGLE_E4_OWNER'])
        # Unauthorized caller rejection precedes owner acceptance and must not
        # mutate the owner's cursor or poison an otherwise usable stream.
        self.assertFalse(stream.poisoned)


if __name__ == '__main__':
    unittest.main()
