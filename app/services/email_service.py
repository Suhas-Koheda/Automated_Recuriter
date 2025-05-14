import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service to handle email sending and templates"""
    
    def __init__(self):
        self.sender_email = settings.EMAIL_SENDER
        self.sender_password = settings.EMAIL_PASSWORD
        self.host = settings.EMAIL_HOST
        self.port = settings.EMAIL_PORT
    
    def send_email(self, recipient: str, subject: str, body: str, is_html: bool = True) -> bool:
        """Send an email to a recipient"""
        try:
            message = MIMEMultipart()
            message["From"] = self.sender_email
            message["To"] = recipient
            message["Subject"] = subject
            
            if is_html:
                message.attach(MIMEText(body, "html"))
            else:
                message.attach(MIMEText(body, "plain"))
            
            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            
            logger.info(f"Email sent successfully to {recipient}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False
    
    def send_interview_invitation(self, recipient: str, candidate_name: str, 
                                  job_title: str, meeting_url: str, 
                                  meeting_time: str, meeting_password: str = None) -> bool:
        """Send interview invitation with Zoom details"""
        subject = f"Interview Invitation: {job_title} Position"
        
        # HTML template for the email body
        body = f"""
        <html>
        <body>
            <h2>Interview Invitation</h2>
            <p>Dear {candidate_name},</p>
            
            <p>We are pleased to invite you for an interview for the <strong>{job_title}</strong> position.</p>
            
            <p>Your interview has been scheduled for <strong>{meeting_time}</strong>.</p>
            
            <h3>Zoom Meeting Details:</h3>
            <p>Meeting URL: <a href="{meeting_url}">{meeting_url}</a></p>
        """
        
        if meeting_password:
            body += f"<p>Meeting Password: <strong>{meeting_password}</strong></p>"
        
        body += """
            <p>Please note that this interview will be conducted by our AI assistant. 
            The assistant will ask you questions related to the position, and your responses will be recorded for evaluation.</p>
            
            <p>If you have any questions or need to reschedule, please reply to this email.</p>
            
            <p>Best regards,<br>
            Recruitment Team</p>
        </body>
        </html>
        """
        
        return self.send_email(recipient, subject, body, is_html=True)
    
    def send_interview_results(self, recipient: str, candidate_name: str, 
                               job_title: str, recommendation: str, 
                               feedback: str) -> bool:
        """Send interview results to candidate"""
        subject = f"Interview Results: {job_title} Position"
        
        # Determine the intro message based on recommendation
        if recommendation == "Selected":
            intro = "We are pleased to inform you that you have been selected for the next stage in our hiring process."
        elif recommendation == "Needs Review":
            intro = "Thank you for participating in our interview process. Your application is currently under review by our team."
        else:  # Rejected
            intro = "Thank you for participating in our interview process. After careful consideration, we have decided to pursue other candidates who more closely match our current requirements."
        
        # HTML template for the email body
        body = f"""
        <html>
        <body>
            <h2>Interview Results</h2>
            <p>Dear {candidate_name},</p>
            
            <p>{intro}</p>
            
            <p><strong>Position:</strong> {job_title}</p>
            
            <h3>Feedback from your interview:</h3>
            <p>{feedback}</p>
            
            <p>Best regards,<br>
            Recruitment Team</p>
        </body>
        </html>
        """
        
        return self.send_email(recipient, subject, body, is_html=True)
    
    def send_bulk_emails(self, recipients: List[dict]) -> dict:
        """Send bulk emails with different content to multiple recipients
        
        Args:
            recipients: List of dicts containing recipient, subject, body
            
        Returns:
            Dict with success and failure counts
        """
        results = {"success": 0, "failed": 0, "failed_emails": []}
        
        for recipient_data in recipients:
            recipient = recipient_data.get("email")
            subject = recipient_data.get("subject")
            body = recipient_data.get("body")
            is_html = recipient_data.get("is_html", True)
            
            success = self.send_email(recipient, subject, body, is_html)
            
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1
                results["failed_emails"].append(recipient)
        
        return results


# Create a singleton instance
email_service = EmailService()