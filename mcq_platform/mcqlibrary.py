from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import pymongo
import jwt


# MongoDB Setup
client = pymongo.MongoClient("mongodb+srv://ihub:ihub@test-portal.lcgyx.mongodb.net/test_portal_db?retryWrites=true&w=majority")
db = client["test_portal_db"]
questions_collection = db["MCQ_Questions_Library"]
mcq_assessment_collection = db["MCQ_Assessment_Data"]

@csrf_exempt
def fetch_all_questions(request):
    try:
        # Fetch all questions from the database
        if request.method != 'GET':
            return JsonResponse({'error': 'Invalid request method'}, status=405)

        questions = list(
            questions_collection.find({}, {"_id": 0, "question_id": 1, "question": 1, "level": 1, "tags": 1})
        )
        return JsonResponse({'questions': questions}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def save_selected_questions(request):
    if request.method == "POST":
        try:
            # Validate Authorization Header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return JsonResponse({"error": "Authorization header missing or invalid."}, status=401)

            # Decode the token to extract contest ID
            token = auth_header.split(" ")[1]
            decoded_token = jwt.decode(token, options={"verify_signature": False})
            contest_id = decoded_token.get("contestId")

            if not contest_id:
                return JsonResponse({"error": "Invalid token or missing contest ID"}, status=401)

            # Parse the request body
            data = json.loads(request.body)
            questions = data.get("questions", [])
            if not questions:
                return JsonResponse({"error": "No questions provided"}, status=400)

            # Transform each question into the required structure
            formatted_questions = []
            for question in questions:
                formatted_question = {
                    "questionType": "MCQ",  # Static type as shown in the structure
                    "question": question.get("question"),
                    "options": question.get("options", []),  # List of options
                    "correctAnswer": question.get("correctAnswer"),  # Correct answer
                    "mark": question.get("mark", 0),  # Default to 0 if not provided
                    "negativeMark": question.get("negativeMark", 0),  # Default to 0 if not provided
                    "randomizeOrder": question.get("randomizeOrder", False)  # Default to False
                }
                formatted_questions.append(formatted_question)

            # Check if the contest already exists
            contest_data = mcq_assessment_collection.find_one({"contestId": contest_id})
            if not contest_data:
                # Create a new contest entry with default values and the provided questions
                mcq_assessment_collection.insert_one({
                    "contestId": contest_id,
                    "assessmentOverview": {
                        "name": "Default Name",
                        "description": "Default Description",
                        "registrationStart": "2024-12-19T00:00",
                        "registrationEnd": "2024-12-20T00:00",
                        "guidelines": "Default Guidelines",
                    },
                    "testConfiguration": {
                        "sections": "1",
                        "questions": str(len(formatted_questions)),
                        "duration": {
                            "hours": "1",
                            "minutes": "0",
                        },
                        "fullScreenMode": True,
                        "faceDetection": False,
                        "deviceRestriction": False,
                        "noiseDetection": False,
                        "passPercentage": "50",
                        "negativeMarking": False,
                        "shuffleQuestions": False,
                        "shuffleOptions": False,
                        "resultVisibility": "Host Control",
                        "submissionRule": "",
                        "negativeMarkingType": "None",
                    },
                    "staffId": "6739d25a9dbecde851fec050",
                    "questions": formatted_questions,
                })
            else:
                # Append new questions to the existing contest
                existing_questions = contest_data.get("questions", [])
                existing_questions.extend(formatted_questions)
                mcq_assessment_collection.update_one(
                    {"contestId": contest_id},
                    {"$set": {
                        "questions": existing_questions,
                        "testConfiguration.questions": str(len(existing_questions)),
                    }}
                )

            return JsonResponse({
                "message": "Questions saved successfully!",
                "questions": formatted_questions,
            }, status=200)

        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=401)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=400)