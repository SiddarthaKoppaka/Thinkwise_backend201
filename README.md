# ThinkWise AI – Backend

This is the **FastAPI backend** powering [ThinkWise AI](#), an AI-driven platform that evaluates business ideas using LangGraph agents, GCP Vertex AI, and external web intelligence.

---

## Overview

**ThinkWise AI** helps users:

* Upload or type business ideas
* Evaluate effort and ROI using multi-agent LLM workflows
* View the top ideas (if batch uploaded)
* Chat with the AI about each idea’s evaluation
* Track analytics on past ideas

---

## Tech Stack

| Layer         | Tools Used                                    |
| ------------- | --------------------------------------------- |
| Web Framework | FastAPI (Python)                              |
| AI/LLM Engine | LangChain + LangGraph + LangSmith + Vertex AI |
| Data Storage  | MongoDB (Ideas, Users, Scores)                |
| Search Tool   | Tavily API (ROI estimation via web)           |
| Auth          | JWT-based token authentication                |

---


Thanks! Based on your **OpenAPI schema**, here is a **clean and developer-friendly `README.md`** section for your backend that documents all the **API routes** logically with descriptions.

You can directly **include this in your backend's `README.md`**, or even generate a separate `API_DOCS.md` if you prefer to split it.

---

## API Endpoints – ThinkWise AI Backend

The backend exposes a RESTful API with endpoints for user authentication, idea analysis, AI chat, and analytics.

> Base URL: `http://localhost:8000` or your deployed URL

---

### Health

| Method | Endpoint  | Description          |
| ------ | --------- | -------------------- |
| GET    | `/health` | Check service status |

---

### Authentication

| Method | Endpoint                | Description                   |
| ------ | ----------------------- | ----------------------------- |
| POST   | `/auth/register`        | Register a new user           |
| POST   | `/auth/login`           | Log in and get access token   |
| GET    | `/auth/me`              | Fetch current user details    |
| POST   | `/auth/forgot-password` | Initiate password reset email |
| POST   | `/auth/reset-password`  | Complete password reset       |

---

### Chat with AI Idea Agent

| Method | Endpoint          | Description                                                |
| ------ | ----------------- | ---------------------------------------------------------- |
| POST   | `/chat/idea/{id}` | Ask follow-up questions to the agent about a specific idea |

---

### Idea Analysis

| Method | Endpoint          | Description                          |
| ------ | ----------------- | ------------------------------------ |
| POST   | `/analyze/single` | Submit one idea for analysis         |
| POST   | `/analyze/csv`    | Submit a CSV file for batch analysis |

---

### Idea Data & Management

| Method | Endpoint              | Description                             |
| ------ | --------------------- | --------------------------------------- |
| GET    | `/ideas/`             | Get all ideas for the current user      |
| GET    | `/ideas/{id}`         | Get full data for a specific idea       |
| GET    | `/ideas/{id}/history` | View chat history with that idea agent  |
| GET    | `/ideas/lookup`       | Lookup idea by filename and internal ID |
| DELETE | `/ideas/{id}`         | Delete a single idea                    |
| DELETE | `/ideas/`             | Delete all ideas for the user           |

---

### Rankings & Top Ideas

| Method | Endpoint             | Description                               |
| ------ | -------------------- | ----------------------------------------- |
| GET    | `/ideas/top`         | Get top-ranked ideas from a specific file |
| GET    | `/ideas/overall_top` | Get top ideas across all submissions      |

---

### Analytics

| Method | Endpoint           | Description                                                           |
| ------ | ------------------ | --------------------------------------------------------------------- |
| GET    | `/ideas/data`      | Get all idea data (for analytics processing)                          |
| GET    | `/ideas/analytics` | Get aggregated analytics (score, category, effort, ROI distributions) |

---


## Multi-Agent Workflow (LangGraph)

### Agent Architecture:

```text
              ┌────────────────────┐
              │  Single/CSV Input  │
              └─────────┬──────────┘
                        ↓
        ┌──────────────────────────────────┐
        │   LangGraph ReAct Multi-Agent    │
        └──────────────────────────────────┘
             ↓ Effort Estimator Tool
             ↓ ROI Estimator Tool (uses Tavily)
             ↓ Aggregator Node
                        ↓
              ┌────────────────────┐
              │    Final Output     │
              └────────────────────┘
```

Each agent tool:

* Fetches external or internal data
* Scores the idea on effort or ROI
* Logs reasoning and results

---

## .env Configuration

Create a `.env` file like:

```env
MONGODB_URI=mongodb://localhost:27017
JWT_SECRET=your_jwt_secret_here
TAVILY_API_KEY=your_tavily_api_key
GOOGLE_PROJECT_ID=your_gcp_project
VERTEX_REGION=us-central1
```

---

## Running Locally

```bash
git clone https://github.com/your-username/thinkwise-backend.git
cd thinkwise-backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Test endpoints with Postman or curl using the returned JWT token.

---

## Example Request

```bash
curl -X POST http://localhost:8000/analyze/single \
  -H "Authorization: Bearer <your_token>" \
  -F "idea=Build an AI-powered job matching system"
```

---

## Contributing

We welcome contributions related to:

* Improving LangGraph tool logic
* Adding new scoring heuristics
* Backend optimizations or CI/CD improvements

---

## Built with ❤️ at the Luddy Hackathon by the ThinkWise AI Team

---
