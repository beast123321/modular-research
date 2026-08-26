import sqlite3
import tempfile
import unittest
from pathlib import Path

class Phase4MigrationTests(unittest.TestCase):

    def test_phase4_tables_exist(self):
        from evidence_store import EvidenceStore
        with tempfile.TemporaryDirectory() as td:
            store = EvidenceStore(Path(td) / 'run.sqlite')
            names = set(store.table_names())
            expected = {'video_metrics_derived', 'creator_metrics_derived', 'comment_labels', 'findings'}
            self.assertTrue(expected.issubset(names), expected - names)
            store.close()

    def test_findings_reject_non_observation_types(self):
        from evidence_store import EvidenceStore
        with tempfile.TemporaryDirectory() as td:
            store = EvidenceStore(Path(td) / 'run.sqlite')
            store.record_run('r1', {'topic': 'x'}, 'p1', 'tikhub')
            with self.assertRaises(sqlite3.IntegrityError):
                store.conn.execute('INSERT INTO findings(id,run_id,finding_type,category,statement,evidence_refs_json,metrics_json,support_count,created_at) VALUES(?,?,?,?,?,?,?,?,?)', ('f1', 'r1', 'HYPOTHESIS', 'X', 'bad', '[]', '{}', 1, '2026-08-26T00:00:00Z'))
            store.close()

class DeterministicMetricsTests(unittest.TestCase):

    def test_rates_compute_without_composite_score(self):
        from analysis.metrics import compute_rates
        got = compute_rates({'views': 1000, 'likes': 100, 'comments': 20, 'shares': 10, 'favorites': 30, 'author_followers': 200})
        self.assertAlmostEqual(got['engagement_rate'], 0.13)
        self.assertAlmostEqual(got['like_rate'], 0.1)
        self.assertAlmostEqual(got['comment_rate'], 0.02)
        self.assertAlmostEqual(got['share_rate'], 0.01)
        self.assertAlmostEqual(got['save_rate'], 0.03)
        self.assertAlmostEqual(got['follower_leverage'], 5.0)
        self.assertNotIn('viral_score', got)

    def test_rates_return_none_when_denominator_is_not_usable(self):
        from analysis.metrics import compute_rates
        got = compute_rates({'views': 0, 'likes': 1, 'author_followers': 0})
        self.assertIsNone(got['like_rate'])
        self.assertIsNone(got['engagement_rate'])
        self.assertIsNone(got['follower_leverage'])

    def test_velocity_requires_at_least_one_hour(self):
        from analysis.metrics import compute_velocity
        rows = [{'captured_at': '2026-08-26T00:00:00+00:00', 'views': 100, 'likes': 10, 'comments': 2}, {'captured_at': '2026-08-26T00:30:00+00:00', 'views': 160, 'likes': 16, 'comments': 5}]
        got = compute_velocity(rows)
        self.assertIsNone(got['view_velocity_per_hour'])
        self.assertIsNone(got['like_velocity_per_hour'])
        self.assertIsNone(got['comment_velocity_per_hour'])

    def test_velocity_uses_earliest_and_latest_snapshots(self):
        from analysis.metrics import compute_velocity
        rows = [{'captured_at': '2026-08-26T00:00:00+00:00', 'views': 100, 'likes': 10, 'comments': 2}, {'captured_at': '2026-08-26T02:00:00+00:00', 'views': 300, 'likes': 30, 'comments': 8}]
        got = compute_velocity(rows)
        self.assertAlmostEqual(got['view_velocity_per_hour'], 100.0)
        self.assertAlmostEqual(got['like_velocity_per_hour'], 10.0)
        self.assertAlmostEqual(got['comment_velocity_per_hour'], 3.0)

