document.body.addEventListener('htmx:afterRequest', (event) => {
  if (event.detail.successful) {
    const form = event.detail.elt;
    const button = form?.querySelector?.('button[type="submit"]');
    if (button) button.blur();
    if (form?.dataset.closeModal) {
      const modal = document.getElementById(form.dataset.closeModal);
      if (modal) bootstrap.Modal.getOrCreateInstance(modal).hide();
    }
  }
});

const sidebarToggle = document.getElementById('sidebar-toggle');

if (sidebarToggle) {
  const setSidebarCollapsed = (collapsed) => {
    document.body.classList.toggle('sidebar-collapsed', collapsed);
    sidebarToggle.setAttribute('aria-expanded', String(!collapsed));
    sidebarToggle.setAttribute('aria-label', collapsed ? 'Expand navigation' : 'Collapse navigation');
    sidebarToggle.setAttribute('title', collapsed ? 'Expand navigation' : 'Collapse navigation');
    sidebarToggle.textContent = collapsed ? '›' : '‹';
    localStorage.setItem('dashboard-sidebar-collapsed', String(collapsed));
  };

  setSidebarCollapsed(localStorage.getItem('dashboard-sidebar-collapsed') === 'true');
  sidebarToggle.addEventListener('click', () => {
    setSidebarCollapsed(!document.body.classList.contains('sidebar-collapsed'));
  });
}

const chartElement = document.getElementById('pipeline-chart');
const chartDataElement = document.getElementById('pipeline-chart-data');

if (chartElement && chartDataElement && window.ApexCharts) {
  const pipeline = JSON.parse(chartDataElement.textContent);
  const chart = new ApexCharts(chartElement, {
    chart: {
      type: 'bar',
      height: 260,
      toolbar: { show: false },
      fontFamily: 'system-ui, -apple-system, Segoe UI, sans-serif',
      foreColor: '#8e9aab',
    },
    series: [{ name: 'Applications', data: pipeline.map((item) => item.count) }],
    colors: ['#5d73ff'],
    plotOptions: { bar: { borderRadius: 5, columnWidth: '52%' } },
    dataLabels: { enabled: false },
    xaxis: {
      categories: pipeline.map((item) => item.stage),
      labels: { trim: true, style: { fontSize: '11px' } },
      axisBorder: { color: 'rgba(255,255,255,.08)' },
      axisTicks: { color: 'rgba(255,255,255,.08)' },
    },
    yaxis: { min: 0, forceNiceScale: true, tickAmount: 4 },
    grid: { borderColor: 'rgba(255,255,255,.08)', strokeDashArray: 4 },
    tooltip: { theme: 'dark' },
  });
  chart.render();
}
