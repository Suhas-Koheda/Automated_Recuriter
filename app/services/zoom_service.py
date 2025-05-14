import httpx
import jwt
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class ZoomService:
    """Service to handle Zoom API integration for meeting scheduling and recordings"""
    
    def __init__(self):
        self.account_id = settings.ZOOM_ACCOUNT_ID
        self.client_id = settings.ZOOM_CLIENT_ID
        self.client_secret = settings.ZOOM_CLIENT_SECRET
        self.base_url = "https://api.zoom.us/v2"
        self.token = None
        self.token_expiry = None
    
    async def _get_access_token(self) -> str:
        """Generate or refresh the Zoom OAuth token"""
        # Check if token exists and is still valid
        current_time = time.time()
        if self.token and self.token_expiry and current_time < self.token_expiry:
            return self.token
        
        # Token doesn't exist or is expired, so generate a new one
        try:
            auth_url = "https://zoom.us/oauth/token"
            auth_headers = {
                "Authorization": f"Basic {self._generate_basic_auth()}"
            }
            auth_data = {
                "grant_type": "account_credentials",
                "account_id": self.account_id
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    auth_url,
                    headers=auth_headers,
                    data=auth_data
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    self.token = token_data.get("access_token")
                    # Set token expiry (subtract 5 minutes for safety margin)
                    expires_in = token_data.get("expires_in", 3600)
                    self.token_expiry = current_time + expires_in - 300
                    return self.token
                else:
                    logger.error(f"Failed to get Zoom token: {response.text}")
                    raise Exception(f"Failed to authenticate with Zoom: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Error getting Zoom access token: {str(e)}")
            raise
    
    def _generate_basic_auth(self) -> str:
        """Generate Basic auth string for Zoom OAuth"""
        import base64
        auth_str = f"{self.client_id}:{self.client_secret}"
        return base64.b64encode(auth_str.encode()).decode()
    
    async def create_meeting(self, topic: str, start_time: datetime, 
                             duration_minutes: int = 30, 
                             agenda: str = "", 
                             settings: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a new Zoom meeting
        
        Args:
            topic: Meeting topic/title
            start_time: Start time of the meeting
            duration_minutes: Duration of meeting in minutes
            agenda: Meeting description
            settings: Additional meeting settings
            
        Returns:
            Dict with meeting details including id, join_url, etc.
        """
        token = await self._get_access_token()
        
        # Format start time according to Zoom API requirements
        formatted_time = start_time.strftime("%Y-%m-%dT%H:%M:%S")
        
        # Default settings for AI interviews
        default_settings = {
            "host_video": True,
            "participant_video": True,
            "join_before_host": True,
            "mute_upon_entry": False,
            "auto_recording": "cloud",  # Record to Zoom cloud
            "waiting_room": False,
        }
        
        # Merge with custom settings if provided
        if settings:
            default_settings.update(settings)
        
        meeting_data = {
            "topic": topic,
            "type": 2,  # Scheduled meeting
            "start_time": formatted_time,
            "duration": duration_minutes,
            "timezone": "UTC",
            "agenda": agenda,
            "settings": default_settings
        }
        
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
                
                response = await client.post(
                    f"{self.base_url}/users/me/meetings",
                    headers=headers,
                    json=meeting_data
                )
                
                if response.status_code in (200, 201):
                    meeting_details = response.json()
                    logger.info(f"Successfully created Zoom meeting with ID: {meeting_details.get('id')}")
                    return {
                        "meeting_id": str(meeting_details.get("id")),
                        "join_url": meeting_details.get("join_url"),
                        "password": meeting_details.get("password"),
                        "start_url": meeting_details.get("start_url")
                    }
                else:
                    logger.error(f"Failed to create Zoom meeting: {response.text}")
                    raise Exception(f"Failed to create meeting: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Error creating Zoom meeting: {str(e)}")
            raise
    
    async def get_meeting(self, meeting_id: str) -> Dict[str, Any]:
        """Get details of an existing meeting"""
        token = await self._get_access_token()
        
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {token}"
                }
                
                response = await client.get(
                    f"{self.base_url}/meetings/{meeting_id}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Failed to get meeting {meeting_id}: {response.text}")
                    raise Exception(f"Failed to get meeting: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Error getting Zoom meeting: {str(e)}")
            raise
    
    async def delete_meeting(self, meeting_id: str) -> bool:
        """Delete/cancel a scheduled meeting"""
        token = await self._get_access_token()
        
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {token}"
                }
                
                response = await client.delete(
                    f"{self.base_url}/meetings/{meeting_id}",
                    headers=headers
                )
                
                if response.status_code in (200, 204):
                    logger.info(f"Successfully deleted meeting {meeting_id}")
                    return True
                else:
                    logger.error(f"Failed to delete meeting {meeting_id}: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error deleting Zoom meeting: {str(e)}")
            return False
    
    async def get_recordings(self, meeting_id: str) -> Dict[str, Any]:
        """Get recordings for a meeting"""
        token = await self._get_access_token()
        
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {token}"
                }
                
                response = await client.get(
                    f"{self.base_url}/meetings/{meeting_id}/recordings",
                    headers=headers
                )
                
                if response.status_code == 200:
                    recordings_data = response.json()
                    logger.info(f"Successfully retrieved recordings for meeting {meeting_id}")
                    return recordings_data
                else:
                    logger.error(f"Failed to get recordings for meeting {meeting_id}: {response.text}")
                    raise Exception(f"Failed to get recordings: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Error getting Zoom recordings: {str(e)}")
            raise
    
    async def get_recording_download_url(self, meeting_id: str) -> Optional[str]:
        """Get the download URL for the recording of a meeting"""
        try:
            recordings_data = await self.get_recordings(meeting_id)
            recording_files = recordings_data.get("recording_files", [])
            
            # Look for an MP4 recording
            for recording in recording_files:
                if recording.get("file_type") == "MP4":
                    return recording.get("download_url")
            
            logger.warning(f"No MP4 recording found for meeting {meeting_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting recording URL: {str(e)}")
            return None
    
    async def create_ai_bot_user(self, email: str, first_name: str = "AI", last_name: str = "Interviewer") -> Dict[str, Any]:
        """Create a Zoom user that will act as the AI interviewer
        
        Note: This requires Zoom account with appropriate admin privileges
        """
        token = await self._get_access_token()
        
        user_data = {
            "action": "create",
            "user_info": {
                "email": email,
                "type": 1,  # Basic user
                "first_name": first_name,
                "last_name": last_name
            }
        }
        
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
                
                response = await client.post(
                    f"{self.base_url}/users",
                    headers=headers,
                    json=user_data
                )
                
                if response.status_code == 201:
                    user_details = response.json()
                    logger.info(f"Successfully created Zoom user: {email}")
                    return user_details
                else:
                    logger.error(f"Failed to create Zoom user: {response.text}")
                    raise Exception(f"Failed to create user: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Error creating Zoom user: {str(e)}")
            raise


# Create a singleton instance
zoom_service = ZoomService()