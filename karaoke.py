from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
import subprocess
import logging
from werkzeug.utils import secure_filename

# Flask App Configuration
app = Flask(__name__, template_folder='templates')

# Use regular paths instead of /tmp since we're on a VM
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

logging.basicConfig(level=logging.DEBUG)

def separate_audio(input_path, output_path, base_filename):
    """ Runs Demucs audio separation on an uploaded file using subprocess. """
    command = [
        'demucs',
        '--two-stems=vocals',
        '-o',
        output_path,
        input_path
    ]
    
    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        app.logger.debug(f'Demucs output: {result.stdout}')
    except subprocess.CalledProcessError as e:
        app.logger.error(f'Demucs error: {e.stderr}')
        raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """ Handles file upload and audio separation. """
    if 'file' not in request.files:
        app.logger.debug('No file part in the request')
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == "":
        app.logger.debug('No selected file')
        return redirect(request.url)

    filename = secure_filename(file.filename)
    base_filename = os.path.splitext(filename)[0]
    upload_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(upload_path)
    
    try:
        separate_audio(upload_path, OUTPUT_FOLDER, base_filename)
        vocals_url = url_for('serve_output', filename=f"htdemucs/{base_filename}/vocals.wav")
        no_vocals_url = url_for('serve_output', filename=f"htdemucs/{base_filename}/no_vocals.wav")
        
        app.logger.debug(f'Vocals URL: {vocals_url}')
        app.logger.debug(f'No Vocals URL: {no_vocals_url}')
        
        return render_template('result.html', vocals_url=vocals_url, no_vocals_url=no_vocals_url)
    except Exception as e:
        app.logger.error(f'Separation failed: {str(e)}')
        return f"Error processing audio: {str(e)}", 500

@app.route('/output/<path:filename>')
def serve_output(filename):
    """ Serves the processed audio file from output directory. """
    app.logger.debug(f'Serving file: {filename}')
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=False)

def handler(event, context):
    """ AWS Lambda/Vercel entry point. """
    return app(event, context)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
