from pymongo import MongoClient
import os

# MongoDB connection setup
MONGO_URI = 'mongodb+srv://tirthofficials:tsQzsG7z9M39ewtq@cluster0.iph3z.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'

client = MongoClient(MONGO_URI)

db = client['deardb']

# Collections
userCollection = db['user']
patientCollection = db['patient']
deardb = db['deardb']  # Collection for storing family member information
familyCollection = db['family']
# You can add more collections or helper functions here if needed

def insert_family_member(family_member_data):
    """
    Insert a new family member document into the deardb collection.
    """
    return deardb.insert_one(family_member_data)

def get_family_members(patient_id):
    """
    Retrieve all family members for a given patient ID.
    """
    return list(deardb.find({'patient_id': patient_id}))

# Add more database operations as needed