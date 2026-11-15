"""Synthetic-only provider contracts. No network requests are made."""
import json

import pytest

from demo.backend.llm_drafts import (
    JbaiProvider, configured_provider, draft_guidance, draft_review,
    guidance_payload, review_payload,
)
from demo.backend.rules.doc_types import DocType

SECRET = "synthetic-not-a-real-key"


def enabled_env(**changes):
    return {"PROGRAM_LLM_ENABLED": "true", "PROGRAM_LLM_PROVIDER": "jbai",
            "JBAI_BASE_URL": "https://drafts.example.invalid/v1", "JBAI_API_KEY": SECRET,
            **changes}


class FakeProvider:
    name = "fake"

    def __init__(self, reply="합성 초안"):
        self.calls = []
        self.reply = reply

    def generate(self, purpose, payload):
        self.calls.append((purpose, payload))
        return self.reply


def test_none_is_default_even_when_credentials_exist():
    assert configured_provider(environ={}).name == "none"
    values = enabled_env()
    values.pop("PROGRAM_LLM_ENABLED")
    assert configured_provider(environ=values).name == "none"
    values = enabled_env(PROGRAM_LLM_ENABLED="false")
    assert configured_provider(environ=values).name == "none"


@pytest.mark.parametrize("changes", [
    {"JBAI_API_KEY": ""}, {"JBAI_BASE_URL": ""}, {"JBAI_BASE_URL": "http://example.invalid"},
    {"JBAI_BASE_URL": "https://user:password@example.invalid"},
    {"JBAI_BASE_URL": "https://example.invalid?secret=synthetic"},
    {"JBAI_BASE_URL": "https://[invalid"}, {"PROGRAM_LLM_PROVIDER": "other"},
])
def test_configuration_never_enables_without_explicit_complete_safe_settings(changes):
    assert configured_provider(environ=enabled_env(**changes)).name == "none"


def test_guidance_projection_discards_applicant_keys_and_arbitrary_doc_values():
    payload = guidance_payload({"title": "합성 사업", "apply_start": "2026-11-01", "apply_end": "2026-12-01",
                                "name": "가상개인", "birth": "1999-01-01", "address": "비공개 합성 주소",
                                "account": "synthetic-private-account", "ocr_fields": {"성명": "가상개인"}},
                               [DocType.RESIDENT_ABSTRACT, "private-document-value", {"성명": "가상개인"}],
                               "합성 공개 공고")
    assert set(payload) == {"title", "apply_start", "apply_end", "documents", "notice_text"}
    assert payload["documents"] == ["주민등록초본"]
    assert "가상개인" not in json.dumps(payload, ensure_ascii=False)
    assert "synthetic-private-account" not in json.dumps(payload)


def test_guidance_fake_provider_receives_only_public_projection():
    provider = FakeProvider()
    result = draft_guidance({"title": "공개 합성 사업", "apply_start": "2026-11-01", "apply_end": "2026-12-01",
                             "identity_json": {"name": "가상개인"}},
                            [DocType.PAYMENT_RECEIPT], "공개 공고문", provider=provider)
    assert result["text"] == "합성 초안" and result["source"] == "fake"
    assert provider.calls[0][0] == "guidance"
    assert "identity_json" not in json.dumps(provider.calls)


def test_review_projection_reconstructs_rules_from_codes_and_drops_all_values():
    provider = FakeProvider()
    codes = ["IDENTITY_UNCERTAIN", {"code": "IDENTITY_UNCERTAIN", "name": "가상개인"},
             "IDENTITY_UNCERTAIN 가상개인 1999-01-01 비공개주소 synthetic-account", "UNKNOWN_PRIVATE", "IDENTITY_UNCERTAIN"]
    result = draft_review(codes, provider=provider)
    sent = provider.calls[0][1]
    assert len(sent["rules"]) == 1
    assert set(sent["rules"][0]) == {"code", "field_names", "rule_text"}
    assert sent["rules"][0]["field_names"] == ["성명", "생년월일"]
    assert "가상개인" not in json.dumps(sent, ensure_ascii=False)
    assert result["label"] == "설명(자동 작성)" and "규칙 결과" in result["basis"]


