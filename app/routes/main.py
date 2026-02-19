from flask import Blueprint, render_template, redirect, url_for
from app.models import Campaign, ProcessingRun

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return redirect(url_for('upload.upload_page'))


@main_bp.route('/campaigns')
def campaigns():
    campaigns = Campaign.query.order_by(Campaign.updated_at.desc()).all()
    campaign_data = []
    for c in campaigns:
        last_run = c.runs.first()
        campaign_data.append({
            'campaign': c,
            'last_run': last_run,
            'last_run_id': last_run.id if last_run else None,
        })
    return render_template('index.html', campaigns=campaign_data)
