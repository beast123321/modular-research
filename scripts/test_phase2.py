"""Modular Research V2 Phase 2 tests: stage planning + executable TikHub chain."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
import unittest
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

def make_request(*, goals=None, depth='standard', scope=None, days=90, seeds=None):
    from research_request import ResearchRequest
    return ResearchRequest.from_dict({'topic': 'standing desk', 'platform': 'tiktok', 'market': 'US', 'language': 'en', 'research_goals': goals or ['creative_patterns', 'voc'], 'time_range': {'days': days}, 'content_scope': scope or {}, 'seed_keywords': ['sit stand desk'] if seeds is None else seeds, 'depth': depth})

class EndpointRegistryPhase2Tests(unittest.TestCase):

    def setUp(self):
        from endpoint_registry import EndpointRegistry
        self.registry = EndpointRegistry()

    def test_tiktok_video_search_is_query_get(self):
        entry = self.registry.get('tikhub', 'tiktok', 'video_search')
        self.assertEqual(entry['method'], 'GET')
        self.assertEqual(entry['request_location'], 'query')
        self.assertEqual(entry['limits']['count_max'], 20)

    def test_ads_search_is_post_json(self):
        entry = self.registry.get('tikhub', 'tiktok', 'ads_search')
        self.assertEqual(entry['method'], 'POST')
        self.assertEqual(entry['request_location'], 'json')
        self.assertEqual(entry['limits']['limit_max'], 50)

    def test_ad_keyframe_is_current_post_json(self):
        entry = self.registry.get('tikhub', 'tiktok', 'ad_keyframe_analysis')
        self.assertEqual(entry['method'], 'POST')
        self.assertEqual(entry['request_location'], 'json')
        self.assertIn('material_id', entry['required_params'])

    def test_provider_default_pricing_fallback_is_marked(self):
        pricing = self.registry.get_pricing('tikhub', 'tiktok', 'video_search')
        self.assertEqual(pricing['unit_price_usd'], '0.001')
        self.assertEqual(pricing['price_source'], 'provider_default')
        self.assertFalse(pricing['is_endpoint_exact'])

    def test_explicit_douyin_price_is_marked_exact(self):
        pricing = self.registry.get_pricing('tikhub', 'douyin', 'video_detail')
        self.assertEqual(pricing['unit_price_usd'], '0.001')
        self.assertEqual(pricing['price_source'], 'endpoint_explicit')
        self.assertTrue(pricing['is_endpoint_exact'])

    def test_all_phase2_tiktok_capabilities_exist(self):
        required = {'creator_search_insights', 'video_search', 'creator_posts', 'video_metrics', 'video_comments', 'ads_search', 'top_ads_spotlight', 'ads_detail', 'ad_keyframe_analysis', 'ad_percentile', 'ad_interactive_analysis'}
        available = set(self.registry.list_capabilities('tikhub', 'tiktok'))
        self.assertTrue(required.issubset(available), required - available)

class StagePlannerTests(unittest.TestCase):

    def test_standard_creative_voc_plan_has_expected_stage_order(self):
        from stage_planner import build_stage_plan
        plan = build_stage_plan(make_request())
        names = [s.name for s in plan.stages]
        self.assertEqual(names[0], 'ORGANIC_DISCOVERY')
        self.assertIn('CHEAP_RANKING', names)
        self.assertIn('CREATOR_CONTEXT', names)
        self.assertIn('VOC', names)
        self.assertLess(names.index('ORGANIC_DISCOVERY'), names.index('CREATOR_CONTEXT'))
        self.assertLess(names.index('CREATOR_CONTEXT'), names.index('VOC'))

    def test_trend_goal_enables_demand(self):
        from stage_planner import build_stage_plan
        plan = build_stage_plan(make_request(goals=['trend_discovery']))
        self.assertEqual(plan.stages[0].name, 'DEMAND')
        caps = {t.capability for s in plan.stages for t in s.tasks}
        self.assertIn('creator_search_insights', caps)

    def test_hooks_goal_does_not_force_ads(self):
        from stage_planner import build_stage_plan
        plan = build_stage_plan(make_request(goals=['hooks'], scope={'ads': False}))
        self.assertNotIn('ADS_DISCOVERY', [s.name for s in plan.stages])

    def test_ads_goal_enables_discovery_and_deep_analysis(self):
        from stage_planner import build_stage_plan
        plan = build_stage_plan(make_request(goals=['ads_analysis']))
        names = [s.name for s in plan.stages]
        self.assertIn('ADS_DISCOVERY', names)
        self.assertIn('CREATIVE_ANALYSIS', names)
        caps = {t.capability for s in plan.stages for t in s.tasks}
        self.assertIn('ads_search', caps)
        self.assertIn('ads_detail', caps)
        self.assertIn('ad_keyframe_analysis', caps)

    def test_retention_goal_plans_ctr_and_cvr_keyframes(self):
        from stage_planner import build_stage_plan
        plan = build_stage_plan(make_request(goals=['retention_analysis']))
        task = next((t for s in plan.stages for t in s.tasks if t.capability == 'ad_keyframe_analysis'))
        metrics = [v['metric'] for v in task.variants]
        self.assertEqual(metrics, ['retain_ctr', 'retain_cvr'])

    def test_voc_goal_enables_comments(self):
        from stage_planner import build_stage_plan
        plan = build_stage_plan(make_request(goals=['voc']))
        caps = {t.capability for s in plan.stages for t in s.tasks}
        self.assertIn('video_comments', caps)

    def test_standard_keyword_universe_dedupes_topic_and_seeds(self):
        from stage_planner import build_stage_plan
        plan = build_stage_plan(make_request(seeds=['standing desk', 'sit stand desk', 'desk setup']))
        self.assertEqual(plan.keywords, ['standing desk', 'sit stand desk', 'desk setup'])

    def test_quick_keyword_limit_is_three(self):
        from stage_planner import build_stage_plan
        seeds = [f'kw{i}' for i in range(10)]
        plan = build_stage_plan(make_request(depth='quick', seeds=seeds))
        self.assertEqual(len(plan.keywords), 3)

    def test_standard_keyword_limit_is_eight(self):
        from stage_planner import build_stage_plan
        seeds = [f'kw{i}' for i in range(20)]
        plan = build_stage_plan(make_request(depth='standard', seeds=seeds))
        self.assertEqual(len(plan.keywords), 8)

    def test_deep_keyword_limit_is_twenty(self):
        from stage_planner import build_stage_plan
        seeds = [f'kw{i}' for i in range(30)]
        plan = build_stage_plan(make_request(depth='deep', seeds=seeds))
        self.assertEqual(len(plan.keywords), 20)

    def test_standard_90d_organic_has_four_variants_per_keyword(self):
        from stage_planner import build_stage_plan
        plan = build_stage_plan(make_request(seeds=[]))
        task = next((t for s in plan.stages for t in s.tasks if t.capability == 'video_search'))
        self.assertEqual(len(task.static_calls), 4)
        combos = {(c['sort_type'], c['publish_time']) for c in task.static_calls}
        self.assertEqual(combos, {(0, 90), (1, 90), (0, 180), (1, 180)})

    def test_quick_90d_organic_has_two_variants(self):
        from stage_planner import build_stage_plan
        plan = build_stage_plan(make_request(depth='quick', seeds=[]))
        task = next((t for s in plan.stages for t in s.tasks if t.capability == 'video_search'))
        self.assertEqual(len(task.static_calls), 2)

    def test_time_range_maps_to_supported_publish_time(self):
        from stage_planner import map_tiktok_publish_time
        self.assertEqual(map_tiktok_publish_time(2), 7)
        self.assertEqual(map_tiktok_publish_time(20), 30)
        self.assertEqual(map_tiktok_publish_time(60), 90)
        self.assertEqual(map_tiktok_publish_time(365), 180)

    def test_ads_period_maps_90_to_120(self):
        from stage_planner import map_ads_period
        self.assertEqual(map_ads_period(90), 120)

    def test_local_stages_have_zero_api_cost(self):
        from stage_planner import build_stage_plan
        plan = build_stage_plan(make_request())
        locals_ = [s for s in plan.stages if s.local_only]
        self.assertTrue(locals_)
        self.assertTrue(all((s.expected_requests == 0 for s in locals_)))

    def test_plan_has_budget_and_pricing_confidence(self):
        from stage_planner import build_stage_plan
        plan = build_stage_plan(make_request())
        self.assertGreater(plan.total_expected_requests, 0)
        self.assertGreater(plan.expected_cost_usd, 0)
        self.assertGreaterEqual(plan.max_cost_usd, plan.expected_cost_usd)
        self.assertIn(plan.pricing_confidence, {'estimated', 'mixed', 'exact'})

    def test_provider_default_price_is_disclosed_in_assumptions(self):
        from stage_planner import build_stage_plan
        plan = build_stage_plan(make_request())
        text = ' '.join(plan.assumptions)
        self.assertIn('provider default', text.lower())

    def test_plan_to_dict_contains_request_order_and_budget(self):
        from stage_planner import build_stage_plan
        payload = build_stage_plan(make_request()).to_dict()
        self.assertIn('request', payload)
        self.assertIn('stages', payload)
        self.assertIn('budget', payload)
        self.assertIn('keywords', payload)

class ExecutorExtractionTests(unittest.TestCase):

    def test_extract_video_ids_dedupes_nested_aweme_and_item(self):
        from research_executor_v2 import extract_video_ids
        payload = {'data': {'items': [{'aweme_id': '100'}, {'item_id': '101'}, {'aweme_id': '100'}]}}
        self.assertEqual(extract_video_ids(payload), ['100', '101'])

    def test_extract_creator_ids_prefers_sec_user_id(self):
        from research_executor_v2 import extract_creator_ids
        payload = {'data': {'items': [{'author': {'sec_user_id': 'SEC1', 'unique_id': 'alice'}}, {'author': {'unique_id': 'bob'}}]}}
        ids = extract_creator_ids(payload)
        self.assertEqual(ids[0], {'sec_user_id': 'SEC1', 'unique_id': 'alice'})
        self.assertEqual(ids[1], {'sec_user_id': None, 'unique_id': 'bob'})

    def test_extract_ad_ids_only_uses_materials(self):
        from research_executor_v2 import extract_ad_ids
        payload = {'data': {'materials': [{'id': 'A1'}, {'material_id': 'A2'}], 'other': {'id': 'NO'}}}
        self.assertEqual(extract_ad_ids(payload), ['A1', 'A2'])

class ExecutorChainTests(unittest.TestCase):

    def test_fake_transport_executes_static_then_dynamic_fanout(self):
        from stage_planner import build_stage_plan
        from research_executor_v2 import ResearchExecutorV2
        req = make_request(goals=['creative_patterns', 'voc', 'ads_analysis'], depth='quick', seeds=[])
        plan = build_stage_plan(req)
        calls = []

        def fake_transport(**kw):
            calls.append(kw)
            path = kw['path']
            body = kw.get('body') or {}
            params = kw.get('params') or {}
            if path.endswith('fetch_video_search_result'):
                return {'code': 200, 'data': {'items': [{'aweme_id': 'V1', 'author': {'sec_user_id': 'SEC1', 'unique_id': 'alice'}}, {'aweme_id': 'V2', 'author': {'unique_id': 'bob'}}]}}
            if path.endswith('search_ads'):
                return {'code': 200, 'data': {'materials': [{'id': 'A1', 'aweme_id': 'AV1'}]}}
            if path.endswith('fetch_video_comments'):
                return {'code': 200, 'data': {'comments': [{'cid': 'C1', 'text': 'price?'}], 'has_more': False}}
            return {'code': 200, 'data': {'ok': True, 'echo': body or params}}
        with tempfile.TemporaryDirectory() as td:
            result = ResearchExecutorV2(transport=fake_transport).execute(plan, api_key='secret', base_url='https://example.test', output_root=Path(td), run_id='run_test')
            self.assertEqual(result.status, 'completed')
            paths = [c['path'] for c in calls]
            search_idx = next((i for i, p in enumerate(paths) if p.endswith('fetch_video_search_result')))
            creator_idx = next((i for i, p in enumerate(paths) if p.endswith('fetch_user_post_videos_v3')))
            comments_idx = next((i for i, p in enumerate(paths) if p.endswith('fetch_video_comments')))
            self.assertLess(search_idx, creator_idx)
            self.assertLess(search_idx, comments_idx)
            self.assertTrue(any((p.endswith('get_ads_detail') for p in paths)))
            self.assertTrue(any((p.endswith('get_ad_keyframe_analysis') for p in paths)))

    def test_post_calls_use_body_and_get_calls_use_params(self):
        from stage_planner import build_stage_plan
        from research_executor_v2 import ResearchExecutorV2
        plan = build_stage_plan(make_request(goals=['ads_analysis'], depth='quick', seeds=[]))
        seen = []

        def fake_transport(**kw):
            seen.append(kw)
            if kw['path'].endswith('fetch_video_search_result'):
                return {'code': 200, 'data': {'items': []}}
            if kw['path'].endswith('search_ads'):
                return {'code': 200, 'data': {'materials': [{'id': 'A1'}]}}
            return {'code': 200, 'data': {}}
        with tempfile.TemporaryDirectory() as td:
            ResearchExecutorV2(transport=fake_transport).execute(plan, api_key='secret', base_url='https://example.test', output_root=Path(td), run_id='run_test')
        ads = next((c for c in seen if c['path'].endswith('search_ads')))
        organic = next((c for c in seen if c['path'].endswith('fetch_video_search_result')))
        self.assertIsInstance(ads.get('body'), dict)
        self.assertFalse(ads.get('params'))
        self.assertIsInstance(organic.get('params'), dict)
        self.assertFalse(organic.get('body'))

    def test_execution_writes_redacted_raw_payloads(self):
        from stage_planner import build_stage_plan
        from research_executor_v2 import ResearchExecutorV2
        plan = build_stage_plan(make_request(goals=['hooks'], depth='quick', seeds=[]))

        def fake_transport(**kw):
            return {'code': 200, 'token': 'LEAK', 'data': {'items': []}}
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ResearchExecutorV2(transport=fake_transport).execute(plan, api_key='secret', base_url='https://example.test', output_root=root, run_id='run_test')
            raw_files = list((root / 'runs' / 'run_test' / 'raw').glob('*.json'))
            self.assertTrue(raw_files)
            joined = '\n'.join((p.read_text(encoding='utf-8') for p in raw_files))
            self.assertNotIn('LEAK', joined)
            self.assertIn('<redacted>', joined)

    def test_no_dynamic_inputs_marks_stage_skipped_not_failed(self):
        from stage_planner import build_stage_plan
        from research_executor_v2 import ResearchExecutorV2
        plan = build_stage_plan(make_request(goals=['voc'], depth='quick', seeds=[]))

        def fake_transport(**kw):
            return {'code': 200, 'data': {'items': []}}
        with tempfile.TemporaryDirectory() as td:
            result = ResearchExecutorV2(transport=fake_transport).execute(plan, api_key='secret', base_url='https://example.test', output_root=Path(td), run_id='run_test')
        voc = next((s for s in result.stages if s['stage'] == 'VOC'))
        self.assertEqual(voc['status'], 'skipped_no_inputs')
        self.assertEqual(result.status, 'completed')

class CliIntegrationTests(unittest.TestCase):

    def test_budget_gate_rejects_execution_without_max_budget(self):
        import run_research
        req = make_request(goals=['hooks'], depth='quick', seeds=[])
        plan = run_research.build_v2_stage_plan(req)
        ok, reason = run_research.validate_v2_execution_gate(plan, yes=True, max_budget_usd=None)
        self.assertFalse(ok)
        self.assertIn('max-budget', reason)

    def test_budget_gate_rejects_insufficient_budget(self):
        import run_research
        req = make_request(goals=['ads_analysis'], depth='quick', seeds=[])
        plan = run_research.build_v2_stage_plan(req)
        ok, reason = run_research.validate_v2_execution_gate(plan, yes=True, max_budget_usd=0.0001)
        self.assertFalse(ok)
        self.assertIn('预算', reason)

    def test_budget_gate_accepts_explicit_sufficient_budget(self):
        import run_research
        req = make_request(goals=['hooks'], depth='quick', seeds=[])
        plan = run_research.build_v2_stage_plan(req)
        ok, reason = run_research.validate_v2_execution_gate(
            plan,
            yes=True,
            max_budget_usd=plan.max_cost_usd + 0.01,
            allow_documented_capabilities=True,
        )
        self.assertTrue(ok, reason)
if __name__ == '__main__':
    unittest.main()
