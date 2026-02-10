/* Smart Reports - Dashboard JavaScript (Chart.js) */
if (typeof ChartDataLabels !== 'undefined') Chart.register(ChartDataLabels);

let rawData = [];
let charts = {};

const colors = {
    cyan1: '#0077b6', cyan2: '#00b4d8', cyan3: '#48cae4',
    blue1: '#0096c7', blue2: '#023e8a', blue3: '#90e0ef',
    cyan1a: 'rgba(0, 119, 182, 0.85)', cyan2a: 'rgba(0, 180, 216, 0.75)',
    cyan3a: 'rgba(72, 202, 228, 0.65)', blue1a: 'rgba(0, 150, 199, 0.55)',
    blue2a: 'rgba(2, 62, 138, 0.45)', blue3a: 'rgba(144, 224, 239, 0.4)'
};

const formatColors = [
    { border: '#10b981', bg: 'rgba(16, 185, 129, 0.15)' },
    { border: '#f59e0b', bg: 'rgba(245, 158, 11, 0.15)' },
    { border: '#8b5cf6', bg: 'rgba(139, 92, 246, 0.15)' },
    { border: '#ef4444', bg: 'rgba(239, 68, 68, 0.15)' },
    { border: '#06b6d4', bg: 'rgba(6, 182, 212, 0.15)' },
    { border: '#ec4899', bg: 'rgba(236, 72, 153, 0.15)' },
    { border: '#84cc16', bg: 'rgba(132, 204, 22, 0.15)' },
    { border: '#6366f1', bg: 'rgba(99, 102, 241, 0.15)' }
];

const platformColors = {
    'META': { border: '#1877f2', bg: 'rgba(24, 119, 242, 0.15)' },
    'GOOGLE': { border: '#ea4335', bg: 'rgba(234, 67, 53, 0.15)' },
    'TIKTOK': { border: '#000000', bg: 'rgba(0, 0, 0, 0.1)' },
    'DESCONOCIDO': { border: '#6b7280', bg: 'rgba(107, 114, 128, 0.15)' }
};

document.addEventListener('DOMContentLoaded', function() {
    fetch(DATA_URL)
        .then(r => r.json())
        .then(data => {
            rawData = data;
            init();
            document.getElementById('loadingOverlay').style.display = 'none';
        })
        .catch(err => {
            console.error('Error loading data:', err);
            document.getElementById('loadingOverlay').innerHTML =
                '<p style="color:#ef4444">Error cargando datos</p>';
        });
});

function init() {
    populateFilters();
    setupFilterListeners();
    updateDashboard();
}

function populateFilters() {
    const fields = {
        'filterPlataforma': 'PLATAFORMA', 'filterEtapa': 'ETAPA',
        'filterCompra': 'COMPRA', 'filterFormato': 'FORMATO', 'filterAudiencia': 'AUDIENCIA'
    };
    Object.entries(fields).forEach(([selectId, field]) => {
        const values = [...new Set(rawData.map(d => d[field]))].filter(Boolean).sort();
        const select = document.getElementById(selectId);
        values.forEach(v => {
            const opt = document.createElement('option');
            opt.value = v; opt.textContent = v;
            select.appendChild(opt);
        });
    });
}

function setupFilterListeners() {
    ['filterPlataforma', 'filterEtapa', 'filterCompra', 'filterFormato', 'filterAudiencia'].forEach(id => {
        document.getElementById(id).addEventListener('change', updateDashboard);
    });
}

function getFilteredData() {
    const filters = {
        PLATAFORMA: document.getElementById('filterPlataforma').value,
        ETAPA: document.getElementById('filterEtapa').value,
        COMPRA: document.getElementById('filterCompra').value,
        FORMATO: document.getElementById('filterFormato').value,
        AUDIENCIA: document.getElementById('filterAudiencia').value
    };
    return rawData.filter(d => {
        for (let [key, val] of Object.entries(filters)) {
            if (val && d[key] !== val) return false;
        }
        return true;
    });
}

function updateDashboard() {
    const data = getFilteredData();
    updateKPIs(data);
    updateAllCharts(data);
    updateTable(data);
}

