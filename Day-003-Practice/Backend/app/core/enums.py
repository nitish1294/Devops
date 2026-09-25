from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    HR_MANAGER = "hr_manager"
    RECRUITER = "recruiter"
    HIRING_MANAGER = "hiring_manager"
    INTERVIEWER = "interviewer"


class JobStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    ON_HOLD = "on_hold"
    CLOSED = "closed"
    FILLED = "filled"


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERN = "intern"


class Stage(StrEnum):
    """Ordered pipeline stages. Order matters for the board and for metrics."""

    SOURCED = "sourced"
    SCREENING = "screening"
    INTERVIEW = "interview"
    ASSESSMENT = "assessment"
    OFFER = "offer"
    HIRED = "hired"
    REJECTED = "rejected"

    @classmethod
    def board_order(cls) -> list[str]:
        return [
            cls.SOURCED,
            cls.SCREENING,
            cls.INTERVIEW,
            cls.ASSESSMENT,
            cls.OFFER,
            cls.HIRED,
            cls.REJECTED,
        ]

    @classmethod
    def terminal(cls) -> set[str]:
        return {cls.HIRED, cls.REJECTED}


class InterviewMode(StrEnum):
    ONSITE = "onsite"
    VIDEO = "video"
    PHONE = "phone"


class InterviewStatus(StrEnum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class Recommendation(StrEnum):
    STRONG_YES = "strong_yes"
    YES = "yes"
    NO = "no"
    STRONG_NO = "strong_no"


class OfferStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"
