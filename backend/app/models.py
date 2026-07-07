"""Pydantic request/response models for the /scan endpoint."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    url: str


class IssueNode(BaseModel):
    html: str
    target: list[str]
    failure_summary: str | None = None


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


class ScanResult(BaseModel):
    url: str
    final_url: str
    page_title: str
    scanned_at: datetime
    score: int
    counts: dict[str, int] = Field(default_factory=dict)
    issues: list[Issue]
    incomplete_count: int
    scan_duration_ms: int