class RankingTests(unittest.TestCase):

    def test_percentile_rank_is_inclusive_and_tie_stable(self):
        from analysis.ranking import percentile_rank
        self.assertAlmostEqual(percentile_rank([10, 20, 20, 40], 20), 0.75)
        self.assertAlmostEqual(percentile_rank([10, 20, 20, 40], 40), 1.0)
        self.assertIsNone(percentile_rank([], 10))

    def test_creator_and_age_buckets_are_deterministic(self):
        from analysis.ranking import creator_size_bucket, video_age_bucket
        self.assertEqual(creator_size_bucket(9999), 'micro_0_10k')
        self.assertEqual(creator_size_bucket(10000), 'small_10k_50k')
        self.assertEqual(creator_size_bucket(1000000), 'mega_1m_plus')
        self.assertEqual(creator_size_bucket(None), 'unknown')
        self.assertEqual(video_age_bucket('2026-08-20T00:00:00+00:00', '2026-08-26T00:00:00+00:00'), 'age_0_7d')
        self.assertEqual(video_age_bucket('2026-07-01T00:00:00+00:00', '2026-08-26T00:00:00+00:00'), 'age_31_90d')

    def test_creator_baseline_requires_three_videos_and_uses_median(self):
        from analysis.ranking import build_creator_baselines
        rows = [{'video_id': 'a1', 'creator_id': 'a', 'views': 100, 'engagement_rate': 0.1, 'evidence_refs': ['r1']}, {'video_id': 'a2', 'creator_id': 'a', 'views': 200, 'engagement_rate': 0.2, 'evidence_refs': ['r2']}, {'video_id': 'a3', 'creator_id': 'a', 'views': 1000, 'engagement_rate': 0.3, 'evidence_refs': ['r3']}, {'video_id': 'b1', 'creator_id': 'b', 'views': 10, 'engagement_rate': 0.1, 'evidence_refs': ['r4']}, {'video_id': 'b2', 'creator_id': 'b', 'views': 20, 'engagement_rate': 0.2, 'evidence_refs': ['r5']}]
        got = build_creator_baselines(rows)
        self.assertEqual(got['a']['baseline_views'], 200.0)
        self.assertEqual(got['a']['sample_size'], 3)
        self.assertEqual(got['a']['median_engagement_rate'], 0.2)
        self.assertNotIn('b', got)

    def test_build_video_rankings_adds_global_cohort_and_overperformance(self):
        from analysis.ranking import build_video_rankings
        rows = [{'video_id': 'a1', 'creator_id': 'a', 'views': 100, 'engagement_rate': 0.1, 'share_rate': 0.01, 'follower_leverage': 1.0, 'author_followers': 10000, 'create_time': '2026-08-20T00:00:00+00:00', 'captured_at': '2026-08-26T00:00:00+00:00', 'keywords': ['desk'], 'evidence_refs': ['r1']}, {'video_id': 'a2', 'creator_id': 'a', 'views': 200, 'engagement_rate': 0.2, 'share_rate': 0.02, 'follower_leverage': 2.0, 'author_followers': 10000, 'create_time': '2026-08-19T00:00:00+00:00', 'captured_at': '2026-08-26T00:00:00+00:00', 'keywords': ['desk'], 'evidence_refs': ['r2']}, {'video_id': 'a3', 'creator_id': 'a', 'views': 1000, 'engagement_rate': 0.3, 'share_rate': 0.03, 'follower_leverage': 10.0, 'author_followers': 10000, 'create_time': '2026-08-18T00:00:00+00:00', 'captured_at': '2026-08-26T00:00:00+00:00', 'keywords': ['desk'], 'evidence_refs': ['r3']}, {'video_id': 'c1', 'creator_id': 'c', 'views': 50, 'engagement_rate': 0.05, 'share_rate': 0.005, 'follower_leverage': 0.1, 'author_followers': 500000, 'create_time': '2026-05-01T00:00:00+00:00', 'captured_at': '2026-08-26T00:00:00+00:00', 'keywords': ['other'], 'evidence_refs': ['r4']}]
        got = {row['video_id']: row for row in build_video_rankings(rows)}
        self.assertEqual(got['a3']['creator_overperformance'], 5.0)
        self.assertEqual(got['a3']['views_percentile'], 1.0)
        self.assertEqual(got['a3']['cohorts']['creator_size'], 'small_10k_50k')
        self.assertEqual(got['a3']['cohort_percentiles']['keyword:desk']['support_count'], 3)
        self.assertEqual(got['a3']['cohort_percentiles']['keyword:desk']['views_percentile'], 1.0)

