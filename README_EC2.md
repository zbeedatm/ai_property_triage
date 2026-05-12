# EC2 Deployment Guide

## Prerequisites

- **EC2 Instance:** t3.xlarge (4 vCPU, 16 GB RAM)
- **Storage:** 30 GB gp3
- **AMI:** Ubuntu 22.04 / 24.04
- **Security Group Inbound Rules:**

  | Port | Purpose         | Source   |
  |------|----------------|----------|
  | 22   | SSH            | My IP    |
  | 5678 | n8n dashboard  | My IP    |
  | 7860 | Gradio WebUI   | Anywhere |

---

## Step 1 — Install Docker on EC2

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-v2
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ubuntu

# Log out and back in for group change to take effect
exit
```

SSH back in, then verify:

```bash
docker --version
docker compose version
```

---

## Step 2 — Create project directory

```bash
mkdir -p ~/app/docker/secrets ~/app/models
cd ~/app
```

---

## Step 3 — Copy config files from your local machine

Run these from your **local PowerShell** (not EC2):

```powershell
$key = "C:\Users\zbeed\Downloads\example-key.pem"
$ec2 = "ubuntu@<EC2_PUBLIC_IP>"

scp -i $key docker-compose.ec2.yml "${ec2}:~/app/"
scp -i $key docker/flow.json "${ec2}:~/app/docker/"
scp -i $key docker/secrets/webui.env "${ec2}:~/app/docker/secrets/"
scp -i $key docker/secrets/rag.env "${ec2}:~/app/docker/secrets/"
scp -i $key docker/secrets/langgraph.env "${ec2}:~/app/docker/secrets/"
scp -i $key docker/secrets/guardrails.env "${ec2}:~/app/docker/secrets/"
scp -i $key docker/secrets/image.env "${ec2}:~/app/docker/secrets/"
```

---

## Step 4 — Download the Mistral GGUF model on EC2

```bash
cd ~/app/models
curl -L -o mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
```

This downloads ~4 GB directly to EC2 (much faster than uploading from your machine).

---

## Step 5 — Pull images and start all services

```bash
cd ~/app
docker compose -f docker-compose.ec2.yml up -d
```

This pulls all 7 images and starts the containers. First run takes a few minutes.

Monitor startup:

```bash
docker compose -f docker-compose.ec2.yml logs -f
```

---

## Step 6 — Configure n8n credentials

1. Open `http://<EC2_PUBLIC_IP>:5678` in your browser
2. Create an owner account when prompted
3. Go to the **AI_Property_Triage** workflow
4. Open each Gemini node and select/create the **Google Gemini (PaLM) API** credential:
   - Gemini Chat Model — Extractor
   - Gemini Chat Model — Agent
   - Gemini Chat Model — Report
5. If the OpenAI Chat Model node is used, create an **OpenAI** credential too
6. Save and activate the workflow

---

## Verify

- **WebUI:** `http://<EC2_PUBLIC_IP>:7860`
- **n8n:** `http://<EC2_PUBLIC_IP>:5678`

---

## Useful Commands

```bash
# View all container statuses
docker ps

# View logs for a specific service
docker logs property_webui --tail 30
docker logs property_n8n --tail 30

# Restart a single service
docker compose -f docker-compose.ec2.yml restart webui

# Stop everything
docker compose -f docker-compose.ec2.yml down

# Start everything
docker compose -f docker-compose.ec2.yml up -d
```
