from flask import Blueprint, jsonify, request
from db import userCollection, patientCollection
from bson import ObjectId
from utils import tokenize_text, embed_chunks, insert_into_database, transcribe_audio

routes = Blueprint('routes', __name__)

@routes.route('/api/insertContent', methods=['POST'])
def insertContent():
    """Process the audio file, transcribe it, tokenize, embed, and insert into SingleStore."""
    try:
        audiofile = request.files['audiofile']
        patient_id = request.form['patient_id']

        # Step 1: Speech to Text transcription
        transcribed_text = transcribe_audio(audiofile)

        # Step 2: Tokenize the text
        text_chunks = tokenize_text(transcribed_text)

        # Step 3: Embed the chunks
        embeddings = embed_chunks(text_chunks)

        # Step 4: Insert into SingleStore DB
        insert_into_database(patient_id, text_chunks, embeddings)

        return jsonify({"status": "success", "message": "Data inserted successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Add other routes from your original routes.py file here