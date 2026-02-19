"""Main processing engine: file loading, column mapping, data processing."""

import io
import re
import pandas as pd
from .nomenclature import normalize, detect_platform, parse_nomenclature, detect_campaign_from_file, extract_campaign_info
from .alerts import verificar_columnas_criticas, verificar_campos_vacios
from .metrics import calcular_alcance_deduplicado
from .history import verificar_plataformas_faltantes, verificar_datos_historicos, save_history

COLUMN_MAPPING = {
    'alcance': ['alcance', 'reach', 'unique users'],
    'gasto': ['importe gastado', 'amount spent', 'cost', 'costo', 'spend', 'coste',
              'importe gastado (usd)', 'total cost'],
    'frecuencia': ['frecuencia', 'frequency', 'avg frequency'],
    'clics': ['clics en el enlace', 'link clicks', 'clics', 'clicks',
              'clicks (destination)', 'all clicks', 'clicks (all)'],
    'views': ['thruplays', 'thru plays',
              'visualizaciones de trueview', 'vistas de trueview',
              'trueview views',
              '15-second focused views',
              'vistas', 'views', 'video views'],
    'impresiones': ['impresiones', 'impressions', 'impr.', 'imps'],
    'dia': ['dia', 'day', 'by day', 'date', 'fecha', 'reporting starts', 'dia', 'daa'],
    'campana': ['nombre de la campana', 'campaign name', 'campaign', 'campana',
                'campana', 'nombre de la campana'],
    'ad_group': ['nombre del conjunto de anuncios', 'ad set name', 'ad group name',
                 'grupo de anuncios', 'ad set', 'ad group']
}

OUTPUT_COLUMNS = ['MARCA', 'PLATAFORMA', 'CAMPANA', 'AD GROUP', 'ETAPA', 'COMPRA',
                  'COM', 'FORMATO', 'AUDIENCIA', 'GASTO', 'ALCANCE', 'FRECUENCIA',
                  'CLICS', 'VIEWS', 'IMPRESIONES', 'CTR', 'VTR', 'DIA']


def normalizar_nombre_campana(nombre):
    """Normalize campaign name for use as slug."""
    nombre = nombre.strip()
    nombre_limpio = nombre.lower().replace(' ', '_')
    nombre_limpio = re.sub(r'[^a-z0-9_\-]', '', nombre_limpio)
    return nombre_limpio


def detect_header_row(df_raw):
    """Detect header row by scanning for keyword matches."""
    keywords = ['campana', 'campaign', 'dia', 'day', 'clics', 'clicks',
                'impresiones', 'impressions', 'gasto', 'cost', 'coste']
    for idx, row in df_raw.iterrows():
        row_text = ' '.join([normalize(str(val)) for val in row.values if pd.notna(val)])
        matches = sum(1 for kw in keywords if kw in row_text)
        if matches >= 2:
            return idx
    return 0


def map_columns(df, filename, platform):
    """Map platform-specific column names to standard names."""
    df = df.copy()
    original_columns = list(df.columns)
    df.columns = [normalize(col) for col in df.columns]

    column_map = {}
    columnas_encontradas = []

    for std_name, variants in COLUMN_MAPPING.items():
        for col in df.columns:
            if col in [normalize(v) for v in variants]:
                column_map[col] = std_name.upper()
                columnas_encontradas.append(std_name.upper())
                break

    df = df.rename(columns=column_map)

    alerts, has_critical = verificar_columnas_criticas(columnas_encontradas, filename, platform)
    return df, has_critical, alerts


