/* Main Application Script - Industry Standard Enterprise Theme Switcher & Interactive Animations */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Theme Manager (Workday Light, ATS Brand, Dark Mode, High Contrast)
    const savedTheme = localStorage.getItem('hrms_theme') || 'light';
    setTheme(savedTheme);

    const themeDropdownBtn = document.getElementById('themeDropdownBtn');
    const themeDropdownMenu = document.getElementById('themeDropdownMenu');

    if (themeDropdownBtn && themeDropdownMenu) {
        themeDropdownBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            themeDropdownMenu.classList.toggle('active');
        });

        document.addEventListener('click', () => {
            themeDropdownMenu.classList.remove('active');
        });
    }

    const themeOptions = document.querySelectorAll('.theme-option-btn');
    themeOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            const targetTheme = opt.getAttribute('data-theme-val');
            setTheme(targetTheme);
            if (themeDropdownMenu) themeDropdownMenu.classList.remove('active');
            showToast(`Theme switched to ${opt.textContent.trim()}`, 'info');
        });
    });

    function setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('hrms_theme', theme);

        // Update active class on options
        const options = document.querySelectorAll('.theme-option-btn');
        options.forEach(opt => {
            if (opt.getAttribute('data-theme-val') === theme) {
                opt.classList.add('active');
            } else {
                opt.classList.remove('active');
            }
        });

        // Update Button Icon & Text
        const label = document.getElementById('themeCurrentLabel');
        const icon = document.getElementById('themeCurrentIcon');
        if (label && icon) {
            if (theme === 'ats-brand') {
                label.textContent = 'ATS Brand';
                icon.className = 'fas fa-palette';
            } else if (theme === 'dark') {
                label.textContent = 'Dark Mode';
                icon.className = 'fas fa-moon';
            } else if (theme === 'contrast') {
                label.textContent = 'High Contrast';
                icon.className = 'fas fa-adjust';
            } else {
                label.textContent = 'Light Mode';
                icon.className = 'fas fa-sun';
            }
        }
    }

    // 2. Mobile Sidebar Toggle
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const sidebar = document.querySelector('.sidebar');
    if (mobileMenuBtn && sidebar) {
        mobileMenuBtn.addEventListener('click', () => {
            sidebar.classList.toggle('active');
        });
    }

    // 3. Staggered Entrance Animations & Stat Counters
    initEntranceAnimations();
    initStatCounters();
    initInteractiveTables();

    // 4. Live Staffing Availability Checker (In Apply Leave Form)
    const startDateInput = document.getElementById('start_date');
    const endDateInput = document.getElementById('end_date');
    const isHalfDayCheckbox = document.getElementById('is_half_day');
    const halfDaySessionGroup = document.getElementById('half_day_session_group');
    const workingDaysDisplay = document.getElementById('working_days_display');
    const availBox = document.getElementById('availability_checker_box');

    if (isHalfDayCheckbox) {
        isHalfDayCheckbox.addEventListener('change', () => {
            if (halfDaySessionGroup) {
                halfDaySessionGroup.style.display = isHalfDayCheckbox.checked ? 'block' : 'none';
            }
            if (endDateInput && startDateInput) {
                if (isHalfDayCheckbox.checked) {
                    endDateInput.value = startDateInput.value;
                    endDateInput.disabled = true;
                } else {
                    endDateInput.disabled = false;
                }
            }
            triggerAvailabilityCheck();
        });
    }

    if (startDateInput) {
        startDateInput.addEventListener('change', () => {
            if (isHalfDayCheckbox && isHalfDayCheckbox.checked && endDateInput) {
                endDateInput.value = startDateInput.value;
            }
            triggerAvailabilityCheck();
        });
    }

    if (endDateInput) {
        endDateInput.addEventListener('change', triggerAvailabilityCheck);
    }

    function triggerAvailabilityCheck() {
        if (!startDateInput || !endDateInput) return;

        const sDate = startDateInput.value;
        const eDate = isHalfDayCheckbox && isHalfDayCheckbox.checked ? sDate : endDateInput.value;

        if (!sDate || !eDate) return;

        // Fetch Working Days
        const isHalf = isHalfDayCheckbox ? isHalfDayCheckbox.checked : false;
        fetch(`/api/check-working-days?start_date=${sDate}&end_date=${eDate}&is_half_day=${isHalf}`)
            .then(res => res.json())
            .then(data => {
                if (workingDaysDisplay) {
                    workingDaysDisplay.textContent = `${data.working_days} working day(s)`;
                }
            });

        // Fetch Availability
        fetch(`/api/check-availability?start_date=${sDate}&end_date=${eDate}`)
            .then(res => res.json())
            .then(data => {
                if (!availBox) return;
                availBox.style.display = 'block';

                const pct = data.availability_pct;
                const fill = availBox.querySelector('.progress-bar-fill');
                const text = availBox.querySelector('.avail-text');
                const warn = availBox.querySelector('.avail-warning');

                if (fill) {
                    fill.style.width = `0%`;
                    setTimeout(() => {
                        fill.style.width = `${pct}%`;
                        fill.style.backgroundColor = data.is_below_threshold ? '#EF4444' : '#10B981';
                    }, 50);
                }

                if (text) {
                    text.textContent = `Team Availability: ${pct}% (${data.available_members}/${data.total_dept_members} available)`;
                }

                if (warn) {
                    if (data.is_below_threshold) {
                        warn.style.display = 'block';
                        let sugHtml = `<strong>Warning:</strong> Staffing falls below minimum required threshold (${data.min_threshold_pct}%).`;
                        if (data.suggested_dates && data.suggested_dates.length > 0) {
                            sugHtml += `<br><em>Suggested alternative dates:</em><ul>`;
                            data.suggested_dates.forEach(d => {
                                sugHtml += `<li>${d.start_date} to ${d.end_date} (Availability: ${d.availability_pct}%)</li>`;
                            });
                            sugHtml += `</ul>`;
                        }
                        warn.innerHTML = sugHtml;
                    } else {
                        warn.style.display = 'none';
                    }
                }
            })
            .catch(err => console.error(err));
    }

    // Form Submission Celebration Hook
    const leaveApplyForm = document.querySelector('form[action*="apply_leave"]');
    if (leaveApplyForm) {
        leaveApplyForm.addEventListener('submit', () => {
            triggerConfetti();
        });
    }
});

