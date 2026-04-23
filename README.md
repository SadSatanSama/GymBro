# 🏋️ GymBro - Your Ultimate Fitness Companion

**GymBro** is a sleek, mobile-first workout tracker designed to help you crush your fitness goals with ease. Built with FastAPI and modern CSS, it combines powerful tracking features with a premium, glassmorphic UI.

![GymBro Dashboard](/static/logo.png)

## ✨ Features

- **📊 Dynamic Dashboard**: Visualize your progress with interactive charts (Weight, Reps, and Cardio) using Chart.js.
- **📝 Effortless Logging**: Log Strength training (Weight/Reps) and Cardio sessions in seconds.
- **🤖 AI Coach**: An integrated fitness assistant powered by Google Gemini to answer your training, nutrition, and recovery questions.
- **📱 PWA Ready**: Install GymBro directly on your Android or iOS device for a full-screen, native app experience.
- **🌐 Internationalization**: Full support for **English**, **Hindi**, and **Spanish**.
- **📅 Smart History**: Filter your past workouts by date and category to track your journey over time.
- **💾 Data Portability**: Export your entire workout history to CSV or import data from other trackers.
- **⚖️ Unit Preferences**: Seamlessly switch between `kg/lbs` and `km/miles`.

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- A Google Gemini API Key (Optional, for AI features)

### Installation
1. **Clone the repository**:
   ```bash
   git clone https://github.com/SadSatanSama/gymbro
   cd gymbro
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app**:
   ```bash
   uvicorn main:app --reload
   ```
4. Open your browser to `http://127.0.0.1:8000`.

## ☁️ Deployment (Render)

GymBro is pre-configured for one-click deployment on **Render**:

1. Push this code to a GitHub repository.
2. Go to [Render Dashboard](https://dashboard.render.com).
3. Click **New +** -> **Blueprint**.
4. Select your repository.
5. Render will automatically set up the persistent disk and deploy your app.

## 🛠️ Tech Stack
- **Backend**: FastAPI (Python)
- **Database**: SQLite with SQLAlchemy
- **Frontend**: Vanilla JS, Modern CSS (Glassmorphism), Jinja2 Templates
- **Charts**: Chart.js
- **AI**: Google Gemini API

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).

---
*Built with 💪 by Arijit Das*
