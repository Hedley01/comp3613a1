"""Database table models.

Import every table model here so ``SQLModel.metadata.create_all`` sees them.
"""

from app.models.academic import (
    Advisor,
    CompletedCourse,
    Course,
    CoursePlan,
    CoursePlanCourse,
    Degree,
    DegreeCourse,
    Student,
)
from app.models.user import User

__all__ = [
    "Advisor",
    "CompletedCourse",
    "Course",
    "CoursePlan",
    "CoursePlanCourse",
    "Degree",
    "DegreeCourse",
    "Student",
    "User",
]
