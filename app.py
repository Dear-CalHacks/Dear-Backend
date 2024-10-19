from flask import Flask
from openai import OpenAI
from routes import routes
from utils import load_environment_variables

app = Flask(__name__)
client = OpenAI()

# Load environment variables
load_environment_variables()

# Register the blueprint
app.register_blueprint(routes)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)