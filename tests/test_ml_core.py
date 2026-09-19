import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core.sites import BUILDING_ENVIRONMENT, ENVIRONMENTS, resolve_environment, resolve_site_id


class TestResolveSiteId(unittest.TestCase):
  def test_numeric_locals_become_residence_positions(self):
    result = resolve_site_id(pd.Series([1.0, 2.0, 3.0, 1.0]))
    self.assertEqual(list(result),
                     ['res-sala', 'res-quarto', 'res-suite', 'res-sala'])

  def test_room_names_resolve_to_the_same_positions_as_their_numbers(self):
    # O transform reescreve os nomes como 1/2/3; as duas grafias são a mesma posição.
    numbers = resolve_site_id(pd.Series([1.0, 2.0, 3.0]))
    names = resolve_site_id(pd.Series(['sala', 'quarto', 'suite']))
    self.assertEqual(list(numbers), list(names))

  def test_uppercase_room_name_resolves_like_lowercase(self):
    result = resolve_site_id(pd.Series(['Sala', 'SALA', 'sala']))
    self.assertEqual(list(result), ['res-sala', 'res-sala', 'res-sala'])

  def test_office_positions_stay_distinct_at_position_level(self):
    office = pd.Series(['cwpb-2m', 'cwpb-10m', 'cwpb-10m-2a', 'cwpb-13m'])
    result = resolve_site_id(office)
    self.assertEqual(result.nunique(), 4)

  def test_building_level_collapses_to_two_groups(self):
    mixed = pd.Series([1.0, 2.0, 3.0, 'cwpb-2m', 'cwpb-13m'])
    result = resolve_site_id(mixed, level='building')
    self.assertEqual(sorted(result.unique()), ['coworking', 'residencia'])

  def test_hotmilk_is_its_own_building(self):
    mixed = pd.Series(['sala', 'cwpb-1', 'hotmilk-copa', 'hotmilk-aquario-fora'])
    result = resolve_site_id(mixed, level='building')
    self.assertEqual(list(result), ['residencia', 'coworking', 'hotmilk', 'hotmilk'])

  def test_hotmilk_positions_stay_distinct_at_position_level(self):
    result = resolve_site_id(pd.Series(['hotmilk-copa', 'hotmilk-aquario', 'hotmilk-aquario-fora']))
    self.assertEqual(result.nunique(), 3)

  def test_old_hotmilk_label_resolves_to_corrected_position(self):
    result = resolve_site_id(pd.Series(['quarto-marcelo', 'hotmilk-aquario']))
    self.assertEqual(list(result), ['hotmilk-aquario', 'hotmilk-aquario'])

  def test_environment_flags_domestic_and_corporate(self):
    result = resolve_environment(pd.Series(['sala', 2.0, 'cwpb-2m', 'hotmilk-copa']))
    self.assertEqual(list(result), ['domestico', 'domestico', 'corporativo', 'corporativo'])

  def test_every_building_has_an_environment(self):
    self.assertEqual(set(BUILDING_ENVIRONMENT.values()), set(ENVIRONMENTS))
    for building in ('residencia', 'coworking', 'hotmilk'):
      self.assertIn(building, BUILDING_ENVIRONMENT)

  def test_unknown_level_raises(self):
    with self.assertRaises(ValueError) as ctx:
      resolve_site_id(pd.Series([1.0]), level='predio')
    self.assertIn('predio', str(ctx.exception))

  def test_unknown_value_raises(self):
    with self.assertRaises(ValueError) as ctx:
      resolve_site_id(pd.Series(['garage']))
    self.assertIn('garage', str(ctx.exception))

  def test_empty_value_raises(self):
    with self.assertRaises(ValueError):
      resolve_site_id(pd.Series([np.nan]))

  def test_non_integer_float_raises(self):
    with self.assertRaises(ValueError) as ctx:
      resolve_site_id(pd.Series([1.5]))
    self.assertIn('1.5', str(ctx.exception))

  def test_infinite_value_raises(self):
    with self.assertRaises(ValueError) as ctx:
      resolve_site_id(pd.Series(['inf']))
    self.assertIn('inf', str(ctx.exception))


