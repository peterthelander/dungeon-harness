from app.main import app
from app.config import load_runtime_config

def main():
    cfg = load_runtime_config()
    app.run(debug=not cfg.is_production, port=5000)

if __name__ == '__main__':
    main()