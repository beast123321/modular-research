"""Modular Research V2 Phase 5 tests: media evidence + creative understanding contract."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
import unittest
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

def make_request(*, goals=None, depth='standard'):
    from research_request import ResearchRequest
    return ResearchRequest.from_dict({'topic': 'standing desk', 'platform': 'tiktok', 'market': 'US', 'language': 'en', 'research_goals': goals or ['hooks'], 'time_range': {'days': 90}, 'content_scope': {}, 'seed_keywords': [], 'depth': depth})

def make_video(path: Path) -> None:
    import cv2
    import numpy as np
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), 10.0, (96, 64))
    if not writer.isOpened():
        raise RuntimeError('OpenCV VideoWriter unavailable')
    for idx in range(30):
        if idx < 10:
            frame = np.zeros((64, 96, 3), dtype=np.uint8)
        elif idx < 20:
            frame = np.full((64, 96, 3), 255, dtype=np.uint8)
        else:
            frame = np.zeros((64, 96, 3), dtype=np.uint8)
            frame[:, :, 1] = 255
        writer.write(frame)
    writer.release()

class Phase5SchemaTests(unittest.TestCase):

    def test_phase5_tables_exist(self):
        from evidence_store import EvidenceStore
        with tempfile.TemporaryDirectory() as td:
            store = EvidenceStore(Path(td) / 'run.sqlite')
            names = set(store.table_names())
            expected = {'media_assets', 'media_keyframes', 'transcript_segments', 'creative_analysis'}
            self.assertTrue(expected.issubset(names), expected - names)
            store.close()

    def test_creative_analysis_persists_provenance_and_confidence(self):
        from evidence_store import EvidenceStore
        with tempfile.TemporaryDirectory() as td:
            store = EvidenceStore(Path(td) / 'run.sqlite')
            store.record_run('r1', {'topic': 'x'}, 'p1', 'tikhub')
            store.upsert_creative_analysis('r1', {'video_id': 'v1', 'schema_version': '1.0', 'analyzer': {'name': 'host-agent', 'version': '1', 'mode': 'multimodal'}, 'hook_type': 'QUESTION', 'hook_text': 'Why does this move?', 'format': 'PRODUCT_DEMO', 'selling_angle': 'FUNCTIONALITY', 'proof_type': 'DEMO', 'product_visible_at': 0.2, 'cta_text': None, 'cta_at': None, 'shot_count': 3, 'avg_shot_length': 1.2, 'visual_style': 'clean', 'timeline': [], 'confidence': {'hook_type': 0.9}, 'evidence_refs': ['frame:v1:0']})
            row = store.conn.execute("SELECT analyzer_name,analyzer_mode,confidence_json,evidence_refs_json FROM creative_analysis WHERE run_id='r1' AND video_id='v1'").fetchone()
            self.assertEqual(row[0], 'host-agent')
            self.assertEqual(row[1], 'multimodal')
            self.assertEqual(json.loads(row[2])['hook_type'], 0.9)
            self.assertEqual(json.loads(row[3]), ['frame:v1:0'])
            store.close()

class ShortlistTests(unittest.TestCase):

    def test_shortlist_uses_transparent_buckets_without_composite_score(self):
        from evidence_store import EvidenceStore
        from creative.shortlist import select_creative_shortlist
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'run.sqlite'
            store = EvidenceStore(db)
            store.record_run('r1', {'topic': 'x'}, 'p1', 'tikhub')
            for idx in range(1, 7):
                store.conn.execute('INSERT INTO videos(video_id,caption,video_url,first_seen_at,last_seen_at,raw_evidence_id) VALUES(?,?,?,?,?,?)', (f'v{idx}', f'video {idx}', f'https://cdn.example.com/v{idx}.mp4', '2026', '2026', f'raw{idx}'))
            metrics = [('v1', 0.99, 0.1, 0.1, 0.1, 1.0), ('v2', 0.2, 0.98, 0.1, 0.1, 1.0), ('v3', 0.2, 0.1, 0.97, 0.1, 1.0), ('v4', 0.2, 0.1, 0.1, 0.96, 5.0), ('v5', 0.95, 0.95, 0.95, 0.95, 4.0), ('v6', 0.1, 0.1, 0.1, 0.1, 0.5)]
            for video_id, views_p, eng_p, share_p, lev_p, over in metrics:
                store.conn.execute('INSERT INTO video_metrics_derived(run_id,video_id,views_percentile,engagement_percentile,share_rate_percentile,follower_leverage_percentile,creator_overperformance,cohort_json,evidence_refs_json,computed_at)\n                       VALUES(?,?,?,?,?,?,?,?,?,?)', ('r1', video_id, views_p, eng_p, share_p, lev_p, over, '{}', json.dumps(['raw:' + video_id]), '2026'))
            store.conn.commit()
            store.close()
            rows = select_creative_shortlist(db, 'r1', 4)
            ids = [r['video_id'] for r in rows]
            self.assertEqual(len(ids), 4)
            self.assertIn('v1', ids)
            self.assertIn('v2', ids)
            self.assertIn('v3', ids)
            self.assertTrue(all(('creative_score' not in row for row in rows)))
            self.assertTrue(all((row['selection_reasons'] for row in rows)))

    def test_shortlist_honors_runtime_video_filters(self):
        from evidence_store import EvidenceStore
        from creative.shortlist import select_creative_shortlist
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'run.sqlite'
            store = EvidenceStore(db)
            store.record_run('r1', {'topic': 'x'}, 'p1', 'tikhub')
            for vid, dur, views, followers in (('short', 10, 50000, 5000), ('long', 45, 1000000, 100000)):
                store.conn.execute('INSERT INTO videos(video_id,duration_sec,video_url,first_seen_at,last_seen_at,raw_evidence_id) VALUES(?,?,?,?,?,?)', (vid, dur, f'https://cdn.example.com/{vid}.mp4', '2026', '2026', f'raw:{vid}'))
                store.conn.execute('INSERT INTO video_snapshots(run_id,video_id,views,author_followers,captured_at,raw_evidence_id) VALUES(?,?,?,?,?,?)', ('r1', vid, views, followers, '2026', f'raw:{vid}'))
                store.conn.execute('INSERT INTO video_metrics_derived(run_id,video_id,views_percentile,engagement_percentile,share_rate_percentile,follower_leverage_percentile,cohort_json,evidence_refs_json,computed_at) VALUES(?,?,?,?,?,?,?,?,?)', ('r1', vid, 1.0, 1.0, 1.0, 1.0, '{}', json.dumps([f'raw:{vid}']), '2026'))
            store.conn.commit()
            store.close()
            rows = select_creative_shortlist(db, 'r1', 10, video_filters={'duration': {'max': 15}, 'creator_size': {'max_followers': 10000}, 'minimum_views': 10000})
            self.assertEqual([r['video_id'] for r in rows], ['short'])

class MediaTests(unittest.TestCase):

    def test_media_url_blocks_private_and_file_urls(self):
        from media.assets import validate_public_media_url
        for url in ('http://127.0.0.1/a.mp4', 'http://10.0.0.5/a.mp4', 'file:///tmp/a.mp4'):
            with self.assertRaises(ValueError, msg=url):
                validate_public_media_url(url)
        validate_public_media_url('https://cdn.example.com/a.mp4', resolve_dns=False)

    def test_download_media_enforces_max_bytes_with_injected_fetcher(self):
        from media.assets import download_media
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / 'x.mp4'

            def fetcher(_url):
                return [b'abc', b'def']
            with self.assertRaises(ValueError):
                download_media('https://cdn.example.com/a.mp4', dest, max_bytes=5, fetcher=fetcher, validate_url=False)
            self.assertFalse(dest.exists())

    def test_probe_and_keyframes_detect_multiple_scenes(self):
        from media.video import probe_video, extract_keyframes
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            video = root / 'test.mp4'
            make_video(video)
            meta = probe_video(video)
            self.assertEqual(meta['width'], 96)
            self.assertEqual(meta['height'], 64)
            self.assertGreater(meta['duration_sec'], 2.5)
            frames = extract_keyframes(video, root / 'frames', max_frames=8, sample_fps=5.0)
            self.assertGreaterEqual(len(frames), 3)
            self.assertEqual(frames[0]['timestamp_sec'], 0.0)
            self.assertTrue(all((Path(f['path']).exists() for f in frames)))
            self.assertEqual(sorted((f['timestamp_sec'] for f in frames)), [f['timestamp_sec'] for f in frames])

class OCRTranscriptTests(unittest.TestCase):

    def test_ocr_none_is_explicitly_unavailable(self):
        from media.ocr import ocr_keyframes
        got = ocr_keyframes([{'path': '/does/not/matter.jpg', 'timestamp_sec': 0.0}], engine='none')
        self.assertEqual(got['status'], 'unavailable')
        self.assertEqual(got['items'], [])

    def test_load_srt_transcript(self):
        from media.transcript import load_sidecar_transcript
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'a.srt'
            p.write_text('1\n00:00:00,000 --> 00:00:01,500\nHello world\n\n2\n00:00:02,000 --> 00:00:03,000\nBuy now\n', encoding='utf-8')
            rows = load_sidecar_transcript(p)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['start_sec'], 0.0)
            self.assertEqual(rows[0]['end_sec'], 1.5)
            self.assertEqual(rows[1]['text'], 'Buy now')

class CreativeContractTests(unittest.TestCase):

    def _valid_payload(self):
        return {'schema_version': '1.0', 'video_id': 'v1', 'analyzer': {'name': 'host-agent', 'version': '1', 'mode': 'multimodal'}, 'hook_type': 'QUESTION', 'hook_text': 'Does this work?', 'product_visible_at': 0.3, 'format': 'PRODUCT_DEMO', 'selling_angle': 'FUNCTIONALITY', 'proof_type': 'DEMO', 'cta_text': 'Shop now', 'cta_at': 8.0, 'shot_count': 4, 'avg_shot_length': 2.0, 'visual_style': 'clean', 'timeline': [{'start_sec': 0.0, 'end_sec': 1.0, 'event_type': 'HOOK', 'description': 'question', 'evidence_refs': ['frame:0'], 'confidence': 0.9}, {'start_sec': 1.0, 'end_sec': 3.0, 'event_type': 'PRODUCT', 'description': 'demo', 'evidence_refs': ['frame:1'], 'confidence': 0.8}], 'confidence': {'hook_type': 0.9, 'format': 0.8}, 'evidence_refs': ['frame:0', 'frame:1']}

    def test_valid_contract_passes_and_preserves_unknown_nulls(self):
        from creative.contracts import validate_analysis_response
        payload = self._valid_payload()
        got = validate_analysis_response(payload)
        self.assertEqual(got['hook_type'], 'QUESTION')
        self.assertEqual(got['format'], 'PRODUCT_DEMO')

    def test_invalid_taxonomy_label_is_rejected(self):
        from creative.contracts import validate_analysis_response
        payload = self._valid_payload()
        payload['hook_type'] = 'MAGIC_VIRAL_HOOK'
        with self.assertRaises(ValueError):
            validate_analysis_response(payload)

    def test_timeline_must_be_ordered_and_confidence_bounded(self):
        from creative.contracts import validate_analysis_response
        payload = self._valid_payload()
        payload['timeline'][1]['start_sec'] = 0.5
        with self.assertRaises(ValueError):
            validate_analysis_response(payload)
        payload = self._valid_payload()
        payload['confidence']['hook_type'] = 1.5
        with self.assertRaises(ValueError):
            validate_analysis_response(payload)

    def test_analysis_request_exposes_evidence_not_business_conclusion(self):
        from creative.agent_bridge import build_analysis_request
        req = build_analysis_request(video={'video_id': 'v1', 'caption': 'desk demo', 'duration_sec': 10}, asset={'local_path': 'media/v1/source.mp4', 'duration_sec': 10}, keyframes=[{'id': 'frame:v1:0', 'timestamp_sec': 0.0, 'path': 'media/v1/f0.jpg', 'ocr_text': 'Desk'}], transcript=[{'start_sec': 0, 'end_sec': 1, 'text': 'Watch this'}])
        self.assertEqual(req['video_id'], 'v1')
        self.assertIn('required_output_schema', req)
        self.assertNotIn('hypothesis', json.dumps(req).lower())
        self.assertNotIn('business_truth', json.dumps(req).lower())

class StageAndRunnerTests(unittest.TestCase):

    def test_hooks_plan_has_local_video_understanding_stage(self):
        from stage_planner import build_stage_plan
        plan = build_stage_plan(make_request(goals=['hooks']))
        stage = next((s for s in plan.stages if s.name == 'VIDEO_UNDERSTANDING'))
        self.assertTrue(stage.local_only)

    def test_voc_only_plan_does_not_force_video_understanding(self):
        from stage_planner import build_stage_plan
        plan = build_stage_plan(make_request(goals=['voc']))
        self.assertNotIn('VIDEO_UNDERSTANDING', [s.name for s in plan.stages])

    def test_executor_media_download_is_explicit_opt_in(self):
        import inspect
        from research_executor_v2 import ResearchExecutorV2
        sig = inspect.signature(ResearchExecutorV2.execute)
        self.assertIn('download_media', sig.parameters)
        self.assertFalse(sig.parameters['download_media'].default)
        self.assertIn('media_limit', sig.parameters)

    def test_cli_exposes_media_opt_in_controls(self):
        import subprocess
        proc = subprocess.run([sys.executable, str(HERE / 'run_research.py'), '--help'], capture_output=True, text=True, check=True)
        self.assertIn('--download-media', proc.stdout)
        self.assertIn('--media-limit', proc.stdout)

    def test_creative_cli_imports_valid_response(self):
        import subprocess
        from evidence_store import EvidenceStore
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / 'r1'
            run_dir.mkdir()
            store = EvidenceStore(run_dir / 'run.sqlite')
            store.record_run('r1', {'topic': 'x'}, 'p1', 'tikhub')
            store.close()
            response = self._valid_payload() if hasattr(self, '_valid_payload') else {'schema_version': '1.0', 'video_id': 'v1', 'analyzer': {'name': 'host-agent', 'version': '1', 'mode': 'multimodal'}, 'hook_type': 'UNKNOWN', 'hook_text': None, 'product_visible_at': None, 'format': 'UNKNOWN', 'selling_angle': 'UNKNOWN', 'proof_type': 'UNKNOWN', 'cta_text': None, 'cta_at': None, 'shot_count': None, 'avg_shot_length': None, 'visual_style': None, 'timeline': [], 'confidence': {}, 'evidence_refs': []}
            rp = run_dir / 'response.json'
            rp.write_text(json.dumps(response), encoding='utf-8')
            proc = subprocess.run([sys.executable, str(HERE / 'creative_cli.py'), 'import-response', '--run-dir', str(run_dir), '--run-id', 'r1', '--response', str(rp)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            store = EvidenceStore(run_dir / 'run.sqlite')
            count = store.conn.execute("SELECT COUNT(*) FROM creative_analysis WHERE run_id='r1'").fetchone()[0]
            store.close()
            self.assertEqual(count, 1)

    def test_runner_prepares_shortlist_and_analysis_requests_without_download(self):
        from evidence_store import EvidenceStore
        from creative.runner import run_video_understanding
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / 'runs' / 'r1'
            run_dir.mkdir(parents=True)
            db = run_dir / 'run.sqlite'
            store = EvidenceStore(db)
            store.record_run('r1', {'topic': 'x'}, 'p1', 'tikhub')
            store.conn.execute('INSERT INTO videos(video_id,caption,video_url,first_seen_at,last_seen_at,raw_evidence_id) VALUES(?,?,?,?,?,?)', ('v1', 'demo', 'https://cdn.example.com/v1.mp4', '2026', '2026', 'raw1'))
            store.conn.execute('INSERT INTO video_metrics_derived(run_id,video_id,views_percentile,engagement_percentile,share_rate_percentile,follower_leverage_percentile,creator_overperformance,cohort_json,evidence_refs_json,computed_at)\n                   VALUES(?,?,?,?,?,?,?,?,?,?)', ('r1', 'v1', 1.0, 1.0, 1.0, 1.0, 2.0, '{}', '["raw1"]', '2026'))
            store.conn.commit()
            store.close()
            result = run_video_understanding(db, run_dir, 'r1', limit=5, download=False)
            self.assertEqual(result['shortlist_count'], 1)
            self.assertEqual(result['analysis_request_count'], 1)
            self.assertEqual(result['media_downloaded'], 0)
            self.assertTrue((run_dir / 'reports' / 'creative_shortlist.json').exists())
            self.assertTrue((run_dir / 'reports' / 'creative_analysis_requests.json').exists())
if __name__ == '__main__':
    unittest.main()
