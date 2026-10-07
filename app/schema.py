"""The structured answer the model must return (Gemini structured output), as Pydantic models.

The same models describe the cleaned answer the API returns: the server drops citations of
passages that were not given, and any part that is left without a citation.

List limits are given to the model as JSON schema hints (json_schema_extra) rather than as
Pydantic constraints, so a reply that exceeds one is trimmed by the server, not rejected.
"""

from pydantic import BaseModel, Field

# Every part of an answer must cite at least one passage. A hint for the model, like the
# limits below; a part left without a valid citation is dropped by the server.
CITED = {"minItems": 1}


class Option(BaseModel):
    label: str = Field(description="Short choice shown to the user, e.g. 'Has a camera'.")
    fact: str = Field(
        description="The same choice as a statement the user confirms, e.g. "
        "'The drone has a camera'."
    )


class DependsOn(BaseModel):
    question: str = Field(description="What the answer depends on, e.g. 'Camera or sensor?'.")
    options: list[Option] = Field(json_schema_extra={"minItems": 2, "maxItems": 4})


class Case(BaseModel):
    condition: str = Field(description="The situation, e.g. 'With a camera'.")
    verdict: str = Field(description="One to three words, e.g. 'REGISTER' or 'NOT REQUIRED'.")
    text: str
    citations: list[int] = Field(
        description="Numbers of the passages this case is based on.", json_schema_extra=CITED
    )


class Section(BaseModel):
    topic: str = Field(description="One to three words, e.g. 'Registration'.")
    text: str | None = Field(
        default=None, description="The rule for this topic; omit if cases are given."
    )
    cases: list[Case] = Field(
        default_factory=list,
        description="Use when the rule differs by a condition the question does not settle.",
    )
    # Required, also for a section given as cases: with a default, the field was optional in the
    # schema sent to Gemini, and a reply came back with no section citations at all.
    citations: list[int] = Field(
        description="Numbers of the passages the text (or, with cases, the cases) is based on.",
        json_schema_extra=CITED,
    )


class Side(BaseModel):
    text: str
    citations: list[int] = Field(
        description="Passage numbers from this side only.", json_schema_extra=CITED
    )


class CompareRow(BaseModel):
    topic: str
    TR: Side | None = Field(default=None, description="Türkiye; null if no Turkish passage.")
    EU: Side | None = Field(default=None, description="EU; null if no EU passage.")


class Compare(BaseModel):
    key_differences: list[str] = Field(json_schema_extra={"maxItems": 3})
    rows: list[CompareRow]


class StructuredAnswer(BaseModel):
    answerable: bool = Field(
        description="False only if the passages contain nothing related to the question."
    )
    depends_on: list[DependsOn] = Field(
        default_factory=list,
        json_schema_extra={"maxItems": 3},
        description="Facts the question does not give but the answer depends on.",
    )
    sections: list[Section] = Field(default_factory=list, json_schema_extra={"maxItems": 8})
    not_in_sources: list[str] = Field(
        default_factory=list,
        json_schema_extra={"maxItems": 5},
        description="What the user should know that the passages do not say.",
    )
    compare: Compare | None = Field(default=None, description="Only in compare mode.")
    follow_ups: list[str] = Field(
        default_factory=list,
        json_schema_extra={"maxItems": 3},
        description="Short follow-up questions.",
    )
