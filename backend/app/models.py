"""Pydantic request/response models for the /scan endpoint."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    url: str


class LeadRequest(BaseModel):
    email: str = Field(max_length=254)
    scanned_url: str = Field(max_length=2000)
    score: int | None = None
    # Top issue titles from the scan the lead was submitted against, so a
    # human following up has something concrete to reference instead of
    # having to re-scan the page themselves. Client-supplied and therefore
    # untrusted -- record_lead caps both list length and per-item length
    # again server-side regardless of what's sent here.
    top_issues: list[str] = Field(default_factory=list, max_length=10)


class Bbox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class IssueNode(BaseModel):
    html: str = Field(max_length=2000)
    target: list[str] = Field(max_length=20)
    failure_summary: str | None = Field(default=None, max_length=2000)
    bbox: Bbox | None = None
    # True if this element only failed at the 320px mobile-width axe pass,
    # not at desktop width (see scanner._run_mobile_axe_pass).
    mobile_only: bool = False


class Issue(BaseModel):
    id: str
    impact: str
    wcag_criterion: str | None = None
    tags: list[str] = Field(max_length=30)
    description: str = Field(max_length=2000)
    help: str = Field(max_length=2000)
    help_url: str
    node_count: int
    # A real scan caps this at 5 (see scanner._MAX_NODES_PER_ISSUE); the export
    # endpoints accept a client-supplied ScanResult though, so this bounds how
    # large a fabricated payload's per-issue node list can be.
    nodes: list[IssueNode] = Field(max_length=50)


class PassItem(BaseModel):
    id: str
    wcag_criterion: str | None = None
    tags: list[str] = Field(max_length=30)
    description: str = Field(max_length=2000)
    help: str = Field(max_length=2000)
    help_url: str
    node_count: int


class ConformanceRow(BaseModel):
    criterion: str
    status: str  # "supports" | "does_not_support" | "needs_review" | "not_applicable"
    passed_rules: list[str] = Field(max_length=100)
    failed_rules: list[str] = Field(max_length=100)
    review_rules: list[str] = Field(max_length=100)
    na_rules: list[str] = Field(default_factory=list, max_length=100)


class VpatRow(BaseModel):
    num: str  # e.g. "1.4.3"
    title: str  # e.g. "Contrast (Minimum)"
    level: str  # "A" | "AA"
    conformance: str  # "Supports" | "Partially Supports" | "Does Not Support" | "Not Evaluated"
    remarks: str = Field(max_length=2000)


class AiFinding(BaseModel):
    criterion: str  # "1.1.1" | "2.4.4" | "2.4.6" -- see ai_page_review.py
    verdict: str  # "ok" | "concern"
    subject: str = Field(max_length=500)
    detail: str = Field(max_length=1000)


class AiReview(BaseModel):
    """Optional, opt-in (AI_PAGE_REVIEW=on) AI-assisted judgment on criteria
    axe-core can only check mechanically -- see ai_page_review.py. This is
    NEVER a conformance determination and never changes the VpatRow entries
    above; it's a separate, clearly-disclosed layer."""
    summary: str = Field(max_length=500)
    findings: list[AiFinding] = Field(default_factory=list, max_length=60)
    model: str
    input_tokens: int = Field(alias="inputTokens", default=0)
    output_tokens: int = Field(alias="outputTokens", default=0)
    disclaimer: str = Field(max_length=500)

    model_config = {"populate_by_name": True}


class ScanResult(BaseModel):
    url: str
    final_url: str
    page_title: str
    scanned_at: datetime
    score: int
    counts: dict[str, int] = Field(default_factory=dict)
    # Bounds are generous relative to what a real scan produces (see
    # scanner.py) -- they exist to cap how large a client-supplied payload to
    # /vpat or /issues.csv can be, not to constrain normal /scan output.
    issues: list[Issue] = Field(max_length=500)
    passes: list[PassItem] = Field(max_length=500)
    conformance: list[ConformanceRow] = Field(max_length=300)
    vpat: list[VpatRow] = Field(default_factory=list, max_length=300)
    vpat_summary: dict[str, int] = Field(default_factory=dict)
    incomplete_count: int
    scan_duration_ms: int
    screenshot: str | None = Field(default=None, max_length=15_000_000)
    # Optional, opt-in AI-assisted judgment (see ai_page_review.py). None
    # when disabled/unconfigured/unavailable -- never affects vpat/conformance.
    ai_review: AiReview | None = None
