"""Pydantic request/response models for the /scan endpoint."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    url: str


class Bbox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class IssueNode(BaseModel):
    html: str
    target: list[str]
    failure_summary: str | None = None
    bbox: Bbox | None = None


class Issue(BaseModel):
    id: str
    impact: str
    wcag_criterion: str | None = None
    tags: list[str]
    description: str
    help: str
    help_url: str
    node_count: int
    nodes: list[IssueNode]


class PassItem(BaseModel):
    id: str
    wcag_criterion: str | None = None
    tags: list[str]
    description: str
    help: str
    help_url: str
    node_count: int


class ConformanceRow(BaseModel):
    criterion: str
    status: str  # "supports" | "does_not_support" | "needs_review"
    passed_rules: list[str]
    failed_rules: list[str]
    review_rules: list[str]


class ScanResult(BaseModel):
    url: str
    final_url: str
    page_title: str
    scanned_at: datetime
    score: int
    counts: dict[str, int] = Field(default_factory=dict)
    issues: list[Issue]
    passes: list[PassItem]
    conformance: list[ConformanceRow]
    incomplete_count: int
    scan_duration_ms: int
    screenshot: str | None = None