function dedupReachList(reaches, factor) {
    if (reaches.length === 0) return 0;
    if (reaches.length === 1) return reaches[0];
    const sorted = reaches.slice().sort((a, b) => b - a);
    return sorted[0] + sorted.slice(1).reduce((s, v) => s + v, 0) * factor;
}

function calcAlcanceDedup(data, overlapPct) {
    const factor = (100 - overlapPct) / 100;
    const reachData = data.filter(d => ['META', 'TIKTOK'].includes(d.PLATAFORMA) && (d.ALCANCE || 0) > 0);
    if (reachData.length === 0) return { alcance: 0, frecuencia: 0 };
    const days = [...new Set(reachData.map(d => d.DIA))].sort();
    const dailyReaches = [];
    for (const day of days) {
        const dayData = reachData.filter(d => d.DIA === day);
        const platforms = [...new Set(dayData.map(d => d.PLATAFORMA))];
        const platReaches = platforms.map(p => {
            const vals = dayData.filter(d => d.PLATAFORMA === p).map(d => d.ALCANCE || 0);
            return dedupReachList(vals, factor);
        });
        dailyReaches.push(dedupReachList(platReaches, factor));
    }
    let accumulated = dailyReaches[0] || 0;
    for (let i = 1; i < dailyReaches.length; i++) { accumulated += dailyReaches[i] * factor; }
    const totalImp = reachData.reduce((s, d) => s + (d.IMPRESIONES || 0), 0);
    return { alcance: accumulated, frecuencia: accumulated > 0 ? totalImp / accumulated : 0 };
}

function updateKPIs(data) {
    const gasto = data.reduce((s, d) => s + (d.GASTO || 0), 0);
    const clics = data.reduce((s, d) => s + (d.CLICS || 0), 0);
    const imp = data.reduce((s, d) => s + (d.IMPRESIONES || 0), 0);
    const views = data.reduce((s, d) => s + (d.VIEWS || 0), 0);
    const dedup = calcAlcanceDedup(data, 72);
    const ctr = imp > 0 ? (clics / imp * 100) : 0;
    const vtr = imp > 0 ? (views / imp * 100) : 0;
    document.getElementById('kpiGasto').textContent = '$' + formatNum(gasto.toFixed(2));
    document.getElementById('kpiImpresiones').textContent = formatNum(imp);
    document.getElementById('kpiClics').textContent = formatNum(clics);
    document.getElementById('kpiViews').textContent = formatNum(views);
    document.getElementById('kpiAlcance').textContent = formatNum(Math.round(dedup.alcance));
    document.getElementById('kpiFrecuencia').textContent = dedup.frecuencia.toFixed(2);
    document.getElementById('kpiCTR').textContent = ctr.toFixed(2) + '%';
    document.getElementById('kpiVTR').textContent = vtr.toFixed(2) + '%';
}

function formatNum(n) { return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ","); }

