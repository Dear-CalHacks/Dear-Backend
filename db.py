from pymongo import MongoClient
import os

# MongoDB connection setup
MONGO_URI = 'mongodb+srv://tirthofficials:tsQzsG7z9M39ewtq@cluster0.iph3z.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'

client = MongoClient(MONGO_URI)
db = client['clahacks_user']  # Replace with your actual database name
userCollection = db['user']  # Replace with your actual collection name
patientCollection = db['patient']  # Replace with your actual collection name