from flask import Blueprint, jsonify, request
from db import userCollection, patientCollection
from bson import ObjectId
from utils import tokenize_text, embed_chunks, insert_into_database, transcribe_audio

routes = Blueprint('routes', __name__)

@routes.route('/api/insertContent', methods=['POST'])
def insertContent():
    """Process the audio file, transcribe it, tokenize, embed, and insert into SingleStore."""
    try:
        # Get the audio file and patient ID from the request
        audiofile = request.files['audiofile']
        patient_id = request.form['patient_id']

        # Ensure that an audio file and patient ID are provided
        if not audiofile or not patient_id:
            return jsonify({'error': 'Audio file and patient ID are required.'}), 400

        # Transcribe the audio file to text
        transcription = transcribe_audio(audiofile)
        
        # Check if transcription was successful
        if not transcription:
            return jsonify({'error': 'Audio transcription failed.'}), 500

        # Tokenize the transcription into chunks
        text_chunks = tokenize_text(transcription)

        # Check if tokenization was successful
        if not text_chunks:
            return jsonify({'error': 'Tokenization failed.'}), 500

        # Embed the text chunks
        embeddings = embed_chunks(text_chunks)

        # Check if embedding was successful
        if not embeddings:
            return jsonify({'error': 'Embedding failed.'}), 500

        # Insert into SingleStore
        insert_result = insert_to_singlestore(patient_id, text_chunks, embeddings)

        # Check if the insertion was successful
        if not insert_result:
            return jsonify({'error': 'Database insertion failed.'}), 500

        return jsonify({'message': 'Content inserted successfully.'}), 200

    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

@routes.route('/api/getPatientData', methods=['GET']) # W.I.P
def getPatientData():
    """Get all data for a specific patient."""
    try:
        # Get patient data and any other possible parameters
        patient_id = request.args.get('patient_id')

        # Ensure that a patient ID is provided
        if not patient_id:
            return jsonify({'error': 'Patient ID is required.'}), 400

        # Find the patient in the database
        patient = patientCollection.find_one({'_id': ObjectId(patient_id)})

        # Check if patient exists
        if not patient:
            return jsonify({'error': 'Patient not found.'}), 404

        return jsonify({'data': patient}), 200

    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500
        