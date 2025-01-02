# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from pymongo import MongoClient
import json
import jwt
import datetime
import csv
from io import StringIO
import logging
from bson.objectid import ObjectId
from rest_framework.exceptions import AuthenticationFailed  # Import this exception
from datetime import datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny  # Correct import for utcnow()

# Initialize MongoDB client
client = MongoClient("mongodb+srv://ihub:ihub@test-portal.lcgyx.mongodb.net/test_portal_db?retryWrites=true&w=majority")
db = client["test_portal_db"]  # Replace with your database name
collection = db["MCQ_Assessment_Data"]  # Replace with your collection name
assessment_questions_collection = db["MCQ_Assessment_Data"]
mcq_report_collection = db["MCQ_Assessment_report"]
coding_report_collection = db["coding_report"]

logger = logging.getLogger(__name__)

SECRET_KEY = "Rahul"
JWT_SECRET = 'test'
JWT_ALGORITHM = "HS256"

from datetime import datetime, timedelta
import jwt
from django.http import JsonResponse

@csrf_exempt
def start_contest(request):
    if request.method == "POST":
        try:
            # Parse the incoming request body
            data = json.loads(request.body)
            contest_id = data.get("contestId")
            if not contest_id:
                return JsonResponse({"error": "Contest ID is required"}, status=400)
            
            # Generate a JWT token
            payload = {
                "contestId": contest_id,
                "exp": datetime.utcnow() + timedelta(hours=1),  # Token valid for 1 hour
            }
            token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

            return JsonResponse({"token": token}, status=200)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=400)



def generate_token(contest_id):
    payload = {
        "contest_id": contest_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)  # Token expiration
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def decode_token(token):
    print("Decode")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        contest_id = payload.get("contestId")  # Ensure correct key
        if not contest_id:
            raise ValueError("Invalid token: 'contestId' not found.")
        return contest_id
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired.")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token.")


from datetime import datetime

@csrf_exempt
def save_data(request):
    if request.method == "POST":
        try:
             # 1. Extract and decode the JWT token from cookies
            jwt_token = request.COOKIES.get("jwt")
            print(f"JWT Token: {jwt_token}")
            if not jwt_token:
                logger.warning("JWT Token missing in cookies")
                raise AuthenticationFailed("Authentication credentials were not provided.")

            try:
                decoded_token = jwt.decode(jwt_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                logger.info("Decoded JWT Token: %s", decoded_token)
            except jwt.ExpiredSignatureError:
                logger.error("Expired JWT Token")
                raise AuthenticationFailed("Access token has expired. Please log in again.")
            except jwt.InvalidTokenError:
                logger.error("Invalid JWT Token")
                raise AuthenticationFailed("Invalid token. Please log in again.")

            staff_id = decoded_token.get("staff_user")
            if not staff_id:
                logger.warning("Invalid payload: 'staff_user' missing")
                raise AuthenticationFailed("Invalid token payload.")

            data = json.loads(request.body)
            data["staffId"] = staff_id
            contest_id = data.get("contestId")
            if not contest_id:
                return JsonResponse({"error": "contestId is required"}, status=400)

            # Check if 'assessmentOverview' exists and contains the necessary fields
            if "assessmentOverview" not in data or "registrationStart" not in data["assessmentOverview"] or "registrationEnd" not in data["assessmentOverview"]:
                return JsonResponse({"error": "'registrationStart' or 'registrationEnd' is missing in 'assessmentOverview'"}, status=400)

            # Log the incoming data for debugging
            print("Incoming Data:", data)

            # Convert registrationStart and registrationEnd to datetime objects
            try:
                data["assessmentOverview"]["registrationStart"] = datetime.fromisoformat(data["assessmentOverview"]["registrationStart"])
                data["assessmentOverview"]["registrationEnd"] = datetime.fromisoformat(data["assessmentOverview"]["registrationEnd"])
            except ValueError as e:
                return JsonResponse({"error": f"Invalid date format: {str(e)}"}, status=400)

            collection.insert_one(data)
            return JsonResponse({"message": "Data saved successfully", "contestId": contest_id}, status=200)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=400)


