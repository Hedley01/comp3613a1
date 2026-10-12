from math import ceil
from typing import TypedDict

from app.repositories.progress import ProgressRepository

COURSES_PER_SEMESTER = 5
ASSUMED_CREDITS_PER_COURSE = 3


class CourseProgress(TypedDict):
    course_code: str
    title: str
    credits: int
    semester_taken: str
    grade: str


class RequiredCourse(TypedDict):
    course_code: str
    title: str
    credits: int


class ProgressData(TypedDict):
    student_name: str
    degree_title: str
    earned_credits: int
    total_required_credits: int
    remaining_credits: int
    estimated_semesters_remaining: int
    courses_per_semester: int
    assumed_credits_per_course: int
    progress_percent: float
    completed_courses: list[CourseProgress]
    remaining_courses: list[RequiredCourse]


class ProgressService:
    def __init__(self, progress_repo: ProgressRepository):
        self.progress_repo = progress_repo

    def calculate_progress_for_user_id(
        self, user_id: int
    ) -> ProgressData | None:
        student = self.progress_repo.get_student_by_user_id(user_id)
        if student is None or student.student_id is None:
            return None
        return self.calculate_progress(student.student_id)

    def calculate_progress(self, student_id: int) -> ProgressData | None:
        records = self.progress_repo.get_progress_records(student_id)
        if records is None:
            return None

        completed_courses: list[CourseProgress] = [
            {
                "course_code": course.course_code,
                "title": course.title,
                "credits": course.credits,
                "semester_taken": completion.semester_taken,
                "grade": completion.grade,
            }
            for course, completion in records.completed_courses
        ]
        remaining_courses: list[RequiredCourse] = [
            {
                "course_code": course.course_code,
                "title": course.title,
                "credits": course.credits,
            }
            for course in records.remaining_courses
        ]
        earned_credits = sum(course["credits"] for course in completed_courses)
        total_required_credits = records.degree.total_required_credits
        remaining_credits = max(total_required_credits - earned_credits, 0)
        credits_per_semester = COURSES_PER_SEMESTER * ASSUMED_CREDITS_PER_COURSE
        estimated_semesters_remaining = ceil(
            remaining_credits / credits_per_semester
        )
        progress_percent = (
            min(earned_credits / total_required_credits * 100, 100)
            if total_required_credits > 0
            else 0
        )

        return {
            "student_name": (
                f"{records.student.first_name} {records.student.last_name}"
            ),
            "degree_title": records.degree.title,
            "earned_credits": earned_credits,
            "total_required_credits": total_required_credits,
            "remaining_credits": remaining_credits,
            "estimated_semesters_remaining": estimated_semesters_remaining,
            "courses_per_semester": COURSES_PER_SEMESTER,
            "assumed_credits_per_course": ASSUMED_CREDITS_PER_COURSE,
            "progress_percent": round(progress_percent, 1),
            "completed_courses": completed_courses,
            "remaining_courses": remaining_courses,
        }
