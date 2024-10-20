from flask import Blueprint, jsonify, request
from db import userCollection, patientCollection
from bson import ObjectId
from utils import tokenize_text, embed_chunks, insert_into_database, transcribe_audio, create_nurse_assistant
from dotenv import load_dotenv
from openai import OpenAI
import os
import requests
from werkzeug.utils import secure_filename
load_dotenv()

routes = Blueprint('routes', __name__)
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
cartesia_key = os.getenv('CARTESIA_API_KEY')
vapi_api_key = os.getenv('VAPI_API')
# Allowed audio extensions
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'm4a', 'ogg', 'flac'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@routes.route('/voice/createFamilyNext', methods=['POST'])
def create_family_next():
    try:
        # Check if the request contains the audio file and form fields
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400

        audio_file = request.files['audio']
        if audio_file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        if not allowed_file(audio_file.filename):
            return jsonify({'error': 'Unsupported file type'}), 400

        # Get form fields
        family_id = request.form.get('family_id')
        name = request.form.get('name', 'Family Member')
        description = request.form.get('description', 'Family member voice')
        language = request.form.get('language', 'en')

        if not family_id:
            return jsonify({'error': 'family_id is required'}), 400

        # Secure the filename
        filename = secure_filename(audio_file.filename)
        temp_audio_path = os.path.join('/tmp', filename)
        audio_file.save(temp_audio_path)

        try:
            # Step 1: Clone Voice
            embedding = clone_voice(temp_audio_path)
            if not embedding:
                return jsonify({'error': 'Failed to clone voice'}), 500

            # Step 2: Create Voice
            voice_id = create_voice(name, description, embedding, language)
            if not voice_id:
                return jsonify({'error': 'Failed to create voice'}), 500

            # Step 3: Create Family Assistant
            assistant_id = create_family_assistant(family_id, voice_id)
            if not assistant_id:
                return jsonify({'error': 'Failed to create family assistant'}), 500

            # Return success response
            return jsonify({
                'message': 'Family assistant created successfully',
                'assistantId': assistant_id
            }), 200

        finally:
            # Clean up the temporary audio file
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)

    except Exception as e:
        print(f"Error in create_family_next: {str(e)}")
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500
    

def clone_voice(audio_path):
    try:
        cartesia_clone_url = "https://api.cartesia.ai/voices/clone/clip"
        headers = {
            "Cartesia-Version": "2024-06-10",
            "X-API-Key": cartesia_key
        }

        with open(audio_path, 'rb') as audio_file:
            files = {'clip': (os.path.basename(audio_path), audio_file, 'audio/wav')}
            payload = {'enhance': 'true'}
            response = requests.post(cartesia_clone_url, headers=headers, files=files, data=payload)

        if response.status_code == 200:
            embedding = response.json().get('embedding')
            return embedding
        else:
            print(f"Clone Voice Error: {response.text}")
            return None
    except Exception as e:
        print(f"Exception in clone_voice: {str(e)}")
        return None


def create_voice(name, description, embedding, language):
    try:
        cartesia_voice_url = "https://api.cartesia.ai/voices"
        headers = {
            "Cartesia-Version": "2024-06-10",
            "X-API-Key": cartesia_key,
            "Content-Type": "application/json"
        }
        payload = {
            "name": name,
            "description": description,
            "embedding": embedding,
            "language": language
        }
        response = requests.post(cartesia_voice_url, headers=headers, json=payload)

        if response.status_code == 200:
            voice_id = response.json().get('id')  # Adjust key if different
            return voice_id
        else:
            print(f"Create Voice Error: {response.text}")
            return None
    except Exception as e:
        print(f"Exception in create_voice: {str(e)}")
        return None

def create_family_assistant(family_id, voice_id):
    try:
        vapi_url = "https://api.vapi.ai/assistant"
        headers = {
            "Authorization": f"Bearer {vapi_api_key}",
            "Content-Type": "application/json"
        }
        assistant_name = f"Family Member {family_id}"
        first_message = f"Hello! I am your family member {family_id}. How can I help you today?"
        vapi_payload = {
            "name": assistant_name,
            "firstMessageMode": "assistant-speaks-first",
            "firstMessage": first_message,
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
                "voiceId": voice_id,
                "fillerInjectionEnabled": True,
                "chunkPlan": {
                    "enabled": True,
                    "minCharacters": 30,
                    "punctuationBoundaries": [".", "!", "?", ","]
                }
            },
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
        response = requests.post(vapi_url, headers=headers, json=vapi_payload)

        if response.status_code == 201:
            assistant_id = response.json().get('id')  # Adjust key if different
            return assistant_id
        else:
            print(f"Create Family Assistant Error: {response.text}")
            return None
    except Exception as e:
        print(f"Exception in create_family_assistant: {str(e)}")
        return None

