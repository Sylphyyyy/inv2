import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from app.utils.ocr_parser import parse_bid_document

bid_upload_bp = Blueprint('bid_upload', __name__, url_prefix='/bids')


def get_upload_folder():
    return current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads')


@bid_upload_bp.route('/scan', methods=['GET', 'POST'])
def scan_bid():
    parsed_data = None

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

            # Process document via OCR
            print("Sending file to parse_bid_document()...")
            parsed_data = parse_bid_document(file_path)
            if parsed_data and parsed_data.get('items') is not None:
                print(f"Document scan extracted {len(parsed_data['items'])} item(s).")
                flash('Document scanned successfully!', 'success')
            else:
                parsed_data = None
                flash('Could not extract bid details from this document. Please check the file and try again.', 'danger')

    return render_template('bids/scan.html', parsed_data=parsed_data)
