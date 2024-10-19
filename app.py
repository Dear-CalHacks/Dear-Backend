from flask import Flask, request, jsonify
from openai import OpenAI
from routes import routes
from utils import tokenize_text, embed_chunks, insert_into_database  

app = Flask(__name__)
client = OpenAI()

# Register the blueprint
app.register_blueprint(routes)

@app.route('/api/insertContent', methods=['POST'])
def insertContent():
    """Process the audio file, transcribe it, tokenize, embed, and insert into SingleStore."""
    audiofile = request.files['audiofile']
    patient_id = request.form['patient_id']
    
    # Step 1: Speech to Text transcription
    transcription = client.audio.transcriptions.create(
        model="whisper-1",  
        file=audiofile
    )
    transcribed_text = transcription['text']
    
    # Tokenize the text with sliding window (wtf is a DSA RAHHHHHH)
    text_chunks = tokenize_text(transcribed_text)
    
    # Embed the chunks
    embeddings = embed_chunks(text_chunks)
    
    # Insert into SingleStore DB
    insert_into_database(patient_id, text_chunks, embeddings)

    return jsonify({"status": "success", "message": "Data inserted successfully"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)