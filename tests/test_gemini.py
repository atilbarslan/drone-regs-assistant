"""The Gemini adapter's pure parts: prompt formats and error mapping. No network."""

from google.genai import errors

from app.gemini import classify_error, document_prompt, query_prompt
from app.providers import Document, RateLimited, TransientError


def quota_error(quota_id: str, retry_delay: str | None = "5s") -> errors.APIError:
    details = [
        {
            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
            "violations": [{"quotaId": quota_id, "quotaValue": "100"}],
        }
    ]
    if retry_delay:
        details.append(
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay}
        )
    body = {
        "error": {
            "code": 429,
            "message": "quota exceeded",
            "status": "RESOURCE_EXHAUSTED",
            "details": details,
        }
    }
    return errors.APIError(429, body)


def test_prompts_follow_the_retrieval_format():
    assert document_prompt(Document("Madde 12 Bölgeler", "Metin")) == (
        "title: Madde 12 Bölgeler | text: Metin"
    )
    assert document_prompt(Document("", "Text")) == "title: none | text: Text"
    assert query_prompt("Where can I fly?") == "task: search result | query: Where can I fly?"


def test_per_minute_quota_is_retryable_with_delay():
    # Shape of the 429 the API returned in a real test on 2026-10-06.
    error = classify_error(
        quota_error("EmbedContentRequestsPerMinutePerUserPerProjectPerModel-FreeTier", "5s")
    )

    assert isinstance(error, RateLimited)
    assert (error.daily, error.retry_after) == (False, 5.0)


def test_per_day_quota_is_daily():
    # Not observed yet: the daily quota id is assumed to name "PerDay" the way the per-minute
    # one names "PerMinute". If it does not, the run still stops once retries are used up.
    error = classify_error(
        quota_error("EmbedContentRequestsPerDayPerUserPerProjectPerModel-FreeTier")
    )

    assert isinstance(error, RateLimited)
    assert error.daily


def test_server_errors_are_transient_and_others_pass_through():
    unavailable = errors.APIError(503, {"error": {"code": 503, "status": "UNAVAILABLE"}})
    bad_request = errors.APIError(400, {"error": {"code": 400, "status": "INVALID_ARGUMENT"}})

    assert isinstance(classify_error(unavailable), TransientError)
    assert classify_error(bad_request) is bad_request
