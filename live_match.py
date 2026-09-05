from datetime import datetime
from database import db
from models import Set, MatchEvent

SET_POINTS = 12
COURT_CHANGE_AT = 7
SUDDEN_DEATH_AT = 11
SETS_TO_WIN = 3


def elapsed_seconds(match):
    if not match.started_at:
        return 0
    return max(0, int((datetime.utcnow() - match.started_at).total_seconds()))


def format_minute(seconds):
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def set_wins(match):
    t1 = t2 = 0
    for s in match.sets:
        if s.completed:
            if s.team1_points > s.team2_points:
                t1 += 1
            elif s.team2_points > s.team1_points:
                t2 += 1
    return t1, t2


def court_players(team, flipped=False):
    players = sorted(
        list(team.players or []),
        key=lambda p: (p.number is None, p.number or 99, p.name or ''),
    )
    items = []
    for i in range(2):
        if i < len(players):
            p = players[i]
            items.append({
                'id': p.id,
                'number': p.number if p.number is not None else i + 1,
                'name': p.name,
            })
        else:
            items.append({'id': None, 'number': i + 1, 'name': str(i + 1)})
    if flipped:
        items.reverse()
    return items


def log_event(match, current, event_type, team=None, note=None, signature=None):
    event = MatchEvent(
        match_id=match.id,
        set_number=current.set_number if current else None,
        event_type=event_type,
        team=team,
        elapsed_sec=elapsed_seconds(match),
        note=note,
        signature=signature,
        t1_points=current.team1_points if current else 0,
        t2_points=current.team2_points if current else 0,
    )
    db.session.add(event)
    return event


def ensure_started(match):
    if match.status == 'completed':
        return False, 'El partido ya terminó'
    if match.status == 'pending':
        match.status = 'active'
    if not match.started_at:
        match.started_at = datetime.utcnow()
    if match.serve_team not in (1, 2):
        match.serve_team = 1
    if match.left_is_team1 is None:
        match.left_is_team1 = True
    return True, None


def ensure_current_set(match):
    wins1, wins2 = set_wins(match)
    if wins1 >= SETS_TO_WIN or wins2 >= SETS_TO_WIN:
        return None
    active = [s for s in match.sets if not s.completed]
    if active:
        return min(active, key=lambda s: s.set_number)
    if len(match.sets) >= 5:
        return None
    nxt = max([s.set_number for s in match.sets], default=0) + 1
    current = Set(
        match_id=match.id,
        set_number=nxt,
        team1_points=0,
        team2_points=0,
        completed=False,
        court_change_pending=False,
        court_changed=False,
        sudden_death=False,
    )
    match.sets.append(current)
    db.session.flush()
    return current


def close_current_set(match, current):
    t1 = current.team1_points or 0
    t2 = current.team2_points or 0
    if t1 == t2:
        return False, 'El set está empatado; anota un punto o desempata antes de cerrarlo'
    current.completed = True
    current.winner = match.team1_id if t1 > t2 else match.team2_id
    current.court_change_pending = False
    log_event(match, current, 'set_won', team=1 if t1 > t2 else 2, note='Set cerrado por el árbitro')
    return True, None


def apply_complete_set(match):
    ok, err = ensure_started(match)
    if not ok:
        return False, err
    current = ensure_current_set(match)
    if not current:
        return False, 'No hay set activo'
    ok, err = close_current_set(match, current)
    if not ok:
        return False, err
    if not maybe_finish_match(match):
        ensure_current_set(match)
    return True, None


def apply_complete_match(match):
    ok, err = ensure_started(match)
    if not ok:
        return False, err
    current = next((s for s in match.sets if not s.completed), None)
    if current and ((current.team1_points or 0) != (current.team2_points or 0)):
        close_current_set(match, current)
    elif current and (current.team1_points or 0) == 0 and (current.team2_points or 0) == 0:
        if current in match.sets:
            match.sets.remove(current)
        db.session.delete(current)

    wins1, wins2 = set_wins(match)
    if wins1 == 0 and wins2 == 0:
        return False, 'No hay sets ganados para definir un ganador'
    if wins1 > wins2:
        match.winner_id = match.team1_id
    elif wins2 > wins1:
        match.winner_id = match.team2_id
    else:
        return False, 'Los sets están empatados; cierra el set actual o anota un punto más'
    match.status = 'completed'
    log_event(match, None, 'match_complete', team=1 if wins1 > wins2 else 2, note='Partido finalizado por el árbitro')
    return True, None


