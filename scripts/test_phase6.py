"""Modular Research V2 Phase 6 tests: pattern mining + synthesis contracts."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

def seed_pattern_run(db: Path, run_id: str='r1', count: int=12) -> None:
    from evidence_store import EvidenceStore
    store = EvidenceStore(db)
    store.record_run(run_id, {'topic': 'desk'}, 'tiktok-video-intelligence-v1', 'tikhub')
    for i in range(1, count + 1):
        vid = f'v{i}'
        creator = f'c{i}'
        store.conn.execute('INSERT INTO videos(video_id,creator_id,caption,first_seen_at,last_seen_at,raw_evidence_id) VALUES(?,?,?,?,?,?)', (vid, creator, f'video {i}', '2026', '2026', f'raw-video-{i}'))
        percentile = 0.8 + i * 0.01 if i <= 4 else 0.1 + i * 0.02
        store.conn.execute('INSERT INTO video_metrics_derived(\n               run_id,video_id,engagement_percentile,views_percentile,share_rate_percentile,\n               follower_leverage_percentile,cohort_json,evidence_refs_json,computed_at)\n               VALUES(?,?,?,?,?,?,?,?,?)', (run_id, vid, percentile, percentile, percentile, percentile, '{}', json.dumps([f'raw-metric-{i}']), '2026'))
        hook = 'QUESTION' if i <= 6 else 'PRODUCT_FIRST'
        store.upsert_creative_analysis(run_id, {'video_id': vid, 'schema_version': '1.0', 'analyzer': {'name': 'host-agent', 'version': '1', 'mode': 'multimodal'}, 'hook_type': hook, 'hook_text': None, 'product_visible_at': 0.2 if i <= 4 else 2.0, 'format': 'PRODUCT_DEMO' if i <= 8 else 'UGC_TALKING_HEAD', 'selling_angle': 'FUNCTIONALITY', 'proof_type': 'DEMO', 'cta_text': None, 'cta_at': None, 'shot_count': 4, 'avg_shot_length': 1.5, 'visual_style': 'clean', 'timeline': [], 'confidence': {'hook_type': 0.9}, 'evidence_refs': [f'frame:{vid}:0']})
    store.conn.execute('INSERT INTO ads(material_id,video_id,ad_title,raw_evidence_id) VALUES(?,?,?,?)', ('ad1', 'v1', 'demo ad', 'raw-ad-1'))
    store.conn.commit()
    store.close()

class Phase6SchemaTests(unittest.TestCase):

    def test_phase6_tables_exist(self):
        from evidence_store import EvidenceStore
        with tempfile.TemporaryDirectory() as td:
            store = EvidenceStore(Path(td) / 'run.sqlite')
            names = set(store.table_names())
            expected = {'creative_patterns', 'insights', 'creative_hypotheses', 'media_briefs'}
            self.assertTrue(expected.issubset(names), expected - names)
            store.close()

class PatternMiningTests(unittest.TestCase):

    def test_pattern_lift_tracks_creator_diversity_and_source_support(self):
        from analysis.patterns import mine_patterns
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'run.sqlite'
            seed_pattern_run(db)
            patterns = mine_patterns(db, 'r1')
            row = next((p for p in patterns if p['performance_metric'] == 'engagement_percentile' and p['pattern_field'] == 'hook_type' and (p['pattern_value'] == 'QUESTION')))
            self.assertEqual(row['top_support'], 4)
            self.assertEqual(row['baseline_support'], 6)
            self.assertAlmostEqual(row['top_share'], 1.0)
            self.assertAlmostEqual(row['baseline_share'], 0.5)
            self.assertAlmostEqual(row['lift'], 2.0)
            self.assertEqual(row['creator_support'], 4)
            self.assertGreaterEqual(row['organic_support'], 4)
            self.assertEqual(row['ad_support'], 1)
            self.assertTrue(row['evidence_refs'])

    def test_pattern_mining_returns_empty_when_baseline_too_small(self):
        from analysis.patterns import mine_patterns
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'run.sqlite'
            seed_pattern_run(db, count=5)
            self.assertEqual(mine_patterns(db, 'r1'), [])

    def test_pattern_persistence_replaces_only_same_run(self):
        from analysis.patterns import mine_patterns
        from evidence_store import EvidenceStore
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'run.sqlite'
            seed_pattern_run(db)
            patterns = mine_patterns(db, 'r1')
            store = EvidenceStore(db)
            store.replace_patterns('r1', patterns)
            first = store.conn.execute("SELECT COUNT(*) FROM creative_patterns WHERE run_id='r1'").fetchone()[0]
            store.record_run('r2', {'topic': 'x'}, 'p', 'tikhub')
            store.conn.execute('INSERT INTO creative_patterns(id,run_id,performance_metric,pattern_field,pattern_value,top_cohort_size,baseline_size,top_support,baseline_support,top_share,baseline_share,lift,creator_support,organic_support,ad_support,evidence_refs_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', ('keep', 'r2', 'engagement_percentile', 'hook_type', 'QUESTION', 4, 10, 3, 4, 0.75, 0.4, 1.875, 3, 3, 0, '[]', '2026'))
            store.conn.commit()
            store.replace_patterns('r1', patterns[:1])
            second = store.conn.execute("SELECT COUNT(*) FROM creative_patterns WHERE run_id='r1'").fetchone()[0]
            other = store.conn.execute("SELECT COUNT(*) FROM creative_patterns WHERE run_id='r2'").fetchone()[0]
            store.close()
            self.assertGreater(first, 1)
            self.assertEqual(second, 1)
            self.assertEqual(other, 1)

class SynthesisContractTests(unittest.TestCase):

    def _response(self):
        return {'schema_version': '1.0', 'analyzer': {'name': 'host-agent', 'version': '1', 'mode': 'reasoning'}, 'insights': [{'id': 'ins-1', 'statement': 'QUESTION hooks are over-represented in the high-engagement cohort and may be worth testing.', 'evidence_refs': ['pattern:p1'], 'confidence': 0.8}], 'hypotheses': [{'id': 'hyp-1', 'statement': 'Opening with a question may improve early engagement for this topic.', 'objective': 'test early engagement', 'hook_type': 'QUESTION', 'format': 'PRODUCT_DEMO', 'selling_angle': 'FUNCTIONALITY', 'proof_type': 'DEMO', 'evidence_refs': ['pattern:p1', 'insight:ins-1'], 'confidence': 0.7}], 'media_briefs': [{'id': 'brief-1', 'hypothesis_id': 'hyp-1', 'objective': 'test early engagement', 'target_audience': None, 'duration_target_sec': 12, 'timeline': [{'start_sec': 0, 'end_sec': 2, 'event': 'QUESTION_HOOK', 'instruction': 'Ask the core question.'}, {'start_sec': 2, 'end_sec': 8, 'event': 'DEMO', 'instruction': 'Show product proof.'}], 'cta': 'Learn more', 'evidence_refs': ['hypothesis:hyp-1', 'pattern:p1'], 'confidence': 0.7}]}

    def test_valid_synthesis_response_passes(self):
        from synthesis.contracts import validate_synthesis_response
        got = validate_synthesis_response(self._response())
        self.assertEqual(got['hypotheses'][0]['hook_type'], 'QUESTION')
        self.assertEqual(got['media_briefs'][0]['hypothesis_id'], 'hyp-1')

    def test_synthesis_requires_evidence_and_bounded_confidence(self):
        from synthesis.contracts import validate_synthesis_response
        payload = self._response()
        payload['insights'][0]['evidence_refs'] = []
        with self.assertRaises(ValueError):
            validate_synthesis_response(payload)
        payload = self._response()
        payload['hypotheses'][0]['confidence'] = 1.5
        with self.assertRaises(ValueError):
            validate_synthesis_response(payload)

    def test_synthesis_request_contains_causality_guardrail(self):
        from synthesis.agent_bridge import build_synthesis_request
        req = build_synthesis_request(run_id='r1', patterns=[{'id': 'p1', 'lift': 2.0, 'evidence_refs': ['raw1']}], observations=[], voc_summary={'sample_size': 0}, topic='desk')
        text = json.dumps(req, ensure_ascii=False).lower()
        self.assertIn('correlation', text)
        self.assertIn('causal', text)
        self.assertIn('business truth', text)
        self.assertIn('required_output_schema', req)

class Phase6RunnerTests(unittest.TestCase):

    def test_runner_writes_pattern_report_and_synthesis_request(self):
        from synthesis.runner import prepare_synthesis
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / 'r1'
            run_dir.mkdir()
            db = run_dir / 'run.sqlite'
            seed_pattern_run(db)
            result = prepare_synthesis(db, run_dir, 'r1')
            self.assertGreater(result['pattern_count'], 0)
            self.assertTrue((run_dir / 'reports' / 'pattern_report.json').exists())
            self.assertTrue((run_dir / 'reports' / 'synthesis_request.json').exists())
            self.assertEqual(result['insights_generated'], 0)
            self.assertEqual(result['hypotheses_generated'], 0)

    def test_executor_runs_pattern_stage_and_skips_semantics_when_evidence_is_insufficient(self):
        from research_executor_v2 import ResearchExecutorV2
        from research_request import ResearchRequest
        from stage_planner import StageResearchPlan, PlanStage
        with tempfile.TemporaryDirectory() as td:
            request = ResearchRequest.from_dict({'topic': 'desk', 'platform': 'tiktok', 'market': 'US', 'research_goals': ['creative_patterns'], 'depth': 'quick'})
            plan = StageResearchPlan(request=request, profile_id='tiktok-video-intelligence-v1', provider='tikhub', keywords=['desk'], stages=[PlanStage('CHEAP_RANKING', local_only=True), PlanStage('FINDINGS', local_only=True), PlanStage('PATTERN_MINING', local_only=True), PlanStage('HYPOTHESES', local_only=True), PlanStage('BRIEFS', local_only=True)], assumptions=[], pricing_confidence='estimated')
            result = ResearchExecutorV2().execute(plan, api_key='unused', base_url='https://example.invalid', output_root=Path(td), run_id='r-empty')
            statuses = {row['stage']: row['status'] for row in result.stages}
            self.assertEqual(statuses['PATTERN_MINING'], 'skipped_insufficient_evidence')
            self.assertEqual(statuses['HYPOTHESES'], 'skipped_insufficient_evidence')
            self.assertEqual(statuses['BRIEFS'], 'skipped_insufficient_evidence')
            self.assertTrue((Path(td) / 'runs' / 'r-empty' / 'reports' / 'pattern_report.json').exists())

    def test_cli_import_persists_semantic_outputs(self):
        from evidence_store import EvidenceStore
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / 'r1'
            run_dir.mkdir()
            db = run_dir / 'run.sqlite'
            seed_pattern_run(db)
            response = SynthesisContractTests()._response()
            rp = run_dir / 'response.json'
            rp.write_text(json.dumps(response), encoding='utf-8')
            proc = subprocess.run([sys.executable, str(HERE / 'synthesis_cli.py'), 'import-response', '--run-dir', str(run_dir), '--run-id', 'r1', '--response', str(rp)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            store = EvidenceStore(db)
            self.assertEqual(store.conn.execute("SELECT COUNT(*) FROM insights WHERE run_id='r1'").fetchone()[0], 1)
            self.assertEqual(store.conn.execute("SELECT COUNT(*) FROM creative_hypotheses WHERE run_id='r1'").fetchone()[0], 1)
            self.assertEqual(store.conn.execute("SELECT COUNT(*) FROM media_briefs WHERE run_id='r1'").fetchone()[0], 1)
            store.close()
if __name__ == '__main__':
    unittest.main()
