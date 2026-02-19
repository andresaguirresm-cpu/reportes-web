from flask import Blueprint, render_template, abort, request
from app.models import ProcessingRun, Campaign, Alert

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard/<int:run_id>')
def dashboard(run_id):
    run = ProcessingRun.query.get_or_404(run_id)
    if run.status != 'completed':
        abort(404)

    campaign = Campaign.query.get(run.campaign_id)

    alerts_criticos = Alert.query.filter_by(run_id=run_id, tipo='CRITICO').all()
    alerts_errores = Alert.query.filter_by(run_id=run_id, tipo='ERROR').all()

    auto_print = request.args.get('print') == '1'
    session_id = request.args.get('session_id', '')

    return render_template('dashboard.html',
                           run=run,
                           campaign=campaign,
                           alerts_criticos=alerts_criticos,
                           alerts_errores=alerts_errores,
                           auto_print=auto_print,
                           session_id=session_id)
