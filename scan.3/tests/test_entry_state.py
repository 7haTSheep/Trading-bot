import unittest

import quickscan


class EntryStateTests(unittest.TestCase):
    def test_bullish_pullback_is_detected(self):
        states = quickscan.classify_entry_state(
            price=100.0,
            ema20=100.2,
            atr=4.0,
            rsi=55,
            trend='BULL',
            swing_high=102.0,
            swing_low=98.0,
            orb_high=None,
            orb_low=None,
        )
        self.assertIn('pullback', states)
        self.assertEqual(quickscan.entry_state_label(states, trend='BULL'), 'BULLISH PULLBACK')

    def test_bullish_extension_and_exhaustion_are_detected(self):
        states = quickscan.classify_entry_state(
            price=107.0,
            ema20=100.0,
            atr=4.0,
            rsi=80,
            trend='BULL',
            swing_high=105.0,
            swing_low=95.0,
            orb_high=None,
            orb_low=None,
        )
        self.assertIn('extended', states)
        self.assertIn('exhausted', states)
        self.assertEqual(quickscan.entry_state_label(states, trend='BULL'), 'BULLISH EXTENDED/EXHAUSTED')

    def test_breakout_is_detected(self):
        states = quickscan.classify_entry_state(
            price=106.0,
            ema20=100.0,
            atr=4.0,
            rsi=50,
            trend='BULL',
            swing_high=105.0,
            swing_low=95.0,
            orb_high=104.0,
            orb_low=96.0,
        )
        self.assertIn('breakout', states)


if __name__ == '__main__':
    unittest.main()
