from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import traceback
from pymongo import MongoClient
import os
from bson.objectid import ObjectId
from student.utils import *
# Update the MongoClient to use the provided connection string
client = MongoClient("mongodb+srv://ihub:ihub@test-portal.lcgyx.mongodb.net/test_portal_db?retryWrites=true&w=majority")
db = client["test_portal_db"]  # Ensure this matches the database name in your connection string
questions_collection = db['Coding_Questions_Library']
final_questions_collection = db['finalQuestions']
coding_assessments_collection = db['coding_assessments']
coding_report_collection = db['coding_report']

PROBLEMS_FILE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'Frontend', 'public', 'json', 'questions.json')

def fetch_Questions(request):
    try:
        # Query the MongoDB collection
        coding_questions = list(questions_collection.find({}, {'_id': 1, 'title': 1, 'level': 1, 'problem_statement': 1,'samples':1,'hidden_samples':1}))
        
        # Map _id to id (convert ObjectId to string)
        for question in coding_questions:
            question['id'] = str(question.pop('_id'))  # Rename `_id` to `id`
        
        # Return the questions as a JSON response
        return JsonResponse({'problems': coding_questions}, status=200)

    except PyMongoError as e:
        # Log the error (optional)
        print(f"Database error: {e}")

        # Return an error response
        return JsonResponse({'error': 'Failed to fetch questions from the database'}, status=500)

    except Exception as e:
        # Catch any other unexpected errors
        print(f"Unexpected error: {e}")
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)

def save_problem_data(new_problem):
    """
    Adds a new problem to the problems array in Coding_Questions_Library. If a document with ObjectId already exists,
    it appends the new problem to problems; otherwise, it creates a new document.
    """
    try:
        # Structure the problem data
        problem_data = {
            "id": new_problem.get('id'),
            "title": new_problem.get('title', ''),
            "role": new_problem.get('role', []),
            "level": new_problem.get('level', ''),
            "problem_statement": new_problem.get('problem_statement', ''),
            "samples": new_problem.get('samples', []),
            "hidden_samples": new_problem.get('hidden_samples', [])
        }

        # Convert the main document ID to ObjectId
        main_document_id = ObjectId('6731ed9e1005131d602865de')
        existing_document = questions_collection.find_one({'_id': main_document_id})

        if existing_document:
            # Append new problem to the problems array
            result = questions_collection.update_one(
                {'_id': main_document_id},
                {'$push': {'problems': problem_data}}
            )
            message = 'Problem added to existing document!'
        else:
            # Create a new document if it doesn’t exist, with the problems array initialized
            new_document = {
                "_id": main_document_id,
                "problems": [problem_data]
            }
            result = questions_collection.insert_one(new_document)
            message = 'New document created and problem added!'

        if result:
            return JsonResponse({
                'message': message,
                'problem_id': problem_data['id']
            }, status=201)
        else:
            raise Exception("Failed to save the document")

    except Exception as e:
        return JsonResponse({
            'error': f'Error saving problem data: {str(e)}'
        }, status=400)

