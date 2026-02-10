"""Metric calculations: CTR, VTR, deduplicated reach."""

import pandas as pd


def deduplicate_reach_list(reaches, new_reach_factor):
    """Deduplicate a list of reaches: Largest + (factor * Sum_of_Others)."""
    if len(reaches) == 0:
        return 0
    if len(reaches) == 1:
        return reaches[0]
    sorted_reaches = sorted(reaches, reverse=True)
    largest = sorted_reaches[0]
    others_sum = sum(sorted_reaches[1:])
    return largest + (others_sum * new_reach_factor)


def calcular_alcance_deduplicado(df, overlap_pct=80):
    """
    3-level reach deduplication (META and TIKTOK only).
    Level 1: Ad sets within same platform (same day)
    Level 2: Between platforms (same day)
    Level 3: Between days (accumulated)

    Google excluded because it doesn't provide reach metric.
    """
    df_reach = df[df['PLATAFORMA'].isin(['META', 'TIKTOK'])].copy()
    df_reach = df_reach[pd.to_numeric(df_reach['ALCANCE'], errors='coerce').fillna(0) > 0]

    if df_reach.empty:
        return {'final_reach': 0, 'frecuencia': 0, 'daily_evolution': []}

    new_reach_factor = (100 - overlap_pct) / 100

    df_reach['DIA_PARSED'] = pd.to_datetime(df_reach['DIA'], format='%d/%m/%y', errors='coerce')
    df_reach = df_reach.sort_values('DIA_PARSED')
    unique_dates = sorted(df_reach['DIA_PARSED'].dropna().unique())

    daily_reaches = []
    daily_evolution = []

    for date in unique_dates:
        day_data = df_reach[df_reach['DIA_PARSED'] == date]

        # Level 1: Deduplicate ad sets within each platform
        platform_reaches = {}
        for platform in day_data['PLATAFORMA'].unique():
            platform_data = day_data[day_data['PLATAFORMA'] == platform]
            ad_set_reaches = pd.to_numeric(platform_data['ALCANCE'], errors='coerce').fillna(0).tolist()
            platform_reaches[platform] = deduplicate_reach_list(ad_set_reaches, new_reach_factor)

        # Level 2: Deduplicate between platforms
        day_reach = deduplicate_reach_list(list(platform_reaches.values()), new_reach_factor)
        daily_reaches.append(day_reach)

        daily_evolution.append({
            'date': str(date.date()) if hasattr(date, 'date') else str(date),
            'day_reach': day_reach,
            'platforms': platform_reaches
        })

    # Level 3: Deduplicate between days (accumulated)
    accumulated = daily_reaches[0] if daily_reaches else 0
    for i in range(1, len(daily_reaches)):
        accumulated += daily_reaches[i] * new_reach_factor

    # Calculate frequency based on deduplicated reach
    total_imp_reach = pd.to_numeric(df_reach['IMPRESIONES'], errors='coerce').fillna(0).sum()
    frecuencia = total_imp_reach / accumulated if accumulated > 0 else 0

    return {
        'final_reach': accumulated,
        'frecuencia': round(frecuencia, 2),
        'overlap_pct': overlap_pct,
        'daily_evolution': daily_evolution
    }
