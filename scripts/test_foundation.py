"""Modular Research V2 Phase 1 foundation tests (stdlib unittest, offline)."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

class ResearchRequestTests(unittest.TestCase):

    def setUp(self):
        from research_request import ResearchRequest
        self.ResearchRequest = ResearchRequest

    def test_valid_request_round_trip(self):
        data = {'schema_version': '1.0', 'topic': 'standing desk', 'platform': 'tiktok', 'market': 'US', 'language': 'en', 'research_goals': ['creative_patterns', 'voc'], 'time_range': {'days': 90}, 'content_scope': {'organic': True, 'ads': True, 'comments': True}, 'depth': 'standard', 'outputs': ['evidence', 'findings'], 'user_goal_text': '研究美国 TikTok standing desk 视频'}
        req = self.ResearchRequest.from_dict(data)
        self.assertEqual(req.to_dict()['topic'], 'standing desk')
        self.assertEqual(req.to_dict()['research_goals'], ['creative_patterns', 'voc'])
        self.assertEqual(req.to_dict()['user_goal_text'], data['user_goal_text'])

    def test_platform_is_normalized(self):
        req = self.ResearchRequest.from_dict({'topic': 'desk', 'platform': 'TikTok', 'market': 'us', 'research_goals': ['hooks']})
        self.assertEqual(req.platform, 'tiktok')
        self.assertEqual(req.market, 'US')

    def test_depth_defaults_to_standard(self):
        req = self.ResearchRequest.from_dict({'topic': 'desk', 'platform': 'tiktok', 'market': 'US', 'research_goals': ['hooks']})
        self.assertEqual(req.depth, 'standard')

    def test_empty_topic_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'topic'):
            self.ResearchRequest.from_dict({'topic': ' ', 'platform': 'tiktok', 'market': 'US', 'research_goals': ['hooks']})

    def test_invalid_depth_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'depth'):
            self.ResearchRequest.from_dict({'topic': 'desk', 'platform': 'tiktok', 'market': 'US', 'research_goals': ['hooks'], 'depth': 'huge'})

    def test_unknown_goal_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'research_goals'):
            self.ResearchRequest.from_dict({'topic': 'desk', 'platform': 'tiktok', 'market': 'US', 'research_goals': ['make_me_viral']})

    def test_tiktok_request_without_market_reports_material_missing(self):
        req = self.ResearchRequest.from_dict({'topic': 'desk', 'platform': 'tiktok', 'research_goals': ['creative_patterns']})
        self.assertIn('market', req.validate_material_fields())

    def test_douyin_topic_radar_does_not_require_market(self):
        req = self.ResearchRequest.from_dict({'topic': '宠物用品', 'platform': 'douyin', 'research_goals': ['low_follower_breakouts']})
        self.assertNotIn('market', req.validate_material_fields())

    def test_filters_and_optional_lists_round_trip(self):
        req = self.ResearchRequest.from_dict({'topic': 'desk', 'platform': 'tiktok', 'market': 'GB', 'research_goals': ['creative_patterns'], 'audience': 'remote workers', 'seed_keywords': ['standing desk', 'desk setup'], 'competitors': ['brand-a'], 'video_filters': {'content_types': ['ugc'], 'duration_sec': {'min': 5, 'max': 30}, 'creator_followers': {'min': None, 'max': 50000}, 'minimum_views': 10000, 'include_ads': True, 'include_organic': True}})
        out = req.to_dict()
        self.assertEqual(out['audience'], 'remote workers')
        self.assertEqual(out['video_filters']['creator_followers']['max'], 50000)
        self.assertEqual(out['seed_keywords'], ['standing desk', 'desk setup'])

    def test_duplicate_goals_are_deduplicated_preserving_order(self):
        req = self.ResearchRequest.from_dict({'topic': 'desk', 'platform': 'tiktok', 'market': 'US', 'research_goals': ['hooks', 'voc', 'hooks']})
        self.assertEqual(req.research_goals, ['hooks', 'voc'])

    def test_schema_version_defaults_to_1_0(self):
        req = self.ResearchRequest.from_dict({'topic': 'desk', 'platform': 'tiktok', 'market': 'US', 'research_goals': ['hooks']})
        self.assertEqual(req.schema_version, '1.0')

    def test_schema_file_exists_and_has_no_business_defaults(self):
        path = ROOT / 'references' / 'schemas' / 'research-request.schema.json'
        obj = json.loads(path.read_text(encoding='utf-8'))
        text = json.dumps(obj, ensure_ascii=False).lower()
        self.assertEqual(obj['title'], 'Modular Research ResearchRequest')
        self.assertNotIn('wood bead bracelet', text)
        self.assertNotIn('"default": "us"', text)

class ProfileResolutionTests(unittest.TestCase):

    def _request(self, **overrides):
        from research_request import ResearchRequest
        data = {'topic': 'generic topic', 'platform': 'tiktok', 'market': 'CA', 'research_goals': ['creative_patterns']}
        data.update(overrides)
        return ResearchRequest.from_dict(data)

    def test_profiles_load_from_canonical_directory(self):
        from profile_loader import load_profiles
        profiles = load_profiles()
        self.assertIn('tiktok-video-intelligence-v1', profiles)
        self.assertIn('douyin-topic-radar-v1', profiles)

    def test_tiktok_creative_goal_resolves_video_intelligence(self):
        from profile_resolver import resolve_profile
        result = resolve_profile(self._request())
        self.assertEqual(result.profile_id, 'tiktok-video-intelligence-v1')
        self.assertIn('PLATFORM_TIKTOK', result.reason_codes)
        self.assertGreaterEqual(result.confidence, 0.9)

    def test_tiktok_voc_goal_resolves_video_intelligence(self):
        from profile_resolver import resolve_profile
        result = resolve_profile(self._request(research_goals=['voc']))
        self.assertEqual(result.profile_id, 'tiktok-video-intelligence-v1')
        self.assertIn('GOAL_VOC', result.reason_codes)

    def test_douyin_low_follower_resolves_topic_radar(self):
        from profile_resolver import resolve_profile
        req = self._request(platform='douyin', market=None, research_goals=['low_follower_breakouts'])
        result = resolve_profile(req)
        self.assertEqual(result.profile_id, 'douyin-topic-radar-v1')
        self.assertIn('PLATFORM_DOUYIN', result.reason_codes)

    def test_unknown_platform_has_no_silent_fallback(self):
        from profile_resolver import resolve_profile
        req = self._request(platform='youtube')
        with self.assertRaisesRegex(ValueError, 'profile'):
            resolve_profile(req)

    def test_profile_files_do_not_hardcode_topic_or_market(self):
        profile_dir = ROOT / 'references' / 'profiles'
        texts = '\n'.join((p.read_text(encoding='utf-8') for p in profile_dir.glob('*.json')))
        lowered = texts.lower()
        self.assertNotIn('wood bead bracelet', lowered)
        self.assertNotIn('"market": "us"', lowered)
        self.assertNotIn('"topic":', lowered)

    def test_profile_loader_rejects_duplicate_profile_ids(self):
        from profile_loader import load_profiles
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            profile = {'id': 'same', 'version': '1.0', 'platform': 'tiktok', 'default_provider': 'tikhub', 'supported_goals': ['hooks'], 'required_capabilities': [], 'default_content_scope': {}, 'depth_presets': {}, 'stages': [], 'analysis_modules': [], 'output_contracts': []}
            (d / 'a.json').write_text(json.dumps(profile), encoding='utf-8')
            (d / 'b.json').write_text(json.dumps(profile), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                load_profiles(d)

class EndpointRegistryTests(unittest.TestCase):

    def test_registry_loads_legacy_douyin_endpoint(self):
        from endpoint_registry import EndpointRegistry
        reg = EndpointRegistry()
        ep = reg.get('tikhub', 'douyin', 'video_detail')
        self.assertEqual(ep['method'], 'GET')
        self.assertEqual(ep['path'], '/api/v1/douyin/web/fetch_one_video')

    def test_registry_loads_tiktok_video_search(self):
        from endpoint_registry import EndpointRegistry
        ep = EndpointRegistry().get('tikhub', 'tiktok', 'video_search')
        self.assertEqual(ep['method'], 'GET')
        self.assertEqual(ep['path'], '/api/v1/tiktok/app/v3/fetch_video_search_result')

    def test_registry_loads_tiktok_creator_search_insights(self):
        from endpoint_registry import EndpointRegistry
        ep = EndpointRegistry().get('tikhub', 'tiktok', 'creator_search_insights')
        self.assertEqual(ep['method'], 'GET')
        self.assertIn('fetch_creator_search_insights', ep['path'])

    def test_registry_loads_tiktok_ad_keyframe_method_individually(self):
        from endpoint_registry import EndpointRegistry
        ep = EndpointRegistry().get('tikhub', 'tiktok', 'ad_keyframe_analysis')
        self.assertEqual(ep['method'], 'POST')
        self.assertEqual(ep['request_location'], 'json')
        self.assertEqual(ep['path'], '/api/v1/tiktok/ads/get_ad_keyframe_analysis')

    def test_registry_unknown_capability_lists_available(self):
        from endpoint_registry import EndpointRegistry
        with self.assertRaisesRegex(KeyError, '已有'):
            EndpointRegistry().get('tikhub', 'tiktok', 'does_not_exist')

    def test_registry_capability_listing_is_sorted(self):
        from endpoint_registry import EndpointRegistry
        caps = EndpointRegistry().list_capabilities('tikhub', 'tiktok')
        self.assertEqual(caps, sorted(caps))
        self.assertIn('video_metrics', caps)
        self.assertIn('video_comments', caps)

    def test_legacy_planner_resolve_endpoint_keeps_decimal_price(self):
        from decimal import Decimal
        import research_planner as planner
        ep = planner.resolve_endpoint('tikhub', 'douyin', 'video_detail')
        self.assertIsInstance(ep['unit_price'], Decimal)
        self.assertEqual(ep['unit_price'], Decimal('0.001'))

    def test_research_planner_has_no_embedded_routing_table_authority(self):
        text = (ROOT / 'scripts' / 'research_planner.py').read_text(encoding='utf-8')
        self.assertNotIn('ROUTING_TABLE: dict =', text)
        self.assertIn('EndpointRegistry', text)

class RequestCliCompatibilityTests(unittest.TestCase):

    def _args(self, **overrides):
        base = dict(request=None, topic=None, platform=None, market=None, research_goal=[], depth='standard', goal=None)
        base.update(overrides)
        return argparse.Namespace(**base)

    def test_load_request_json(self):
        import run_research
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'request.json'
            path.write_text(json.dumps({'topic': 'coffee machine', 'platform': 'tiktok', 'market': 'GB', 'research_goals': ['voc']}), encoding='utf-8')
            req = run_research.load_research_request_from_args(self._args(request=str(path)))
            self.assertEqual(req.topic, 'coffee machine')
            self.assertEqual(req.market, 'GB')

    def test_load_convenience_args(self):
        import run_research
        req = run_research.load_research_request_from_args(self._args(topic='standing desk', platform='TikTok', market='us', research_goal=['hooks', 'voc'], depth='deep'))
        self.assertEqual(req.platform, 'tiktok')
        self.assertEqual(req.research_goals, ['hooks', 'voc'])
        self.assertEqual(req.depth, 'deep')

    def test_legacy_goal_without_new_request_returns_none(self):
        import run_research
        req = run_research.load_research_request_from_args(self._args(goal='旧 Douyin 调研'))
        self.assertIsNone(req)

    def test_request_file_and_convenience_args_cannot_be_mixed(self):
        import run_research
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'request.json'
            path.write_text(json.dumps({'topic': 'x', 'platform': 'tiktok', 'market': 'US', 'research_goals': ['hooks']}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'cannot mix'):
                run_research.load_research_request_from_args(self._args(request=str(path), topic='other'))

    def test_new_request_parser_does_not_require_internal_profile_or_endpoint(self):
        text = (ROOT / 'scripts' / 'run_research.py').read_text(encoding='utf-8')
        self.assertIn('--request', text)
        self.assertIn('--research-goal', text)
        self.assertNotIn('--profile', text)
        self.assertNotIn('--endpoint', text)

    def test_new_request_requires_plan_only_in_phase1(self):
        import run_research
        req = run_research.load_research_request_from_args(self._args(topic='desk', platform='tiktok', market='US', research_goal=['hooks']))
        result = run_research.build_intake_plan(req)
        self.assertEqual(result['profile']['profile_id'], 'tiktok-video-intelligence-v1')
        self.assertEqual(result['execution_status'], 'PLAN_ONLY_FOUNDATION')
        self.assertEqual(result['missing_material_fields'], [])

class PortabilityAndDocsTests(unittest.TestCase):

    def test_foundation_modules_have_no_host_project_imports(self):
        names = ['research_request.py', 'profile_loader.py', 'profile_resolver.py', 'endpoint_registry.py', 'research_planner.py']
        text = '\n'.join(((ROOT / 'scripts' / name).read_text(encoding='utf-8') for name in names)).lower()
        self.assertNotIn('import hco', text)
        self.assertNotIn('import hermes', text)
        self.assertNotIn('import shopify', text)

    def test_gitignore_excludes_plaintext_config_and_runtime_outputs(self):
        text = (ROOT / '.gitignore').read_text(encoding='utf-8')
        self.assertIn('config.json', text)
        self.assertIn('__pycache__/', text)
        self.assertIn('social-research/', text)

    def test_skill_defines_runtime_intake_not_fixed_business_request(self):
        text = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        lowered = text.lower()
        self.assertIn('researchrequest', lowered)
        self.assertIn('research intake', lowered)
        self.assertIn('profile resolver', lowered)
        self.assertNotIn('例："宠物防滑袜选题调研', lowered)

    def test_skill_says_user_need_not_provide_internal_profile_or_endpoint(self):
        text = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        self.assertIn('不得要求用户提供', text)
        self.assertIn('endpoint', text.lower())
        self.assertIn('profile', text.lower())

    def test_routing_table_marks_endpoints_json_as_machine_authority(self):
        text = (ROOT / 'references' / 'routing-table.md').read_text(encoding='utf-8')
        self.assertIn('endpoints.json', text)
        self.assertIn('唯一机器权威', text)

    def test_distributed_profiles_contain_no_api_key(self):
        text = '\n'.join((p.read_text(encoding='utf-8') for p in (ROOT / 'references' / 'profiles').glob('*.json')))
        self.assertNotIn('api_key', text.lower())
        self.assertNotIn('bearer ', text.lower())
if __name__ == '__main__':
    unittest.main()
