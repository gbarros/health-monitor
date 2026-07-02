from __future__ import annotations

import unittest

from scripts.extract_chatgpt_log_signals import extract_signal_payload


class ChatGPTSignalExtractionTest(unittest.TestCase):
    def test_extract_signal_payload_returns_sanitized_candidates_without_records(self) -> None:
        html = """
        <html><body>
          <p>2026-07-01 10am, 100g queijo minas, 2 ovos. Total 450 kcal.</p>
          <p>Na verdade corrigir queijo para 50g.</p>
          <p>Usei novo rótulo do Iogurte Batavo Protein. Código 7891000000000.</p>
          <p>KFC Double Crunch combo no Brasil precisa de pesquisa externa.</p>
          <p>Revisão da semana: social dinners made adherence harder.</p>
        </body></html>
        """

        payload = extract_signal_payload(html, source_name="synthetic.html", redact=True)
        candidate_types = {item["candidate_type"] for item in payload["candidates"]}

        self.assertEqual(payload["format"], "health-monitor.chatgpt-signals")
        self.assertIn("meal_log_candidate", candidate_types)
        self.assertIn("correction_candidate", candidate_types)
        self.assertIn("label_or_version_candidate", candidate_types)
        self.assertIn("restaurant_lookup_candidate", candidate_types)
        self.assertIn("review_note_candidate", candidate_types)
        self.assertEqual(payload["durable_write_policy"], "proposals_or_fixtures_only")
        self.assertNotIn("diary_entries", payload)
        self.assertNotIn("7891000000000", str(payload["candidates"]))


if __name__ == "__main__":
    unittest.main()
