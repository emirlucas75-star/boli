// Funciones globales para el sistema
document.addEventListener('DOMContentLoaded', function() {
    // Auto-cerrar alertas después de 5 segundos
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.display = 'none';
        }, 5000);
    });
    
    // Validación de formularios
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const requiredFields = form.querySelectorAll('[required]');
            let isValid = true;
            
            requiredFields.forEach(field => {
                if (field.disabled) return;
                const value = field.value == null ? '' : String(field.value);
                if (!value.trim()) {
                    field.style.borderColor = '#e74c3c';
                    isValid = false;
                } else {
                    field.style.borderColor = '#ddd';
                }
            });
            
            if (!isValid) {
                e.preventDefault();
                alert('Por favor, completa todos los campos requeridos');
            }
        });
    });
});

// Función para actualizar tabla de posiciones en tiempo real
async function updateStandings() {
    try {
        const response = await fetch('/standings');
        const standings = await response.json();
        
        const standingsTable = document.getElementById('standings-table');
        if (standingsTable) {
            let html = `
                <thead>
                    <tr>
                        <th>Pos</th>
                        <th>Equipo</th>
                        <th>Puntos</th>
                        <th>V</th>
                        <th>D</th>
                        <th>SF</th>
                        <th>SC</th>
                    </tr>
                </thead>
                <tbody>
            `;
            
            standings.forEach((team, index) => {
                html += `
                    <tr>
                        <td>${index + 1}</td>
                        <td>${team.name}</td>
                        <td>${team.points}</td>
                        <td>${team.wins}</td>
                        <td>${team.losses}</td>
                        <td>${team.sets_won}</td>
                        <td>${team.sets_lost}</td>
                    </tr>
                `;
            });
            
            html += '</tbody>';
            standingsTable.innerHTML = html;
        }
    } catch (error) {
        console.error('Error al actualizar tabla de posiciones:', error);
    }
}

// Actualizar tabla cada 30 segundos si estamos en la página de equipos
if (window.location.pathname === '/teams') {
    updateStandings();
    setInterval(updateStandings, 30000);
}

function initCoverflows() {
    document.querySelectorAll('[data-coverflow]').forEach((root) => {
        const cards = [...root.querySelectorAll('.coverflow-card')];
        const countEl = root.querySelector('.coverflow-count b');
        const bar = root.querySelector('.coverflow-bar i');
        const n = cards.length;
        if (!n) return;

        let index = 0;
        let timer = null;
        const delay = Number(root.dataset.autoplay || 0);

        const paint = () => {
            cards.forEach((card, idx) => {
                card.classList.remove('is-active', 'is-prev', 'is-next');
                if (idx === index) {
                    card.classList.add('is-active');
                } else if (n > 2 && idx === (index - 1 + n) % n) {
                    card.classList.add('is-prev');
                } else if (n > 1 && idx === (index + 1) % n) {
                    card.classList.add('is-next');
                }
            });
            if (countEl) countEl.textContent = String(index + 1).padStart(2, '0');
            if (bar) {
                bar.style.animation = 'none';
                void bar.offsetWidth;
                bar.style.animation = '';
            }
        };

        const go = (delta) => {
            index = (index + delta + n) % n;
            paint();
            start();
        };

        const start = () => {
            if (n < 2 || !delay) return;
            clearInterval(timer);
            timer = setInterval(() => go(1), delay);
        };

        const stop = () => clearInterval(timer);

        const prevBtn = root.querySelector('.coverflow-btn.is-prev');
        const nextBtn = root.querySelector('.coverflow-btn.is-next');
        if (n < 2) {
            if (prevBtn) prevBtn.hidden = true;
            if (nextBtn) nextBtn.hidden = true;
        }

        prevBtn?.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            go(-1);
        });
        nextBtn?.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            go(1);
        });
        prevBtn?.addEventListener('pointerdown', (e) => e.stopPropagation());
        nextBtn?.addEventListener('pointerdown', (e) => e.stopPropagation());

        let startX = null;
        const stage = root.querySelector('.coverflow-stage');
        stage?.addEventListener('pointerdown', (e) => {
            startX = e.clientX;
            stop();
        });
        stage?.addEventListener('pointerup', (e) => {
            if (startX == null) return;
            const dx = e.clientX - startX;
            startX = null;
            if (dx > 40) go(-1);
            else if (dx < -40) go(1);
            else start();
        });
        stage?.addEventListener('pointercancel', () => {
            startX = null;
            start();
        });

        root.addEventListener('mouseenter', stop);
        root.addEventListener('mouseleave', start);

        paint();
        start();
    });
}

