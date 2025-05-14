# AI Interview Automation System

An intelligent FastAPI-based application that automates and enhances the interview process by leveraging AI technologies, video analysis, and automated scheduling.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Code Flow](#code-flow)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Using the System](#using-the-system)
  - [Step 1: Create Job Postings](#step-1-create-job-postings)
  - [Step 2: Add Candidates](#step-2-add-candidates)
  - [Step 3: Schedule Interviews](#step-3-schedule-interviews)
  - [Step 4: Conduct & Analyze Interviews](#step-4-conduct--analyze-interviews)
  - [Step 5: Review Evaluations](#step-5-review-evaluations)
- [Testing](#testing)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Future Enhancements](#future-enhancements)
- [License](#license)

## Overview

The AI Interview Automation System is designed to streamline the interview process by:
- Automatically scheduling interviews using the Zoom API
- Generating relevant interview questions using Google's Gemini AI
- Analyzing interview recordings for candidate assessment
- Providing comprehensive evaluation reports

This system reduces the manual effort required in the interview process while ensuring consistent and objective candidate evaluation.

## Features

- **Automated Interview Scheduling**: Integration with Zoom API for seamless interview scheduling
- **AI-Powered Question Generation**: Uses Google's Gemini AI to generate relevant interview questions based on job descriptions and candidate profiles
- **Video Analysis**: Analyze candidate's interview recordings for insights on behavior, speech patterns, and engagement
- **Email Notifications**: Automated email communication with candidates
- **Comprehensive Reporting**: Generate detailed reports after interviews

## Project Structure

```
app/
├── api/             # API routes and endpoints
├── core/            # Core configuration and database setup
├── models/          # Database models and schemas
├── services/        # Integration with external services (Zoom, Gemini, Email)
├── utils/           # Utility functions for analysis and interview management
recordings/          # Storage for interview recordings
reports/             # Generated interview reports
```

## Code Flow

The system follows this general flow:

1. **Configuration & Initialization**:
   - `app/core/config.py` - Defines application settings and environment variables
   - `app/core/database.py` - Sets up the SQLAlchemy database connection
   - `app/main.py` - Initializes the FastAPI application and includes routes

2. **Data Models**:
   - `app/models/database.py` - SQLAlchemy ORM models for database tables
   - `app/models/schemas.py` - Pydantic models for request/response validation

3. **API Routes**:
   - `app/api/routes.py` - Defines all API endpoints that clients interact with

4. **External Services**:
   - `app/services/zoom_service.py` - Handles Zoom API integration
   - `app/services/gemini_service.py` - Handles Google Gemini AI integration
   - `app/services/email_service.py` - Handles email communication

5. **Utility Functions**:
   - `app/utils/interview_utils.py` - Core interview management logic
   - `app/utils/analysis_utils.py` - Video and audio analysis functions

## Prerequisites

- Python 3.8+
- FastAPI
- SQLAlchemy
- OpenCV (for video analysis)
- Zoom API credentials
- Google Gemini API key
- SMTP server for emails

## Installation & Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd project-resume
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables or create a `.env` file with the following:
   ```
   DATABASE_URL=sqlite:///interview_automation.db
   ZOOM_API_KEY=your_zoom_api_key
   ZOOM_API_SECRET=your_zoom_api_secret
   GEMINI_API_KEY=your_gemini_api_key
   EMAIL_HOST=smtp.example.com
   EMAIL_PORT=587
   EMAIL_USERNAME=your_email
   EMAIL_PASSWORD=your_email_password
   ```

## Running the Application

Start the application with:

```bash
python -m app.main
```

The API will be available at `http://localhost:8000`.

- API Documentation: `http://localhost:8000/docs`
- OpenAPI Specification: `http://localhost:8000/openapi.json`

## API Documentation

The system provides a comprehensive Swagger UI documentation at `/docs` which allows you to:
- View all available endpoints
- Understand request/response formats
- Test API calls directly from the browser

## Using the System

### Step 1: Create Job Postings

Before scheduling interviews, you need to create job postings:

```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/jobs/' \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Senior Software Engineer",
    "description": "We are looking for a senior software engineer with experience in Python and cloud technologies.",
    "requirements": "5+ years experience with Python, experience with AWS, knowledge of REST APIs",
    "is_active": true
  }'
```

Or use the Swagger UI at `/docs` to create job postings.

### Step 2: Add Candidates

Next, add candidates to the system:

```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/candidates/' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "John Doe",
    "email": "john.doe@example.com",
    "phone": "123-456-7890",
    "resume_url": "https://example.com/resume.pdf"
  }'
```

### Step 3: Schedule Interviews

Schedule interviews for candidates:

```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/schedule-interview/' \
  -H 'Content-Type: application/json' \
  -d '{
    "candidate_email": "john.doe@example.com",
    "job_id": 1,
    "scheduled_time": "2025-05-20T10:00:00Z",
    "duration_minutes": 45
  }'
```

Upon successful scheduling:
- A Zoom meeting is created
- Interview questions are automatically generated
- Email invitation is sent to the candidate

### Step 4: Conduct & Analyze Interviews

After the interview is conducted:

1. Process the recording (automatically triggered if Zoom webhooks are configured, or can be triggered manually):

```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/interviews/1/process-recording'
```

2. Generate the evaluation:

```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/interviews/1/evaluate'
```

The system will:
- Analyze video for non-verbal cues
- Analyze audio for speaking patterns
- Evaluate responses to questions
- Generate a comprehensive report

### Step 5: Review Evaluations

Access the evaluation results:

```bash
curl -X 'GET' \
  'http://localhost:8000/api/v1/interviews/1/evaluation'
```

The system automatically:
- Updates candidate status based on evaluation
- Sends results to candidate (if configured)
- Saves detailed report for review

## Testing

The application includes several ways to test functionality:

### Manual Testing via Swagger UI

1. Access the Swagger UI at `http://localhost:8000/docs`
2. Authenticate if required
3. Test the following endpoints:

#### Basic Endpoints
- `GET /` - Verify the API is running
- `GET /health` - Check system health

#### Candidate Management
- `POST /api/v1/candidates/` - Create a new candidate profile
- `GET /api/v1/candidates/` - List all candidates
- `GET /api/v1/candidates/{candidate_id}` - Get specific candidate details

#### Job Management
- `POST /api/v1/jobs/` - Create a new job posting
- `GET /api/v1/jobs/` - List all job postings

#### Interview Management
- `POST /api/v1/schedule-interview/` - Schedule a new interview
- `GET /api/v1/interviews/` - List all scheduled interviews
- `PUT /api/v1/interviews/{interview_id}` - Update interview details

#### AI Features
- `POST /api/v1/generate-questions/` - Generate AI questions for an interview
- `POST /api/v1/analyze-interview/` - Analyze a recorded interview

### Automated Testing

For automated testing, you can use pytest. Create test files in a `tests` directory and run:

```bash
pytest
```

## Configuration

The system is configurable through `app/core/config.py` or environment variables:

- **Database settings**: Configure the database connection
- **API integration**: Set API keys for Zoom and Gemini
- **Email settings**: Configure SMTP settings for email notifications
- **Storage paths**: Set paths for recordings and reports

## Troubleshooting

### Common Issues

- **Database issues**: Check that `interview_automation.db` is created and accessible
- **OpenCV errors**: Ensure OpenCV is properly installed (`pip install opencv-python`)
- **API credentials**: Verify all API keys and credentials in your configuration
- **Email sending failures**: Check SMTP settings and permissions

### Logging

The application logs to both console and file (`app.log`). Check these logs for detailed error information.

## Future Enhancements

Planned enhancements include:
- Real-time interview monitoring
- Integration with more AI models
- Custom interview templates
- Advanced analytics dashboard
- Multi-language support

## License

[Specify your license here]