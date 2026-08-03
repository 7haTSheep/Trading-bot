import unittest
import numpy as np
import quickscan


class InstitutionalEngineTests(unittest.TestCase):
    def test_entry_quality_score_weightings_and_grades(self):
        tf_data = {
            'M5': {'stack': 'BULL', 'rsi': 55.0, 'atr': 2.0},
            'M15': {'stack': 'BULL', 'rsi': 58.0, 'atr': 5.0},
            'H1': {'stack': 'BULL', 'rsi': 60.0, 'atr': 12.0},
        }
        score, grade, confidence, breakdown = quickscan.calculate_entry_quality_score(
            tf_data=tf_data,
            confluence_score=3,
            price=100.2,
            ema20=100.0,
            ema50=98.0,
            atr_val=2.0,
            vwap_val=99.5,
            london={'status': 'established', 'broke': 'above'},
            ny={'status': 'not_open'},
            rsi_val=55.0,
            adx_val=30.0,
            vol_ratio=1.0,
            trend='BULL'
        )
        self.assertGreaterEqual(score, 90)
        self.assertIn('A+', grade)
        self.assertEqual(confidence, 'High')
        self.assertEqual(breakdown['trend'], 30)
        self.assertEqual(breakdown['confluence'], 20)
        self.assertEqual(breakdown['ema_pullback'], 15)

    def test_trade_decision_buy_now(self):
        decision, icon, reason = quickscan.determine_trade_decision(
            trend='BULL',
            quality_score=92,
            price=100.2,
            ema20=100.0,
            atr_val=2.0,
            state='pullback',
            rsi_val=55.0,
            confluence_score=3
        )
        self.assertEqual(decision, 'BUY NOW')
        self.assertEqual(icon, '🟢')
        self.assertIn('Bullish', reason)

    def test_trade_decision_wait_for_pullback_when_extended(self):
        decision, icon, reason = quickscan.determine_trade_decision(
            trend='BULL',
            quality_score=92,
            price=110.0,
            ema20=100.0,
            atr_val=2.0,
            state='extended',
            rsi_val=78.0,
            confluence_score=3
        )
        self.assertEqual(decision, 'WAIT FOR PULLBACK')
        self.assertEqual(icon, '🟡')
        self.assertIn('extended', reason)

    def test_dynamic_stop_loss_selection(self):
        ds = quickscan.calculate_dynamic_stop(
            trend='BULL',
            price=100.0,
            atr_val=2.0,
            swing_high=105.0,
            swing_low=97.0,
            london={'status': 'not_open'},
            ny={'status': 'not_open'},
            order_blocks={'bullish': []},
            stop_atr_mult=2.0
        )
        self.assertEqual(ds.method, 'Below Swing Low')
        self.assertLess(ds.price, 97.0)

    def test_profit_targets_generation(self):
        targets = quickscan.calculate_profit_targets(
            trend='BULL',
            price=100.0,
            stop_dist=2.0,
            atr_val=2.0,
            swing_high=105.0,
            swing_low=95.0,
            pivots={'R1': 108.0}
        )
        self.assertEqual(len(targets), 4)
        self.assertEqual(targets[0].name, 'TP1')
        self.assertGreater(targets[0].price, 100.0)
        self.assertGreater(targets[1].rr, targets[0].rr)

    def test_profit_targets_are_ordered_away_from_entry(self):
        """A distant pivot must not push TP2 past TP3.

        R1 was previously taken for TP2 unconditionally, so a pivot beyond
        TP3's 4x ATR produced targets out of order: R:R fell as the target
        number rose, and the fixed 80/60/40 ladder then advertised a nearer
        target as less likely than a further one. An EA placing these as real
        take-profit orders would set them at the wrong levels.
        """
        for r1 in (104.0, 108.0, 110.0, 140.0):
            targets = quickscan.calculate_profit_targets(
                trend='BULL', price=100.0, stop_dist=2.0, atr_val=2.0,
                swing_high=105.0, swing_low=95.0, pivots={'R1': r1})
            prices = [t.price for t in targets]
            self.assertEqual(prices, sorted(prices), f'targets out of order for R1={r1}')
            self.assertEqual(len(set(prices)), len(prices), f'duplicate targets for R1={r1}')
            rrs = [t.rr for t in targets]
            self.assertEqual(rrs, sorted(rrs), f'R:R must rise with distance for R1={r1}')

        for s1 in (96.0, 92.0, 90.0, 60.0):
            targets = quickscan.calculate_profit_targets(
                trend='BEAR', price=100.0, stop_dist=2.0, atr_val=2.0,
                swing_high=105.0, swing_low=95.0, pivots={'S1': s1})
            prices = [t.price for t in targets]
            self.assertEqual(prices, sorted(prices, reverse=True), f'short targets out of order for S1={s1}')

    def test_fair_value_gap_detection(self):
        h = np.array([100.0, 101.0, 106.0, 107.0, 108.0])
        l = np.array([98.0, 99.0, 103.0, 105.0, 106.0])
        c = np.array([99.0, 100.5, 105.5, 106.5, 107.5])
        fvgs = quickscan.detect_fair_value_gaps(h, l, c)
        self.assertGreater(len(fvgs['bullish']), 0)
        self.assertEqual(fvgs['bullish'][0]['low'], 100.0)
        self.assertEqual(fvgs['bullish'][0]['high'], 103.0)

    def test_chart_marking_assistant(self):
        levels, guidance = quickscan.generate_chart_markings(
            price=100.0,
            swing_high=105.0,
            swing_low=95.0,
            london={'status': 'established', 'hi': 102.0, 'lo': 98.0},
            ny={'status': 'not_open'},
            pivots={'P': 99.0, 'R1': 104.0, 'S1': 96.0},
            vwap_val=99.5,
            e20=99.8,
            e50=98.5,
            e200=95.0,
            fvgs={'bullish': [{'low': 98.5, 'high': 99.2}], 'bearish': []},
            order_blocks={'bullish': [], 'bearish': []},
            liquidity={'eqh': 104.5, 'eql': 95.5},
            atr_val=2.0
        )
        self.assertGreater(len(levels), 5)
        self.assertGreater(len(guidance), 2)
        names = [lvl.name for lvl in levels]
        self.assertIn('Swing High', names)
        self.assertIn('London ORB High', names)
        self.assertIn('M5 EMA20', names)
        self.assertIn('Bullish FVG', names)

    def test_setup_checklist(self):
        items = quickscan.build_setup_checklist(
            trend='BULL',
            confluence_score=3,
            london={'status': 'established', 'broke': 'above'},
            ny={'status': 'not_open'},
            vwap_val=99.0,
            price=100.0,
            ema20=99.8,
            rsi_val=55.0,
            adx_val=28.0,
            liquidity={'eqh': 105.0, 'eql': 95.0},
            fits_account=True,
            quality_score=92
        )
        self.assertEqual(len(items), 8)
        statuses = [item.status for item in items]
        self.assertIn('YES', statuses)

    def test_scan_result_dict_serialization_for_windows_app(self):
        dp = quickscan.TradeDecisionPanel('BUY NOW', '🟢', 'Bullish trend', 92, 'A+', 'High')
        ep = quickscan.EntryPanel('BUY NOW', 'Healthy Pullback', 'Reason', '99.5-100.5', '104-105', ['Engulfing'], 2.4)
        ds = quickscan.DynamicStopInfo(97.0, 3.0, 'Below Swing Low', 'Structure protection')
        tp = quickscan.ProfitTargetItem('TP1', 104.0, 1.33, 80, '~20m')
        rp = quickscan.RiskPanel(ds, [tp], 0.1, 15.0, 1.5, True, '🟢 FIT')
        cmp = quickscan.ChartMarkingPanel([], [])
        tcp = quickscan.TradeChecklistPanel([])
        msp = quickscan.MarketStructurePanel('Strong', 'High', 'Discount', 'NORMAL', 'Expansion', 28.0, '100-105', '95-100', 96.0, 104.0)
        ps = quickscan.ProfessionalSummary('BULL', 'BUY NOW', '100', 97.0, 104.0, 108.0, 112.0, 'High', 'A+', 'Low', 'Enter')

        result = quickscan.ScanResult('EURUSD', 100.0, 100.1, 0.1, dp, ep, rp, cmp, tcp, msp, ps)
        res_dict = result.to_dict()
        self.assertEqual(res_dict['symbol'], 'EURUSD')
        self.assertEqual(res_dict['decision_panel']['decision'], 'BUY NOW')
        self.assertEqual(res_dict['summary']['grade'], 'A+')


if __name__ == '__main__':
    unittest.main()
