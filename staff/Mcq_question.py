import csv
from pymongo import MongoClient
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import FileSystemStorage
import json 
import uuid
from bson import ObjectId

# MongoDB connection
client = MongoClient('mongodb+srv://ihub:ihub@test-portal.lcgyx.mongodb.net/test_portal_db?retryWrites=true&w=majority')
db = client['test_portal_db']

questions_collection = db['MCQ_Questions_Library']

@csrf_exempt
def bulk_upload(request):
    if request.method == "POST" and request.FILES.get("file"):
        # Save the uploaded file temporarily
        file = request.FILES["file"]
        fs = FileSystemStorage(location="uploads/")
        filename = fs.save(file.name, file)
        file_path = fs.path(filename)
        
        try:
            # Process the CSV file with UTF-8-BOM encoding
            with open(file_path, "r", encoding="utf-8-sig") as csv_file:
                csv_reader = csv.DictReader(csv_file)
                questions = []
                for row in csv_reader:
                    # Clean up potential BOM issues
                    first_key = list(row.keys())[0]
                    question = row.get(first_key, "").strip() if '\ufeff' in first_key else row.get("question", "").strip()
                    option1 = row.get("option1", "").strip()
                    option2 = row.get("option2", "").strip()
                    option3 = row.get("option3", "").strip()
                    option4 = row.get("option4", "").strip()
                    answer = row.get("answer", "").strip()
                    level = row.get("Level", "").strip().lower()  # Fetch level from file
                    tags = row.get("tags", "").strip().split(",") if "tags" in row else []  # Parse tags as a list

                    # If level is missing or invalid, use 'general' as the default level
                    if not level or level not in {"easy", "medium", "hard"}:
                        level = "general"

                    # Skip rows with missing critical information
                    if not all([question, option1, option2, option3, option4, answer]):
                        print(f"Skipping invalid row: {row}")
                        continue

                    # Validate answer is one of the options
                    options = [option1, option2, option3, option4]
                    if answer not in options:
                        print(f"Invalid answer for question: {question}")
                        continue

                    # Prepare question data with the level from the CSV
                    question_data = {
                        "question_id": str(uuid.uuid4()), 
                        "question": question,
                        "options": options,
                        "answer": answer,
                        "level": level,  # Use level from CSV or default to 'general'
                        "tags": tags
                    }
                    questions.append(question_data)

                # Insert all questions into MongoDB
                if questions:
                    # Debug: Print the prepared data
                    print(f"Prepared questions for insertion: {questions}")

                    # Insert questions into MongoDB
                    result = questions_collection.insert_many(questions)

                    # Debug: Check the result of insertion
                    print(f"Inserted {len(result.inserted_ids)} questions with levels: {[q['level'] for q in questions]}")
                    return JsonResponse({
                        "message": f"File uploaded and {len(result.inserted_ids)} questions stored in MongoDB successfully!",
                        "inserted_count": len(result.inserted_ids)
                    }, status=200)
                else:
                    return JsonResponse({"error": "No valid questions found in the CSV file."}, status=400)
        
        except csv.Error as csv_error:
            print(f"CSV Error: {csv_error}")
            return JsonResponse({"error": f"CSV parsing error: {str(csv_error)}"}, status=400)
        except Exception as e:
            print(f"Unexpected error: {e}")
            return JsonResponse({"error": str(e)}, status=400)
        finally:
            # Clean up the uploaded file
            fs.delete(filename)
    
    return JsonResponse({"error": "Invalid request. Please upload a file."}, status=400)





