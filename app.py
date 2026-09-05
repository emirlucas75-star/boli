from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from database import db
from models import User, Team, Player, Match, Set, BannerImage
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'sqlite:///tournament.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

SPANISH_DAYS = {
    'Monday': 'LUNES',
    'Tuesday': 'MARTES',
    'Wednesday': 'MIÉRCOLES',
    'Thursday': 'JUEVES',
    'Friday': 'VIERNES',
    'Saturday': 'SÁBADO',
    'Sunday': 'DOMINGO'
}

SPANISH_MONTHS = {
    'January': 'ENERO',
    'February': 'FEBRERO',
    'March': 'MARZO',
    'April': 'ABRIL',
    'May': 'MAYO',
    'June': 'JUNIO',
    'July': 'JULIO',
    'August': 'AGOSTO',
    'September': 'SEPTIEMBRE',
    'October': 'OCTUBRE',
    'November': 'NOVIEMBRE',
    'December': 'DICIEMBRE'
}


def format_spanish_date(value):
    if not value:
        return ''
    day_name = SPANISH_DAYS.get(value.strftime('%A'), value.strftime('%A')).upper()
    month_name = SPANISH_MONTHS.get(value.strftime('%B'), value.strftime('%B')).upper()
    return f"{day_name}, {value:%d} DE {month_name} {value:%Y}"

app.jinja_env.filters['spanish_date'] = format_spanish_date

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/assets/<filename>')
def serve_asset(filename):
    if filename in ['pelota-de-voleibol.png', 'voleibol.png']:
        return send_from_directory(os.path.dirname(os.path.abspath(__file__)), filename)
    return "Not found", 404

@app.route('/')
def index():
    hero_banners = BannerImage.query.filter_by(image_type='hero', active=True).order_by(BannerImage.position).all()
    sponsor_banners = BannerImage.query.filter_by(image_type='sponsor', active=True).order_by(BannerImage.position).all()
    matches_list = Match.query.order_by(Match.date).all()
    
    categories = sorted(list(set(m.category for m in matches_list if m.category)))
    groups = sorted(list(set(m.group for m in matches_list if m.group)))
    
    return render_template('index.html', 
                           hero_banners=hero_banners, 
                           sponsor_banners=sponsor_banners, 
                           matches=matches_list,
                           categories=categories,
                           groups=groups)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'team':
                return redirect(url_for('team_dashboard'))
            elif user.role == 'referee':
                return redirect(url_for('referee_dashboard'))
        else:
            flash('Usuario o contraseña incorrectos')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# Rutas del Administrador
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    teams = Team.query.all()
    matches = Match.query.order_by(Match.date).all()
    users = User.query.all()
    banners = BannerImage.query.order_by(BannerImage.image_type, BannerImage.position).all()
    return render_template('admin_dashboard.html', teams=teams, matches=matches, users=users, banners=banners)

@app.route('/admin/create_user', methods=['POST'])
@login_required
def create_user():
    if current_user.role != 'admin':
        return jsonify({'error': 'No autorizado'}), 403
    
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', '').strip()
    team_id = request.form.get('team_id') or None

    if not username or not password:
        return jsonify({'error': 'Usuario y contraseña son obligatorios'}), 400

    if role not in ('admin', 'team', 'referee'):
        return jsonify({'error': 'Rol inválido'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Usuario ya existe'}), 400

    # Solo los usuarios de equipo llevan team_id; árbitros y admin quedan sin equipo.
    if role == 'team':
        if not team_id:
            return jsonify({'error': 'Debes seleccionar un equipo'}), 400
        try:
            team_id = int(team_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'Equipo inválido'}), 400
        if not Team.query.get(team_id):
            return jsonify({'error': 'Equipo no encontrado'}), 400
    else:
        team_id = None

    user = User(username=username, role=role, team_id=team_id)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({'success': True, 'user': {'id': user.id, 'username': user.username, 'role': user.role}})

@app.route('/admin/create_team', methods=['POST'])
@login_required
def create_team():
    if current_user.role != 'admin':
        return jsonify({'error': 'No autorizado'}), 403
    
    name = request.form['name']
    coach = request.form['coach']
    category = request.form.get('category', '')
    if category == 'Otro':
        category = request.form.get('custom_category', '')
    group = request.form.get('group', '')
    
    if Team.query.filter_by(name=name).first():
        return jsonify({'error': 'Equipo ya existe'}), 400
    
    team = Team(name=name, coach=coach, category=category, group=group)
    db.session.add(team)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'team': {
            'id': team.id, 
            'name': team.name, 
            'coach': team.coach,
            'category': team.category,
            'group': team.group
        }
    })

