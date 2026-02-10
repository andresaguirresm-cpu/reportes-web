from flask import Blueprint, jsonify, abort
from app.models import ProcessingRun, ReportRow

api_bp = Blueprint('api', __name__)


@api_bp.route('/api/run/<int:run_id>/data')
def run_data(run_id):
    run = ProcessingRun.query.get_or_404(run_id)
    if run.status != 'completed':
        abort(404)

    rows = ReportRow.query.filter_by(run_id=run_id).all()
    data = [row.to_dict() for row in rows]
    return jsonify(data)


@api_bp.route('/api/run/<int:run_id>/summary')
def run_summary(run_id):
    run = ProcessingRun.query.get_or_404(run_id)
    if run.status != 'completed':
        abort(404)

    from app.models import Campaign, Alert
    campaign = Campaign.query.get(run.campaign_id)
    alerts = Alert.query.filter_by(run_id=run_id).all()

    return jsonify({
        'run_id': run.id,
        'campaign': campaign.name,
        'brand': campaign.brand_display or campaign.brand,
        'total_rows': run.total_rows,
        'total_files': run.total_files,
        'platforms': run.platforms.split(',') if run.platforms else [],
        'created_at': run.created_at.strftime('%Y-%m-%d %H:%M'),
        'alerts': {
            'criticos': sum(1 for a in alerts if a.tipo == 'CRITICO'),
            'errores': sum(1 for a in alerts if a.tipo == 'ERROR'),
            'advertencias': sum(1 for a in alerts if a.tipo == 'ADVERTENCIA'),
        }
    })
