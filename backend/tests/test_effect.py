import unittest

from src.domain.demo import demo_completion_rows, demo_effect_rows
from src.domain.effect import _match, analyze_effect, validate_completion_rows


def site_row(site_id, district='滨河片区', fixtures=10):
    return {'record_type': '灯组台账', 'site_id': site_id, 'district': district,
            'site_name': f'{site_id}点位', 'fixture_count': fixtures, 'incident_id': None, 'report_date': None}


def order_rows(site_id, days, month='2026-11'):
    return [{'record_type': '暗区工单', 'site_id': site_id, 'district': None, 'site_name': None,
             'fixture_count': None, 'incident_id': f'GD-{site_id}-{day:02d}',
             'report_date': f'{month}-{day:02d}'} for day in days]


def registry(*entries):
    return [{'completion_id': f'ZG-{i:02d}', 'site_id': site, 'completion_date': day}
            for i, (site, day) in enumerate(entries, start=1)]


def pair_map(result):
    pairs, unmatched = result['tables'][0]['rows'], result['tables'][1]['rows']
    return {row['site_id']: row for row in pairs}, {row['site_id']: row for row in unmatched}


class CompletionValidationTest(unittest.TestCase):
    def test_normalizes_and_takes_first_date(self):
        rows = validate_completion_rows([
            {'completion_id': ' zg-01 ', 'site_id': ' lh-01 ', 'completion_date': '2026-11-16'},
            {'completion_id': 'ZG-02', 'site_id': 'LH-01', 'completion_date': '2026-11-12'},
        ])
        self.assertEqual(rows[0], {'completion_id': 'ZG-01', 'site_id': 'LH-01', 'completion_date': '2026-11-16'})

    def test_rejects_duplicate_and_bad_date(self):
        with self.assertRaises(ValueError):
            validate_completion_rows([
                {'completion_id': 'ZG-01', 'site_id': 'LH-01', 'completion_date': '2026-11-16'},
                {'completion_id': 'zg-01', 'site_id': 'LH-02', 'completion_date': '2026-11-17'},
            ])
        with self.assertRaises(ValueError):
            validate_completion_rows([{'completion_id': 'ZG-01', 'site_id': 'LH-01', 'completion_date': '11月16日'}])
        with self.assertRaises(ValueError):
            validate_completion_rows([])


class MatchingTest(unittest.TestCase):
    def test_max_pairs_before_min_weight(self):
        # 两个对照、三个整治组：必须先凑满两对，而不是只留差值最小的一对。
        candidates = {'A': [('X', 1), ('Y', 2)], 'B': [('X', 1)], 'C': [('Y', 9)]}
        pairs = _match(['A', 'B', 'C'], candidates)
        self.assertEqual(sorted(pairs), [('A', 'Y'), ('B', 'X')])

    def test_min_weight_among_full_matchings(self):
        candidates = {'A': [('X', 1), ('Y', 5)], 'B': [('X', 2), ('Y', 4)]}
        pairs = _match(['A', 'B'], candidates)
        self.assertEqual(sorted(pairs), [('A', 'X'), ('B', 'Y')])

    def test_control_used_once_and_deterministic(self):
        candidates = {'A': [('X', 0)], 'B': [('X', 0)]}
        first = _match(['A', 'B'], candidates)
        second = _match(['A', 'B'], candidates)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 1)  # 同一对照只能配给一对


class WindowTest(unittest.TestCase):
    def test_completion_day_excluded_and_first_date_used(self):
        rows = [site_row('LH-01'), site_row('LH-02')]
        rows += order_rows('LH-01', [9, 10, 12, 15, 16, 17, 23, 24])  # 12 日为首次完工当日
        rows += order_rows('LH-02', [10, 18])
        snap = registry(('LH-01', '2026-11-16'), ('LH-01', '2026-11-12'))  # 首次完工日取 11-12
        result = analyze_effect(rows, {'window_days': 7}, snap)
        pairs, _ = pair_map(result)
        # 首次完工日 11-12：前期 11-05–11-11（9、10 两单），后期 11-13–11-19（15、16、17 三单），12 日当单不计
        self.assertEqual(pairs['LH-01']['treated_pre'], 2)
        self.assertEqual(pairs['LH-01']['treated_post'], 3)
        self.assertEqual(pairs['LH-01']['pre_window'], '2026-11-05–2026-11-11')
        self.assertEqual(pairs['LH-01']['post_window'], '2026-11-13–2026-11-19')

    def test_control_must_be_untreated_through_window_end(self):
        rows = [site_row('LH-01'), site_row('LH-02'), site_row('LH-03')]
        rows += order_rows('LH-01', [10, 18])
        rows += order_rows('LH-02', [10, 18])
        rows += order_rows('LH-03', [10, 18])
        # LH-02 在窗口末日（11-23）当天完工：已整治，不能作对照；LH-03 窗口末日次日完工，仍可作对照。
        snap = registry(('LH-01', '2026-11-16'), ('LH-02', '2026-11-23'), ('LH-03', '2026-11-24'))
        result = analyze_effect(rows, {'window_days': 7}, snap)
        pairs, unmatched = pair_map(result)
        self.assertEqual(pairs['LH-01']['control_id'], 'LH-03')
        self.assertIn('LH-02', unmatched)