from ml.core.splits import assert_sites_disjoint, outer_logo_folds, validate_site_count


def _frame(n_per_site=4, sites=('home-1', 'home-2', 'home-3', 'office-cwpb')):
  # Build each site's rows as its own frame (indices 0..n_per_site-1) and
  # concat *without* ignore_index, so the merged frame has duplicate,
  # non-monotonic index labels across sites -- the same shape the real
  # multi-CSV per-site loading produces. This is what makes the disjointness
  # tests below actually exercise `.iloc` vs `.loc`: on a fresh RangeIndex
  # the two are indistinguishable, so a regression to `.loc` would pass
  # silently.
  site_frames = []
  for s in sites:
    rows = [{'site_id': s, 'feat': float(i), 'target': float(i) * 2} for i in range(n_per_site)]
    site_frames.append(pd.DataFrame(rows))
  return pd.concat(site_frames)


class TestSplits(unittest.TestCase):
  def setUp(self):
    self.df = _frame()
    self.X = self.df[['feat']]
    self.y = self.df['target']
    self.sites = self.df['site_id']

  def test_every_fold_has_disjoint_sites(self):
    for fold in outer_logo_folds(self.X, self.y, self.sites):
      self.assertEqual(set(fold.train_sites) & {fold.test_site}, set())

  def test_each_site_is_test_exactly_once(self):
    tested = [f.test_site for f in outer_logo_folds(self.X, self.y, self.sites)]
    self.assertEqual(sorted(tested), sorted(self.sites.unique()))

  def test_fold_count_equals_site_count(self):
    folds = list(outer_logo_folds(self.X, self.y, self.sites))
    self.assertEqual(len(folds), self.sites.nunique())

  def test_disjointness_assertion_rejects_overlap(self):
    with self.assertRaises(AssertionError) as ctx:
      assert_sites_disjoint(['home-1', 'home-2'], ['home-2'])
    self.assertIn('home-2', str(ctx.exception))

  def test_single_site_is_rejected(self):
    with self.assertRaises(ValueError):
      validate_site_count(pd.Series(['home-1', 'home-1']))

  def test_three_sites_warns(self):
    with self.assertWarns(UserWarning):
      validate_site_count(pd.Series(['home-1', 'home-2', 'home-3']))

  def test_inner_splits_never_contain_outer_test_site(self):
    from ml.core.splits import inner_logo_splits
    for fold in outer_logo_folds(self.X, self.y, self.sites):
      inner = inner_logo_splits(fold.train_site_ids)
      self.assertGreaterEqual(len(inner), 2)
      for tr, va in inner:
        seen = set(fold.train_site_ids.iloc[tr]) | set(fold.train_site_ids.iloc[va])
        self.assertNotIn(fold.test_site, seen)

  def test_inner_splits_are_site_disjoint(self):
    from ml.core.splits import inner_logo_splits
    fold = next(iter(outer_logo_folds(self.X, self.y, self.sites)))
    for tr, va in inner_logo_splits(fold.train_site_ids):
      assert_sites_disjoint(fold.train_site_ids.iloc[tr], fold.train_site_ids.iloc[va])


from ml.core.metrics import (
  CLASS_NAMES,
  apply_thresholds,
  quartile_thresholds,
  regression_metrics,
  safe_mape,
)