@csrf_exempt
def save_question(request):
    if request.method == "POST":
        try:
            # Validate Authorization Header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return JsonResponse({"error": "Authorization header missing or invalid."}, status=401)

            # Decode the token to get the contest_id
            token = auth_header.split(" ")[1]
            contest_id = decode_token(token)

            # Parse the request body
            data = json.loads(request.body)
            questions = data.get("questions", [])
            if not questions:
                return JsonResponse({"error": "No questions provided"}, status=400)

            # Check if the contest_id already exists
            assessment = assessment_questions_collection.find_one({"contestId": contest_id})
            if not assessment:
                # If the contest does not exist, create it
                print(f"Creating new contest entry for contest_id: {contest_id}")
                assessment_questions_collection.insert_one({
                    "contestId": contest_id,
                    "questions": []
                })
                assessment = {"contestId": contest_id, "questions": []}

            # Append new questions to the contest
            existing_questions = assessment.get("questions", [])
            question_ids = {q.get("question_id") for q in existing_questions}  # Get existing question IDs

            new_questions = []
            for question in questions:
                if question.get("question_id") not in question_ids:
                    new_questions.append(question)

            # Add only unique questions
            if new_questions:
                assessment_questions_collection.update_one(
                    {"contestId": contest_id},
                    {"$addToSet": {"questions": {"$each": new_questions}}}
                )

            return JsonResponse({
                "message": "Questions saved successfully!",
                "added_questions": new_questions
            }, status=200)

        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=401)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}"}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=405)

@csrf_exempt
def get_questions(request):
    if request.method == "GET":
        print("GET request received")
        try:
            # Validate Authorization Header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                print("Authorization header missing or invalid")
                return JsonResponse({"error": "Unauthorized access"}, status=401)

            # Decode the token to get the contest_id
            token = auth_header.split(" ")[1]
            contest_id = decode_token(token)
            print(f"Decoded contest ID: {contest_id}")

            # Check if the contest exists in the database
            assessment = assessment_questions_collection.find_one({"contestId": contest_id})
            if not assessment:
                # If no contest found, create a new entry with an empty questions list
                print(f"Creating new contest entry for contest_id: {contest_id}")
                assessment_questions_collection.insert_one({
                    "contestId": contest_id,
                    "questions": []
                })
                assessment = {"contestId": contest_id, "questions": []}

            # Fetch the questions
            questions = assessment.get("questions", [])
            print(f"Fetched questions: {questions}")
            return JsonResponse({"questions": questions}, status=200)
        except ValueError as e:
            print(f"Authorization error: {str(e)}")
            return JsonResponse({"error": str(e)}, status=401)
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=400)

@csrf_exempt
def update_question(request):
    if request.method == "PUT":
        try:
            token = request.headers.get("Authorization").split(" ")[1]
            contest_id = decode_token(token)

            data = json.loads(request.body)
            question_id = data.get("question_id")

            result = assessment_questions_collection.update_one(
                {
                    "contest_id": contest_id,
                    "questions.question_id": question_id,
                },
                {
                    "$set": {
                        "questions.$.questionType": data.get("questionType", "MCQ"),
                        "questions.$.question": data.get("question", ""),
                        "questions.$.options": data.get("options", []),
                        "questions.$.correctAnswer": data.get("correctAnswer", ""),
                        "questions.$.mark": data.get("mark", 0),
                        "questions.$.negativeMark": data.get("negativeMark", 0),
                        "questions.$.randomizeOrder": data.get("randomizeOrder", False),
                    }
                }
            )

            if result.matched_count == 0:
                return JsonResponse({"error": "Question not found"}, status=404)

            return JsonResponse({"message": "Question updated successfully"})
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=401)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=400)


