"""Pure independent E4 reconstruction for the original791 continuous sense ABI.

No source authentication, IO, motion permission or hardware acceptance. Root
binds these bytes to its actual request/source/transport journal. The frozen
golden payload decoder is reused read-only after explicit E4 revision checks;
its historical ``tick_ms`` fields contain microseconds in this791 ABI.
"""
from dataclasses import dataclass
import binascii
import hashlib
import json
import os
import re
import struct
import threading

from .adapter import (ABI, Binding, DetachedReply, ProtocolError, Ticket, U32,
                      _hex, _int, _json, _need, _quality, _raw)
from competition.deepeye.golden.codec.trace_candidate import decode_payload


@dataclass(frozen=True)
class E4Observation:
    counts: tuple
    source_seq: int
    adc_tick_ms: int
    em_tick_ms: int
    quality: int
    source_digest: str
    tag: int
    wire_sha256: str
    request_sha256: str
    response_sha256: str
    ledger_raw: bytes
    authority: str = 'none'

    @property
    def ledger(self):
        return json.loads(self.ledger_raw)


class E4Stream:
    """Single-owner bounded cursor. Bad or replayed evidence poisons this stream.

    The first hardware result/rx counters may have an arbitrary existing base.
    Subsequent four-frame batches must continue it exactly. Natural counter and
    format exhaustion needs a new Root-authorized session, never an in-place
    reset. Only the previous cursor is retained, with no mission total limit.
    """
    def __init__(self, binding):
        _need(type(binding) is Binding, 'EXACT_BINDING')
        binding.__post_init__()
        self.binding = binding
        self.poisoned = False
        self._source = self._request = self._tag = 0
        self._em = self._adc = -1
        self._result = self._rx = None
        self._owner = (os.getpid(), threading.get_ident())

    def accept(self, ticket, reply):
        _need(self._owner == (os.getpid(), threading.get_ident()), 'SINGLE_E4_OWNER')
        _need(not self.poisoned, 'E4_UNKNOWN_NO_REPLAY')
        try:
            return self._accept(ticket, reply)
        except BaseException as error:
            self.poisoned = True
            if isinstance(error, ProtocolError):
                raise
            if isinstance(error, Exception):
                raise ProtocolError('E4_INVALID_OR_INTERRUPTED') from error
            raise

    def _accept(self, ticket, reply):
        _need(type(ticket) is Ticket and type(reply) is DetachedReply, 'EXACT_SENSE_TYPES')
        _need(ticket.op == reply.op == 'sense' and reply.authority == 'none', 'SENSE_ONLY_NO_AUTHORITY')
        seq = _int(ticket.request_seq, self._request + 1, U32)
        _need(type(reply.request_seq) is int and reply.request_seq == seq, 'SENSE_REQUEST_SEQUENCE')
        _need(type(ticket.raw) is bytes and len(ticket.raw) <= 16384, 'SENSE_REQUEST_BOUND')
        request = _json(ticket.raw)
        _need(type(request) is dict and set(request) == {'abi','op','request_seq','source_seq',
                  'adc_tick_ms','em_tick_ms','counts','quality','source_digest'}
              and request['abi'] == ABI and request['op'] == 'sense'
              and type(request['request_seq']) is int and request['request_seq'] == seq, 'SENSE_REQUEST_SHAPE')
        request_sha = hashlib.sha256(ticket.raw[:-1]).hexdigest()
        _need(reply.request_sha256 == request_sha, 'REQUEST_BYTES_HASH')
        _hex(reply.response_sha256, 64)
        s = _int(request['source_seq'], self._source + 1, 65535 // 4)
        adc = _int(request['adc_tick_ms'], max(0, self._adc), U32 // 1000)
        em = _int(request['em_tick_ms'], self._em + 1, adc)
        counts, q = request['counts'], request['quality']
        _quality(counts, q)
        _hex(request['source_digest'], 64)
        _need(type(reply.result_raw) is bytes, 'RESULT_BYTES')
        r = _json(reply.result_raw + b'\n')
        _need(type(r) is dict and set(r) == {'wire_hex','decoded','result_rows','tag','source_digest',
              'source_seq','correlation','quality','adc_tick_ms','em_tick_ms'}, 'SENSE_RESULT_SHAPE')
        _need(all(type(r[k]) is int and r[k] == request[k] for k in ('source_seq','quality','adc_tick_ms','em_tick_ms'))
              and r['source_digest'] == request['source_digest']
              and r['correlation'] == 'FOUR_FRAME_CRC_SOURCE_CONSISTENT', 'SENSE_METADATA')
        tag = _int(r['tag'], self._tag + 1, U32)
        _need(type(r['wire_hex']) is str and 0 < len(r['wire_hex']) <= 504
              and len(r['wire_hex']) % 2 == 0 and re.fullmatch('[0-9a-f]+', r['wire_hex']), 'WIRE_BOUND')
        wire = bytes.fromhex(r['wire_hex'])
        rows, declared = r['result_rows'], r['decoded']
        _need(type(rows) is list and len(rows) == 4 and type(declared) is list and len(declared) == 4, 'FOUR_LANES')
        prior_id, prior_rx, offset = self._result, self._rx, 0
        ledgers = []
        for lane, row in enumerate(rows):
            _need(type(row) is dict and set(row) == {'id','error','bytes','refusal','rx_before','rx_end'}, 'RESULT_ROW_FIELDS')
            for k in row:
                _int(row[k], 0, U32)
            _need(row['id'] > 0 and (prior_id is None or row['id'] == prior_id + 1)
                  and row['error'] == row['refusal'] == 0, 'RESULT_ID_OR_ERROR')
            n = _int(row['bytes'], 14, 63)
            _need((prior_rx is None or row['rx_before'] == prior_rx)
                  and row['rx_end'] == row['rx_before'] + n, 'RX_CURSOR')
            frame = wire[offset:offset+n]
            _need(len(frame) == n, 'TRUNCATED_FRAME')
            magic, version, kind, length, view, frame_seq, tick = struct.unpack_from('<2sBBBBHI', frame)
            _need(magic == b'\xa5\x5a' and version == 3 and kind == 0xe4 and view == 1
                  and n == length + 14 and frame_seq == 4*(s-1)+lane+1 and tick == adc*1000, 'E4_HEADER')
            _need(struct.unpack_from('<H', frame, n-2)[0] == binascii.crc_hqx(frame[2:-2], 0xffff), 'E4_CRC')
            payload = frame[12:-2]
            _need(len(payload) >= 21 and payload[0] == 2, 'E4_REVISION2')
            d = decode_payload(bytes([1])+payload[1:], {'session':self.binding.session_id,'config_epoch':1,'e':0})
            expected = dict(index=s,tick_ms=adc*1000,value=counts[lane],valid=counts[lane] is not None,
                            saturated=bool(q & (16 << lane)),held=counts[lane] is not None and em < adc,
                            source_fault=bool(q & 0x1000),source_tick_ms=em*1000 if counts[lane] is not None else None)
            _need(d['channel'] == lane and d['count'] == 1 and d['e'] == 0
                  and _raw(d['points']) == _raw([expected]), 'E4_CAUSAL_LOSSLESS_SOURCE')
            _need(_raw(declared[lane]) == _raw(d), 'SERVER_DECODE_NOT_INDEPENDENT_TRUTH')
            ledger = dict(d['ledger'],lane=lane,mode=d['mode'],e=0,result_id=row['id'],
                          frame_sha256=hashlib.sha256(frame).hexdigest())
            _need(ledger['frame_bytes'] == n and ledger['payload_bytes'] == length, 'CODEC_LEDGER_LENGTH')
            ledgers.append(ledger)
            prior_id, prior_rx, offset = row['id'], row['rx_end'], offset+n
        _need(offset == len(wire), 'NO_EXTRA_WIRE')
        ledger = dict(frames=ledgers,wire_bytes=len(wire),selected_raw_bytes=sum(x['selected_raw_bytes'] for x in ledgers),
                      code_bytes=sum(x['stored_code_bytes'] for x in ledgers),
                      significant_bits=sum(x['significant_bits'] for x in ledgers),
                      value_count=sum(v is not None for v in counts),lossless_e=0,
                      compression_ratio_claimed=False,tick_fields_unit='microseconds_in_legacy_tick_ms_keys')
        observation = E4Observation(tuple(counts),s,adc,em,q,request['source_digest'],tag,
                                    hashlib.sha256(wire).hexdigest(),request_sha,reply.response_sha256,_raw(ledger))
        self._source,self._request,self._tag = s,seq,tag
        self._adc,self._em,self._result,self._rx = adc,em,prior_id,prior_rx
        return observation