function updateAllCharts(data) {
    const compraMap = getCompraByFormato(data);
    createBarChart('chartGastoPlataforma', groupBy(data, 'PLATAFORMA', 'GASTO'), 'Gasto');
    createDoughnutChart('chartGastoAudiencia', groupBy(data, 'AUDIENCIA', 'GASTO'));
    createDoughnutChart('chartGastoCompra', groupBy(data, 'COMPRA', 'GASTO'));
    createBarChart('chartImpPlataforma', groupBy(data, 'PLATAFORMA', 'IMPRESIONES'), 'Impresiones');
    createBarChart('chartImpFormato', groupBy(data, 'FORMATO', 'IMPRESIONES'), 'Impresiones', compraMap);
    createDoughnutChart('chartImpAudiencia', groupBy(data, 'AUDIENCIA', 'IMPRESIONES'));
    createBarChart('chartClicsPlataforma', groupBy(data, 'PLATAFORMA', 'CLICS'), 'Clics');
    createBarChart('chartClicsFormato', groupBy(data, 'FORMATO', 'CLICS'), 'Clics', compraMap);
    createDoughnutChart('chartClicsAudiencia', groupBy(data, 'AUDIENCIA', 'CLICS'));
    createBarChart('chartViewsPlataforma', groupBy(data, 'PLATAFORMA', 'VIEWS'), 'Views');
    createBarChart('chartViewsFormato', groupBy(data, 'FORMATO', 'VIEWS'), 'Views', compraMap);
    createDoughnutChart('chartViewsAudiencia', groupBy(data, 'AUDIENCIA', 'VIEWS'));
    createBarChart('chartAlcancePlataforma', groupBy(data, 'PLATAFORMA', 'ALCANCE'), 'Alcance');
    createDoughnutChart('chartAlcanceAudiencia', groupBy(data, 'AUDIENCIA', 'ALCANCE'));
    createBarChart('chartFrecuenciaPlataforma', groupByAvg(data, 'PLATAFORMA', 'FRECUENCIA'), 'Frecuencia');
    createBarChart('chartEfPlatImp', groupBy(data, 'PLATAFORMA', 'IMPRESIONES'), 'Impresiones');
    createBarChart('chartEfPlatCTR', groupByAvg(data, 'PLATAFORMA', 'CTR'), 'CTR %');
    createBarChart('chartEfPlatVTR', groupByAvg(data, 'PLATAFORMA', 'VTR'), 'VTR %');
    createBarChart('chartEfEtapaImp', groupBy(data, 'ETAPA', 'IMPRESIONES'), 'Impresiones');
    createBarChart('chartEfEtapaCTR', groupByAvg(data, 'ETAPA', 'CTR'), 'CTR %');
    createBarChart('chartEfEtapaVTR', groupByAvg(data, 'ETAPA', 'VTR'), 'VTR %');
    createBarChart('chartEfCompraImp', groupBy(data, 'COMPRA', 'IMPRESIONES'), 'Impresiones');
    createBarChart('chartEfCompraCTR', groupByAvg(data, 'COMPRA', 'CTR'), 'CTR %');
    createBarChart('chartEfCompraVTR', groupByAvg(data, 'COMPRA', 'VTR'), 'VTR %');
    createBarChart('chartEfFmtImp', groupBy(data, 'FORMATO', 'IMPRESIONES'), 'Impresiones', compraMap);
    createBarChart('chartEfFmtCTR', groupByAvg(data, 'FORMATO', 'CTR'), 'CTR %', compraMap);
    createBarChart('chartEfFmtVTR', groupByAvg(data, 'FORMATO', 'VTR'), 'VTR %', compraMap);
    createBarChart('chartEfAudImp', groupBy(data, 'AUDIENCIA', 'IMPRESIONES'), 'Impresiones');
    createBarChart('chartEfAudCTR', groupByAvg(data, 'AUDIENCIA', 'CTR'), 'CTR %');
    createBarChart('chartEfAudVTR', groupByAvg(data, 'AUDIENCIA', 'VTR'), 'VTR %');
    createBarChart('chartEfComImp', groupBy(data, 'COM', 'IMPRESIONES'), 'Impresiones');
    createBarChart('chartEfComCTR', groupByAvg(data, 'COM', 'CTR'), 'CTR %');
    createBarChart('chartEfComVTR', groupByAvg(data, 'COM', 'VTR'), 'VTR %');

    const daily = getDailyData(data);
    createSingleLineChart('chartEvoGasto', daily, 'gasto', 'Inversion ($)');
    createDualLineChart('chartEvoImpresiones', daily, 'imp', 'Impresiones', 'frec', 'Frecuencia', '');
    createDualLineChart('chartEvoClics', daily, 'clics', 'Clics', 'ctr', 'CTR', '%');
    createDualLineChart('chartEvoViews', daily, 'views', 'Video Views', 'vtr', 'VTR', '%');

    const dailyByPlat = getDailyDataByPlatform(data);
    createPlatformLineChart('chartEvoGastoPlat', dailyByPlat, 'gasto', 'Inversion ($)', true);
    createPlatformLineChart('chartEvoImpPlat', dailyByPlat, 'imp', 'Impresiones', false);
    createPlatformLineChart('chartEvoClicsPlat', dailyByPlat, 'clics', 'Clics', false);
    createPlatformLineChart('chartEvoViewsPlat', dailyByPlat, 'views', 'Video Views', false);

    const dailyByFmt = getDailyDataByFormat(data);
    createFormatLineChart('chartEvoGastoFmt', dailyByFmt, 'gasto', 'Inversion ($)', true);
    createFormatLineChart('chartEvoImpFmt', dailyByFmt, 'imp', 'Impresiones', false);
    createFormatLineChart('chartEvoClicsFmt', dailyByFmt, 'clics', 'Clics', false);
    createFormatLineChart('chartEvoViewsFmt', dailyByFmt, 'views', 'Video Views', false);
}