class VOCTests(unittest.TestCase):

    def test_classify_comment_supports_multilabel_english(self):
        from analysis.voc import load_taxonomy, classify_comment
        taxonomy = load_taxonomy()
        got = classify_comment('Where can I buy this and how much is it?', taxonomy)
        self.assertIn('QUESTION', got['labels'])
        self.assertIn('PURCHASE_INTENT', got['labels'])
        self.assertIn('PRICE', got['labels'])
        self.assertTrue(got['matched_terms'])

    def test_classify_comment_supports_chinese_question_and_complaint(self):
        from analysis.voc import load_taxonomy, classify_comment
        taxonomy = load_taxonomy()
        got = classify_comment('这个多少钱？质量太差了，容易坏', taxonomy)
        self.assertIn('QUESTION', got['labels'])
        self.assertIn('PRICE', got['labels'])
        self.assertIn('COMPLAINT', got['labels'])
        self.assertIn('DURABILITY', got['labels'])

    def test_unmatched_comment_returns_empty_labels(self):
        from analysis.voc import load_taxonomy, classify_comment
        got = classify_comment('blue sky today', load_taxonomy())
        self.assertEqual(got['labels'], [])
        self.assertEqual(got['matched_terms'], {})

    def test_voc_summary_counts_and_weights_by_comment_likes(self):
        from analysis.voc import summarize_voc
        rows = [{'comment_id': 'c1', 'labels': ['PRICE'], 'matched_terms': {'PRICE': ['price']}, 'like_count': 99, 'evidence_refs': ['r1']}, {'comment_id': 'c2', 'labels': ['PRICE', 'QUESTION'], 'matched_terms': {'PRICE': ['how much'], 'QUESTION': ['?']}, 'like_count': 0, 'evidence_refs': ['r2']}, {'comment_id': 'c3', 'labels': ['QUESTION'], 'matched_terms': {'QUESTION': ['?']}, 'like_count': 0, 'evidence_refs': ['r3']}]
        got = summarize_voc(rows)
        self.assertEqual(got['sample_size'], 3)
        self.assertEqual(got['labels']['PRICE']['count'], 2)
        self.assertAlmostEqual(got['labels']['PRICE']['share'], 2 / 3)
        self.assertGreater(got['labels']['PRICE']['weighted_intensity'], got['labels']['QUESTION']['weighted_intensity'])
        self.assertEqual(set(got['labels']['PRICE']['evidence_refs']), {'r1', 'r2'})

class FindingTests(unittest.TestCase):

    def test_observations_are_evidence_backed_and_never_hypotheses(self):
        from analysis.findings import build_observations
        video_rows = [{'video_id': 'v1', 'engagement_rate': 0.1, 'engagement_percentile': 0.5, 'creator_overperformance': None, 'evidence_refs': ['r1']}, {'video_id': 'v2', 'engagement_rate': 0.3, 'engagement_percentile': 1.0, 'creator_overperformance': 4.0, 'creator_baseline_views': 100, 'creator_baseline_sample': 4, 'evidence_refs': ['r2', 'r3']}]
        voc_summary = {'sample_size': 10, 'labels': {'PRICE': {'count': 4, 'share': 0.4, 'weighted_intensity': 6.2, 'evidence_refs': ['r4', 'r5']}}}
        findings = build_observations(video_rows, voc_summary)
        categories = {f['category'] for f in findings}
        self.assertIn('RUN_TOP_ENGAGEMENT', categories)
        self.assertIn('CREATOR_OVERPERFORMANCE', categories)
        self.assertIn('VOC_PREVALENCE', categories)
        for finding in findings:
            self.assertEqual(finding['finding_type'], 'OBSERVATION')
            self.assertTrue(finding['evidence_refs'])
            self.assertTrue(finding['support_count'] >= 1)
            self.assertIn('metrics', finding)
            self.assertNotIn('insight', finding)
            self.assertNotIn('hypothesis', finding)

