"""
LLM-based structured extraction of qualitative filing content.
"""

from __future__ import annotations

# from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from stock_news.processing.edgar.routing.classifier import FilingClassification

# DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_MODEL = "gemini-3.5-flash-lite"


class ExtractedFilingSignal(BaseModel):
    """
    Structured qualitative content pulled from a filing's relevant
    section(s). Fields are optional/empty-list because not every filing
    touches on every field.
    """

    guidance_commentary: str = Field(
        default="",
        description=(
            "Forward-looking guidance mentioned: revenue/margin targets, "
            "capacity or capex plans, demand outlook. Empty string if none."
        ),
    )
    segment_commentary: str = Field(
        default="",
        description=(
            "Commentary on specific business segments or product lines "
            "(e.g. data center vs. gaming, foundry vs. IP licensing). "
            "Empty string if the filing doesn't break out segments."
        ),
    )
    executive_quote_summary: str = Field(
        default="",
        description=(
            "A brief, paraphrased (not verbatim-quoted) summary of any "
            "executive commentary on strategy, demand drivers, or "
            "competitive position. Empty string if none."
        ),
    )
    mentioned_customers: list[str] = Field(
        default_factory=list,
        description="Company names mentioned as customers, if any.",
    )
    mentioned_competitors: list[str] = Field(
        default_factory=list,
        description="Company names mentioned as competitors, if any.",
    )


_EXTRACTION_INSTRUCTIONS = """
You are extracting structured signals from a section of a US public
company's SEC filing. Only report what is actually stated in the text -
do not infer, estimate, or fill in plausible-sounding values. Paraphrase
any executive commentary in your own words rather than quoting it verbatim.
Leave fields empty (not guessed) if the text doesn't address them.

For mentioned_customers and mentioned_competitors: classify each named
company by the specific relationship the text describes, not by proximity
to other company names in the same sentence or paragraph. A company that
purchases, deploys, or uses the filer's products is a customer. A company
described as a rival, or as creating competitive pressure, in a similar
market is a competitor. A company must not appear in both lists unless the
text explicitly describes it in both roles - do not default to including
a company in mentioned_competitors just because other companies nearby
were identified as competitors.
""".strip()


def extract_filing_signal(
    classification: FilingClassification,
    model_name: str = DEFAULT_MODEL,
) -> ExtractedFilingSignal | None:
    """
    Run LLM structured extraction over a classified filing's relevant
    sections.

    Returns None without making any API call if classification.should_extract
    is False - low-signal filings (e.g. routine 8-K items, or a 10-Q/10-K
    where no target section was found).
    """
    if not classification.should_extract:
        return None

    combined_text = "\n\n".join(
        f"[{section_name}]\n{text}"
        for section_name, text in classification.sections.items()
    )

    # model = ChatGroq(model=model_name, temperature=0)
    model = ChatGoogleGenerativeAI(model=model_name, temperature=0)
    structured_model = model.with_structured_output(ExtractedFilingSignal)

    return structured_model.invoke(f"{_EXTRACTION_INSTRUCTIONS}\n\n{combined_text}")
