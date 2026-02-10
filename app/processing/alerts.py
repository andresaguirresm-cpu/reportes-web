"""Alert system for data validation."""

import pandas as pd


COLUMNAS_CRITICAS = ['GASTO', 'IMPRESIONES', 'DIA']
COLUMNAS_IMPORTANTES = ['CLICS', 'VIEWS', 'CAMPANA']

COLUMNAS_EXCLUIDAS_POR_PLATAFORMA = {
    'GOOGLE': ['ALCANCE', 'FRECUENCIA'],
}


def verificar_campos_vacios(df):
    """Check for important fields with many empty values. Returns list of alert dicts."""
    alerts = []
    campos_importantes = {
        'AUDIENCIA': 'Necesario para segmentacion',
        'ETAPA': 'Necesario para analisis de funnel',
        'FORMATO': 'Necesario para analisis de creativos',
        'COMPRA': 'Necesario para analisis de costos',
        'COM': 'Necesario para analisis de mensajes'
    }

    total_filas = len(df)
    if total_filas == 0:
        return alerts

    for campo, descripcion in campos_importantes.items():
        if campo in df.columns:
            vacios = df[campo].isna() | (df[campo] == '') | (df[campo] == 'Sin definir')
            cantidad_vacios = vacios.sum()
            porcentaje_vacio = cantidad_vacios / total_filas

            if porcentaje_vacio >= 0.5:
                plataformas_afectadas = df[vacios]['PLATAFORMA'].unique().tolist()
                plataformas_str = ', '.join(str(p) for p in plataformas_afectadas)

                msg = (f"Campo {campo} vacio en {cantidad_vacios}/{total_filas} filas "
                       f"({porcentaje_vacio*100:.0f}%). Plataformas afectadas: {plataformas_str}. {descripcion}")

                tipo = 'CRITICO' if porcentaje_vacio >= 0.8 else 'ADVERTENCIA'
                alerts.append({'tipo': tipo, 'archivo': 'VALIDACION DE DATOS', 'mensaje': msg})

    return alerts


def verificar_columnas_criticas(columnas_encontradas, filename, platform):
    """Check for missing critical and important columns. Returns list of alert dicts."""
    alerts = []
    excluidas = COLUMNAS_EXCLUIDAS_POR_PLATAFORMA.get(platform, [])

    criticas_faltantes = [col for col in COLUMNAS_CRITICAS
                          if col not in columnas_encontradas and col not in excluidas]
    if criticas_faltantes:
        msg = f"COLUMNAS CRITICAS FALTANTES: {', '.join(criticas_faltantes)}"
        alerts.append({'tipo': 'CRITICO', 'archivo': filename, 'mensaje': msg})

    importantes_faltantes = [col for col in COLUMNAS_IMPORTANTES
                             if col not in columnas_encontradas and col not in excluidas]
    if importantes_faltantes:
        msg = f"Columnas importantes faltantes: {', '.join(importantes_faltantes)}"
        alerts.append({'tipo': 'ADVERTENCIA', 'archivo': filename, 'mensaje': msg})

    return alerts, len(criticas_faltantes) == 0
