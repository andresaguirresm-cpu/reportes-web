from flask import Blueprint, render_template
from app.models import Campaign

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    campaigns = Campaign.query.order_by(Campaign.updated_at.desc()).all()
    campaign_data = []
    for c in campaigns:
        last_run = c.runs.first()
        campaign_data.append({
            'campaign': c,
            'last_run': last_run,
        })
    return render_template('index.html', campaigns=campaign_data)
