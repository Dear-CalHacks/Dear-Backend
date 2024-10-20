import os
from dotenv import load_dotenv
from singlestoredb import connect
import tiktoken
from openai import OpenAI
import requests

load_dotenv()

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
cartesia_key = os.getenv('CARTESIA_API_KEY')
vapi_api_key = os.getenv('VAPI_API')

def get_singlestore_connection():
    """Establish a connection to SingleStore DB."""
    return connect(
        host=os.getenv('SS_HOST_NAME'),
        user=os.getenv('SS_USERNAME'),
        password=os.getenv('SS_PASSWORD'),
        database=os.getenv('SS_DB_NAME')
    )

def insert_into_database(patient_id, text_chunks, embeddings):
    """Insert the tokenized chunks and embeddings into SingleStore."""
    connection = get_singlestore_connection()
    cursor = connection.cursor()
    
    for text_chunk, embedding in zip(text_chunks, embeddings):
        embedding_str = ','.join(map(str, embedding))
        query = """
            INSERT INTO your_table_name (patient_id, text_chunk, embedding)
            VALUES (%s, %s, %s)
        """
        cursor.execute(query, (patient_id, text_chunk, embedding_str))

    
    connection.commit()
    cursor.close()
    connection.close()

def transcribe_audio(audiofile):
    """Transcribe audio file using OpenAI's Whisper model."""
    transcription = client.audio.transcriptions.create(
        model="whisper-1",
        file=audiofile
    )
    return transcription.text

def create_nurse_assistant(name, first_message):
    """Create a nurse assistant using the Vapi API."""
    
    url = "https://api.vapi.com/assistant"  # Vapi endpoint for creating assistants
    headers = {
        "Authorization": f"Bearer {os.getenv('VAPI_API_KEY')}",
        "Content-Type": "application/json"
    }

    data = {
        "name": name,
        "firstMessageMode": "assistant-speaks-first",
        "firstMessage": first_message,
        "model": {
            "OpenAIModel": {
                "model": "gpt-3.5-turbo"
            }
        },
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "en-US"
        },
        "voice": {
            "provider": "cartesia",
            "voice_id": "replace_with_voice_id",
            "fillerInjectionEnabled": True,

        },
        "serverUrl": "https://your-server-url.com/callback",  # Replace with your callback URL
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

    # Send POST request to Vapi API
    response = requests.post(url, json=data, headers=headers)
    
    return response

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

def create_custom_assistant(audio_file_path, family_id, name, description, language):
    try:
        # Step 1: Clone Voice
        embedding = clone_voice(audio_file_path)
        if not embedding:
            print('Failed to clone voice')
            return None, 'Failed to clone voice'

        # Step 2: Create Voice
        voice_id = create_voice(name, description, embedding, language)
        if not voice_id:
            print('Failed to create voice')
            return None, 'Failed to create voice'

        # Step 3: Create Family Assistant
        assistant_id = create_family_assistant(family_id, voice_id)
        if not assistant_id:
            print('Failed to create family assistant')
            return None, 'Failed to create family assistant'

        return assistant_id, None

    except Exception as e:
        print(f"Error in create_custom_assistant: {str(e)}")
        return None, f'An unexpected error occurred: {str(e)}'
    
def process_audio_and_update_voice_id(family_member_id):
    try:
        # Retrieve the family member from MongoDB
        family_member = familyCollection.find_one({'_id': ObjectId(family_member_id)})

        if not family_member:
            print(f"No family member found with ID {family_member_id}")
            return

        audio_content = family_member.get('audio')
        if not audio_content:
            print(f"No audio content found for family member ID {family_member_id}")
            return

        # Save the audio content temporarily
        temp_audio_path = f"/tmp/{family_member_id}.webm"
        with open(temp_audio_path, 'wb') as f:
            f.write(audio_content)

        try:
            # Process the audio with Cartesia to get the voice ID
            embedding = clone_voice(temp_audio_path)
            if not embedding:
                print('Failed to clone voice')
                return

            voice_id = create_voice(family_member['name'], family_member['memories'], embedding, family_member['language'])
            if not voice_id:
                print('Failed to create voice')
                return

            # Update the MongoDB document with the voice ID
            familyCollection.update_one(
                {'_id': ObjectId(family_member_id)},
                {'$set': {'voice_id': voice_id}}
            )

            print(f"Voice ID {voice_id} updated for family member ID {family_member_id}")

        finally:
            # Clean up the temporary audio file
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)

    except Exception as e:
        print(f"Error in process_audio_and_update_voice_id: {str(e)}")