from typing import Optional
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database import init_db, SessionLocal
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from pydantic import BaseModel
import models
import os
from dotenv import load_dotenv
import google.generativeai as genai

# Security Imports
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer

load_dotenv()

# Auth Config
SECRET_KEY = os.getenv("SECRET_KEY", "gymbro-super-secret-key-change-this-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 1 week

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

GYMBRO_SYSTEM_PROMPT = """You are GymBro, a friendly and knowledgeable AI fitness assistant built into a gym tracking app.
You ONLY answer questions related to: gym workouts, exercise form, training programs, muscle groups, fitness goals, sports nutrition, diet, supplements, rest and recovery, body composition, and general health and wellness.
If a user asks about ANY topic outside of fitness and health (e.g. politics, coding, movies, math), you must politely decline and remind them you are a gym-only assistant.
Be encouraging, motivating, and concise. Use bullet points for lists. Keep responses clear and practical."""

# Initialize database
init_db()

app = FastAPI(title="Gym Progress Tracker")

# Mount Static Files and Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Helper functions for Auth
def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@app.get("/.well-known/assetlinks.json")
async def get_assetlinks():
    return [{
      "relation": ["delegate_permission/common.handle_all_urls"],
      "target": {
        "namespace": "android_app",
        "package_name": "com.onrender.gymbro_euvi.twa",
        "sha256_cert_fingerprints": ["AC:38:CB:A1:D9:B8:F6:FB:E0:59:64:01:16:DD:E4:DE:39:9B:05:43:55:E2:8C:16:DB:EF:DD:DD:77:ED:C5:AB"]
      }
    }]

@app.get("/sw.js")
async def get_sw():
    from fastapi.responses import FileResponse
    return FileResponse("static/sw.js")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Dependency to get current user from cookie
async def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
    except JWTError:
        return None
    
    user = db.query(models.User).filter(models.User.email == email).first()
    return user

# --- Auth Routes ---
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "user": None})

@app.post("/login")
async def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": {}, "error": "Invalid email or password", "user": None})
    
    token = create_access_token(data={"sub": email})
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    return response

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "user": None})

@app.post("/register")
async def register(username: str = Form(...), email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.email == email).first()
    if existing_user:
        return templates.TemplateResponse("register.html", {"request": {}, "error": "Email already registered", "user": None})
    
    hashed_pwd = get_password_hash(password)
    new_user = models.User(email=email, hashed_password=hashed_pwd, username=username)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # --- Data Migration ---
    # If this is the first user, or if there are orphan workouts, assign them to this user
    orphan_workouts = db.query(models.Workout).filter(models.Workout.user_id == None).all()
    if orphan_workouts:
        for w in orphan_workouts:
            w.user_id = new_user.id
        db.commit()

    token = create_access_token(data={"sub": email})
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response

