# 1. Set your Pinecone API key in .env
#    PINECONE_API_KEY=your-key-here

# 2. Download the GGUF model into service_rag/models/
huggingface-cli download TheBloke/Mistral-7B-Instruct-v0.2-GGUF \
  mistral-7b-instruct-v0.2.Q4_K_M.gguf --local-dir ../../../models

# 3. Seed Pinecone (run once — or rely on RAG_AUTO_SEED=true)
docker compose run --rm rag python seed_pinecone.py

# 4. Start the service
docker compose up --build

# 5. Test it
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"description": "3-bedroom apartment, Tel Aviv, sea view, renovated kitchen"}'