def process_file_from_memory(file_storage, filename):
    """Process an uploaded file (from memory). Returns (df_output, platform, alerts)."""
    alerts = []
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    is_csv = ext == 'csv'

    file_bytes = file_storage.read()
    file_storage.seek(0)

    if is_csv:
        # Detect encoding
        csv_encoding = 'utf-8'
        try:
            raw_text = file_bytes.decode('utf-8')
        except UnicodeDecodeError:
            csv_encoding = 'latin-1'
            raw_text = file_bytes.decode('latin-1')

        raw_lines = raw_text.split('\n')[:15]

        # Detect header row
        skiprows = 0
        keywords = ['campana', 'campaign', 'dia', 'day', 'clics', 'clicks',
                     'impresiones', 'impressions', 'gasto', 'cost', 'coste', 'impr', 'fecha', 'date']
        for i, line in enumerate(raw_lines):
            line_lower = normalize(line)
            matches = sum(1 for kw in keywords if kw in line_lower)
            if matches >= 2:
                skiprows = i
                break

        # Detect European number format
        sample_lines = '\n'.join(raw_lines[skiprows+1:skiprows+5])
        uses_european_format = bool(re.search(r'"[\d.]+,\d{2}"', sample_lines))

        csv_params = {'encoding': csv_encoding, 'skiprows': skiprows, 'on_bad_lines': 'skip'}
        if uses_european_format:
            csv_params['decimal'] = ','
            csv_params['thousands'] = '.'

        try:
            df = pd.read_csv(io.BytesIO(file_bytes), **csv_params)
        except Exception as e:
            alerts.append({'tipo': 'ERROR', 'archivo': filename, 'mensaje': f"No se pudo leer CSV: {e}"})
            raise
    else:
        # Excel
        try:
            df_raw = pd.read_excel(io.BytesIO(file_bytes), header=None, nrows=10)
        except Exception as e:
            alerts.append({'tipo': 'ERROR', 'archivo': filename, 'mensaje': f"No se pudo leer el archivo: {e}"})
            raise

        skiprows = detect_header_row(df_raw)
        df = pd.read_excel(io.BytesIO(file_bytes), skiprows=skiprows)

    # Detect platform BEFORE normalizing columns
    platform = detect_platform(df)
    if platform == 'DESCONOCIDO':
        alerts.append({'tipo': 'ADVERTENCIA', 'archivo': filename,
                       'mensaje': 'No se pudo detectar la plataforma automaticamente'})

    # Map columns
    df, has_critical, map_alerts = map_columns(df, filename, platform)
    alerts.extend(map_alerts)

    # Find campaign column
    campaign_col = None
    for col in df.columns:
        col_norm = normalize(col)
        if 'campaign' in col_norm or 'campana' in col_norm or col == 'CAMPANA':
            campaign_col = col
            break

    # Extract nomenclature metadata
    fields_to_extract = ['MARCA', 'PLATAFORMA', 'ETAPA', 'COMPRA', 'COM', 'FORMATO', 'AUDIENCIA']
    for field in fields_to_extract:
        df[field] = ''

    if campaign_col:
        for idx, row in df.iterrows():
            parsed = parse_nomenclature(row[campaign_col])
            for field in fields_to_extract:
                if field in parsed:
                    df.at[idx, field] = parsed[field]
        df['CAMPANA'] = df[campaign_col]

    # Parse ad group column for fallback metadata
    ad_group_col_for_parse = None
    for col in df.columns:
        col_norm = normalize(col)
        if any(kw in col_norm for kw in ['conjunto', 'ad set', 'ad group', 'ad_group', 'grupo']) or col == 'AD_GROUP':
            ad_group_col_for_parse = col
            break

    if ad_group_col_for_parse:
        for idx, row in df.iterrows():
            parsed_adgroup = parse_nomenclature(row[ad_group_col_for_parse])
            for field in fields_to_extract:
                if (pd.isna(df.at[idx, field]) or df.at[idx, field] == '') and field in parsed_adgroup:
                    df.at[idx, field] = parsed_adgroup[field]

    # Assign detected platform where empty
    if 'PLATAFORMA' not in df.columns:
        df['PLATAFORMA'] = platform
    else:
        df['PLATAFORMA'] = df['PLATAFORMA'].replace('', platform)
        df['PLATAFORMA'] = df['PLATAFORMA'].fillna(platform)

    # Find ad group column for output
    ad_group_col = None
    for col in df.columns:
        col_norm = normalize(col)
        if 'ad group' in col_norm or 'ad set' in col_norm or 'conjunto' in col_norm or col == 'AD_GROUP':
            ad_group_col = col
            break

    if ad_group_col:
        df['AD GROUP'] = df[ad_group_col]
    else:
        df['AD GROUP'] = ''

    # Calculate CTR and VTR
    if 'CLICS' in df.columns and 'IMPRESIONES' in df.columns:
        df['CTR'] = (pd.to_numeric(df['CLICS'], errors='coerce') /
                     pd.to_numeric(df['IMPRESIONES'], errors='coerce') * 100).round(2).fillna(0)
    else:
        df['CTR'] = 0

    if 'VIEWS' in df.columns and 'IMPRESIONES' in df.columns:
        df['VTR'] = (pd.to_numeric(df['VIEWS'], errors='coerce') /
                     pd.to_numeric(df['IMPRESIONES'], errors='coerce') * 100).round(2).fillna(0)
    else:
        df['VTR'] = 0

    # Standardize numeric formats
    numeric_cols = ['GASTO', 'ALCANCE', 'FRECUENCIA', 'CLICS', 'VIEWS', 'IMPRESIONES']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Format date — drop rows where date can't be parsed (they become "nan" and create ghost data points)
    if 'DIA' in df.columns:
        df['DIA'] = pd.to_datetime(df['DIA'], errors='coerce')
        df = df.dropna(subset=['DIA'])
        df['DIA'] = df['DIA'].dt.strftime('%d/%m/%y')

    # Ensure all output columns exist
    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = ''

    df_output = df[OUTPUT_COLUMNS].copy()
    return df_output, platform, alerts