# --- Protected Routes ---
@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request, 
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    exercise: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse(url="/login")
    workouts = db.query(models.Workout).filter(models.Workout.user_id == current_user.id).order_by(models.Workout.date.desc()).limit(5).all()
    sets_query = db.query(models.Set).join(models.Workout).filter(models.Workout.user_id == current_user.id)
    total_volume = sum(s.weight * s.reps for s in sets_query.filter(models.Workout.category.notin_(["Cardio", "HIIT"])).all() if s.weight and s.reps)
    total_cardio_min = sum(s.reps for s in sets_query.filter(models.Workout.category.in_(["Cardio", "HIIT"])).all() if s.reps)
    total_cardio_dist = sum(s.weight for s in sets_query.filter(models.Workout.category.in_(["Cardio", "HIIT"])).all() if s.weight)
    
    today = date.today()
    s_date = today - timedelta(days=6)
    e_date = today
    
    if request.query_params.get("all_time"):
        first_workout = db.query(models.Workout).filter(models.Workout.user_id == current_user.id).order_by(models.Workout.date.asc()).first()
        if first_workout:
            s_date = first_workout.date
    else:
        if start_date:
            try:
                s_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                pass
        if end_date:
            try:
                e_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                pass
            
    if e_date < s_date:
        e_date = s_date

    delta = (e_date - s_date).days
    
    # Extract all unique categories and exercises safely
    exercises_by_cat = {}
    all_workouts = db.query(models.Workout).filter(models.Workout.user_id == current_user.id).all()
    for w in all_workouts:
        cat = w.category or "Uncategorized"
        if cat not in exercises_by_cat:
            exercises_by_cat[cat] = set()
        for s in w.sets:
            if s.exercise and s.exercise.name:
                exercises_by_cat[cat].add(s.exercise.name)
    
    # Convert sets to sorted lists for JSON serialization
    safe_exercises_by_cat = {}
    for k, v in exercises_by_cat.items():
        safe_exercises_by_cat[k] = sorted(list(v))
        
    weekly_labels = []
    weekly_weight = []
    weekly_reps = []
    weekly_cardio = []
    
    for i in range(delta + 1):
        d = s_date + timedelta(days=i)
        weekly_labels.append(d.strftime("%b %d"))
        
        query = db.query(models.Set).join(models.Workout).filter(models.Workout.user_id == current_user.id, models.Workout.date == d)
        if category:
            query = query.filter(models.Workout.category == category)
        if exercise:
            query = query.join(models.Exercise).filter(models.Exercise.name == exercise)
            
        day_sets = query.all()
        
        if day_sets:
            max_w = max((s.weight for s in day_sets if s.weight), default=0)
            max_r = max((s.reps for s in day_sets if s.reps), default=0)
            # Max duration for the day if it's cardio
            cardio_durations = [s.reps for s in day_sets if s.reps and s.workout and s.workout.category and s.workout.category in ["Cardio", "HIIT"]]
            max_c = max(cardio_durations, default=0)
        else:
            max_w = 0
            max_r = 0
            max_c = 0
            
        weekly_weight.append(max_w)
        weekly_reps.append(max_r)
        weekly_cardio.append(max_c)
        
    # Calculate current streak safely
    unique_dates_raw = db.query(models.Workout.date).join(models.Set).filter(models.Workout.user_id == current_user.id).distinct().all()
    unique_dates = {d[0].isoformat() for d in unique_dates_raw if d[0]}
    
    current_streak = 0
    if unique_dates:
        check_date = today
        while check_date.isoformat() in unique_dates or (check_date == today and (check_date - timedelta(days=1)).isoformat() in unique_dates):
            if check_date.isoformat() in unique_dates:
                current_streak += 1
                check_date -= timedelta(days=1)
            else:
                # If today hasn't been logged yet, but yesterday was, the streak is still alive
                check_date -= timedelta(days=1)
                if check_date.isoformat() not in unique_dates:
                    break

    # Calculate workouts this week
    week_start = today - timedelta(days=today.weekday())
    workouts_this_week = db.query(models.Workout).join(models.Set).filter(models.Workout.user_id == current_user.id, models.Workout.date >= week_start).distinct().count()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "total_volume": round(total_volume, 1),
            "total_cardio_min": total_cardio_min,
            "total_cardio_dist": round(total_cardio_dist, 1),
            "weekly_labels": weekly_labels,
            "weekly_weight": weekly_weight,
            "weekly_reps": weekly_reps,
            "weekly_cardio": weekly_cardio,
            "workouts_this_week": workouts_this_week,
            "current_streak": current_streak,
            "start_date": s_date.isoformat(),
            "end_date": e_date.isoformat(),
            "selected_category": category or "",
            "selected_exercise": exercise or "",
            "exercises_by_cat": safe_exercises_by_cat,
            "user": current_user
        }
    )