def apply_set_rules(match, current, scoring_team):
    t1 = current.team1_points or 0
    t2 = current.team2_points or 0

    if t1 >= SUDDEN_DEATH_AT and t2 >= SUDDEN_DEATH_AT:
        current.sudden_death = True

    # En muerte súbita el siguiente punto gana el set (no se exige diferencia de 2).
    if current.sudden_death and t1 != t2:
        current.completed = True
        current.winner = match.team1_id if t1 > t2 else match.team2_id
        current.court_change_pending = False
        return 'set'

    if (t1 >= SET_POINTS or t2 >= SET_POINTS) and abs(t1 - t2) >= 2:
        current.completed = True
        current.winner = match.team1_id if t1 > t2 else match.team2_id
        current.court_change_pending = False
        return 'set'

    if (
        not current.court_changed
        and not current.court_change_pending
        and not current.sudden_death
        and (t1 == COURT_CHANGE_AT or t2 == COURT_CHANGE_AT)
        and t1 <= COURT_CHANGE_AT
        and t2 <= COURT_CHANGE_AT
    ):
        current.court_change_pending = True
        log_event(match, current, 'court_change_due')
        return 'court'

    return None


def apply_point(match, team):
    ok, err = ensure_started(match)
    if not ok:
        return False, err
    if team not in (1, 2):
        return False, 'Equipo inválido'
    current = ensure_current_set(match)
    if not current:
        return False, 'El partido ya no tiene sets por jugar'
    if current.court_change_pending:
        return False, 'Debes aceptar el cambio de cancha (7 puntos)'

    held_serve = match.serve_team == team
    if team == 1:
        current.team1_points = (current.team1_points or 0) + 1
    else:
        current.team2_points = (current.team2_points or 0) + 1

    match.serve_team = team
    log_event(match, current, 'point', team=team)

    if held_serve:
        if team == 1:
            match.switch_t1 = not bool(match.switch_t1)
        else:
            match.switch_t2 = not bool(match.switch_t2)
        log_event(match, current, 'switch', team=team, note='Switch por punto en propio saque')

    result = apply_set_rules(match, current, team)
    if result == 'set':
        log_event(match, current, 'set_won', team=team)
        maybe_finish_match(match)
        if match.status != 'completed':
            ensure_current_set(match)
    return True, None


def apply_timeout(match, team):
    ok, err = ensure_started(match)
    if not ok:
        return False, err
    if team not in (1, 2):
        return False, 'Equipo inválido'
    if team == 1 and match.timeout_t1:
        return False, 'Ese equipo ya usó su único tiempo muerto'
    if team == 2 and match.timeout_t2:
        return False, 'Ese equipo ya usó su único tiempo muerto'
    current = ensure_current_set(match)
    if team == 1:
        match.timeout_t1 = True
    else:
        match.timeout_t2 = True
    log_event(match, current, 'timeout', team=team)
    return True, None


def apply_delay(match, team, note, signature):
    ok, err = ensure_started(match)
    if not ok:
        return False, err
    if not (signature or '').strip():
        return False, 'La demora requiere firma en observaciones'
    current = ensure_current_set(match)
    obs = match.observations or ''
    line = f"[{format_minute(elapsed_seconds(match))}] Demora equipo {team}: {(note or '').strip()} — Firma: {signature.strip()}"
    match.observations = (obs + '\n' if obs else '') + line
    log_event(match, current, 'delay', team=team, note=note, signature=signature.strip())
    return True, None


def apply_admonition(match, team, note):
    ok, err = ensure_started(match)
    if not ok:
        return False, err
    current = ensure_current_set(match)
    log_event(match, current, 'admonition', team=team, note=note)
    return True, None


def apply_switch(match, team):
    ok, err = ensure_started(match)
    if not ok:
        return False, err
    if team not in (1, 2):
        return False, 'Equipo inválido'
    current = ensure_current_set(match)
    if team == 1:
        match.switch_t1 = not bool(match.switch_t1)
    else:
        match.switch_t2 = not bool(match.switch_t2)
    log_event(match, current, 'switch', team=team, note='Cambio de switch')
    return True, None


def apply_court_change(match):
    ok, err = ensure_started(match)
    if not ok:
        return False, err
    current = ensure_current_set(match)
    if not current or not current.court_change_pending:
        return False, 'No hay cambio de cancha pendiente'
    match.left_is_team1 = not bool(match.left_is_team1)
    current.court_change_pending = False
    current.court_changed = True
    log_event(match, current, 'court_change', note='Cambio de cancha a los 7 puntos')
    return True, None


def swap_sides(match):
    ok, err = ensure_started(match)
    if not ok:
        return False, err
    current = ensure_current_set(match)
    match.left_is_team1 = not bool(match.left_is_team1)
    log_event(match, current, 'swap_sides', note='Cambio de campo visual')
    return True, None


