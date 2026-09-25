"""Single import surface so metadata.create_all sees every table."""

from app.models.application import Application, StageEvent  # noqa: F401
from app.models.candidate import Candidate  # noqa: F401
from app.models.department import Department  # noqa: F401
from app.models.interview import Interview, InterviewPanelist  # noqa: F401
from app.models.job import Job  # noqa: F401
from app.models.offer import Offer  # noqa: F401
from app.models.user import User  # noqa: F401
