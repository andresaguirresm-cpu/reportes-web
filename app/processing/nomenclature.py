"""Nomenclature parsing and platform detection."""

import re
import unicodedata


PLATFORM_KEYWORDS = {
    'META': ['thruplays', 'thru plays', 'frecuencia', 'alcance', 'nombre del conjunto de anuncios'],
    'GOOGLE': ['visualizaciones de trueview', 'trueview'],
    'TIKTOK': ['6-second video views', '2-second video views', 'video views at 25%',
               'video views at 50%', 'paid likes', 'paid shares', 'paid comments',
               '6-second focused views', '15-second focused views']
}

NOMENCLATURE_ALIASES = {
    'COMUNICACION': 'COM',
}

BRAND_NAMES = {
    'DC': 'DINERS CLUB',
    'VISA': 'VISA',
    'MC': 'MASTERCARD',
    'AMEX': 'AMERICAN EXPRESS',
}


def normalize(text):
    """Remove accents and convert to lowercase."""
    text = str(text).lower().strip()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return text


def detect_platform(df):
    """Detect platform based on file columns."""
    columns_lower = [normalize(col) for col in df.columns]
    columns_text = ' '.join(columns_lower)

    scores = {}
    for platform, keywords in PLATFORM_KEYWORDS.items():
        score = sum(1 for kw in keywords if normalize(kw) in columns_text)
        scores[platform] = score

    if max(scores.values()) > 0:
        return max(scores, key=scores.get)
    return 'DESCONOCIDO'


def parse_nomenclature(campaign_name):
    """Parse FIELD:VALUE nomenclature from campaign/ad group names."""
    parsed = {}
    segments = str(campaign_name).split('_')
    for segment in segments:
        match = re.match(r'^([A-Za-z\u00C0-\u00FF\u00D1\u00F1]+):(.+)$', segment.strip())
        if match:
            field = normalize(match.group(1)).upper()
            field = NOMENCLATURE_ALIASES.get(field, field)
            value = match.group(2).strip()
            if field not in parsed:
                parsed[field] = value
    return parsed


def detect_campaign_from_file(df):
    """Detect campaign name from DataFrame by parsing nomenclature."""
    campaign_col = None
    for col in df.columns:
        col_norm = normalize(str(col))
        if 'campaign' in col_norm or 'campana' in col_norm:
            campaign_col = col
            break

    if campaign_col is None:
        return None

    for _, row in df.iterrows():
        val = row[campaign_col]
        if not val or str(val).strip() == '':
            continue
        parsed = parse_nomenclature(str(val))
        if 'CAMPANA' in parsed and parsed['CAMPANA']:
            return parsed['CAMPANA']

    return None


def extract_campaign_info(df):
    """Extract campaign title and brand from unified dataset."""
    marca = ''
    campana_nombre = ''

    if 'MARCA' in df.columns:
        import pandas as pd
        marcas = df['MARCA'].replace('', pd.NA).dropna()
        if not marcas.empty:
            marca = marcas.value_counts().index[0]

    if 'CAMPANA' in df.columns:
        for campaign_name in df['CAMPANA'].dropna().unique():
            parsed = parse_nomenclature(str(campaign_name))
            if 'CAMPANA' in parsed and parsed['CAMPANA']:
                campana_nombre = parsed['CAMPANA']
                break

    if not campana_nombre and 'CAMPANA' in df.columns:
        nombres = df['CAMPANA'].dropna().unique()
        if len(nombres) > 0:
            nombre_base = min(nombres, key=len)
            limpio = re.sub(r'[A-Za-z\u00C0-\u00FF\u00D1\u00F1]+:[^_]+_?', '', str(nombre_base)).strip('_ ')
            if limpio:
                campana_nombre = limpio

    marca_display = BRAND_NAMES.get(marca.upper(), marca) if marca else ''

    if campana_nombre:
        titulo = campana_nombre.upper()
    elif marca:
        titulo = f"CAMPANA {marca.upper()}"
    else:
        titulo = "REPORTE DE PERFORMANCE"

    return {
        'titulo': titulo,
        'marca': marca,
        'marca_display': marca_display,
    }
