"""State and approval primitives shared by channel launch orchestrators."""

from __future__ import annotations

from enum import Enum


class ChannelLaunchState(str, Enum):
    CHANNEL_DISCOVERY = "CHANNEL_DISCOVERY"
    CHANNEL_PREFLIGHT = "CHANNEL_PREFLIGHT"
    CHANNEL_PRICING = "CHANNEL_PRICING"
    CHANNEL_APPROVAL = "CHANNEL_APPROVAL"
    CHANNEL_PUBLISH = "CHANNEL_PUBLISH"
    CHANNEL_REVIEW = "CHANNEL_REVIEW"
    CHANNEL_SYNC = "CHANNEL_SYNC"


class ApprovalRequired(RuntimeError):
    pass


def require_channel_approval(
    *,
    channel: str,
    confirmation: str,
    expected_confirmation: str,
    preflight_ready: bool,
) -> None:
    if not preflight_ready:
        raise ApprovalRequired(f"{channel}: no se puede publicar sin preflight válido")
    if confirmation != expected_confirmation:
        raise ApprovalRequired(f"{channel}: se requiere aprobación explícita")