@app.route('/admin/add_player', methods=['POST'])
@login_required
def add_player():
    if current_user.role != 'admin':
        return jsonify({'error': 'No autorizado'}), 403
    
    name = request.form['name']
    number = request.form['number']
    position = request.form['position']
    team_id = request.form['team_id']
    
    player = Player(name=name, number=number, position=position, team_id=team_id)
    db.session.add(player)
    db.session.commit()
    
    return jsonify({'success': True, 'player': {'id': player.id, 'name': player.name}})

@app.route('/admin/create_match', methods=['POST'])
@login_required
def create_match():
    if current_user.role != 'admin':
        return jsonify({'error': 'No autorizado'}), 403
    
    team1_id = request.form['team1_id']
    team2_id = request.form['team2_id']
    date_str = request.form['date']
    location = request.form.get('location', '')
    cancha = request.form.get('cancha', '')
    referee_id = request.form['referee_id']
    category = request.form.get('category', '')
    group = request.form.get('group', '')
    
    # Fallback to team1's category/group if they are blank
    if not category or not group:
        t1 = Team.query.get(team1_id)
        if t1:
            if not category:
                category = t1.category or ''
            if not group:
                group = t1.group or ''
                
    date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
    
    match = Match(
        team1_id=team1_id,
        team2_id=team2_id,
        date=date,
        location=location,
        cancha=cancha,
        referee_id=referee_id,
        category=category,
        group=group
    )
    db.session.add(match)
    db.session.commit()
    
    return jsonify({'success': True, 'match': {'id': match.id}})

@app.route('/admin/edit_team/<int:team_id>', methods=['POST'])
@login_required
def edit_team(team_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'No autorizado'}), 403

    team = Team.query.get_or_404(team_id)
    name = request.form.get('name', '').strip()
    coach = request.form.get('coach', '').strip()
    category = request.form.get('category', '')
    if category == 'Otro':
        category = request.form.get('custom_category', '').strip()
    group = request.form.get('group', '').strip()

    if not name:
        return jsonify({'error': 'El nombre del equipo es obligatorio'}), 400

    existing = Team.query.filter(Team.name == name, Team.id != team.id).first()
    if existing:
        return jsonify({'error': 'Ya existe otro equipo con ese nombre'}), 400

    team.name = name
    team.coach = coach
    team.category = category
    team.group = group
    db.session.commit()

    return jsonify({
        'success': True,
        'team': {
            'id': team.id,
            'name': team.name,
            'coach': team.coach,
            'category': team.category,
            'group': team.group
        }
    })

@app.route('/admin/delete_team/<int:team_id>', methods=['POST'])
@login_required
def delete_team(team_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'No autorizado'}), 403

    team = Team.query.get_or_404(team_id)

    Player.query.filter_by(team_id=team.id).delete()
    User.query.filter_by(team_id=team.id).update({'team_id': None})

    matches = Match.query.filter(
        (Match.team1_id == team.id) | (Match.team2_id == team.id)
    ).all()
    for match in matches:
        db.session.delete(match)

    db.session.delete(team)
    db.session.commit()

    return jsonify({'success': True})