function createBarChart(canvasId, grouped, label, subtitles) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    if (charts[canvasId]) charts[canvasId].destroy();
    const rawLabels = Object.keys(grouped);
    const labels = subtitles ? rawLabels.map(l => subtitles[l] ? [l, subtitles[l]] : l) : rawLabels;
    const data = Object.values(grouped);
    const total = data.reduce((s, v) => s + v, 0);
    const bgColors = [colors.cyan1a, colors.cyan2a, colors.cyan3a, colors.blue1a, colors.blue2a, colors.blue3a];
    const borderColors = [colors.cyan1, colors.cyan2, colors.cyan3, colors.blue1, colors.blue2, colors.blue3];
    charts[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: { labels: labels, datasets: [{ label: label, data: data, backgroundColor: bgColors.slice(0, labels.length), borderColor: borderColors.slice(0, labels.length), borderWidth: 2, borderRadius: 6 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, datalabels: { color: '#1e293b', anchor: 'end', align: 'top', font: { size: 10, weight: 'bold', family: 'Orbitron' }, formatter: (value) => { if (label.includes('%')) return value.toFixed(2) + '%'; const pct = total > 0 ? (value / total * 100).toFixed(1) : 0; return pct + '%'; } } }, scales: { x: { ticks: { color: '#64748b', font: { size: 9 }, maxRotation: 0, autoSkip: false }, grid: { display: false } }, y: { ticks: { color: 'rgba(100, 116, 139, 0.7)', font: { size: 9 } }, grid: { color: 'rgba(0, 0, 0, 0.08)' } } } }
    });
}

function createDoughnutChart(canvasId, grouped) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    if (charts[canvasId]) charts[canvasId].destroy();
    const labels = Object.keys(grouped); const data = Object.values(grouped);
    const total = data.reduce((s, v) => s + v, 0);
    const bgColors = [colors.cyan1a, colors.cyan2a, colors.cyan3a, colors.blue1a, colors.blue2a, colors.blue3a];
    const borderColors = [colors.cyan1, colors.cyan2, colors.cyan3, colors.blue1, colors.blue2, colors.blue3];
    charts[canvasId] = new Chart(ctx, {
        type: 'doughnut',
        data: { labels: labels, datasets: [{ data: data, backgroundColor: bgColors.slice(0, labels.length), borderColor: borderColors.slice(0, labels.length), borderWidth: 2 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { color: '#64748b', font: { size: 10 }, boxWidth: 12, padding: 8 } }, datalabels: { color: '#1e293b', font: { size: 11, weight: 'bold', family: 'Orbitron' }, formatter: (value) => { const pct = total > 0 ? (value / total * 100).toFixed(1) : 0; return pct + '%'; } } } }
    });
}

function getDailyData(data) {
    const daily = {};
    data.forEach(d => {
        const day = d.DIA || '';
        if (!day || day === 'nan' || day === 'NaT') return;
        if (!daily[day]) daily[day] = { gasto: 0, imp: 0, clics: 0, views: 0, frecSum: 0, frecCount: 0 };
        daily[day].gasto += (d.GASTO || 0);
        daily[day].imp += (d.IMPRESIONES || 0);
        daily[day].clics += (d.CLICS || 0);
        daily[day].views += (d.VIEWS || 0);
        if (d.FRECUENCIA > 0) { daily[day].frecSum += d.FRECUENCIA; daily[day].frecCount += 1; }
    });
    const sorted = Object.keys(daily).sort((a, b) => {
        const [da, ma, ya] = a.split('/').map(Number);
        const [db, mb, yb] = b.split('/').map(Number);
        return (ya * 10000 + ma * 100 + da) - (yb * 10000 + mb * 100 + db);
    });
    return sorted.map(day => ({
        label: day.substring(0, 5),
        gasto: parseFloat(daily[day].gasto.toFixed(2)),
        imp: daily[day].imp,
        clics: daily[day].clics,
        views: daily[day].views,
        ctr: daily[day].imp > 0 ? (daily[day].clics / daily[day].imp * 100) : 0,
        vtr: daily[day].imp > 0 ? (daily[day].views / daily[day].imp * 100) : 0,
        frec: daily[day].frecCount > 0 ? daily[day].frecSum / daily[day].frecCount : 0
    }));
}