// Staggered Entrance Animations Initialization
function initEntranceAnimations() {
    const cards = document.querySelectorAll('.card, .balance-card, .welcome-banner');
    cards.forEach((card, index) => {
        card.classList.add('animate-fade-up');
        card.style.animationDelay = `${(index % 6) * 0.08}s`;
    });
}

// Stat Counters Animation (Animates numbers smoothly up from 0)
function initStatCounters() {
    const values = document.querySelectorAll('.balance-value, .stat-value, .stat-number');
    values.forEach(el => {
        const text = el.textContent.trim();
        const num = parseFloat(text);
        if (!isNaN(num) && num > 0 && !el.dataset.animated) {
            el.dataset.animated = 'true';
            let start = 0;
            const duration = 800; // ms
            const stepTime = 20;
            const steps = duration / stepTime;
            const increment = num / steps;
            const isFloat = text.includes('.');

            const timer = setInterval(() => {
                start += increment;
                if (start >= num) {
                    el.textContent = isFloat ? num.toFixed(1) : Math.round(num);
                    clearInterval(timer);
                } else {
                    el.textContent = isFloat ? start.toFixed(1) : Math.floor(start);
                }
            }, stepTime);
        }
    });
}

// Live Interactive Table Filter & Quick Filter Pills
function initInteractiveTables() {
    const tables = document.querySelectorAll('.table');
    tables.forEach((table, index) => {
        const parentCard = table.closest('.card');
        if (!parentCard) return;

        // Inject Filter Controls if not present
        if (!parentCard.querySelector('.table-filter-input')) {
            const header = parentCard.querySelector('.card-header');
            if (header) {
                const searchContainer = document.createElement('div');
                searchContainer.style.display = 'flex';
                searchContainer.style.alignItems = 'center';
                searchContainer.style.gap = '10px';

                searchContainer.innerHTML = `
                    <div style="position: relative;">
                        <i class="fas fa-search" style="position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: var(--text-muted); font-size: 0.8rem;"></i>
                        <input type="text" class="table-filter-input form-control" placeholder="Search table..." style="padding-left: 32px; height: 36px; font-size: 0.82rem; width: 220px; border-radius: var(--radius-full);">
                    </div>
                `;
                header.appendChild(searchContainer);

                const input = searchContainer.querySelector('.table-filter-input');
                input.addEventListener('input', (e) => {
                    const query = e.target.value.toLowerCase();
                    const rows = table.querySelectorAll('tbody tr');
                    rows.forEach(row => {
                        const text = row.textContent.toLowerCase();
                        if (text.includes(query)) {
                            row.style.display = '';
                            row.classList.add('animate-scale-in');
                        } else {
                            row.style.display = 'none';
                        }
                    });
                });
            }
        }
    });
}

// Toast Notifications System
function showToast(message, type = 'info') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const iconMap = {
        success: 'fa-check-circle',
        danger: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };

    toast.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <i class="fas ${iconMap[type] || 'fa-info-circle'}" style="font-size: 1.1rem;"></i>
            <span>${message}</span>
        </div>
        <i class="fas fa-times" style="cursor: pointer; opacity: 0.6;" onclick="this.parentElement.remove()"></i>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('toast-exit');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// Confetti Particle Explosion Animation
