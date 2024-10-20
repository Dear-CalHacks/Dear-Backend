from flask import Blueprint, jsonify, request
from db import userCollection, patientCollection
from bson import ObjectId
from utils import tokenize_text, embed_chunks, insert_into_database, transcribe_audio, create_nurse_assistant
from dotenv import load_dotenv
from openai import OpenAI
import os
import requests
load_dotenv()

routes = Blueprint('routes', __name__)
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

@routes.route('/db/insertContent', methods=['POST'])
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
        insert_result = insert_into_database(patient_id, text_chunks, embeddings)

        # Check if the insertion was successful
        if not insert_result:
            return jsonify({'error': 'Database insertion failed.'}), 500

        return jsonify({'message': 'Content inserted successfully.'}), 200

    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

@routes.route('/db/getPatientData', methods=['GET']) # W.I.P
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


@routes.route('/voice/createNurse', methods=['POST'])
def create_nurse(): #only once for nurse, then use call_nurse_assistant
    """Create a nurse assistant by making an API call to Vapi."""
    print("Creating a new nurse assistant...")
    try:
        # Extract parameters from the JSON body
        data = request.json
        assistant_name = "Nurse Assistant Hub"
        first_message = data.get('firstMessage', "Hello! I am your nurse assistant. How can I help you today?")
        voice_id = data.get('voiceId', 'en-US-JennyNeural')  # Optional voice parameter
        server_url = data.get('serverUrl', 'https://your-server-url.com/callback')  # Optional server URL

        # Prepare the data for the Vapi API request
        vapi_payload = {
            "name": assistant_name,
            "firstMessageMode": "assistant-speaks-first",
            "firstMessage": first_message,
            "messages": [
                {"role": "system and hub", "content": "You are a nurse assistant who can help patients with health inquiries or transfer them to a family member upon request."}
            ],
            "model": {
                "provider": "openai",
                "model": "gpt-3.5-turbo"
            },
            "transcriber": {
                "provider": "deepgram",
                "language": "en-US",
                "model": "nova-2"
            },
            "voice": {
                "provider": "cartesia",
                "voiceId": "ae0c424a-4330-4a0a-bc73-f20448ad7c3c",
                "fillerInjectionEnabled": True,
                "chunkPlan": {
                    "enabled": True,
                    "minCharacters": 30,
                    "punctuationBoundaries": [".", "!", "?", ","]
                }
            },
            "serverUrl": server_url,
            "recordingEnabled": True,
            "hipaaEnabled": True,
            "clientMessages": ["conversation-update", "transcript", "status-update", "voice-input"],
            "serverMessages": ["conversation-update", "end-of-call-report", "speech-update"],
            "silenceTimeoutSeconds": 30,
            "maxDurationSeconds": 600,
            "backgroundSound": "office",
            "backchannelingEnabled": False,
            "backgroundDenoisingEnabled": True
        }

        # Send the request to the Vapi API
        vapi_url = "https://api.vapi.ai/assistant"
        headers = {
            "Authorization": f"Bearer {os.getenv('VAPI_API')}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(vapi_url, json=vapi_payload, headers=headers)

        # Check the response from Vapi
        if response.status_code == 201:
            return jsonify({"status": "success", "data": response.json()}), 201
        else:
            return jsonify({"status": "error", "message": response.text}), response.status_code

    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500
    
@routes.route('/cartesia/Family', methods=['POST'])
def create_voice():
    """Creates a voice by sending a request to the Cartesia API with a given embedding."""
    print('hello')
    # Get the data from the POST request
    name = request.json.get('name')
    description = request.json.get('description')
    embedding = request.json.get('embedding')
    language = request.json.get('language', 'en')  # Default to 'en' if not provided

    # Validate the input data
    if not name or not description or not embedding:
        return jsonify({"error": "Missing required fields: 'name', 'description', or 'embedding'"}), 400

    # Set the Cartesia API URL
    cartesia_voice_url = "https://api.cartesia.ai/voices"

    # Prepare the payload for the Cartesia API
    payload = {
        "name": name,
        "description": description,
        "embedding": embedding,
        "language": language
    }

    # Set the headers for the Cartesia API request
    headers = {
        "Cartesia-Version": "2024-06-10",
        "X-API-Key": os.getenv('CARTEISIA_API'),  # Use the API key from your environment
    }

    # Send the POST request to the Cartesia API to create the voice
    try:
        response = requests.post(cartesia_voice_url, json=payload, headers=headers)
        
        # Check if the request was successful
        if response.status_code == 200:
            # Return the response from the Cartesia API
            return jsonify({
                "message": "Voice created successfully", 
                "data": response.json()
            }), 200
        else:
            # Return an error message with details from the Cartesia API response
            return jsonify({
                "error": "Failed to create voice", 
                "details": response.text
            }), response.status_code
    except requests.exceptions.RequestException as e:
        # Handle any exceptions that occur during the request
        return jsonify({
            "error": "An error occurred while creating the voice", 
            "details": str(e)
        }), 500


@routes.route('/cartesia/cloneVoice', methods=['POST'])
def clone_voice():
    """Creates a unique voice using an audio clip sent to the Cartesia API."""
    
    # Check if the 'audio' file is in the request
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files['audio']

    # Ensure the file is in an acceptable audio format (optional)
    if audio_file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Get the optional 'enhance' parameter from the request body
    enhance = request.form.get('enhance', 'true').lower() == 'true'

    # Set the headers for the Cartesia API request
    headers = {
        "Cartesia-Version": "2024-06-10",
        "X-API-Key": cartesia_key
    }

    # Prepare the files payload for the Cartesia API request
    files = {
        'clip': (audio_file.filename, audio_file, audio_file.content_type)
    }

    # Prepare the data payload
    payload = {
        'enhance': enhance
    }

    # Send the POST request to Cartesia's API to create a unique voice
    try:
        response = requests.post(cartesia_clone_url, headers=headers, files=files, data=payload)
        
        # Check if the request was successful
        if response.status_code == 200:
            # Return the response from the Cartesia API (e.g., unique voice ID)
            return jsonify({"message": "Voice created successfully", "data": response.json()}), 200
        else:
            return jsonify({"error": "Failed to create voice", "details": response.text}), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "An error occurred while creating the voice", "details": str(e)}), 500