function getDailyDataByPlatform(data) {
    const platforms = [...new Set(data.map(d => d.PLATAFORMA))].filter(Boolean).sort();
    const dailyByPlat = {};
    platforms.forEach(p => { dailyByPlat[p] = {}; });
    data.forEach(d => {
        const day = d.DIA || '';
        const plat = d.PLATAFORMA || '';
        if (!day || !plat) return;
        if (!dailyByPlat[plat][day]) dailyByPlat[plat][day] = { gasto: 0, imp: 0, clics: 0, views: 0 };
        dailyByPlat[plat][day].gasto += (d.GASTO || 0);
        dailyByPlat[plat][day].imp += (d.IMPRESIONES || 0);
        dailyByPlat[plat][day].clics += (d.CLICS || 0);
        dailyByPlat[plat][day].views += (d.VIEWS || 0);
    });
    const allDays = [...new Set(data.map(d => d.DIA))].filter(Boolean).sort((a, b) => {
        const [da, ma, ya] = a.split('/').map(Number);
        const [db, mb, yb] = b.split('/').map(Number);
        return (ya * 10000 + ma * 100 + da) - (yb * 10000 + mb * 100 + db);
    });
    const result = {};
    platforms.forEach(p => {
        result[p] = allDays.map(day => ({
            label: day.substring(0, 5),
            gasto: dailyByPlat[p][day] ? parseFloat(dailyByPlat[p][day].gasto.toFixed(2)) : 0,
            imp: dailyByPlat[p][day] ? dailyByPlat[p][day].imp : 0,
            clics: dailyByPlat[p][day] ? dailyByPlat[p][day].clics : 0,
            views: dailyByPlat[p][day] ? dailyByPlat[p][day].views : 0
        }));
    });
    result._labels = allDays.map(d => d.substring(0, 5));
    result._platforms = platforms;
    return result;
}

function getDailyDataByFormat(data) {
    const formats = [...new Set(data.map(d => d.FORMATO))].filter(Boolean).sort();
    const dailyByFmt = {};
    formats.forEach(f => { dailyByFmt[f] = {}; });
    data.forEach(d => {
        const day = d.DIA || '';
        const fmt = d.FORMATO || '';
        if (!day || !fmt) return;
        if (!dailyByFmt[fmt][day]) dailyByFmt[fmt][day] = { gasto: 0, imp: 0, clics: 0, views: 0 };
        dailyByFmt[fmt][day].gasto += (d.GASTO || 0);
        dailyByFmt[fmt][day].imp += (d.IMPRESIONES || 0);
        dailyByFmt[fmt][day].clics += (d.CLICS || 0);
        dailyByFmt[fmt][day].views += (d.VIEWS || 0);
    });
    const allDays = [...new Set(data.map(d => d.DIA))].filter(Boolean).sort((a, b) => {
        const [da, ma, ya] = a.split('/').map(Number);
        const [db, mb, yb] = b.split('/').map(Number);
        return (ya * 10000 + ma * 100 + da) - (yb * 10000 + mb * 100 + db);
    });
    const result = {};
    formats.forEach(f => {
        result[f] = allDays.map(day => ({
            label: day.substring(0, 5),
            gasto: dailyByFmt[f][day] ? parseFloat(dailyByFmt[f][day].gasto.toFixed(2)) : 0,
            imp: dailyByFmt[f][day] ? dailyByFmt[f][day].imp : 0,
            clics: dailyByFmt[f][day] ? dailyByFmt[f][day].clics : 0,
            views: dailyByFmt[f][day] ? dailyByFmt[f][day].views : 0
        }));
    });
    result._labels = allDays.map(d => d.substring(0, 5));
    result._formats = formats;
    return result;
}

function getPlatformColor(platform) {
    return platformColors[platform] || { border: '#8b5cf6', bg: 'rgba(139, 92, 246, 0.15)' };
}

