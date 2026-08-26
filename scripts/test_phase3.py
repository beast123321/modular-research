"""Modular Research V2 Phase 3 tests: enrichment + normalizers + evidence store."""
from __future__ import annotations
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

def make_request(*, goals=None, depth='standard', seeds=None, scope=None):
    from research_request import ResearchRequest
    return ResearchRequest.from_dict({'topic': 'standing desk', 'platform': 'tiktok', 'market': 'US', 'language': 'en', 'research_goals': goals or ['creative_patterns', 'trend_discovery'], 'time_range': {'days': 90}, 'content_scope': scope or {}, 'seed_keywords': ['sit stand desk'] if seeds is None else seeds, 'depth': depth})

class EndpointRegistryPhase3Tests(unittest.TestCase):

    def setUp(self):
        from endpoint_registry import EndpointRegistry
        self.registry = EndpointRegistry()

    def test_top_contents_list_is_post_json(self):
        ep = self.registry.get('tikhub', 'tiktok', 'top_contents_list')
        self.assertEqual(ep['method'], 'POST')
        self.assertEqual(ep['request_location'], 'json')
        self.assertEqual(ep['path'], '/api/v1/tiktok/ads/get_top_contents_list')
        self.assertIn('order_by_metric', ep['defaults'])

    def test_top_contents_detail_is_post_json_and_requires_item_id(self):
        ep = self.registry.get('tikhub', 'tiktok', 'top_contents_item_detail')
        self.assertEqual(ep['method'], 'POST')
        self.assertEqual(ep['request_location'], 'json')
        self.assertIn('item_id', ep['required_params'])

    def test_search_insight_enrichment_endpoints_remain_get_query(self):
        for cap in ('creator_search_insights_trend', 'creator_search_insights_videos', 'creator_search_insights_detail'):
            ep = self.registry.get('tikhub', 'tiktok', cap)
            self.assertEqual(ep['method'], 'GET')
            self.assertEqual(ep['request_location'], 'query')

class StagePlannerPhase3Tests(unittest.TestCase):

    def test_trend_plan_enriches_search_insights(self):
        from stage_planner import build_stage_plan
        plan = build_stage_plan(make_request(goals=['trend_discovery']))
        demand = next((s for s in plan.stages if s.name == 'DEMAND'))
        caps = [t.capability for t in demand.tasks]
        self.assertEqual(caps[0], 'creator_search_insights')
        self.assertIn('creator_search_insights_trend', caps)
        self.assertIn('creator_search_insights_videos', caps)
        self.assertIn('creator_search_insights_detail', caps)
        dynamic = [t for t in demand.tasks if t.capability != 'creator_search_insights']
        self.assertTrue(all((t.mode == 'per_search_insight' for t in dynamic)))

    def test_quick_trend_skips_expensive_detail_enrichment(self):
        from stage_planner import build_stage_plan
        plan = build_stage_plan(make_request(goals=['trend_discovery'], depth='quick'))
        demand = next((s for s in plan.stages if s.name == 'DEMAND'))
        caps = {t.capability for t in demand.tasks}
        self.assertIn('creator_search_insights_trend', caps)
        self.assertIn('creator_search_insights_videos', caps)
        self.assertNotIn('creator_search_insights_detail', caps)

    def test_creative_plan_adds_top_contents_three_rankings_and_detail(self):
        from stage_planner import build_stage_plan
        plan = build_stage_plan(make_request(goals=['creative_patterns']))
        stage = next((s for s in plan.stages if s.name == 'ORGANIC_DISCOVERY'))
        top = next((t for t in stage.tasks if t.capability == 'top_contents_list'))
        self.assertEqual({c['order_by_metric'] for c in top.static_calls}, {1, 2, 3})
        detail = next((t for t in stage.tasks if t.capability == 'top_contents_item_detail'))
        self.assertEqual(detail.mode, 'per_top_content')
        self.assertGreater(detail.max_items, 0)

    def test_top_contents_not_for_pure_voc_when_scope_does_not_request_creative(self):
        from stage_planner import build_stage_plan
        plan = build_stage_plan(make_request(goals=['voc'], scope={'organic': True, 'comments': True}))
        caps = {t.capability for s in plan.stages for t in s.tasks}
        self.assertNotIn('top_contents_list', caps)

    def test_phase3_dynamic_enrichment_is_in_budget(self):
        from stage_planner import build_stage_plan
        base = build_stage_plan(make_request(goals=['voc'], scope={'organic': True, 'comments': True}))
        enriched = build_stage_plan(make_request(goals=['creative_patterns', 'trend_discovery']))
        self.assertGreater(enriched.total_max_requests, base.total_max_requests)
        self.assertGreater(enriched.max_cost_usd, base.max_cost_usd)

