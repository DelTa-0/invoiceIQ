"""LLM client, JSON parsing, and retry-with-fix tests (docs/12 §4, docs/13)."""

from __future__ import annotations

from invoiceiq.llm.client import MockClient, complete_structured, parse_json_text
from invoiceiq.llm.schema import LLMExtraction


def test_parse_strips_fences():
    assert parse_json_text('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_text('noise {"a": 1} more noise') == {"a": 1}


def test_mock_client_returns_canned_response():
    client = MockClient('{"doc_type": "invoice", "fields": {}}')
    assert client.complete([], json_mode=True) == '{"doc_type": "invoice", "fields": {}}'


def test_retry_with_fix_on_schema_failure():
    class Flaky(MockClient):
        def __init__(self, responses):
            super().__init__(responses[0])
            self._responses = list(responses)
            self.calls = 0

        def complete(self, messages, *, json_mode=False, temperature=0.0):
            self.calls += 1
            return self._responses[min(self.calls, len(self._responses)) - 1]

    flaky = Flaky(['{"doc_type": 123', '{"doc_type": "invoice", "fields": {}}'])
    result = complete_structured(flaky, [{"role": "user", "content": "x"}], LLMExtraction)
    assert result.doc_type == "invoice"
    assert flaky.calls == 2