@csrf_exempt
def upload_single_question(request):
    if request.method == "POST":
        try:
            # Parse JSON data from the request body
            data = json.loads(request.body)
            
            # Extract question details
            question = data.get("question", "").strip()
            option1 = data.get("option1", "").strip()
            option2 = data.get("option2", "").strip()
            option3 = data.get("option3", "").strip()
            option4 = data.get("option4", "").strip()
            answer = data.get("answer", "").strip()
            level = data.get("level", "general").strip()  # Fix inconsistent key
            tags = data.get("tags", [])  # Default to an empty list if no tags provided

            # Validate input
            if not all([question, option1, option2, option3, option4, answer]):
                return JsonResponse({
                    "error": "Missing required fields. Please provide all question details."
                }, status=400)

            # Validate answer is one of the options
            options = [option1, option2, option3, option4]
            if answer not in options:
                return JsonResponse({
                    "error": "Invalid answer. The answer must be one of the provided options."
                }, status=400)

            # Prepare question data
            question_data = {
                "question_id": str(uuid.uuid4()), 
                "question": question,
                "options": options,
                "answer": answer,
                "level": level,
                "tags": tags
            }

            # Insert the question into MongoDB
            result = questions_collection.insert_one(question_data)
            
            return JsonResponse({
                "message": "Question uploaded successfully!",
                "question_id": str(result.inserted_id)
            }, status=200)
        
        except json.JSONDecodeError:
            return JsonResponse({
                "error": "Invalid JSON format. Please send a valid JSON payload."
            }, status=400)
        except Exception as e:
            return JsonResponse({
                "error": f"An unexpected error occurred: {str(e)}"
            }, status=500)
    
    return JsonResponse({
        "error": "Only POST requests are allowed."
    }, status=405)


def fetch_all_questions(request):
    try:
        # Get query parameters for filtering and searching
        level = request.GET.get('level', '').strip()
        tags = request.GET.getlist('tags')  # Supports multiple tags as a list
        search = request.GET.get('search', '').strip()

        # Build the MongoDB query
        query = {}
        if level:
            query['level'] = level
        if tags:
            query['tags'] = {'$all': tags}  # Matches all specified tags
        if search:
            query['$or'] = [
                {'question': {'$regex': re.escape(search), '$options': 'i'}},  # Case-insensitive search in question
                {'tags': {'$regex': re.escape(search), '$options': 'i'}}  # Case-insensitive search in tags
            ]

        # Fetch filtered data from MongoDB
        questions = list(questions_collection.find(query, {'_id': 0}))  # Exclude MongoDB's _id field
        
        return JsonResponse({"questions": questions}, status=200)
    
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def update_question(request, question_id):
    """
    Update an existing question in the database using a PUT request.
    """
    if request.method == "PUT":
        try:
            # Parse JSON payload
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError as e:
                return JsonResponse({"error": f"Invalid JSON payload: {str(e)}"}, status=400)

            # Extract and clean fields
            question = data.get("question", "").strip()
            options = data.get("options", [])
            answer = data.get("answer", "").strip()
            level = data.get("level", "general").strip()
            tags = data.get("tags", [])

            # Input validation
            errors = []
            if not question:
                errors.append("Question text cannot be empty.")
            if len(options) != 4 or len(set(options)) != 4:
                errors.append("Exactly 4 unique options are required.")
            if not answer:
                errors.append("Answer cannot be empty.")
            if answer not in options:
                errors.append("Answer must be one of the provided options.")
            if errors:
                return JsonResponse({"error": errors}, status=400)

            # Build the update payload
            update_data = {
                "question": question,
                "options": options,
                "answer": answer,
                "level": level,
                "tags": tags,
            }

            # Execute the update query using question_id
            result = questions_collection.update_one(
                {"question_id": question_id}, {"$set": update_data}
            )

            # Check update status
            if result.matched_count == 0:
                return JsonResponse({"error": "Question not found"}, status=404)

            return JsonResponse({"message": "Question updated successfully"}, status=200)

        except Exception as e:
            return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)

    return JsonResponse({"error": "Only PUT requests are allowed"}, status=405)




import logging

logger = logging.getLogger(__name__)



@csrf_exempt
def delete_question(request, question_id):
    if request.method == "DELETE":
        try:
            logger.debug(f"Attempting to delete question_id: {question_id}")
            result = questions_collection.delete_one({"question_id": question_id})
            logger.debug(f"Deleted count: {result.deleted_count}")

            if result.deleted_count == 0:
                return JsonResponse({"error": "Question not found"}, status=404)

            return JsonResponse({"message": "Question deleted successfully"}, status=200)

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)

    return JsonResponse({"error": "Only DELETE requests are allowed"}, status=405)