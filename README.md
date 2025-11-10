# 🎓 Quizly – AI-Powered Quiz Generator

Quizly is a Django & React-based web application that allows users to automatically generate multiple‑choice quizzes from YouTube videos.  
The system downloads audio, transcribes it using Whisper, and uses Google Gemini to generate structured quiz questions.  
Users can manage, edit, and delete their own quizzes — all with secure authentication.

---

## 🚀 Features

✅ **AI‑Generated Quizzes** from YouTube video content  
✅ **Secure User Authentication** (JWT + HttpOnly cookies)  
✅ **Transcription via Whisper**  
✅ **Quiz Generation via Google Gemini API**  
✅ **Full CRUD for Quizzes**  
✅ **Comprehensive Test Suite** using `pytest`  
✅ **80%+ Test Coverage** ensured with `coverage.py`  
✅ **CORS-ready REST API** built with Django REST Framework

---

## 🛠️ Tech Stack

**Backend:**

- Django 5
- Django REST Framework
- SimpleJWT
- Whisper (openai‑whisper)
- Google Gemini (google-genai)
- yt‑dlp
- pytest / pytest‑django

---

## 📦 Installation

### 1️⃣ Clone the repository

```bash
git clone https://github.com/JoCro/Quizzly.git
cd quizly
```

### 2️⃣ Create a virtual environment

```bash
python -m venv .env
source .env/bin/activate
```

### 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Run migrations

```bash
python manage.py migrate
```

### 5️⃣ Start the development server

```bash
python manage.py runserver
```

---

## 🔑 Environment Variables

Create a `.env` file in your .env-folder:
**f.e. the .env.example-file**

```
GEMINI_API_KEY=your_api_key (required!)
OPTIONALS :
SECRET_KEY=your_secret_key
DEBUG=True
```

---

## ✅ Running Tests

Run the full test suite:

```bash
pytest -q
```

Generate a coverage report:

```bash
pytest --cov
```

---

## 📚 API Overview

### 🔐 Authentication

- `POST /api/register/` — Create a user
- `POST /api/login/` — Login with JWTs
- `POST /api/logout/` — Clear cookies
- `POST /api/token/refresh/` — Refresh access token

### 📝 Quizzes

- `POST /api/createQuiz/` — Generate quiz from YouTube URL
- `GET /api/quizzes/` — List user quizzes
- `GET /api/quizzes/{id}/` — Retrieve quiz
- `PATCH /api/quizzes/{id}/` — Update quiz
- `DELETE /api/quizzes/{id}/` — Delete quiz

---

## 🧪 Test Coverage

✅ 80%+ total coverage required  
✅ Mocked AI/video/download calls  
✅ Full coverage of CRUD and auth flows

---

## 📂 Project Structure

```
quizly/
│── core/                 # Django settings
│── quizzly_app/          # Quiz generation logic
│   ├── api/
│   ├── models.py
│   ├── tests/
│── user_auth_app/        # Auth system
│   ├── api/
│   ├── tests/
│── requirements.txt
│── manage.py
```

---

## 🤝 Contributing

Pull requests are welcome!  
Please open an issue first to discuss major changes.

---

## 📄 License

MIT License. You are free to use this project for learning, experimenting, or extending your own applications.

---
