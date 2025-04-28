document.addEventListener('DOMContentLoaded', function() {
    const recordButton = document.getElementById('recordButton');
    const transcriptBox = document.getElementById('transcriptBox');
    const feedbackBox = document.getElementById('feedbackBox');
    let isRecording = false;
    let mediaRecorder;
    let audioChunks = [];

    // Check browser compatibility
    function checkBrowserSupport() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error('Your browser does not support audio recording. Please use a modern browser like Chrome, Firefox, or Edge.');
        }

        // Check for supported MIME types
        const mimeTypes = [
            'audio/wav',
            'audio/webm',
            'audio/ogg'
        ];

        const supportedType = mimeTypes.find(type => MediaRecorder.isTypeSupported(type));
        if (!supportedType) {
            throw new Error('Your browser does not support any of the required audio formats. Please use Chrome, Firefox, or Edge.');
        }

        return supportedType;
    }

    // Initialize recording functionality
    recordButton.addEventListener('click', async function() {
        if (!isRecording) {
            try {
                // Check browser support first
                const supportedMimeType = checkBrowserSupport();

                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        channelCount: 1,
                        sampleRate: 16000,
                        sampleSize: 16,
                        echoCancellation: true,
                        noiseSuppression: true
                    } 
                });

                mediaRecorder = new MediaRecorder(stream, {
                    mimeType: supportedMimeType
                });
                
                mediaRecorder.ondataavailable = (event) => {
                    audioChunks.push(event.data);
                };

                mediaRecorder.onstop = async () => {
                    // Create audio blob
                    const audioBlob = new Blob(audioChunks, { type: supportedMimeType });
                    
                    // Convert to WAV format
                    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    const arrayBuffer = await audioBlob.arrayBuffer();
                    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
                    
                    // Create WAV file
                    const wavBlob = await convertToWav(audioBuffer);
                    await submitRecording(wavBlob);
                };

                mediaRecorder.start();
                isRecording = true;
                recordButton.innerHTML = '<i class="fas fa-stop"></i> Stop Recording';
                recordButton.classList.remove('btn-primary');
                recordButton.classList.add('btn-danger');
            } catch (err) {
                console.error('Error accessing microphone:', err);
                let errorMessage = 'Error accessing microphone. ';
                
                if (err.name === 'NotAllowedError') {
                    errorMessage += 'Please grant microphone permissions in your browser settings.';
                } else if (err.name === 'NotFoundError') {
                    errorMessage += 'No microphone found. Please connect a microphone and try again.';
                } else if (err.name === 'NotReadableError') {
                    errorMessage += 'Your microphone is busy or not working properly. Please check your microphone settings.';
                } else {
                    errorMessage += err.message || 'Please ensure you have granted microphone permissions.';
                }
                
                alert(errorMessage);
            }
        } else {
            mediaRecorder.stop();
            isRecording = false;
            recordButton.innerHTML = '<i class="fas fa-microphone"></i> Record Answer';
            recordButton.classList.remove('btn-danger');
            recordButton.classList.add('btn-primary');
        }
    });

    // Function to convert AudioBuffer to WAV format
    function convertToWav(audioBuffer) {
        const numOfChannels = 1;
        const length = audioBuffer.length * numOfChannels * 2;
        const buffer = new ArrayBuffer(44 + length);
        const view = new DataView(buffer);
        
        // Write WAV header
        writeString(view, 0, 'RIFF');
        view.setUint32(4, 36 + length, true);
        writeString(view, 8, 'WAVE');
        writeString(view, 12, 'fmt ');
        view.setUint32(16, 16, true);
        view.setUint16(20, 1, true);
        view.setUint16(22, numOfChannels, true);
        view.setUint32(24, audioBuffer.sampleRate, true);
        view.setUint32(28, audioBuffer.sampleRate * 2, true);
        view.setUint16(32, numOfChannels * 2, true);
        view.setUint16(34, 16, true);
        writeString(view, 36, 'data');
        view.setUint32(40, length, true);
        
        // Write audio data
        const channelData = audioBuffer.getChannelData(0);
        let offset = 44;
        for (let i = 0; i < channelData.length; i++) {
            view.setInt16(offset, channelData[i] * 0x7FFF, true);
            offset += 2;
        }
        
        return new Blob([buffer], { type: 'audio/wav' });
    }

    function writeString(view, offset, string) {
        for (let i = 0; i < string.length; i++) {
            view.setUint8(offset + i, string.charCodeAt(i));
        }
    }

    // Function to submit recording to server
    async function submitRecording(audioBlob) {
        const formData = new FormData();
        formData.append('audio', audioBlob);
        
        // Get the question_id from the URL
        const urlParams = new URLSearchParams(window.location.search);
        const questionId = urlParams.get('question_id') || window.location.pathname.split('/').pop();
        formData.append('question_id', questionId);
        
        try {
            // Show processing message
            transcriptBox.textContent = 'Processing your recording...';
            feedbackBox.innerHTML = '<div class="text-center"><div class="spinner-border text-primary" role="status"></div><p class="mt-2">Generating feedback...</p></div>';
            
            const response = await fetch('/api/record-answer', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            if (data.status === 'success' && data.transcript) {
                // Update transcript
                transcriptBox.textContent = data.transcript || 'No transcript available';
                
                // Get feedback
                const feedbackResponse = await fetch('/api/submit-feedback', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ 
                        question_id: questionId,
                        transcript: data.transcript 
                    })
                });
                
                const feedbackData = await feedbackResponse.json();
                if (feedbackData.status === 'success') {
                    // Format the feedback with proper HTML
                    const score = feedbackData.score || 'N/A';
                    
                    feedbackBox.innerHTML = `
                        <div class="mb-3">
                            <strong>Score:</strong> ${score}/10
                        </div>
                        ${feedbackData.feedback}
                    `;
                } else {
                    feedbackBox.innerHTML = '<div class="alert alert-warning">Feedback will be available shortly...</div>';
                }
            } else {
                transcriptBox.textContent = 'Error processing your recording. Please try again.';
                feedbackBox.innerHTML = '<div class="alert alert-danger">Feedback unavailable due to an error.</div>';
            }
        } catch (err) {
            console.error('Error submitting recording:', err);
            transcriptBox.textContent = 'Error processing your recording. Please try again.';
            feedbackBox.innerHTML = '<div class="alert alert-danger">Feedback unavailable due to an error.</div>';
        }
    }

    function stopRecording() {
        if (!mediaRecorder) return;
        
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
        mediaRecorder = null;
        
        // Show processing message
        const transcriptDiv = document.getElementById('transcript');
        transcriptDiv.innerHTML = '<p class="text-muted">Processing your recording...</p>';
        
        // Create form data
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.wav');
        formData.append('question_id', currentQuestionId);
        
        // Send the recording to the server
        fetch('/api/record-answer', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success' && data.transcript) {
                transcriptDiv.innerHTML = `<p><strong>Your Answer:</strong><br>${data.transcript}</p>`;
                // Enable the submit button
                document.getElementById('submitFeedback').disabled = false;
            } else {
                transcriptDiv.innerHTML = `<p class="text-danger">${data.message || 'Error processing your recording. Please try again.'}</p>`;
                document.getElementById('submitFeedback').disabled = true;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            transcriptDiv.innerHTML = '<p class="text-danger">Error processing your recording. Please try again.</p>';
            document.getElementById('submitFeedback').disabled = true;
        });
    }
}); 