@csrf_exempt
def finish_contest(request):
    if request.method == "POST":
        try:
            # Validate Authorization Header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return JsonResponse({"error": "Authorization header missing or invalid."}, status=401)

            # Decode the token to get the contest_id
            token = auth_header.split(" ")[1]
            contest_id = decode_token(token)

            # Get the list of questions from the request body
            data = json.loads(request.body)
            questions_data = data.get("questions", [])

            if not questions_data:
                return JsonResponse({"error": "No question data provided."}, status=400)

            # Retrieve the existing entry for the contest_id
            existing_entry = collection.find_one({"contestId": contest_id})

            if existing_entry:
                # Update the existing entry with the new questions data
                collection.update_one(
                    {"contestId": contest_id},
                    {"$set": {"questions": questions_data}}  # Save the entire questions data
                )
            else:
                # If no entry exists for this contest_id, create a new one with all the question data
                collection.insert_one({
                    "contestId": contest_id,
                    "questions": questions_data,  # Store the full question data here
                    "assessmentOverview": {},  # Preserve the structure
                    "testConfiguration": {}
                })

            return JsonResponse({"message": "Contest finished successfully!"}, status=200)
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=401)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=400)


@csrf_exempt
def bulk_upload_questions(request):
    if request.method == "POST":
        try:
            # Validate Authorization Header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return JsonResponse({"error": "Authorization header missing or invalid."}, status=401)

            # Decode the token to get the contest_id
            token = auth_header.split(" ")[1]
            contest_id = decode_token(token)

            # Retrieve the uploaded file
            file = request.FILES.get("file")
            if not file:
                return JsonResponse({"error": "No file uploaded"}, status=400)

            # Parse CSV content
            file_data = file.read().decode("utf-8")
            csv_reader = csv.DictReader(StringIO(file_data))
            questions = []

            for row in csv_reader:
                try:
                    logger.debug("Processing row: %s", row)
                    # Extract and validate fields
                    mark = int(row.get("mark", 0)) if row.get("mark") else 0
                    negative_mark = int(row.get("negative_marking", 0)) if row.get("negative_marking") else 0
                    # question_id = str(uuid4())  # Generate unique ID

                    question = {
                        # "questionId": question_id,
                        "questionType": "MCQ",  # Assuming MCQ for bulk upload
                        "question": row.get("question", "").strip(),
                        "options": [
                            row.get("option_1", "").strip(),
                            row.get("option_2", "").strip(),
                            row.get("option_3", "").strip(),
                            row.get("option_4", "").strip(),
                            row.get("option_5", "").strip(),
                            row.get("option_6", "").strip(),
                        ],
                        "correctAnswer": row.get("correct_answer", "").strip(),
                        "mark": mark,
                        "negativeMark": negative_mark,
                        "randomizeOrder": False,  # Default to False
                        "level": row.get("level", "easy").strip(),  # Default level to "easy"
                        "tags": row.get("tags", "").split(",") if row.get("tags") else [],  # Convert tags to list
                    }
                    questions.append(question)
                except Exception as e:
                    logger.error("Error processing row: %s", row)
                    logger.error("Error: %s", str(e))
                    return JsonResponse({"error": f"Error in row: {row}. Details: {str(e)}"}, status=400)

            # Log the parsed questions
            logger.debug("Parsed Questions: %s", questions)

            return JsonResponse({"questions": questions}, status=200)
        except ValueError as e:
            logger.error("ValueError: %s", str(e))
            return JsonResponse({"error": str(e)}, status=401)
        except Exception as e:
            logger.error("Exception: %s", str(e))
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=400)
@csrf_exempt
def publish_mcq(request):
    if request.method == 'POST':
        try:
            # Validate Authorization Header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return JsonResponse({"error": "Authorization header missing or invalid."}, status=401)

            # Decode the token to get the contest_id
            token = auth_header.split(" ")[1]
            contest_id = decode_token(token)

            data = json.loads(request.body)
            print("contest_id: ",contest_id)

            selected_students = data.get('students', [])

            # Validate input
            if not contest_id:
                return JsonResponse({'error': 'Contest ID is required'}, status=400)
            if not isinstance(selected_students, list) or not selected_students:
                return JsonResponse({'error': 'No students selected'}, status=400)

            # Check if the contest document exists
            existing_document = collection.find_one({"contestId": contest_id})
            if not existing_document:
                return JsonResponse({'error': 'Contest not found'}, status=404)

            # Append questions and students to the existing document
            collection.update_one(
                {"contestId": contest_id},
                {
                    '$addToSet': {
                        'visible_to': {'$each': selected_students},  # Append new students
                    }
                }
            )

            return JsonResponse({'message': 'Questions and students appended successfully!'}, status=200)

        except Exception as e:
            return JsonResponse({'error': f'Error appending questions and students: {str(e)}'}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
def get_mcqquestions(request, contestId):
    if request.method == "GET":
        try:
            # Find the contest/assessment document based on the contest_id
            assessment = collection.find_one({"contestId": contestId})
            if not assessment:
                return JsonResponse(
                    {"error": f"No assessment found for contestId: {contestId}"}, status=404
                )

            # Extract questions and test configurations
            questions = assessment.get("questions", [])
            test_configuration = assessment.get("testConfiguration", {})

            # Check for question shuffling configuration
            if test_configuration.get("shuffleQuestions", False):
                import random
                random.shuffle(questions)

            # Check for options shuffling configuration for each question
            for question in questions:
                if question.get("randomizeOrder", False):
                    import random
                    random.shuffle(question["options"])

            # Format the response
            response_data = {
                "assessmentName": assessment["assessmentOverview"].get("name"),
                "duration": test_configuration.get("duration"),
                "questions": [
                    {
                        "text": question.get("question"),
                        "options": question.get("options"),
                        "mark": question.get("mark"),
                        "negativeMark": question.get("negativeMark"),
                    }
                    for question in questions
                ],
            }

            return JsonResponse(response_data, safe=False, status=200)

        except Exception as e:
            return JsonResponse(
                {"error": f"Failed to fetch MCQ questions: {str(e)}"}, status=500
            )
    else:
        return JsonResponse({"error": "Invalid request method"}, status=405)





# Assume `collection` and `mcq_report_collection` are your MongoDB collections

@csrf_exempt
def submit_mcq_assessment(request):
    if request.method == "POST":
        try:
            # Parse the incoming request data
            data = json.loads(request.body)
            contest_id = data.get("contestId")
            answers = data.get("answers", {})
            warnings = data.get("warnings", 0)  # Assuming warnings are passed in the request
            jwt_token = request.COOKIES.get("jwt")

            # Validate JWT token
            if not jwt_token:
                raise AuthenticationFailed("Authentication credentials were not provided.")

            try:
                decoded_token = jwt.decode(jwt_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            except jwt.ExpiredSignatureError:
                raise AuthenticationFailed("Access token has expired. Please log in again.")
            except jwt.InvalidTokenError:
                raise AuthenticationFailed("Invalid token. Please log in again.")

            student_id = decoded_token.get("student_id")
            if not student_id:
                raise AuthenticationFailed("Invalid token payload.")

            # Validate the contest_id and answers
            if not contest_id:
                return JsonResponse({"error": "Contest ID is required"}, status=400)
            if not answers:
                return JsonResponse({"error": "No answers provided"}, status=400)

            # Fetch the assessment questions from the database
            assessment = collection.find_one({"contestId": contest_id})
            if not assessment:
                return JsonResponse(
                    {"error": f"No assessment found for contestId: {contest_id}"},
                    status=404,
                )

            questions = assessment.get("questions", [])
            score = 0
            total_marks = 0
            attended_questions = []

            # Evaluate the answers
            for index, question in enumerate(questions):
                try:
                    # Sanitize and cast mark to integer
                    mark = int(float(str(question.get("mark", 0)).strip('"')))
                except (ValueError, TypeError):
                    mark = 0  # Default to 0 if invalid

                total_marks += mark
                is_correct = answers.get(str(index)) == question.get("correctAnswer")
                score += mark if is_correct else 0

                # Record attended question details
                attended_questions.append({
                    "title": question.get("question"),
                    "student_answer": answers.get(str(index)),
                    "correct_answer": question.get("correctAnswer"),
                })

            percentage = (score / total_marks) * 100 if total_marks > 0 else 0
            grade = "A" if percentage >= 90 else "B" if percentage >= 75 else "C" if percentage >= 50 else "F"

            # Update or insert into the MCQ_Assessment_report collection
            report = mcq_report_collection.find_one({"contest_id": contest_id})

            if not report:
                # If no report exists, create a new one
                mcq_report_collection.insert_one({
                    "contest_id": contest_id,
                    "students": [
                        {
                            "student_id": student_id,
                            "status": "Completed",
                            "grade": grade,
                            "attended_question": attended_questions,
                            "warnings": warnings,  # Insert warnings here
                            "startTime": datetime.utcnow(),
                            "finishTime": datetime.utcnow(),
                        }
                    ],
                })
            else:
                # Update the existing report
                students = report.get("students", [])
                for student in students:
                    if student["student_id"] == student_id:
                        student["status"] = "Completed"
                        student["grade"] = grade
                        student["attended_question"] = attended_questions
                        student["warnings"] = warnings  # Update warnings here
                        student["finishTime"] = datetime.utcnow()
                        break
                else:
                    # Add a new student entry if not found
                    students.append({
                        "student_id": student_id,
                        "status": "Completed",
                        "grade": grade,
                        "attended_question": attended_questions,
                        "warnings": warnings,  # Add warnings here
                        "startTime": datetime.utcnow(),
                        "finishTime": datetime.utcnow(),
                    })

                # Update the report in the database
                mcq_report_collection.update_one(
                    {"contest_id": contest_id},
                    {"$set": {"students": students}}
                )

            # Return the result
            result = {
                "contestId": contest_id,
                "score": score,
                "totalMarks": total_marks,
                "percentage": percentage,
                "grade": grade
            }
            return JsonResponse(result, status=200)

        except Exception as e:
            return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)
    else:
        return JsonResponse({"error": "Invalid request method"}, status=405)




@csrf_exempt
def get_student_report(request, contestId, regno):
    if request.method == "GET":
        try:
            # Fetch the contest report
            report = mcq_report_collection.find_one({"contest_id": contestId})
            if not report:
                return JsonResponse({"error": f"No report found for contest_id: {contestId}"}, status=404)

            # Find the student in the report
            student_report = next(
                (student for student in report.get("students", []) if student["student_id"] == regno), None
            )
            if not student_report:
                return JsonResponse({"error": f"No report found for student with regno: {regno}"}, status=404)

            # Calculate the number of correct answers
            correct_answers = sum(
                1 for q in student_report.get("attended_question", []) if q.get("student_answer") == q.get("correct_answer")
            )

            # Format the response
            formatted_report = {
                "contest_id": contestId,
                "student_id": regno,
                "status": student_report.get("status"),
                "grade": student_report.get("grade"),
                "start_time": student_report.get("startTime"),
                "finish_time": student_report.get("finishTime"),
                "red_flags": student_report.get("warnings", 0),
                "attended_questions": [
                    {
                        "id": index + 1,
                        "question": q.get("title"),
                        "userAnswer": q.get("student_answer"),
                        "correctAnswer": q.get("correct_answer"),
                        "isCorrect": q.get("student_answer") == q.get("correct_answer"),
                    }
                    for index, q in enumerate(student_report.get("attended_question", []))
                ],
                "correct_answers": correct_answers,
                "passPercentage": report.get("passPercentage", 0),  # Include passPercentage
            }

            return JsonResponse(formatted_report, status=200, safe=False)

        except Exception as e:
            return JsonResponse({"error": f"Failed to fetch student report: {str(e)}"}, status=500)
    else:
        return JsonResponse({"error": "Invalid request method"}, status=405)


@api_view(["POST"])
@permission_classes([AllowAny])  # Ensure only authorized users can access
def publish_result(request, contestId):
    try:
        # Validate the contest_id
        if not contestId:
            return JsonResponse({"error": "Contest ID is required"}, status=400)

        # Update the ispublish flag in the database
        result = mcq_report_collection.update_one(
            {"contest_id": contestId},
            {"$set": {"ispublish": True}}
        )

        result = coding_report_collection.update_one(
            {"contest_id": contestId},
            {"$set": {"ispublish": True}}
        )

        if result.modified_count == 0:
            return JsonResponse({"error": "Contest not found or already published"}, status=404)

        return JsonResponse({"message": "Results published successfully"}, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

