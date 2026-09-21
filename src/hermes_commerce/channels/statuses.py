from enum import Enum


class ChannelStatus(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    READY = "READY"
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"
