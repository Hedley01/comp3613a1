from datetime import date

from sqlmodel import Field, Relationship, SQLModel


class DegreeCourse(SQLModel, table=True):
    degree_id: int = Field(foreign_key="degree.degree_id", primary_key=True)
    course_code: str = Field(foreign_key="course.course_code", primary_key=True)


class DegreeElectiveCourse(SQLModel, table=True):
    degree_id: int = Field(foreign_key="degree.degree_id", primary_key=True)
    course_code: str = Field(foreign_key="course.course_code", primary_key=True)


class CoursePrerequisite(SQLModel, table=True):
    course_code: str = Field(foreign_key="course.course_code", primary_key=True)
    prerequisite_code: str = Field(
        foreign_key="course.course_code", primary_key=True
    )


class CoursePlanCourse(SQLModel, table=True):
    plan_id: int = Field(foreign_key="courseplan.plan_id", primary_key=True)
    course_code: str = Field(foreign_key="course.course_code", primary_key=True)


class Advisor(SQLModel, table=True):
    advisor_id: int | None = Field(default=None, primary_key=True)
    first_name: str
    last_name: str
    department: str

    students: list["Student"] = Relationship(back_populates="advisor")
    course_plans: list["CoursePlan"] = Relationship(back_populates="advisor")


class Degree(SQLModel, table=True):
    degree_id: int | None = Field(default=None, primary_key=True)
    title: str
    total_required_credits: int

    students: list["Student"] = Relationship(back_populates="degree")
    courses: list["Course"] = Relationship(
        back_populates="degrees", link_model=DegreeCourse
    )


class Course(SQLModel, table=True):
    course_code: str = Field(primary_key=True)
    title: str
    credits: int
    description: str

    degrees: list[Degree] = Relationship(
        back_populates="courses", link_model=DegreeCourse
    )
    completed_records: list["CompletedCourse"] = Relationship(
        back_populates="course"
    )
    course_plans: list["CoursePlan"] = Relationship(
        back_populates="courses", link_model=CoursePlanCourse
    )


class Student(SQLModel, table=True):
    student_id: int | None = Field(default=None, primary_key=True)
    first_name: str
    last_name: str
    email: str = Field(index=True, unique=True)
    auth_user_id: int | None = Field(
        default=None, foreign_key="user.id", index=True, unique=True
    )
    advisor_id: int | None = Field(
        default=None, foreign_key="advisor.advisor_id"
    )
    degree_id: int = Field(foreign_key="degree.degree_id")

    advisor: Advisor | None = Relationship(back_populates="students")
    degree: Degree = Relationship(back_populates="students")
    completed_courses: list["CompletedCourse"] = Relationship(
        back_populates="student"
    )
    course_plans: list["CoursePlan"] = Relationship(back_populates="student")


class CompletedCourse(SQLModel, table=True):
    completion_id: int | None = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.student_id", index=True)
    course_code: str = Field(foreign_key="course.course_code", index=True)
    semester_taken: str
    grade: str

    student: Student = Relationship(back_populates="completed_courses")
    course: Course = Relationship(back_populates="completed_records")


class CoursePlan(SQLModel, table=True):
    plan_id: int | None = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.student_id", index=True)
    advisor_id: int | None = Field(
        default=None, foreign_key="advisor.advisor_id"
    )
    target_semester: str
    status: str = Field(default="draft", index=True)
    submission_date: date | None = None
    advisor_feedback: str = Field(default="")

    student: Student = Relationship(back_populates="course_plans")
    advisor: Advisor | None = Relationship(back_populates="course_plans")
    courses: list[Course] = Relationship(
        back_populates="course_plans", link_model=CoursePlanCourse
    )
