from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Workout(Base):
    __tablename__ = "workouts"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, index=True)
    category = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    
    sets = relationship("Set", back_populates="workout", cascade="all, delete-orphan")

class Exercise(Base):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    muscle_group = Column(String)
    
    sets = relationship("Set", back_populates="exercise")

class Set(Base):
    __tablename__ = "sets"
    id = Column(Integer, primary_key=True, index=True)
    workout_id = Column(Integer, ForeignKey("workouts.id"))
    exercise_id = Column(Integer, ForeignKey("exercises.id"))
    weight = Column(Float)
    reps = Column(Integer)
    
    workout = relationship("Workout", back_populates="sets")
    exercise = relationship("Exercise", back_populates="sets")