def apply_undo(match):
    ok, err = ensure_started(match)
    if not ok:
        return False, err
    events = MatchEvent.query.filter_by(match_id=match.id).order_by(MatchEvent.id.desc()).all()
    if not events:
        return False, 'No hay jugadas para deshacer'

    last_point = next((e for e in events if e.event_type == 'point'), None)
    if last_point:
        to_delete = [e for e in events if e.id >= last_point.id]
        current = Set.query.filter_by(match_id=match.id, set_number=last_point.set_number).first()
        if current:
            if last_point.team == 1 and (current.team1_points or 0) > 0:
                current.team1_points -= 1
            elif last_point.team == 2 and (current.team2_points or 0) > 0:
                current.team2_points -= 1
            current.completed = False
            current.winner = None
            current.sudden_death = (
                (current.team1_points or 0) >= SUDDEN_DEATH_AT
                and (current.team2_points or 0) >= SUDDEN_DEATH_AT
            )
            if (current.team1_points or 0) < COURT_CHANGE_AT and (current.team2_points or 0) < COURT_CHANGE_AT:
                current.court_change_pending = False
                current.court_changed = False
        match.status = 'active'
        match.winner_id = None
        older = [e for e in events if e.id < last_point.id and e.event_type == 'point']
        match.serve_team = older[0].team if older else 1
        if any(e.event_type == 'switch' and e.team == last_point.team for e in to_delete):
            if last_point.team == 1:
                match.switch_t1 = not bool(match.switch_t1)
            else:
                match.switch_t2 = not bool(match.switch_t2)
        if any(e.event_type == 'court_change' for e in to_delete) and current:
            match.left_is_team1 = not bool(match.left_is_team1)
            current.court_changed = False
            current.court_change_pending = True
        for e in to_delete:
            db.session.delete(e)
        return True, None

    last = events[0]
    current = Set.query.filter_by(match_id=match.id, set_number=last.set_number).first() if last.set_number else None
    if last.event_type == 'timeout':
        if last.team == 1:
            match.timeout_t1 = False
        elif last.team == 2:
            match.timeout_t2 = False
    elif last.event_type == 'switch':
        if last.team == 1:
            match.switch_t1 = not bool(match.switch_t1)
        elif last.team == 2:
            match.switch_t2 = not bool(match.switch_t2)
    elif last.event_type == 'court_change' and current:
        match.left_is_team1 = not bool(match.left_is_team1)
        current.court_changed = False
        current.court_change_pending = True
    elif last.event_type == 'swap_sides':
        match.left_is_team1 = not bool(match.left_is_team1)
    db.session.delete(last)
    return True, None


def serialize_live(match):
    current = None
    for s in sorted(match.sets, key=lambda x: x.set_number):
        if not s.completed:
            current = s
            break
    if current is None and match.sets:
        current = max(match.sets, key=lambda x: x.set_number)

    wins1, wins2 = set_wins(match)
    events = MatchEvent.query.filter_by(match_id=match.id).order_by(MatchEvent.id.desc()).limit(80).all()
    t1 = current.team1_points if current else 0
    t2 = current.team2_points if current else 0
    left_is_t1 = True if match.left_is_team1 is None else bool(match.left_is_team1)

    def side_payload(team_no):
        team = match.home_team if team_no == 1 else match.away_team
        flipped = bool(match.switch_t1 if team_no == 1 else match.switch_t2)
        timeout_used = bool(match.timeout_t1 if team_no == 1 else match.timeout_t2)
        return {
            'team': team_no,
            'id': team.id,
            'name': team.name,
            'points': t1 if team_no == 1 else t2,
            'sets': wins1 if team_no == 1 else wins2,
            'has_ball': match.serve_team == team_no,
            'timeout_used': timeout_used,
            'players': court_players(team, flipped),
        }

    return {
        'match_id': match.id,
        'status': match.status,
        'winner_id': match.winner_id,
        'winner_name': match.winner.name if match.winner else None,
        'location': match.location,
        'cancha': match.cancha,
        'elapsed_sec': elapsed_seconds(match),
        'elapsed_label': format_minute(elapsed_seconds(match)),
        'observations': match.observations or '',
        'set_number': current.set_number if current else 1,
        'team1_points': t1,
        'team2_points': t2,
        'sets_team1': wins1,
        'sets_team2': wins2,
        'serve_team': match.serve_team or 1,
        'left_is_team1': left_is_t1,
        'court_change_pending': bool(current.court_change_pending) if current else False,
        'court_changed': bool(current.court_changed) if current else False,
        'sudden_death': bool(current.sudden_death) if current else False,
        'locked': bool(current.court_change_pending) if current else False,
        'completed': match.status == 'completed',
        'left': side_payload(1 if left_is_t1 else 2),
        'right': side_payload(2 if left_is_t1 else 1),
        'sets': [{
            'set_number': s.set_number,
            'team1_points': s.team1_points,
            'team2_points': s.team2_points,
            'completed': s.completed,
            'sudden_death': bool(s.sudden_death),
            'court_changed': bool(s.court_changed),
        } for s in sorted(match.sets, key=lambda x: x.set_number)],
        'events': [{
            'id': e.id,
            'type': e.event_type,
            'team': e.team,
            'set': e.set_number,
            'minute': format_minute(e.elapsed_sec or 0),
            'note': e.note,
            'signature': bool(e.signature),
            'score': f"{e.t1_points}-{e.t2_points}",
        } for e in events],
        'rules': {
            'set_points': SET_POINTS,
            'court_change_at': COURT_CHANGE_AT,
            'sudden_death_at': SUDDEN_DEATH_AT,
            'timeouts': 1,
            'sets_to_win': SETS_TO_WIN,
        },
    }
