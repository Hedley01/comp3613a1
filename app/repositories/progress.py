from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.academic import (
    CompletedCourse,
    Course,
    Degree,
    DegreeCourse,
    Student,
)


@dataclass
class StudentProgressRecords:
    student: Student
    degree: Degree
    completed_courses: list[tuple[Course, CompletedCourse]]
    remaining_courses: list[Course]


class ProgressRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_student_by_user_id(self, user_id: int) -> Student | None:
        return self.db.exec(
            select(Student).where(Student.auth_user_id == user_id)
        ).one_or_none()

    def get_progress_records(self, student_id: int) -> StudentProgressRecords | None:
        student = self.db.get(Student, student_id)
        if student is None:
            return None

        degree = self.db.get(Degree, student.degree_id)
        if degree is None:
            raise ValueError(
                f"Degree {student.degree_id} is missing for student {student_id}"
            )

        completed_rows = self.db.exec(
            select(Course, CompletedCourse)
            .join(CompletedCourse, CompletedCourse.course_code == Course.course_code)
            .join(DegreeCourse, DegreeCourse.course_code == Course.course_code)
            .where(
                CompletedCourse.student_id == student_id,
                DegreeCourse.degree_id == student.degree_id,
            )
            .order_by(Course.course_code)
        ).all()
        completed_codes = {course.course_code for course, _ in completed_rows}

        remaining_courses = self.db.exec(
            select(Course)
            .join(DegreeCourse, DegreeCourse.course_code == Course.course_code)
            .where(
                DegreeCourse.degree_id == student.degree_id,
                Course.course_code.not_in(completed_codes),
            )
            .order_by(Course.course_code)
        ).all()

        return StudentProgressRecords(
            student=student,
            degree=degree,
            completed_courses=completed_rows,
            remaining_courses=remaining_courses,
        )
