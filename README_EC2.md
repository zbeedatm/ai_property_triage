# EC2 Deployment Guide

## Preparation — Build, tag, and push images to Docker Hub (laptop, before EC2)

Do this on the machine where you have the **git repo** and Docker, **before** you install Docker on EC2 or copy files to the server. `docker-compose.ec2.yml` pulls pre-built images (for example `zbeedatm/property-triage-*`). **`n8nio/n8n:latest`** is pulled from Docker Hub as-is; you do **not** push that unless you maintain your own n8n image.

Build the **five** app services from the root `docker-compose.yml`, then publish them under **your** Docker Hub namespace so names match `docker-compose.ec2.yml` (or edit every `image:` line in that file to your namespace).

**First time publishing:** run **§2 Log in**, **§3 Build**, and **§4 Confirm image names** below, then either **§1 Tag and push** (manual `docker tag` / `docker push`) **or** use **§1b** (Compose `build --push`, no per-image tagging). If `ai_property_triage-*` images are already on your machine from an earlier build, run **§2** then **§1** or **§1b**.

### 1. Tag and push (replace `YOUR_DOCKERHUB_USER`)

Image names in `docker-compose.ec2.yml` follow `YOUR_DOCKERHUB_USER/property-triage-<service>:latest`. **Bash:**

```bash
export HUB=YOUR_DOCKERHUB_USER

docker tag ai_property_triage-webui:latest            "${HUB}/property-triage-webui:latest"
docker tag ai_property_triage-guardrails:latest      "${HUB}/property-triage-guardrails:latest"
docker tag ai_property_triage-rag:latest             "${HUB}/property-triage-rag:latest"
docker tag ai_property_triage-image_analyser:latest  "${HUB}/property-triage-image_analyser:latest"
docker tag ai_property_triage-langgraph_agent:latest "${HUB}/property-triage-langgraph_agent:latest"

docker push "${HUB}/property-triage-webui:latest"
docker push "${HUB}/property-triage-guardrails:latest"
docker push "${HUB}/property-triage-rag:latest"
docker push "${HUB}/property-triage-image_analyser:latest"
docker push "${HUB}/property-triage-langgraph_agent:latest"
```

**Windows PowerShell** (repo root):

```powershell
$HUB = "YOUR_DOCKERHUB_USER"

docker tag ai_property_triage-webui:latest            "${HUB}/property-triage-webui:latest"
docker tag ai_property_triage-guardrails:latest      "${HUB}/property-triage-guardrails:latest"
docker tag ai_property_triage-rag:latest             "${HUB}/property-triage-rag:latest"
docker tag ai_property_triage-image_analyser:latest  "${HUB}/property-triage-image_analyser:latest"
docker tag ai_property_triage-langgraph_agent:latest "${HUB}/property-triage-langgraph_agent:latest"

docker push "${HUB}/property-triage-webui:latest"
docker push "${HUB}/property-triage-guardrails:latest"
docker push "${HUB}/property-triage-rag:latest"
docker push "${HUB}/property-triage-image_analyser:latest"
docker push "${HUB}/property-triage-langgraph_agent:latest"
```

If your Hub username is not the one in `docker-compose.ec2.yml`, either change every `image:` line there to your `HUB/...` names or retag to match the file before pushing.

### 1b. Optional — one Compose command (no manual `docker tag`)

Compose can **build and push in one step** if each buildable service has an **`image:`** entry that points at Docker Hub (same names as in `docker-compose.ec2.yml`, e.g. `YOUR_DOCKERHUB_USER/property-triage-webui:latest`).

1. In **`docker-compose.yml`**, under **`webui`**, **`guardrails`**, **`rag`**, **`image_analyser`**, and **`langgraph_agent`**, add a sibling line next to `build:` (do not change **n8n**):

   ```yaml
   image: YOUR_DOCKERHUB_USER/property-triage-webui:latest
   ```

   Use the matching `property-triage-…` image name for each service (see `docker-compose.ec2.yml`).

2. From the repo root (after **`docker login`**):

   ```bash
   docker compose build --push webui guardrails rag image_analyser langgraph_agent
   ```

   That builds all five and pushes each image that has an `image:` registry name. (Requires a recent Compose v2; if `--push` is not supported, run **`docker compose build …`** then **`docker compose push webui guardrails rag image_analyser langgraph_agent`**.)

