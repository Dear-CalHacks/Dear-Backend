from singlestoredb import connect
import tiktoken
from openai import OpenAI

client = OpenAI()

const openai = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY
});

# SingleStore DB connection
def get_singlestore_connection():
    """Establish a connection to SingleStore DB."""
    connection = connect(
        host='your_host',
        user='your_user',
        password='your_password',
        database='your_database'
    )
    return connection

# Tokenization method
def tokenize_text(text, max_token_length=1000):
    """Tokenize the input text into chunks."""
    tokenizer = tiktoken.get_encoding("gpt-3.5-turbo")  # Load tokenizer
    tokens = tokenizer.encode(text)
    # Sliding window for chunking
    token_chunks = [tokens[i:i + max_token_length] for i in range(0, len(tokens), max_token_length)]
    return token_chunks

# Embedding method
def embed_chunks(token_chunks):
    """Generate embeddings for each chunk of text."""
    embeddings = []
    for chunk in token_chunks:
        embedding = client.embeddings.create(
            model="text-embedding-ada-002",  # Replace with your chosen model
            input=chunk
        )
        embeddings.append(embedding['data'][0]['embedding'])
    return embeddings

# Insert into SingleStore DB
def insert_into_database(patient_id, text_chunks, embeddings):
    """Insert the tokenized chunks and embeddings into SingleStore."""
    connection = get_singlestore_connection()
    cursor = connection.cursor()
    
    for text_chunk, embedding in zip(text_chunks, embeddings):
        embedding_str = ','.join(map(str, embedding))  # Convert list to string for DB insertion
        query = """
            INSERT INTO your_table_name (patient_id, text_chunk, embedding)
            VALUES (%s, %s, %s)
        """
        cursor.execute(query, (patient_id, text_chunk, embedding_str))
    
    connection.commit()
    cursor.close()
    connection.close()