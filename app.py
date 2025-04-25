from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
import json
import openai
import os
from io import BytesIO
from flask_migrate import Migrate


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///interview.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this to a secure secret key in production
db = SQLAlchemy(app)

# Assuming `db` is already initialized
migrate = Migrate(app, db)

# Models
class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Float, default=0.0)
    feedback_status = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tests = db.relationship('Test', backref='candidate', lazy=True)

class Interview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate.id'), nullable=False)
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.Text)
    audio_path = db.Column(db.String(200))
    score = db.Column(db.Float)
    feedback = db.Column(db.Text)

class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Pending')  # Pending, In Progress, Completed
    questions = db.relationship('Question', backref='test', lazy=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    order = db.Column(db.Integer, nullable=False)
    answer = db.Column(db.Text)
    audio_path = db.Column(db.String(200))
    score = db.Column(db.Float)
    feedback = db.Column(db.Text)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)

class SampleQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)

def create_default_admin():
    # Check if the admin user already exists
    admin_user = User.query.filter_by(username="admin").first()
    if not admin_user:
        # Create the default admin user
        admin_user = User(username="admin", password="admin123", role="admin")
        db.session.add(admin_user)
        db.session.commit()

def populate_sample_questions():
    sample_questions = [
        "Tell me about a challenge you overcame?",
        "What are your greatest strengths and weaknesses?",
        "Where do you see yourself in 5 years?",
        "Why should we hire you?",
        "Describe a situation where you showed leadership.",
        "How do you handle stress and pressure?",
        "What is your approach to problem-solving?",
        "Tell me about a time you failed and what you learned from it."
    ]

    for question_text in sample_questions:
        existing_question = SampleQuestion.query.filter_by(text=question_text).first()
        if not existing_question:
            question = SampleQuestion(text=question_text)
            db.session.add(question)

    db.session.commit()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Role-based access control decorator
def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session or session['role'] != role:
                flash(f'You do not have permission to access this page.', 'danger')
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Routes
@app.route('/')
def index():
    if 'user' in session:
        if session['role'] == 'candidate':
            return redirect(url_for('candidate_home'))
        else:
            return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Check if the username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('register'))

        # Create a new user and store it in the database
        new_user = User(username=username, password=password, role='candidate')  # Default role is 'candidate'
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Check if user exists and password is correct
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user'] = user.username
            session['role'] = user.role
            flash(f'Welcome, {user.username}!', 'success')
            
            # Redirect based on role
            if user.role == 'candidate':
                return redirect(url_for('candidate_home'))
            else:
                return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('role', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Candidate Routes
@app.route('/candidate')
@login_required
@role_required('candidate')
def candidate_home():
    # Get candidate's tests
    candidate = Candidate.query.filter_by(name=session['user']).first()
    if not candidate:
        # Create a sample candidate if not exists
        candidate = Candidate(name=session['user'], position="Software Engineer")
        db.session.add(candidate)
        db.session.commit()
        
        # Create a sample test for the new candidate
        test = Test(
            title="Sample Interview Test",
            description="This is a sample test to get you started.",
            candidate_id=candidate.id
        )
        db.session.add(test)
        db.session.commit()
        
        # Add sample questions to the test
        sample_questions = SampleQuestion.query.limit(3).all()
        for i, question_text in enumerate(sample_questions[:3], 1):  # Add first 3 sample questions
            question = Question(
                test_id=test.id,
                text=question_text.text,
                order=i
            )
            db.session.add(question)
        
        db.session.commit()
    
    # Get all tests for the candidate
    tests = Test.query.filter_by(candidate_id=candidate.id).all()
    return render_template('candidate_home.html', tests=tests)

@app.route('/candidate/test/<int:test_id>')
@login_required
@role_required('candidate')
def candidate_test(test_id):
    test = Test.query.get_or_404(test_id)
    questions = Question.query.filter_by(test_id=test_id).order_by(Question.order).all()
    
    # Update test status to In Progress if it's Pending
    if test.status == 'Pending':
        test.status = 'In Progress'
        db.session.commit()
    
    return render_template('candidate_test.html', test=test, questions=questions)

@app.route('/api/test/<int:test_id>', methods=['GET'])
def get_test_details(test_id):
    try:
        test = Test.query.get_or_404(test_id)
        questions = [{
            'text': q.text,
            'answer': q.answer,
            'score': q.score,
            'feedback': q.feedback
        } for q in test.questions]
        return jsonify({'status': 'success', 'test': {'title': test.title, 'description': test.description, 'questions': questions}})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/candidate/question/<int:question_id>')
@login_required
@role_required('candidate')
def candidate_question(question_id):
    question = Question.query.get_or_404(question_id)
    test = Test.query.get(question.test_id)
    
    # Get all questions in the test for navigation
    all_questions = Question.query.filter_by(test_id=test.id).order_by(Question.order).all()
    current_index = next((i for i, q in enumerate(all_questions) if q.id == question_id), 0)
    
    return render_template('candidate_question.html', 
                          question=question, 
                          test=test, 
                          all_questions=all_questions,
                          current_index=current_index)

@app.route('/api/record-answer', methods=['POST'])
@login_required
@role_required('candidate')
def record_answer():
    question_id = request.form.get('question_id')
    question = Question.query.get_or_404(question_id)

    try:
        audio_file = request.files.get('audio')
        if not audio_file:
            return jsonify({'status': 'error', 'message': 'No audio file provided'}), 400

        # Read the uploaded file and wrap it in BytesIO with a proper filename
        file_stream = BytesIO(audio_file.read())
        file_stream.name = "upload.wav"  # Important for OpenAI
        file_stream.seek(0)

        openai.api_key = os.getenv("OPENAI_API_KEY")

        # Send the file to OpenAI Whisper
        response = openai.Audio.transcribe(
            model="whisper-1",
            file=file_stream,
            response_format="text",
            language="en"
        )

    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error processing audio: {str(e)}'}), 500

    question.answer = response
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'transcript': question.answer
    })

