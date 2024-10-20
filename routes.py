from flask import Blueprint, jsonify, request
from db import insert_family_member, get_family_members, deardb
from bson import ObjectId
from utils import insert_into_database, transcribe_audio, create_nurse_assistant
from dotenv import load_dotenv
from openai import OpenAI
import os
import requests
from werkzeug.utils import secure_filename
from utils import create_custom_assistant, process_audio_and_update_voice_id

load_dotenv()

routes = Blueprint('routes', __name__)
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
cartesia_key = os.getenv('CARTESIA_API_KEY')
vapi_api_key = os.getenv('VAPI_API')


@routes.route('/', methods=['GET'])
def home():
    return "hello"
    


@routes.route('/db/insertFamilyMember', methods=['POST'])  # W.I.P
def insertFamilyMember():
    """Insert a family member into MongoDB."""
    
    data = request.json
    print(data)
    result = insert_family_member(data)
    return jsonify({"success": True, "id": str(result.inserted_id)}), 201


@routes.route('/db/getFamilyMembers/<string:patient_id>', methods=['GET'])
def getFamilyMembers(patient_id):
    """Get all family members for a specific patient."""
    try:
        family_members = list(familyCollection.find({'patient_id': patient_id}))
        for member in family_members:
            member['_id'] = str(member['_id'])  # Convert ObjectId to string
            member.pop('audio', None)  # Remove audio content from the response

        return jsonify({"success": True, "data": family_members}), 200
    except Exception as e:
        print(f"Error in getFamilyMembers: {str(e)}")
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
def create_voice(name, description, embedding, language):
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

@routes.route('/db/insertFamilyMember', methods=['POST'])
def insert_family_member_route():
    """Insert a family member into MongoDB and process the audio."""
    try:
        # Check if the request contains the audio file and form fields
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400

        audio_file = request.files['audio']
        if audio_file.filename == '':
            return jsonify({'error': 'No selected audio file'}), 400

        # Get form fields
        patient_id = request.form.get('patient_id')
        name = request.form.get('name')
        age = request.form.get('age')
        relation = request.form.get('relation')
        memories = request.form.get('memories')
        language = request.form.get('language', 'en')

        if not all([patient_id, name, age, relation, memories]):
            return jsonify({'error': 'Missing required form fields'}), 400

        # Read the audio file content
        audio_content = audio_file.read()

        # Insert data into MongoDB
        family_member = {
            'patient_id': patient_id,
            'name': name,
            'age': age,
            'relation': relation,
            'memories': memories,
            'language': language,
            'audio': audio_content,  # Store audio content in MongoDB
            'voice_id': None  # Will update after processing
        }
        result = familyCollection.insert_one(family_member)
        inserted_id = result.inserted_id

        # Process audio and update voice ID
        process_audio_and_update_voice_id(inserted_id)

        return jsonify({'success': True, 'id': str(inserted_id)}), 201

    except Exception as e:
        print(f"Error in insert_family_member_route: {str(e)}")
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

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

@routes.route('/createCustomAssistant', methods=['POST'])
def create_custom_assistant_route():
    try:
        # Check if the request contains the audio file and form fields
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400

        audio_file = request.files['audio']
        if audio_file.filename == '':
            return jsonify({'error': 'No selected audio file'}), 400

        # Get form fields
        family_id = request.form.get('patient_id')
        name = request.form.get('name', 'Family Member')
        description = request.form.get('memories', 'Family member voice')
        language = request.form.get('language', 'en')
        age = request.form.get('age')
        relation = request.form.get('relation')

        if not family_id:
            return jsonify({'error': 'patient_id is required'}), 400

        # Save the audio file temporarily
        filename = secure_filename(audio_file.filename)
        temp_audio_path = os.path.join('/tmp', filename)
        audio_file.save(temp_audio_path)

        try:
            # Call the service layer function
            assistant_id, error = create_custom_assistant(
                temp_audio_path, family_id, name, description, language
            )

            if error:
                return jsonify({'error': error}), 500

            # Save additional data to MongoDB
            new_family_member = {
                'patient_id': family_id,
                'name': name,
                'age': age,
                'relation': relation,
                'memories': description,
                'assistant_id': assistant_id
            }
            # Insert into MongoDB
            # Assuming you have a collection called `familyCollection`
            deardb.insert_one(new_family_member)

            # Return success response
            return jsonify({
                'message': 'Custom assistant created and data saved successfully',
                'assistantId': assistant_id
            }), 200

        finally:
            # Clean up the temporary audio file
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)

    except Exception as e:
        print(f"Error in create_custom_assistant_route: {str(e)}")
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500