document.addEventListener('DOMContentLoaded', initCoverflows);
document.addEventListener('DOMContentLoaded', initHeroCarousel);

function initHeroCarousel() {
    document.querySelectorAll('[data-carousel]').forEach((root) => {
        const track = root.querySelector('.img-carousel-track');
        const slides = [...root.querySelectorAll('.img-carousel-slide')];
        const dots = [...root.querySelectorAll('.img-carousel-dot')];
        if (!track || slides.length < 2) return;

        let index = 0;
        let timer = null;
        const delay = Number(root.dataset.autoplay || 0);

        const go = (i) => {
            index = (i + slides.length) % slides.length;
            track.scrollTo({ left: slides[index].offsetLeft, behavior: 'smooth' });
            dots.forEach((dot, di) => dot.classList.toggle('is-on', di === index));
        };

        const start = () => {
            if (!delay) return;
            clearInterval(timer);
            timer = setInterval(() => go(index + 1), delay);
        };

        const stop = () => clearInterval(timer);

        root.querySelector('.img-carousel-nav.is-prev')?.addEventListener('click', (e) => {
            e.stopPropagation();
            go(index - 1);
            start();
        });
        root.querySelector('.img-carousel-nav.is-next')?.addEventListener('click', (e) => {
            e.stopPropagation();
            go(index + 1);
            start();
        });
        dots.forEach((dot, i) => {
            dot.addEventListener('click', () => {
                go(i);
                start();
            });
        });

        track.addEventListener('scroll', () => {
            const mid = track.scrollLeft + track.clientWidth / 2;
            let best = 0;
            let dist = Infinity;
            slides.forEach((slide, i) => {
                const center = slide.offsetLeft + slide.offsetWidth / 2;
                const d = Math.abs(center - mid);
                if (d < dist) {
                    dist = d;
                    best = i;
                }
            });
            if (best !== index) {
                index = best;
                dots.forEach((dot, di) => dot.classList.toggle('is-on', di === index));
            }
        }, { passive: true });

        track.addEventListener('pointerdown', stop);
        track.addEventListener('pointerup', start);
        root.addEventListener('mouseenter', stop);
        root.addEventListener('mouseleave', start);

        go(0);
        start();
    });
}

window.selectedCancha = 'all';

function listCanchasFromPage() {
    const names = new Set();
    document.querySelectorAll('.match-card').forEach(card => {
        const value = (card.dataset.cancha || '').trim();
        if (value) names.add(value);
    });
    document.querySelectorAll('#canchaFilter option').forEach(opt => {
        const value = (opt.value || '').trim();
        if (value && value !== 'all') names.add(value);
    });
    return [...names].sort((a, b) => a.localeCompare(b, 'es', { numeric: true }));
}

function renderCanchaChips() {
    const bar = document.getElementById('canchaChips');
    if (!bar) return;
    const canchas = listCanchasFromPage();
    const current = window.selectedCancha || 'all';
    bar.innerHTML = '';

    const makeChip = (value, label) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'cancha-chip' + (current === value ? ' is-on' : '');
        btn.dataset.cancha = value;
        btn.textContent = label;
        btn.addEventListener('click', () => selectCancha(value));
        bar.appendChild(btn);
    };

    makeChip('all', 'Todas');
    canchas.forEach(name => makeChip(name, name));

    const hint = document.getElementById('canchaEmptyHint');
    if (hint) hint.hidden = canchas.length > 0;

    const modal = document.getElementById('canchaFilter');
    if (modal) {
        modal.innerHTML = '<option value="all">Todas las canchas</option>' +
            canchas.map(name => `<option value="${name.replace(/"/g, '&quot;')}">${name}</option>`).join('');
        modal.value = current;
    }
}