class TestMetrics(unittest.TestCase):
  def test_mape_is_a_percentage(self):
    y_true = np.array([100.0, 100.0])
    y_pred = np.array([110.0, 90.0])
    self.assertAlmostEqual(safe_mape(y_true, y_pred), 10.0, places=6)

  def test_mape_ignores_zero_denominators(self):
    y_true = np.array([0.0, 100.0])
    y_pred = np.array([5.0, 110.0])
    self.assertAlmostEqual(safe_mape(y_true, y_pred), 10.0, places=6)

  def test_mape_all_zero_is_nan(self):
    self.assertTrue(np.isnan(safe_mape(np.array([0.0]), np.array([1.0]))))

  def test_thresholds_ignore_test_fold_values(self):
    y_train = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    baseline = quartile_thresholds(y_train)
    # A wildly different test fold must not move the training thresholds.
    _ = pd.Series([1000.0, 2000.0, 3000.0])
    self.assertEqual(quartile_thresholds(y_train), baseline)

  def test_apply_thresholds_labels_three_classes(self):
    labels = apply_thresholds(pd.Series([0.0, 5.0, 100.0]), 1.0, 10.0)
    self.assertEqual(list(labels), CLASS_NAMES)

  def test_single_class_fold_raises_clear_error(self):
    from ml.core.metrics import assert_multiclass
    with self.assertRaises(ValueError) as ctx:
      assert_multiclass(pd.Series(['bad', 'bad', 'bad']), 'home-2')
    self.assertIn('home-2', str(ctx.exception))

  def test_tied_thresholds_raise_clear_error_not_pandas_internal(self):
    y_train = pd.Series([5.0] * 10 + [1.0] * 2 + [20.0] * 2)
    t_low, t_high = quartile_thresholds(y_train)
    self.assertEqual(t_low, t_high)
    with self.assertRaises(ValueError) as ctx:
      apply_thresholds(y_train, t_low, t_high)
    self.assertIn('5.0', str(ctx.exception))

  def test_apply_thresholds_boundary_belongs_to_class_above(self):
    labels = apply_thresholds(pd.Series([1.0, 10.0]), 1.0, 10.0)
    self.assertEqual(list(labels), ['mid', 'good'])

  def test_regression_metrics_perfect_prediction(self):
    y = np.array([1.0, 2.0, 3.0])
    metrics = regression_metrics(y, y)
    self.assertEqual(set(metrics.keys()), {'r2', 'rmse', 'mae', 'mape_pct', 'p90_ae'})
    self.assertAlmostEqual(metrics['r2'], 1.0, places=6)
    self.assertAlmostEqual(metrics['rmse'], 0.0, places=6)
    self.assertAlmostEqual(metrics['mae'], 0.0, places=6)
    self.assertAlmostEqual(metrics['mape_pct'], 0.0, places=6)
    self.assertAlmostEqual(metrics['p90_ae'], 0.0, places=6)

  def test_disjoint_scales_raise(self):
    from ml.core.metrics import assert_comparable_scales
    y = pd.Series([0.1, 0.5, 1.9, 3.0, 20.0, 6000.0])
    groups = pd.Series(['coworking'] * 3 + ['residencia'] * 3)
    with self.assertRaises(ValueError) as ctx:
      assert_comparable_scales(y, groups, 'qoe_dw_score')
    message = str(ctx.exception)
    self.assertIn('coworking', message)
    self.assertIn('residencia', message)
    self.assertIn('qoe_dw_score', message)

  def test_overlapping_scales_pass(self):
    from ml.core.metrics import assert_comparable_scales
    y = pd.Series([38.0, 94.0, 204.0, 567.0, 48.0, 105.0, 208.0, 667.0])
    groups = pd.Series(['coworking'] * 4 + ['residencia'] * 4)
    assert_comparable_scales(y, groups, 'speedtest_down_mbps')

  def test_single_group_has_nothing_to_compare(self):
    from ml.core.metrics import assert_comparable_scales
    y = pd.Series([1.0, 2.0, 3.0])
    groups = pd.Series(['residencia'] * 3)
    assert_comparable_scales(y, groups, 'qualquer_alvo')

  def test_length_mismatch_raises_instead_of_silently_passing(self):
    from ml.core.metrics import assert_comparable_scales
    y = pd.Series([0.1, 0.5, 1.9])
    groups = pd.Series(['coworking', 'coworking'])
    with self.assertRaises(ValueError) as ctx:
      assert_comparable_scales(y, groups, 'qualquer_alvo')
    self.assertIn('mesmo comprimento', str(ctx.exception))

  def test_three_groups_only_the_true_violation_is_flagged(self):
    from ml.core.metrics import assert_comparable_scales
    y = pd.Series([10.0, 15.0, 20.0, 30.0,   # sala
                   12.0, 18.0, 25.0, 35.0,   # quarto — qualidade diferente da sala, mesma unidade
                   0.1, 0.2, 0.3, 0.4])      # coworking — unidade genuinamente diferente
    groups = pd.Series(['sala'] * 4 + ['quarto'] * 4 + ['coworking'] * 4)
    with self.assertRaises(ValueError) as ctx:
      assert_comparable_scales(y, groups, 'qualquer_alvo')
    message = str(ctx.exception)
    self.assertIn('coworking', message)


