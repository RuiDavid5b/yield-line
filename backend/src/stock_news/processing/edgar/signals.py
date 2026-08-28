"""
LLM-based structured extraction of qualitative filing content.
"""

from __future__ import annotations

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from stock_news.processing.edgar.routing.classifier import FilingClassification
from stock_news.storage.rate_limiter import acquire_gemini_call

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
            "Explicit forward-looking statements about the company's expected "
            "future performance or planned actions. Include revenue, margin, "
            "demand, capacity, capex, investment, hiring, cost, production, "
            "or other business outlooks and plans. Do not infer guidance from "
            "historical results or general industry trends. Empty string if "
            "no explicit forward-looking company commentary is present."
        ),
    )
    segment_commentary: str = Field(
        default="",
        description=(
            "Explicit commentary about the company's business segments, end "
            "markets, products, or industry conditions affecting its business. "
            "Include demand trends, growth drivers, technology adoption, "
            "cyclicality, market conditions, and factors driving or weakening "
            "demand in areas such as data centers, AI, automotive, mobile, "
            "industrial, or other end markets. This does not require the filing "
            "to formally name a segment. Empty string only if the text contains "
            "no relevant business or market commentary."
        ),
    )
    executive_quote_summary: str = Field(
        default="",
        description=(
            "A brief paraphrased summary of explicit commentary attributed to "
            "an executive or company management, especially statements about "
            "strategy, demand, market conditions, competitive position, or "
            "future plans. Do not quote verbatim. Do not invent executive "
            "opinions from statements that are not attributed to management. "
            "Empty string if no such commentary is present."
        ),
    )
    mentioned_customers: list[str] = Field(
        default_factory=list,
        description=(
            "Distinct company names explicitly identified as customers, "
            "including companies described as purchasing, using, deploying, "
            "or receiving the company's products or services. Do not include "
            "a company merely because it is mentioned near a customer. "
            "Deduplicate companies and use one canonical company name when "
            "multiple legal entities or subsidiaries of the same company are "
            "mentioned."
        ),
    )
    mentioned_competitors: list[str] = Field(
        default_factory=list,
        description=(
            "Distinct company names explicitly identified as competitors, "
            "rivals, or sources of competitive pressure. Do not include a "
            "company merely because it operates in the same industry or is "
            "mentioned near competitors. Deduplicate companies and use one "
            "canonical company name when multiple legal entities or "
            "subsidiaries of the same company are mentioned."
        ),
    )


_EXTRACTION_INSTRUCTIONS = """
Extract structured qualitative signals from the provided SEC filing text.
The filing company is: {company_name}

GENERAL RULES:
- Extract only information explicitly stated in the text.
- Do not infer, speculate, or use outside knowledge.
- Prefer concrete, filing-specific statements over generic descriptions of
  the company's business.
- A field should be populated whenever the text contains relevant information
  for that field. Do not leave a field empty merely because the information
  is not presented in exactly the form described by the field name.
- Paraphrase rather than quoting the filing verbatim.
- Keep each field concise and focused on the information relevant to that
  field.
- The same passage may support more than one field when it contains distinct
  relevant information.

FIELD-SPECIFIC RULES:
- guidance_commentary: capture forward-looking statements about expected
  demand, revenue, margins, capacity, capital expenditures, investments,
  production plans, or other future business conditions.
- segment_commentary: capture commentary about specific business segments,
  end markets, products, technologies, or customer markets, including
  changes in demand or performance affecting them.
- executive_quote_summary: capture substantive management commentary about
  strategy, business conditions, demand drivers, opportunities, risks, or
  competitive position. Do not require the text to be a literal quotation
  from an executive.
- mentioned_customers: include named companies only when the text explicitly
  identifies them as customers or describes them purchasing, using, or
  deploying the company's products or services.
- mentioned_competitors: include named companies only when the text explicitly
  identifies them as competitors, rivals, or sources of competitive pressure.

CUSTOMERS AND COMPETITORS:
- Classify each company according to the specific relationship described in
  the text, not merely because it appears near other companies.
- Do not infer a customer or competitor relationship from general industry
  knowledge.
- Do not put the same company in both lists unless the text explicitly
  describes it in both roles.
- If multiple names refer to the same underlying company, return only one
  normalized company name rather than repeating the company under different
  legal or subsidiary names.
""".strip()


def extract_filing_signal(
    classification: FilingClassification,
    company_name: str,
    model_name: str = DEFAULT_MODEL,
) -> ExtractedFilingSignal | None:
    """
    Run LLM structured extraction over a classified filing's relevant
    sections.

    Returns None without making any API call if classification.should_extract
    is False - low-signal filings (e.g. routine 8-K items, or a 10-Q/10-K
    where no target section was found).
    """
    acquire_gemini_call()

    if not classification.should_extract:
        return None

    combined_text = "\n\n".join(
        f"[{section_name}]\n{text}"
        for section_name, text in classification.sections.items()
    )

    instructions = _EXTRACTION_INSTRUCTIONS.format(
        company_name=company_name,
    )

    model = ChatGoogleGenerativeAI(model=model_name)
    structured_model = model.with_structured_output(ExtractedFilingSignal)

    return structured_model.invoke(f"{instructions}\n\n{combined_text}")
