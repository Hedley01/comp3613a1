from sqlmodel import Session, func, select

from app.models.academic import Advisor, Student
from app.models.user import User


class AdvisorAssignmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_advisors_by_student_load(self) -> list[tuple[Advisor, int]]:
        statement = (
            select(Advisor, func.count(Student.student_id))
            .join(User, User.id == Advisor.user_id)
            .outerjoin(Student, Student.advisor_id == Advisor.advisor_id)
            .where(User.role == "advisor")
            .group_by(Advisor.advisor_id)
            .order_by(func.count(Student.student_id), Advisor.advisor_id)
        )
        return [
            (advisor, int(student_count))
            for advisor, student_count in self.db.exec(statement).all()
        ]
