import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import graph, search, memory
from backend.main import api, build


class CoreTests(unittest.TestCase):
    def setUp(self):
        memory.clear()

    def test_missing_search_key_does_not_invent_evidence(self):
        with patch.dict('os.environ', {'TAVILY_API_KEY': ''}):
            evidence, cached = search.fetch_evidence({'text': 'GPT-4 costs $10'})
        self.assertEqual(evidence, [])
        self.assertFalse(cached)

    def test_outdated_claim_requires_cited_source(self):
        claims = [{'id': 1, 'text': 'Price is $10', 'category': 'pricing'}]
        evidence = [{'claim_id': 1, 'url': 'https://example.com', 'content': 'Price is $20'}]
        with patch.object(graph, 'ask_json', return_value={'analysis': [{'id': 1, 'status': 'outdated', 'current_fact': 'Price is $20', 'sources': []}]}):
            result = graph.run_analysis_logic(claims, evidence, analyst_model={'model': 'test'})
        self.assertEqual(result[0]['status'], 'unverifiable')

    def test_unanalyzed_evidence_does_not_create_verdict(self):
        claims = [{'id': 1, 'text': 'A claim', 'category': 'other'}]
        evidence = [{'claim_id': 1, 'url': 'https://example.com', 'content': 'deprecated'}]
        self.assertEqual(graph.run_analysis_logic(claims, evidence)[0]['status'], 'unverifiable')

    def test_rewrite_requires_only_allowed_citations(self):
        results = [{'verdict': 'Stale', 'current_fact': 'New fact', 'sources': ['https://example.com']}]
        for replacement in ['New fact', 'New fact [source](https://evil.com)', 'New [source](https://example.com) [other](https://evil.com)']:
            self.assertEqual(graph.apply_rewrite('Old fact', results, custom_edits=[{'original': 'Old fact', 'replacement': replacement}]), 'Old fact')
        self.assertEqual(graph.apply_rewrite('Old fact', results, custom_edits=[{'original': 'Old fact', 'replacement': 'New fact [source](https://example.com)'}]), 'New fact [source](https://example.com)')

    def test_no_claims_is_not_a_perfect_score(self):
        self.assertIsNone(build('An answer', {'results': []}).overall)

    def test_missing_llm_key_fails_instead_of_placeholder(self):
        with patch.dict('os.environ', {'OPENAI_API_KEY': '', 'BIFROST_API_KEY': '', 'BIFROST_KEY': ''}):
            with self.assertRaises(RuntimeError):
                graph.local_answer('A question')

    def test_api_validation_and_empty_claims(self):
        client = TestClient(api)
        self.assertEqual(client.post('/api/check', json={'text': 'a'}).status_code, 422)
        with patch('backend.graph.ask_json', return_value={'claims': [], 'stable_facts': ['A stable fact.']}):
            response = client.post('/api/check', json={'text': 'A stable fact.'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['overall'])


if __name__ == '__main__':
    unittest.main()
