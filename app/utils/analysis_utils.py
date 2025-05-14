import os
import cv2
import numpy as np
import logging
from typing import List, Dict, Any, Optional, Tuple
import tempfile
import httpx
from pathlib import Path

from app.core.config import settings
from app.services.gemini_service import gemini_service

logger = logging.getLogger(__name__)


class InterviewAnalyzer:
    """Utility class for analyzing interview recordings and responses"""
    
    def __init__(self):
        self.recording_path = settings.RECORDING_PATH
        self.reports_path = settings.REPORTS_PATH
        
    async def analyze_interview_recording(self, video_path: str) -> Dict[str, Any]:
        """Analyze a video recording of an interview
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Dict with analysis results including video and audio analysis
        """
        results = {}
        
        # Check if file exists
        if not os.path.exists(video_path):
            logger.error(f"Recording file not found: {video_path}")
            return {"error": "Recording file not found"}
        
        # Extract audio from video for separate analysis
        audio_path = self._extract_audio(video_path)
        
        # Analyze video (facial expressions, body language)
        video_analysis = await gemini_service.analyze_video(video_path)
        results["video_analysis"] = video_analysis
        
        # Analyze audio (tone, speaking rate, etc.)
        if audio_path:
            audio_analysis = await gemini_service.analyze_audio(audio_path)
            results["audio_analysis"] = audio_analysis
            
            # Clean up temporary audio file
            try:
                os.remove(audio_path)
            except Exception as e:
                logger.warning(f"Failed to remove temporary audio file: {str(e)}")
        
        return results
    
    def _extract_audio(self, video_path: str) -> Optional[str]:
        """Extract audio from video file using ffmpeg"""
        try:
            import subprocess
            
            # Create a temporary file for the audio
            fd, temp_audio_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            
            # Use ffmpeg to extract audio
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-q:a", "0",
                "-map", "a",
                temp_audio_path
            ]
            
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            return temp_audio_path
            
        except Exception as e:
            logger.error(f"Failed to extract audio from video: {str(e)}")
            return None
    
    async def download_zoom_recording(self, download_url: str, meeting_id: str) -> Optional[str]:
        """Download a Zoom recording to the local system
        
        Args:
            download_url: The Zoom recording download URL
            meeting_id: The Zoom meeting ID for filename
            
        Returns:
            Path to the downloaded file or None if failed
        """
        try:
            # Create filename with meeting ID
            filename = f"zoom_recording_{meeting_id}.mp4"
            filepath = os.path.join(self.recording_path, filename)
            
            # Download the file
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", download_url) as response:
                    if response.status_code != 200:
                        logger.error(f"Failed to download recording: HTTP {response.status_code}")
                        return None
                    
                    # Create the directory if it doesn't exist
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    
                    # Write the file
                    with open(filepath, "wb") as f:
                        async for chunk in response.aiter_bytes():
                            f.write(chunk)
            
            logger.info(f"Successfully downloaded recording to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error downloading Zoom recording: {str(e)}")
            return None
    
    async def transcribe_audio(self, audio_path: str) -> str:
        """Transcribe interview audio to text
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Transcribed text
        """
        try:
            # Load audio file
            import speech_recognition as sr
            
            recognizer = sr.Recognizer()
            with sr.AudioFile(audio_path) as source:
                audio_data = recognizer.record(source)
                
                # Recognize speech using Google Speech Recognition
                text = recognizer.recognize_google(audio_data)
                return text
                
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            return ""
    
    async def detect_plagiarism(self, response: str) -> Dict[str, Any]:
        """Check if a response is plagiarized or AI-generated
        
        Args:
            response: The candidate's response text
            
        Returns:
            Dict with plagiarism detection results
        """
        try:
            is_plagiarism, confidence, explanation = await gemini_service.check_plagiarism(response)
            
            return {
                "is_plagiarism_detected": is_plagiarism,
                "confidence_score": confidence,
                "explanation": explanation
            }
            
        except Exception as e:
            logger.error(f"Error checking plagiarism: {str(e)}")
            return {
                "is_plagiarism_detected": False,
                "confidence_score": 0.0,
                "explanation": f"Error checking plagiarism: {str(e)}"
            }


# Create a singleton instance
interview_analyzer = InterviewAnalyzer()