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


def verificar_datos_historicos(agg_stats, campaign_id):
    """Check for missing formats and date range changes. Returns alerts.

    agg_stats: {platform: {formats: set, fecha_min, fecha_max, gasto, impresiones, views}}
    """
    alerts = []
    last = get_last_history(campaign_id)
    if not last:
        return alerts

    # Check missing formats per platform
    formatos_previos = last['formats']
    if formatos_previos:
        for plat, formatos_prev in formatos_previos.items():
            formatos_prev_set = set(formatos_prev)
            formatos_act_set = agg_stats.get(plat, {}).get('formats', set())
            for fmt in formatos_prev_set - formatos_act_set:
                msg = f"FORMATO FALTANTE: {fmt} de {plat} estaba en ejecucion anterior pero no aparece hoy"
                alerts.append({'tipo': 'CRITICO', 'archivo': 'COMPARACION HISTORICA', 'mensaje': msg})

    # Check date range changes per platform
    fechas_previas = last['dates']
    if fechas_previas:
        for plat, fechas_prev in fechas_previas.items():
            fecha_min_prev = fechas_prev.get('fecha_min')
            if not fecha_min_prev:
                continue

            fecha_min_actual = agg_stats.get(plat, {}).get('fecha_min')
            if fecha_min_actual is None:
                continue

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
        for plat, metricas_prev in totales_previos.items():
            if plat in agg_stats:
                gasto_prev = metricas_prev.get('GASTO', 0)
                gasto_act = agg_stats[plat].get('gasto', 0)
                if gasto_prev > 0:
                    variacion = ((gasto_act - gasto_prev) / gasto_prev) * 100
                    if variacion < -50:
                        msg = (f"CAIDA DRASTICA EN {plat}: Gasto cayo {abs(variacion):.0f}% "
                               f"(${gasto_prev:,.2f} -> ${gasto_act:,.2f})")
                        alerts.append({'tipo': 'ADVERTENCIA', 'archivo': 'COMPARACION HISTORICA', 'mensaje': msg})

                views_prev = metricas_prev.get('VIEWS', 0)
                views_act = agg_stats[plat].get('views', 0)
                if views_prev > 0 and views_act == 0:
                    msg = (f"VIEWS DESAPARECIERON EN {plat}: La ejecucion anterior tenia "
                           f"{views_prev:,.0f} views pero ahora es 0. "
                           f"Verifique que la columna de views este presente en el archivo.")
                    alerts.append({'tipo': 'CRITICO', 'archivo': 'COMPARACION HISTORICA', 'mensaje': msg})

    return alerts


def save_history(run_id, campaign_id, plataformas, agg_stats):
    """Save processing history to database.

    agg_stats: {platform: {formats: set, fecha_min, fecha_max, gasto, impresiones, views}}
    """
    from app import db

    platforms_data = {
        'plataformas': list(plataformas),
        'per_campaign': True,
    }

    # Formats per platform
    formatos = {
        plat: sorted(data['formats'])
        for plat, data in agg_stats.items()
        if plat and str(plat).strip() and data.get('formats')
    }

    # Date ranges per platform
    dates_data = {}
    for plat, data in agg_stats.items():
        if plat and str(plat).strip() and data.get('fecha_min'):
            dates_data[plat] = {
                'fecha_min': data['fecha_min'].strftime('%Y-%m-%d'),
                'fecha_max': data['fecha_max'].strftime('%Y-%m-%d') if data.get('fecha_max') else data['fecha_min'].strftime('%Y-%m-%d'),
            }

    # Totals per platform
    totals_data = {}
    for plat, data in agg_stats.items():
        if plat and str(plat).strip():
            entry = {
                'GASTO': round(data.get('gasto', 0), 2),
                'IMPRESIONES': round(data.get('impresiones', 0), 2),
            }
            if data.get('views', 0) > 0:
                entry['VIEWS'] = round(data['views'], 2)
            totals_data[plat] = entry

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