class IntelligenceRunnerIntegrationTests(unittest.TestCase):

    def test_executor_runs_deterministic_intelligence_and_persists_reports(self):
        from research_request import ResearchRequest
        from stage_planner import build_stage_plan
        from research_executor_v2 import ResearchExecutorV2
        request = ResearchRequest.from_dict({'topic': 'standing desk', 'platform': 'tiktok', 'market': 'US', 'language': 'en', 'research_goals': ['creator_analysis', 'voc'], 'time_range': {'days': 30}, 'content_scope': {}, 'depth': 'quick'})
        plan = build_stage_plan(request)
        videos = [('101', 100, 10, 1, 1), ('102', 200, 40, 2, 4), ('103', 1000, 300, 20, 50)]

        def fake_transport(**kwargs):
            path = kwargs['path']
            params = kwargs.get('params') or {}
            if path.endswith('fetch_video_search_result'):
                return {'code': 200, 'data': {'items': [{'aweme_id': vid, 'desc': f'Desk {vid}', 'create_time': 1787600000, 'statistics': {'play_count': views, 'digg_count': likes, 'comment_count': comments, 'share_count': shares}, 'author': {'uid': 'u1', 'sec_uid': 'sec1', 'unique_id': 'alice', 'follower_count': 100}} for vid, views, likes, comments, shares in videos]}}
            if path.endswith('fetch_user_post_videos_v3'):
                return {'code': 200, 'data': {'items': []}}
            if path.endswith('fetch_video_metrics'):
                item_id = str(params.get('item_id'))
                match = next((row for row in videos if row[0] == item_id))
                return {'code': 200, 'data': {'views': match[1], 'likes': match[2], 'comments': match[3], 'shares': match[4]}}
            if path.endswith('fetch_video_comments'):
                vid = str(params.get('aweme_id'))
                return {'code': 200, 'data': {'comments': [{'cid': f'c-{vid}', 'text': 'Where can I buy this? How much is it?', 'digg_count': 5, 'user': {'uid': 'commenter'}}], 'cursor': 0, 'has_more': False}}
            return {'code': 200, 'data': {}}
        with tempfile.TemporaryDirectory() as td:
            result = ResearchExecutorV2(transport=fake_transport).execute(plan, api_key='secret', base_url='https://example.invalid', output_root=Path(td), run_id='rphase4')
            run_dir = Path(result.output_dir)
            reports = run_dir / 'reports'
            for name in ('metrics.json', 'rankings.json', 'voc.json', 'findings.json', 'deterministic_summary.json'):
                self.assertTrue((reports / name).exists(), name)
            conn = sqlite3.connect(run_dir / 'run.sqlite')
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM video_metrics_derived WHERE run_id='rphase4'").fetchone()[0], 3)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM creator_metrics_derived WHERE run_id='rphase4'").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM comment_labels WHERE run_id='rphase4'").fetchone()[0], 3)
            self.assertGreater(conn.execute("SELECT COUNT(*) FROM findings WHERE run_id='rphase4'").fetchone()[0], 0)
            top = conn.execute("SELECT creator_overperformance FROM video_metrics_derived WHERE video_id='103'").fetchone()[0]
            self.assertAlmostEqual(top, 5.0)
            conn.close()
            statuses = {row['stage']: row['status'] for row in result.stages}
            self.assertEqual(statuses['CHEAP_RANKING'], 'completed_local')
            self.assertEqual(statuses['FINDINGS'], 'completed_local')
            self.assertEqual(statuses['PATTERN_MINING'], 'skipped_insufficient_evidence')
            self.assertEqual(statuses['HYPOTHESES'], 'skipped_insufficient_evidence')
            self.assertEqual(statuses['BRIEFS'], 'skipped_insufficient_evidence')
if __name__ == '__main__':
    unittest.main(verbosity=2)
