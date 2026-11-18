from __future__ import annotations

"""
Data models for post-call processing.

These dataclasses represent the structured output of a completed call:
transcript entries, action items, scorecard entries, and the full call record.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TranscriptEntry:
    """A single line in a call transcript."""
    timestamp: float
    speaker: str
    text: str
    is_partial: bool = False


@dataclass
class ActionItem:
    """A task or follow-up extracted from a call."""
    task: str
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    status: str = "open"


@dataclass
class ScorecardEntry:
    """Evaluation of a single objective for a call."""
    objective: str
    status: str  # "achieved", "partially", "missed"
    notes: Optional[str] = None


@dataclass
class CallRecord:
    """Complete record of a finished call."""
    id: str
    agent_name: str
    start_time: str
    end_time: Optional[str] = None
    duration: Optional[float] = None
    summary: Optional[str] = None
    status: str = "completed"
    transcript: list[TranscriptEntry] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)
    scorecard: list[ScorecardEntry] = field(default_factory=list)
    key_topics: list[str] = field(default_factory=list)
    sentiment: dict[str, str] = field(default_factory=dict)