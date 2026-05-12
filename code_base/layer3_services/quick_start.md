# From layer3_ec2/ — start all services simultaneously
cd service_rag        && docker compose up -d
cd ../service_image   && docker compose up -d
cd ../service_guardrails && docker compose up -d
cd ../service_langgraph  && docker compose up --build -d

# Verify all four are healthy
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health