@app.route('/api/submit-feedback', methods=['POST'])
@login_required
@role_required('candidate')
def submit_feedback():
    question_id = request.json.get('question_id')
    question = Question.query.get_or_404(question_id)
    
    # TODO: Implement feedback generation
    # For now, just update the question with dummy feedback
    question.feedback = "Good answer! You demonstrated clear communication skills."
    question.score = 8.5
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'feedback': question.feedback
    })

@app.route('/api/complete-test/<int:test_id>', methods=['POST'])
@login_required
@role_required('candidate')
def complete_test(test_id):
    test = Test.query.get_or_404(test_id)
    test.status = 'Completed'
    db.session.commit()
    
    return jsonify({'status': 'success'})

# Admin Routes
@app.route('/admin')
@login_required
@role_required('admin')
def admin_dashboard():
    # Create example data if no candidates exist
    if Candidate.query.count() == 0:
        create_example_data()
    
    candidates = Candidate.query.all()
    return render_template('admin.html', candidates=candidates)

@app.route('/admin/tests')
@login_required
@role_required('admin')
def admin_tests():
    tests = Test.query.all()
    return render_template('admin_tests.html', tests=tests)

@app.route('/admin/create-test', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def create_test():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        candidate_id = request.form.get('candidate_id')
        
        # Create new test
        test = Test(title=title, description=description, candidate_id=candidate_id)
        db.session.add(test)
        db.session.commit()
        
        # Generate questions for the test
        questions = request.form.getlist('questions')
        for i, question_text in enumerate(questions):
            question = Question(test_id=test.id, text=question_text, order=i+1)
            db.session.add(question)
        
        db.session.commit()
        flash('Test created successfully!', 'success')
        return redirect(url_for('admin_tests'))
    
    candidates = Candidate.query.all()
    return render_template('admin_create_test.html', candidates=candidates)

@app.route('/api/generate-questions', methods=['POST'])
@login_required
@role_required('admin')
def generate_questions():
    try:
        # Fetch all sample questions from the database
        sample_questions = SampleQuestion.query.all()
        questions = [q.text for q in sample_questions]

        return jsonify({
            'status': 'success',
            'questions': questions
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to generate questions: {str(e)}'
        }), 500

@app.route('/api/check-answer', methods=['POST'])
@login_required
@role_required('admin')
def check_answer():
    # TODO: Implement answer checking
    return jsonify({
        'status': 'success',
        'answer': "This is a sample answer from the AI."
    })

@app.route('/api/candidate/<int:candidate_id>')
@login_required
@role_required('admin')
def get_candidate_details(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    tests = Test.query.filter_by(candidate_id=candidate_id).all()
    
    # Format candidate data for JSON response
    candidate_data = {
        'id': candidate.id,
        'name': candidate.name,
        'position': candidate.position,
        'score': candidate.score,
        'feedback_status': candidate.feedback_status,
        'tests': [{
            'id': test.id,
            'title': test.title,
            'status': test.status,
            'questions': [{
                'id': q.id,
                'question': q.text,
                'answer': q.answer,
                'score': q.score,
                'feedback': q.feedback
            } for q in test.questions]
        } for test in tests]
    }
    
    return jsonify({
        'status': 'success',
        'candidate': candidate_data
    })

def create_example_data():
    # Create example candidate if not exists
    example_candidate = Candidate.query.filter_by(name="example_candidate").first()
    if not example_candidate:
        example_candidate = Candidate(
            name="example_candidate",
            position="Software Engineer",
            score=0.0,
            feedback_status="Pending"
        )
        db.session.add(example_candidate)
        db.session.commit()

        # Create example test
        example_test = Test(
            title="Technical Interview Assessment",
            description="A comprehensive technical interview test covering programming concepts and problem-solving skills.",
            candidate_id=example_candidate.id,
            status="Pending"
        )
        db.session.add(example_test)
        db.session.commit()

        # Add example questions
        example_questions = [
            "Explain the concept of object-oriented programming and its main principles.",
            "Describe your experience with version control systems like Git.",
            "How would you handle a situation where your code is causing performance issues?",
            "Explain the difference between REST and SOAP APIs.",
            "Describe your approach to debugging complex issues."
        ]

        for i, question_text in enumerate(example_questions, 1):
            question = Question(
                test_id=example_test.id,
                text=question_text,
                order=i
            )
            db.session.add(question)
        
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_default_admin()  # Ensure the default admin is created
        populate_sample_questions()  # Populate sample questions

    app.run(debug=True) 