You can remove or comment out the temporary `image:` lines later if you prefer local-only names for day-to-day development.

### 1c. Optional — one Bash loop instead of many `docker tag` lines

If you keep the default Compose image names (`ai_property_triage-*` from **`docker compose config --images`**), you can tag and push in a loop (names must match your Hub layout):

```bash
export HUB=YOUR_DOCKERHUB_USER
for pair in \
  "webui:property-triage-webui" \
  "guardrails:property-triage-guardrails" \
  "rag:property-triage-rag" \
  "image_analyser:property-triage-image_analyser" \
  "langgraph_agent:property-triage-langgraph_agent"; do
  svc="${pair%%:*}"
  remote="${pair#*:}"
  docker tag "ai_property_triage-${svc}:latest" "${HUB}/${remote}:latest"
  docker push "${HUB}/${remote}:latest"
done
```

### 2. Log in to Docker Hub

```bash
docker login
```

### 3. Build (repository root)

```bash
docker compose build webui guardrails rag image_analyser langgraph_agent
```

### 4. Confirm local image names

Compose assigns default image names from the top-level `name:` in `docker-compose.yml` (currently `AI_Property_Triage` → `ai_property_triage-*`):

```bash
docker compose config --images
```

You should see `ai_property_triage-webui`, `ai_property_triage-guardrails`, `ai_property_triage-rag`, `ai_property_triage-image_analyser`, and `ai_property_triage-langgraph_agent` (plus `n8nio/n8n:latest`). Use the printed names if yours differ after a `name:` change.

### 5. Versioned tags (optional)

For reproducible deploys, tag and push a version or date in addition to `latest`, for example `:v1.0.0` or `:2026-05-15`, then set the same tag in `docker-compose.ec2.yml` on EC2.

### 6. On EC2 after you push newer images

```bash
cd ~/app
docker compose -f docker-compose.ec2.yml pull
docker compose -f docker-compose.ec2.yml up -d
```

---

## Prerequisites

- **EC2 instance (pick one):**
  - **Recommended for this stack:** **m6i.xlarge** or **c6i.xlarge** (4 vCPU, 16 GB RAM, non-burstable CPU). Avoid **t3** for sustained multi-service CPU load unless you accept throttling.
  - **GPU** is optional now that chat + RAG insights use **Ollama Cloud** (no local 7B GGUF on the instance).
