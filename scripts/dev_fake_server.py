"""Try the page without a Gemini API key: a local server whose answers are FAKE.

    python -m scripts.dev_fake_server [port]      (from the repository root; default port 8770)

Every answer this server gives is made up. It is written in code below to look like the
approved designs (notes/design/2-Answer.html, 3-Compare.html), so the page can be built and
checked without spending the Gemini free-tier quota. It is not about the question asked and
it is not legal information. Never deploy it.

- No Gemini key is read and no Gemini client is created: the app gets a fake embedder and a
  fake model (create_app only builds Gemini clients when neither is given).
- Retrieval is real: it runs on the development database (DATABASE_URL, as for the app), with
  bag-of-words query vectors compared against the stored embeddings. The passages are real but
  arbitrary, and the fake answers cite their numbers, on the right side in a comparison.
- request_log rows are still written, with generation_model = "fake-design-llm", so they can be
  told apart and removed:  DELETE FROM request_log WHERE generation_model = 'fake-design-llm'
- FAKE_DELAY (seconds, default 1.2) delays each answer, to see the loading state. The request
  limits (ASK_IP_PER_MINUTE, ...) apply as in the app.
"""

import asyncio
import os
import re
import sys

import uvicorn

from app.config import Settings
from app.main import create_app
from app.providers import Generation
from tests.fakes import FakeEmbedder

FAKE_MODEL = "fake-design-llm"


class StoredModelNameEmbedder(FakeEmbedder):
    """Bag-of-words vectors under the stored model's name, so the search finds the chunks."""

    def __init__(self, model: str):
        super().__init__()
        self.model = model


def pick(numbers: list[int], i: int) -> list[int]:
    return [numbers[i % len(numbers)]] if numbers else []


def section(topic, text, citations, cases=()):
    return {"topic": topic, "text": text, "citations": citations, "cases": list(cases)}


def case(condition, verdict, text, citations):
    return {"condition": condition, "verdict": verdict, "text": text, "citations": citations}


CAMERA = {
    "en": {
        "question": "Camera or other sensor?",
        "options": [
            {"label": "Has a camera", "fact": "The drone has a camera or another sensor."},
            {"label": "No camera", "fact": "The drone has no camera or other sensor."},
        ],
    },
    "tr": {
        "question": "Kamera ya da başka bir sensör var mı?",
        "options": [
            {"label": "Kamera var", "fact": "Dronda kamera ya da başka bir sensör var."},
            {"label": "Kamera yok", "fact": "Dronda kamera ya da başka bir sensör yok."},
        ],
    },
}
CLASS_LABEL = {
    "question": "Class label on the drone?",
    "options": [
        {"label": "C0", "fact": "The drone carries a C0 class label."},
        {"label": "C1", "fact": "The drone carries a C1 class label."},
        {"label": "Privately built", "fact": "The drone is privately built."},
    ],
}


def eu_answer(lang: str, eu: list[int], facts: list[str]) -> dict:
    camera = any("has a camera" in f or "sensör var" in f for f in facts)
    no_camera = any("has no camera" in f or "sensör yok" in f for f in facts)
    if camera or no_camera:
        text = (
            "Register: the 250 g threshold does not apply to drones that can capture personal "
            "data, unless it is a toy."
            if camera
            else "Not required: under 250 g and unable to transfer more than 80 J on impact."
        )
        registration = section("Registration", text, pick(eu, 0))
    else:
        registration = section(
            "Registration",
            None,
            pick(eu, 0),
            [
                case(
                    "With a camera",
                    "REGISTER",
                    "The 250 g threshold does not apply to drones that can capture personal "
                    "data — unless it is a toy.",
                    pick(eu, 0),
                ),
                case(
                    "Without a camera",
                    "NOT REQUIRED",
                    "Under 250 g and unable to transfer more than 80 J on impact.",
                    pick(eu, 0),
                ),
            ],
        )
    depends_on = [] if camera or no_camera else [CAMERA[lang]]
    if not any("class label" in f or "privately built" in f for f in facts):
        depends_on.append(CLASS_LABEL)
    return {
        "answerable": True,
        "depends_on": depends_on,
        "sections": [
            section(
                "Category",
                "Open category, subcategory A1 — if the drone carries a C0 label or is privately "
                "built (under 250 g and under 19 m/s).",
                pick(eu, 1),
            ),
            registration,
            section(
                "Training",
                "No online course or exam for a C0 or privately built drone under 250 g — you "
                "must know the manufacturer’s instructions. The online course and 40-question "
                "exam start at class C1.",
                pick(eu, 1),
            ),
            section(
                "Where you can fly",
                "You may fly over uninvolved people, but never over assemblies of people. Stay "
                "within 120 m of the closest point of the surface.",
                pick(eu, 1) + pick(eu, 2),
            ),
            section(
                "Pilot age",
                "16 in general. No minimum age for a C0 toy in A1 or a privately built drone "
                "under 250 g.",
                pick(eu, 3),
            ),
        ],
        "not_in_sources": [
            "Germany’s own geographical zones and insurance rules. Each member state publishes "
            "its zones; check the national authority before flying."
        ],
        "follow_ups": ["I want to fly commercially", "Can I fly at night?"],
    }


