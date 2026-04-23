from typing import Optional
from fastapi import FastAPI, Request, Form, Depends
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

load_dotenv()

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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request, 
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    exercise: Optional[str] = None,
    db: Session = Depends(get_db)
):
    workouts = db.query(models.Workout).order_by(models.Workout.date.desc()).limit(5).all()
    sets_query = db.query(models.Set).join(models.Workout)
    total_volume = sum(s.weight * s.reps for s in sets_query.filter(models.Workout.category.notin_(["Cardio", "HIIT"])).all() if s.weight and s.reps)
    total_cardio_min = sum(s.reps for s in sets_query.filter(models.Workout.category.in_(["Cardio", "HIIT"])).all() if s.reps)
    total_cardio_dist = sum(s.weight for s in sets_query.filter(models.Workout.category.in_(["Cardio", "HIIT"])).all() if s.weight)
    
    today = date.today()
    s_date = today - timedelta(days=6)
    e_date = today
    
    if request.query_params.get("all_time"):
        first_workout = db.query(models.Workout).order_by(models.Workout.date.asc()).first()
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
    
    # Extract all unique categories and exercises for the dropdowns
    exercises_by_cat = {}
    all_workouts = db.query(models.Workout).all()
    for w in all_workouts:
        if w.category not in exercises_by_cat:
            exercises_by_cat[w.category] = set()
        for s in w.sets:
            if s.exercise and s.exercise.name:
                exercises_by_cat[w.category].add(s.exercise.name)
    
    # Sort the data
    for k in exercises_by_cat:
        exercises_by_cat[k] = sorted(list(exercises_by_cat[k]))
        
    weekly_labels = []
    weekly_weight = []
    weekly_reps = []
    weekly_cardio = []
    
    for i in range(delta + 1):
        d = s_date + timedelta(days=i)
        weekly_labels.append(d.strftime("%b %d"))
        
        query = db.query(models.Set).join(models.Workout).filter(models.Workout.date == d)
        if category:
            query = query.filter(models.Workout.category == category)
        if exercise:
            query = query.join(models.Exercise).filter(models.Exercise.name == exercise)
            
        day_sets = query.all()
        
        if day_sets:
            max_w = max((s.weight for s in day_sets if s.weight), default=0)
            max_r = max((s.reps for s in day_sets if s.reps), default=0)
            # Max duration for the day if it's cardio
            cardio_durations = [s.reps for s in day_sets if s.reps and s.workout.category == "Cardio"]
            max_c = max(cardio_durations, default=0)
        else:
            max_w = 0
            max_r = 0
            max_c = 0
            
        weekly_weight.append(max_w)
        weekly_reps.append(max_r)
        weekly_cardio.append(max_c)
        
    # Calculate current streak
    unique_dates_raw = [d[0] for d in db.query(models.Workout.date).distinct().order_by(models.Workout.date.desc()).all()]
    unique_dates = [d.isoformat() if hasattr(d, 'isoformat') else str(d) for d in unique_dates_raw]
    
    current_streak = 0
    if unique_dates:
        check_date = today
        check_str = check_date.isoformat()
        
        if check_str not in unique_dates:
            check_date -= timedelta(days=1)
            check_str = check_date.isoformat()
            
        while check_str in unique_dates:
            current_streak += 1
            check_date -= timedelta(days=1)
            check_str = check_date.isoformat()

    # Calculate workouts this week
    week_start = today - timedelta(days=today.weekday())
    workouts_this_week = db.query(models.Workout).filter(models.Workout.date >= week_start).count()

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
            "exercises_by_cat": exercises_by_cat
        }
    )

@app.get("/log", response_class=HTMLResponse)
async def log_workout_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="log.html", 
        context={"today": date.today().isoformat()}
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
    db: Session = Depends(get_db)
):
    try:
        w_date = datetime.strptime(workout_date, "%Y-%m-%d").date()
    except ValueError:
        w_date = date.today()

    workout = db.query(models.Workout).filter(
        models.Workout.date == w_date, 
        models.Workout.category == workout_category
    ).first()
    
    if not workout:
        workout = models.Workout(date=w_date, category=workout_category, notes="")
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
async def workout_history(request: Request, db: Session = Depends(get_db)):
    workouts = db.query(models.Workout).order_by(models.Workout.date.desc()).all()
    
    history_data = []

    for w in workouts:
        exercises_summary = {}
        for s in w.sets:
            ex_name = s.exercise.name
            if ex_name not in exercises_summary:
                exercises_summary[ex_name] = {"max_weight": 0, "max_reps": 0, "all_sets": []}
            
            exercises_summary[ex_name]["all_sets"].append({
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
        context={"history_data": history_data}
    )

@app.post("/history/delete_exercise/{exercise_id}")
async def delete_exercise(exercise_id: int, db: Session = Depends(get_db)):
    exercise_to_delete = db.query(models.Set).filter(models.Set.id == exercise_id).first()
    if exercise_to_delete:
        db.delete(exercise_to_delete)
        db.commit()
    return {"status": "success"}

@app.get("/timer", response_class=HTMLResponse)
async def timer_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="timer.html"
    )

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="settings.html"
    )

import csv
import io
from fastapi import UploadFile, File
from fastapi.responses import StreamingResponse

@app.get("/settings/export")
async def export_workouts(db: Session = Depends(get_db)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Category", "Exercise", "Weight", "Reps", "Notes"])
    
    workouts = db.query(models.Workout).all()
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
async def import_workouts(file: UploadFile = File(...), db: Session = Depends(get_db)):
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
                models.Workout.date == w_date,
                models.Workout.category == category
            ).first()
            if not workout:
                workout = models.Workout(date=w_date, category=category, notes=notes)
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
async def ask_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="ask.html"
    )

class ChatMessage(BaseModel):
    message: str
    history: list = []
    api_key: str = ""

@app.post("/ask/chat")
async def ask_chat(payload: ChatMessage):
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
async def delete_workout(workout_id: int, db: Session = Depends(get_db)):
    workout = db.query(models.Workout).filter(models.Workout.id == workout_id).first()
    if workout:
        db.delete(workout)
        db.commit()
        return {"status": "success"}
    return {"status": "error", "message": "Workout not found"}, 404

@app.delete("/workout/{workout_id}/exercise/{exercise_name}")
async def delete_workout_exercise(workout_id: int, exercise_name: str, db: Session = Depends(get_db)):
    exercise = db.query(models.Exercise).filter(models.Exercise.name == exercise_name).first()
    if not exercise:
        return {"status": "error", "message": "Exercise not found"}, 404
        
    sets_deleted = db.query(models.Set).filter(
        models.Set.workout_id == workout_id,
        models.Set.exercise_id == exercise.id
    ).delete()
    
    db.commit()
    return {"status": "success", "deleted_count": sets_deleted}

@app.post("/workout/{workout_id}/category")
async def update_workout_category(workout_id: int, category: str = Form(...), db: Session = Depends(get_db)):
    workout = db.query(models.Workout).filter(models.Workout.id == workout_id).first()
    if workout:
        workout.category = category
        db.commit()
        return {"status": "success"}
    return {"status": "error", "message": "Workout not found"}, 404
