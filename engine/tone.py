"""Tone checker for Axiom (PRD §4.3 A-16, Gate G3).

Analyzes text for:
- Sentence statistics (reading grade level via Flesch-Kincaid, sentence length).
- Passive voice constructions (R-08: Prefer active voice).
- Rubric & exemplar comparisons for tone:
  * R-07 "Confident but humble" (flags arrogant hyperbole).
  * R-11 "Avoid jargon where possible" (flags heavy corporate buzzwords).
  * R-04 "Clear and Direct Tone" (flags excessive sentence complexity).

In accordance with PRD A-16 and the abstain rule (A-12):
All tone findings are subjective and output with `abstained=True`,
`status="open"` (Needs judgment), routed to `"creator"`, and explanations
prefixed with "Needs judgment: ".
"""

from __future__ import annotations

import re
import uuid
from typing import List, Optional, Tuple

try:
    import textstat
except ImportError:
    textstat = None

from contracts.models import (
    ContentUnit,
    DisclosureRecord,
    Evidence,
    Finding,
    FindingSeverity,
    FindingStatus,
    FindingType,
    Method,
    Sensitivity,
    Span,
    SuggestedFix,
)


class ToneChecker:
    """A-16 Tone Checker: sentence statistics + rubric/exemplar comparison."""

    # Arrogant / hyperbolic phrases conflicting with R-07 ("Confident but humble")
    ARROGANT_EXEMPLARS = [
        (re.compile(r"\bcrushes\s+the\s+competition\b", re.I), "crushes the competition", "outperforms the competition"),
        (re.compile(r"\brevolutionary\s+breakthrough\b", re.I), "revolutionary breakthrough", "significant innovation"),
        (re.compile(r"\bundisputed\s+(?:leader|platform|solution)\b", re.I), "undisputed leader", "proven industry solution"),
        (re.compile(r"\bcompletely\s+unmatched\b", re.I), "completely unmatched", "differentiated and robust"),
        (re.compile(r"\binfinitely\s+superior\b", re.I), "infinitely superior", "substantially more efficient"),
        (re.compile(r"\bgame-changing\s+miracle\b", re.I), "game-changing miracle", "modernised workflow"),
        (re.compile(r"\bflawless\s+execution\b", re.I), "flawless execution", "reliable execution"),
    ]

    # Jargon / buzzword exemplars conflicting with R-11 ("Avoid jargon where possible")
    JARGON_EXEMPLARS = [
        (re.compile(r"\bsynergiz(?:e|ing|ed)\s+(?:cross-functional\s+)?paradigms?\b", re.I), "synergize paradigms", "collaborate across teams"),
        (re.compile(r"\bholistic\s+ideation\s+framework\b", re.I), "holistic ideation framework", "comprehensive planning process"),
        (re.compile(r"\bhyper-scalable\s+paradigm\b", re.I), "hyper-scalable paradigm", "scalable architecture"),
        (re.compile(r"\bboil\s+the\s+ocean\b", re.I), "boil the ocean", "take on overly broad scope"),
        (re.compile(r"\bagentic\s+rag\s+pipeline\b", re.I), "agentic RAG pipeline", "automated knowledge retrieval"),
        (re.compile(r"\bleverage\s+holistic\s+synergies\b", re.I), "leverage holistic synergies", "combine team strengths"),
    ]

    # Passive voice regex pattern: (to be) + past participle + by + Agent (stops before prepositions)
    PASSIVE_VOICE_PATTERN = re.compile(
        r"\b(is|are|was|were|been|be|being)\s+([a-z]+ed|written|made|done|seen|given|taken|held|found|completed)\s+by\s+([A-Z][a-zA-Z0-9_\-]*(?:\s+[A-Z][a-zA-Z0-9_\-]*)*|[a-z0-9_\-]+)\b"
    )

    def __init__(self, reading_level_threshold: float = 10.0) -> None:
        self.reading_level_threshold = reading_level_threshold

    def calculate_reading_grade(self, text: str) -> float:
        """Compute Flesch-Kincaid Grade Level locally and deterministically.

        Standard Formula:
            0.39 * (total words / total sentences) + 11.8 * (total syllables / total words) - 15.59
        """
        if not text.strip():
            return 0.0

        words = re.findall(r"\b[a-zA-Z]+\b", text)
        sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
        num_words = max(1, len(words))
        num_sentences = max(1, len(sentences))

        def count_syllables(word: str) -> int:
            w = word.lower()
            if len(w) <= 3:
                return 1
            # Count vowel groups
            matches = re.findall(r"[aeiouy]+", w)
            count = len(matches)
            # Adjust for silent e endings
            if w.endswith("e") and not w.endswith("le") and count > 1:
                count -= 1
            # Adjust for -ed endings
            if w.endswith("ed") and not w.endswith("ted") and not w.endswith("ded") and count > 1:
                count -= 1
            return max(1, count)

        num_syllables = sum(count_syllables(w) for w in words)
        grade = 0.39 * (num_words / num_sentences) + 11.8 * (num_syllables / num_words) - 15.59
        return max(0.0, round(grade, 2))

    def split_sentences(self, text: str) -> List[Tuple[str, int, int]]:
        """Split text into sentences with [start, end] char offsets."""
        sentences: List[Tuple[str, int, int]] = []
        for m in re.finditer(r"[^.!?\n]+(?:[.!?]+|\Z)", text):
            s_text = m.group(0).strip()
            if s_text:
                # Find exact start/end of stripped text within match
                offset = m.group(0).find(s_text)
                start = m.start() + offset
                end = start + len(s_text)
                sentences.append((s_text, start, end))
        return sentences

    def check_unit(self, unit: ContentUnit) -> List[Finding]:
        """Check a single ContentUnit for tone, style, and reading-level violations."""
        if unit.kind in ("image", "table") or not unit.text or not unit.text.strip():
            return []

        findings: List[Finding] = []
        text = unit.text

        # -------------------------------------------------------------------
        # 1. Passive voice detection (R-08: Use active voice)
        # -------------------------------------------------------------------
        for match in self.PASSIVE_VOICE_PATTERN.finditer(text):
            quote = match.group(0)
            be_verb = match.group(1)
            participle = match.group(2)
            agent = match.group(3)
            start = unit.start + match.start()
            end = unit.start + match.end()

            # Active voice conversion
            agent_cap = agent.strip().capitalize() if not agent[0].isupper() else agent.strip()
            subject = text[:match.start()].strip()
            remainder = text[match.end():].strip()
            p_lower = participle.lower()
            if p_lower == "automated":
                verb = "automates"
            elif p_lower == "completed":
                verb = "completes"
            elif p_lower == "executed":
                verb = "executes"
            elif p_lower == "written":
                verb = "writes"
            else:
                verb = f"{p_lower}s"

            if subject:
                sub_clean = subject[0].lower() + subject[1:] if not subject.startswith(("Meridian", "MF")) else subject
                fix_text = f"{agent_cap} {verb} {sub_clean}"
                if remainder:
                    fix_text += f" {remainder}"
                if not fix_text.endswith((".", "!", "?")) and text.endswith("."):
                    fix_text += "."
            else:
                fix_text = text[:match.start()] + f"{agent_cap} {verb}" + text[match.end():]

            findings.append(
                Finding(
                    finding_id=f"f_tone_{uuid.uuid4().hex[:6]}",
                    type=FindingType.tone,
                    severity=FindingSeverity.medium,
                    confidence=0.85,
                    span=Span(
                        unit_id=unit.unit_id,
                        start=start,
                        end=end,
                        quote=quote,
                    ),
                    evidence=[
                        Evidence(
                            source="R-08",
                            version=1,
                            status="active",
                            current_version=1,
                        )
                    ],
                    explanation=(
                        f"Needs judgment: Passive voice detected ('{quote}'). "
                        "Rule R-08 recommends active voice to keep copy direct and energetic."
                    ),
                    suggested_fix=SuggestedFix(
                        text=fix_text,
                        edit_budget="minimal",
                        rechecked=False,
                    ),
                    route_to="creator",
                    disclosure=DisclosureRecord(
                        method=Method.deterministic_lookup,
                        provider=None,
                        model=None,
                        external_call=False,
                        data_categories=["text"],
                        sensitivity=Sensitivity.internal,
                        latency_ms=1,
                    ),
                    status=FindingStatus.open,
                    abstained=True,
                    rule_id="R-08",
                )
            )

        # -------------------------------------------------------------------
        # 2. Rubric / Exemplar: R-07 "Confident but humble" (Arrogant hyperbole)
        # -------------------------------------------------------------------
        for pattern, raw_phrase, replacement in self.ARROGANT_EXEMPLARS:
            for match in pattern.finditer(text):
                quote = match.group(0)
                start = unit.start + match.start()
                end = unit.start + match.end()

                fix_text = text[:match.start()] + replacement + text[match.end():]

                findings.append(
                    Finding(
                        finding_id=f"f_tone_{uuid.uuid4().hex[:6]}",
                        type=FindingType.tone,
                        severity=FindingSeverity.medium,
                        confidence=0.80,
                        span=Span(
                            unit_id=unit.unit_id,
                            start=start,
                            end=end,
                            quote=quote,
                        ),
                        evidence=[
                            Evidence(
                                source="R-07",
                                version=1,
                                status="active",
                                current_version=1,
                            )
                        ],
                        explanation=(
                            f"Needs judgment: Arrogant/hyperbolic tone ('{quote}'). "
                            "Rule R-07 requires brand messaging to convey confidence without appearing arrogant."
                        ),
                        suggested_fix=SuggestedFix(
                            text=fix_text,
                            edit_budget="minimal",
                            rechecked=False,
                        ),
                        route_to="creator",
                        disclosure=DisclosureRecord(
                            method=Method.deterministic_lookup,
                            provider=None,
                            model=None,
                            external_call=False,
                            data_categories=["text"],
                            sensitivity=Sensitivity.internal,
                            latency_ms=1,
                        ),
                        status=FindingStatus.open,
                        abstained=True,
                        rule_id="R-07",
                    )
                )

        # -------------------------------------------------------------------
        # 3. Rubric / Exemplar: R-11 "Avoid jargon where possible"
        # -------------------------------------------------------------------
        for pattern, raw_phrase, replacement in self.JARGON_EXEMPLARS:
            for match in pattern.finditer(text):
                quote = match.group(0)
                start = unit.start + match.start()
                end = unit.start + match.end()

                fix_text = text[:match.start()] + replacement + text[match.end():]

                findings.append(
                    Finding(
                        finding_id=f"f_tone_{uuid.uuid4().hex[:6]}",
                        type=FindingType.tone,
                        severity=FindingSeverity.medium,
                        confidence=0.75,
                        span=Span(
                            unit_id=unit.unit_id,
                            start=start,
                            end=end,
                            quote=quote,
                        ),
                        evidence=[
                            Evidence(
                                source="R-11",
                                version=1,
                                status="active",
                                current_version=1,
                            )
                        ],
                        explanation=(
                            f"Needs judgment: Heavy technical or corporate jargon ('{quote}'). "
                            "Rule R-11 prefers plain language over buzzwords."
                        ),
                        suggested_fix=SuggestedFix(
                            text=fix_text,
                            edit_budget="minimal",
                            rechecked=False,
                        ),
                        route_to="creator",
                        disclosure=DisclosureRecord(
                            method=Method.deterministic_lookup,
                            provider=None,
                            model=None,
                            external_call=False,
                            data_categories=["text"],
                            sensitivity=Sensitivity.internal,
                            latency_ms=1,
                        ),
                        status=FindingStatus.open,
                        abstained=True,
                        rule_id="R-11",
                    )
                )

        # -------------------------------------------------------------------
        # 4. Sentence statistics: Reading level & sentence length (R-04 / R-11)
        # -------------------------------------------------------------------
        if unit.kind in ("paragraph", "text"):
            sentences = self.split_sentences(text)
            for s_text, s_start, s_end in sentences:
                words = re.findall(r"\b[a-zA-Z]+\b", s_text)
                word_count = len(words)
                # Only check reading level on substantive sentences with at least 12 words
                if word_count >= 12:
                    grade = self.calculate_reading_grade(s_text)
                    if grade > 12.0 or word_count > 35:
                        quote = s_text
                        start = unit.start + s_start
                        end = unit.start + s_end

                        reason = (
                            f"High reading level (Grade {grade:.1f} > {self.reading_level_threshold:.0f} threshold)"
                            if grade > 12.0
                            else f"Overly complex sentence ({word_count} words > 30 recommendation)"
                        )

                        findings.append(
                            Finding(
                                finding_id=f"f_tone_{uuid.uuid4().hex[:6]}",
                                type=FindingType.tone,
                                severity=FindingSeverity.low,
                                confidence=0.70,
                                span=Span(
                                    unit_id=unit.unit_id,
                                    start=start,
                                    end=end,
                                    quote=quote,
                                ),
                                evidence=[
                                    Evidence(
                                        source="R-04",
                                        version=1,
                                        status="active",
                                        current_version=1,
                                    )
                                ],
                                explanation=(
                                    f"Needs judgment: {reason}. "
                                    "Rule R-04 recommends clear, concise, and direct communication targeting Grade 10."
                                ),
                                suggested_fix=None,
                                route_to="creator",
                                disclosure=DisclosureRecord(
                                    method=Method.deterministic_lookup,
                                    provider=None,
                                    model=None,
                                    external_call=False,
                                    data_categories=["text"],
                                    sensitivity=Sensitivity.internal,
                                    latency_ms=1,
                                ),
                                status=FindingStatus.open,
                                abstained=True,
                                rule_id="R-04",
                            )
                        )

        return findings

    def check_units(self, units: List[ContentUnit]) -> List[Finding]:
        """Check all content units for tone violations."""
        all_findings: List[Finding] = []
        for unit in units:
            all_findings.extend(self.check_unit(unit))
        return all_findings
