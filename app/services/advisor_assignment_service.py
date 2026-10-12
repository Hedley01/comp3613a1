from app.models.academic import Advisor
from app.repositories.advisor_assignment import AdvisorAssignmentRepository


class AdvisorAssignmentService:
    def __init__(self, repository: AdvisorAssignmentRepository):
        self.repository = repository

    def get_least_loaded_advisor(self) -> Advisor:
        advisors_by_load = self.repository.get_advisors_by_student_load()
        if not advisors_by_load:
            raise LookupError("No advisor accounts are available for assignment.")
        return advisors_by_load[0][0]
