document.addEventListener('DOMContentLoaded', function() {
    const dataElement = document.getElementById('dashboard-data');
    if (!dataElement) return;

    const dashboardData = JSON.parse(dataElement.textContent);
    const ctx = document.getElementById('volumeChart').getContext('2d');
    
    // Create Premium Gradients
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(99, 102, 241, 0.4)');
    gradient.addColorStop(1, 'rgba(99, 102, 241, 0)');

    let currentMode = 'volume';
    let myChart = null;

    function getChartData(mode) {
        switch(mode) {
            case 'weight': return dashboardData.weeklyWeight;
            case 'reps': return dashboardData.weeklyReps;
            case 'cardio': return dashboardData.weeklyCardio;
            default: return dashboardData.weeklyVolume;
        }
    }

    function getChartLabel(mode) {
        switch(mode) {
            case 'weight': return 'Max Weight (kg)';
            case 'reps': return 'Max Reps';
            case 'cardio': return 'Cardio Duration (min)';
            default: return 'Total Volume (kg)';
        }
    }

    function getChartColors(mode) {
        switch(mode) {
            case 'weight': return { border: '#10b981', bg: 'rgba(16, 185, 129, 0.4)' }; // Emerald
            case 'reps': return { border: '#f59e0b', bg: 'rgba(245, 158, 11, 0.4)' };   // Amber
            case 'cardio': return { border: '#ec4899', bg: 'rgba(236, 72, 153, 0.4)' }; // Pink
            default: return { border: '#6366f1', bg: 'rgba(99, 102, 241, 0.4)' };       // Indigo
        }
    }

    function initChart(mode) {
        const labels = dashboardData.weeklyLabels || [];
        const data = getChartData(mode);
        const label = getChartLabel(mode);
        const colors = getChartColors(mode);
        
        const isLight = document.documentElement.getAttribute('data-theme') === 'light';
        const textColor = isLight ? '#475569' : '#94a3b8';
        const gridColor = isLight ? 'rgba(0, 0, 0, 0.08)' : 'rgba(255, 255, 255, 0.08)';

        // Create Premium Dynamic Gradient
        const chartGradient = ctx.createLinearGradient(0, 0, 0, 400);
        chartGradient.addColorStop(0, colors.bg);
        chartGradient.addColorStop(1, 'rgba(0, 0, 0, 0)');

        if (myChart) {
            myChart.destroy();
        }

        myChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: label,
                    data: data,
                    borderColor: colors.border,
                    borderWidth: 3,
                    backgroundColor: chartGradient,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: colors.border,
                    pointBorderColor: isLight ? '#ffffff' : 'rgba(255, 255, 255, 0.8)',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: isLight ? 'rgba(255, 255, 255, 0.95)' : 'rgba(15, 17, 36, 0.9)',
                        titleColor: isLight ? '#0f172a' : '#ffffff',
                        bodyColor: isLight ? '#64748b' : '#94a3b8',
                        titleFont: { family: 'Outfit', size: 14, weight: 'bold' },
                        bodyFont: { family: 'Outfit', size: 13 },
                        padding: 12,
                        cornerRadius: 12,
                        displayColors: false,
                        borderColor: isLight ? 'rgba(0, 0, 0, 0.1)' : 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: gridColor, drawBorder: false },
                        ticks: { 
                            color: textColor, 
                            font: { family: 'Outfit', size: 12, weight: '600' } 
                        }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { 
                            color: textColor, 
                            font: { family: 'Outfit', size: 12, weight: '600' } 
                        }
                    }
                }
            }
        });
    }

    // Global function for the toggle buttons in dashboard.html
    window.setChartMode = function(mode) {
        currentMode = mode;
        
        // Update button active states
        document.querySelectorAll('.toggle-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        const activeBtn = document.getElementById('btnChart' + mode.charAt(0).toUpperCase() + mode.slice(1));
        if (activeBtn) activeBtn.classList.add('active');
        
        initChart(mode);
    };

    // Exercise Selection Logic
    const categoryFilter = document.getElementById('categoryFilter');
    const exerciseFilter = document.getElementById('exerciseFilter');
    
    if (categoryFilter && exerciseFilter) {
        const exercisesByCat = dashboardData.exercisesByCat || {};
        const selectedExercise = exerciseFilter.getAttribute('data-selected');

        function updateExerciseOptions() {
            const cat = categoryFilter.value;
            exerciseFilter.innerHTML = '<option value="">All Exercises</option>';
            
            if (cat && exercisesByCat[cat]) {
                exercisesByCat[cat].forEach(ex => {
                    const opt = document.createElement('option');
                    opt.value = ex;
                    opt.textContent = ex;
                    if (ex === selectedExercise) opt.selected = true;
                    exerciseFilter.appendChild(opt);
                });
            }
        }

        categoryFilter.addEventListener('change', updateExerciseOptions);
        updateExerciseOptions();
    }

    // Start with volume chart
    initChart('volume');
});
