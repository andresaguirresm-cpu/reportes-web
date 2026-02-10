from datetime import datetime
from app import db


class Campaign(db.Model):
    __tablename__ = 'campaigns'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), nullable=False, unique=True)
    brand = db.Column(db.String(100), default='')
    brand_display = db.Column(db.String(100), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    runs = db.relationship('ProcessingRun', backref='campaign', lazy='dynamic',
                           order_by='ProcessingRun.created_at.desc()')


class ProcessingRun(db.Model):
    __tablename__ = 'processing_runs'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    status = db.Column(db.String(20), default='processing')  # processing, completed, error
    total_files = db.Column(db.Integer, default=0)
    total_rows = db.Column(db.Integer, default=0)
    platforms = db.Column(db.Text, default='')  # comma-separated
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    rows = db.relationship('ReportRow', backref='run', lazy='dynamic')
    alerts = db.relationship('Alert', backref='run', lazy='dynamic')
    files = db.relationship('UploadedFile', backref='run', lazy='dynamic')
    history = db.relationship('RunHistory', backref='run', uselist=False)


class ReportRow(db.Model):
    __tablename__ = 'report_rows'

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('processing_runs.id'), nullable=False)
    marca = db.Column(db.String(100), default='')
    plataforma = db.Column(db.String(50), default='')
    campana = db.Column(db.String(500), default='')
    ad_group = db.Column(db.String(500), default='')
    etapa = db.Column(db.String(100), default='')
    compra = db.Column(db.String(100), default='')
    com = db.Column(db.String(100), default='')
    formato = db.Column(db.String(100), default='')
    audiencia = db.Column(db.String(200), default='')
    gasto = db.Column(db.Float, default=0)
    alcance = db.Column(db.Float, default=0)
    frecuencia = db.Column(db.Float, default=0)
    clics = db.Column(db.Float, default=0)
    views = db.Column(db.Float, default=0)
    impresiones = db.Column(db.Float, default=0)
    ctr = db.Column(db.Float, default=0)
    vtr = db.Column(db.Float, default=0)
    dia = db.Column(db.String(20), default='')

    def to_dict(self):
        return {
            'MARCA': self.marca or '',
            'PLATAFORMA': self.plataforma or '',
            'CAMPANA': self.campana or '',
            'AD GROUP': self.ad_group or '',
            'ETAPA': self.etapa or '',
            'COMPRA': self.compra or '',
            'COM': self.com or '',
            'FORMATO': self.formato or '',
            'AUDIENCIA': self.audiencia or '',
            'GASTO': self.gasto or 0,
            'ALCANCE': self.alcance or 0,
            'FRECUENCIA': self.frecuencia or 0,
            'CLICS': self.clics or 0,
            'VIEWS': self.views or 0,
            'IMPRESIONES': self.impresiones or 0,
            'CTR': self.ctr or 0,
            'VTR': self.vtr or 0,
            'DIA': self.dia or '',
        }


class Alert(db.Model):
    __tablename__ = 'alerts'

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('processing_runs.id'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # CRITICO, ERROR, ADVERTENCIA
    archivo = db.Column(db.String(300), default='')
    mensaje = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RunHistory(db.Model):
    __tablename__ = 'run_history'

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('processing_runs.id'), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    platforms_json = db.Column(db.Text, default='{}')
    formats_json = db.Column(db.Text, default='{}')
    dates_json = db.Column(db.Text, default='{}')
    totals_json = db.Column(db.Text, default='{}')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UploadedFile(db.Model):
    __tablename__ = 'uploaded_files'

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('processing_runs.id'), nullable=False)
    filename = db.Column(db.String(300), nullable=False)
    file_size = db.Column(db.Integer, default=0)
    platform_detected = db.Column(db.String(50), default='')
    rows_processed = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='pending')  # pending, processed, error
    error_message = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