class EffectAnalysisTest(unittest.TestCase):
    def test_demo_dataset_pairs_and_average(self):
        result = analyze_effect(demo_effect_rows(), {'window_days': 7}, demo_completion_rows())
        pairs, unmatched = pair_map(result)
        self.assertEqual(set(pairs), {'LH-04', 'LH-09', 'LH-10'})
        self.assertEqual(pairs['LH-04']['control_id'], 'LH-01')
        self.assertEqual(pairs['LH-09']['control_id'], 'LH-08')
        self.assertEqual(pairs['LH-10']['control_id'], 'LH-05')
        self.assertEqual(pairs['LH-04']['diff'], 3)   # (5-0) - (6-4)
        self.assertEqual(pairs['LH-09']['diff'], 2)   # (5-2) - (4-3)
        self.assertEqual(pairs['LH-10']['diff'], 1)   # (4-2) - (3-2)
        self.assertEqual(set(unmatched), {'LH-02'})
        self.assertEqual(unmatched['LH-02']['reason'], '同片区可用对照已配完')
        metrics = {item['label']: item['value'] for item in result['metrics']}
        self.assertEqual(metrics['平均每对少报（单）'], 2.0)
        self.assertEqual(metrics['成功配对'], 3)
        self.assertEqual(metrics['未配对整治组'], 1)
        self.assertEqual(metrics['配对整治组合计少报（单）'], 10)

    def test_completion_day_order_not_counted_in_demo(self):
        result = analyze_effect(demo_effect_rows(), {'window_days': 7}, demo_completion_rows())
        _, unmatched = pair_map(result)
        # LH-02 在 11-16 完工当日有一单：前期 6 单（09–15）、后期 1 单（19），当日单不计。
        self.assertEqual(unmatched['LH-02']['treated_pre'], 6)
        self.assertEqual(unmatched['LH-02']['treated_post'], 1)

    def test_registry_gap_and_empty_registry(self):
        rows = [site_row('LH-01')]
        rows += order_rows('LH-01', [10, 18])
        snap = registry(('LH-01', '2026-11-16'), ('LH-99', '2026-11-16'))
        result = analyze_effect(rows, {'window_days': 7}, snap)
        self.assertEqual(result['tables'][2]['title'], '未匹配台账的完工登记')
        self.assertEqual(result['tables'][2]['rows'][0]['site_id'], 'LH-99')
        with self.assertRaises(ValueError):
            analyze_effect(rows, {'window_days': 7}, [])
        with self.assertRaises(ValueError):
            analyze_effect(rows, {'window_days': 7}, registry(('LH-99', '2026-11-16')))

    def test_late_completion_only_in_new_snapshot(self):
        rows = [site_row('LH-01'), site_row('LH-02')]
        rows += order_rows('LH-01', [10, 18])
        rows += order_rows('LH-02', [10, 18])
        early = registry(('LH-01', '2026-11-16'))
        late = registry(('LH-01', '2026-11-16'), ('LH-02', '2026-11-17'))
        first = analyze_effect(rows, {'window_days': 7}, early)
        second = analyze_effect(rows, {'window_days': 7}, late)
        self.assertEqual(first['tables'][0]['rows'][0]['control_id'], 'LH-02')  # 旧快照里 LH-02 仍未整治
        _, unmatched = pair_map(second)
        self.assertEqual(set(unmatched), {'LH-01', 'LH-02'})  # 新快照里两组都完工，彼此窗口末日均已整治

    def test_window_days_param(self):
        rows = [site_row('LH-01'), site_row('LH-02')]
        rows += order_rows('LH-01', [14, 15, 17, 18])
        rows += order_rows('LH-02', [14, 18])
        result = analyze_effect(rows, {'window_days': 3}, registry(('LH-01', '2026-11-16')))
        pairs, _ = pair_map(result)
        # 窗口 3 天：前期 11-13–11-15（14、15），后期 11-17–11-19（17、18）
        self.assertEqual(pairs['LH-01']['treated_pre'], 2)
        self.assertEqual(pairs['LH-01']['treated_post'], 2)
        with self.assertRaises(ValueError):
            analyze_effect(rows, {'window_days': 0}, registry(('LH-01', '2026-11-16')))


if __name__ == '__main__':
    unittest.main()