class ExtractorPhase3Tests(unittest.TestCase):

    def test_extract_creator_ids_accepts_tiktok_sec_uid_alias(self):
        from research_executor_v2 import extract_creator_ids
        payload = {'data': {'items': [{'author': {'sec_uid': 'SEC1', 'unique_id': 'alice'}}]}}
        self.assertEqual(extract_creator_ids(payload), [{'sec_user_id': 'SEC1', 'unique_id': 'alice'}])

    def test_search_insight_dynamic_params_do_not_leak_internal_keys(self):
        from research_executor_v2 import ResearchExecutorV2
        from stage_planner import PlanTask
        task = PlanTask(capability='creator_search_insights_trend', endpoint='/x', method='GET', request_location='query', mode='per_search_insight', variants=[{}], max_items=1)
        params = ResearchExecutorV2._dynamic_params(task, {'query_id': 'q1', 'keyword': 'desk'}, {})
        self.assertEqual(params, {'query_id_str': 'q1'})
        self.assertFalse(any((k.startswith('_') for k in params)))

    def test_extract_search_insights_dedupes_query_id(self):
        from research_executor_v2 import extract_search_insights
        payload = {'data': {'items': [{'query_id': 'q1', 'query': 'standing desk'}, {'query_id_str': 'q2', 'keyword': 'desk setup'}, {'query_id': 'q1', 'query': 'standing desk'}]}}
        self.assertEqual(extract_search_insights(payload), [{'query_id': 'q1', 'keyword': 'standing desk'}, {'query_id': 'q2', 'keyword': 'desk setup'}])

    def test_extract_top_content_ids_only_uses_content_item_ids(self):
        from research_executor_v2 import extract_top_content_ids
        payload = {'data': {'items': [{'item_id': 'v1', 'author': {'id': 'not-video'}}, {'item_id': 'v2'}], 'random': {'id': 'ignore'}}}
        self.assertEqual(extract_top_content_ids(payload), ['v1', 'v2'])

