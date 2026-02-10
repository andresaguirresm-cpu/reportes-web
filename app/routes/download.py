import io
from flask import Blueprint, send_file, abort
from app.models import ProcessingRun, ReportRow, Alert
from app.processing.engine import OUTPUT_COLUMNS
import pandas as pd

download_bp = Blueprint('download', __name__)


@download_bp.route('/download/excel/<int:run_id>')
def download_excel(run_id):
    run = ProcessingRun.query.get_or_404(run_id)
    if run.status != 'completed':
        abort(404)

    rows = ReportRow.query.filter_by(run_id=run_id).all()
    if not rows:
        abort(404)

    data = [row.to_dict() for row in rows]
    df = pd.DataFrame(data)

    # Ensure column order
    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = ''
    df = df[OUTPUT_COLUMNS]

    output = io.BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)

    from app.models import Campaign
    campaign = Campaign.query.get(run.campaign_id)
    filename = f"REPORTE_{campaign.slug}_{run.created_at.strftime('%Y-%m-%d')}.xlsx"

    return send_file(output, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@download_bp.route('/download/alerts/<int:run_id>')
def download_alerts(run_id):
    run = ProcessingRun.query.get_or_404(run_id)
    alerts = Alert.query.filter_by(run_id=run_id).all()

    if not alerts:
        abort(404)

    output = io.StringIO()
    output.write("=" * 60 + "\n")
    output.write("ALERTAS DEL PROCESAMIENTO\n")
    output.write(f"Fecha: {run.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.write("=" * 60 + "\n\n")

    criticos = [a for a in alerts if a.tipo == 'CRITICO']
    errores = [a for a in alerts if a.tipo == 'ERROR']
    advertencias = [a for a in alerts if a.tipo == 'ADVERTENCIA']

    if criticos:
        output.write(">>> CRITICOS (requieren atencion inmediata):\n")
        output.write("-" * 40 + "\n")
        for a in criticos:
            output.write(f"  Archivo: {a.archivo}\n")
            output.write(f"  Problema: {a.mensaje}\n\n")

    if errores:
        output.write(">>> ERRORES:\n")
        output.write("-" * 40 + "\n")
        for a in errores:
            output.write(f"  Archivo: {a.archivo}\n")
            output.write(f"  Problema: {a.mensaje}\n\n")

    if advertencias:
        output.write(">>> ADVERTENCIAS:\n")
        output.write("-" * 40 + "\n")
        for a in advertencias:
            output.write(f"  Archivo: {a.archivo}\n")
            output.write(f"  Detalle: {a.mensaje}\n\n")

    output.write("=" * 60 + "\n")
    output.write("Revisa estos puntos antes de usar el reporte.\n")

    text_bytes = io.BytesIO(output.getvalue().encode('utf-8'))

    from app.models import Campaign
    campaign = Campaign.query.get(run.campaign_id)
    filename = f"ALERTAS_{campaign.slug}_{run.created_at.strftime('%Y-%m-%d')}.txt"

    return send_file(text_bytes, as_attachment=True, download_name=filename,
                     mimetype='text/plain')
