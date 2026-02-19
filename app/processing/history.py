"""Historical comparison using database."""

import json
import pandas as pd
from app.models import RunHistory


def get_last_history(campaign_id):
    """Get the most recent per-campaign history record.

    Only considers records saved under the per-campaign flow (marked with
    per_campaign=True). Records from the old combined flow are ignored to
    avoid false cross-campaign comparisons.
    """
    histories = RunHistory.query.filter_by(campaign_id=campaign_id)\
        .order_by(RunHistory.created_at.desc()).all()

    for history in histories:
        platforms = json.loads(history.platforms_json) if history.platforms_json else {}
        # Skip records from the old combined-upload flow (no per_campaign marker)
        if not platforms.get('per_campaign'):
            continue
        return {
            'platforms': platforms,
            'formats': json.loads(history.formats_json) if history.formats_json else {},
            'dates': json.loads(history.dates_json) if history.dates_json else {},
            'totals': json.loads(history.totals_json) if history.totals_json else {},
        }

    return None


def verificar_plataformas_faltantes(plataformas_actuales, campaign_id):
    """Compare current platforms against last historical run. Returns alerts."""
    alerts = []
    last = get_last_history(campaign_id)
    if not last:
        return alerts

    plataformas_previas = set(last['platforms'].get('plataformas', []))
    plataformas_actuales_set = set(plataformas_actuales)

    faltantes = plataformas_previas - plataformas_actuales_set
    for plat in faltantes:
        msg = f"PLATAFORMA FALTANTE: {plat} estaba en la ejecucion anterior pero no hay datos de ella hoy"
        alerts.append({'tipo': 'CRITICO', 'archivo': 'COMPARACION HISTORICA', 'mensaje': msg})

    return alerts


def verificar_datos_historicos(df_unified, campaign_id):
    """Check for missing formats and date range changes. Returns alerts."""
    alerts = []
    last = get_last_history(campaign_id)
    if not last:
        return alerts

    # Check missing formats per platform
    formatos_previos = last['formats']
    if formatos_previos:
        formatos_actuales = {}
        for plat in df_unified['PLATAFORMA'].unique():
            if plat and str(plat).strip():
                formatos = df_unified[df_unified['PLATAFORMA'] == plat]['FORMATO'].dropna().unique()
                formatos = [f for f in formatos if f and str(f).strip()]
                if formatos:
                    formatos_actuales[plat] = set(formatos)

        for plat, formatos_prev in formatos_previos.items():
            formatos_prev_set = set(formatos_prev)
            formatos_act_set = formatos_actuales.get(plat, set())
            for fmt in formatos_prev_set - formatos_act_set:
                msg = f"FORMATO FALTANTE: {fmt} de {plat} estaba en ejecucion anterior pero no aparece hoy"
                alerts.append({'tipo': 'CRITICO', 'archivo': 'COMPARACION HISTORICA', 'mensaje': msg})

    # Check date range changes per platform
    fechas_previas = last['dates']
    if fechas_previas and 'DIA' in df_unified.columns:
        for plat, fechas_prev in fechas_previas.items():
            fecha_min_prev = fechas_prev.get('fecha_min')
            if not fecha_min_prev:
                continue

            df_plat = df_unified[df_unified['PLATAFORMA'] == plat]
            if df_plat.empty:
                continue

            fechas_plat = pd.to_datetime(df_plat['DIA'], format='%d/%m/%y', errors='coerce').dropna()
            if fechas_plat.empty:
                continue

            fecha_min_actual = fechas_plat.min()
            fecha_min_prev_dt = pd.to_datetime(fecha_min_prev)
            dias_diferencia = (fecha_min_actual - fecha_min_prev_dt).days

            if dias_diferencia > 3:
                msg = (f"RANGO DE FECHAS REDUCIDO en {plat}: Datos inician "
                       f"{fecha_min_actual.strftime('%d/%m/%Y')}, pero antes iniciaban "
                       f"{fecha_min_prev_dt.strftime('%d/%m/%Y')} (faltan {dias_diferencia} dias)")
                alerts.append({'tipo': 'CRITICO', 'archivo': 'COMPARACION HISTORICA', 'mensaje': msg})

    # Check drastic metric drops
    totales_previos = last['totals']
    if totales_previos:
        totales_actuales = df_unified.groupby('PLATAFORMA').agg({
            'GASTO': 'sum', 'IMPRESIONES': 'sum'
        }).to_dict('index')

        for plat, metricas_prev in totales_previos.items():
            if plat in totales_actuales:
                gasto_prev = metricas_prev.get('GASTO', 0)
                gasto_act = totales_actuales[plat].get('GASTO', 0)
                if gasto_prev > 0:
                    variacion = ((gasto_act - gasto_prev) / gasto_prev) * 100
                    if variacion < -50:
                        msg = (f"CAIDA DRASTICA EN {plat}: Gasto cayo {abs(variacion):.0f}% "
                               f"(${gasto_prev:,.2f} -> ${gasto_act:,.2f})")
                        alerts.append({'tipo': 'ADVERTENCIA', 'archivo': 'COMPARACION HISTORICA', 'mensaje': msg})

    return alerts


def save_history(run_id, campaign_id, plataformas, df_unified):
    """Save processing history to database."""
    from app import db

    # per_campaign=True marks this record as coming from the per-campaign filtered
    # flow. Records without this flag (old combined-upload runs) are ignored by
    # get_last_history to prevent cross-campaign false comparisons.
    platforms_data = {
        'plataformas': list(plataformas),
        'per_campaign': True,
    }

    # Formats per platform
    formatos = {}
    for plat in df_unified['PLATAFORMA'].unique():
        if plat and str(plat).strip():
            fmts = df_unified[df_unified['PLATAFORMA'] == plat]['FORMATO'].dropna().unique()
            fmts = [f for f in fmts if f and str(f).strip()]
            if fmts:
                formatos[plat] = sorted(fmts)

    # Date ranges per platform
    dates_data = {}
    if 'DIA' in df_unified.columns:
        for plat in df_unified['PLATAFORMA'].unique():
            if plat and str(plat).strip():
                df_plat = df_unified[df_unified['PLATAFORMA'] == plat]
                fechas = pd.to_datetime(df_plat['DIA'], format='%d/%m/%y', errors='coerce').dropna()
                if not fechas.empty:
                    dates_data[plat] = {
                        'fecha_min': fechas.min().strftime('%Y-%m-%d'),
                        'fecha_max': fechas.max().strftime('%Y-%m-%d')
                    }

    # Totals per platform
    totales = df_unified.groupby('PLATAFORMA').agg({
        'GASTO': 'sum', 'IMPRESIONES': 'sum'
    }).to_dict('index')
    totals_data = {k: {m: round(v, 2) for m, v in vals.items()}
                   for k, vals in totales.items()}

    history = RunHistory(
        run_id=run_id,
        campaign_id=campaign_id,
        platforms_json=json.dumps(platforms_data),
        formats_json=json.dumps(formatos),
        dates_json=json.dumps(dates_data),
        totals_json=json.dumps(totals_data),
    )
    db.session.add(history)
    db.session.commit()
