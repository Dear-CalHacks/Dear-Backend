from flask import Blueprint, jsonify, request
from db import userCollection ,  patientCollection # Import the MongoDB userCollection
from bson import ObjectId

# Create a blueprint for routes
routes = Blueprint('routes', __name__)

# Home route
@routes.route('/')
def home():
    return "Flask HTTP server is running on port 8080!"

# POST route to add data
import uuid

@routes.route('/add-data', methods=['POST'])
def add_data():
    try:
        data = request.get_json()
        
        # Insert the data into the MongoDB collection
        result = userCollection.insert_one(data)
        
        return jsonify({"message": "Family member added successfully", "id": str(result.inserted_id)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@routes.route('/add-data-patient', methods=['POST'])
def add_data_patient():
    try:
        data = request.get_json()
        
        # Insert the data into the MongoDB collection
        result = patientCollection.insert_one(data)
        
        return jsonify({"message": "Patient added successfully", "id": str(result.inserted_id)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@routes.route('/get-user-by-id/<string:user_id>', methods=['GET'])
def get_user_by_id(user_id):
    try:
        print(user_id)
        # Retrieve user by user_id
        user = userCollection.find_one({"_id": ObjectId(user_id)})
        print(user)
        
        if user is None:
            return jsonify({"message": "User not found"}), 404
        
        # Convert the ObjectId to string for JSON response
        user['_id'] = str(user['_id'])
        
        return jsonify(user), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@routes.route('/get-patient-by-id/<string:patient_id>', methods=['GET'])
def get_patient_by_id(patient_id):
    try:
        print(patient_id)
        # Retrieve user by user_id
        patient = patientCollection.find_one({"patient_id": patient_id})
        print(patient)
        
        if patient is None:
            return jsonify({"message": "User not found"}), 404
        
        # Convert the ObjectId to string for JSON response
        patient['_id'] = str(patient['_id'])
        
        return jsonify(patient), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@routes.route('/get-user-by-patient-id/<string:patient_id>', methods=['GET'])
def get_user_by_patient_id(patient_id):
    try:
        print(patient_id)
        # Retrieve user by user_id
        print("Looking up users associated with patient_id:", patient_id)
        
        # Retrieve all users with the given patient_id
        users = list(userCollection.find({"patient_id": patient_id}))
        print(users)
        
        # Convert ObjectId to string for JSON response
        for user in users:
            user['_id'] = str(user['_id'])

        if not users:
            return jsonify({"message": "No users found"}), 404
        
        return jsonify(users), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 50


# GET route to retrieve all data
@routes.route('/get-data', methods=['GET'])
def get_data():
    try:
        data = list(userCollection.find())
        for doc in data:
            doc['_id'] = str(doc['_id'])
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
