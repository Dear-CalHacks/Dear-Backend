from flask import Flask
from db import userCollection  # Import the MongoDB collection to ensure the DB connects
from routes import routes  # Import the routes blueprint

app = Flask(__name__)

# Register the blueprint
app.register_blueprint(routes)

@app.before_request
def init_db():
    """Initialize the database connection before the first request."""
    try:
        # Test the connection to MongoDB by querying one document
        userCollection.find_one()
        print("MongoDB connection established.")
    except Exception as e:
        print(f"Error connecting to MongoDB: {str(e)}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
