import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import json

from app.core.config import settings
from app.services.zoom_service import zoom_service
from app.services.email_service import email_service
from app.services.gemini_service import gemini_service
from app.utils.analysis_utils import interview_analyzer

logger = logging.getLogger(__name__)


class InterviewManager:
    """Utility class for managing the interview process"""
    
    def __init__(self):
        pass
    
    async def schedule_interview(self, candidate_name: str, candidate_email: str, job_title: str, 
                               job_description: str, scheduled_time: datetime, 
                               duration_minutes: int = 30) -> Dict[str, Any]:
        """Schedule a Zoom interview and send invitation to candidate
        
        Args:
            candidate_name: Name of the candidate
            candidate_email: Email of the candidate
            job_title: Title of the job
            job_description: Description of the job
            scheduled_time: When the interview is scheduled
            duration_minutes: Duration of the interview in minutes
            
        Returns:
            Dict with meeting details
        """
        try:
            # Create a descriptive meeting topic
            topic = f"Interview: {candidate_name} for {job_title} position"
            
            # Create a meeting description/agenda
            agenda = f"AI-conducted interview for the {job_title} position. The interview will last approximately {duration_minutes} minutes."
            
            # Schedule the Zoom meeting
            meeting_details = await zoom_service.create_meeting(
                topic=topic,
                start_time=scheduled_time,
                duration_minutes=duration_minutes,
                agenda=agenda
            )
            
            if not meeting_details or "meeting_id" not in meeting_details:
                logger.error("Failed to create Zoom meeting")
                return {"error": "Failed to create Zoom meeting"}
            
            # Send email invitation to candidate
            meeting_time_str = scheduled_time.strftime("%A, %B %d, %Y at %I:%M %p")
            email_sent = email_service.send_interview_invitation(
                recipient=candidate_email,
                candidate_name=candidate_name,
                job_title=job_title,
                meeting_url=meeting_details["join_url"],
                meeting_time=meeting_time_str,
                meeting_password=meeting_details.get("password")
            )
            
            if not email_sent:
                logger.warning(f"Failed to send email invitation to {candidate_email}")
                meeting_details["email_sent"] = False
            else:
                meeting_details["email_sent"] = True
            
            return meeting_details
            
        except Exception as e:
            logger.error(f"Error scheduling interview: {str(e)}")
            return {"error": f"Error scheduling interview: {str(e)}"}
    
    async def generate_interview_questions(self, job_description: str, 
                                         job_requirements: str,
                                         num_questions: int = 5) -> List[str]:
        """Generate interview questions based on job description
        
        Args:
            job_description: Full job description
            job_requirements: Job requirements
            num_questions: Number of questions to generate
            
        Returns:
            List of interview questions
        """
        return await gemini_service.generate_interview_questions(
            job_description=job_description,
            job_requirements=job_requirements,
            num_questions=num_questions
        )
    
    async def evaluate_candidate_response(self, question: str, response: str, 
                                        job_requirements: str) -> Dict[str, Any]:
        """Evaluate a candidate's response to an interview question
        
        Args:
            question: The interview question
            response: The candidate's response
            job_requirements: Job requirements for context
            
        Returns:
            Dict with evaluation details
        """
        # Get the response evaluation from Gemini
        evaluation = await gemini_service.evaluate_response(
            question=question,
            response=response,
            job_requirements=job_requirements
        )
        
        # Check if the response might be plagiarized
        plagiarism_check = await interview_analyzer.detect_plagiarism(response)
        
        # Add plagiarism detection results to the evaluation
        if "feedback" not in evaluation:
            evaluation["feedback"] = {}
        
        evaluation["feedback"]["plagiarism_detected"] = plagiarism_check["is_plagiarism_detected"]
        evaluation["feedback"]["plagiarism_confidence"] = plagiarism_check["confidence_score"]
        evaluation["feedback"]["plagiarism_explanation"] = plagiarism_check["explanation"]
        
        return evaluation
    
    async def process_interview_recording(self, meeting_id: str) -> Dict[str, Any]:
        """Process a completed interview recording
        
        Args:
            meeting_id: Zoom meeting ID
            
        Returns:
            Dict with processing results
        """
        try:
            # Get recording download URL from Zoom
            recording_url = await zoom_service.get_recording_download_url(meeting_id)
            
            if not recording_url:
                logger.error(f"No recording found for meeting {meeting_id}")
                return {"error": "No recording found"}
            
            # Download the recording
            video_path = await interview_analyzer.download_zoom_recording(recording_url, meeting_id)
            
            if not video_path:
                logger.error(f"Failed to download recording for meeting {meeting_id}")
                return {"error": "Failed to download recording"}
            
            # Analyze the interview recording
            analysis_results = await interview_analyzer.analyze_interview_recording(video_path)
            
            return {
                "meeting_id": meeting_id,
                "video_path": video_path,
                "analysis_results": analysis_results
            }
            
        except Exception as e:
            logger.error(f"Error processing recording: {str(e)}")
            return {"error": f"Error processing recording: {str(e)}"}
    
    async def generate_final_evaluation(self, candidate_name: str, job_title: str,
                                      job_description: str, question_responses: List[Dict[str, Any]],
                                      recording_analysis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate a final evaluation report for a candidate
        
        Args:
            candidate_name: Name of the candidate
            job_title: Title of the job
            job_description: Full job description
            question_responses: List of dicts with questions, responses and evaluations
            recording_analysis: Optional recording analysis results
            
        Returns:
            Dict with final evaluation
        """
        # Extract audio and video analysis if available
        audio_analysis = None
        video_analysis = None
        
        if recording_analysis and "analysis_results" in recording_analysis:
            results = recording_analysis["analysis_results"]
            if "audio_analysis" in results:
                audio_analysis = results["audio_analysis"]
            if "video_analysis" in results:
                video_analysis = results["video_analysis"]
        
        # Generate final evaluation
        final_evaluation = await gemini_service.generate_final_evaluation(
            candidate_name=candidate_name,
            job_title=job_title,
            job_description=job_description,
            question_responses=question_responses,
            audio_analysis=audio_analysis,
            video_analysis=video_analysis
        )
        
        # Add metadata
        final_evaluation["candidate_name"] = candidate_name
        final_evaluation["job_title"] = job_title
        final_evaluation["evaluation_date"] = datetime.utcnow().isoformat()
        
        return final_evaluation
    
    async def send_evaluation_results(self, candidate_email: str, candidate_name: str,
                                    job_title: str, final_evaluation: Dict[str, Any]) -> bool:
        """Send evaluation results to the candidate
        
        Args:
            candidate_email: Email of the candidate
            candidate_name: Name of the candidate
            job_title: Title of the job
            final_evaluation: The final evaluation report
            
        Returns:
            Boolean indicating success
        """
        recommendation = final_evaluation.get("recommendation", "Needs Review")
        
        # Create feedback from the assessment
        feedback = final_evaluation.get("assessment", "")
        
        # Add strengths and areas for improvement
        strengths = final_evaluation.get("key_strengths", "")
        areas_for_improvement = final_evaluation.get("areas_for_improvement", "")
        
        if strengths:
            feedback += f"\n\nKey Strengths:\n{strengths}"
        
        if areas_for_improvement and recommendation != "Rejected":
            # Only include areas for improvement for non-rejected candidates
            feedback += f"\n\nAreas for Improvement:\n{areas_for_improvement}"
        
        # Send the email
        return email_service.send_interview_results(
            recipient=candidate_email,
            candidate_name=candidate_name,
            job_title=job_title,
            recommendation=recommendation,
            feedback=feedback
        )
    
    def save_evaluation_report(self, candidate_name: str, job_title: str,
                             final_evaluation: Dict[str, Any]) -> str:
        """Save the evaluation report to a file
        
        Args:
            candidate_name: Name of the candidate
            job_title: Title of the job
            final_evaluation: The final evaluation report
            
        Returns:
            Path to the saved report
        """
        try:
            # Create a filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            candidate_name_clean = candidate_name.replace(' ', '_').lower()
            job_title_clean = job_title.replace(' ', '_').lower()
            
            filename = f"evaluation_{candidate_name_clean}_{job_title_clean}_{timestamp}.json"
            filepath = os.path.join(settings.REPORTS_PATH, filename)
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Save the evaluation as JSON
            with open(filepath, 'w') as f:
                json.dump(final_evaluation, f, indent=2)
            
            logger.info(f"Saved evaluation report to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error saving evaluation report: {str(e)}")
            return ""


# Create a singleton instance
interview_manager = InterviewManager()