class TikTokNormalizerTests(unittest.TestCase):

    def test_video_normalizer_maps_common_app_shape(self):
        from normalizers.tiktok import normalize_capability
        payload = {'data': {'items': [{'aweme_id': '100', 'desc': 'Desk setup', 'create_time': 1700000000, 'video': {'duration': 15000, 'cover': {'url_list': ['https://cover']}, 'play_addr': {'url_list': ['https://video']}}, 'statistics': {'play_count': 1000, 'digg_count': 120, 'comment_count': 10, 'share_count': 5, 'collect_count': 7}, 'author': {'uid': 'u1', 'sec_uid': 'sec1', 'unique_id': 'alice', 'nickname': 'Alice', 'follower_count': 321}, 'text_extra': [{'hashtag_name': 'desksetup'}], 'music': {'id': 'm1', 'title': 'sound'}}]}}
        bundle = normalize_capability('video_search', payload, raw_evidence_id='raw1', request_payload={'keyword': 'standing desk', 'region': 'US'})
        self.assertEqual(bundle['videos'][0]['video_id'], '100')
        self.assertEqual(bundle['videos'][0]['duration_sec'], 15.0)
        self.assertEqual(bundle['video_snapshots'][0]['views'], 1000)
        self.assertEqual(bundle['creators'][0]['sec_user_id'], 'sec1')
        self.assertEqual(bundle['discoveries'][0]['query_text'], 'standing desk')

    def test_comment_normalizer_maps_text_and_counts(self):
        from normalizers.tiktok import normalize_capability
        payload = {'data': {'comments': [{'cid': 'c1', 'text': 'where can I buy?', 'create_time': 1700000001, 'digg_count': 12, 'reply_comment_total': 2, 'user': {'uid': 'u2'}}]}}
        bundle = normalize_capability('video_comments', payload, raw_evidence_id='raw2', request_payload={'aweme_id': '100'})
        self.assertEqual(bundle['comments'][0]['comment_id'], 'c1')
        self.assertEqual(bundle['comments'][0]['video_id'], '100')
        self.assertEqual(bundle['comments'][0]['like_count'], 12)

    def test_search_insight_normalizer_keeps_evidence_not_interpretation(self):
        from normalizers.tiktok import normalize_capability
        payload = {'data': {'items': [{'query_id': 'q1', 'query': 'standing desk', 'rank': 3, 'search_value': 999}]}}
        bundle = normalize_capability('creator_search_insights', payload, raw_evidence_id='raw3', request_payload={'tab': 'content_gap', 'language_filters': 'en'})
        rec = bundle['search_insights'][0]
        self.assertEqual(rec['query_id'], 'q1')
        self.assertEqual(rec['keyword'], 'standing desk')
        self.assertEqual(rec['insight_type'], 'content_gap')
        self.assertNotIn('hypothesis', rec)
        self.assertNotIn('insight_statement', rec)

    def test_ad_timeseries_normalizer_maps_keyframe_points(self):
        from normalizers.tiktok import normalize_capability
        payload = {'data': {'time_points': [0, 1, 2], 'retention_rates': [100, 92, 80], 'drop_points': [2], 'highlight_points': [1]}}
        bundle = normalize_capability('ad_keyframe_analysis', payload, raw_evidence_id='raw4', request_payload={'material_id': 'mat1', 'metric': 'retain_ctr'})
        rows = bundle['ad_timeseries']
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]['value'], 92)
        self.assertEqual(rows[1]['is_highlight'], 1)
        self.assertEqual(rows[2]['is_drop'], 1)

class EvidenceStoreTests(unittest.TestCase):

    def test_migration_creates_phase3_tables(self):
        from evidence_store import EvidenceStore
        with tempfile.TemporaryDirectory() as td:
            store = EvidenceStore(Path(td) / 'run.sqlite')
            names = set(store.table_names())
            expected = {'research_runs', 'raw_evidence', 'discoveries', 'videos', 'video_snapshots', 'creators', 'comments', 'ads', 'ad_timeseries', 'search_insights'}
            self.assertTrue(expected.issubset(names), expected - names)
            store.close()

    def test_ids_are_text_and_video_upsert_is_idempotent(self):
        from evidence_store import EvidenceStore
        with tempfile.TemporaryDirectory() as td:
            store = EvidenceStore(Path(td) / 'run.sqlite')
            store.record_run('r1', {'topic': 'x'}, 'p1', 'tikhub')
            store.persist_bundle({'videos': [{'video_id': '9223372036854775808123', 'caption': 'a', 'raw_evidence_id': 'raw1'}]}, run_id='r1')
            store.persist_bundle({'videos': [{'video_id': '9223372036854775808123', 'caption': 'b', 'raw_evidence_id': 'raw2'}]}, run_id='r1')
            row = store.conn.execute('SELECT video_id, caption, typeof(video_id) FROM videos').fetchone()
            self.assertEqual(row[0], '9223372036854775808123')
            self.assertEqual(row[1], 'b')
            self.assertEqual(row[2], 'text')
            self.assertEqual(store.conn.execute('SELECT COUNT(*) FROM videos').fetchone()[0], 1)
            store.close()

    def test_raw_evidence_links_normalized_record(self):
        from evidence_store import EvidenceStore
        with tempfile.TemporaryDirectory() as td:
            store = EvidenceStore(Path(td) / 'run.sqlite')
            store.record_run('r1', {'topic': 'x'}, 'p1', 'tikhub')
            store.record_raw_evidence(evidence_id='raw1', run_id='r1', endpoint='/x', method='GET', request_payload={'keyword': 'x'}, response_payload={'data': {}}, source_type='video_search', source_key='x')
            store.persist_bundle({'videos': [{'video_id': '100', 'caption': 'x', 'raw_evidence_id': 'raw1'}]}, run_id='r1')
            value = store.conn.execute("SELECT raw_evidence_id FROM videos WHERE video_id='100'").fetchone()[0]
            self.assertEqual(value, 'raw1')
            store.close()