def scan_campaigns_from_files(file_paths):
    """Quick read to detect campaigns without processing or saving to DB.

    Returns list of dicts: {nombre, plataformas, filas, fecha_min, fecha_max}
    """
    import os
    campaign_data = {}

    for file_path in file_paths:
        filename = os.path.basename(file_path)
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

        try:
            with open(file_path, 'rb') as f:
                file_bytes = f.read()

            if ext == 'csv':
                try:
                    raw_text = file_bytes.decode('utf-8')
                    encoding = 'utf-8'
                except UnicodeDecodeError:
                    raw_text = file_bytes.decode('latin-1')
                    encoding = 'latin-1'

                raw_lines = raw_text.split('\n')[:15]
                skiprows = 0
                kws = ['campana', 'campaign', 'dia', 'day', 'clics', 'clicks',
                       'impresiones', 'impressions', 'gasto', 'cost', 'coste']
                for i, line in enumerate(raw_lines):
                    if sum(1 for kw in kws if kw in normalize(line)) >= 2:
                        skiprows = i
                        break
                df = pd.read_csv(io.BytesIO(file_bytes), skiprows=skiprows,
                                 on_bad_lines='skip', encoding=encoding)
            else:
                df_raw = pd.read_excel(io.BytesIO(file_bytes), header=None, nrows=10)
                skiprows = detect_header_row(df_raw)
                df = pd.read_excel(io.BytesIO(file_bytes), skiprows=skiprows)

            platform = detect_platform(df)

            campaign_col = None
            for col in df.columns:
                col_norm = normalize(str(col))
                if 'campaign' in col_norm or 'campana' in col_norm:
                    campaign_col = col
                    break

            date_col = None
            for col in df.columns:
                col_norm = normalize(str(col))
                if col_norm in ['dia', 'day', 'date', 'fecha']:
                    date_col = col
                    break

            if campaign_col is None:
                continue

            for raw_name in df[campaign_col].dropna().unique():
                raw_name = str(raw_name).strip()
                if not raw_name:
                    continue

                parsed = parse_nomenclature(raw_name)
                # Skip campaigns with legacy nomenclature (no CAMPO:VALOR segments found)
                if not parsed:
                    continue
                display_name = parsed.get('CAMPANA', raw_name)

                if display_name not in campaign_data:
                    campaign_data[display_name] = {
                        'nombre': display_name,
                        'plataformas': set(),
                        'filas': 0,
                        'fechas': [],
                    }

                rows_for_name = df[df[campaign_col] == raw_name]
                campaign_data[display_name]['plataformas'].add(platform)
                campaign_data[display_name]['filas'] += len(rows_for_name)

                if date_col:
                    dates = pd.to_datetime(rows_for_name[date_col], errors='coerce').dropna()
                    campaign_data[display_name]['fechas'].extend(dates.tolist())

        except Exception:
            continue

    result = []
    for display_name, data in campaign_data.items():
        fecha_min = min(data['fechas']).strftime('%d/%m/%y') if data['fechas'] else None
        fecha_max = max(data['fechas']).strftime('%d/%m/%y') if data['fechas'] else None
        result.append({
            'nombre': display_name,
            'plataformas': sorted(data['plataformas']),
            'filas': data['filas'],
            'fecha_min': fecha_min,
            'fecha_max': fecha_max,
        })

    return result