- **Storage:** at least **40 GB gp3** (Docker images, checkpoints, n8n data, logs).
- **AMI:** Ubuntu 22.04 / 24.04
- **Ollama Cloud:** create an API key at [ollama.com/settings/keys](https://ollama.com/settings/keys) and set `OLLAMA_API_KEY` in both `docker/secrets/webui.env` and `docker/secrets/rag.env` (see `docker/examples/*.env.example`).
- **Security Group Inbound Rules:**

  | Port | Purpose       | Source   |
  | ---- | ------------- | -------- |
  | 22   | SSH           | My IP    |
  | 5678 | n8n dashboard | My IP    |
  | 7860 | Gradio WebUI  | Anywhere |


---

## Step 1 — SSH into the instance

From your **local** terminal (replace the key path and public IP):

```bash
ssh -i your-key.pem ubuntu@203.0.113.10
```

Replace the key path and host with your values (no `<` or `>` around the IP).

---

## Step 2 — Install Docker on EC2

On the instance (Ubuntu), install Docker and the Compose v2 plugin (needed for `docker compose` later):

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
```

Allow running Docker without `sudo` (then disconnect and SSH back in so the group change applies):

```bash
sudo usermod -aG docker ubuntu
exit
```

After you reconnect, validate:

```bash
docker version
docker info | head
docker compose version
```

If **`docker compose version`** fails, install the Compose plugin and reconnect before Step 5:

```bash
sudo apt update && sudo apt install -y docker-compose-v2
```

**`unknown shorthand flag: 'f'`** when you run `docker compose -f ...` almost always means the CLI is not running the **Compose v2** subcommand (plugin missing, or a typo so `-f` is parsed by `docker` instead of `compose`). Fix with `docker-compose-v2` above, then confirm `docker compose version` prints a version.

If only the legacy **`docker-compose`** binary (with a hyphen) is available, use the same `-f` flag with that command instead, for example:

```bash
cd ~/app && docker-compose -f docker-compose.ec2.yml pull
```

---

## Step 3 — Create project directory

```bash
mkdir -p ~/app/docker/secrets ~/app/docker
cd ~/app
```

---

## Step 4 — Copy config files from your local machine

Run these from your **local PowerShell** (not EC2), from the **repository root** (so paths like `docker-compose.ec2.yml` resolve).

Copy at least:

1. **`docker-compose.ec2.yml`** → `~/app/` on the instance (required for Step 5).
2. **`code_base/layer2_n8n/flow.json`** → `~/app/code_base/layer2_n8n/` (n8n bind mount).
3. **Secrets** under `docker/secrets/` → `~/app/docker/secrets/`.

```powershell
$key = "C:\Users\zbeed\Downloads\example-key.pem"
# Use the real IP or hostname only — no angle brackets (wrong: ubuntu@<1.2.3.4>).
$ec2 = "ubuntu@203.0.113.10"

ssh -i $key $ec2 "mkdir -p ~/app/code_base/layer2_n8n"

# Compose file (must exist on EC2 before `docker compose -f docker-compose.ec2.yml ...`)
scp -i $key docker-compose.ec2.yml "${ec2}:~/app/"
scp -i $key code_base/layer2_n8n/flow.json "${ec2}:~/app/code_base/layer2_n8n/"
scp -i $key docker/secrets/webui.env "${ec2}:~/app/docker/secrets/"
scp -i $key docker/secrets/rag.env "${ec2}:~/app/docker/secrets/"
scp -i $key docker/secrets/langgraph.env "${ec2}:~/app/docker/secrets/"
scp -i $key docker/secrets/guardrails.env "${ec2}:~/app/docker/secrets/"
scp -i $key docker/secrets/image.env "${ec2}:~/app/docker/secrets/"
```

The compose file expects this repo layout on the server (e.g. `~/app/code_base/layer2_n8n/flow.json`) so the n8n volume mount resolves.

Ensure `webui.env` and `rag.env` include `OLLAMA_HOST=https://ollama.com`, `OLLAMA_API_KEY`, and `OLLAMA_MODEL` (defaults are in `docker/examples/`).

---

## Step 5 — Pull images and start all services

On **EC2** (after SSH), `~/app/docker-compose.ec2.yml` must exist — that comes from **Step 4** (`scp ... docker-compose.ec2.yml`). If you used `git clone` on the server instead, run compose from the directory that contains that file.

```bash
cd ~/app
docker compose -f docker-compose.ec2.yml pull
docker compose -f docker-compose.ec2.yml up -d
```

`pull` downloads every image referenced in the compose file; `up -d` starts the stack. First run can take several minutes.

If you pushed newer images from your laptop, run **`pull`** again before **`up -d`** (same as **Preparation — §6**).

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
- **RAG health:** `curl -s http://<EC2_PUBLIC_IP>:8001/health`

---

## Useful Commands

```bash
# Pull latest images for every service (from ~/app, compose file must be present)
docker compose -f docker-compose.ec2.yml pull

# View all container statuses
docker ps

# --- Logs: all services (follow)
docker compose -f docker-compose.ec2.yml logs -f

# --- Logs: one compose service by service name (follow, last 100 lines)
docker compose -f docker-compose.ec2.yml logs -f --tail=100 webui
docker compose -f docker-compose.ec2.yml logs -f --tail=100 n8n
docker compose -f docker-compose.ec2.yml logs -f --tail=100 guardrails
docker compose -f docker-compose.ec2.yml logs -f --tail=100 rag
docker compose -f docker-compose.ec2.yml logs -f --tail=100 image_analyser
docker compose -f docker-compose.ec2.yml logs -f --tail=100 langgraph_agent

# --- Logs: by container name (same containers, useful if you only remember `docker ps` names)
docker logs -f --tail=100 property_webui
docker logs -f --tail=100 property_n8n
docker logs -f --tail=100 property_guardrails
docker logs -f --tail=100 property_rag_pinecone
docker logs -f --tail=100 property_image_analyser
docker logs -f --tail=100 property_langgraph_agent

# Restart a single service
docker compose -f docker-compose.ec2.yml restart webui

# Stop everything
docker compose -f docker-compose.ec2.yml down

# Start everything
docker compose -f docker-compose.ec2.yml up -d
```