def test_review_unknown_codes_do_not_call_provider_or_echo_values():
    provider = FakeProvider()
    result = draft_review(["UNRECOGNIZED synthetic-secret", {"name": "가상개인"}], provider=provider)
    assert provider.calls == [] and result["source"] == "rules"
    assert "가상개인" not in result["text"] and "synthetic-secret" not in result["text"]


def test_rule_fallback_uses_only_canonical_rules():
    provider = FakeProvider(reply=None)
    result = draft_review(["FORM_REQUIRED_MISSING"], provider=provider)
    assert result["source"] == "rules" and "필수 입력칸" in result["text"]
    guidance = draft_guidance({"title": "공개 사업", "apply_start": "2026-11-01", "apply_end": "2026-12-01"},
                              [DocType.RESIDENT_ABSTRACT], provider=provider)
    assert guidance["source"] == "rules" and "본인인증" in guidance["text"]


def test_fake_jbai_transport_receives_reprojected_canonical_only_and_no_redirect():
    calls = []

    def fake_transport(url, headers, body, timeout):
        calls.append((url, headers, body, timeout))
        return {"choices": [{"message": {"content": "자동 설명 합성"}}]}

    provider = configured_provider(environ=enabled_env(JBAI_LLM_MODEL="synthetic-model"), transport=fake_transport)
    result = provider.generate("review", {"rules": [{"code": "IDENTITY_UNCERTAIN", "field_names": ["가상개인"],
                                                     "rule_text": "비공개주소 synthetic-account"}],
                                          "name": "가상개인", "birth": "1999-01-01"})
    assert result == "자동 설명 합성"
    url, headers, body, timeout = calls[0]
    assert url == "https://drafts.example.invalid/v1/chat/completions" and timeout == 10
    assert headers["Authorization"] == "Bearer " + SECRET
    assert body["model"] == "synthetic-model"
    sent = json.loads(body["messages"][1]["content"])
    assert sent == review_payload(["IDENTITY_UNCERTAIN"])
    assert all(value not in json.dumps(body, ensure_ascii=False) for value in ("가상개인", "비공개주소", "synthetic-account", "1999-01-01", SECRET))
    assert SECRET not in repr(provider)


def test_fake_jbai_guidance_transport_reprojects_fields_at_send_boundary():
    calls = []

    def fake_transport(url, headers, body, timeout):
        calls.append(body)
        return {"choices": [{"message": {"content": "합성 사업 안내"}}]}

    provider = configured_provider(environ=enabled_env(), transport=fake_transport)
    provider.generate("guidance", {"title": "공개 사업", "apply_start": "2026-11-01", "apply_end": "2026-12-01",
                                   "documents": ["주민등록초본", "가상개인 계좌"], "notice_text": "공개 공고문",
                                   "ocr_fields": {"성명": "가상개인"}, "address": "비공개주소"})
    assert len(calls) == 1
    assert "가상개인" not in json.dumps(calls[0], ensure_ascii=False)
    assert "비공개주소" not in json.dumps(calls[0], ensure_ascii=False)


def test_transport_failure_is_silent_and_uses_rules(capsys, caplog):
    def fake_transport(*args):
        raise RuntimeError("synthetic-secret private data")

    provider = configured_provider(environ=enabled_env(), transport=fake_transport)
    result = draft_review(["LOW_OCR_CONFIDENCE"], provider=provider)
    assert result["source"] == "rules"
    assert "synthetic-secret" not in capsys.readouterr().out + caplog.text + repr(result)


def test_limits_and_invalid_dates_are_normalized_before_provider():
    payload = guidance_payload({"title": "x" * 200, "apply_start": "2026-02-30", "apply_end": "not-a-date"}, [], "x" * 20_000)
    assert len(payload["title"]) == 100 and len(payload["notice_text"]) == 16_000
    assert payload["apply_start"] == payload["apply_end"] == ""