@app.get("/log", response_class=HTMLResponse)
async def log_workout_form(request: Request, current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(
        request=request,
        name="log.html", 
        context={"today": date.today().isoformat(), "user": current_user}
    )

@app.post("/log")
async def process_log(
    request: Request,
    workout_date: str = Form(...),
    workout_category: str = Form(None),
    exercise_name: str = Form(...),
    weight: float = Form(...),
    reps: int = Form(...),
    notes: str = Form(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        return JSONResponse({"status": "error", "message": "Not logged in"}, status_code=401)
        
    try:
        w_date = datetime.strptime(workout_date, "%Y-%m-%d").date()
    except ValueError:
        w_date = date.today()

    workout = db.query(models.Workout).filter(
        models.Workout.user_id == current_user.id,
        models.Workout.date == w_date, 
        models.Workout.category == workout_category
    ).first()
    
    if not workout:
        workout = models.Workout(user_id=current_user.id, date=w_date, category=workout_category, notes="")
        db.add(workout)
        db.commit()
        db.refresh(workout)

    exercise = db.query(models.Exercise).filter(models.Exercise.name == exercise_name).first()
    if not exercise:
        exercise = models.Exercise(name=exercise_name, muscle_group="Unknown")
        db.add(exercise)
        db.commit()
        db.refresh(exercise)

    new_set = models.Set(
        workout_id=workout.id,
        exercise_id=exercise.id,
        weight=weight,
        reps=reps
    )
    if notes and not workout.notes:
        workout.notes = notes
    elif notes:
        workout.notes += f" | {notes}"

    db.add(new_set)
    db.commit()

    return {"status": "success", "message": "Set logged successfully!"}

@app.get("/history", response_class=HTMLResponse)
async def workout_history(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login")
    workouts = db.query(models.Workout).filter(models.Workout.user_id == current_user.id).order_by(models.Workout.date.desc()).all()
    
    history_data = []

    for w in workouts:
        exercises_summary = {}
        for s in w.sets:
            ex_name = s.exercise.name
            if ex_name not in exercises_summary:
                exercises_summary[ex_name] = {"max_weight": 0, "max_reps": 0, "all_sets": []}
            
            exercises_summary[ex_name]["all_sets"].append({
                "id": s.id,
                "weight": s.weight,
                "reps": s.reps
            })
            if s.weight and s.weight > exercises_summary[ex_name]["max_weight"]:
                exercises_summary[ex_name]["max_weight"] = s.weight
            if s.reps and s.reps > exercises_summary[ex_name]["max_reps"]:
                exercises_summary[ex_name]["max_reps"] = s.reps
                
        if exercises_summary or w.notes:
            history_data.append({
                "id": w.id,
                "raw_date": w.date.isoformat(),
                "display_date": w.date.strftime("%b %d, %Y"),
                "category": w.category or "Uncategorized",
                "notes": w.notes,
                "exercises": exercises_summary
            })

    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"history_data": history_data, "user": current_user}
    )

@app.delete("/set/{set_id}")
async def delete_set(set_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not current_user: return JSONResponse({"status": "error"}, status_code=401)
    set_to_delete = db.query(models.Set).join(models.Workout).filter(models.Set.id == set_id, models.Workout.user_id == current_user.id).first()
    if set_to_delete:
        workout_id = set_to_delete.workout_id
        db.delete(set_to_delete)
        db.commit()
        
        # Cleanup: If no sets left in workout, delete workout
        remaining = db.query(models.Set).filter(models.Set.workout_id == workout_id).count()
        if remaining == 0:
            workout = db.query(models.Workout).filter(models.Workout.id == workout_id).first()
            if workout:
                db.delete(workout)
                db.commit()
                return {"status": "success", "workout_deleted": True}
        
        return {"status": "success", "workout_deleted": False}
    return {"status": "error", "message": "Set not found"}, 404

@app.post("/set/{set_id}/edit")
async def edit_set(set_id: int, weight: float = Form(...), reps: int = Form(...), db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not current_user: return JSONResponse({"status": "error"}, status_code=401)
    target_set = db.query(models.Set).join(models.Workout).filter(models.Set.id == set_id, models.Workout.user_id == current_user.id).first()
    if target_set:
        target_set.weight = weight
        target_set.reps = reps
        db.commit()
        return {"status": "success"}
    return {"status": "error", "message": "Set not found"}, 404

@app.post("/history/delete_exercise/{exercise_id}")
async def delete_exercise(exercise_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not current_user: return JSONResponse({"status": "error"}, status_code=401)
    exercise_to_delete = db.query(models.Set).join(models.Workout).filter(models.Set.id == exercise_id, models.Workout.user_id == current_user.id).first()
    if exercise_to_delete:
        db.delete(exercise_to_delete)
        db.commit()
    return {"status": "success"}

@app.get("/timer", response_class=HTMLResponse)
async def timer_page(request: Request, current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(
        request=request,
        name="timer.html",
        context={"user": current_user}
    )

@app.get("/offline", response_class=HTMLResponse)
async def offline_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="offline.html",
        context={"user": None}
    )

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={"user": current_user}
    )

import csv
import io
from fastapi import UploadFile, File
from fastapi.responses import StreamingResponse

@app.get("/settings/export")
async def export_workouts(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not current_user: return JSONResponse({"status": "error"}, status_code=401)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Category", "Exercise", "Weight", "Reps", "Notes"])
    
    workouts = db.query(models.Workout).filter(models.Workout.user_id == current_user.id).all()
    for w in workouts:
        for s in w.sets:
            writer.writerow([
                w.date.isoformat(),
                w.category or "",
                s.exercise.name,
                s.weight or 0,
                s.reps or 0,
                w.notes or ""
            ])
            
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=gymbro_history.csv"}
    )

@app.post("/settings/import")
async def import_workouts(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not current_user: return JSONResponse({"status": "error"}, status_code=401)
    content = await file.read()
    stream = io.StringIO(content.decode('utf-8'))
    reader = csv.DictReader(stream)
    
    import_count = 0
    for row in reader:
        try:
            w_date = datetime.strptime(row["Date"], "%Y-%m-%d").date()
            category = row["Category"]
            ex_name = row["Exercise"]
            weight = float(row["Weight"])
            reps = int(row["Reps"])
            notes = row.get("Notes", "")

            # Find or create workout
            workout = db.query(models.Workout).filter(
                models.Workout.user_id == current_user.id,
                models.Workout.date == w_date,
                models.Workout.category == category
            ).first()
            if not workout:
                workout = models.Workout(user_id=current_user.id, date=w_date, category=category, notes=notes)
                db.add(workout)
                db.commit()
                db.refresh(workout)
            
            # Find or create exercise
            exercise = db.query(models.Exercise).filter(models.Exercise.name == ex_name).first()
            if not exercise:
                exercise = models.Exercise(name=ex_name, muscle_group="Unknown")
                db.add(exercise)
                db.commit()
                db.refresh(exercise)
            
            # Add set
            new_set = models.Set(
                workout_id=workout.id,
                exercise_id=exercise.id,
                weight=weight,
                reps=reps
            )
            db.add(new_set)
            import_count += 1
        except Exception as e:
            print(f"Error importing row: {e}")
            continue
            
    db.commit()
    return {"status": "success", "message": f"Successfully imported {import_count} sets!"}

@app.get("/ask", response_class=HTMLResponse)
async def ask_page(request: Request, current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(
        request=request,
        name="ask.html",
        context={"user": current_user}
    )

class ChatMessage(BaseModel):
    message: str
    history: list = []
    api_key: str = ""

@app.post("/ask/chat")
async def ask_chat(payload: ChatMessage, current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return JSONResponse({"reply": "Please log in to talk to GymBro."}, status_code=401)
    if not payload.api_key:
        return JSONResponse({"reply": "__NO_KEY__"}, status_code=401)
    try:
        user_genai = genai.Client(api_key=payload.api_key)
        response = user_genai.models.generate_content(
            model="gemini-1.5-flash",
            contents=[
                *[{"role": msg["role"], "parts": [{"text": msg["text"]}]} for msg in payload.history],
                {"role": "user", "parts": [{"text": payload.message}]}
            ],
            config={"system_instruction": GYMBRO_SYSTEM_PROMPT}
        )
        return JSONResponse({"reply": response.text})
    except Exception as e:
        err = str(e).lower()
        if "api_key" in err or "invalid" in err or "403" in err or "401" in err:
            return JSONResponse({"reply": "__BAD_KEY__"}, status_code=401)
        return JSONResponse({"reply": "Sorry, I'm having trouble connecting right now. Please try again!"}, status_code=500)

@app.delete("/workout/{workout_id}")
async def delete_workout(workout_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not current_user: return JSONResponse({"status": "error"}, status_code=401)
    workout = db.query(models.Workout).filter(models.Workout.id == workout_id, models.Workout.user_id == current_user.id).first()
    if workout:
        db.delete(workout)
        db.commit()
        return {"status": "success"}
    return {"status": "error", "message": "Workout not found"}, 404

@app.delete("/workout/{workout_id}/exercise/{exercise_name}")
async def delete_workout_exercise(workout_id: int, exercise_name: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not current_user: return JSONResponse({"status": "error"}, status_code=401)
    # Ensure workout belongs to user
    workout_exists = db.query(models.Workout).filter(models.Workout.id == workout_id, models.Workout.user_id == current_user.id).first()
    if not workout_exists:
        return JSONResponse({"status": "error", "message": "Workout not found"}, status_code=404)
    exercise = db.query(models.Exercise).filter(models.Exercise.name == exercise_name).first()
    if not exercise:
        return {"status": "error", "message": "Exercise not found"}, 404
        
    sets_deleted = db.query(models.Set).filter(
        models.Set.workout_id == workout_id,
        models.Set.exercise_id == exercise.id
    ).delete()
    
    db.commit()
    
    # Check if the workout is now empty
    remaining_sets = db.query(models.Set).filter(models.Set.workout_id == workout_id).count()
    if remaining_sets == 0:
        workout = db.query(models.Workout).filter(models.Workout.id == workout_id).first()
        if workout:
            db.delete(workout)
            db.commit()
            return {"status": "success", "deleted_count": sets_deleted, "workout_deleted": True}
            
    return {"status": "success", "deleted_count": sets_deleted, "workout_deleted": False}

@app.post("/workout/{workout_id}/category")
async def update_workout_category(workout_id: int, category: str = Form(...), db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not current_user: return JSONResponse({"status": "error"}, status_code=401)
    workout = db.query(models.Workout).filter(models.Workout.id == workout_id, models.Workout.user_id == current_user.id).first()
    if not workout:
        return {"status": "error", "message": "Workout not found"}, 404

    # Check if a workout with the target category already exists ON THE SAME DAY FOR THIS USER
    existing_workout = db.query(models.Workout).filter(
        models.Workout.user_id == current_user.id,
        models.Workout.date == workout.date,
        models.Workout.category == category,
        models.Workout.id != workout_id
    ).first()

    if existing_workout:
        # Move all sets from current workout to the existing one using bulk update
        # This avoids the "delete-orphan" cascade issue
        db.query(models.Set).filter(models.Set.workout_id == workout.id).update(
            {"workout_id": existing_workout.id}, 
            synchronize_session='fetch'
        )
        
        # Merge notes if they exist
        if workout.notes:
            if existing_workout.notes:
                existing_workout.notes += f" | {workout.notes}"
            else:
                existing_workout.notes = workout.notes
        
        db.delete(workout)
        db.commit()
        return {"status": "merged", "new_id": existing_workout.id}
    else:
        # Just update the category
        workout.category = category
        db.commit()
        return {"status": "success"}
