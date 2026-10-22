from __future__ import annotations

"""
Conversation flow manager.

Tracks which objectives have been covered during a call and provides
guidance to the agent's system prompt. Supports two modes:

- **guided**: The agent should work through objectives sequentially.
- **freeform**: The agent should cover objectives naturally in conversation.

Coverage is detected via simple keyword matching against the user's messages.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class FlowManager:
    """
    Manages conversation flow and objective coverage tracking.

    Attributes:
        objectives: The full list of objectives to cover.
        mode: Conversation mode ("guided" or "freeform").
        covered_objectives: Objectives that have been addressed.
        current_objective_index: Index of the current objective (guided mode).
        conversation_turns: Total number of conversation turns processed.
    """

    def __init__(
        self,
        objectives: list[str],
        mode: str = "guided",
    ) -> None:
        """
        Initialize the flow manager.

        Args:
            objectives: List of objective strings to track.
            mode: "guided" (sequential) or "freeform" (natural coverage).

        Raises:
            ValueError: If mode is not "guided" or "freeform".
        """
        if mode not in ("guided", "freeform"):
            raise ValueError(f"Invalid mode '{mode}'. Must be 'guided' or 'freeform'.")

        self.objectives: list[str] = list(objectives)
        self.mode: str = mode
        self.covered_objectives: list[str] = []
        self.current_objective_index: int = 0
        self.conversation_turns: int = 0

        # Pre-compute keyword sets for each objective for efficient matching
        self._objective_keywords: list[list[str]] = [
            self._extract_keywords(obj) for obj in self.objectives
        ]

        logger.info(
            "FlowManager initialised: %d objectives, mode=%s",
            len(self.objectives),
            self.mode,
        )

    # ------------------------------------------------------------------ #
    #  Update                                                            #
    # ------------------------------------------------------------------ #

    def update(self, user_message: str, agent_response: str) -> None:
        """
        Process a conversation turn and update coverage tracking.

        Args:
            user_message: The caller's message.
            agent_response: The agent's response.
        """
        self.conversation_turns += 1
        combined = f"{user_message} {agent_response}".lower()

        for i, objective in enumerate(self.objectives):
            if objective in self.covered_objectives:
                continue
            keywords = self._objective_keywords[i]
            # An objective is considered covered if any of its keywords appear
            if any(kw in combined for kw in keywords):
                self.covered_objectives.append(objective)
                logger.debug("Objective covered: %s", objective)

        # Advance the current objective index in guided mode
        if self.mode == "guided":
            while (
                self.current_objective_index < len(self.objectives)
                and self.objectives[self.current_objective_index] in self.covered_objectives
            ):
                self.current_objective_index += 1

    # ------------------------------------------------------------------ #
    #  Guidance                                                          #
    # ------------------------------------------------------------------ #

    def get_flow_guidance(self) -> str:
        """
        Build a guidance string to inject into the agent's system prompt.

        In guided mode, directs the agent to the current objective.
        In freeform mode, lists objectives to cover naturally.
        """
        remaining = [
            obj for obj in self.objectives if obj not in self.covered_objectives
        ]

        if not remaining:
            return "All objectives have been covered. Wind down the conversation naturally."

        if self.mode == "guided":
            current = self.objectives[
                self.current_objective_index
            ] if self.current_objective_index < len(self.objectives) else remaining[0]
            next_q = self.get_next_question()
            guidance = (
                f"You are currently working on objective: \"{current}\". "
            )
            if next_q:
                guidance += f"Suggested next question: {next_q}. "
            guidance += f"Already covered: {self._format_list(self.covered_objectives)}. "
            guidance += f"Remaining: {self._format_list(remaining)}."
            return guidance

        # freeform
        return (
            f"Objectives to cover naturally: {self._format_list(remaining)}. "
            f"Already covered: {self._format_list(self.covered_objectives)}."
        )

    # ------------------------------------------------------------------ #
    #  Next question                                                     #
    # ------------------------------------------------------------------ #

    def get_next_question(self) -> str | None:
        """
        Suggest a next question based on the current objective.

        Returns:
            A suggested question string, or None if all objectives are covered.
        """
        if self.current_objective_index >= len(self.objectives):
            return None

        current = self.objectives[self.current_objective_index]

        # Generate a simple question prompt from the objective text
        # Strip trailing punctuation and turn into a question
        cleaned = current.rstrip(".!?").strip()
        # If the objective is already a question, return it
        if cleaned.endswith("?"):
            return cleaned
        # Otherwise, frame it as a question
        return f"Could you tell me about {cleaned.lower()}?"

    # ------------------------------------------------------------------ #
    #  Status                                                            #
    # ------------------------------------------------------------------ #

    def all_objectives_covered(self) -> bool:
        """Return True if every objective has been covered."""
        return len(self.covered_objectives) >= len(self.objectives)

    def get_progress(self) -> dict:
        """
        Return a progress summary.

        Returns:
            Dict with: total, covered, remaining, current_objective.
        """
        remaining = [
            obj for obj in self.objectives if obj not in self.covered_objectives
        ]
        current = (
            self.objectives[self.current_objective_index]
            if self.current_objective_index < len(self.objectives)
            else None
        )
        return {
            "total": len(self.objectives),
            "covered": len(self.covered_objectives),
            "remaining": len(remaining),
            "current_objective": current,
        }

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_keywords(objective: str) -> list[str]:
        """
        Extract meaningful keywords from an objective string.

        Removes common stop words and returns lowercased tokens.
        """
        stop_words = {
            "a", "an", "the", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "to", "of", "in", "for", "on", "with", "at",
            "by", "from", "up", "about", "into", "through", "during",
            "before", "after", "above", "below", "under", "over",
            "and", "or", "but", "not", "no", "so", "than", "too",
            "very", "just", "as", "if", "then", "that", "this",
            "these", "those", "it", "its", "they", "them", "their",
            "we", "us", "our", "you", "your", "he", "she", "him", "her",
            "what", "which", "who", "whom", "whose", "when", "where",
            "why", "how", "all", "each", "every", "both", "few",
            "more", "most", "other", "some", "such", "only", "own",
            "same", "s", "t",
        }
        # Split on non-word characters
        tokens = re.split(r"[^\w]+", objective.lower())
        keywords = [
            token for token in tokens
            if len(token) > 2 and token not in stop_words
        ]
        # If no keywords extracted (e.g. very short objective), use the whole string
        if not keywords:
            keywords = [objective.lower().strip()]
        return keywords

    @staticmethod
    def _format_list(items: list[str]) -> str:
        """Format a list as a human-readable string."""
        if not items:
            return "[]"
        if len(items) == 1:
            return f"[{items[0]}]"
        return "[" + ", ".join(items) + "]"