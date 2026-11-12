# MyAdvisor - Test Plan and Strategy

## 1. User Acceptance Test Plan
Reference: Application Wireframes and Core Workflows

| Test ID | Module / Wireframe | Scenario / Description | Expected Outcome | Status |
| :--- | :--- | :--- | :--- | :--- |
| **User Acceptance Test 1** | Student Dashboard | Student logs in and reviews degree progress and completed credits. | Dashboard correctly displays pre-seeded degree progress, total credits, and remaining courses. | Pass |
| **User Acceptance Test 2** | Course Planning | Student selects courses for the upcoming semester and submits the plan. | System saves the course plan and updates the status to "Pending Approval". | Pass |
| **User Acceptance Test 3** | Advisor Review | Advisor logs in, views pending student submissions, and reviews selected courses against requirements. | Advisor dashboard lists the pending submission with accurate student and course details. | Pass |
| **User Acceptance Test 4** | Plan Approval | Advisor approves the pending course plan. | System updates plan status to "Approved" and reflects the change on the student view. | Pass |

---

## 2. Unit Test Plan
Scope: Isolated component and core logic testing using pre-seeded data structures.

* **Test 1 (Authentication Login Verification - `test_user_authentication`):** Verifies that authenticating with the valid pre-seeded student credentials (`bob` / `bobpass`) and advisor credentials (`admin` / `adminpass`) succeeds, while invalid credentials fail.
* **Test 2 (Course Plan Calculation / Credit Summation - `test_credit_calculation`):** Verifies that the internal logic correctly accumulates credit values from selected courses in a plan.
* **Test 3 (Course Plan Status State Machine - `test_plan_status_transitions`):** Verifies that a course plan initializes correctly and transitions its status accurately (e.g., from draft/pending to approved).

---

## 3. Integration Test Plan
Scope: Component interaction, database persistence, and workflow state transitions.

* **Test Flow 1 (Course Plan Submission Flow):** Test the integration between the student user session, course selection logic, and database state change from draft to "Pending Approval".
* **Test Flow 2 (Advisor Authorization & Approval Flow):** Test that user authorization restricts regular students from accessing advisor approval endpoints, and verify that an advisor successfully transitions a plan to "Approved".
