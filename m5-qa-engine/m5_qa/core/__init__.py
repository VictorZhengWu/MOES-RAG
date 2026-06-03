"""
M5 QA Engine - Core module.

Contains configuration, user tier system, mode router, and the main QA engine.
"""

from m5_qa.core.config import QAConfig, LLMBackend
from m5_qa.core.tier import UserTier, PremiumQuota, USER_TIERS
from m5_qa.core.router import ModeRouter

__all__ = [
    "QAConfig",
    "LLMBackend",
    "UserTier",
    "PremiumQuota",
    "USER_TIERS",
    "ModeRouter",
]