function createPlatformLineChart(canvasId, dailyByPlat, metricKey, metricLabel, isCurrency) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    if (charts[canvasId]) charts[canvasId].destroy();
    const labels = dailyByPlat._labels || [];
    const platforms = dailyByPlat._platforms || [];
    const datasets = platforms.map(p => {
        const pColor = getPlatformColor(p);
        return {
            label: p,
            data: (dailyByPlat[p] || []).map(d => d[metricKey]),
            borderColor: pColor.border, backgroundColor: pColor.bg,
            borderWidth: 2, pointRadius: 3, pointBackgroundColor: pColor.border,
            fill: false, tension: 0.3
        };
    });
    charts[canvasId] = new Chart(ctx, {
        type: 'line',
        data: { labels: labels, datasets: datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'top', labels: { color: '#1e293b', font: { size: 10 }, boxWidth: 12, padding: 15 } },
                datalabels: { display: false }
            },
            scales: {
                x: { ticks: { color: '#64748b', font: { size: 9 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 15 }, grid: { display: false } },
                y: { ticks: { color: '#1e293b', font: { size: 9 }, callback: (v) => isCurrency ? '$' + formatNum(v.toFixed(0)) : formatNum(v) }, grid: { color: 'rgba(0, 0, 0, 0.06)' }, title: { display: true, text: metricLabel, color: '#1e293b', font: { size: 10 } } }
            }
        }
    });
}

function createFormatLineChart(canvasId, dailyByFmt, metricKey, metricLabel, isCurrency) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    if (charts[canvasId]) charts[canvasId].destroy();
    const labels = dailyByFmt._labels || [];
    const formats = dailyByFmt._formats || [];
    const datasets = formats.map((f, idx) => {
        const fColor = formatColors[idx % formatColors.length];
        return {
            label: f,
            data: (dailyByFmt[f] || []).map(d => d[metricKey]),
            borderColor: fColor.border, backgroundColor: fColor.bg,
            borderWidth: 2, pointRadius: 3, pointBackgroundColor: fColor.border,
            fill: false, tension: 0.3
        };
    });
    charts[canvasId] = new Chart(ctx, {
        type: 'line',
        data: { labels: labels, datasets: datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'top', labels: { color: '#1e293b', font: { size: 10 }, boxWidth: 12, padding: 15 } },
                datalabels: { display: false }
            },
            scales: {
                x: { ticks: { color: '#64748b', font: { size: 9 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 15 }, grid: { display: false } },
                y: { ticks: { color: '#1e293b', font: { size: 9 }, callback: (v) => isCurrency ? '$' + formatNum(v.toFixed(0)) : formatNum(v) }, grid: { color: 'rgba(0, 0, 0, 0.06)' }, title: { display: true, text: metricLabel, color: '#1e293b', font: { size: 10 } } }
            }
        }
    });
}

function createSingleLineChart(canvasId, dailyData, metricKey, metricLabel) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    if (charts[canvasId]) charts[canvasId].destroy();
    const labels = dailyData.map(d => d.label);
    const data1 = dailyData.map(d => d[metricKey]);
    charts[canvasId] = new Chart(ctx, {
        type: 'line',
        data: { labels: labels, datasets: [
            { label: metricLabel, data: data1, borderColor: colors.cyan1, backgroundColor: colors.cyan1a, borderWidth: 2, pointRadius: 4, pointBackgroundColor: colors.cyan1, fill: true, tension: 0.3 }
        ] },
        options: { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
            plugins: { legend: { labels: { color: '#1e293b', font: { size: 10 }, boxWidth: 12, padding: 15 } }, datalabels: { display: false } },
            scales: {
                x: { ticks: { color: '#64748b', font: { size: 9 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 15 }, grid: { display: false } },
                y: { ticks: { color: colors.cyan1, font: { size: 9 }, callback: (v) => '$' + formatNum(v.toFixed(0)) }, grid: { color: 'rgba(0, 0, 0, 0.06)' }, title: { display: true, text: metricLabel, color: colors.cyan1, font: { size: 10 } } }
            }
        }
    });
}