def process_uploaded_files(file_storages, run_id, campaign_id, campaign_filter=None):
    """Process multiple uploaded files and save results to database.

    Args:
        file_storages: list of (file_storage, filename) tuples
        run_id: ProcessingRun.id
        campaign_id: Campaign.id

    Returns:
        dict with processing results
    """
    from app import db
    from app.models import ProcessingRun, ReportRow, Alert, UploadedFile

    run = ProcessingRun.query.get(run_id)
    all_data = []
    all_alerts = []
    platforms_found = []

    for file_storage, filename in file_storages:
        uploaded = UploadedFile.query.filter_by(run_id=run_id, filename=filename).first()

        try:
            df, platform, file_alerts = process_file_from_memory(file_storage, filename)

            # Filter by campaign display name if specified
            if campaign_filter and 'CAMPANA' in df.columns:
                def _get_display(raw):
                    p = parse_nomenclature(str(raw))
                    return p.get('CAMPANA', str(raw).strip())
                mask = df['CAMPANA'].apply(_get_display) == campaign_filter
                df = df[mask].copy()
                if len(df) == 0:
                    if uploaded:
                        uploaded.platform_detected = platform
                        uploaded.rows_processed = 0
                        uploaded.status = 'processed'
                    continue

            all_data.append(df)
            all_alerts.extend(file_alerts)
            platforms_found.append(platform)

            if uploaded:
                uploaded.platform_detected = platform
                uploaded.rows_processed = len(df)
                uploaded.status = 'processed'
        except Exception as e:
            all_alerts.append({'tipo': 'ERROR', 'archivo': filename, 'mensaje': str(e)})
            if uploaded:
                uploaded.status = 'error'
                uploaded.error_message = str(e)

    if not all_data:
        run.status = 'error'
        db.session.commit()
        return {'error': 'No se pudo procesar ningun archivo'}

    # Unify all dataframes
    df_unified = pd.concat(all_data, ignore_index=True)

    # Historical comparisons
    hist_alerts = verificar_plataformas_faltantes(platforms_found, campaign_id)
    all_alerts.extend(hist_alerts)

    hist_data_alerts = verificar_datos_historicos(df_unified, campaign_id)
    all_alerts.extend(hist_data_alerts)

    # Validate empty fields
    empty_alerts = verificar_campos_vacios(df_unified)
    all_alerts.extend(empty_alerts)

    # Calculate deduplicated reach
    alcance_dedup = calcular_alcance_deduplicado(df_unified, overlap_pct=72)

    # Extract campaign info
    info_campana = extract_campaign_info(df_unified)

    # Save report rows to database
    for _, row in df_unified.iterrows():
        report_row = ReportRow(
            run_id=run_id,
            marca=str(row.get('MARCA', '') or ''),
            plataforma=str(row.get('PLATAFORMA', '') or ''),
            campana=str(row.get('CAMPANA', '') or ''),
            ad_group=str(row.get('AD GROUP', '') or ''),
            etapa=str(row.get('ETAPA', '') or ''),
            compra=str(row.get('COMPRA', '') or ''),
            com=str(row.get('COM', '') or ''),
            formato=str(row.get('FORMATO', '') or ''),
            audiencia=str(row.get('AUDIENCIA', '') or ''),
            gasto=float(row.get('GASTO', 0) or 0),
            alcance=float(row.get('ALCANCE', 0) or 0),
            frecuencia=float(row.get('FRECUENCIA', 0) or 0),
            clics=float(row.get('CLICS', 0) or 0),
            views=float(row.get('VIEWS', 0) or 0),
            impresiones=float(row.get('IMPRESIONES', 0) or 0),
            ctr=float(row.get('CTR', 0) or 0),
            vtr=float(row.get('VTR', 0) or 0),
            dia=str(row.get('DIA', '') or ''),
        )
        db.session.add(report_row)

    # Save alerts to database
    for alert_data in all_alerts:
        alert = Alert(
            run_id=run_id,
            tipo=alert_data['tipo'],
            archivo=alert_data.get('archivo', ''),
            mensaje=alert_data.get('mensaje', ''),
        )
        db.session.add(alert)

    # Update run metadata
    run.status = 'completed'
    run.total_files = len(file_storages)
    run.total_rows = len(df_unified)
    run.platforms = ','.join(sorted(set(platforms_found)))

    # Update campaign info
    from app.models import Campaign
    campaign = Campaign.query.get(campaign_id)
    if campaign and info_campana:
        if info_campana.get('marca'):
            campaign.brand = info_campana['marca']
        if info_campana.get('marca_display'):
            campaign.brand_display = info_campana['marca_display']

    db.session.commit()

    # Save history
    save_history(run_id, campaign_id, platforms_found, df_unified)

    return {
        'run_id': run_id,
        'total_rows': len(df_unified),
        'total_files': len(file_storages),
        'platforms': list(set(platforms_found)),
        'alerts_count': len(all_alerts),
        'alcance_dedup': alcance_dedup,
        'info_campana': info_campana,
    }