import tempfile

from ml.core.data import load_datasets, validate_columns


class TestData(unittest.TestCase):
  def _write_csv(self, rows):
    handle = tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False)
    pd.DataFrame(rows).to_csv(handle.name, index=False)
    handle.close()
    return handle.name

  def _write_text(self, content):
    handle = tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False)
    handle.write(content)
    handle.close()
    return handle.name

  def test_merges_multiple_files_and_adds_site_id(self):
    a = self._write_csv([{'local': 1.0, 'feat': 1.0, 'target': 2.0}])
    b = self._write_csv([{'local': 'cwpb-2m', 'feat': 3.0, 'target': 4.0}])
    df = load_datasets([a, b])
    self.assertEqual(len(df), 2)
    self.assertEqual(sorted(df['site_id'].unique()), ['cwpb-2m', 'res-sala'])

  def test_missing_column_raises_with_name(self):
    df = pd.DataFrame({'a': [1]})
    with self.assertRaises(ValueError) as ctx:
      validate_columns(df, ['b'], 'feature')
    self.assertIn('b', str(ctx.exception))

  def test_rows_with_nan_target_are_dropped(self):
    path = self._write_csv([
      {'local': 1.0, 'feat': 1.0, 'target': 2.0},
      {'local': 1.0, 'feat': 1.0, 'target': None},
    ])
    df = load_datasets([path], target='target')
    self.assertEqual(len(df), 1)

  def test_target_missing_in_one_file_raises_instead_of_dropping_silently(self):
    a = self._write_csv([{'local': 1.0, 'feat': 1.0, 'target': 2.0}])
    b = self._write_csv([{'local': 2.0, 'feat': 3.0, 'targett': 4.0}])
    with self.assertRaises(ValueError) as ctx:
      load_datasets([a, b], target='target')
    self.assertIn('target', str(ctx.exception))

  def test_malformed_csv_raises_with_path(self):
    path = self._write_text('local,feat,target\n1,2,3\n1,2,3,4\n')
    with self.assertRaises(ValueError) as ctx:
      load_datasets([path])
    self.assertIn(path, str(ctx.exception))

  def test_merged_index_is_contiguous(self):
    a = self._write_csv([
      {'local': 1.0, 'feat': 1.0, 'target': 2.0},
      {'local': 2.0, 'feat': 3.0, 'target': 4.0},
    ])
    b = self._write_csv([
      {'local': 'cwpb-2m', 'feat': 5.0, 'target': 6.0},
      {'local': 'cwpb-3m', 'feat': 7.0, 'target': 8.0},
    ])
    df = load_datasets([a, b])
    self.assertEqual(list(df.index), list(range(len(df))))

  def test_group_level_building_merges_positions(self):
    a = self._write_csv([{'local': 1.0, 'feat': 1.0, 'target': 2.0},
                         {'local': 2.0, 'feat': 2.0, 'target': 3.0}])
    b = self._write_csv([{'local': 'cwpb-2m', 'feat': 3.0, 'target': 4.0}])
    by_position = load_datasets([a, b])
    by_building = load_datasets([a, b], group_level='building')
    self.assertEqual(by_position['site_id'].nunique(), 3)
    self.assertEqual(sorted(by_building['site_id'].unique()),
                     ['coworking', 'residencia'])


import re

from ml.core.reporting import format_fold_plan, format_per_site_table


