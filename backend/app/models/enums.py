from enum import Enum


class AuditStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FindingSeverity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class AiQueryCategory(str, Enum):
    BRAND = "BRAND"
    PRODUCT = "PRODUCT"
    INDUSTRY = "INDUSTRY"
    COMPETITOR = "COMPETITOR"
    COMMERCIAL = "COMMERCIAL"
    INFORMATIONAL = "INFORMATIONAL"


class RecommendationPriority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ReportStatus(str, Enum):
    GENERATING = "GENERATING"
    READY = "READY"
    FAILED = "FAILED"
