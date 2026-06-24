# 🚀 Business Intelligence Platform

> AI-powered business analysis platform built with FastAPI + Gemini

## 🧠 Features
- JWT Authentication
- Business Management (CRUD)
- SWOT Analysis (AI-powered via Gemini)
- MongoDB Reports Storage
- Multi-tenant Architecture

## 🛠️ Tech Stack
- FastAPI
- PostgreSQL
- MongoDB
- Redis
- Vertex AI (Gemini)
- Docker

## ▶️ Run Locally

```bash
pip install -r requirements.txt
docker compose up -d
uvicorn app.main:app --reload