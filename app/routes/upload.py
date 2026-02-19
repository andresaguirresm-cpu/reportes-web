import io
import os
import uuid
import shutil
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app
from app import db
from app.models import Campaign, ProcessingRun, UploadedFile
from app.processing.engine import (normalizar_nombre_campana, process_uploaded_files,
                                   scan_campaigns_from_files, detect_header_row)
from app.processing.nomenclature import normalize, detect_campaign_from_file
import pandas as pd

upload_bp = Blueprint('upload', __name__)

ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_uploads_dir():
    """Return the uploads directory path, creating it if needed."""
    uploads_dir = os.path.join(current_app.instance_path, 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)
    return uploads_dir


def cleanup_old_uploads(max_age_hours=24):
    """Remove upload session directories older than max_age_hours."""
    try:
        uploads_dir = get_uploads_dir()
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        for name in os.listdir(uploads_dir):
            path = os.path.join(uploads_dir, name)
            if os.path.isdir(path):
                mtime = datetime.fromtimestamp(os.path.getmtime(path))
                if mtime < cutoff:
                    shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def detect_campaign_from_upload(file_storage, filename):
    """Detect campaign name from an uploaded file without consuming the stream."""
    file_bytes = file_storage.read()
    file_storage.seek(0)

    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    try:
        if ext == 'csv':
            try:
                raw_text = file_bytes.decode('utf-8')
            except UnicodeDecodeError:
                raw_text = file_bytes.decode('latin-1')

            raw_lines = raw_text.split('\n')[:15]
            skiprows = 0
            keywords = ['campana', 'campaign', 'dia', 'day', 'clics', 'clicks',
                        'impresiones', 'impressions', 'gasto', 'cost', 'coste']
            for i, line in enumerate(raw_lines):
                line_lower = normalize(line)
                matches = sum(1 for kw in keywords if kw in line_lower)
                if matches >= 2:
                    skiprows = i
                    break
            df = pd.read_csv(io.BytesIO(file_bytes), skiprows=skiprows, on_bad_lines='skip', nrows=20)
        else:
            df_raw = pd.read_excel(io.BytesIO(file_bytes), header=None, nrows=10)
            skiprows = detect_header_row(df_raw)
            df = pd.read_excel(io.BytesIO(file_bytes), skiprows=skiprows, nrows=20)

        return detect_campaign_from_file(df)
    except Exception:
        return None


@upload_bp.route('/upload', methods=['GET'])
def upload_page():
    return render_template('upload.html')


@upload_bp.route('/upload/<campaign_slug>', methods=['GET'])
def upload_update_mode(campaign_slug):
    """Upload page in update mode for a specific campaign."""
    campaign = Campaign.query.filter_by(slug=campaign_slug).first_or_404()
    return render_template('upload.html', update_campaign=campaign)


@upload_bp.route('/upload', methods=['POST'])
def upload_files():
    if 'files' not in request.files:
        return jsonify({'error': 'No se seleccionaron archivos'}), 400

    files = request.files.getlist('files')
    valid_files = [(f, f.filename) for f in files if f.filename and allowed_file(f.filename)]

    if not valid_files:
        return jsonify({'error': 'No se encontraron archivos validos (CSV/Excel)'}), 400

    # Save files to a temporary session directory
    session_id = str(uuid.uuid4())
    uploads_dir = get_uploads_dir()
    session_dir = os.path.join(uploads_dir, session_id)
    os.makedirs(session_dir, exist_ok=True)

    saved_paths = []
    for file_storage, filename in valid_files:
        safe_name = os.path.basename(filename).replace('/', '_').replace('\\', '_')
        dest_path = os.path.join(session_dir, safe_name)
        file_storage.seek(0)
        with open(dest_path, 'wb') as f:
            f.write(file_storage.read())
        saved_paths.append(dest_path)

    cleanup_old_uploads()

    # Update mode: target campaign slug passed as hidden field
    target_slug = request.form.get('target_slug', '').strip()
    if target_slug:
        campaign = Campaign.query.filter_by(slug=target_slug).first()
        if campaign:
            result = _process_session_files(session_dir, saved_paths, campaign.name,
                                            campaign_filter=campaign.name)
            if 'error' not in result:
                return redirect(url_for('dashboard.dashboard', run_id=result['run_id']))

    return redirect(url_for('upload.select_campaign', session_id=session_id))


