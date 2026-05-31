from app.main import app

if __name__ == '__main__':
    # Run the dungeon harness. Be sure GEMINI_API_KEY is available in your shell.
    app.run(debug=True, port=5000)