from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
import json
import openai
import os
from io import BytesIO
from flask_migrate import Migrate
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from dotenv import load_dotenv
from transformers import pipeline, AutoTokenizer, AutoModelForQuestionAnswering

# Load environment variables
load_dotenv()

# Initialize OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Initialize LangChain
llm = OpenAI(temperature=0.7)

# Initialize QA pipeline
model_path = os.path.join(os.path.dirname(__file__), "model")
tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
model = AutoModelForQuestionAnswering.from_pretrained(model_path, local_files_only=True)

# Create pipeline with loaded model
qa_pipeline = pipeline(
    "question-answering",
    model=model,
    tokenizer=tokenizer,
    device=-1  # Use CPU
)

def get_answer(question, context):
    try:
        # Ensure context is not empty
        if not context or not context.strip():
            context = question  # Use question as context if none provided
            
        print(f"Processing question: {question}")
        print(f"Using context: {context}")
            
        result = qa_pipeline({
            "question": question,
            "context": context
        })
        
        print(f"QA pipeline result: {result}")
        
        return {
            "score": result["score"],
            "answer": result["answer"]
        }
    except Exception as e:
        print(f"Error in QA pipeline: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return {
            "score": 0.0,
            "answer": f"Error processing the question: {str(e)}"
        }

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
    context = db.Column(db.Text, nullable=True)
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

