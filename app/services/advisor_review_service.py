from dataclasses import dataclass

from app.repositories.advisor_reviews import (
    AdvisorReviewRepository,
    PendingCoursePlan,
)


@dataclass
class AdvisorReviewInbox:
    advisor_name: str | None
    pending_plans: list[PendingCoursePlan]
    selected_plan: PendingCoursePlan | None = None
    error: str | None = None


@dataclass
class AdvisorReviewResult:
    succeeded: bool
    message: str


class AdvisorReviewService:
    def __init__(self, repository: AdvisorReviewRepository):
        self.repository = repository

    def get_inbox(
        self, user_id: int, selected_plan_id: int | None = None
    ) -> AdvisorReviewInbox:
        advisor = self.repository.get_advisor_for_user(user_id)
        if advisor is None:
            return AdvisorReviewInbox(
                advisor_name=None,
                pending_plans=[],
                error="Your account is not linked to an advisor profile.",
            )
        if advisor.advisor_id is None:
            return AdvisorReviewInbox(
                advisor_name=None,
                pending_plans=[],
                error="Your advisor profile is missing its database identifier.",
            )
        pending_plans = self.repository.get_pending_plans(advisor.advisor_id)
        selected_plan = next(
            (
                item
                for item in pending_plans
                if item.plan.plan_id == selected_plan_id
            ),
            None,
        )
        if selected_plan is None and pending_plans:
            selected_plan = pending_plans[0]
        return AdvisorReviewInbox(
            advisor_name=f"{advisor.first_name} {advisor.last_name}",
            pending_plans=pending_plans,
            selected_plan=selected_plan,
        )

    def review_plan(
        self,
        *,
        user_id: int,
        plan_id: int,
        decision: str,
        feedback: str,
    ) -> AdvisorReviewResult:
        advisor = self.repository.get_advisor_for_user(user_id)
        if advisor is None or advisor.advisor_id is None:
            return AdvisorReviewResult(
                succeeded=False,
                message="Your account is not linked to an advisor profile.",
            )

        if decision not in {"approve", "request_revisions"}:
            return AdvisorReviewResult(
                succeeded=False,
                message="Choose Approve or Request Revisions.",
            )
        feedback = feedback.strip()
        if decision == "request_revisions" and not feedback:
            return AdvisorReviewResult(
                succeeded=False,
                message="Add feedback before requesting revisions.",
            )
        if len(feedback) > 2000:
            return AdvisorReviewResult(
                succeeded=False,
                message="Feedback must be 2,000 characters or fewer.",
            )

        plan = self.repository.get_reviewable_plan(
            plan_id=plan_id,
            advisor_id=advisor.advisor_id,
        )
        if plan is None:
            return AdvisorReviewResult(
                succeeded=False,
                message="This plan is no longer pending in your review queue.",
            )

        self.repository.save_decision(
            plan=plan,
            status=(
                "approved" if decision == "approve" else "revision_requested"
            ),
            feedback=feedback,
        )
        return AdvisorReviewResult(
            succeeded=True,
            message=(
                "Plan approved."
                if decision == "approve"
                else "Revisions requested. The student can now update and resubmit the plan."
            ),
        )

    def withdraw_plan(self, *, user_id: int, plan_id: int) -> AdvisorReviewResult:
        advisor = self.repository.get_advisor_for_user(user_id)
        if advisor is None or advisor.advisor_id is None:
            return AdvisorReviewResult(
                succeeded=False,
                message="Your account is not linked to an advisor profile.",
            )

        plan = self.repository.get_reviewable_plan(
            plan_id=plan_id,
            advisor_id=advisor.advisor_id,
        )
        if plan is None:
            return AdvisorReviewResult(
                succeeded=False,
                message="This plan is no longer pending in your review queue.",
            )

        self.repository.withdraw_plan(plan=plan)
        return AdvisorReviewResult(
            succeeded=True,
            message="Submission withdrawn and retained in the student's plan history.",
        )