function triggerConfetti() {
    const canvas = document.createElement('canvas');
    canvas.style.position = 'fixed';
    canvas.style.top = '0';
    canvas.style.left = '0';
    canvas.style.width = '100vw';
    canvas.style.height = '100vh';
    canvas.style.pointerEvents = 'none';
    canvas.style.zIndex = '3000';
    document.body.appendChild(canvas);

    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    const particles = [];
    const colors = ['#4F46E5', '#10B981', '#F59E0B', '#EF4444', '#06B6D4', '#EC4899'];

    for (let i = 0; i < 80; i++) {
        particles.push({
            x: canvas.width / 2,
            y: canvas.height / 2,
            vx: (Math.random() - 0.5) * 14,
            vy: (Math.random() - 0.8) * 16,
            size: Math.random() * 8 + 4,
            color: colors[Math.floor(Math.random() * colors.length)],
            rotation: Math.random() * 360,
            rSpeed: (Math.random() - 0.5) * 10,
            opacity: 1
        });
    }

    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        particles.forEach(p => {
            p.x += p.vx;
            p.y += p.vy;
            p.vy += 0.4; // gravity
            p.opacity -= 0.015;
            p.rotation += p.rSpeed;

            if (p.opacity > 0) {
                ctx.save();
                ctx.translate(p.x, p.y);
                ctx.rotate((p.rotation * Math.PI) / 180);
                ctx.globalAlpha = Math.max(0, p.opacity);
                ctx.fillStyle = p.color;
                ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);
                ctx.restore();
            }
        });

        if (particles.some(p => p.opacity > 0)) {
            requestAnimationFrame(animate);
        } else {
            canvas.remove();
        }
    }

    animate();
}

// FAB Quick Action Speed Dial Toggle
function initFABMenu() {
    const fabContainer = document.getElementById('fabContainer');
    const fabMainBtn = document.getElementById('fabMainBtn');
    if (fabContainer && fabMainBtn) {
        fabMainBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            fabContainer.classList.toggle('active');
        });

        document.addEventListener('click', () => {
            fabContainer.classList.remove('active');
        });
    }
}

// Click Ripple Animation Handler
function initRippleEffect() {
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.btn, .card, .fab-main-btn, .theme-dropdown-btn');
        if (!btn) return;

        const circle = document.createElement('span');
        const diameter = Math.max(btn.clientWidth, btn.clientHeight);
        const radius = diameter / 2;

        const rect = btn.getBoundingClientRect();
        circle.style.width = circle.style.height = `${diameter}px`;
        circle.style.left = `${e.clientX - rect.left - radius}px`;
        circle.style.top = `${e.clientY - rect.top - radius}px`;
        circle.classList.add('ripple-wave');

        const ripple = btn.getElementsByClassName('ripple-wave')[0];
        if (ripple) {
            ripple.remove();
        }

        btn.appendChild(circle);
        setTimeout(() => circle.remove(), 600);
    });
}

// Ambient Background Mesh Particle Canvas Animation
function initAmbientMeshCanvas() {
    const canvas = document.getElementById('ambientMeshCanvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let width = canvas.width = window.innerWidth;
    let height = canvas.height = window.innerHeight;

    window.addEventListener('resize', () => {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    });

    const nodes = [];
    const numNodes = Math.min(35, Math.floor(width / 40));

    for (let i = 0; i < numNodes; i++) {
        nodes.push({
            x: Math.random() * width,
            y: Math.random() * height,
            vx: (Math.random() - 0.5) * 0.8,
            vy: (Math.random() - 0.5) * 0.8,
            radius: Math.random() * 2 + 1
        });
    }

    function renderMesh() {
        ctx.clearRect(0, 0, width, height);

        // Draw connections
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                const dx = nodes[i].x - nodes[j].x;
                const dy = nodes[i].y - nodes[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < 140) {
                    ctx.beginPath();
                    ctx.moveTo(nodes[i].x, nodes[i].y);
                    ctx.lineTo(nodes[j].x, nodes[j].y);
                    ctx.strokeStyle = `rgba(99, 102, 241, ${0.15 * (1 - dist / 140)})`;
                    ctx.lineWidth = 1;
                    ctx.stroke();
                }
            }
        }

        // Draw nodes
        nodes.forEach(node => {
            node.x += node.vx;
            node.y += node.vy;

            if (node.x < 0 || node.x > width) node.vx *= -1;
            if (node.y < 0 || node.y > height) node.vy *= -1;

            ctx.beginPath();
            ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(79, 70, 229, 0.4)';
            ctx.fill();
        });

        requestAnimationFrame(renderMesh);
    }

    renderMesh();
}

// 3D Card Spotlight & Cursor Tracking Animation
function initCardSpotlight() {
    const cards = document.querySelectorAll('.card, .balance-card, .welcome-banner');
    cards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            card.style.background = `radial-gradient(circle at ${x}px ${y}px, rgba(99, 102, 241, 0.08), var(--bg-card) 70%)`;
        });

        card.addEventListener('mouseleave', () => {
            card.style.background = 'var(--bg-card)';
        });
    });
}

// Auto-run interactive background enhancements on DOMReady
document.addEventListener('DOMContentLoaded', () => {
    initFABMenu();
    initRippleEffect();
    initAmbientMeshCanvas();
    initCardSpotlight();
});

// Modal Dialog Helpers
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.add('active');
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('active');
}