class ExecutorEvidenceIntegrationTests(unittest.TestCase):

    def test_executor_writes_sqlite_raw_and_normalized_evidence(self):
        from stage_planner import build_stage_plan
        from research_executor_v2 import ResearchExecutorV2
        plan = build_stage_plan(make_request(goals=['voc'], depth='quick', seeds=[]))

        def fake_transport(**kwargs):
            path = kwargs['path']
            params = kwargs.get('params') or {}
            if path.endswith('fetch_video_search_result'):
                return {'code': 200, 'data': {'items': [{'aweme_id': '100', 'desc': 'Desk', 'statistics': {'play_count': 10}, 'author': {'uid': 'u1', 'sec_uid': 'sec1', 'unique_id': 'alice'}}]}}
            if path.endswith('fetch_video_comments'):
                return {'code': 200, 'data': {'comments': [{'cid': 'c1', 'text': 'price?', 'user': {'uid': 'u2'}}], 'cursor': 0, 'has_more': False}}
            return {'code': 200, 'data': {}}
        with tempfile.TemporaryDirectory() as td:
            result = ResearchExecutorV2(transport=fake_transport).execute(plan, api_key='secret', base_url='https://example.invalid', output_root=Path(td), run_id='rphase3')
            db_path = Path(result.output_dir) / 'run.sqlite'
            self.assertTrue(db_path.exists())
            conn = sqlite3.connect(db_path)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM raw_evidence').fetchone()[0], result.calls_succeeded)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM videos WHERE video_id='100'").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM comments WHERE comment_id='c1'").fetchone()[0], 1)
            raw_id = conn.execute("SELECT raw_evidence_id FROM comments WHERE comment_id='c1'").fetchone()[0]
            self.assertTrue(raw_id.startswith('rphase3:raw:'))
            conn.close()

    def test_raw_files_include_evidence_id_and_redact_secrets(self):
        from stage_planner import build_stage_plan
        from research_executor_v2 import ResearchExecutorV2
        plan = build_stage_plan(make_request(goals=['voc'], depth='quick', seeds=[]))

        def fake_transport(**kwargs):
            if kwargs['path'].endswith('fetch_video_search_result'):
                return {'code': 200, 'token': 'LEAK', 'data': {'items': [{'aweme_id': '100'}]}}
            return {'code': 200, 'token': 'LEAK', 'data': {'comments': [], 'has_more': False}}
        with tempfile.TemporaryDirectory() as td:
            result = ResearchExecutorV2(transport=fake_transport).execute(plan, api_key='secret', base_url='https://example.invalid', output_root=Path(td), run_id='rphase3b')
            files = sorted((Path(result.output_dir) / 'raw').glob('*.json'))
            self.assertTrue(files)
            first = json.loads(files[0].read_text(encoding='utf-8'))
            self.assertIn('raw_evidence_id', first)
            self.assertNotIn('LEAK', files[0].read_text(encoding='utf-8'))
if __name__ == '__main__':
    unittest.main(verbosity=2)