function selectCancha(value) {
    window.selectedCancha = value || 'all';
    document.querySelectorAll('#canchaChips .cancha-chip').forEach(btn => {
        btn.classList.toggle('is-on', btn.dataset.cancha === window.selectedCancha);
    });
    const modal = document.getElementById('canchaFilter');
    if (modal) modal.value = window.selectedCancha;
    if (typeof window.applyCurrentMatchFilters === 'function') {
        window.applyCurrentMatchFilters();
    }
}

function currentCancha() {
    return window.selectedCancha || 'all';
}

document.addEventListener('DOMContentLoaded', function() {
    renderCanchaChips();
    
    // Actualizar partidos cada 3 segundos si estamos en una página con partidos
    const matchCards = document.querySelectorAll('.match-card');
    if (matchCards.length > 0) {
        updateMatches();
        setInterval(updateMatches, 3000);
    }
});

// Función para actualizar estados de partidos en tiempo real
async function updateMatches() {
    const matchCards = document.querySelectorAll('.match-card[data-match-id]');
    if (!matchCards.length) return;

    try {
        const response = await fetch('/api/matches/scores');
        if (!response.ok) return;
        const scores = await response.json();
        const byId = {};
        scores.forEach(s => { byId[s.match_id] = s; });

        const labels = { pending: 'Pendiente', active: 'EN VIVO', completed: 'Finalizado' };
        const footerLabels = { pending: 'Pendiente', active: 'En Vivo', completed: 'Completado' };

        matchCards.forEach(card => {
            const data = byId[parseInt(card.dataset.matchId, 10)];
            if (!data) return;

            const oldStatus = card.dataset.status;
            card.dataset.status = data.status;

            const badge = card.querySelector('.js-badge, .category-badge');
            if (badge) {
                badge.className = `category-badge cat-${data.status} js-badge`;
                badge.textContent = labels[data.status] || data.status;
            }

            const statusIndicator = card.querySelector('.status-indicator');
            if (statusIndicator) {
                statusIndicator.textContent = footerLabels[data.status] || data.status;
                statusIndicator.className = `status-indicator status-${data.status}`;
                if (oldStatus && oldStatus !== data.status) {
                    statusIndicator.style.animation = 'pulse 0.6s ease';
                    setTimeout(() => { statusIndicator.style.animation = ''; }, 600);
                }
            }

            const timeEl = card.querySelector('.js-match-time');
            const scoreBlock = card.querySelector('.js-score-block');
            const liveEl = card.querySelector('.js-live');
            const showScore = data.status === 'active' || data.status === 'completed';
            if (timeEl) timeEl.hidden = showScore;
            if (scoreBlock) scoreBlock.hidden = !showScore;
            if (liveEl) liveEl.hidden = data.status !== 'active';

            const s1 = card.querySelector('.js-sets1');
            const s2 = card.querySelector('.js-sets2');
            if (s1) s1.textContent = data.sets_team1;
            if (s2) s2.textContent = data.sets_team2;
            const p1 = card.querySelector('.js-p1');
            const p2 = card.querySelector('.js-p2');
            if (p1) p1.textContent = data.team1_points;
            if (p2) p2.textContent = data.team2_points;
            const liveSmall = liveEl && liveEl.querySelector('small');
            if (liveSmall) liveSmall.textContent = 'Set ' + data.set_number;
        });
    } catch (error) {
        console.error('Error al actualizar partidos:', error);
    }
}