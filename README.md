# 🧠 AI Assistant: Private Document Analysis Platform

This project is a full-stack AI assistant designed for **secure internal document analysis**. It uses **local LLMs** via Ollama and integrates with **Azure Blob Storage** and **ChromaDB** for a privacy-focused AI workflow.

---

## 🧾 Key Features

- 🔐 **Private AI Assistant** using local Ollama-hosted Phi model for secure, offline LLM inference
- 📄 **upload, query, and analyze documents** using RESTful API endpoints powered by FastAPI
- 📦 **Containerized deployment** with Azure Container Apps for scalable, production-ready microservices
- 💾 **Document embedding and retrieval** using ChromaDB for fast and accurate semantic search (RAG)
- ☁️ **Azure Blob Storage integration** for persistent document and vector store backups
- 🔍 **LangChain integration with guardrails** to ensure controlled and safe LLM responses
- 📊 **Frontend interface** built with Streamlit for easy document upload and query visualization
- 🔁 **Chunking, embedding, and metadata enrichment** for structured and contextualized document analysis
- 🧠 **RAG + LLM powered pipeline** for contextual answers, summarization, and classification of documents

---

## ⚙️ Core API Endpoints

| Endpoint       | Method | Description                                                                 |
|----------------|--------|-----------------------------------------------------------------------------|
| `/upload`      | POST   | Uploads document to Azure Blob and Chroma after chunking/embedding         |
| `/query`       | POST   | Allows RAG-style queries against document embeddings                        |
| `/analyze`     | POST   | Performs document-wide summary/classification using LLM                     |
| `/health`      | GET    | Health check endpoint                                                       |

---

## 🧠 Architecture Overview

This system consists of three main services:

- **Frontend (Streamlit)**: Document upload, query interface
- **Backend (FastAPI)**: Handles API, document processing, embedding, querying
- **Ollama service**: Hosts the Phi model for inference (runs locally)

![AI Assessment Architecture](AIAssesment.drawio.svg)

---

## 🗂️ Project Structure

```
.
├── AI_Assistant
│   ├── backend
│   │   ├── app
│   │   │   ├── document_analyzer.py
│   │   │   ├── guardrails.py
│   │   │   ├── main.py
│   │   │   ├── models.py
│   │   │   └── rag.py
│   │   └── requirements.txt
│   ├── frontend
│   │   ├── app.py
│   │   └── requirements.txt
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── ollama.dockerfile
│   └── wait_for_ollama.sh
├── AIAssesment.drawio.svg
├── Deployment.drawio.svg
└── README.md
```

---

## 🔐 .env File (Sample Structure)

> **Note**: Do not share or expose real values.

```bash
# Backend configuration
UPLOAD_DIR=./uploads
CHROMA_DB_PATH=./chroma_db

# Ollama configuration
OLLAMA_HOST=ollama:11434
OLLAMA_HOST_LOCAL=http://localhost:11434/
OLLAMA_MODEL=phi:latest

# Frontend configuration
BACKEND_URL=http://localhost:8000

# Azure Blob configuration
AZURE_STORAGE_ACCOUNT_NAME=your_storage_account
AZURE_STORAGE_ACCOUNT_KEY=your_storage_key
UPLOAD_CONTAINER=uploads
CHROMADB_CONTAINER=chromadb
```

---
## 🧩 Deployment Architecture

This high-level diagram explains how Azure Container Apps are orchestrated:

![Deployment Architecture](Deployment.drawio.svg)

- Each service runs in its own container
- Env vars injected at deployment
- Ollama is the LLM inference layer
- Frontend communicates via backend APIs

---

## 🚀 Azure Deployment Commands

### 1. Create ACR
```bash
az acr create --name myaiassistantregistry --resource-group ai-assistant-rg --location eastus --sku Basic --admin-enabled true
```

### 2. Build and Push Images
```bash
docker build --platform linux/amd64 -t myaiassistantregistry.azurecr.io/rag-backend:1.1 --target backend .
docker push myaiassistantregistry.azurecr.io/rag-backend:1.1

docker build --platform linux/amd64 -t myaiassistantregistry.azurecr.io/rag-frontend:1.1 --target frontend .
docker push myaiassistantregistry.azurecr.io/rag-frontend:1.1

docker build --platform linux/amd64 -t myaiassistantregistry.azurecr.io/ollama-service:1.0 -f ollama.dockerfile .
docker push myaiassistantregistry.azurecr.io/ollama-service:1.0
```

### 3. Create Azure Container App Environment
```bash
az containerapp env create \
  --name my-ai-assistant-env \
  --resource-group ai-assistant-rg \
  --location eastus
```

### 4. Deploy Ollama Service
```bash
az containerapp create \
  --name ollama-service \
  --resource-group ai-assistant-rg \
  --image myaiassistantregistry.azurecr.io/ollama-service:1.0 \
  --environment my-ai-assistant-env \
  --ingress external \
  --target-port 11434 \
  --registry-server myaiassistantregistry.azurecr.io \
  --cpu 2.5 \
  --memory 5.0Gi
```

### 5. Deploy Backend
```bash
az containerapp create \
  --name rag-backend \
  --resource-group ai-assistant-rg \
  --image myaiassistantregistry.azurecr.io/rag-backend:1.1 \
  --environment my-ai-assistant-env \
  --ingress external \
  --target-port 8000 \
  --registry-server myaiassistantregistry.azurecr.io \
  --cpu 2.0 \
  --memory 4.0Gi \
  --env-vars \
    OLLAMA_HOST=ollama-service:11434 \
    AZURE_STORAGE_ACCOUNT_NAME=your_storage_account \
    AZURE_STORAGE_ACCOUNT_KEY=your_storage_key \
    UPLOAD_CONTAINER=uploads \
    CHROMADB_CONTAINER=chromadb
```

### 6. Deploy Frontend
```bash
az containerapp create \
  --name rag-frontend \
  --resource-group ai-assistant-rg \
  --image myaiassistantregistry.azurecr.io/rag-frontend:1.1 \
  --environment my-ai-assistant-env \
  --ingress external \
  --target-port 80 \
  --registry-server myaiassistantregistry.azurecr.io \
  --cpu 1.5 \
  --memory 3.0Gi \
  --env-vars BACKEND_URL=http://rag-backend:8000
```

---

## 🧪 Useful Azure CLI Commands

```bash
# Get URLs
az containerapp show --name ollama-service --resource-group ai-assistant-rg --query properties.configuration.ingress.fqdn -o tsv
az containerapp show --name rag-backend --resource-group ai-assistant-rg --query properties.configuration.ingress.fqdn -o tsv
az containerapp show --name rag-frontend --resource-group ai-assistant-rg --query properties.configuration.ingress.fqdn -o tsv

# Check provisioning state
az containerapp show --name ollama-service --resource-group ai-assistant-rg --query properties.provisioningState
az containerapp show --name rag-backend --resource-group ai-assistant-rg --query properties.provisioningState
az containerapp show --name rag-frontend --resource-group ai-assistant-rg --query properties.provisioningState

# View logs
az containerapp logs show --name rag-backend --resource-group ai-assistant-rg

# Update container images
az containerapp update --name rag-backend --resource-group ai-assistant-rg --image myaiassistantregistry.azurecr.io/rag-backend:1.1
az containerapp update --name rag-frontend --resource-group ai-assistant-rg --image myaiassistantregistry.azurecr.io/rag-frontend:1.1
az containerapp update --name ollama-service --resource-group ai-assistant-rg --image myaiassistantregistry.azurecr.io/ollama-service:1.0
```

---


## 🧑‍💻 Author
**Rutuja Kute** – AI and Data Engineer




