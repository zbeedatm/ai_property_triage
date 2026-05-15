"""
Guardrails Service
------------------
POST /check/input   — validate that a submission is a genuine property listing
POST /check/output  — audit an AI-generated report (fabrication, listing-data doubt, or failed tools)

Both endpoints return a unified CheckResult schema so downstream callers
(n8n nodes) have a consistent interface.

Uses Google Gemini for classification via the action functions defined in
actions.py. The NeMo Guardrails flow engine is kept for config/structure
but classification is called directly for reliability.
"""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dotenv import load_dotenv
load_dotenv()

from actions import _classify, _INPUT_VALIDATION_PROMPT, _INJECTION_DETECTION_PROMPT, _OUTPUT_AUDIT_PROMPT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Property Guardrails Service",
    description="Input validation and output auditing for the property triage pipeline.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class InputCheckRequest(BaseModel):
    text: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "3-bedroom apartment in Tel Aviv, 110sqm, renovated kitchen, asking 4.2M ILS"
            }
        }
    }


class OutputCheckRequest(BaseModel):
    report: str
    original_listing: str | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "report": "This property is certified energy rating A and guarantees 8% ROI.",
                "original_listing": "3-bedroom apartment in Tel Aviv..."
            }
        }
    }


class CheckResult(BaseModel):
    passed: bool
    reason: str | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "rails": ["input_validation", "injection_detection", "output_audit"]}


@app.post("/check/input", response_model=CheckResult)
async def check_input(request: InputCheckRequest):
    """
    Validates that the submitted text is a genuine property listing
    and contains no prompt injection attempts.
    Returns passed=True if both rails clear.
    """
    if not request.text.strip():
        return CheckResult(passed=False, reason="Empty submission")

    try:
        is_listing = await _classify(_INPUT_VALIDATION_PROMPT, request.text)
        logger.info("check_is_property_listing → %s | input: %.80r", is_listing, request.text)

        if not is_listing:
            return CheckResult(
                passed=False,
                reason="This submission does not appear to be a genuine property listing. "
                       "Please provide a valid listing with details such as property type, "
                       "location, size, and features.",
            )

        is_injection = await _classify(_INJECTION_DETECTION_PROMPT, request.text)
        logger.info("check_prompt_injection → %s | input: %.80r", is_injection, request.text)

        if is_injection:
            return CheckResult(
                passed=False,
                reason="Your submission contains content that cannot be processed. "
                       "Please submit a genuine property listing only.",
            )

        return CheckResult(passed=True)

    except Exception as exc:
        logger.exception("Input rail check failed")
        raise HTTPException(status_code=502, detail=f"Guardrail LLM error: {exc}")


@app.post("/check/output", response_model=CheckResult)
async def check_output(request: OutputCheckRequest):
    """
    Audits an AI-generated property report. Returns passed=False when the report
    should be held for human review: fabricated/unverifiable claims, explicit doubt
    that user-submitted core facts (e.g. price) are accurate, or material tool failures.
    """
    if not request.report.strip():
        return CheckResult(passed=False, reason="Empty report")

    try:
        listing = (request.original_listing or "").strip()
        audit_payload = (
            "ORIGINAL LISTING:\n"
            + (listing if listing else "[not provided]")
            + "\n\nAI REPORT:\n"
            + request.report.strip()
        )
        block_for_review = await _classify(_OUTPUT_AUDIT_PROMPT, audit_payload)
        logger.info(
            "check_output_audit → %s | listing_len=%s output: %.80r",
            block_for_review,
            len(listing),
            request.report,
        )

        if block_for_review:
            return CheckResult(
                passed=False,
                reason=(
                    "Output audit failed: fabricated/unverifiable claims, "
                    "material doubt about submitted listing accuracy, "
                    "or critical analysis steps did not complete — human review required."
                ),
            )

        return CheckResult(passed=True)

    except Exception as exc:
        logger.exception("Output rail check failed")
        raise HTTPException(status_code=502, detail=f"Guardrail LLM error: {exc}")
