from flask import Blueprint, render_template, abort
from app.models import ProcessingRun, Campaign

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard/<int:run_id>')
def dashboard(run_id):
    run = ProcessingRun.query.get_or_404(run_id)
    if run.status != 'completed':
        abort(404)

    campaign = Campaign.query.get(run.campaign_id)

    return render_template('dashboard.html',
                           run=run,
                           campaign=campaign)
