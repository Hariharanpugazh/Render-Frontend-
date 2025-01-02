import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from pymongo import MongoClient
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models_contest import ContestDetails
from datetime import datetime
from bson import ObjectId
import os
from django.utils import timezone


# Update the MongoClient to use the provided connection string
client = MongoClient("mongodb+srv://ihub:ihub@test-portal.lcgyx.mongodb.net/test_portal_db?retryWrites=true&w=majority")
db = client["test_portal_db"]  # Ensure this matches the database name in your connection string
contest_collection = db["Contest_Details"]
user_info_collection = db["User_info"]
final_questions_collection = db["finalQuestions"]
coding_assessment = db["coding_assessment"]
coding_report_collection = db['coding_report']


def get_contests(request):
    # Fetch all contests from the Contest_Details collection
    contests = list(contest_collection.find({}, {"_id": 0}))  
    return JsonResponse(contests, safe=False)

@csrf_exempt
def delete_contest(request, contest_id):
    if request.method == 'DELETE':
        try:
            # Find the contest by contest_id in the MongoDB collection and delete it
            result = contest_collection.delete_one({'contest_id': contest_id})
            if result.deleted_count == 0:
                return JsonResponse({'error': 'Contest not found'}, status=404)

            # Also delete the corresponding finalQuestions document
            final_questions_result = final_questions_collection.delete_one({'contestId': contest_id})
            if final_questions_result.deleted_count == 0:
                return JsonResponse({'warning': 'Contest deleted, but no corresponding finalQuestions found'}, status=200)

            return JsonResponse({'message': f'Contest with ID {contest_id} and its questions deleted successfully'}, status=200)
        except Exception as e:
            return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)



@csrf_exempt
def saveDetails(request):
    if request.method == "POST":
        # Parse JSON data from the request body
        data = json.loads(request.body)
        contest_name = data.get('contest_name', '')
        start_time = data.get('start_time', '')
        end_time = data.get('end_time', '')
        organization_type = data.get('organization_type', '')
        organization_name = data.get('organization_name', '')
        testType = data.get('ContestType', '')
        contest_id = data.get('contest_id', '')

        # Prepare data for MongoDB
        contest_data = {
            'contest_name': contest_name,
            'start_time': start_time,
            'end_time': end_time,
            'organization_type': organization_type,
            'organization_name': organization_name,
            'testType': testType,
            'contest_id': contest_id,
        }

        # Insert data into MongoDB collection
        try:
            contest_collection.insert_one(contest_data)
            return JsonResponse({"message": "Contest details saved successfully"})
        except Exception as e:
            return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)

    return JsonResponse({"error": "Invalid request method."}, status=405)

@csrf_exempt
def saveUserInfo(request):
    if request.method == "POST":
        # Parse JSON data from the request body
        data = json.loads(request.body)
        print("Received data:", data)  # Debugging line
        
        name = data.get('name', '')
        role = data.get('role', '')
        skills = data.get('skills', [])
        contest_id = data.get('contest_id', '')

        # Prepare data for MongoDB
        user_info_data = {
            'name': name,
            'role': role,
            'skills': skills,
            'contest_id': contest_id,
        }

        print("Data to save:", user_info_data)  # Debugging line

        # Insert data into MongoDB collection
        try:
            user_info_collection.insert_one(user_info_data)
            print("Data inserted successfully")  # Debugging line
            return JsonResponse({"message": "User information saved successfully"})
        except Exception as e:
            print("Error inserting data:", e)  # Debugging line
            return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)

    return JsonResponse({"error": "Invalid request method."}, status=405)



import random

