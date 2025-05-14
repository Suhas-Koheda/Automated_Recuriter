from pydantic import BaseModel, EmailStr, Field, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class CandidateStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    INTERVIEWED = "interviewed"
    SELECTED = "selected"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


# Base Pydantic Models
class CandidateBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    resume_url: Optional[str] = None


class JobBase(BaseModel):
    title: str
    description: str
    requirements: str
    is_active: bool = True


class InterviewBase(BaseModel):
    scheduled_time: datetime
    duration_minutes: int = 30


class InterviewQuestionBase(BaseModel):
    question_text: str
    order: int


class InterviewEvaluationBase(BaseModel):
    technical_score: Optional[float] = None
    behavioral_score: Optional[float] = None
    communication_score: Optional[float] = None
    overall_score: Optional[float] = None
    plagiarism_detected: bool = False
    recommendation: Optional[str] = None
    feedback: Optional[str] = None


# Create Models
class CandidateCreate(CandidateBase):
    pass


class JobCreate(JobBase):
    pass


class InterviewCreate(InterviewBase):
    candidate_id: int
    job_application_id: int


class InterviewQuestionCreate(InterviewQuestionBase):
    interview_id: int


class InterviewEvaluationCreate(InterviewEvaluationBase):
    interview_id: int


# Response Models
class CandidateResponse(CandidateBase):
    id: int
    created_at: datetime
    updated_at: datetime
    status: str
    
    class Config:
        orm_mode = True


class JobResponse(JobBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


class JobApplicationResponse(BaseModel):
    id: int
    candidate_id: int
    job_id: int
    applied_date: datetime
    status: str
    
    class Config:
        orm_mode = True


class InterviewQuestionResponse(InterviewQuestionBase):
    id: int
    interview_id: int
    response: Optional[str] = None
    response_audio_url: Optional[str] = None
    response_evaluation: Optional[str] = None
    
    class Config:
        orm_mode = True


class InterviewEvaluationResponse(InterviewEvaluationBase):
    id: int
    interview_id: int
    created_at: datetime
    
    class Config:
        orm_mode = True


class InterviewResponse(InterviewBase):
    id: int
    candidate_id: int
    job_application_id: int
    zoom_meeting_id: Optional[str] = None
    zoom_meeting_url: Optional[str] = None
    zoom_meeting_password: Optional[str] = None
    recording_url: Optional[str] = None
    status: str
    created_at: datetime
    questions: Optional[List[InterviewQuestionResponse]] = []
    evaluation: Optional[InterviewEvaluationResponse] = None
    
    class Config:
        orm_mode = True


# Additional schemas for specific operations
class ScheduleInterviewRequest(BaseModel):
    candidate_email: EmailStr
    job_id: int
    scheduled_time: datetime
    duration_minutes: int = 30


class InterviewResultRequest(BaseModel):
    interview_id: int


class InterviewResultResponse(BaseModel):
    interview_id: int
    candidate_name: str
    job_title: str
    overall_score: float
    recommendation: str
    detailed_evaluation: Dict[str, Any]
    
    class Config:
        orm_mode = True


class ZoomMeetingResponse(BaseModel):
    meeting_id: str
    join_url: str
    password: Optional[str] = None
    start_url: str


class GenerateQuestionsRequest(BaseModel):
    job_id: int
    num_questions: int = 5


class GenerateQuestionsResponse(BaseModel):
    questions: List[str]