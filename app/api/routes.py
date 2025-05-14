from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Path
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from app.core.database import get_db
from app.models import schemas, database as models
from app.services.zoom_service import zoom_service
from app.services.email_service import email_service
from app.services.gemini_service import gemini_service
from app.utils.interview_utils import interview_manager
from app.utils.analysis_utils import interview_analyzer

router = APIRouter()
logger = logging.getLogger(__name__)


# Candidate endpoints
@router.post("/candidates/", response_model=schemas.CandidateResponse)
async def create_candidate(
    candidate: schemas.CandidateCreate,
    db: Session = Depends(get_db)
):
    """Create a new candidate"""
    # Check if candidate with this email already exists
    db_candidate = db.query(models.Candidate).filter(
        models.Candidate.email == candidate.email
    ).first()
    
    if db_candidate:
        raise HTTPException(status_code=400, detail="Candidate with this email already exists")
    
    # Create new candidate
    db_candidate = models.Candidate(
        name=candidate.name,
        email=candidate.email,
        phone=candidate.phone,
        resume_url=candidate.resume_url
    )
    
    db.add(db_candidate)
    db.commit()
    db.refresh(db_candidate)
    
    return db_candidate


@router.get("/candidates/", response_model=List[schemas.CandidateResponse])
async def get_candidates(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all candidates"""
    candidates = db.query(models.Candidate).offset(skip).limit(limit).all()
    return candidates


@router.get("/candidates/{candidate_id}", response_model=schemas.CandidateResponse)
async def get_candidate(
    candidate_id: int = Path(..., description="The ID of the candidate to get"),
    db: Session = Depends(get_db)
):
    """Get a specific candidate by ID"""
    candidate = db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    return candidate


# Job endpoints
@router.post("/jobs/", response_model=schemas.JobResponse)
async def create_job(
    job: schemas.JobCreate,
    db: Session = Depends(get_db)
):
    """Create a new job posting"""
    db_job = models.Job(
        title=job.title,
        description=job.description,
        requirements=job.requirements,
        is_active=job.is_active
    )
    
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    
    return db_job


@router.get("/jobs/", response_model=List[schemas.JobResponse])
async def get_jobs(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False, 
    db: Session = Depends(get_db)
):
    """Get all jobs"""
    query = db.query(models.Job)
    
    if active_only:
        query = query.filter(models.Job.is_active == True)
        
    jobs = query.offset(skip).limit(limit).all()
    return jobs


@router.get("/jobs/{job_id}", response_model=schemas.JobResponse)
async def get_job(
    job_id: int = Path(..., description="The ID of the job to get"),
    db: Session = Depends(get_db)
):
    """Get a specific job by ID"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job


# Interview scheduling endpoints
@router.post("/schedule-interview/", response_model=Dict[str, Any])
async def schedule_interview(
    interview_request: schemas.ScheduleInterviewRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Schedule an interview for a candidate"""
    # Find the candidate by email
    candidate = db.query(models.Candidate).filter(
        models.Candidate.email == interview_request.candidate_email
    ).first()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Find the job
    job = db.query(models.Job).filter(models.Job.id == interview_request.job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check if there's an existing job application
    job_application = db.query(models.JobApplication).filter(
        models.JobApplication.candidate_id == candidate.id,
        models.JobApplication.job_id == job.id
    ).first()
    
    if not job_application:
        # Create a new job application
        job_application = models.JobApplication(
            candidate_id=candidate.id,
            job_id=job.id,
            status=models.CandidateStatus.PENDING
        )
        db.add(job_application)
        db.commit()
        db.refresh(job_application)
    
    # Schedule the Zoom meeting
    meeting_details = await interview_manager.schedule_interview(
        candidate_name=candidate.name,
        candidate_email=candidate.email,
        job_title=job.title,
        job_description=job.description,
        scheduled_time=interview_request.scheduled_time,
        duration_minutes=interview_request.duration_minutes
    )
    
    if "error" in meeting_details:
        raise HTTPException(status_code=500, detail=meeting_details["error"])
    
    # Create interview record
    interview = models.Interview(
        candidate_id=candidate.id,
        job_application_id=job_application.id,
        scheduled_time=interview_request.scheduled_time,
        duration_minutes=interview_request.duration_minutes,
        zoom_meeting_id=meeting_details.get("meeting_id"),
        zoom_meeting_url=meeting_details.get("join_url"),
        zoom_meeting_password=meeting_details.get("password"),
        status="scheduled"
    )
    
    db.add(interview)
    db.commit()
    db.refresh(interview)
    
    # Update candidate status
    candidate.status = models.CandidateStatus.SCHEDULED
    job_application.status = models.CandidateStatus.SCHEDULED
    db.commit()
    
    # Generate interview questions in the background
    background_tasks.add_task(
        generate_and_store_questions,
        db_id=interview.id,
        job=job
    )
    
    return {
        "interview_id": interview.id,
        "meeting_details": meeting_details,
        "candidate": {
            "id": candidate.id,
            "name": candidate.name,
            "email": candidate.email
        },
        "job": {
            "id": job.id,
            "title": job.title
        },
        "scheduled_time": interview_request.scheduled_time.isoformat(),
        "duration_minutes": interview_request.duration_minutes
    }


async def generate_and_store_questions(db_id: int, job: models.Job):
    """Background task to generate and store interview questions"""
    try:
        # Get DB session for the background task
        db = next(get_db())
        
        # Generate questions using Gemini
        questions = await interview_manager.generate_interview_questions(
            job_description=job.description,
            job_requirements=job.requirements,
            num_questions=5  # Generate 5 questions by default
        )
        
        # Get the interview
        interview = db.query(models.Interview).filter(models.Interview.id == db_id).first()
        
        if not interview:
            logger.error(f"Interview {db_id} not found when storing questions")
            return
        
        # Store the questions
        for i, question_text in enumerate(questions):
            question = models.InterviewQuestion(
                interview_id=interview.id,
                question_text=question_text,
                order=i+1
            )
            db.add(question)
        
        db.commit()
        logger.info(f"Successfully generated and stored {len(questions)} questions for interview {db_id}")
        
    except Exception as e:
        logger.error(f"Error generating questions for interview {db_id}: {str(e)}")


@router.get("/interviews/", response_model=List[schemas.InterviewResponse])
async def get_interviews(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all interviews"""
    query = db.query(models.Interview)
    
    if status:
        query = query.filter(models.Interview.status == status)
        
    interviews = query.offset(skip).limit(limit).all()
    return interviews


@router.get("/interviews/{interview_id}", response_model=schemas.InterviewResponse)
async def get_interview(
    interview_id: int = Path(..., description="The ID of the interview to get"),
    db: Session = Depends(get_db)
):
    """Get a specific interview by ID"""
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    return interview


@router.get("/interviews/{interview_id}/questions", response_model=List[schemas.InterviewQuestionResponse])
async def get_interview_questions(
    interview_id: int = Path(..., description="The ID of the interview"),
    db: Session = Depends(get_db)
):
    """Get questions for a specific interview"""
    questions = db.query(models.InterviewQuestion).filter(
        models.InterviewQuestion.interview_id == interview_id
    ).order_by(models.InterviewQuestion.order).all()
    
    return questions


@router.post("/interviews/{interview_id}/process-recording", response_model=Dict[str, Any])
async def process_interview_recording(
    interview_id: int = Path(..., description="The ID of the interview"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """Process a completed interview recording"""
    # Get the interview
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    if not interview.zoom_meeting_id:
        raise HTTPException(status_code=400, detail="No Zoom meeting ID associated with this interview")
    
    # Process the recording in the background
    background_tasks.add_task(
        process_recording_background,
        interview_id=interview_id,
        meeting_id=interview.zoom_meeting_id
    )
    
    # Update interview status
    interview.status = "processing"
    db.commit()
    
    return {
        "message": "Processing recording in the background",
        "interview_id": interview_id,
        "meeting_id": interview.zoom_meeting_id
    }


async def process_recording_background(interview_id: int, meeting_id: str):
    """Background task to process recording"""
    try:
        # Get DB session for the background task
        db = next(get_db())
        
        # Process the recording
        processing_result = await interview_manager.process_interview_recording(meeting_id)
        
        # Get the interview
        interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
        
        if not interview:
            logger.error(f"Interview {interview_id} not found when processing recording")
            return
        
        # Update interview with recording URL
        if "video_path" in processing_result:
            interview.recording_url = processing_result["video_path"]
            interview.status = "interviewed"
            db.commit()
            
            # Also update the candidate status
            candidate = db.query(models.Candidate).filter(models.Candidate.id == interview.candidate_id).first()
            if candidate:
                candidate.status = models.CandidateStatus.INTERVIEWED
                db.commit()
                
            # And update the job application status
            job_app = db.query(models.JobApplication).filter(models.JobApplication.id == interview.job_application_id).first()
            if job_app:
                job_app.status = models.CandidateStatus.INTERVIEWED
                db.commit()
            
        else:
            logger.error(f"Failed to process recording for interview {interview_id}: {processing_result.get('error', 'Unknown error')}")
            
            # Mark as needing review since processing failed
            interview.status = "needs_review"
            db.commit()
            
        logger.info(f"Successfully processed recording for interview {interview_id}")
        
    except Exception as e:
        logger.error(f"Error processing recording for interview {interview_id}: {str(e)}")


@router.post("/interviews/{interview_id}/evaluate", response_model=schemas.InterviewResultResponse)
async def evaluate_interview(
    interview_id: int = Path(..., description="The ID of the interview to evaluate"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """Generate a final evaluation for an interview"""
    # Get the interview with its questions and candidate
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    # Check if the interview has been processed
    if interview.status not in ["interviewed", "processing", "needs_review"]:
        raise HTTPException(status_code=400, detail="Interview has not been conducted or processed yet")
    
    # Get the questions and responses
    questions = db.query(models.InterviewQuestion).filter(
        models.InterviewQuestion.interview_id == interview_id
    ).order_by(models.InterviewQuestion.order).all()
    
    # Get the candidate and job
    candidate = db.query(models.Candidate).filter(models.Candidate.id == interview.candidate_id).first()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    job_app = db.query(models.JobApplication).filter(models.JobApplication.id == interview.job_application_id).first()
    
    if not job_app:
        raise HTTPException(status_code=404, detail="Job application not found")
    
    job = db.query(models.Job).filter(models.Job.id == job_app.job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Start evaluation in the background
    background_tasks.add_task(
        evaluate_interview_background,
        interview_id=interview_id,
        candidate_name=candidate.name,
        candidate_email=candidate.email,
        job_title=job.title,
        job_description=job.description,
        job_requirements=job.requirements
    )
    
    # Return a response immediately
    return {
        "interview_id": interview_id,
        "candidate_name": candidate.name,
        "job_title": job.title,
        "overall_score": 0,  # Placeholder
        "recommendation": "In Progress",
        "detailed_evaluation": {
            "message": "Evaluation in progress. Check back later for results."
        }
    }


async def evaluate_interview_background(
    interview_id: int,
    candidate_name: str,
    candidate_email: str,
    job_title: str,
    job_description: str,
    job_requirements: str
):
    """Background task to evaluate an interview"""
    try:
        # Get DB session for the background task
        db = next(get_db())
        
        # Get the interview
        interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
        
        if not interview:
            logger.error(f"Interview {interview_id} not found when evaluating")
            return
        
        # Get all questions and responses
        questions = db.query(models.InterviewQuestion).filter(
            models.InterviewQuestion.interview_id == interview_id
        ).order_by(models.InterviewQuestion.order).all()
        
        # Prepare question responses for evaluation
        question_responses = []
        for q in questions:
            # Skip questions without responses
            if not q.response:
                continue
                
            # Evaluate the response if not already evaluated
            if not q.response_evaluation:
                evaluation = await interview_manager.evaluate_candidate_response(
                    question=q.question_text,
                    response=q.response,
                    job_requirements=job_requirements
                )
                
                # Store the evaluation
                q.response_evaluation = str(evaluation)
                db.commit()
            else:
                # Parse the stored evaluation
                import ast
                try:
                    evaluation = ast.literal_eval(q.response_evaluation)
                except:
                    evaluation = {"error": "Could not parse stored evaluation"}
            
            # Add to responses list
            question_responses.append({
                "question": q.question_text,
                "response": q.response,
                "evaluation": evaluation
            })
        
        # Get recording analysis if available
        recording_analysis = None
        if interview.recording_url:
            recording_analysis = {
                "video_path": interview.recording_url
            }
        
        # Generate final evaluation
        final_evaluation = await interview_manager.generate_final_evaluation(
            candidate_name=candidate_name,
            job_title=job_title,
            job_description=job_description,
            question_responses=question_responses,
            recording_analysis=recording_analysis
        )
        
        # Save the evaluation to the database
        db_eval = models.InterviewEvaluation(
            interview_id=interview_id,
            technical_score=final_evaluation.get("overall_score", 0) / 10,  # Convert to 0-10 scale
            behavioral_score=final_evaluation.get("behavioral_score", 0) if "behavioral_score" in final_evaluation else None,
            communication_score=final_evaluation.get("communication_score", 0) if "communication_score" in final_evaluation else None,
            overall_score=final_evaluation.get("overall_score", 0) / 10,  # Convert to 0-10 scale
            recommendation=final_evaluation.get("recommendation", "Needs Review"),
            feedback=str(final_evaluation)
        )
        
        db.add(db_eval)
        db.commit()
        
        # Save the report to a file
        report_path = interview_manager.save_evaluation_report(
            candidate_name=candidate_name,
            job_title=job_title,
            final_evaluation=final_evaluation
        )
        
        # Update candidate and job application status based on recommendation
        candidate = db.query(models.Candidate).filter(models.Candidate.id == interview.candidate_id).first()
        job_app = db.query(models.JobApplication).filter(models.JobApplication.id == interview.job_application_id).first()
        
        recommendation = final_evaluation.get("recommendation", "Needs Review")
        
        if recommendation == "Selected":
            new_status = models.CandidateStatus.SELECTED
        elif recommendation == "Needs Review":
            new_status = models.CandidateStatus.NEEDS_REVIEW
        else:
            new_status = models.CandidateStatus.REJECTED
        
        if candidate:
            candidate.status = new_status
            db.commit()
            
        if job_app:
            job_app.status = new_status
            db.commit()
        
        # Send evaluation results to candidate
        await interview_manager.send_evaluation_results(
            candidate_email=candidate_email,
            candidate_name=candidate_name,
            job_title=job_title,
            final_evaluation=final_evaluation
        )
        
        logger.info(f"Successfully evaluated interview {interview_id} with recommendation: {recommendation}")
        
    except Exception as e:
        logger.error(f"Error evaluating interview {interview_id}: {str(e)}")


@router.get("/interviews/{interview_id}/evaluation", response_model=schemas.InterviewEvaluationResponse)
async def get_interview_evaluation(
    interview_id: int = Path(..., description="The ID of the interview"),
    db: Session = Depends(get_db)
):
    """Get the evaluation for a specific interview"""
    evaluation = db.query(models.InterviewEvaluation).filter(
        models.InterviewEvaluation.interview_id == interview_id
    ).first()
    
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    
    return evaluation


# Zoom webhook endpoints
@router.post("/zoom/webhook")
async def zoom_webhook(payload: Dict[str, Any]):
    """Handle Zoom webhooks for meeting events"""
    try:
        event = payload.get("event")
        
        if not event:
            return {"status": "error", "message": "No event in payload"}
        
        event_type = event.get("type")
        meeting_id = event.get("meeting", {}).get("id")
        
        if not meeting_id:
            return {"status": "error", "message": "No meeting ID in payload"}
        
        # Handle different event types
        if event_type == "meeting.ended":
            # When a meeting ends, process the recording
            # Get DB session
            db = next(get_db())
            
            # Find the interview with this meeting ID
            interview = db.query(models.Interview).filter(
                models.Interview.zoom_meeting_id == str(meeting_id)
            ).first()
            
            if interview:
                # Update status
                interview.status = "completed"
                db.commit()
                
                # Process recording in the background
                import asyncio
                asyncio.create_task(process_recording_background(
                    interview_id=interview.id,
                    meeting_id=str(meeting_id)
                ))
                
                return {"status": "success", "message": f"Processing recording for meeting {meeting_id}"}
            else:
                return {"status": "error", "message": f"No interview found for meeting {meeting_id}"}
        
        return {"status": "success", "message": f"Received event {event_type} for meeting {meeting_id}"}
        
    except Exception as e:
        logger.error(f"Error handling Zoom webhook: {str(e)}")
        return {"status": "error", "message": str(e)}


# Question generation endpoint
@router.post("/generate-questions/", response_model=schemas.GenerateQuestionsResponse)
async def generate_questions(
    request: schemas.GenerateQuestionsRequest,
    db: Session = Depends(get_db)
):
    """Generate interview questions based on a job"""
    # Get the job
    job = db.query(models.Job).filter(models.Job.id == request.job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Generate questions
    questions = await interview_manager.generate_interview_questions(
        job_description=job.description,
        job_requirements=job.requirements,
        num_questions=request.num_questions
    )
    
    return {"questions": questions}