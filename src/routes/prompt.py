from flask import Blueprint, jsonify, request, render_template, send_from_directory
from models import db, UserProfile
from pathlib import Path
import os
from cv_ocr import extract_text_from_cv

prompt_bp = Blueprint('prompt', __name__)

# Directory to store uploaded CVs
CV_UPLOAD_DIR = Path(__file__).parent.parent.parent / 'uploads' / 'cvs'
CV_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# PAGE ROUTE
# ============================================================================

@prompt_bp.route('/prompt')
def prompt():
    return render_template('prompt.html', active_page='prompt')

# ============================================================================
# PROFILE API ENDPOINTS
# ============================================================================

@prompt_bp.route('/profile', methods=['GET'])
def get_profile():
    try:
        # Get or create the first profile (assuming single user system)
        profile = UserProfile.query.first()
        if not profile:
            profile = UserProfile()
            db.session.add(profile)
            db.session.commit()

        return jsonify({
            'id': profile.id,
            'cv_text': profile.cv_text,
            'cv_filename': profile.cv_filename,
            'job_preferences': profile.job_preferences,
            'no_preferences': profile.no_preferences,
            'updated_at': profile.updated_at.isoformat()
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@prompt_bp.route('/profile', methods=['PUT'])
def update_profile():
    try:
        data = request.json
        profile = UserProfile.query.first()
        if not profile:
            profile = UserProfile()
            db.session.add(profile)

        if 'cv_text' in data:
            profile.cv_text = data['cv_text']
        if 'cv_filename' in data:
            profile.cv_filename = data['cv_filename']
        if 'job_preferences' in data:
            profile.job_preferences = data['job_preferences']
        if 'no_preferences' in data:
            profile.no_preferences = data['no_preferences']

        db.session.commit()
        return jsonify({
            'status': 'success',
            'updated_at': profile.updated_at.isoformat()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@prompt_bp.route('/profile/cv/<filename>')
def serve_cv(filename):
    """Serve the uploaded CV PDF file."""
    try:
        return send_from_directory(CV_UPLOAD_DIR, filename)
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'CV file not found'}), 404

@prompt_bp.route('/profile/check', methods=['GET'])
def check_profile():
    """Check if user has uploaded CV and provided job preferences."""
    try:
        profile = UserProfile.query.first()

        has_cv = profile and profile.cv_text and len(profile.cv_text.strip()) > 0
        has_preferences = profile and profile.job_preferences and len(profile.job_preferences.strip()) > 0

        return jsonify({
            'has_cv': has_cv,
            'has_preferences': has_preferences,
            'is_complete': has_cv and has_preferences
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@prompt_bp.route('/profile/upload', methods=['POST'])
def upload_cv():
    try:
        if 'cv_file' not in request.files:
            return jsonify({'status': 'error', 'message': 'No file provided'}), 400

        file = request.files['cv_file']
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'No file selected'}), 400

        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'status': 'error', 'message': 'Only PDF files are supported'}), 400

        # Get or create profile
        profile = UserProfile.query.first()
        if not profile:
            profile = UserProfile()
            db.session.add(profile)

        # Save file permanently to uploads/cvs directory
        cv_file_path = CV_UPLOAD_DIR / file.filename
        file.save(str(cv_file_path))

        # Extract text from PDF using Ollama vision model
        extracted_text = extract_text_from_cv(cv_file_path)

        # Update profile with extracted text and filename
        profile.cv_filename = file.filename
        profile.cv_text = extracted_text
        db.session.commit()

        return jsonify({
            'status': 'success',
            'filename': file.filename,
            'extracted_text': extracted_text
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
