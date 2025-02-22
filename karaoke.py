from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
import logging
import torch
from werkzeug.utils import secure_filename
from demucs.apply import apply_model
from demucs.pretrained import get_model
from demucs.audio import AudioFile, save_audio
import numpy as np

# Flask App Configuration
app = Flask(__name__, template_folder='app/templates')

UPLOAD_FOLDER = '/tmp/uploads'
OUTPUT_FOLDER = '/tmp/output'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

logging.basicConfig(level=logging.DEBUG)

def separate_audio(input_path, output_path, base_filename):
    """ Runs Demucs audio separation on an uploaded file. """
    device = torch.device("cpu")  # Ensure CPU execution
    model = get_model('mdx_extra_q')
    model.to(device)
    model.eval()

    # Load and process audio file
    audio = AudioFile(input_path).read()
    audio = torch.from_numpy(audio).float().mean(0, keepdim=True).to(device)  # Convert to mono & move to CPU

    # Apply model for separation
    with torch.no_grad():
        sources = apply_model(model, audio, split=True)[0].cpu()  # Ensure output is on CPU

    # Prepare output directory
    output_dir = os.path.join(output_path, 'htdemucs', base_filename)
    os.makedirs(output_dir, exist_ok=True)

    # Convert tensors to numpy arrays and save
    save_audio(sources[0].numpy(), f"{output_dir}/vocals.wav", model.samplerate)
    save_audio(sources[1].numpy(), f"{output_dir}/no_vocals.wav", model.samplerate)

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
    app.run(debug=True)
