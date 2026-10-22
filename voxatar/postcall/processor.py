from __future__ import annotations

"""
Post-call processor.

Takes a completed call's conversation history and uses an LLM to generate:
- A summary
- Action items
- Key topics
- Per-speaker sentiment
- An objective scorecard (if objectives are defined)

Results are persisted to the CallDatabase and returned as a CallRecord.
"""

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

from voxatar.llm import Message
from voxatar.llm.ollama_adapter import OllamaLLM
from voxatar.postcall.models import (
    ActionItem,
    CallRecord,
    ScorecardEntry,
    TranscriptEntry,
)
from voxatar.storage.database import CallDatabase

logger = logging.getLogger(__name__)


class PostCallProcessor:
    """
    Orchestrates post-call analysis using an LLM and persists results.

    Usage::

        processor = PostCallProcessor(llm, database)
        record = await processor.process_call(
            call_id="abc-123",
            agent_name="Sales Agent",
            conversation_history=messages,
            objectives=["Qualify the lead", "Schedule a demo"],
            start_time=time.time(),
        )
    """

    def __init__(self, llm: OllamaLLM, database: CallDatabase) -> None:
        self.llm = llm
        self.database = database

    # ------------------------------------------------------------------ #
    #  Main entry point                                                  #
    # ------------------------------------------------------------------ #

    async def process_call(
        self,
        call_id: str,
        agent_name: str,
        conversation_history: list[Message],
        objectives: list[str],
        start_time: float,
    ) -> CallRecord:
        """
        Run full post-call analysis and save results.

        Args:
            call_id: Unique call identifier.
            agent_name: Name of the Voxatar agent.
            conversation_history: Full list of conversation messages.
            objectives: List of objective strings (may be empty).
            start_time: Unix timestamp of call start.

        Returns:
            A populated CallRecord.
        """
        logger.info("Starting post-call processing for call %s", call_id)

        # Build transcript entries from conversation history
        transcript = self._build_transcript(conversation_history, start_time)

        # Persist transcript entries
        for entry in transcript:
            self.database.save_transcript_entry(
                call_id=call_id,
                timestamp=entry.timestamp,
                speaker=entry.speaker,
                text=entry.text,
                is_partial=entry.is_partial,
            )

        # Prepare a plain-text version of the conversation for LLM prompts
        conversation_text = self._format_conversation_text(transcript)

        # Run LLM analyses concurrently-ish (sequential for simplicity in MVP)
        summary = await self._generate_summary(conversation_text)
        action_items = await self._extract_action_items(conversation_text)
        key_topics = await self._extract_key_topics(conversation_text)
        sentiment = await self._analyze_sentiment(conversation_text)

        scorecard: list[ScorecardEntry] = []
        objectives_met: list[str] = []
        if objectives:
            scorecard = await self._generate_scorecard(conversation_text, objectives)
            objectives_met = [
                e.objective for e in scorecard if e.status == "achieved"
            ]

        # Compute end time / duration
        end_time_dt = datetime.now(timezone.utc)
        end_time_iso = end_time_dt.isoformat()
        duration = max(0.0, end_time_dt.timestamp() - start_time)

        # Update the call record in the database
        self.database.update_call_end(
            call_id=call_id,
            end_time=end_time_iso,
            duration=duration,
            summary=summary,
            status="completed",
            objectives_met=objectives_met,
        )

        # Persist action items and scorecard
        self.database.save_action_items(
            call_id,
            [
                {
                    "task": ai.task,
                    "assignee": ai.assignee,
                    "due_date": ai.due_date,
                    "status": ai.status,
                }
                for ai in action_items
            ],
        )
        self.database.save_scorecard(
            call_id,
            [
                {
                    "objective": e.objective,
                    "status": e.status,
                    "notes": e.notes,
                }
                for e in scorecard
            ],
        )

        record = CallRecord(
            id=call_id,
            agent_name=agent_name,
            start_time=datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat(),
            end_time=end_time_iso,
            duration=duration,
            summary=summary,
            status="completed",
            transcript=transcript,
            action_items=action_items,
            scorecard=scorecard,
            key_topics=key_topics,
            sentiment=sentiment,
        )

        logger.info("Post-call processing complete for call %s", call_id)
        return record

    # ------------------------------------------------------------------ #
    #  Transcript building                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_transcript(
        conversation_history: list[Message],
        start_time: float,
    ) -> list[TranscriptEntry]:
        """
        Convert conversation Message objects into TranscriptEntry objects.

        Maps 'user' -> 'Caller' and 'assistant' -> agent label.
        """
        transcript: list[TranscriptEntry] = []
        for i, msg in enumerate(conversation_history):
            if msg.role == "system":
                continue
            speaker = "Caller" if msg.role == "user" else "Agent"
            # Approximate timestamp: stagger by 2 seconds per turn
            ts = start_time + (i * 2.0)
            transcript.append(
                TranscriptEntry(
                    timestamp=ts,
                    speaker=speaker,
                    text=msg.content,
                    is_partial=False,
                )
            )
        return transcript

    @staticmethod
    def _format_conversation_text(transcript: list[TranscriptEntry]) -> str:
        """Render transcript entries as a plain-text dialogue."""
        lines = []
        for entry in transcript:
            lines.append(f"{entry.speaker}: {entry.text}")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    #  LLM helpers                                                       #
    # ------------------------------------------------------------------ #

    async def _generate_summary(self, conversation_text: str) -> str:
        """Ask the LLM for a 2-3 paragraph summary."""
        prompt = (
            "Summarize this conversation in 2-3 paragraphs. "
            "Focus on the key points discussed, decisions made, and any outcomes.\n\n"
            f"Conversation:\n{conversation_text}"
        )
        messages = [Message(role="user", content=prompt)]
        try:
            response = await self.llm.generate(
                messages=messages,
                system_prompt="You are a professional call analyst.",
                temperature=0.3,
                max_tokens=500,
            )
            return response.strip()
        except Exception as e:
            logger.error("Summary generation failed: %s", e)
            return "Summary unavailable due to an error."

    async def _extract_action_items(self, conversation_text: str) -> list[ActionItem]:
        """Ask the LLM to extract action items as a JSON array."""
        prompt = (
            "Analyze the following conversation and extract action items.\n"
            "Return a JSON array where each item has:\n"
            '  "task": brief description of the task,\n'
            '  "assignee": who should do it (or null),\n'
            '  "due_date": due date in ISO format (or null),\n'
            '  "status": "open"\n\n'
            "Return ONLY the JSON array, no other text.\n\n"
            f"Conversation:\n{conversation_text}"
        )
        messages = [Message(role="user", content=prompt)]
        try:
            response = await self.llm.generate(
                messages=messages,
                system_prompt="You are a professional call analyst. Respond only with JSON.",
                temperature=0.2,
                max_tokens=800,
            )
            items_raw = self._parse_json_response(response)
            if not isinstance(items_raw, list):
                return []
            return [
                ActionItem(
                    task=item.get("task", ""),
                    assignee=item.get("assignee"),
                    due_date=item.get("due_date"),
                    status=item.get("status", "open"),
                )
                for item in items_raw
                if isinstance(item, dict)
            ]
        except Exception as e:
            logger.error("Action item extraction failed: %s", e)
            return []

    async def _extract_key_topics(self, conversation_text: str) -> list[str]:
        """Ask the LLM for key topics as bullet points."""
        prompt = (
            "Identify the key topics discussed in this conversation.\n"
            "Return a JSON array of strings, each a short topic label.\n"
            "Return ONLY the JSON array.\n\n"
            f"Conversation:\n{conversation_text}"
        )
        messages = [Message(role="user", content=prompt)]
        try:
            response = await self.llm.generate(
                messages=messages,
                system_prompt="You are a professional call analyst. Respond only with JSON.",
                temperature=0.2,
                max_tokens=300,
            )
            topics = self._parse_json_response(response)
            if isinstance(topics, list):
                return [str(t) for t in topics]
            return []
        except Exception as e:
            logger.error("Key topic extraction failed: %s", e)
            return []

    async def _analyze_sentiment(self, conversation_text: str) -> dict[str, str]:
        """Ask the LLM to classify sentiment per speaker."""
        prompt = (
            "Analyze the sentiment of each speaker in this conversation.\n"
            "Return a JSON object mapping each speaker to one of: "
            '"positive", "neutral", "negative".\n'
            "Return ONLY the JSON object.\n\n"
            f"Conversation:\n{conversation_text}"
        )
        messages = [Message(role="user", content=prompt)]
        try:
            response = await self.llm.generate(
                messages=messages,
                system_prompt="You are a sentiment analysis assistant. Respond only with JSON.",
                temperature=0.2,
                max_tokens=200,
            )
            result = self._parse_json_response(response)
            if isinstance(result, dict):
                return {str(k): str(v) for k, v in result.items()}
            return {}
        except Exception as e:
            logger.error("Sentiment analysis failed: %s", e)
            return {}

    async def _generate_scorecard(
        self,
        conversation_text: str,
        objectives: list[str],
    ) -> list[ScorecardEntry]:
        """Ask the LLM to evaluate each objective."""
        objectives_text = "\n".join(f"  {i+1}. {obj}" for i, obj in enumerate(objectives))
        prompt = (
            "Evaluate whether each objective was met in this conversation.\n"
            "Objectives:\n"
            f"{objectives_text}\n\n"
            "Return a JSON array where each item has:\n"
            '  "objective": the objective text,\n'
            '  "status": "achieved", "partially", or "missed",\n'
            '  "notes": brief explanation\n\n'
            "Return ONLY the JSON array.\n\n"
            f"Conversation:\n{conversation_text}"
        )
        messages = [Message(role="user", content=prompt)]
        try:
            response = await self.llm.generate(
                messages=messages,
                system_prompt="You are a professional call analyst. Respond only with JSON.",
                temperature=0.2,
                max_tokens=800,
            )
            entries_raw = self._parse_json_response(response)
            if not isinstance(entries_raw, list):
                return []
            return [
                ScorecardEntry(
                    objective=entry.get("objective", ""),
                    status=entry.get("status", "missed"),
                    notes=entry.get("notes"),
                )
                for entry in entries_raw
                if isinstance(entry, dict)
            ]
        except Exception as e:
            logger.error("Scorecard generation failed: %s", e)
            return []

    # ------------------------------------------------------------------ #
    #  JSON parsing                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_json_response(text: str) -> object | None:
        """
        Parse an LLM JSON response, stripping markdown code fences.

        Returns the parsed JSON object or None on failure.
        """
        # Strip markdown code fences ```json ... ``` or ``` ... ```
        cleaned = text.strip()
        fence_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
        match = re.search(fence_pattern, cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()

        # If the response has extra text, try to extract the JSON block
        if not cleaned.startswith(("[", "{")):
            # Try to locate the first [ or { and match to the last ] or }
            start = min(
                (cleaned.find(c) for c in "[{" if c in cleaned),
                default=-1,
            )
            if start == -1:
                logger.warning("No JSON found in LLM response")
                return None
            cleaned = cleaned[start:]

        # Try direct parse first
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # If direct parse fails, try to extract just the JSON structure
        # by matching balanced brackets/braces
        opener = cleaned[0]
        closer = "]" if opener == "[" else "}"
        depth = 0
        in_string = False
        escape = False
        end_pos = -1
        for i, ch in enumerate(cleaned):
            if escape:
                escape = False
                continue
            if ch == "\\" and in_string:
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    end_pos = i + 1
                    break

        if end_pos > 0:
            try:
                return json.loads(cleaned[:end_pos])
            except json.JSONDecodeError as e:
                logger.warning("JSON parse error: %s — raw: %.200s", e, cleaned[:end_pos])
        else:
            logger.warning("Could not find balanced JSON in: %.200s", cleaned)
        return None

    # ------------------------------------------------------------------ #
    #  Export helpers                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def export_markdown(record: CallRecord) -> str:
        """Render a CallRecord as a formatted Markdown report."""
        lines: list[str] = []
        lines.append(f"# Call Report: {record.id}")
        lines.append("")
        lines.append(f"**Agent:** {record.agent_name}")
        lines.append(f"**Start:** {record.start_time}")
        if record.end_time:
            lines.append(f"**End:** {record.end_time}")
        if record.duration is not None:
            lines.append(f"**Duration:** {record.duration:.1f}s")
        lines.append(f"**Status:** {record.status}")
        lines.append("")

        # Summary
        if record.summary:
            lines.append("## Summary")
            lines.append("")
            lines.append(record.summary)
            lines.append("")

        # Key topics
        if record.key_topics:
            lines.append("## Key Topics")
            lines.append("")
            for topic in record.key_topics:
                lines.append(f"- {topic}")
            lines.append("")

        # Sentiment
        if record.sentiment:
            lines.append("## Sentiment")
            lines.append("")
            for speaker, sentiment in record.sentiment.items():
                lines.append(f"- **{speaker}**: {sentiment}")
            lines.append("")

        # Transcript
        if record.transcript:
            lines.append("## Transcript")
            lines.append("")
            for entry in record.transcript:
                time_str = datetime.fromtimestamp(
                    entry.timestamp, tz=timezone.utc
                ).strftime("%H:%M:%S")
                lines.append(f"**[{time_str}] {entry.speaker}:** {entry.text}")
                lines.append("")

        # Action items
        if record.action_items:
            lines.append("## Action Items")
            lines.append("")
            lines.append("| Task | Assignee | Due Date | Status |")
            lines.append("|------|----------|----------|--------|")
            for item in record.action_items:
                due = item.due_date or "—"
                assignee = item.assignee or "—"
                lines.append(
                    f"| {item.task} | {assignee} | {due} | {item.status} |"
                )
            lines.append("")

        # Scorecard
        if record.scorecard:
            lines.append("## Scorecard")
            lines.append("")
            lines.append("| Objective | Status | Notes |")
            lines.append("|-----------|--------|-------|")
            for entry in record.scorecard:
                notes = entry.notes or "—"
                lines.append(
                    f"| {entry.objective} | {entry.status} | {notes} |"
                )
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def export_json(record: CallRecord) -> str:
        """Serialize a CallRecord to a JSON string."""
        import dataclasses

        def _default(obj: object) -> object:
            if dataclasses.is_dataclass(obj):
                return dataclasses.asdict(obj)
            raise TypeError(f"Cannot serialize {type(obj)}")

        # Convert to dict via asdict, then dump
        data = dataclasses.asdict(record)
        return json.dumps(data, indent=2, default=str, ensure_ascii=False)