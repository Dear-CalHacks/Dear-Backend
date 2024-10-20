from flask import Flask
from openai import OpenAI
from routes import routes
from dotenv import load_dotenv
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
# Load environment variables
load_dotenv()

# Register the blueprint
app.register_blueprint(routes)

if __name__ == '__main__':
    print(app.url_map)
    app.run(host='0.0.0.0', port=8080, debug=True)