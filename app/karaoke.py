from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
import subprocess
from werkzeug.utils import secure_filename
import logging

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output/htdemucs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        app.logger.debug('No file part in the request')
        return redirect(request.url)
    file = request.files['file']
    if file.filename == "":
        app.logger.debug('No selected file')
        return redirect(request.url)

    filename = secure_filename(file.filename)
    upload_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(upload_path)
    
    # Run demucs command to split audio into vocals and no_vocals using the faster model
    base_filename = os.path.splitext(filename)[0]
    # Demucs will create output/htdemucs/<base_filename>/vocals.wav and no_vocals.wav
    command = ['demucs', '--two-stems=vocals', '--out', 'output', upload_path]
    subprocess.run(command, check=True)
    
    vocals_url = url_for('serve_output', filename=f"htdemucs/{base_filename}/vocals.wav")
    no_vocals_url = url_for('serve_output', filename=f"htdemucs/{base_filename}/no_vocals.wav")
    
    app.logger.debug(f'Vocals URL: {vocals_url}')
    app.logger.debug(f'No Vocals URL: {no_vocals_url}')
    
    return render_template('result.html', vocals_url=vocals_url, no_vocals_url=no_vocals_url)

@app.route('/output/<path:filename>')
def serve_output(filename):
    app.logger.debug(f'Serving file: {filename}')
    return send_from_directory('output', filename, as_attachment=False)

def handler(event, context):
    return app(event, context)