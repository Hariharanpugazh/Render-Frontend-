from django.http import JsonResponse
from pymongo import MongoClient

def studentstats(request, regno):
    client = MongoClient('mongodb+srv://ihub:ihub@test-portal.lcgyx.mongodb.net/test_portal_db?retryWrites=true&w=majority')
    db = client['test_portal_db']

    # Fetch student data
    student_data = db.students.find_one({"regno": regno})
    if not student_data:
        return JsonResponse({"error": "Student not found"}, status=404)

    # Fetch contest data visible to the student
    contest_data = db.coding_assessments.find({"visible_to": regno}, {"_id": 0})
    contest_list = list(contest_data)

    # Fetch all contest IDs visible to the student
    contest_ids = [contest.get("contestId") for contest in contest_list if contest.get("contestId")]

    # Fetch coding report for contests relevant to the student
    coding_reports = db.coding_report.find({"contest_id": {"$in": contest_ids}})
    coding_report_map = {report["contest_id"]: report for report in coding_reports}

    # Determine test statuses
    completed_tests = 0
    in_progress_tests = 0

    for contest_id in contest_ids:
        report = coding_report_map.get(contest_id)

        if not report:
            # No report means the test is in progress
            in_progress_tests += 1
        else:
            # Find the status for the current student
            student_status = None
            for student in report["students"]:
                if str(student["student_id"]) == str(student_data["_id"]):
                    student_status = student.get("status")
                    break

            if student_status == "Completed":
                completed_tests += 1
            else:
                in_progress_tests += 1

    # Response with all assessment details
    assessments = []
    for contest in contest_list:
        assessment_overview = contest.get("assessmentOverview", {})
        problems = []
        contest_status = "Yet to Start"  # Default status for contest

        # Check the contest status based on the coding report
        report = coding_report_map.get(contest.get("contestId"))
        if report:
            for student in report["students"]:
                if str(student["student_id"]) == str(student_data["_id"]):
                    contest_status = student.get("status", "Pending")  # Get the contest status
                    break

        # Handle problems based on contest status
        if contest_status == "Completed":
            for student in report["students"]:
                if str(student["student_id"]) == str(student_data["_id"]):
                    attended_questions = student.get("attended_question", [])
                    for attended_problem in attended_questions:
                        problems.append({
                            "title": attended_problem.get("title", ""),
                            "result": attended_problem.get("result", ""),
                            "level": attended_problem.get("level", ""),
                            "problem_statement": attended_problem.get("problem_statement", "")
                        })
                    break
        elif contest_status == "Pending":
            problems = "Pending"
        else:  # Yet to Start
            problems = "No problems yet"

        # Add assessment details for this contest
        assessments.append({
            "contestId": contest.get("contestId", ""),
            "name": assessment_overview.get("name", ""),
            "description": assessment_overview.get("description", ""),
            "registrationStart": assessment_overview.get("registrationStart", ""),
            "registrationEnd": assessment_overview.get("registrationEnd", ""),
            "guidelines": assessment_overview.get("guidelines", ""),
            "questions": contest.get("testConfiguration", {}).get("questions", ""),
            "duration": contest.get("testConfiguration", {}).get("duration", ""),
            "passPercentage": contest.get("testConfiguration", {}).get("passPercentage", ""),
            "problems": problems,
            "contestStatus": contest_status  # Added contest status
        })

    response_data = {
        "student": {
            "name": student_data.get("name", ""),
            "email": student_data.get("email", ""),
            "collegename": student_data.get("collegename", ""),
            "dept": student_data.get("dept", ""),
            "regno": regno,
        },
        "performance": {
            "total_tests": len(contest_ids),
            "completed_tests": completed_tests,
            "in_progress_tests": in_progress_tests,
            "average_score": 0,  # Placeholder for average score logic
        },
        "assessments": assessments
    }

    return JsonResponse(response_data)