@csrf_exempt
def start_test(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            contest_id = data.get("contest_id")
            student_id = data.get("student_id")

            # Validate inputs
            if not contest_id or not student_id:
                return JsonResponse({"error": "contest_id and student_id are required"}, status=400)

            # Clear the entire directory
            directory_path = os.path.join(os.path.dirname(__file__), '..', '..', 'Frontend', 'public', 'json')
            if os.path.exists(directory_path):
                # Remove all files in the directory
                for filename in os.listdir(directory_path):
                    file_path = os.path.join(directory_path, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)

            # Step 1: Update or insert into 'contest_activity'
            db.contest_activity.update_one(
                {"contest_id": contest_id, "student_id": student_id},
                {"$set": {"status": "started", "start_time": datetime.utcnow()}},
                upsert=True
            )

            # Step 2: Fetch contest assessment data
            assessment = db.coding_assessments.find_one({"contestId": contest_id}, {"_id": 0, "problems": 1, "testConfiguration": 1})
            if not assessment or "problems" not in assessment:
                return JsonResponse({"error": "No problems found for the given contest_id"}, status=404)

            problems = assessment["problems"]
            test_config = assessment.get("testConfiguration", {})
            questions_count = int(test_config.get("questions", 0))

            # If the number of questions is greater than the available problems, use the total number of problems
            if questions_count > len(problems):
                questions_count = len(problems)

            # Step 3: Randomly select the specified number of problems
            selected_problems = random.sample(problems, questions_count)

            # Step 4: Transform problems to the desired structure
            transformed_problems = {
                "problems": [
                    {
                        "id": index + 1,
                        "title": problem["title"],
                        "role": problem["role"],
                        "level": problem["level"],
                        "problem_statement": problem["problem_statement"],
                        "samples": problem["samples"],
                        "hidden_samples": problem["hidden_samples"],
                    }
                    for index, problem in enumerate(selected_problems)
                ]
            }

            # Step 5: Save transformed problems to a JSON file
            file_path = os.path.join(
                os.path.dirname(__file__), '..', '..', 'Frontend', 'public', 'json', 'questions.json'
            )
            os.makedirs(os.path.dirname(file_path), exist_ok=True)  # Ensure directory exists

            # Save the new file
            with open(file_path, "w") as json_file:
                json.dump(transformed_problems, json_file, indent=4)

            # Confirm file is written before responding
            if not os.path.exists(file_path):
                return JsonResponse({"error": "Failed to write file"}, status=500)

            return JsonResponse({
                "message": "Test started successfully, and problems saved.",
                "file_path": file_path
            }, status=200)

        except Exception as e:
            return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)


@csrf_exempt
def save_coding_report(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            contest_id = data.get("contest_id")
            student_id = data.get("student_id")

            # Validate inputs
            if not contest_id or not student_id:
                return JsonResponse({"error": "contest_id and student_id are required"}, status=400)

            # Prepare the student structure
            student_data = {
                "student_id": student_id,
                "status": "Pending",
                "grade": "Pending",
                "attended_question": [
                    {
                        "title": "Pending",
                        "result": "Pending"
                    }
                ],
                "startTime": datetime.utcnow(),
                "finishTime": "Pending"
            }

            # Update or insert into 'coding_report'
            db.coding_report.update_one(
                {"contest_id": contest_id},
                {"$addToSet": {"students": student_data}},  # Avoid duplicates for the same student
                upsert=True  # Create the document if it doesn't exist
            )

            return JsonResponse({"message": "Contest report updated successfully"}, status=200)

        except Exception as e:
            return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)



@csrf_exempt
def finish_test(request):
    if request.method == "POST":
        try:
            # Parse the payload
            data = json.loads(request.body)
            contest_id = data.get("contest_id")
            student_id = data.get("student_id")
            results = data.get("results", [])

            # Validate inputs
            if not contest_id or not student_id or not results:
                return JsonResponse({"error": "Missing required fields in the payload"}, status=400)

            # Fetch contest details from 'coding_assessments'
            contest = db.coding_assessments.find_one({"contestId": contest_id})
            if not contest:
                return JsonResponse({"error": "Contest not found in coding_assessments"}, status=404)

            # Get the pass percentage from test configuration
            test_config = contest.get("testConfiguration", {})
            pass_percentage = float(test_config.get("passPercentage", 0))

            # Calculate the grade
            total_questions = len(results)
            correct_answers = sum(1 for result in results if result.get("result") == "Correct")
            score_percentage = (correct_answers / total_questions) * 100
            grade = "Pass" if score_percentage >= pass_percentage else "Fail"

            # Prepare the attended question structure
            attended_questions = [
                {
                    "title": result.get("title", "Unknown"),  # Handle 'title' instead of 'problemId'
                    "result": result.get("result", "Pending")
                }
                for result in results
            ]

            # Check if the student exists in the array
            student_exists = db.coding_report.find_one({
                "contest_id": contest_id,
                "students.student_id": student_id
            })

            if student_exists:
                # Update the specific student in the students array
                db.coding_report.update_one(
                    {"contest_id": contest_id, "students.student_id": student_id},
                    {
                        "$set": {
                            "students.$.status": "Completed",
                            "students.$.grade": grade,
                            "students.$.attended_question": attended_questions,
                            "students.$.finishTime": timezone.now()
                        }
                    }
                )
            else:
                # Add a new student entry if the student doesn't exist
                new_student_data = {
                    "student_id": student_id,
                    "status": "Completed",
                    "grade": grade,
                    "attended_question": attended_questions,
                    "startTime": timezone.now(),
                    "finishTime": timezone.now()
                }
                db.coding_report.update_one(
                    {"contest_id": contest_id},
                    {"$addToSet": {"students": new_student_data}}
                )

            return JsonResponse({"message": "Test results processed successfully"}, status=200)

        except Exception as e:
            return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)