def tr_answer(question: str, tr: list[int]) -> dict:
    if re.search(r"sigorta|insurance", question, re.IGNORECASE):
        # A refusal, to see that state and the "same question for the EU" button.
        return {
            "answerable": False,
            "not_in_sources": [
                "SHT-İHA metninde ticari faaliyetler için sigorta zorunluluğuna dair bir hüküm yok."
            ],
            "follow_ups": ["Ticari operasyon için hangi lisans gerekir?"],
        }
    return {
        "answerable": True,
        "depends_on": [
            {
                "question": "Dron Basit İHA mı?",
                "options": [
                    {
                        "label": "Basit İHA",
                        "fact": "Dron, 10 m yarıçap ve 20 m yükseklik zarfını aşamayan bir "
                        "Basit İHA.",
                    },
                    {"label": "Basit İHA değil", "fact": "Dron Basit İHA değil."},
                ],
            }
        ],
        "sections": [
            section(
                "Kayıt",
                None,
                pick(tr, 0) + pick(tr, 1),
                [
                    case(
                        "Basit İHA",
                        "MUAF",
                        "Basit İHA tanımına uyan araçlar kayıt ve lisans yükümlülüklerinden "
                        "muaftır.",
                        pick(tr, 0),
                    ),
                    case(
                        "Basit İHA değil",
                        "KAYIT GEREKİR",
                        "Kullanıcı İHATTYS üzerinden kayıt yaptırır; yükümlülük edinme "
                        "tarihinden doğar.",
                        pick(tr, 1),
                    ),
                ],
            ),
            section(
                "Pilot lisansı",
                "Hobi uçuşları için P0, ticari uçuşlar için P1 gerekir; diploma lisansı tek "
                "başına yetmez, operasyonel lisans şarttır.",
                pick(tr, 2),
            ),
            section(
                "Uçuş bölgesi",
                "Kırmızı bölgede uçuş izne tabidir; yeşil bölgede izin gerekmez.",
                pick(tr, 3),
            ),
        ],
        "not_in_sources": ["Satın alma ve devir işlemlerine dair özel usuller."],
        "follow_ups": ["P0 lisansı nasıl alınır?", "Kırmızı bölge izni nereden alınır?"],
    }


COMPARE_ROWS = [
    (
        "Class / category",
        "“Basit İHA” only if it cannot leave a 10 m radius / 20 m height envelope; otherwise "
        "M0 rules apply even under 500 g.",
        "Subcategory A1 if C0-labelled or privately built under 250 g.",
    ),
    (
        "Pilot licence",
        "P0 (hobby) or P1 (commercial), whatever the drone’s class. A diploma licence alone "
        "does not allow flying — an operational licence is required.",
        "No online exam for C0 / under 250 g; know the manufacturer’s instructions.",
    ),
    (
        "Registration",
        "Every user except a Basit İHA registers through İHATTYS.",
        "Required — the camera can capture personal data, unless the drone is a toy.",
    ),
    (
        "Minimum age",
        "P0: 10 · P1 and P2: 18.",
        "16; none for a C0 toy in A1 or a privately built drone under 250 g.",
    ),
    (
        "Maximum height",
        "120 m and 3,000 m horizontal for P0 / P1, always within visual line of sight.",
        "120 m from the closest point of the surface.",
    ),
    (
        "Using the other side’s certificate",
        "Foreign licences can be recognised under international agreements, then a difference "
        "course gives the matching P1 or P2.",
        None,  # an empty cell, to see that state
    ),
]


def compare_answer(tr: list[int], eu: list[int]) -> dict:
    rows = []
    for i, (topic, tr_text, eu_text) in enumerate(COMPARE_ROWS):
        rows.append(
            {
                "topic": topic,
                "TR": {"text": tr_text, "citations": pick(tr, i)} if tr_text else None,
                "EU": {"text": eu_text, "citations": pick(eu, i)} if eu_text else None,
            }
        )
    return {
        "answerable": True,
        "compare": {
            "key_differences": [
                "Türkiye sets the rules by pilot licence level and airspace zone; the EU by "
                "operating subcategory and the drone’s class label.",
                "Light is not automatically exempt in Türkiye: only a “Basit İHA” that cannot "
                "leave a 10 m × 20 m envelope is.",
                "Neither side automatically accepts the other’s pilot certificate.",
            ],
            "rows": rows,
        },
        "not_in_sources": [
            "No recognition of Turkish certificates under Article 41(3) appears in the sources."
        ],
        "follow_ups": ["Registration rules for a 250 g drone"],
    }


class FakeDesignLLM:
    """Returns one of three fixed answers, chosen from the mode in the system prompt."""

    model = FAKE_MODEL

    async def generate(self, system: str, prompt: str, schema) -> Generation:
        await asyncio.sleep(float(os.environ.get("FAKE_DELAY", "1.2")))
        given = re.findall(r"^\[(\d+)\] (Türkiye|European Union) \|", prompt, re.MULTILINE)
        tr = [int(n) for n, side in given if side == "Türkiye"]
        eu = [int(n) for n, side in given if side == "European Union"]
        question = prompt.rsplit("Question: ", 1)[-1]
        lang = "tr" if "Write every text in Turkish" in system else "en"
        facts = []
        if "The user has confirmed these facts" in system:
            confirmed = system.split("The user has confirmed these facts", 1)[1]
            facts = re.findall(r"^- (.+)$", confirmed, re.MULTILINE)
        if "Compare Türkiye and the EU" in system:
            data = compare_answer(tr, eu)
        elif "Answer for Türkiye" in system:
            data = tr_answer(question, tr)
        else:
            data = eu_answer(lang, eu, facts)
        return Generation(
            data=data, prompt_tokens=len(prompt.split()), output_tokens=0, thinking_tokens=None
        )


def build_app(settings: Settings | None = None):
    settings = settings or Settings(gemini_api_key=None)  # never read or use a key
    embedder = StoredModelNameEmbedder(settings.gemini_embedding_model)
    return create_app(settings, embedder=embedder, llm=FakeDesignLLM())


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8770
    print(f"FAKE answers (no Gemini) on http://127.0.0.1:{port}", flush=True)
    uvicorn.run(build_app(), host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