class TestReporting(unittest.TestCase):
  def test_fold_plan_names_train_and_test_sites(self):
    text = format_fold_plan([('home-1', 'home-2'), ('home-1', 'home-3')],
                            ['home-3', 'home-2'])
    self.assertIn('home-3', text)
    self.assertIn('fold 0', text)

  def test_fold_plan_raises_on_mismatched_lengths(self):
    with self.assertRaises(ValueError) as ctx:
      format_fold_plan(
        [('home-1', 'home-2'), ('home-1', 'home-3'), ('home-2', 'home-3')],
        ['home-3', 'home-2'])
    message = str(ctx.exception)
    self.assertIn('3', message)
    self.assertIn('2', message)

  def test_per_site_table_reports_spread_and_n(self):
    rows = [
      {'model': 'rf', 'test_site': 'home-1', 'r2': 0.5},
      {'model': 'rf', 'test_site': 'home-2', 'r2': 0.1},
    ]
    text = format_per_site_table(pd.DataFrame(rows), 'r2')
    self.assertIn('home-1', text)
    self.assertIn('n_sites=2', text)

  def test_per_site_table_supports_multiple_models(self):
    rows = [
      {'model': 'rf', 'test_site': 'home-1', 'r2': 0.5},
      {'model': 'rf', 'test_site': 'home-2', 'r2': 0.1},
      {'model': 'svm', 'test_site': 'home-1', 'r2': 0.4},
      {'model': 'svm', 'test_site': 'home-2', 'r2': 0.3},
    ]
    text = format_per_site_table(pd.DataFrame(rows), 'r2')
    self.assertIn('rf', text)
    self.assertIn('svm', text)
    self.assertIn('n_sites=2', text)

  def test_per_site_table_n_reflects_missing_site_per_model(self):
    rows = [
      {'model': 'rf', 'test_site': 'home-1', 'r2': 0.5},
      {'model': 'rf', 'test_site': 'home-2', 'r2': 0.1},
      {'model': 'svm', 'test_site': 'home-1', 'r2': 0.3},
    ]
    text = format_per_site_table(pd.DataFrame(rows), 'r2')
    n_by_model = {}
    for line in text.splitlines():
      tokens = line.split()
      if tokens and tokens[0] in ('rf', 'svm'):
        n_token = next(token for token in tokens[1:] if re.fullmatch(r'\d+', token))
        n_by_model[tokens[0]] = int(n_token)
    self.assertEqual(n_by_model['rf'] - n_by_model['svm'], 1)

  def test_per_site_table_raises_friendly_error_on_duplicate_model_site(self):
    rows = [
      {'model': 'rf', 'test_site': 'home-1', 'r2': 0.5},
      {'model': 'rf', 'test_site': 'home-1', 'r2': 0.6},
    ]
    with self.assertRaises(ValueError) as ctx:
      format_per_site_table(pd.DataFrame(rows), 'r2')
    message = str(ctx.exception).lower()
    self.assertIn('duplicate', message)
    self.assertIn('model', message)
    self.assertIn('test_site', message)


from ml.core.data import SITE_COLUMN


class TestIntegration(unittest.TestCase):
  def _write_csv(self, rows):
    handle = tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False)
    pd.DataFrame(rows).to_csv(handle.name, index=False)
    handle.close()
    return handle.name

  def test_load_datasets_output_feeds_outer_logo_folds_without_leakage(self):
    # Real multi-CSV merge + real resolve_site_id (numeric -> res-<cômodo>,
    # cwpb-* -> its own position, including across files), not the hand-built
    # site_id column TestSplits uses. This is the connection between
    # core/data.py and core/splits.py that the CLI scripts rely on.
    a = self._write_csv([
      {'local': 1.0, 'feat': 1.0, 'target': 10.0},
      {'local': 1.0, 'feat': 2.0, 'target': 20.0},
      {'local': 2.0, 'feat': 3.0, 'target': 30.0},
      {'local': 2.0, 'feat': 4.0, 'target': 40.0},
      {'local': 'cwpb-2m', 'feat': 5.0, 'target': 50.0},
    ])
    b = self._write_csv([
      {'local': 3.0, 'feat': 6.0, 'target': 60.0},
      {'local': 3.0, 'feat': 7.0, 'target': 70.0},
      {'local': 'cwpb-10m', 'feat': 8.0, 'target': 80.0},
    ])

    df = load_datasets([a, b], target='target')
    X = df[['feat']]
    y = df['target']
    sites = df[SITE_COLUMN]

    folds = outer_logo_folds(X, y, sites)

    for fold in folds:
      self.assertEqual(set(fold.train_sites) & {fold.test_site}, set())
    self.assertEqual(sorted(f.test_site for f in folds), sorted(sites.unique()))


