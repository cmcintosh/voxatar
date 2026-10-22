"""
Energy-based Voice Activity Detection (VAD).

Simple but effective VAD that uses RMS energy thresholding to detect
speech vs. silence in 16-bit PCM audio chunks. Tracks silence duration
to emit end-of-speech events when the user pauses long enough.

Used by the pipeline to gate audio sent to STT and to detect
barge-in (user interrupting the agent).
"""

from __future__ import annotations

import logging
import struct
import time

import numpy as np

logger = logging.getLogger(__name__)


class EnergyVAD:
    """
    Energy-based Voice Activity Detection.

    Analyzes 16-bit PCM audio chunks and classifies them as speech or
    silence based on RMS energy. Tracks cumulative silence duration to
    emit ``end_of_speech`` events after a configurable silence gap.

    Parameters
    ----------
    energy_threshold : float
        RMS energy level above which a chunk is considered speech.
        Typical values for 16-bit PCM at 16 kHz range from 100–2000
        depending on microphone gain and noise floor.
    min_silence_ms : int
        Minimum consecutive silence duration (in milliseconds) after
        speech before an ``end_of_speech`` event is emitted.
    chunk_duration_ms : int
        Duration of each audio chunk in milliseconds. Used to compute
        how many chunks constitute the silence threshold.
    """

    def __init__(
        self,
        energy_threshold: float = 500,
        min_silence_ms: int = 700,
        chunk_duration_ms: int = 100,
    ) -> None:
        self.energy_threshold = energy_threshold
        self.min_silence_ms = min_silence_ms
        self.chunk_duration_ms = chunk_duration_ms

        # Derived: how many chunks of silence before we declare end-of-speech
        self._silence_chunks_needed = max(1, min_silence_ms // chunk_duration_ms)
        logger.debug(
            "EnergyVAD initialised: threshold=%.1f, min_silence=%dms, "
            "chunk=%dms, silence_chunks_needed=%d",
            energy_threshold,
            min_silence_ms,
            chunk_duration_ms,
            self._silence_chunks_needed,
        )

        # State tracking
        self._in_speech: bool = False
        self._consecutive_silence_chunks: int = 0
        self._total_chunks: int = 0
        self._speech_chunks: int = 0
        self._last_energy: float = 0.0

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def is_speech(self, audio_bytes: bytes) -> bool:
        """
        Check whether a PCM chunk contains speech based on RMS energy.

        Parameters
        ----------
        audio_bytes : bytes
            Raw 16-bit signed little-endian PCM audio (mono).

        Returns
        -------
        bool
            ``True`` if the chunk's RMS energy exceeds the threshold.
        """
        energy = self._compute_rms(audio_bytes)
        self._last_energy = energy
        is_speech = energy >= self.energy_threshold

        logger.debug(
            "is_speech: energy=%.2f threshold=%.2f → %s",
            energy,
            self.energy_threshold,
            is_speech,
        )
        return is_speech

    def process_chunk(self, audio_bytes: bytes) -> str:
        """
        Process a PCM chunk and return a state classification.

        Returns one of:
        - ``"speech"`` — the chunk contains speech energy.
        - ``"silence"`` — the chunk is silent (below threshold).
        - ``"end_of_speech"`` — silence has persisted long enough after
          speech to signal that the user has finished talking.

        Parameters
        ----------
        audio_bytes : bytes
            Raw 16-bit signed little-endian PCM audio (mono).

        Returns
        -------
        str
            One of ``"speech"``, ``"silence"``, or ``"end_of_speech"``.
        """
        self._total_chunks += 1
        energy = self._compute_rms(audio_bytes)
        self._last_energy = energy
        chunk_is_speech = energy >= self.energy_threshold

        if chunk_is_speech:
            self._speech_chunks += 1
            self._consecutive_silence_chunks = 0
            if not self._in_speech:
                logger.info(
                    "Speech started (energy=%.2f, chunk #%d)",
                    energy,
                    self._total_chunks,
                )
            self._in_speech = True
            return "speech"

        # Chunk is silence
        if self._in_speech:
            self._consecutive_silence_chunks += 1
            logger.debug(
                "Silence chunk #%d after speech (energy=%.2f, %d/%d needed)",
                self._consecutive_silence_chunks,
                energy,
                self._consecutive_silence_chunks,
                self._silence_chunks_needed,
            )
            if self._consecutive_silence_chunks >= self._silence_chunks_needed:
                logger.info(
                    "End of speech detected (%dms silence after speech)",
                    self._consecutive_silence_chunks * self.chunk_duration_ms,
                )
                self._in_speech = False
                self._consecutive_silence_chunks = 0
                return "end_of_speech"

            return "silence"

        # Not in speech and still silent
        return "silence"

    def reset(self) -> None:
        """Reset all internal state to defaults (start of a new utterance)."""
        logger.debug(
            "Resetting VAD state (was: in_speech=%s, silence_chunks=%d, "
            "total=%d, speech=%d)",
            self._in_speech,
            self._consecutive_silence_chunks,
            self._total_chunks,
            self._speech_chunks,
        )
        self._in_speech = False
        self._consecutive_silence_chunks = 0
        self._total_chunks = 0
        self._speech_chunks = 0
        self._last_energy = 0.0

    # ------------------------------------------------------------------ #
    # Introspection helpers
    # ------------------------------------------------------------------ #

    @property
    def in_speech(self) -> bool:
        """Whether the VAD currently believes the user is speaking."""
        return self._in_speech

    @property
    def last_energy(self) -> float:
        """RMS energy of the most recently processed chunk."""
        return self._last_energy

    @property
    def stats(self) -> dict:
        """Return a dictionary of current VAD statistics."""
        return {
            "total_chunks": self._total_chunks,
            "speech_chunks": self._speech_chunks,
            "in_speech": self._in_speech,
            "consecutive_silence_chunks": self._consecutive_silence_chunks,
            "last_energy": self._last_energy,
            "energy_threshold": self.energy_threshold,
        }

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_rms(audio_bytes: bytes) -> float:
        """
        Compute the RMS energy of a 16-bit PCM audio chunk.

        Parameters
        ----------
        audio_bytes : bytes
            Raw 16-bit signed little-endian PCM samples.

        Returns
        -------
        float
            Root-mean-square energy value.
        """
        if len(audio_bytes) < 2:
            logger.warning("Audio chunk too short for RMS: %d bytes", len(audio_bytes))
            return 0.0

        try:
            samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
        except ValueError as exc:
            logger.error("Failed to parse PCM data: %s", exc)
            return 0.0

        if samples.size == 0:
            return 0.0

        rms = float(np.sqrt(np.mean(samples**2)))
        return rms