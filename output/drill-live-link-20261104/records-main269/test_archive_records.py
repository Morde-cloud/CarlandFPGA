"""Focused new archival boundaries, using public835 samples; no device IO."""
from pathlib import Path
import copy
import hashlib
import json
import sys
import unittest

R = Path(__file__).resolve().parents[3]
D = Path(__file__).resolve().parents[1]
P = R / '.local/deployment/node-b/main-handoff-20261029/successor-01/successor-work/resume-88'
A = P / 'A261/handoffs/a/A-CONTINUOUS-ACTUAL-835'
sys.path.insert(0, str(D))
import archive_records as adapter
from drill_live_link.model import FollowMapper, FollowError


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chain = json.loads((A / 'ACTUAL_FIRST_CHAIN.json').read_bytes())
        cls.phases = json.loads((A / 'ACTUAL_PHASES.json').read_bytes())
        cls.result = json.loads((A / 'RESULT835.json').read_bytes())
        cls.context = adapter.Context(cls.result['operation_id'], cls.result['world_epoch'],
            '9821bbdf0f6e7bd8e156bc699156fb9f8371dba0',
            hashlib.sha256((A / 'ACTUAL_FIRST_CHAIN.json').read_bytes()).hexdigest(),
            'ACTUAL_FIRST_CHAIN.json', 'A835-QPC-ns', 'A835-native-us', 'A834-monotonic-ns')

    def test_original_clocks_and_pose_preserved(self):
        event = self.phases['last']
        row = adapter.adapt_event(event, self.context)
        self.assertEqual(row['payload']['actual_pose']['tick_usec'], event['sample']['native']['tick_usec'])
        self.assertEqual(row['payload']['host_sample']['accepted_tick_qpc_interval_ns'], event['sample']['host']['accepted_tick_qpc_interval_ns'])
        self.assertEqual(row['payload']['host_event_qpc_ns'], event['host_qpc_ns'])
        self.assertEqual(len(set(row['provenance']['clock_domains'].values())), 3)

    def test_actual_target_command_and_capture_stay_separate(self):
        row = adapter.adapt_event(self.chain[3], self.context)['payload']
        self.assertEqual(row['actual_pose']['speed_m_s'], 0)
        self.assertEqual(row['actual_pose']['target_speed_m_s'], .025)
        self.assertEqual(row['requested_command']['speed_code'], 2)
        self.assertEqual(row['actual_board']['measurement_or_stop']['capture_words'][15:18], [125000, 125000, 26000])
        self.assertEqual(row['actual_board']['host_deadline_qpc_ns'], self.chain[3]['board']['host_deadline_qpc_ns'])

    def test_C3_null_and_original_source_acquisition(self):
        source = adapter.adapt_event(self.chain[1], self.context)['payload']
        ai = adapter.adapt_event(self.chain[2], self.context)['payload']
        self.assertIsNone(source['channel_counts'][3])
        self.assertIsNone(ai['advice']['decoded_features'][3])
        self.assertEqual(source['source_acquisition_qpc_ns'], ai['advice']['source_acquisition_qpc_ns'])

    def test_every_kind_archival_and_live_follower_refuses(self):
        rows = [adapter.adapt_event(v, self.context) for v in self.chain]
        rows += [adapter.adapt_event(self.phases['last'], self.context), adapter.adapt_result(self.result, self.context)]
        for row in rows:
            self.assertEqual(row['authority'], 'archival_read_only')
            self.assertIs(row['live'], False)
            self.assertIs(row['may_drive'], False)
            with self.assertRaises(FollowError):
                FollowMapper('test', 'MANUAL', [0, 0, 0, 1]).map(row, now_ns=1)

    def test_canonical_response_tamper_rejected(self):
        event = copy.deepcopy(self.chain[3])
        event['board']['response']['result']['pwm_high'][0] += 1
        with self.assertRaisesRegex(ValueError, 'canonical response SHA256'):
            adapter.adapt_event(event, self.context)

    def test_epoch_and_operation_mismatch_rejected(self):
        for index in (1, 2):
            event = copy.deepcopy(self.chain[index])
            event['public_observation' if index == 1 else 'advice']['world_epoch'] = 'foreign'
            with self.assertRaises(ValueError):
                adapter.adapt_event(event, self.context)
        result = dict(self.result, operation_id='foreign')
        with self.assertRaisesRegex(ValueError, 'operation/epoch'):
            adapter.adapt_result(result, self.context)

    def test_unknown_nan_and_malformed_bool_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unsupported public event'):
            adapter.adapt_event({'event': 'move_now', 'host_qpc_ns': '1'}, self.context)
        event = copy.deepcopy(self.phases['last'])
        event['sample']['native']['position_m'][0] = float('nan')
        with self.assertRaises(ValueError):
            adapter.adapt_event(event, self.context)
        event = copy.deepcopy(self.phases['last'])
        event['sample']['native']['ready'] = 1
        with self.assertRaisesRegex(ValueError, 'boolean'):
            adapter.adapt_event(event, self.context)

    def test_unknown_response_retained_without_motion_authority(self):
        event = copy.deepcopy(self.chain[3])
        event['board']['response']['unknown'] = True
        event['board']['response_sha256'] = hashlib.sha256(json.dumps(event['board']['response'], sort_keys=True, separators=(',', ':')).encode('ascii')).hexdigest()
        row = adapter.adapt_event(event, self.context)
        self.assertIs(row['payload']['actual_board']['unknown'], True)
        self.assertIs(row['may_drive'], False)

    def test_unknown_fields_never_exported_even_nested(self):
        event = copy.deepcopy(self.chain[3])
        event['control_token'] = 'SECRET_SENTINEL'
        event['board']['response']['result']['measured']['hidden_geometry'] = 'SECRET_SENTINEL'
        event['board']['response_sha256'] = hashlib.sha256(json.dumps(event['board']['response'], sort_keys=True, separators=(',', ':')).encode('ascii')).hexdigest()
        self.assertNotIn('SECRET_SENTINEL', json.dumps(adapter.adapt_event(event, self.context)))
        event = copy.deepcopy(self.chain[2])
        event['advice']['control_token'] = 'SECRET_SENTINEL'
        event['advice']['source_pose']['hidden_geometry'] = 'SECRET_SENTINEL'
        self.assertNotIn('SECRET_SENTINEL', json.dumps(adapter.adapt_event(event, self.context)))

    def test_terminal_ACK_zero_and_connection_remain_distinct(self):
        row = adapter.adapt_result(self.result, self.context)['payload']
        self.assertIs(row['native_stop']['response_ok'], True)
        self.assertIs(row['native_stop']['board_stop_acknowledged'], False)
        self.assertEqual(row['actual_board_stop']['request_seq'], 836)
        self.assertEqual(row['actual_board_stop']['measurement_or_stop']['fault'], 6)
        self.assertIs(row['connection_close']['physical_zero_capture_proven'], False)
        self.assertIs(row['connection_close']['wait_confirmed'], True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
