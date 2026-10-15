from dotenv import load_dotenv

# Load environment variables from .env file before app initialization
load_dotenv()

from app import create_app

app = create_app()

if __name__ == '__main__':
    print("Starting Admin Portal on http://127.0.0.1:5000")
    app.run(debug=True, host='127.0.0.1', port=5000)
