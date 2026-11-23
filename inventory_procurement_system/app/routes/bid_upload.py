import os
import uuid
import threading
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from werkzeug.utils import secure_filename
from app.utils.ocr_parser import parse_bid_document
from app.utils.consensus import parse_with_consensus

bid_upload_bp = Blueprint('bid_upload', __name__, url_prefix='/bids')

JOBS = {}


def get_upload_folder():
    return current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads')


def parse_and_store(job_id: str, file_path: str, use_consensus: bool):
    """Background worker: parse document and store result in JOBS."""
    try:
        if use_consensus:
            result = parse_with_consensus(file_path)
            parsed = result.get('llm') or result.get('regex') or {}
            parsed['_consensus'] = result
        else:
            parsed = parse_bid_document(file_path)
        JOBS[job_id] = {'status': 'done', 'result': parsed}
    except Exception as e:
        print(f"[ERROR] Background parse failed for job {job_id}: {e}")
        JOBS[job_id] = {'status': 'error', 'result': None}


@bid_upload_bp.route('/scan', methods=['GET', 'POST'])
def scan_bid():
    parsed_data = None
    job_id = None

    if request.method == 'POST':
        print("--- POST REQUEST RECEIVED ---")

        if 'file' not in request.files:
            print("ERROR: No 'file' found in request.files")
            flash('No file part uploaded.', 'danger')
            return redirect(request.url)

        file = request.files['file']
        print(f"File uploaded: {file.filename}")

        if file.filename == '':
            print("ERROR: File name is empty")
            flash('No file selected.', 'warning')
            return redirect(request.url)

        if file:
            upload_folder = get_upload_folder()
            os.makedirs(upload_folder, exist_ok=True)
            filename = secure_filename(file.filename)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            print(f"File saved successfully to: {file_path}")

            use_consensus = request.form.get('use_consensus') == '1'

            if use_consensus:
                # Async: start background job and return job id for polling
                job_id = str(uuid.uuid4())
                JOBS[job_id] = {'status': 'pending', 'result': None}
                threading.Thread(
                    target=parse_and_store, args=(job_id, file_path, True)
                ).start()
                return jsonify({'job_id': job_id, 'status': 'pending'}), 202

            # Synchronous parse (default)
            print("Sending file to parse_bid_document()...")
            parsed_data = parse_bid_document(file_path)
            if parsed_data and parsed_data.get('items') is not None:
                print(f"Document scan extracted {len(parsed_data['items'])} item(s).")
                flash('Document scanned successfully!', 'success')
            else:
                parsed_data = None
                flash('Could not extract bid details from this document. Please check the file and try again.', 'danger')

    return render_template('bids/scan.html', parsed_data=parsed_data, job_id=job_id)


@bid_upload_bp.route('/scan/status/<job_id>')
def scan_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({'error': 'not found'}), 404
    if job['status'] == 'pending':
        return jsonify({'status': 'pending'})
    return jsonify({'status': 'done', 'data': job['result']})
