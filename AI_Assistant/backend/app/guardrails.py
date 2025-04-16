# backend/app/guardrails.py
from typing import Dict, Tuple
import re
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class Guardrails:
    def __init__(self):
        self.banned_patterns = {
            "pii": [
                r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"  # Email
            ],
            "toxic_language": [
                r"hate speech", 
                r"discriminatory"
            ],
            "prompt_injection": [
                r"ignore previous instructions",
                r"system prompt"
            ]
        }
        
        self.fallback_responses = {
            "pii": "I cannot process requests containing personal identifiable information",
            "toxic": "I aim to maintain respectful conversations",
            "injection": "I can't comply with instruction-override requests"
        }

    def audit_prompt(self, text: str) -> Tuple[bool, Dict]:
        """Check prompt for violations"""
        audit_result = {
            "is_flagged": False,
            "flagged_categories": [],
            "sanitized_text": text,
            "timestamp": datetime.utcnow().isoformat()
        }

        for category, patterns in self.banned_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    audit_result["is_flagged"] = True
                    audit_result["flagged_categories"].append(category)
                    audit_result["sanitized_text"] = re.sub(
                        pattern, 
                        "[REDACTED]", 
                        audit_result["sanitized_text"]
                    )

        return audit_result["is_flagged"], audit_result

    def audit_response(self, text: str) -> str:
        """Sanitize LLM output"""
        # Remove common LLM disclaimers
        disclaimers = [
            "as an AI language model",
            "I cannot answer that",
            "I don't have personal opinions"
        ]
        for phrase in disclaimers:
            text = text.replace(phrase, "")
        
        return text.strip()

    def get_fallback_response(self, category: str) -> str:
        """Get predefined safe response"""
        return self.fallback_responses.get(category, 
               "I'm unable to provide a response to that query")

# Singleton instance
guard = Guardrails()