"""Tests for the calibration gate.

These guard the one property that makes an adaptive layer safe here: it must
refuse to act until the evidence is strong. The measured edge on these
instruments is a few hundredths of an R, and a 130-setup study during
development concluded four of five instruments were unprofitable, which
reversed entirely at 1,000 setups. A gate that can be talked round by a
short losing streak would encode that kind of reversal as fact.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calibration
import outcome_tracker as ot


def signal(symbol, score, outcome):
    return {'symbol': symbol, 'timeframe': 'M5', 'logged_at_utc': 'x',
            'signal_time': 1, 'direction': 'BUY', 'decision': 'BUY NOW',
            'grade': 'A', 'score': score, 'entry': 100.0, 'stop': 98.0,
            'targets': {'TP1': 103.0}, 'outcome': outcome,
            'outcome_bars': 3, 'resolved_at_utc': 'y'}


class CalibrationGateTests(unittest.TestCase):
    def test_small_losing_streak_changes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            ot._rewrite([signal('BAD', 88, 'SL') for _ in range(50)], d)
            suppress, _ = calibration.should_suppress('BAD', 88, d)
            self.assertFalse(suppress, 'acted on a sample far below MIN_SAMPLES')

    def test_large_negative_sample_suppresses(self):
        with tempfile.TemporaryDirectory() as d:
            n = calibration.MIN_SAMPLES + 50
            ot._rewrite([signal('BAD', 88, 'SL') for _ in range(n)], d)
            suppress, reason = calibration.should_suppress('BAD', 88, d)
            self.assertTrue(suppress)
            self.assertIn('BAD', reason)

    def test_ambiguous_large_sample_is_left_alone(self):
        half = calibration.MIN_SAMPLES
        with tempfile.TemporaryDirectory() as d:
            ot._rewrite([signal('MIX', 88, 'SL') for _ in range(half)] +
                        [signal('MIX', 88, 'TP1') for _ in range(half)], d)
            suppress, _ = calibration.should_suppress('MIX', 88, d)
            self.assertFalse(suppress, 'suppressed a bucket that is not clearly negative')

    def test_profitable_bucket_is_never_suppressed(self):
        with tempfile.TemporaryDirectory() as d:
            ot._rewrite([signal('GOOD', 88, 'TP1')
                         for _ in range(calibration.MIN_SAMPLES + 50)], d)
            suppress, _ = calibration.should_suppress('GOOD', 88, d)
            self.assertFalse(suppress)

    def test_r_multiple_matches_the_level_reached(self):
        # Entry 100, stop 98 means 1R is 2 points; TP1 at 103 is therefore 1.5R.
        self.assertAlmostEqual(calibration._r_multiple(signal('X', 88, 'TP1')), 1.5)
        self.assertAlmostEqual(calibration._r_multiple(signal('X', 88, 'SL')), -1.0)
        self.assertAlmostEqual(calibration._r_multiple(signal('X', 88, 'EXPIRED')), 0.0)
        self.assertIsNone(calibration._r_multiple(signal('X', 88, 'OPEN')))


class EntryPlacementTests(unittest.TestCase):
    """Where the entry sat relative to the zone the scanner published.

    A buy waits for price to fall into the zone, so an entry above it was
    taken before price arrived and one below it after price passed through.
    A sell mirrors that, which is the part easiest to get backwards.
    """

    def test_buy_placement(self):
        self.assertEqual(ot._classify_placement('BUY', 101, 100, 102), ot.PLACEMENT_IN)
        self.assertEqual(ot._classify_placement('BUY', 105, 100, 102), ot.PLACEMENT_BEFORE)
        self.assertEqual(ot._classify_placement('BUY', 95, 100, 102), ot.PLACEMENT_AFTER)

    def test_sell_placement_is_mirrored(self):
        self.assertEqual(ot._classify_placement('SELL', 101, 100, 102), ot.PLACEMENT_IN)
        self.assertEqual(ot._classify_placement('SELL', 95, 100, 102), ot.PLACEMENT_BEFORE)
        self.assertEqual(ot._classify_placement('SELL', 105, 100, 102), ot.PLACEMENT_AFTER)

    def test_boundaries_count_as_inside(self):
        self.assertEqual(ot._classify_placement('BUY', 100, 100, 102), ot.PLACEMENT_IN)
        self.assertEqual(ot._classify_placement('BUY', 102, 100, 102), ot.PLACEMENT_IN)

    def test_missing_zone_yields_no_placement(self):
        self.assertIsNone(ot._classify_placement('BUY', 101, None, None))

    def test_zone_parsing_handles_en_dash(self):
        # The scanner renders zones with an en dash, not a hyphen.
        self.assertEqual(ot._zone_bounds('7854.9–7865.9'), (7854.9, 7865.9))
        self.assertEqual(ot._zone_bounds('7854.9-7865.9'), (7854.9, 7865.9))
        self.assertEqual(ot._zone_bounds(''), (None, None))


if __name__ == '__main__':
    unittest.main()