@app.route('/admin/reset_tournament', methods=['POST'])
@login_required
def reset_tournament():
    if current_user.role != 'admin':
        return jsonify({'error': 'No autorizado'}), 403

    Set.query.delete()
    Match.query.delete()
    Player.query.delete()
    Team.query.delete()
    User.query.filter(User.role == 'team').update({'team_id': None})
    db.session.commit()

    return jsonify({'success': True})

# Rutas para Equipos
@app.route('/team/dashboard')
@login_required
def team_dashboard():
    if current_user.role != 'team':
        return redirect(url_for('index'))
    
    team = Team.query.get(current_user.team_id)
    if not team:
        flash('No tienes un equipo asignado')
        return redirect(url_for('index'))
    
    matches = Match.query.filter(
        (Match.team1_id == team.id) | (Match.team2_id == team.id)
    ).order_by(Match.date).all()
    
    return render_template('team_dashboard.html', team=team, matches=matches)

# Rutas para Árbitros
@app.route('/referee/dashboard')
@login_required
def referee_dashboard():
    if current_user.role != 'referee':
        return redirect(url_for('index'))
    
    assigned_matches = Match.query.filter_by(referee_id=current_user.id).order_by(Match.date).all()
    return render_template('referee_dashboard.html', matches=assigned_matches)

@app.route('/referee/match/<int:match_id>')
@login_required
def match_scoreboard(match_id):
    if current_user.role != 'referee':
        return redirect(url_for('index'))
    
    match = Match.query.get_or_404(match_id)
    if match.referee_id != current_user.id:
        flash('No estás asignado a este partido')
        return redirect(url_for('referee_dashboard'))
    
    return render_template('scoreboard.html', match=match)

def recalculate_all_team_stats():
    """Recalcula todas las estadísticas de los equipos desde cero basándose en partidos completados"""
    # Resetear todas las estadísticas
    teams = Team.query.all()
    for team in teams:
        team.points = 0
        team.wins = 0
        team.losses = 0
        team.sets_won = 0
        team.sets_lost = 0
    
    # Recalcular basándose en partidos completados
    completed_matches = Match.query.filter_by(status='completed').all()
    
    for match in completed_matches:
        team1 = Team.query.get(match.team1_id)
        team2 = Team.query.get(match.team2_id)
        
        if not team1 or not team2:
            continue
        
        # Contar sets ganados por cada equipo en este partido
        sets_team1 = 0
        sets_team2 = 0
        
        for s in match.sets:
            if s.completed:
                if s.team1_points > s.team2_points:
                    sets_team1 += 1
                elif s.team2_points > s.team1_points:
                    sets_team2 += 1
        
        # Determinar ganador y actualizar estadísticas
        if sets_team1 > sets_team2:
            # Team1 ganó
            team1.wins += 1
            team2.losses += 1
            team1.points += 3  # 3 puntos por victoria
        elif sets_team2 > sets_team1:
            # Team2 ganó
            team2.wins += 1
            team1.losses += 1
            team2.points += 3  # 3 puntos por victoria
        
        # Actualizar sets ganados/perdidos
        team1.sets_won += sets_team1
        team1.sets_lost += sets_team2
        team2.sets_won += sets_team2
        team2.sets_lost += sets_team1
    
    db.session.commit()

