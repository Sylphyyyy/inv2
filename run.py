from dotenv import load_dotenv

load_dotenv()

from app import create_app

app = create_app()

if __name__ == '__main__':
    import os
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    print("Starting Admin Portal on http://127.0.0.1:5000")
    app.run(debug=debug_mode, host='127.0.0.1', port=5000)