from ml.fix_target_scale import denormalise_targets


class TestDenormaliseTargets(unittest.TestCase):
  def test_normalised_column_is_multiplied_back(self):
    df = pd.DataFrame({'speedtest_down_mbps': [0.0, 0.5, 1.0]})
    fixed, report = denormalise_targets(df, {'speedtest_down_mbps': 600.0})
    self.assertEqual(list(fixed['speedtest_down_mbps']), [0.0, 300.0, 600.0])
    self.assertIn('600', report['speedtest_down_mbps'])

  def test_already_physical_column_is_untouched(self):
    # Idempotência: rodar o script duas vezes não pode multiplicar duas vezes.
    df = pd.DataFrame({'latency_ms': [10.0, 500.0, 1947.1]})
    fixed, report = denormalise_targets(df, {'latency_ms': 4464.33})
    self.assertEqual(list(fixed['latency_ms']), [10.0, 500.0, 1947.1])
    self.assertEqual(report['latency_ms'], 'already physical')

  def test_absent_column_is_reported_not_skipped(self):
    df = pd.DataFrame({'jitter_ms': [0.0, 1.0]})
    fixed, report = denormalise_targets(df, {'nao_existe': 100.0})
    self.assertEqual(report['nao_existe'], 'not found in dataframe')
    self.assertEqual(list(fixed['jitter_ms']), [0.0, 1.0])

  def test_all_nan_column_is_reported_distinctly(self):
    df = pd.DataFrame({'speedtest_down_mbps': [None, None]})
    fixed, report = denormalise_targets(df, {'speedtest_down_mbps': 600.0})
    self.assertEqual(report['speedtest_down_mbps'], 'no data (all NaN)')

  def test_value_exactly_at_threshold_is_treated_as_normalised(self):
    df = pd.DataFrame({'jitter_ms': [0.0, 1.5]})
    fixed, report = denormalise_targets(df, {'jitter_ms': 500.0})
    self.assertEqual(list(fixed['jitter_ms']), [0.0, 750.0])
    self.assertIn('multiplied by', report['jitter_ms'])

  def test_multiple_columns_processed_independently(self):
    df = pd.DataFrame({
      'speedtest_down_mbps': [0.0, 1.0],
      'latency_ms': [0.0, 1.0],
      'speedtest_up_mbps': [10.0, 292.6],  # já físico
    })
    maxima = {'speedtest_down_mbps': 667.48, 'latency_ms': 4464.33, 'speedtest_up_mbps': 292.65}
    fixed, report = denormalise_targets(df, maxima)
    self.assertAlmostEqual(fixed['speedtest_down_mbps'].iloc[1], 667.48)
    self.assertAlmostEqual(fixed['latency_ms'].iloc[1], 4464.33)
    self.assertEqual(list(fixed['speedtest_up_mbps']), [10.0, 292.6])
    self.assertEqual(report['speedtest_up_mbps'], 'already physical')

  def test_target_missing_from_raw_is_reported_not_silenced(self):
    from ml.fix_target_scale import read_raw_maxima
    raw_handle = tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False)
    pd.DataFrame({'speedtest_down_mbps': [600.0, 500.0]}).to_csv(raw_handle.name, index=False)
    raw_handle.close()
    maxima = read_raw_maxima(raw_handle.name)
    self.assertNotIn('jitter_ms', maxima)  # ausente do bruto, como esperado

    df = pd.DataFrame({'jitter_ms': [0.0, 0.9]})  # ainda normalizado, precisa de correção
    fixed, report = denormalise_targets(df, maxima)
    self.assertNotIn('jitter_ms', report)  # denormalise_targets em si nao sabe do gap

    # a lacuna e fechada em main(), nao em denormalise_targets — este teste documenta
    # onde a responsabilidade fica, para que main() nao regrida silenciosamente


