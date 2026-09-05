from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from database import db
from datetime import datetime

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, team, referee
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Team(db.Model):
    __tablename__ = 'teams'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    coach = db.Column(db.String(100))
    points = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    sets_won = db.Column(db.Integer, default=0)
    sets_lost = db.Column(db.Integer, default=0)
    eliminated = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(50), nullable=True)
    group = db.Column(db.String(50), nullable=True)
    
    players = db.relationship('Player', backref='team', lazy=True)
    matches_home = db.relationship('Match', foreign_keys='Match.team1_id', backref='home_team')
    matches_away = db.relationship('Match', foreign_keys='Match.team2_id', backref='away_team')

class Player(db.Model):
    __tablename__ = 'players'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    number = db.Column(db.Integer)
    position = db.Column(db.String(50))
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'))

class Match(db.Model):
    __tablename__ = 'matches'
    
    id = db.Column(db.Integer, primary_key=True)
    team1_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    team2_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200))
    cancha = db.Column(db.String(50), nullable=True)
    referee_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.String(20), default='pending')  # pending, active, completed
    winner_id = db.Column(db.Integer, db.ForeignKey('teams.id'))
    category = db.Column(db.String(50), nullable=True)
    group = db.Column(db.String(50), nullable=True)
    serve_team = db.Column(db.Integer, default=1)  # 1 local, 2 visitante
    left_is_team1 = db.Column(db.Boolean, default=True)
    started_at = db.Column(db.DateTime)
    timeout_t1 = db.Column(db.Boolean, default=False)
    timeout_t2 = db.Column(db.Boolean, default=False)
    switch_t1 = db.Column(db.Boolean, default=False)
    switch_t2 = db.Column(db.Boolean, default=False)
    observations = db.Column(db.Text)

    sets = db.relationship('Set', backref='match', lazy=True, cascade='all, delete-orphan')
    events = db.relationship('MatchEvent', backref='match', lazy=True, cascade='all, delete-orphan', order_by='MatchEvent.id')
    referee = db.relationship('User', foreign_keys=[referee_id])
    winner = db.relationship('Team', foreign_keys=[winner_id], backref='won_matches')

class Set(db.Model):
    __tablename__ = 'sets'
    
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=False)
    set_number = db.Column(db.Integer, nullable=False)
    team1_points = db.Column(db.Integer, default=0)
    team2_points = db.Column(db.Integer, default=0)
    completed = db.Column(db.Boolean, default=False)
    winner = db.Column(db.Integer, db.ForeignKey('teams.id'))
    court_change_pending = db.Column(db.Boolean, default=False)
    court_changed = db.Column(db.Boolean, default=False)
    sudden_death = db.Column(db.Boolean, default=False)

class MatchEvent(db.Model):
    __tablename__ = 'match_events'

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=False)
    set_number = db.Column(db.Integer)
    event_type = db.Column(db.String(30), nullable=False)
    team = db.Column(db.Integer)  # 1 o 2
    elapsed_sec = db.Column(db.Integer, default=0)
    note = db.Column(db.Text)
    signature = db.Column(db.Text)
    t1_points = db.Column(db.Integer, default=0)
    t2_points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BannerImage(db.Model):
    __tablename__ = 'banner_images'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    image_type = db.Column(db.String(50), nullable=False)  # hero, sponsor, category
    title = db.Column(db.String(200))
    position = db.Column(db.Integer, default=0)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)