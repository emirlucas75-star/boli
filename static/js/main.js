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
                if (!field.value.trim()) {
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

// Sponsor Carousel
let currentSlide = 0;
let carouselInterval;

function updateCarousel() {
    const carousel = document.querySelector('.sponsor-carousel-inner');
    const dots = document.querySelectorAll('.carousel-dot');
    
    if (carousel) {
        const slideCount = carousel.querySelectorAll('.sponsor-banner').length;
        if (slideCount > 1) {
            carousel.style.transform = `translateX(-${currentSlide * 100}%)`;
            
            // Update dots
            dots.forEach((dot, index) => {
                dot.classList.toggle('active', index === currentSlide);
            });
        }
    }
}

function goToSlide(index) {
    const carousel = document.querySelector('.sponsor-carousel-inner');
    if (carousel) {
        const slideCount = carousel.querySelectorAll('.sponsor-banner').length;
        currentSlide = index % slideCount;
        updateCarousel();
        
        // Reset auto-play
        clearInterval(carouselInterval);
        startAutoplay();
    }
}

function nextSlide() {
    const carousel = document.querySelector('.sponsor-carousel-inner');
    if (carousel) {
        const slideCount = carousel.querySelectorAll('.sponsor-banner').length;
        currentSlide = (currentSlide + 1) % slideCount;
        updateCarousel();
    }
}

function startAutoplay() {
    const carousel = document.querySelector('.sponsor-carousel-inner');
    if (carousel && carousel.querySelectorAll('.sponsor-banner').length > 1) {
        carouselInterval = setInterval(nextSlide, 5000);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    updateCarousel();
    startAutoplay();
    
    // Actualizar partidos cada 3 segundos si estamos en una página con partidos
    const matchCards = document.querySelectorAll('.match-card');
    if (matchCards.length > 0) {
        updateMatches();
        setInterval(updateMatches, 3000);
    }
});

// Función para actualizar estados de partidos en tiempo real
async function updateMatches() {
    const matchCards = document.querySelectorAll('.match-card');
    
    for (const card of matchCards) {
        const matchId = card.dataset.matchId;
        if (!matchId) continue;
        
        try {
            const response = await fetch(`/api/match/${matchId}`);
            if (!response.ok) continue;
            
            const data = await response.json();
            const statusIndicator = card.querySelector('.status-indicator');
            const statusText = statusIndicator?.querySelector('span') || statusIndicator;
            
            // Actualizar el estado visual
            const oldStatus = card.dataset.status;
            card.dataset.status = data.status;
            
            if (statusIndicator) {
                const statusLabel = {
                    'pending': 'Pendiente',
                    'active': 'En Vivo',
                    'completed': 'Completado'
                };
                
                statusIndicator.textContent = statusLabel[data.status] || data.status;
                statusIndicator.className = `status-indicator status-${data.status}`;
                
                // Animación cuando cambia el estado
                if (oldStatus && oldStatus !== data.status) {
                    statusIndicator.style.animation = 'pulse 0.6s ease';
                    setTimeout(() => {
                        statusIndicator.style.animation = '';
                    }, 600);
                }
            }
        } catch (error) {
            console.error('Error al actualizar partido:', error);
        }
    }
}