"""Classify emails by sender + subject to determine courier and delivery status."""
from __future__ import annotations

import logging

from .const import BUILTIN_SENDER_RULES, CONFIDENCE_LOW, CONFIDENCE_MEDIUM, SenderRule

_LOGGER = logging.getLogger(__name__)


class EmailClassifier:
    """Map sender email address & subject to (courier, status, confidence)."""

    def __init__(self, extra_rules: list[dict[str, str]] | None = None) -> None:
        """Initialize with built-ins plus any user-defined extras."""
        self._rules: dict[str, SenderRule] = dict(BUILTIN_SENDER_RULES)
        for rule in extra_rules or []:
            sender = rule.get("sender", "").strip().lower()
            if sender:
                self._rules[sender] = SenderRule(
                    courier=rule.get("courier", "Unknown"),
                    confidence=rule.get("confidence", CONFIDENCE_MEDIUM),
                    subject_patterns={},
                )

    def classify(
        self, sender: str | None, subject: str | None
    ) -> tuple[str | None, str | None, str]:
        """Return (courier, status, confidence). Returns (None, None, low) on no match."""
        if not sender or not subject:
            return None, None, CONFIDENCE_LOW

        rule = self._rules.get(sender.lower())
        if rule is None:
            _LOGGER.debug("No classifier rule for sender: %s", sender)
            return None, None, CONFIDENCE_LOW

        courier: str = rule["courier"]
        confidence: str = rule["confidence"]
        status: str | None = None

        for pattern, matched_status in rule.get("subject_patterns", {}).items():
            if pattern in subject:
                status = matched_status
                _LOGGER.debug("Classified '%s' as %s / %s", subject, courier, status)
                break

        return courier, status, confidence