import importlib.util

from ml.core.explain import ShapConfig, mean_abs_shap_frame, resolve_shap_models, sample_rows

HAS_SHAP = importlib.util.find_spec('shap') is not None


class TestShapHelpers(unittest.TestCase):
  def test_ranking_orders_by_mean_absolute_value(self):
    # 'b' tem o maior |SHAP| médio (3.0) apesar de ser negativo na primeira linha.
    ranking = mean_abs_shap_frame(np.array([[1.0, -5.0], [3.0, 1.0]]), ['a', 'b'])
    self.assertEqual(list(ranking['feature']), ['b', 'a'])
    self.assertEqual(list(ranking['rank']), [1, 2])
    self.assertAlmostEqual(ranking['mean_abs_shap'].iloc[0], 3.0)

  def test_ranking_rejects_misaligned_feature_names(self):
    # Sem esta checagem os nomes sairiam deslocados das colunas, sem erro.
    with self.assertRaises(ValueError) as ctx:
      mean_abs_shap_frame(np.zeros((4, 3)), ['a', 'b'])
    self.assertIn('desalinhados', str(ctx.exception))

  def test_resolve_keeps_training_order_not_cli_order(self):
    available = ['rf', 'extra_trees', 'hist_gb', 'mlp', 'XGB']
    self.assertEqual(resolve_shap_models(['XGB', 'rf'], available), ('rf', 'XGB'))
    self.assertEqual(resolve_shap_models(None, available), tuple(available))

  def test_resolve_rejects_unknown_model(self):
    with self.assertRaises(ValueError) as ctx:
      resolve_shap_models(['lightgbm'], ['rf', 'XGB'])
    self.assertIn('lightgbm', str(ctx.exception))

  def test_sampling_is_identical_across_models(self):
    # Todos os modelos precisam ser explicados sobre as MESMAS linhas, senão os
    # beeswarms de modelos diferentes não são comparáveis ponto a ponto.
    X = pd.DataFrame({'f': range(100)})
    first = sample_rows(X, 10, seed=42)
    second = sample_rows(X, 10, seed=42)
    self.assertEqual(list(first.index), list(second.index))
    self.assertEqual(len(first), 10)
    self.assertEqual(len(sample_rows(X, 0, seed=42)), 100)  # 0 = todas as linhas

  @unittest.skipUnless(HAS_SHAP, 'shap não instalado neste interpretador')
  def test_tree_explanation_has_one_value_per_cell(self):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline

    from ml.core.explain import explain_fold

    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(60, 3)), columns=['a', 'b', 'c'])
    y = pd.Series(X['a'] * 2.0 + rng.normal(scale=0.1, size=60))
    fitted = Pipeline([
      ('imputer', SimpleImputer(strategy='median')),
      ('reg', RandomForestRegressor(n_estimators=10, random_state=0)),
    ]).fit(X, y)

    config = ShapConfig(models=('rf',), out_dir='/tmp', max_samples=20, seed=42)
    explanation = explain_fold(fitted, X, X, 'rf', config)
    self.assertEqual(explanation.values.shape, (20, 3))
    self.assertEqual(list(explanation.feature_names), ['a', 'b', 'c'])
    # 'a' é o único sinal real; tem de liderar o ranking.
    ranking = mean_abs_shap_frame(explanation.values, explanation.feature_names)
    self.assertEqual(ranking['feature'].iloc[0], 'a')


if __name__ == '__main__':
  unittest.main()