@app.route('/referee/update_score', methods=['POST'])
@login_required
def update_score():
    if current_user.role != 'referee':
        return jsonify({'error': 'No autorizado'}), 403
    
    match_id = request.json['match_id']
    set_number = request.json['set_number']
    team1_points = request.json['team1_points']
    team2_points = request.json['team2_points']
    completed = request.json.get('completed', False)
    
    match = Match.query.get(match_id)
    if not match:
        return jsonify({'error': 'Partido no encontrado'}), 404
        
    match_set = Set.query.filter_by(match_id=match_id, set_number=set_number).first()
    
    if not match_set:
        match_set = Set(match_id=match_id, set_number=set_number)
        db.session.add(match_set)
    
    match_set.team1_points = team1_points
    match_set.team2_points = team2_points
    match_set.completed = completed
    
    # Si el set está completado, determinar ganador
    if completed:
        if team1_points > team2_points:
            match_set.winner = match.team1_id
        else:
            match_set.winner = match.team2_id
    
    db.session.commit()
    
    # Verificar si el partido terminó
    sets_completed = Set.query.filter_by(match_id=match_id, completed=True).count()
    
    if sets_completed >= 3:
        # Calcular sets ganados por cada equipo
        sets_team1 = 0
        sets_team2 = 0
        for s in match.sets:
            if s.completed:
                if s.team1_points > s.team2_points:
                    sets_team1 += 1
                else:
                    sets_team2 += 1
        
        if sets_team1 == 3 or sets_team2 == 3:
            match.status = 'completed'
            match.winner_id = match.team1_id if sets_team1 == 3 else match.team2_id
            db.session.commit()
            # Recalcular todas las estadísticas de equipos
            recalculate_all_team_stats()
    
    return jsonify({'success': True})

@app.route('/referee/start_match', methods=['POST'])
@login_required
def start_match():
    """Inicia un partido (cambia estado de pending a active)"""
    if current_user.role != 'referee':
        return jsonify({'error': 'No autorizado'}), 403
    
    match_id = request.json['match_id']
    match = Match.query.get_or_404(match_id)
    
    if match.referee_id != current_user.id:
        return jsonify({'error': 'No estás asignado a este partido'}), 403
    
    if match.status != 'pending':
        return jsonify({'error': 'El partido ya ha comenzado o está completado'}), 400
    
    match.status = 'active'
    db.session.commit()
    
    return jsonify({'success': True, 'status': 'active'})

@app.route('/referee/complete_match', methods=['POST'])
@login_required
def complete_match():
    if current_user.role != 'referee':
        return jsonify({'error': 'No autorizado'}), 403
    
    match_id = request.json['match_id']
    match = Match.query.get_or_404(match_id)
    
    if match.referee_id != current_user.id:
        return jsonify({'error': 'No estás asignado a este partido'}), 403
    
    # Calcular sets ganados por cada equipo
    sets_team1 = 0
    sets_team2 = 0
    for s in match.sets:
        if s.completed:
            if s.team1_points > s.team2_points:
                sets_team1 += 1
            elif s.team2_points > s.team1_points:
                sets_team2 += 1
    
    # Determinar ganador basado en sets ganados
    if sets_team1 > sets_team2:
        match.winner_id = match.team1_id
    elif sets_team2 > sets_team1:
        match.winner_id = match.team2_id
    # Si hay empate, el árbitro puede decidir o dejar sin ganador
    
    match.status = 'completed'
    db.session.commit()
    
    # Recalcular todas las estadísticas de equipos
    recalculate_all_team_stats()
    
    return jsonify({'success': True, 'winner_id': match.winner_id})

@app.route('/api/match/<int:match_id>')
def get_match_status(match_id):
    """API para obtener el estado del partido en tiempo real"""
    match = Match.query.get_or_404(match_id)
    
    sets_data = []
    for s in match.sets:
        sets_data.append({
            'set_number': s.set_number,
            'team1_points': s.team1_points,
            'team2_points': s.team2_points,
            'completed': s.completed
        })
    
    # Calcular sets ganados
    sets_team1 = 0
    sets_team2 = 0
    for s in match.sets:
        if s.completed:
            if s.team1_points > s.team2_points:
                sets_team1 += 1
            elif s.team2_points > s.team1_points:
                sets_team2 += 1
    
    return jsonify({
        'match_id': match.id,
        'status': match.status,
        'winner_id': match.winner_id,
        'winner_name': match.winner.name if match.winner else None,
        'sets': sets_data,
        'sets_team1': sets_team1,
        'sets_team2': sets_team2
    })