@csrf_exempt
def contest_stats(request, contest_id):
    """
    API to fetch stats for a specific contest.
    """
    try:
        # Fetch students registered for the contest
        total_students = user_info_collection.count_documents({"contest_id": contest_id})

        # Fetch the number of students who started the test
        started = db.contest_activity.count_documents({"contest_id": contest_id, "status": "started"})

        # Fetch the number of students who completed the test
        completed = db.contest_activity.count_documents({"contest_id": contest_id, "status": "completed"})

        # Return the stats as JSON
        return JsonResponse({
            "total_students": total_students,
            "started": started,
            "completed": completed,
        }, status=200)
    except Exception as e:
        return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)

@csrf_exempt
def contest_students(request, contest_id):
    """
    API to fetch students for a specific contest.
    """
    try:
        # Fetch student activities for the contest
        contest_activities = db.contest_activity.find({"contest_id": contest_id})

        student_list = []
        for activity in contest_activities:
            student_id = activity["student_id"]
            student = db.students.find_one({"_id": ObjectId(student_id)})

            if student:
                student_list.append({
                    "id": str(student["_id"]),
                    "name": student["name"],
                    "registration_number": student["regno"],
                    "department": student["dept"],
                    "collegename": student["collegename"],
                    "status": activity.get("status", "not_started"),
                })

        return JsonResponse(student_list, safe=False, status=200)
    except Exception as e:
        return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)


@csrf_exempt
def start_mcqtest(request):
    if request.method == "POST":
        try:
            # Parse request data
            data = json.loads(request.body)
            contest_id = data.get("contest_id")
            student_id = data.get("student_id")

            if not contest_id or not student_id:
                return JsonResponse({"error": "contest_id and student_id are required"}, status=400)

            # Debug: Log incoming data
            print(f"Contest ID: {contest_id}, Student ID: {student_id}")

            # Access the MCQ_Assessment_report collection
            mcq_report_collection = db['MCQ_Assessment_report']

            # Check if a report exists for the contest
            report = mcq_report_collection.find_one({"contest_id": contest_id})
            print(f"Existing report: {report}")

            if not report:
                # Create a new report if none exists
                result = mcq_report_collection.insert_one({
                    "contest_id": contest_id,
                    "students": [
                        {
                            "student_id": student_id,
                            "status": "started",
                            "startTime": datetime.utcnow(),
                            "ispublish": False
                        }
                    ],
                })
                print(f"Inserted new report with ID: {result.inserted_id}")
            else:
                # Update the existing report
                students = report.get("students", [])
                student_found = False

                for student in students:
                    if student["student_id"] == student_id:
                        student["status"] = "started"
                        student["startTime"] = datetime.utcnow()
                        student_found = True
                        break

                if not student_found:
                    # Add the student if not already in the list
                    students.append({
                        "student_id": student_id,
                        "status": "started",
                        "startTime": datetime.utcnow(),
                    })

                # Update the report
                update_result = mcq_report_collection.update_one(
                    {"contest_id": contest_id},
                    {"$set": {"students": students}}
                )
                print(f"Update result: {update_result.modified_count} documents updated")

            # Send the response
            return JsonResponse({"message": "Test started successfully."}, status=200)

        except Exception as e:
            # Log the exception for debugging
            print(f"Error: {str(e)}")
            return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)
    else:
        return JsonResponse({"error": "Invalid request method"}, status=405)


