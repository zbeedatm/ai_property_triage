# 1. Set your API key
cp .env.example .env && echo "OPENAI_API_KEY=sk-..." >> .env

# 2. Start
docker compose up --build

# 2. Deploy manually
uvicorn main:app --host 0.0.0.0 --port 8003

# 3. Run the 20-case test suite
python test_rails.py --base-url http://localhost:8003



