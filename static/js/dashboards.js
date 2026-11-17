/* Dashboard Analytics Script - Chart.js Visualizations with Animations */

document.addEventListener('DOMContentLoaded', () => {
    const deptChartCanvas = document.getElementById('deptLeaveChart');
    const trendChartCanvas = document.getElementById('leaveTrendChart');

    if (deptChartCanvas || trendChartCanvas) {
        fetch('/api/chart-data')
            .then(res => res.json())
            .then(data => {
                // Department Leave Breakdown Chart
                if (deptChartCanvas && data.department_breakdown) {
                    const labels = data.department_breakdown.map(d => d.dept_name);
                    const counts = data.department_breakdown.map(d => d.leave_count);

                    new Chart(deptChartCanvas, {
                        type: 'doughnut',
                        data: {
                            labels: labels.length > 0 ? labels : ['Engineering', 'HR', 'Sales'],
                            datasets: [{
                                data: counts.length > 0 ? counts : [0, 0, 0],
                                backgroundColor: ['#4F46E5', '#10B981', '#F59E0B', '#EF4444', '#06B6D4'],
                                hoverOffset: 8,
                                borderWidth: 2,
                                borderColor: 'var(--bg-card)'
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            animation: {
                                animateScale: true,
                                animateRotate: true,
                                duration: 1200,
                                easing: 'easeOutQuart'
                            },
                            plugins: {
                                legend: { 
                                    position: 'bottom',
                                    labels: {
                                        padding: 16,
                                        font: { family: 'Inter', weight: '600', size: 12 }
                                    }
                                }
                            }
                        }
                    });
                }

                // Monthly Leave Trends Bar Chart
                if (trendChartCanvas && data.monthly_trends) {
                    const months = data.monthly_trends.map(t => t.month).reverse();
                    const counts = data.monthly_trends.map(t => t.count).reverse();
                    const ctx = trendChartCanvas.getContext('2d');
                    
                    const gradient = ctx.createLinearGradient(0, 0, 0, 300);
                    gradient.addColorStop(0, 'rgba(99, 102, 241, 0.9)');
                    gradient.addColorStop(1, 'rgba(99, 102, 241, 0.15)');

                    new Chart(trendChartCanvas, {
                        type: 'bar',
                        data: {
                            labels: months.length > 0 ? months : ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                            datasets: [{
                                label: 'Approved Leave Applications',
                                data: counts.length > 0 ? counts : [0, 0, 0, 0, 0, 0],
                                backgroundColor: gradient,
                                hoverBackgroundColor: '#4F46E5',
                                borderRadius: 8,
                                borderSkipped: false
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            animation: {
                                duration: 1400,
                                easing: 'easeOutBack'
                            },
                            scales: {
                                y: { 
                                    beginAtZero: true, 
                                    ticks: { precision: 0, font: { family: 'Inter' } },
                                    grid: { color: 'rgba(226, 232, 240, 0.4)' }
                                },
                                x: {
                                    ticks: { font: { family: 'Inter' } },
                                    grid: { display: false }
                                }
                            },
                            plugins: {
                                legend: { display: false }
                            }
                        }
                    });
                }
            })
            .catch(err => console.error('Error fetching dashboard chart data:', err));
    }
});

