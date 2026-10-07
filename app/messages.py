"""User-facing texts in Turkish and English: limits, provider errors and refusals.

Which jurisdiction an answer follows is no longer written into the answer: the API returns it
as structured fields (mode, detected) and the page shows it."""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.limits import Refusal

TURKEY = ZoneInfo("Europe/Istanbul")


def _reset_time(resets_at: datetime, lang: str) -> str:
    if lang == "tr":
        return f"{resets_at.astimezone(TURKEY):%d.%m.%Y %H:%M} (Türkiye saati)"
    return f"{resets_at:%Y-%m-%d %H:%M} UTC"


def limit_message(refusal: Refusal, lang: str) -> str:
    n, wait = refusal.limit, refusal.retry_after
    reset = _reset_time(refusal.resets_at, lang) if refusal.resets_at else ""
    texts = {
        "ip_minute": (
            f"Çok hızlı soru gönderiyorsunuz: dakikada en fazla {n} soru sorulabilir. "
            f"{wait} saniye sonra tekrar deneyin.",
            f"Too many questions: at most {n} per minute. Please try again in {wait} seconds.",
        ),
        "global_minute": (
            f"Şu anda çok fazla soru geliyor (bu demo için dakikada en fazla {n}). "
            f"{wait} saniye sonra tekrar deneyin.",
            f"The demo is receiving too many questions right now (at most {n} per minute). "
            f"Please try again in {wait} seconds.",
        ),
        "ip_day": (
            f"Bugünkü soru hakkınız doldu (günde {n} soru). Sınır {reset} itibarıyla sıfırlanır.",
            f"You have used today's {n} questions. The limit resets at {reset}.",
        ),
        "global_day": (
            f"Bu demo bugünkü toplam soru sınırına ulaştı (günde {n} soru). "
            f"Sınır {reset} itibarıyla sıfırlanır.",
            f"The demo has reached today's limit of {n} questions in total. It resets at {reset}.",
        ),
    }
    tr, en = texts[refusal.scope]
    return tr if lang == "tr" else en


def provider_quota_message(daily: bool, resets_at: datetime, lang: str) -> str:
    if daily:
        reset = _reset_time(resets_at, lang)
        if lang == "tr":
            return f"Yapay zekâ servisinin günlük kotası doldu. {reset} itibarıyla tekrar deneyin."
        return f"The AI service's daily quota is used up. Please try again after {reset}."
    if lang == "tr":
        return "Yapay zekâ servisi şu anda yoğun. Lütfen bir dakika sonra tekrar deneyin."
    return "The AI service is busy right now. Please try again in a minute."


def provider_error_message(lang: str) -> str:
    if lang == "tr":
        return "Yapay zekâ servisinde geçici bir sorun oluştu. Lütfen tekrar deneyin."
    return "The AI service had a temporary problem. Please try again."


def not_configured_message(lang: str) -> str:
    if lang == "tr":
        return "Soru-cevap servisi şu anda yapılandırılmamış."
    return "The question service is not configured right now."


def no_passages_message(lang: str) -> str:
    if lang == "tr":
        return "Kaynaklarda bu soruyla ilgili bir bölüm bulunamadı."
    return "No relevant section was found in the sources."


def uncited_message(lang: str) -> str:
    if lang == "tr":
        return (
            "Üretilen cevap kaynaklardaki bölümlere dayandırılamadığı için gösterilmiyor. "
            "Soruyu daha açık sormayı deneyebilirsiniz."
        )
    return (
        "The generated answer could not be tied to any section of the sources, so it is not "
        "shown. You could try asking more specifically."
    )
