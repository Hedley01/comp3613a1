# MyAdvisor - Test Plan and Strategy

All tests run from the project root with `pytest` (see "Running the tests" at the end).
Demo accounts (created by `python manage.py init`):

| Username | Password | Role |
| :--- | :--- | :--- |
| `bob` | `bobpass` | Student |
| `advisor` | `advisorpass` | Advisor |
| `advisor2` | `advisorpass2` | Advisor |
| `admin` | `adminpass` | Admin (no workflow screens yet) |

---

## 1. User Acceptance Test Plan

Reference: wireframes in `docs/wireframes/` (`view-progess.png`, `submit-plan.png`, `review-plan.png`).
Run on a freshly seeded database (`python manage.py init`), in the order below.

| Test ID | Wireframe | Task for the tester | Success criteria | Status |
| :--- | :--- | :--- | :--- | :--- |
| **UAT-1** | View Degree Progress | Sign in as `bob`. Open the Degree progress page. | Page shows BSc Computer Science, **63 of 96 credits earned**, **33 credits to go**, about 3 semesters remaining, 21 completed courses and 11 remaining courses. | Pending |
| **UAT-2** | Submit Course Plan | As `bob`, open Course Plan. Choose **Semester 1**, add **CSCI 122**, and submit. | Bob is redirected to Degree progress. Under "Your submissions", the Semester 1 plan is listed with status *submitted*. | Pending |
| **UAT-3** | Submit Course Plan (validation) | As `bob`, choose **Semester 2**, add **CSCI 123** (needs CSCI 122, not yet completed) and try to submit. | Submission is blocked. An inline error next to CSCI 123 names CSCI 122 as the missing prerequisite. The selection is kept as an editable draft. | Pending |
| **UAT-4** | Review and Approve Plan | Sign in as `advisor` (Bob's advisor). Open Plan reviews. | Bob's Semester 1 plan is listed with his name, degree, CSCI 122 and the submission date. | Pending |
| **UAT-5** | Review and Approve Plan (revisions) | As `advisor`, leave the feedback box empty and click Request revisions, then enter feedback and click Request revisions again. | The empty attempt is refused with a message. With feedback, the plan leaves the pending list. As `bob`, the Course Plan page shows the advisor's feedback and lets him edit and resubmit; after resubmitting, the plan is back in the advisor's list. | Pending |
| **UAT-6** | Review and Approve Plan (approval) | As `advisor`, click Approve on Bob's pending plan. Then sign in as `bob` and open Degree progress. | The plan leaves the advisor's pending list. Bob's Current courses shows CSCI 122 for Semester 1 and it is no longer in his remaining courses. | Pending |
| **UAT-7** | Access control | As `bob`, open `/advisor/reviews` in the address bar. | Access is refused ("Advisor access is required."). | Pending |

---

## 2. Unit Test Plan

Scope: one module at a time, with its collaborators replaced by in-memory fakes. No database and no web server.
Location: `tests/unit/`. Run with `pytest -m unit`.

| Test ID | Module under test | File | What it verifies |
| :--- | :--- | :--- | :--- |
| **UT-1** Authentication | `AuthService`, `utilities/security.py` | `test_auth_service.py` | Valid credentials for bob, admin and advisor return a token carrying that user's id and role. Wrong password, another user's password, unknown user, wrong case and empty password all fail. Passwords are stored hashed (salted) and only the original password verifies. Registration hashes the password and assigns the `regular_user` role. |
| **UT-2** Credit calculation | `ProgressService` | `test_progress_calculation.py` | Earned credits are the sum of completed course credits. Remaining credits never go negative. Percent complete is rounded to 1 decimal and capped at 100. A degree with 0 required credits does not divide by zero. Semesters remaining assume 15 credits per semester (0, 1, 15, 16, 30, 31 credit boundaries). Approved current courses are listed but not counted as earned. No result when there is no student profile. |
| **UT-3** Plan status transitions | `CoursePlanService`, `AdvisorReviewService` | `test_plan_status_transitions.py` | Student: save keeps a *draft*; a valid plan becomes *submitted*; an unmet prerequisite (including one selected in the same plan), empty plan, course outside the degree, invalid semester or second submission for a semester blocks submission. Advisor: *submitted* becomes *approved* or *revision_requested*; revisions need feedback (max 2,000 characters); only the assigned advisor can decide; an already-decided plan cannot be reviewed again; a pending plan can be withdrawn. |

---

## 3. Integration Test Plan

Scope: routes + services + repositories + a real (in-memory SQLite) database, using the real login and session cookie.
Location: `tests/integration/`. Run with `pytest -m integration`.

| Test Flow | File | What it verifies |
| :--- | :--- | :--- |
| **IT-1** Login and access control | `test_auth_flow.py` | Each role is redirected to its own home page after login and receives a session cookie. Bad logins get no cookie. Anonymous users get the session-expired page. Logout ends the session. Students and admins are refused (403) on advisor routes; students are refused on the admin page. |
| **IT-2** View degree progress | `test_progress_page.py` | The seeded student sees degree, credits earned and credits to go. An account without a student profile sees the empty state. |
| **IT-3** Course plan submission | `test_course_plan_flow.py` | Student session + course selection + database: a valid plan is stored as *submitted*, with its courses and the student's advisor. An unmet prerequisite returns 422 and stores a *draft*. Draft save, delete and withdraw work. Only one submitted plan per semester, but different semesters are allowed. |
| **IT-4** Advisor authorization and approval | `test_advisor_review_flow.py` | A submitted plan appears only in the assigned advisor's inbox. Approval changes the status to *approved* and the course appears under Current courses on the student's progress page. Revision requests need feedback, reach the student, and the student can resubmit. Students, admins, anonymous users and other advisors cannot approve the plan. |
| **IT-5** Existing service-level tests | `test_progress_service.py`, `test_advisor_review_service.py` | Service + repository behaviour against the database: progress calculation from the seed data, prerequisite validation, advisor inbox filtering, approval and withdrawal. |

---

## Running the tests

```bash
pytest                  # everything
pytest -m unit          # unit tests only
pytest -m integration   # integration tests only
pytest -v               # one line per test 
```