function createDualLineChart(canvasId, dailyData, m1Key, m1Label, m2Key, m2Label, m2Suffix) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    if (charts[canvasId]) charts[canvasId].destroy();
    const labels = dailyData.map(d => d.label);
    const data1 = dailyData.map(d => d[m1Key]);
    const data2 = dailyData.map(d => parseFloat(d[m2Key].toFixed(2)));
    charts[canvasId] = new Chart(ctx, {
        type: 'line',
        data: { labels: labels, datasets: [
            { label: m1Label, data: data1, borderColor: colors.cyan1, backgroundColor: colors.cyan1a, borderWidth: 2, pointRadius: 3, pointBackgroundColor: colors.cyan1, fill: true, tension: 0.3, yAxisID: 'y' },
            { label: m2Label, data: data2, borderColor: '#ff6b9d', backgroundColor: 'rgba(255, 107, 157, 0.1)', borderWidth: 2, pointRadius: 3, pointBackgroundColor: '#ff6b9d', borderDash: [5, 3], fill: false, tension: 0.3, yAxisID: 'y1' }
        ] },
        options: { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
            plugins: { legend: { labels: { color: '#1e293b', font: { size: 10 }, boxWidth: 12, padding: 15 } }, datalabels: { display: false } },
            scales: {
                x: { ticks: { color: '#64748b', font: { size: 9 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 15 }, grid: { display: false } },
                y: { type: 'linear', position: 'left', ticks: { color: colors.cyan1, font: { size: 9 } }, grid: { color: 'rgba(0, 0, 0, 0.06)' }, title: { display: true, text: m1Label, color: colors.cyan1, font: { size: 10 } } },
                y1: { type: 'linear', position: 'right', ticks: { color: '#ff6b9d', font: { size: 9 }, callback: (v) => v.toFixed(1) + (m2Suffix || '') }, grid: { drawOnChartArea: false }, title: { display: true, text: m2Label, color: '#ff6b9d', font: { size: 10 } } }
            }
        }
    });
}

function getCompraByFormato(data) {
    const map = {};
    data.forEach(d => {
        const fmt = d['FORMATO']; const compra = d['COMPRA'];
        if (!fmt || !compra || fmt === '' || compra === '') return;
        if (!map[fmt]) map[fmt] = new Set();
        map[fmt].add(compra);
    });
    const result = {};
    Object.keys(map).forEach(k => { result[k] = Array.from(map[k]).join(' / '); });
    return result;
}

function groupBy(data, key, sumKey) {
    return data.reduce((acc, d) => {
        const k = d[key];
        if (!k || k === '' || k === null) return acc;
        acc[k] = (acc[k] || 0) + (d[sumKey] || 0); return acc;
    }, {});
}

function groupByAvg(data, key, avgKey) {
    const sums = {}, counts = {};
    data.forEach(d => {
        const k = d[key];
        if (!k || k === '' || k === null) return;
        sums[k] = (sums[k] || 0) + (d[avgKey] || 0);
        counts[k] = (counts[k] || 0) + 1;
    });
    const result = {};
    Object.keys(sums).forEach(k => { result[k] = parseFloat((sums[k] / counts[k]).toFixed(2)); });
    return result;
}

function updateTable(data) {
    const tbody = document.querySelector('#dataTable tbody');
    tbody.innerHTML = '';
    data.slice(0, 50).forEach(d => {
        const tr = document.createElement('tr');
        tr.innerHTML = '<td><span class="platform-badge">' + (d.PLATAFORMA || '-') + '</span></td>' +
            '<td>' + (d.ETAPA || '-') + '</td>' +
            '<td>' + (d.COMPRA || '-') + '</td>' +
            '<td>' + (d.FORMATO || '-') + '</td>' +
            '<td>' + (d.AUDIENCIA || '-') + '</td>' +
            '<td>' + (d.GASTO || 0).toFixed(2) + '</td>' +
            '<td>' + formatNum(d.IMPRESIONES || 0) + '</td>' +
            '<td>' + formatNum(d.CLICS || 0) + '</td>' +
            '<td>' + formatNum(d.VIEWS || 0) + '</td>' +
            '<td>' + (d.CTR || 0).toFixed(2) + '%</td>' +
            '<td>' + (d.VTR || 0).toFixed(2) + '%</td>';
        tbody.appendChild(tr);
    });
}

function exportPDF() {
    Object.values(charts).forEach(function(c) { c.resize(); });
    setTimeout(function() { window.print(); }, 300);
}
