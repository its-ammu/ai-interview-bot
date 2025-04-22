document.addEventListener('DOMContentLoaded', function() {
    const generateQuestionsBtn = document.getElementById('generateQuestions');
    const questionList = document.getElementById('questionList');
    const chatMessages = document.getElementById('chatMessages');
    const questionInput = document.getElementById('questionInput');
    const sendQuestionBtn = document.getElementById('sendQuestion');
    const candidateModal = new bootstrap.Modal(document.getElementById('candidateModal'));

    // Generate Questions
    generateQuestionsBtn.addEventListener('click', async function() {
        try {
            const response = await fetch('/api/generate-questions', {
                method: 'POST'
            });
            
            const data = await response.json();
            if (data.status === 'success') {
                displayQuestions(data.questions);
            }
        } catch (err) {
            console.error('Error generating questions:', err);
            alert('Error generating questions. Please try again.');
        }
    });

    // Display generated questions
    function displayQuestions(questions) {
        questionList.innerHTML = '';
        questions.forEach((question, index) => {
            const questionElement = document.createElement('div');
            questionElement.className = 'question-item p-2 border-bottom';
            questionElement.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <span>${index + 1}. ${question}</span>
                    <button class="btn btn-sm btn-outline-primary edit-question" data-index="${index}">
                        <i class="fas fa-edit"></i>
                    </button>
                </div>
            `;
            questionList.appendChild(questionElement);
        });
    }

    // Question Answering Bot
    sendQuestionBtn.addEventListener('click', async function() {
        const question = questionInput.value.trim();
        if (!question) return;

        // Add user question to chat
        addMessageToChat('user', question);
        questionInput.value = '';

        try {
            const response = await fetch('/api/check-answer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ question })
            });
            
            const data = await response.json();
            if (data.status === 'success') {
                addMessageToChat('bot', data.answer);
            }
        } catch (err) {
            console.error('Error checking answer:', err);
            addMessageToChat('bot', 'Sorry, I encountered an error processing your question.');
        }
    });

    // Add message to chat interface
    function addMessageToChat(sender, message) {
        const messageElement = document.createElement('div');
        messageElement.className = `chat-message ${sender}-message mb-2 p-2 rounded`;
        messageElement.innerHTML = `
            <strong>${sender === 'user' ? 'You' : 'Bot'}:</strong>
            <p class="mb-0">${message}</p>
        `;
        chatMessages.appendChild(messageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // View candidate details
    document.querySelectorAll('.view-details').forEach(button => {
        button.addEventListener('click', function() {
            const candidateId = this.dataset.id;
            loadCandidateDetails(candidateId);
            candidateModal.show();
        });
    });

    // Load candidate details
    async function loadCandidateDetails(candidateId) {
        try {
            const response = await fetch(`/api/candidate/${candidateId}`);
            const data = await response.json();
            
            if (data.status === 'success') {
                displayCandidateDetails(data.candidate);
            }
        } catch (err) {
            console.error('Error loading candidate details:', err);
            alert('Error loading candidate details. Please try again.');
        }
    }

    // Display candidate details in modal
    function displayCandidateDetails(candidate) {
        const questionBreakdown = document.querySelector('.question-breakdown');
        const audioPlayer = document.querySelector('.audio-player');
        
        // Display question breakdown
        questionBreakdown.innerHTML = candidate.questions.map(q => `
            <div class="question-item mb-3">
                <h6>${q.question}</h6>
                <p class="mb-1">Answer: ${q.answer}</p>
                <p class="mb-1">Score: ${q.score}</p>
                <p class="mb-0">Feedback: ${q.feedback}</p>
            </div>
        `).join('');

        // Display audio player if audio exists
        if (candidate.audio_path) {
            audioPlayer.innerHTML = `
                <audio controls class="w-100">
                    <source src="${candidate.audio_path}" type="audio/wav">
                    Your browser does not support the audio element.
                </audio>
            `;
        } else {
            audioPlayer.innerHTML = '<p>No audio available</p>';
        }
    }

    // Download scorecard
    document.getElementById('downloadScorecard').addEventListener('click', function() {
        // TODO: Implement scorecard download functionality
        alert('Scorecard download functionality will be implemented here');
    });
}); 