@app.route('/api/test/<int:test_id>', methods=['GET', 'DELETE'])
@login_required
@role_required('admin')
def manage_test(test_id):
    test = Test.query.get_or_404(test_id)
    
    if request.method == 'DELETE':
        try:
            # Delete all questions associated with the test
            Question.query.filter_by(test_id=test_id).delete()
            
            # Delete the test
            db.session.delete(test)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Test deleted successfully'
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Failed to delete test: {str(e)}'
            }), 500
    
    # GET request - return test details
    try:
        questions = [{
            'text': q.text,
            'answer': q.answer,
            'score': q.score,
            'feedback': q.feedback
        } for q in test.questions]
        return jsonify({
            'status': 'success',
            'test': {
                'title': test.title,
                'description': test.description,
                'questions': questions
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

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

        # Save the audio file temporarily
        temp_path = os.path.join(app.root_path, 'temp_audio.webm')
        audio_file.save(temp_path)

        try:
            # Read the file and prepare it for Whisper
            with open(temp_path, 'rb') as audio_file:
                # Send the file to OpenAI Whisper with improved parameters
                response = openai.Audio.transcribe(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text",
                    language="en",
                    temperature=0.2,
                    prompt="This is an interview answer. Please transcribe it accurately."
                )

            # Clean up the temporary file
            os.remove(temp_path)

            if not response or not response.strip():
                return jsonify({
                    'status': 'error',
                    'message': 'No transcript was generated. Please try recording again.'
                }), 400

            # Update the question with the transcribed answer
            question.answer = response.strip()
            db.session.commit()
            
            print("--------------------------------")
            print("Transcribed text:", question.answer)
            print("--------------------------------")
            
            return jsonify({
                'status': 'success',
                'transcript': question.answer
            })

        except Exception as e:
            # Clean up the temporary file in case of error
            if os.path.exists(temp_path):
                os.remove(temp_path)
            print(f"Error during transcription: {str(e)}")
            raise e

    except Exception as e:
        print(f"Error in record_answer: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Error processing your recording. Please try again.'
        }), 500

@app.route('/api/submit-feedback', methods=['POST'])
@login_required
@role_required('candidate')
def submit_feedback():
    question_id = request.json.get('question_id')
    transcript = request.json.get('transcript')
    question = Question.query.get_or_404(question_id)
    
    try:
        # Create a separate LLM instance specifically for feedback
        feedback_llm = OpenAI(temperature=0.3)  # Lower temperature for more consistent output
        
        # Generate feedback using LLM with a specific format
        feedback_prompt = PromptTemplate(
            input_variables=["answer"],
            template="""You are an expert English language evaluator. Your task is to evaluate the grammatical correctness and fluency of the following answer.

            Answer: {answer}
            
            IMPORTANT: This text has been converted from speech using speech-to-text technology. 
            Please be understanding of potential transcription errors and focus on evaluating the 
            grammatical structure and fluency that can be reasonably inferred from the text.
            
            Please evaluate ONLY the grammatical correctness and fluency of the answer, NOT the content or correctness of the information.
            
            Provide your evaluation in the EXACT format below:
            
            SCORE: [number between 1-10]
            GRAMMAR: [brief assessment of grammar]
            FLUENCY: [brief assessment of fluency]
            SUGGESTIONS: [2-3 specific suggestions for improvement]
            
            Do not deviate from this format. Do not evaluate the content or correctness of the answer.
            """
        )
        
        # Create a chain for feedback generation
        feedback_chain = LLMChain(llm=feedback_llm, prompt=feedback_prompt)
        
        # Generate feedback
        feedback_result = feedback_chain.run(answer=transcript)
        
        # Parse the feedback result more robustly
        score = 7.0  # Default score if parsing fails
        grammar = "Grammar assessment not available"
        fluency = "Fluency assessment not available"
        suggestions = "No suggestions available"
        
        # Try to extract feedback components
        try:
            # Split by newlines and look for specific sections
            lines = feedback_result.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('SCORE:'):
                    try:
                        score_text = line.split('SCORE:')[1].strip()
                        # Extract just the number
                        score = float(score_text.split()[0])
                    except (ValueError, IndexError):
                        # If parsing fails, keep default score
                        pass
                elif line.startswith('GRAMMAR:'):
                    grammar = line.split('GRAMMAR:')[1].strip()
                elif line.startswith('FLUENCY:'):
                    fluency = line.split('FLUENCY:')[1].strip()
                elif line.startswith('SUGGESTIONS:'):
                    suggestions = line.split('SUGGESTIONS:')[1].strip()
                    # Add any remaining lines
                    remaining_lines = [l.strip() for l in lines[lines.index(line)+1:] if l.strip()]
                    if remaining_lines:
                        suggestions += "\n" + "\n".join(remaining_lines)
        except Exception as e:
            print(f"Error parsing feedback result: {str(e)}")
            # Keep default values if parsing fails
        
        # Format the feedback text
        suggestions_html = suggestions.replace('\n', '<br>')
        feedback_text = f"""
        <p><strong>Grammar:</strong> {grammar}</p>
        <p><strong>Fluency:</strong> {fluency}</p>
        <p><strong>Suggestions for improvement:</strong></p>
        <p>{suggestions_html}</p>
        """
        
        # Update the question with the generated feedback
        question.feedback = feedback_text
        question.score = score
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'score': score,
            'feedback': feedback_text
        })
        
    except Exception as e:
        print(f"Error generating feedback: {str(e)}")
        # Return a default response in case of error
        return jsonify({
            'status': 'success',
            'score': 7.0,
            'feedback': """
            <p><strong>Grammar:</strong> Unable to assess grammar at this time.</p>
            <p><strong>Fluency:</strong> Unable to assess fluency at this time.</p>
            <p><strong>Suggestions for improvement:</strong></p>
            <p>Please try recording your answer again.</p>
            """
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
        contexts = request.form.getlist('contexts')
        
        for i, (question_text, context) in enumerate(zip(questions, contexts)):
            question = Question(
                test_id=test.id,
                text=question_text,
                context=context,
                order=i+1
            )
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
        # Get the candidate's position from the request
        data = request.get_json()
        position = data.get('position', 'Software Engineer')  # Default to Software Engineer if not specified
        
        # Generate questions and context using LLM
        qa_pairs = generate_questions_with_llm(position)
        
        return jsonify({
            'status': 'success',
            'questions': qa_pairs
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

def generate_questions_with_llm(position, num_questions=5):
    """
    Generate interview questions and their context using LangChain and OpenAI.
    
    Args:
        position (str): The position being interviewed for
        num_questions (int): Number of questions to generate
        
    Returns:
        list: List of dictionaries containing questions and their context
    """
    # Create a prompt template for generating interview questions with context
    prompt_template = PromptTemplate(
        input_variables=["position", "num_questions"],
        template="""You are an expert technical interviewer. Generate {num_questions} interview questions 
        for a {position} position. For each question, also provide a detailed context/answer that would be 
        considered a strong response. The questions should be:
        1. Technical and relevant to the position
        2. Open-ended to assess problem-solving skills
        3. Include both theoretical and practical aspects
        4. Suitable for assessing both technical knowledge and soft skills
        
        Format each question and its context as follows:
        Q: [Question text ending with a question mark]
        C: [Detailed context/answer that would be considered a strong response]
        
        Return the questions and context in this format, with each Q/C pair separated by a blank line.
        Do not include any additional text or numbering."""
    )
    
    # Create a chain
    chain = LLMChain(llm=llm, prompt=prompt_template)
    
    # Generate questions and context
    result = chain.run(position=position, num_questions=num_questions)
    
    # Parse the result into questions and context pairs
    qa_pairs = []
    current_pair = {}
    
    for line in result.split('\n'):
        line = line.strip()
        if not line:
            if current_pair:
                qa_pairs.append(current_pair)
                current_pair = {}
        elif line.startswith('Q:'):
            current_pair['question'] = line[2:].strip()
        elif line.startswith('C:'):
            current_pair['context'] = line[2:].strip()
    
    # Add the last pair if exists
    if current_pair:
        qa_pairs.append(current_pair)
    
    return qa_pairs

@app.route('/api/question/<int:question_id>', methods=['DELETE'])
@login_required
@role_required('admin')
def delete_question(question_id):
    try:
        question = Question.query.get_or_404(question_id)
        
        # Delete the question from the database
        db.session.delete(question)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Question deleted successfully'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to delete question: {str(e)}'
        }), 500

@app.route('/admin/evaluate-test/<int:test_id>')
@login_required
@role_required('admin')
def evaluate_test(test_id):
    test = Test.query.get_or_404(test_id)
    questions = Question.query.filter_by(test_id=test_id).order_by(Question.order).all()
    return render_template('admin_evaluate_test.html', test=test, questions=questions)

@app.route('/api/evaluate-question/<int:question_id>', methods=['POST'])
@login_required
@role_required('admin')
def evaluate_question(question_id):
    try:
        question = Question.query.get_or_404(question_id)
        
        # Get the question text and context
        question_text = question.text
        context = question.context or ""  # Use empty string if context is None
        
        # Use the QA pipeline to get the answer
        qa_result = get_answer(question_text, context)
        
        # Return the model's answer for admin evaluation
        return jsonify({
            'status': 'success',
            'model_answer': qa_result['answer'],
            'score': None  # Score will be set by admin
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to evaluate question: {str(e)}'
        }), 500

@app.route('/api/update-question-score/<int:question_id>', methods=['POST'])
@login_required
@role_required('admin')
def update_question_score(question_id):
    try:
        question = Question.query.get_or_404(question_id)
        data = request.get_json()
        
        # Update the question with admin-provided score
        question.score = float(data.get('score', 0))
        question.feedback = data.get('feedback', '')
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Score updated successfully'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to update score: {str(e)}'
        }), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_default_admin()  # Ensure the default admin is created
        populate_sample_questions()  # Populate sample questions

    app.run(debug=True) 