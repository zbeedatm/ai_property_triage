# 1. Download the GGUF model into service_rag/models/
huggingface-cli download TheBloke/Mistral-7B-Instruct-v0.2-GGUF \
  mistral-7b-instruct-v0.2.Q4_K_M.gguf --local-dir ../../../models

# 2. Seed ChromaDB (run once)
docker compose run --rm rag python seed_chroma.py

# 3. Start the service
docker compose up --build

# 4. Test it
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"description": "3-bedroom apartment, Tel Aviv, sea view, renovated kitchen"}'