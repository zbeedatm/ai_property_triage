# 1. Pull the model (once)
ollama pull mistral && ollama serve

# 2. Run the UI
pip install -r requirements.txt && python app.py
# → open http://localhost:7860