@upload_bp.route('/upload/select/<session_id>', methods=['GET'])
def select_campaign(session_id):
    """Show detected campaigns after upload so the user can choose one."""
    uploads_dir = get_uploads_dir()
    session_dir = os.path.join(uploads_dir, session_id)

    if not os.path.isdir(session_dir):
        return redirect(url_for('upload.upload_page'))

    file_paths = [os.path.join(session_dir, f) for f in os.listdir(session_dir)]
    campaigns = scan_campaigns_from_files(file_paths)

    if not campaigns:
        return redirect(url_for('upload.upload_page'))

    return render_template('select_campaign.html',
                           campaigns=campaigns,
                           session_id=session_id)


@upload_bp.route('/upload/process', methods=['POST'])
def process_campaign():
    """Process a specific campaign from a saved upload session."""
    session_id = request.form.get('session_id', '').strip()
    campaign_name = request.form.get('campaign_name', '').strip()

    if not session_id or not campaign_name:
        return redirect(url_for('upload.upload_page'))

    uploads_dir = get_uploads_dir()
    session_dir = os.path.join(uploads_dir, session_id)

    if not os.path.isdir(session_dir):
        return redirect(url_for('upload.upload_page'))

    saved_paths = [os.path.join(session_dir, f) for f in os.listdir(session_dir)]

    result = _process_session_files(session_dir, saved_paths, campaign_name,
                                    campaign_filter=campaign_name)

    if 'error' in result:
        return jsonify(result), 500

    return redirect(url_for('dashboard.dashboard', run_id=result['run_id']))


def _process_session_files(session_dir, saved_paths, campaign_name, campaign_filter=None):
    """Create DB records and process files from a saved session directory.

    Returns dict with 'run_id' on success or 'error' on failure.
    Removes session_dir on success.
    """
    # Build in-memory file storage list
    file_storages = []
    for path in saved_paths:
        filename = os.path.basename(path)
        with open(path, 'rb') as f:
            file_bytes = f.read()
        file_storages.append((io.BytesIO(file_bytes), filename))

    if not file_storages:
        return {'error': 'No se encontraron archivos para procesar'}

    # Get or create campaign
    slug = normalizar_nombre_campana(campaign_name)
    campaign = Campaign.query.filter_by(slug=slug).first()
    if not campaign:
        campaign = Campaign(name=campaign_name, slug=slug)
        db.session.add(campaign)
        db.session.flush()

    # Create processing run
    run = ProcessingRun(campaign_id=campaign.id, total_files=len(file_storages))
    db.session.add(run)
    db.session.flush()

    for _, filename in file_storages:
        uploaded = UploadedFile(run_id=run.id, filename=filename, file_size=0)
        db.session.add(uploaded)

    db.session.commit()

    result = process_uploaded_files(file_storages, run.id, campaign.id,
                                    campaign_filter=campaign_filter)

    if 'error' not in result:
        # Remove session files only after successful processing
        shutil.rmtree(session_dir, ignore_errors=True)

    return result


@upload_bp.route('/run/<int:run_id>')
def run_results(run_id):
    run = ProcessingRun.query.get_or_404(run_id)
    campaign = Campaign.query.get(run.campaign_id)
    from app.models import Alert
    alerts = Alert.query.filter_by(run_id=run_id).order_by(Alert.id).all()
    order = {'CRITICO': 0, 'ERROR': 1, 'ADVERTENCIA': 2}
    alerts.sort(key=lambda a: order.get(a.tipo, 3))
    files = run.files.all()

    criticos = sum(1 for a in alerts if a.tipo == 'CRITICO')
    errores = sum(1 for a in alerts if a.tipo == 'ERROR')
    advertencias = sum(1 for a in alerts if a.tipo == 'ADVERTENCIA')

    return render_template('processing.html',
                           run=run,
                           campaign=campaign,
                           alerts=alerts,
                           files=files,
                           criticos=criticos,
                           errores=errores,
                           advertencias=advertencias)