@app.route('/matches')
def matches():
    matches_list = Match.query.order_by(Match.date).all()
    sponsor_banners = BannerImage.query.filter_by(image_type='sponsor', active=True).order_by(BannerImage.position).all()
    
    categories = sorted(list(set(m.category for m in matches_list if m.category)))
    groups = sorted(list(set(m.group for m in matches_list if m.group)))
    
    return render_template('matches.html', 
                           matches=matches_list, 
                           sponsor_banners=sponsor_banners,
                           categories=categories,
                           groups=groups)

@app.route('/teams')
def teams():
    teams_list = Team.query.filter_by(eliminated=False).order_by(
        Team.category,
        Team.group,
        Team.points.desc(),
        (Team.sets_won - Team.sets_lost).desc()
    ).all()
    
    # Group them by category and group
    grouped_teams = {}
    for t in teams_list:
        cat = t.category or "Sin Categoría"
        grp = t.group or "Sin Grupo"
        if cat not in grouped_teams:
            grouped_teams[cat] = {}
        if grp not in grouped_teams[cat]:
            grouped_teams[cat][grp] = []
        grouped_teams[cat][grp].append(t)
        
    return render_template('teams.html', grouped_teams=grouped_teams)

@app.route('/standings')
def standings():
    category = request.args.get('category')
    group = request.args.get('group')
    
    query = Team.query.filter_by(eliminated=False)
    if category:
        query = query.filter_by(category=category)
    if group:
        query = query.filter_by(group=group)
        
    teams_list = query.order_by(
        Team.points.desc(), 
        (Team.sets_won - Team.sets_lost).desc()
    ).all()
    
    return jsonify([{
        'id': t.id,
        'name': t.name,
        'points': t.points,
        'wins': t.wins,
        'losses': t.losses,
        'sets_won': t.sets_won,
        'sets_lost': t.sets_lost,
        'category': t.category,
        'group': t.group
    } for t in teams_list])

# ===== Rutas de gestión de imágenes/banners =====
@app.route('/admin/upload_banner', methods=['POST'])
@login_required
def upload_banner():
    if current_user.role != 'admin':
        return jsonify({'error': 'No autorizado'}), 403
    
    if 'image' not in request.files:
        return jsonify({'error': 'No se encontró archivo'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No se seleccionó archivo'}), 400
    
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(filepath)
        
        image_type = request.form.get('image_type', 'hero')
        title = request.form.get('title', '')
        position = request.form.get('position', 0)
        
        banner = BannerImage(
            filename=filename,
            image_type=image_type,
            title=title,
            position=int(position)
        )
        db.session.add(banner)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'banner': {
                'id': banner.id, 
                'filename': banner.filename, 
                'image_type': banner.image_type,
                'title': banner.title
            }
        })
    
    return jsonify({'error': 'Tipo de archivo no permitido'}), 400

@app.route('/admin/delete_banner/<int:banner_id>', methods=['POST'])
@login_required
def delete_banner(banner_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'No autorizado'}), 403
    
    banner = BannerImage.query.get_or_404(banner_id)
    
    # Delete file from disk
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], banner.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    
    db.session.delete(banner)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/admin/toggle_banner/<int:banner_id>', methods=['POST'])
@login_required
def toggle_banner(banner_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'No autorizado'}), 403
    
    banner = BannerImage.query.get_or_404(banner_id)
    banner.active = not banner.active
    db.session.commit()
    
    return jsonify({'success': True, 'active': banner.active})

def init_db():
    with app.app_context():
        db.create_all()
        
        # Migración automática para agregar columnas si no existen
        for table, col in [
            ("teams", "category"), ("teams", '"group"'),
            ("matches", "category"), ("matches", '"group"'), ("matches", "cancha")
        ]:
            try:
                db.session.execute(db.text(f"ALTER TABLE {table} ADD COLUMN {col} VARCHAR(50)"))
                db.session.commit()
            except Exception:
                db.session.rollback()
        
        # Crear usuario admin por defecto
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 7500))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)
