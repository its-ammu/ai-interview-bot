# AI Interview Bot – Voice & Text-based Candidate Evaluator

A Flask-based web application that provides an AI-powered interview system with both candidate and admin interfaces.

## Features

### Candidate Interface
- Voice recording for interview answers
- Real-time transcription using OpenAI Whisper API
- AI-powered feedback
- Modern, responsive design

### Admin Dashboard
- Candidate management
- Question generation
- Interview feedback review
- Audio playback
- Scorecard generation
- Question answering bot

### Authentication
- Role-based access control (Candidate/Admin)
- Secure login system
- Session management

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd <repository-name>
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the root directory with the following variables:
```
OPENAI_API_KEY=your_openai_api_key_here
```

5. Initialize the database:
```bash
flask db init
flask db migrate
flask db upgrade
```

6. Run the application:
```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Dependencies

The application uses the following key dependencies:
- Flask: Web framework
- OpenAI Python SDK (v1.0.0+): For audio transcription and AI features
- Flask-SQLAlchemy: Database ORM
- Flask-Migrate: Database migrations
- LangChain: For AI-powered question generation and feedback
- Transformers: For question answering
- gTTS: For text-to-speech conversion

## Login Credentials

For testing purposes, the following credentials are available:

- **Candidate Account**:
  - Username: candidate
  - Password: candidate123

- **Admin Account**:
  - Username: admin
  - Password: admin123

> **Note**: These credentials are hardcoded for demonstration purposes. In a production environment, user authentication should be implemented using a database with proper password hashing.

## Project Structure

```
.
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── .env                # Environment variables (not in repo)
├── static/            # Static files
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── candidate.js
│       └── admin.js
└── templates/         # HTML templates
    ├── candidate.html
    ├── admin.html
    └── login.html
```

## API Endpoints

- `POST /api/record-answer`: Record and process interview answers (uses OpenAI Whisper API)
- `POST /api/submit-feedback`: Submit feedback for review
- `POST /api/generate-questions`: Generate new interview questions
- `POST /api/check-answer`: Check answers using the QA bot
- `GET /api/candidate/<id>`: Get candidate details

## Future Improvements

- Move user authentication to a database
- Implement password hashing and security best practices
- Add user registration functionality
- Implement email verification
- Add password reset functionality
- Implement rate limiting for API calls
- Add error handling for OpenAI API failures

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 