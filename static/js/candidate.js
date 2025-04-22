document.addEventListener('DOMContentLoaded', function() {
    const recordButton = document.getElementById('recordButton');
    const transcriptBox = document.getElementById('transcriptBox');
    const feedbackBox = document.getElementById('feedbackBox');
    let isRecording = false;
    let mediaRecorder;
    let audioChunks = [];

    // Initialize recording functionality
    recordButton.addEventListener('click', async function() {
        if (!isRecording) {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                
                mediaRecorder.ondataavailable = (event) => {
                    audioChunks.push(event.data);
                };

                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    await submitRecording(audioBlob);
                };

                mediaRecorder.start();
                isRecording = true;
                recordButton.innerHTML = '<i class="fas fa-stop"></i> Stop Recording';
                recordButton.classList.remove('btn-primary');
                recordButton.classList.add('btn-danger');
            } catch (err) {
                console.error('Error accessing microphone:', err);
                alert('Error accessing microphone. Please ensure you have granted microphone permissions.');
            }
        } else {
            mediaRecorder.stop();
            isRecording = false;
            recordButton.innerHTML = '<i class="fas fa-microphone"></i> Record Answer';
            recordButton.classList.remove('btn-danger');
            recordButton.classList.add('btn-primary');
        }
    });

    // Function to submit recording to server
    async function submitRecording(audioBlob) {
        const formData = new FormData();
        formData.append('audio', audioBlob);
        
        try {
            const response = await fetch('/api/record-answer', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            if (data.status === 'success') {
                // Update transcript
                transcriptBox.textContent = data.transcript || 'Processing...';
                
                // Get feedback
                const feedbackResponse = await fetch('/api/submit-feedback', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ transcript: data.transcript })
                });
                
                const feedbackData = await feedbackResponse.json();
                feedbackBox.textContent = feedbackData.feedback || 'Feedback will be available shortly...';
            }
        } catch (err) {
            console.error('Error submitting recording:', err);
            alert('Error submitting recording. Please try again.');
        }
    }
}); 