@routes.route('/', methods=['GET'])
def home():
    return "hello"
    
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
        assistant_name = "Nurse Assistant Hub"
        first_message = "Hello! I am your nurse assistant. How can I help you today?"
        voice_id = "emma"  # Optional voice parameter
        server_url = "https://your-server-url.com/callback"  # Optional server URL

        # Prepare the data for the Vapi API request
        vapi_payload = {
            "name": assistant_name,
            "firstMessageMode": "assistant-speaks-first",
            "firstMessage": first_message,
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
                "provider": "azure",
                "voiceId": voice_id,
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
    
@routes.route('/cartesia/cloneVoice', methods=['POST']) #cartesia voice clone
def clone_voice():
    """Creates a unique voice using an audio clip sent to the Cartesia API."""
    cartesia_clone_url = "https://api.cartesia.ai/voices/clone/clip"
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
        
        # Log the response status code for debugging
        print(f"Response status code: {response.status_code}")
        print(f"Response data: {response.text}")

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            return jsonify({"message": "Voice created successfully", "data": response.json()}), 200
        elif response.status_code >= 400:
            # Handle any specific error cases with the status code and response data
            return jsonify({"error": "Failed to create voice", "details": response.json()}), response.status_code
        else:
            # Handle other status codes if necessary
            return jsonify({"error": "Unexpected error", "details": response.text}), response.status_code
    except requests.exceptions.RequestException as e:
        # Handle any exceptions that occur during the request
        return jsonify({"error": "An error occurred while creating the voice", "details": str(e)}), 500
@routes.route('/cartesia/createVoice', methods=['POST']) #cartesia voice creation after clone embedding
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
        "X-API-Key": cartesia_key,  # Use the API key from your environment
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

@routes.route('/voice/createFamily/<string:family_id>', methods=['POST']) #create family member with cartesia argument
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

@routes.route('/voice/getNurse/<string:assistant_id>', methods=['GET']) #get nurse assistant
def get_nurse(assistant_id):
    """Retrieve a nurse assistant by ID from the Vapi API."""
    try:
        print(f'trying to get nurse with id: {assistant_id}')
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
    
@routes.route('/voice/initiateCall/<string:assistant_id>', methods=['POST']) #initiate call with nurse
def initiate_call(assistant_id):
    """Initiates a call with a specific agent using the Vapi API."""
    try:
        # Extract the user or patient message from the request
        user_message = request.json.get('message', 'Hello, can you assist me?')
        
        # Prepare the payload for initiating the call
        vapi_call_payload = {
            "assistantId": assistant_id,
            "message": {
                "role": "user",
                "content": user_message
            },
            "voice": {
                "provider": "cartesia",
                "voiceId": "ae0c424a-4330-4a0a-bc73-f20448ad7c3c"  # Use appropriate voiceId
            },
            "transcriber": {
                "provider": "deepgram",
                "language": "en-US"
            }
        }

        # Vapi API endpoint for initiating a conversation
        vapi_url = f"https://api.vapi.ai/assistant/{assistant_id}/conversation"

        # Set the headers for the Vapi API request
        headers = {
            "Authorization": f"Bearer {os.getenv('VAPI_API')}",
            "Content-Type": "application/json"
        }

        # Send the POST request to Vapi's API to initiate the conversation
        response = requests.post(vapi_url, json=vapi_call_payload, headers=headers)

        # Check the response from Vapi
        if response.status_code == 200:
            return jsonify({"status": "success", "data": response.json()}), 200
        else:
            return jsonify({"error": f"Failed to initiate call: {response.text}"}), response.status_code

    except Exception as e:
        return jsonify({"error": f"An error occurred while initiating the call: {str(e)}"}), 500

@routes.route('/voice/endCall/<string:assistant_id>', methods=['POST']) #end call with nurse
def end_call(assistant_id):
    """Ends an ongoing call with a specific agent using the Vapi API."""
    try:
        # Vapi API endpoint for ending the conversation
        vapi_end_url = f"https://api.vapi.ai/assistant/{assistant_id}/conversation/end"

        # Set the headers for the Vapi API request
        headers = {
            "Authorization": f"Bearer {os.getenv('VAPI_API')}",
            "Content-Type": "application/json"
        }

        # Send the POST request to Vapi's API to end the conversation
        response = requests.post(vapi_end_url, headers=headers)

        # Check the response from Vapi
        if response.status_code == 200:
            return jsonify({"status": "success", "message": "Call ended successfully."}), 200
        else:
            return jsonify({"error": f"Failed to end call: {response.text}"}), response.status_code

    except Exception as e:
        return jsonify({"error": f"An error occurred while ending the call: {str(e)}"}), 500