@routes.route('/voice/createFamily/<string:family_id>', methods=['POST'])
def create_family(family_id):
    """Create a family member dynamically using the Vapi API, with their voice and family_id from Cartesia."""
    try:
        # Extract parameters from the JSON body
        data = request.json
        assistant_name = f"Family Member for Family ID: {family_id}"
        first_message = data.get('firstMessage', f"Hello! I am your family member {family_id}. How can I help you today?")
        voice_id = data.get('voiceId', 'en-US-JennyNeural')  # Optional voice parameter, can be dynamic based on family_id
        server_url = data.get('serverUrl', 'https://your-server-url.com/callback')  # Optional server URL
    
        # Prepare the data for the Vapi API request
        vapi_payload = {
            "name": assistant_name,
            "firstMessageMode": "assistant-speaks-first",
            "firstMessage": first_message,
            "messages": [
                {"role": "system", "content": f"You are assisting a patient and can transfer them to a family member with family_id {family_id} upon request."}
            ],
            "model": {
                "provider": "openai",
                "model": "gpt-3.5-turbo"
            },
            "transcriber": {
                "provider": "deepgram",
                "language": "en-US",
                "model": "nova-2"
            },
            "voice": {
                "provider": "cartesia",
                "voiceId": voice_id,  # Use the dynamic voiceId based on family_id
                "fillerInjectionEnabled": True,
                "chunkPlan": {
                    "enabled": True,
                    "minCharacters": 30,
                    "punctuationBoundaries": [".", "!", "?", ","]
                }
            },
            "serverUrl": server_url,
            "recordingEnabled": True,
            "hipaaEnabled": True,
            "clientMessages": ["conversation-update", "transcript", "status-update", "voice-input"],
            "serverMessages": ["conversation-update", "end-of-call-report", "speech-update"],
            "silenceTimeoutSeconds": 30,
            "maxDurationSeconds": 600,
            "backgroundSound": "office",
            "backchannelingEnabled": False,
            "backgroundDenoisingEnabled": True
        }

        # Send the request to the Vapi API
        vapi_url = "https://api.vapi.ai/assistant"
        headers = {
            "Authorization": f"Bearer {os.getenv('VAPI_API')}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(vapi_url, json=vapi_payload, headers=headers)

        # Check the response from Vapi
        if response.status_code == 201:
            return jsonify({"status": "success", "data": response.json()}), 201
        else:
            return jsonify({"status": "error", "message": response.text}), response.status_code

    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@routes.route('/voice/getNurse/<string:assistant_id>', methods=['GET'])
def get_nurse(assistant_id):
    """Retrieve a nurse assistant by ID from the Vapi API."""
    try:
        # URL for the Vapi API (with assistant ID)
        url = f"https://api.vapi.ai/assistant/{assistant_id}"
        
        # API Key for authorization (use your actual API key)
        headers = {
            "Authorization": f"Bearer {os.getenv('VAPI_API')}"
        }
        
        # Make the GET request to Vapi API
        response = requests.get(url, headers=headers)
        
        # Check for successful response
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({"error": response.text}), response.status_code

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
    