@csrf_exempt
def publish_questions(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            contest_id = data.get('contestId')
            print("contest_id: ",contest_id)
            selected_questions = data.get('questions', [])
            selected_students = data.get('students', [])

            # Validate input
            if not contest_id:
                return JsonResponse({'error': 'Contest ID is required'}, status=400)
            if not isinstance(selected_questions, list) or not selected_questions:
                return JsonResponse({'error': 'No questions selected'}, status=400)
            if not isinstance(selected_students, list) or not selected_students:
                return JsonResponse({'error': 'No students selected'}, status=400)

            # Fetch selected questions' data
            all_problems = []
            for question_id in selected_questions:
                question_data = questions_collection.find_one({"_id": ObjectId(question_id)}, {"_id": 0})
                if question_data:
                    all_problems.append(question_data)

            # Check if the contest document exists
            existing_document = coding_assessments_collection.find_one({"contestId": contest_id})
            if not existing_document:
                return JsonResponse({'error': 'Contest not found'}, status=404)

            # Append questions and students to the existing document
            coding_assessments_collection.update_one(
                {"contestId": contest_id},
                {
                    '$addToSet': {
                        'problems': {'$each': all_problems},  # Append new questions
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
def modify_problem_data(new_problem):
    """
    Modifies an existing problem in `Coding_Questions_Library` based on its ID.
    """
    try:
        problem_id = new_problem.get("id")
        result = questions_collection.update_one(
            {'problems.id': problem_id},  # Match within the `problems` array by `id`
            {'$set': {'problems.$': new_problem}}  # Update the matched problem
        )

        if result.modified_count > 0:
            return JsonResponse({'message': 'Problem modified successfully!'}, status=200)
        else:
            return JsonResponse({'error': 'Problem not found or not modified'}, status=404)

    except Exception as e:
        print("Error modifying problem:", str(e))
        traceback.print_exc()
        return JsonResponse({'error': 'Failed to modify problem data'}, status=500)


def delete_problem_data(problem_id):
    """
    Deletes a problem from `Coding_Questions_Library` based on its ID within the `problems` array.
    """
    try:
        # Use `$pull` to remove the specific problem from the `problems` array
        result = questions_collection.update_one(
            {},  # Assuming there's only one document; otherwise, specify a filter if needed
            {'$pull': {'problems': {'id': problem_id}}}
        )

        if result.modified_count > 0:
            return JsonResponse({'message': 'Problem deleted successfully!'}, status=200)
        else:
            return JsonResponse({'error': 'Problem not found for deletion'}, status=404)

    except Exception as e:
        print("Error deleting problem:", str(e))
        traceback.print_exc()
        return JsonResponse({'error': 'Failed to delete problem data'}, status=500)


@csrf_exempt
def save_problem(request):
    """
    Handles saving, modifying, and deleting problems in `Coding_Questions_Library`.
    """
    if request.method == 'GET':
        return fetch_Questions(request)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_problem = data.get("problems", [])[0]
            return save_problem_data(new_problem)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            print("An error occurred:", str(e))
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)

    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            new_problem = data.get("problems", [])[0]
            return modify_problem_data(new_problem)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            print("An error occurred:", str(e))
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)

    elif request.method == 'DELETE':
        try:
            print("entered")
            data = json.loads(request.body)
            problem_id = data.get("id")
            print(problem_id)
            return delete_problem_data(problem_id)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            print("An error occurred:", str(e))
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)

    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
def upload_bulk_coding_questions(request):
    if request.method == "POST":
        try:
            # Check if file exists in request
            uploaded_file = request.FILES.get("file")
            if not uploaded_file:
                return JsonResponse({"error": "No file uploaded."}, status=400)

            # Read file content
            file_content = uploaded_file.read().decode("utf-8")
            
            # Parse JSON
            data = json.loads(file_content)
            if not isinstance(data, list):  # Expecting a list of coding questions
                return JsonResponse({"error": "Invalid JSON format. Expected an array."}, status=400)

            # Insert data into MongoDB
            result = questions_collection.insert_many(data)
            return JsonResponse({"message": f"Successfully uploaded {len(result.inserted_ids)} coding questions."})

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON file."}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)

    return JsonResponse({"error": "Invalid request method."}, status=405)

@csrf_exempt
def fetch_coding_questions(request):
    try:
        # Fetch all coding questions from MongoDB
        questions = list(questions_collection.find({}, {"_id": 0}))  # Exclude MongoDB ObjectId from response
        
        # Return questions as JSON
        return JsonResponse({"questions": questions}, safe=False)

    except Exception as e:
        return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)
    
# Assuming you have a function to get the MongoDB collection
def get_coding_report_collection():
    coding_report_collection = get_coding_report_collection()

@csrf_exempt
def get_coding_student_report(request, contestId, regno):
    if request.method == "GET":
        try:
            # Fetch the contest report
            report = coding_report_collection.find_one({"contest_id": contestId})
            if not report:
                return JsonResponse({"error": f"No report found for contest_id: {contestId}"}, status=404)

            # Find the student in the report
            student_report = next(
                (student for student in report.get("students", []) if student["student_id"] == regno), None
            )
            if not student_report:
                return JsonResponse({"error": f"No report found for student with regno: {regno}"}, status=404)

            # Format the response
            formatted_report = {
                "contest_id": contestId,
                "student_id": regno,
                "status": student_report.get("status"),
                "grade": student_report.get("grade"),
                "start_time": student_report.get("startTime"),
                "finish_time": student_report.get("finishTime"),
                "attended_questions": [
                    {
                        "id": index + 1,
                        "question": q.get("title"),
                        "result": q.get("result"),
                        "isCorrect": q.get("result") == "Correct",
                    }
                    for index, q in enumerate(student_report.get("attended_question", []))
                ],
            }

            return JsonResponse(formatted_report, status=200, safe=False)

        except Exception as e:
            return JsonResponse({"error": f"Failed to fetch student report: {str(e)}"}, status=500)
    else:
        return JsonResponse({"error": "Invalid request method"}, status=405)