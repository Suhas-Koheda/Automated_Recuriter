import google.generativeai as genai
import logging
import base64
import os
from typing import List, Dict, Any, Optional, Tuple
import json

from app.core.config import settings

logger = logging.getLogger(__name__)


class GeminiService:
    """Service to handle Google Gemini AI integration for interviews"""
    
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        # Configure the API key
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')  # Using most capable model
        self.vision_model = genai.GenerativeModel('gemini-pro-vision')  # For multimodal analysis
    
    async def generate_interview_questions(self, job_description: str, 
                                         job_requirements: str, 
                                         num_questions: int = 5) -> List[str]:
        """Generate interview questions based on job description and requirements
        
        Args:
            job_description: The full job description
            job_requirements: The job requirements
            num_questions: Number of questions to generate
            
        Returns:
            List of interview questions
        """
        prompt = f"""
        As an AI interviewer, generate {num_questions} interview questions for a candidate
        applying for the following position:
        
        Job Description:
        {job_description}
        
        Job Requirements:
        {job_requirements}
        
        Please create a mix of technical questions specific to the role,
        problem-solving questions, and behavioral questions.
        Return only the questions in a numbered list format.
        """
        
        try:
            response = await self.model.generate_content_async(prompt)
            
            if hasattr(response, 'text'):
                # Process the response to extract just the questions
                questions_text = response.text
                
                # Split by newlines and filter out any empty lines
                questions = [q.strip() for q in questions_text.split('\n') if q.strip()]
                
                # Remove numbering if present (e.g., "1. " or "1) ")
                questions = [q[q.find(' ')+1:] if q[0].isdigit() else q for q in questions]
                
                # Limit to requested number
                return questions[:num_questions]
            else:
                logger.error("Gemini API didn't return a valid text response")
                return self._get_fallback_questions(job_description)
                
        except Exception as e:
            logger.error(f"Error generating interview questions: {str(e)}")
            return self._get_fallback_questions(job_description)
    
    def _get_fallback_questions(self, job_description: str) -> List[str]:
        """Return fallback questions if API fails"""
        return [
            "Can you tell me about your relevant experience for this position?",
            "What are your key strengths that make you suitable for this role?",
            "How do you handle challenges in your work?",
            "Describe a project you worked on that you're proud of.",
            "Why are you interested in this position?"
        ]
    
    async def evaluate_response(self, question: str, 
                              response: str, 
                              job_requirements: str) -> Dict[str, Any]:
        """Evaluate a candidate's text response to an interview question
        
        Args:
            question: The interview question
            response: Candidate's response
            job_requirements: The job requirements to judge against
            
        Returns:
            Dict with evaluation scores and feedback
        """
        prompt = f"""
        Evaluate the following candidate response to an interview question.
        
        Question: {question}
        
        Response: {response}
        
        Job Requirements: {job_requirements}
        
        Please evaluate the response on the following criteria, on a scale of 1-10:
        1. Relevance: How relevant was the answer to the question asked?
        2. Clarity: How clear and well-articulated was the response?
        3. Technical accuracy: How technically accurate was the response? (If applicable)
        4. Experience level: What level of experience does the response demonstrate?
        5. Overall quality: Overall assessment of the response quality
        
        Also provide:
        - Strengths: Key strengths identified in the response
        - Weaknesses: Areas where the response could be improved
        - Feedback: Specific constructive feedback
        - Plagiarism indicators: Any indicators that the response might be plagiarized or AI-generated
        
        Return the evaluation as a structured JSON object with numeric scores and text feedback.
        """
        
        try:
            response_obj = await self.model.generate_content_async(prompt)
            
            if hasattr(response_obj, 'text'):
                # Try to parse the response as JSON
                try:
                    # Extract JSON if embedded in markdown code block
                    text = response_obj.text
                    if "```json" in text and "```" in text.split("```json", 1)[1]:
                        json_str = text.split("```json", 1)[1].split("```", 1)[0].strip()
                    elif "```" in text and "```" in text.split("```", 1)[1]:
                        json_str = text.split("```", 1)[1].split("```", 1)[0].strip()
                    else:
                        json_str = text
                        
                    evaluation = json.loads(json_str)
                    return evaluation
                except json.JSONDecodeError:
                    # If JSON parsing fails, create a structured response manually
                    lines = response_obj.text.split('\n')
                    evaluation = {
                        "scores": {
                            "relevance": self._extract_score(lines, "Relevance"),
                            "clarity": self._extract_score(lines, "Clarity"),
                            "technical_accuracy": self._extract_score(lines, "Technical accuracy"),
                            "experience_level": self._extract_score(lines, "Experience level"),
                            "overall_quality": self._extract_score(lines, "Overall quality")
                        },
                        "feedback": {
                            "strengths": self._extract_section(lines, "Strengths"),
                            "weaknesses": self._extract_section(lines, "Weaknesses"),
                            "feedback": self._extract_section(lines, "Feedback"),
                            "plagiarism_indicators": self._extract_section(lines, "Plagiarism indicators")
                        }
                    }
                    return evaluation
            else:
                logger.error("Gemini API didn't return a valid text response for evaluation")
                return self._get_fallback_evaluation()
                
        except Exception as e:
            logger.error(f"Error evaluating response: {str(e)}")
            return self._get_fallback_evaluation()
    
    def _extract_score(self, lines: List[str], criteria: str) -> int:
        """Extract numeric score from text response"""
        for line in lines:
            if criteria.lower() in line.lower():
                # Look for numbers in the line
                import re
                numbers = re.findall(r'\d+', line)
                if numbers:
                    score = int(numbers[0])
                    return min(10, max(1, score))  # Ensure between 1-10
        return 5  # Default middle score if not found
    
    def _extract_section(self, lines: List[str], section_name: str) -> str:
        """Extract a text section from the response"""
        section_text = ""
        in_section = False
        
        for i, line in enumerate(lines):
            if section_name.lower() in line.lower() and ":" in line:
                in_section = True
                # Extract text after the colon
                section_text = line.split(":", 1)[1].strip()
                continue
                
            if in_section:
                # Check if we've reached the next section
                if i+1 < len(lines) and ":" in lines[i+1] and any(s.lower() in lines[i+1].lower() for s in 
                                                                 ["relevance", "clarity", "technical", "experience", 
                                                                  "overall", "strengths", "weaknesses", "feedback", "plagiarism"]):
                    break
                
                if line.strip():  # If not empty line
                    section_text += " " + line.strip()
                    
        return section_text.strip()
    
    def _get_fallback_evaluation(self) -> Dict[str, Any]:
        """Return fallback evaluation if API fails"""
        return {
            "scores": {
                "relevance": 5,
                "clarity": 5, 
                "technical_accuracy": 5,
                "experience_level": 5,
                "overall_quality": 5
            },
            "feedback": {
                "strengths": "Unable to analyze response. Please review manually.",
                "weaknesses": "Unable to analyze response. Please review manually.",
                "feedback": "System was unable to generate automated feedback for this response.",
                "plagiarism_indicators": "Unable to detect plagiarism automatically."
            }
        }
    
    async def analyze_video(self, video_path: str) -> Dict[str, Any]:
        """Analyze a video recording of an interview
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Dict with analysis results
        """
        try:
            # Extract a few frames from the video
            frames = self._extract_frames_from_video(video_path)
            
            if not frames:
                logger.error(f"Failed to extract frames from video: {video_path}")
                return {"error": "Failed to extract frames from video"}
            
            # Create prompt with images
            prompt = """
            Analyze these frames from a job interview video. Focus on:
            1. Candidate's facial expressions and emotions
            2. Body language and posture
            3. Eye contact and engagement
            4. Overall presentation
            
            Provide a detailed assessment of the candidate's non-verbal communication.
            """
            
            # Process frames with vision model
            inputs = [prompt]
            for frame in frames:
                try:
                    # Convert frame to base64
                    _, buffer = cv2.imencode('.jpg', frame)
                    encoded_frame = base64.b64encode(buffer).decode('utf-8')
                    
                    # Add as image to the input
                    image_part = {
                        "inlineData": {
                            "data": encoded_frame,
                            "mimeType": "image/jpeg"
                        }
                    }
                    inputs.append(image_part)
                except Exception as e:
                    logger.error(f"Error encoding frame: {str(e)}")
                    continue
            
            response = await self.vision_model.generate_content_async(inputs)
            
            if hasattr(response, 'text'):
                analysis = {
                    "non_verbal_analysis": response.text,
                    "frames_analyzed": len(frames)
                }
                return analysis
            else:
                logger.error("Vision model didn't return a valid text response")
                return {"error": "Failed to analyze video frames"}
                
        except Exception as e:
            logger.error(f"Error analyzing video: {str(e)}")
            return {"error": f"Error analyzing video: {str(e)}"}
    
    def _extract_frames_from_video(self, video_path: str, num_frames: int = 5) -> List:
        """Extract frames from a video file at regular intervals"""
        try:
            import cv2
            
            frames = []
            video = cv2.VideoCapture(video_path)
            
            # Get video properties
            frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
            if frame_count <= 0:
                logger.error(f"Invalid frame count: {frame_count}")
                return []
                
            # Calculate frame interval
            interval = max(1, frame_count // num_frames)
            
            for i in range(num_frames):
                frame_position = min(i * interval, frame_count - 1)
                video.set(cv2.CAP_PROP_POS_FRAMES, frame_position)
                success, frame = video.read()
                
                if success:
                    frames.append(frame)
            
            video.release()
            return frames
            
        except Exception as e:
            logger.error(f"Error extracting frames: {str(e)}")
            return []
    
    async def analyze_audio(self, audio_path: str) -> Dict[str, Any]:
        """Analyze audio from an interview
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Dict with analysis results
        """
        try:
            # Extract audio features
            features = self._extract_audio_features(audio_path)
            
            # Create prompt with audio features
            prompt = f"""
            Analyze the following audio features from a job interview:
            
            Speaking rate: {features.get('speaking_rate', 'Unknown')} words per minute
            Average volume: {features.get('average_volume', 'Unknown')} dB
            Volume variation: {features.get('volume_variation', 'Unknown')} dB
            Pause frequency: {features.get('pause_frequency', 'Unknown')} pauses per minute
            Average pause duration: {features.get('average_pause_duration', 'Unknown')} seconds
            
            Based on these audio features, provide an assessment of:
            1. The candidate's speaking confidence
            2. Communication clarity
            3. Speech pacing and rhythm
            4. Overall verbal communication quality
            
            Explain what these features suggest about the candidate's communication style and interview performance.
            """
            
            response = await self.model.generate_content_async(prompt)
            
            if hasattr(response, 'text'):
                analysis = {
                    "audio_features": features,
                    "verbal_analysis": response.text
                }
                return analysis
            else:
                logger.error("Model didn't return a valid text response for audio analysis")
                return {"error": "Failed to analyze audio features"}
                
        except Exception as e:
            logger.error(f"Error analyzing audio: {str(e)}")
            return {"error": f"Error analyzing audio: {str(e)}"}
    
    def _extract_audio_features(self, audio_path: str) -> Dict[str, Any]:
        """Extract features from audio file"""
        try:
            import librosa
            import numpy as np
            
            # Load audio file
            y, sr = librosa.load(audio_path, sr=None)
            
            # Extract features
            # 1. Volume (RMS energy)
            rms = librosa.feature.rms(y=y)[0]
            average_volume = float(np.mean(rms))
            volume_variation = float(np.std(rms))
            
            # 2. Speaking rate estimation (approximate)
            # Use onset detection to approximate word boundaries
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
            estimated_speaking_rate = len(onset_frames) / (len(y) / sr) * 60  # words per minute (approximation)
            
            # 3. Silence detection for pauses
            non_silent_intervals = librosa.effects.split(y, top_db=20)
            pauses = []
            
            for i in range(len(non_silent_intervals) - 1):
                pause_start = non_silent_intervals[i][1]
                pause_end = non_silent_intervals[i+1][0]
                pause_duration = (pause_end - pause_start) / sr
                
                if pause_duration >= 0.5:  # Only count pauses >= 0.5 seconds
                    pauses.append(pause_duration)
            
            pause_frequency = len(pauses) / (len(y) / sr) * 60  # pauses per minute
            avg_pause_duration = np.mean(pauses) if pauses else 0
            
            return {
                "speaking_rate": round(estimated_speaking_rate, 2),
                "average_volume": round(average_volume * 100, 2),  # Scale for readability
                "volume_variation": round(volume_variation * 100, 2),  # Scale for readability
                "pause_frequency": round(pause_frequency, 2),
                "average_pause_duration": round(avg_pause_duration, 2)
            }
            
        except Exception as e:
            logger.error(f"Error extracting audio features: {str(e)}")
            return {
                "speaking_rate": 0,
                "average_volume": 0,
                "volume_variation": 0,
                "pause_frequency": 0,
                "average_pause_duration": 0,
                "error": str(e)
            }
    
    async def check_plagiarism(self, response: str) -> Tuple[bool, float, str]:
        """Check if a response might be plagiarized or AI-generated
        
        Args:
            response: The text response to check
            
        Returns:
            Tuple of (is_plagiarism_suspected, confidence_score, explanation)
        """
        prompt = f"""
        Analyze the following response from a job interview to determine if it appears to be:
        1. Plagiarized from a common source
        2. Generated by an AI
        3. Memorized from a textbook or common resource
        4. Original and authentic
        
        Response to analyze:
        "{response}"
        
        Provide your assessment with:
        1. A determination (Yes/No) if plagiarism or AI generation is suspected
        2. A confidence score (0-100%)
        3. A brief explanation of why you made this determination
        4. Specific indicators that led to your conclusion
        
        Format your response as a JSON object with keys: "plagiarism_suspected", "confidence_score", "explanation", "indicators"
        """
        
        try:
            response_obj = await self.model.generate_content_async(prompt)
            
            if hasattr(response_obj, 'text'):
                # Try to parse the response as JSON
                try:
                    # Extract JSON if embedded in markdown code block
                    text = response_obj.text
                    if "```json" in text and "```" in text.split("```json", 1)[1]:
                        json_str = text.split("```json", 1)[1].split("```", 1)[0].strip()
                    elif "```" in text and "```" in text.split("```", 1)[1]:
                        json_str = text.split("```", 1)[1].split("```", 1)[0].strip()
                    else:
                        json_str = text
                        
                    result = json.loads(json_str)
                    
                    # Extract values with proper conversion
                    is_plagiarism = self._parse_boolean(result.get("plagiarism_suspected", "No"))
                    
                    # Extract confidence score
                    confidence_score = 0.0
                    conf_score = result.get("confidence_score", 0)
                    if isinstance(conf_score, (int, float)):
                        confidence_score = float(conf_score)
                    elif isinstance(conf_score, str):
                        # Handle cases like "75%" by extracting numbers
                        import re
                        numbers = re.findall(r'\d+', conf_score)
                        if numbers:
                            confidence_score = float(numbers[0])
                    
                    # Normalize to 0-1 range
                    if confidence_score > 1:
                        confidence_score /= 100
                        
                    # Get explanation
                    explanation = result.get("explanation", "No explanation provided")
                    
                    return is_plagiarism, confidence_score, explanation
                    
                except (json.JSONDecodeError, KeyError) as e:
                    # If JSON parsing fails, extract information manually
                    logger.warning(f"JSON parsing failed: {str(e)}")
                    
                    text = response_obj.text.lower()
                    is_plagiarism = "yes" in text and ("plagiarism" in text or "ai generated" in text)
                    
                    # Extract confidence with regex
                    import re
                    confidence_matches = re.findall(r'(\d+)%', text)
                    confidence_score = float(confidence_matches[0])/100 if confidence_matches else 0.5
                    
                    # Extract explanation - take the paragraph after "explanation"
                    explanation_match = re.search(r'explanation[:\s]+(.*?)(?=\n\n|\Z)', text, re.DOTALL)
                    explanation = explanation_match.group(1).strip() if explanation_match else "No explanation available"
                    
                    return is_plagiarism, confidence_score, explanation
                    
            else:
                logger.error("Gemini API didn't return a valid text response for plagiarism check")
                return False, 0.0, "Unable to check for plagiarism"
                
        except Exception as e:
            logger.error(f"Error checking plagiarism: {str(e)}")
            return False, 0.0, f"Error checking plagiarism: {str(e)}"
    
    def _parse_boolean(self, value: Any) -> bool:
        """Parse various representations of boolean values"""
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            return value.lower() in ('yes', 'true', 'y', '1')
        elif isinstance(value, (int, float)):
            return value > 0
        return False
    
    async def generate_final_evaluation(self, 
                                      candidate_name: str,
                                      job_title: str,
                                      job_description: str,
                                      question_responses: List[Dict[str, Any]],
                                      audio_analysis: Optional[Dict[str, Any]] = None,
                                      video_analysis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate a final evaluation report for a candidate
        
        Args:
            candidate_name: Name of the candidate
            job_title: Title of the job
            job_description: Full job description
            question_responses: List of dicts containing questions, responses and evaluations
            audio_analysis: Optional audio analysis results
            video_analysis: Optional video analysis results
            
        Returns:
            Dict with final evaluation report
        """
        # Construct a detailed prompt with all available information
        prompt = f"""
        Generate a comprehensive final evaluation report for the following candidate interview:
        
        Candidate: {candidate_name}
        Position: {job_title}
        
        Job Description:
        {job_description}
        
        Questions and Responses:
        """
        
        # Add all question responses
        for i, qr in enumerate(question_responses):
            prompt += f"""
            Question {i+1}: {qr.get('question', 'Unknown')}
            Response: {qr.get('response', 'No response')}
            Evaluation: 
            - Relevance: {qr.get('evaluation', {}).get('scores', {}).get('relevance', 'N/A')}/10
            - Clarity: {qr.get('evaluation', {}).get('scores', {}).get('clarity', 'N/A')}/10
            - Technical accuracy: {qr.get('evaluation', {}).get('scores', {}).get('technical_accuracy', 'N/A')}/10
            - Experience level: {qr.get('evaluation', {}).get('scores', {}).get('experience_level', 'N/A')}/10
            - Overall quality: {qr.get('evaluation', {}).get('scores', {}).get('overall_quality', 'N/A')}/10
            
            Strengths: {qr.get('evaluation', {}).get('feedback', {}).get('strengths', 'N/A')}
            Weaknesses: {qr.get('evaluation', {}).get('feedback', {}).get('weaknesses', 'N/A')}
            """
        
        # Add audio analysis if available
        if audio_analysis and 'verbal_analysis' in audio_analysis:
            prompt += f"""
            Audio Analysis:
            {audio_analysis.get('verbal_analysis', 'No audio analysis available')}
            """
        
        # Add video analysis if available
        if video_analysis and 'non_verbal_analysis' in video_analysis:
            prompt += f"""
            Video Analysis:
            {video_analysis.get('non_verbal_analysis', 'No video analysis available')}
            """
        
        # Request for final evaluation
        prompt += """
        Based on all the above information, please provide:
        
        1. An overall score from 0-100
        2. A hiring recommendation (Selected, Needs Review, or Rejected)
        3. A summary of key strengths
        4. A summary of areas for improvement
        5. An overall assessment explaining the recommendation (300-500 words)
        
        Format your response as a JSON object with keys: "overall_score", "recommendation", "key_strengths", "areas_for_improvement", "assessment"
        """
        
        try:
            response = await self.model.generate_content_async(prompt)
            
            if hasattr(response, 'text'):
                # Try to parse the response as JSON
                try:
                    # Extract JSON if embedded in markdown code block
                    text = response.text
                    if "```json" in text and "```" in text.split("```json", 1)[1]:
                        json_str = text.split("```json", 1)[1].split("```", 1)[0].strip()
                    elif "```" in text and "```" in text.split("```", 1)[1]:
                        json_str = text.split("```", 1)[1].split("```", 1)[0].strip()
                    else:
                        json_str = text
                        
                    evaluation_report = json.loads(json_str)
                    
                    # Calculate overall score from questions if not present
                    if "overall_score" not in evaluation_report:
                        scores = []
                        for qr in question_responses:
                            if qr.get('evaluation') and qr.get('evaluation').get('scores'):
                                scores.append(qr.get('evaluation').get('scores').get('overall_quality', 0))
                        
                        if scores:
                            evaluation_report["overall_score"] = sum(scores) * 10 / len(scores)  # Convert 0-10 to 0-100
                    
                    # Ensure recommendation has a valid value
                    valid_recommendations = ["Selected", "Needs Review", "Rejected"]
                    if "recommendation" not in evaluation_report or evaluation_report["recommendation"] not in valid_recommendations:
                        score = evaluation_report.get("overall_score", 0)
                        if score >= 80:
                            evaluation_report["recommendation"] = "Selected"
                        elif score >= 60:
                            evaluation_report["recommendation"] = "Needs Review"
                        else:
                            evaluation_report["recommendation"] = "Rejected"
                    
                    return evaluation_report
                    
                except json.JSONDecodeError as e:
                    # If JSON parsing fails, extract information using sections
                    logger.warning(f"JSON parsing failed for final evaluation: {str(e)}")
                    
                    lines = response.text.split('\n')
                    evaluation_report = {
                        "overall_score": self._extract_numeric_value(response.text, "overall score", 0, 100),
                        "recommendation": self._extract_recommendation(response.text),
                        "key_strengths": self._extract_section_from_text(response.text, "key strengths", "areas for improvement"),
                        "areas_for_improvement": self._extract_section_from_text(response.text, "areas for improvement", "assessment"),
                        "assessment": self._extract_section_from_text(response.text, "assessment", None)
                    }
                    
                    return evaluation_report
                    
            else:
                logger.error("Gemini API didn't return a valid text response for final evaluation")
                return self._get_fallback_final_evaluation()
                
        except Exception as e:
            logger.error(f"Error generating final evaluation: {str(e)}")
            return self._get_fallback_final_evaluation()
    
    def _extract_numeric_value(self, text: str, section_name: str, min_val: int, max_val: int) -> float:
        """Extract a numeric value from text"""
        import re
        
        # Look for the section
        pattern = rf"{section_name}[\s:]+(\d+)"
        match = re.search(pattern, text.lower())
        
        if match:
            value = float(match.group(1))
            return max(min_val, min(max_val, value))  # Clamp to range
        
        return (min_val + max_val) / 2  # Default to middle value
    
    def _extract_recommendation(self, text: str) -> str:
        """Extract recommendation from text"""
        text_lower = text.lower()
        
        if "selected" in text_lower:
            return "Selected"
        elif "needs review" in text_lower:
            return "Needs Review"
        elif "rejected" in text_lower:
            return "Rejected"
        
        # Default based on any score mention
        score = self._extract_numeric_value(text, "score", 0, 100)
        if score >= 80:
            return "Selected"
        elif score >= 60:
            return "Needs Review"
        else:
            return "Rejected"
    
    def _extract_section_from_text(self, text: str, section_start: str, section_end: str = None) -> str:
        """Extract a section of text between two markers"""
        text_lower = text.lower()
        start_pos = text_lower.find(section_start.lower())
        
        if start_pos == -1:
            return ""
            
        # Find the starting point after the section header
        line_end = text.find('\n', start_pos)
        if line_end == -1:
            line_end = len(text)
        
        content_start = line_end + 1
        
        # Find the ending point
        if section_end:
            end_pos = text_lower.find(section_end.lower(), content_start)
            if end_pos == -1:
                content = text[content_start:].strip()
            else:
                content = text[content_start:end_pos].strip()
        else:
            content = text[content_start:].strip()
            
        return content
    
    def _get_fallback_final_evaluation(self) -> Dict[str, Any]:
        """Return fallback final evaluation if API fails"""
        return {
            "overall_score": 50,
            "recommendation": "Needs Review",
            "key_strengths": "Unable to automatically determine strengths. Please review manually.",
            "areas_for_improvement": "Unable to automatically determine areas for improvement. Please review manually.",
            "assessment": "The automated evaluation system encountered an error. This candidate requires manual review by the recruitment team."
        }


# Create a singleton instance
gemini_service = GeminiService()