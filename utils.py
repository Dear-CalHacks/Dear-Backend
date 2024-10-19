import os
from dotenv import load_dotenv
from singlestoredb import connect
import tiktoken
from openai import OpenAI

client = OpenAI()

def load_environment_variables():
    load_dotenv()
    global client
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