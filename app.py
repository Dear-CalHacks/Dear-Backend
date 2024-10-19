from flask import Flask
from openai import OpenAI
from routes import routes
from dotenv import load_dotenv

app = Flask(__name__)

# Load environment variables
load_dotenv()

# Register the blueprint
app.register_blueprint(routes)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)