from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from pymongo import MongoClient
import json

# Backend: Fetch and return all student details
@csrf_exempt
def student_profile(request):
    client = MongoClient('mongodb+srv://ihub:ihub@test-portal.lcgyx.mongodb.net/test_portal_db?retryWrites=true&w=majority')
    db = client['test_portal_db']
    collection = db['students']

    if request.method == 'GET':
        # Retrieve all student records
        students = list(collection.find({}, {'_id': 0}))  # Exclude MongoDB's _id field
        return JsonResponse({'students': students}, safe=False)

    elif request.method == 'POST':
        # Add or update student record
        try:
            data = json.loads(request.body)
            filter_query = {"regno": data["regno"]}  # Update based on unique 'regno'
            collection.update_one(filter_query, {"$set": data}, upsert=True)
            return JsonResponse({"message": "Student details updated successfully"}, status=201)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
