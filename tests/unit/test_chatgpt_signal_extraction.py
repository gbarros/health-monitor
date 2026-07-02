from __future__ import annotations

import unittest
from datetime import date

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

    def test_extract_signal_payload_filters_by_inferred_context_date(self) -> None:
        html = """
        <html><body>
          <h2>2026-07-01</h2>
          <p>100g queijo minas. Total 315 kcal.</p>
          <h2>2026-07-02</h2>
          <p>100g Iogurte Batavo Protein. Total 70 kcal.</p>
          <h2>2026-07-03</h2>
          <p>Revisão da semana: social dinner.</p>
        </body></html>
        """

        payload = extract_signal_payload(
            html,
            source_name="synthetic.html",
            start_date=date(2026, 7, 2),
            end_date=date(2026, 7, 2),
        )

        self.assertEqual(payload["filters"]["start_date"], "2026-07-02")
        self.assertEqual(payload["filters"]["end_date"], "2026-07-02")
        self.assertEqual(
            {item["source_context"]["context_date"] for item in payload["candidates"]},
            {"2026-07-02"},
        )
        self.assertIn("Iogurte Batavo", str(payload["candidates"]))
        self.assertNotIn("queijo minas", str(payload["candidates"]))
        self.assertNotIn("social dinner", str(payload["candidates"]))


if __name__ == "__main__":
    unittest.main()
