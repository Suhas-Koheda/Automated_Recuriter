from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base


class CandidateStatus(str, enum.Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    INTERVIEWED = "interviewed"
    SELECTED = "selected"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class Candidate(Base):
    __tablename__ = "candidates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True)
    email = Column(String(100), unique=True, index=True)
    phone = Column(String(20), nullable=True)
    resume_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String, default=CandidateStatus.PENDING)
    
    # Relationships
    job_applications = relationship("JobApplication", back_populates="candidate")
    interviews = relationship("Interview", back_populates="candidate")


class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), index=True)
    description = Column(Text)
    requirements = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    job_applications = relationship("JobApplication", back_populates="job")


class JobApplication(Base):
    __tablename__ = "job_applications"
    
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    job_id = Column(Integer, ForeignKey("jobs.id"))
    applied_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default=CandidateStatus.PENDING)
    
    # Relationships
    candidate = relationship("Candidate", back_populates="job_applications")
    job = relationship("Job", back_populates="job_applications")
    interviews = relationship("Interview", back_populates="job_application")


class Interview(Base):
    __tablename__ = "interviews"
    
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    job_application_id = Column(Integer, ForeignKey("job_applications.id"))
    scheduled_time = Column(DateTime)
    duration_minutes = Column(Integer, default=30)
    zoom_meeting_id = Column(String(100), nullable=True)
    zoom_meeting_url = Column(String(255), nullable=True)
    zoom_meeting_password = Column(String(100), nullable=True)
    recording_url = Column(String(255), nullable=True)
    status = Column(String, default="scheduled")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    candidate = relationship("Candidate", back_populates="interviews")
    job_application = relationship("JobApplication", back_populates="interviews")
    questions = relationship("InterviewQuestion", back_populates="interview")
    evaluation = relationship("InterviewEvaluation", back_populates="interview", uselist=False)


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"
    
    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"))
    question_text = Column(Text)
    order = Column(Integer)
    response = Column(Text, nullable=True)
    response_audio_url = Column(String(255), nullable=True)
    response_evaluation = Column(Text, nullable=True)
    
    # Relationships
    interview = relationship("Interview", back_populates="questions")


class InterviewEvaluation(Base):
    __tablename__ = "interview_evaluations"
    
    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), unique=True)
    technical_score = Column(Float, nullable=True)
    behavioral_score = Column(Float, nullable=True)
    communication_score = Column(Float, nullable=True)
    overall_score = Column(Float, nullable=True)
    plagiarism_detected = Column(Boolean, default=False)
    recommendation = Column(String, nullable=True)
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    interview = relationship("Interview", back_populates="evaluation")