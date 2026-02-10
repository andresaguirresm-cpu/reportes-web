import io
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from app import db
from app.models import Campaign, ProcessingRun, UploadedFile
from app.processing.engine import normalizar_nombre_campana, process_uploaded_files
from app.processing.nomenclature import normalize, detect_campaign_from_file, parse_nomenclature
import pandas as pd

upload_bp = Blueprint('upload', __name__)

ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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
            from app.processing.engine import detect_header_row
            skiprows = detect_header_row(df_raw)
            df = pd.read_excel(io.BytesIO(file_bytes), skiprows=skiprows, nrows=20)

        return detect_campaign_from_file(df)
    except Exception:
        return None


@upload_bp.route('/upload', methods=['GET'])
def upload_page():
    return render_template('upload.html')


@upload_bp.route('/upload', methods=['POST'])
def upload_files():
    if 'files' not in request.files:
        return jsonify({'error': 'No se seleccionaron archivos'}), 400

    files = request.files.getlist('files')
    valid_files = [(f, f.filename) for f in files if f.filename and allowed_file(f.filename)]

    if not valid_files:
        return jsonify({'error': 'No se encontraron archivos validos (CSV/Excel)'}), 400

    # Detect campaign from first file
    campaign_name = None
    for file_storage, filename in valid_files:
        campaign_name = detect_campaign_from_upload(file_storage, filename)
        if campaign_name:
            break

    # Allow manual override from form
    manual_campaign = request.form.get('campaign_name', '').strip()
    if manual_campaign:
        campaign_name = manual_campaign
    elif not campaign_name:
        campaign_name = 'Sin Campana'

    # Get or create campaign
    slug = normalizar_nombre_campana(campaign_name)
    campaign = Campaign.query.filter_by(slug=slug).first()
    if not campaign:
        campaign = Campaign(name=campaign_name, slug=slug)
        db.session.add(campaign)
        db.session.flush()

    # Create processing run
    run = ProcessingRun(campaign_id=campaign.id, total_files=len(valid_files))
    db.session.add(run)
    db.session.flush()

    # Register uploaded files
    for file_storage, filename in valid_files:
        file_storage.seek(0, 2)  # seek to end
        file_size = file_storage.tell()
        file_storage.seek(0)

        uploaded = UploadedFile(
            run_id=run.id,
            filename=filename,
            file_size=file_size,
        )
        db.session.add(uploaded)

    db.session.commit()

    # Process files
    # Reset file pointers
    for file_storage, filename in valid_files:
        file_storage.seek(0)

    result = process_uploaded_files(valid_files, run.id, campaign.id)

    if 'error' in result:
        return jsonify(result), 500

    return redirect(url_for('upload.run_results', run_id=run.id))


@upload_bp.route('/run/<int:run_id>')
def run_results(run_id):
    run = ProcessingRun.query.get_or_404(run_id)
    campaign = Campaign.query.get(run.campaign_id)
    from app.models import Alert
    alerts = Alert.query.filter_by(run_id=run_id).order_by(Alert.id).all()
    # Sort: CRITICO first, then ERROR, then ADVERTENCIA
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
