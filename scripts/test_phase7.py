import json
import tempfile
import unittest
from pathlib import Path
from live_validation import LiveValidationRunner, ProbeSpec, build_default_probes, summarize_shape

class Phase7ShapeTests(unittest.TestCase):

    def test_summarize_shape_does_not_copy_sensitive_values(self):
        payload = {'code': 200, 'request_id': 'rid-secret', 'token': 'do-not-copy', 'data': {'items': [{'id': '123', 'desc': 'private-ish content'}], 'cursor': 1}}
        summary = summarize_shape(payload)
        text = json.dumps(summary, ensure_ascii=False)
        self.assertNotIn('do-not-copy', text)
        self.assertNotIn('private-ish content', text)
        self.assertEqual(summary['type'], 'dict')
        self.assertIn('data', summary['keys'])
        self.assertEqual(summary['children']['data']['children']['items']['length'], 1)

    def test_default_probes_are_bounded(self):
        probes = build_default_probes(topic='standing desk', market='US')
        caps = [p.capability for p in probes]
        self.assertEqual(len(caps), len(set(caps)))
        self.assertIn('video_search', caps)
        self.assertIn('ads_search', caps)
        self.assertIn('top_contents_list', caps)
        self.assertLessEqual(len(probes), 16)

class Phase7RunnerTests(unittest.TestCase):

    def test_dns_block_returns_zero_calls(self):
        calls = []

        def transport(**kwargs):
            calls.append(kwargs)
            return {'code': 200, 'data': {}}
        runner = LiveValidationRunner(transport=transport)
        with tempfile.TemporaryDirectory() as td:
            result = runner.run([ProbeSpec('video_search', {'keyword': 'x', 'count': 1})], api_key='secret', base_url='https://nonexistent.invalid', output_dir=Path(td), max_calls=1, max_budget_usd=0.001, unit_price_usd=0.001, skip_dns_check=False)
        self.assertEqual(result['status'], 'BLOCKED_ENVIRONMENT')
        self.assertEqual(result['calls_attempted'], 0)
        self.assertEqual(calls, [])

    def test_budget_gate_stops_before_transport(self):
        calls = []

        def transport(**kwargs):
            calls.append(kwargs)
            return {'code': 200, 'data': {}}
        probes = [ProbeSpec('video_search', {'keyword': 'x', 'count': 1})]
        runner = LiveValidationRunner(transport=transport)
        with tempfile.TemporaryDirectory() as td:
            result = runner.run(probes, api_key='secret', base_url='https://example.invalid', output_dir=Path(td), max_calls=1, max_budget_usd=0.0, unit_price_usd=0.001, skip_dns_check=True)
        self.assertEqual(result['status'], 'BLOCKED_BUDGET')
        self.assertEqual(calls, [])

    def test_runner_saves_shape_and_redacted_raw(self):

        def transport(**kwargs):
            return {'code': 200, 'request_id': 'rid-1', 'token': 'LEAK', 'data': {'items': [{'aweme_id': '123', 'desc': 'hello'}]}}
        probes = [ProbeSpec('video_search', {'keyword': 'x', 'count': 1})]
        runner = LiveValidationRunner(transport=transport)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = runner.run(probes, api_key='secret', base_url='https://example.invalid', output_dir=root, max_calls=1, max_budget_usd=0.001, unit_price_usd=0.001, skip_dns_check=True)
            report = json.loads((root / 'live-validation.json').read_text())
            raw = next((root / 'raw').glob('*.json')).read_text()
        self.assertEqual(result['status'], 'COMPLETED')
        self.assertEqual(report['calls_attempted'], 1)
        self.assertNotIn('hello', json.dumps(report, ensure_ascii=False))
        self.assertNotIn('LEAK', raw)
        self.assertIn('<redacted>', raw)

    def test_runner_expands_one_video_and_one_ad_dependency_within_call_cap(self):
        calls = []

        def transport(**kwargs):
            calls.append(kwargs['path'])
            if kwargs['path'].endswith('fetch_video_search_result'):
                return {'code': 200, 'data': {'items': [{'aweme_id': 'v1', 'desc': 'x', 'author': {'sec_uid': 's1', 'unique_id': 'u1'}}]}}
            if kwargs['path'].endswith('search_ads'):
                return {'code': 200, 'data': {'materials': [{'material_id': 'a1'}]}}
            return {'code': 200, 'data': {}}
        probes = [ProbeSpec('video_search', {'keyword': 'x', 'count': 1}), ProbeSpec('ads_search', {'keyword': 'x', 'limit': 1})]
        runner = LiveValidationRunner(transport=transport)
        with tempfile.TemporaryDirectory() as td:
            result = runner.run(probes, api_key='secret', base_url='https://example.invalid', output_dir=Path(td), max_calls=7, max_budget_usd=0.007, unit_price_usd=0.001, skip_dns_check=True)
        caps = [x['capability'] for x in result['results']]
        self.assertIn('video_detail', caps)
        self.assertIn('video_metrics', caps)
        self.assertIn('ads_detail', caps)
        self.assertLessEqual(result['calls_attempted'], 7)

    def test_provider_code_non_200_is_classified_as_provider_error(self):

        def transport(**kwargs):
            return {'code': 400, 'message': 'bad request', 'data': None}
        runner = LiveValidationRunner(transport=transport)
        with tempfile.TemporaryDirectory() as td:
            result = runner.run([ProbeSpec('video_search', {'keyword': 'x', 'count': 1})], api_key='secret', base_url='https://example.invalid', output_dir=Path(td), max_calls=1, max_budget_usd=0.001, unit_price_usd=0.001, skip_dns_check=True)
        self.assertEqual(result['results'][0]['status'], 'error')
        self.assertEqual(result['results'][0]['error_class'], 'provider')

    def test_runner_marks_transport_failure_without_claiming_provider_failure(self):

        def transport(**kwargs):
            raise OSError('temporary DNS failure')
        probes = [ProbeSpec('video_search', {'keyword': 'x', 'count': 1})]
        runner = LiveValidationRunner(transport=transport)
        with tempfile.TemporaryDirectory() as td:
            result = runner.run(probes, api_key='secret', base_url='https://example.invalid', output_dir=Path(td), max_calls=1, max_budget_usd=0.001, unit_price_usd=0.001, skip_dns_check=True)
        self.assertEqual(result['status'], 'COMPLETED_WITH_ERRORS')
        self.assertEqual(result['results'][0]['error_class'], 'transport')

class Phase7DistributionTests(unittest.TestCase):

    def test_gitignore_root_scopes_runtime_media_so_scripts_media_is_publishable(self):
        lines = [line.strip() for line in (Path(__file__).resolve().parent.parent / '.gitignore').read_text().splitlines()]
        self.assertIn('/media/', lines)
        self.assertNotIn('media/', lines)
        self.assertIn('/raw/', lines)
        self.assertIn('/reports/', lines)
if __name__ == '__main__':
    unittest.main()
