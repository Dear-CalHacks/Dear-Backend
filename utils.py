import os
from dotenv import load_dotenv
from singlestoredb import connect
import tiktoken
from openai import OpenAI
import requests

load_dotenv()

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))



def get_singlestore_connection():
    """Establish a connection to SingleStore DB."""
    return connect(
        host=os.getenv('SS_HOST_NAME'),
        user=os.getenv('SS_USERNAME'),
        password=os.getenv('SS_PASSWORD'),
        database=os.getenv('SS_DB_NAME')
    )

def tokenize_text(text, max_token_length=1000):
    """Tokenize the input text into chunks."""
    tokenizer = tiktoken.get_encoding("gpt-3.5-turbo")
    tokens = tokenizer.encode(text)
    return [tokens[i:i + max_token_length] for i in range(0, len(tokens), max_token_length)] # wtf is a DSA RAAAAAAH

def embed_chunks(token_chunks):
    """Generate embeddings for each chunk of text."""
    return [
        client.embeddings.create(model="text-embedding-ada-002", input=chunk)['data'][0]['embedding']
        for chunk in token_chunks
    ]

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