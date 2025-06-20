from flask import Flask, render_template, request, g, session, jsonify, redirect, url_for, flash
from db import get_db, close_db, query_devices, get_categories, get_statuses, init_db, get_all_users, CATEGORIAS_FIJAS
from datetime import datetime, date
import time
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'reemplaza_esto_por_un_valor_secreto_unico'


@app.before_request
def before_request():
    get_db()


@app.teardown_appcontext
def teardown_db(exception):
    close_db(exception)


@app.before_request
def require_login():
    allowed_routes = ['login', 'register_admin', 'static', 'cambiar_password']
    if request.endpoint not in allowed_routes and not session.get('user_id'):
        return redirect(url_for('login'))


def solo_roles(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Admin y Técnico pueden hacer todo
            if session.get('user_rol') in ['admin', 'tecnico']:
                return f(*args, **kwargs)
            if 'user_rol' not in session or session['user_rol'] not in roles:
                flash('No estás autorizado para acceder a esta sección.', 'danger')
                return redirect(request.referrer or url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@app.route("/")
def home():
    return redirect(url_for("dashboard"))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    # Medir tiempos de consulta
    tiempos = {}
    t0 = time.perf_counter()
    total_dispositivos = db.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
    tiempos['total_dispositivos'] = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    prestamos_activos = db.execute("SELECT COUNT(*) FROM devices WHERE status = 'En uso'").fetchone()[0]
    tiempos['prestamos_activos'] = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    mantenimientos = db.execute("SELECT COUNT(*) FROM devices WHERE status = 'Mantenimiento'").fetchone()[0]
    tiempos['mantenimientos'] = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    alertas_danados = db.execute("SELECT COUNT(*) FROM devices WHERE status = 'Dañado' OR status = 'Averiado' OR status = 'Roto'").fetchone()[0]
    tiempos['alertas_danados'] = (time.perf_counter() - t0) * 1000
    metrics = [
        {
            'title': 'Total de dispositivos',
            'value': total_dispositivos,
            'icon': 'bi-hdd-network',
            'subtitle': 'Dispositivos registrados'
        },
        {
            'title': 'Préstamos activos',
            'value': prestamos_activos,
            'icon': 'bi-arrow-left-right',
            'subtitle': 'Actualmente prestados'
        },
        {
            'title': 'Mantenimientos pendientes',
            'value': mantenimientos,
            'icon': 'bi-tools',
            'subtitle': 'Por realizar'
        },
        {
            'title': 'Alertas de dispositivos dañados',
            'value': alertas_danados,
            'icon': 'bi-exclamation-triangle',
            'subtitle': 'Requieren atención'
        }
    ]
    # Datos de rendimiento de la base de datos
    t0 = time.perf_counter()
    total_usuarios = db.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    tiempo_usuarios = (time.perf_counter() - t0) * 1000
    total_prestamos = prestamos_activos
    t0 = time.perf_counter()
    total_devoluciones = 0
    try:
        total_devoluciones = db.execute("SELECT COUNT(*) FROM devoluciones").fetchone()[0]
    except Exception:
        pass
    tiempo_devoluciones = (time.perf_counter() - t0) * 1000
    # Nueva zona: obtener alertas recientes (solo no resueltas)
    alertas_recientes = db.execute('SELECT * FROM alertas WHERE resuelto=0 ORDER BY fecha DESC LIMIT 5').fetchall()
    rendimiento = {
        'total_usuarios': total_usuarios,
        'total_prestamos': total_prestamos,
        'total_devoluciones': total_devoluciones,
        'tiempos': tiempos,
        'tiempo_usuarios': tiempo_usuarios,
        'tiempo_devoluciones': tiempo_devoluciones
    }
    return render_template("dashboard.html", metrics=metrics, rendimiento=rendimiento, alertas_recientes=alertas_recientes)


@app.route("/usuarios", methods=["GET", "POST"])
@solo_roles('admin', 'jefe')
def usuarios():
    db = get_db()
    mensaje = None
    if request.method == 'POST':
        if request.form.get('accion') == 'eliminar':
            id_usuario = request.form.get('id')
            if id_usuario:
                db.execute('DELETE FROM usuarios WHERE id = ?', (id_usuario,))
                db.commit()
                mensaje = 'Usuario eliminado correctamente.'
        elif request.form.get('accion') == 'editar':
            id_usuario = request.form.get('id')
            nombre = request.form.get('nombre')
            correo = request.form.get('correo')
            rol = request.form.get('rol')
            if id_usuario and nombre and correo and rol:
                db.execute('UPDATE usuarios SET nombre=?, correo=?, rol=? WHERE id=?', (nombre, correo, rol, id_usuario))
                db.commit()
                mensaje = 'Usuario editado correctamente.'
            else:
                mensaje = 'Todos los campos son obligatorios para editar.'
        else:
            nombre = request.form.get('nombre')
            correo = request.form.get('correo')
            rol = request.form.get('rol')
            if nombre and correo and rol:
                password_hash = generate_password_hash('12345')
                db.execute('INSERT INTO usuarios (nombre, correo, password, rol) VALUES (?, ?, ?, ?)', (nombre, correo, password_hash, rol))
                db.commit()
                mensaje = 'Usuario agregado correctamente. Contraseña por defecto: 12345'
            else:
                mensaje = 'Todos los campos son obligatorios.'
    search = request.args.get('search', '').strip()
    if search:
        usuarios = db.execute('SELECT * FROM usuarios WHERE LOWER(nombre) LIKE ? OR LOWER(correo) LIKE ?', (f'%{search.lower()}%', f'%{search.lower()}%')).fetchall()
    else:
        usuarios = db.execute('SELECT * FROM usuarios').fetchall()
    return render_template('usuarios.html', usuarios=usuarios, mensaje=mensaje, search=search)


@app.route("/devices", methods=["GET", "POST"])
@solo_roles('admin', 'jefe', 'tecnico')
def dispositivos():
    db = get_db()
    mensaje = None
    # Agregar dispositivo
    if request.method == "POST" and request.form.get("accion") == "agregar":
        nombre = request.form.get("nombre")
        categoria = request.form.get("categoria")
        ubicacion = request.form.get("ubicacion")
        if nombre and categoria and ubicacion:
            db.execute(
                "INSERT INTO devices (name, category, status, location, supervisor) VALUES (?, ?, 'Disponible', ?, '')",
                (nombre, categoria, ubicacion)
            )
            db.commit()
            mensaje = "Dispositivo agregado correctamente."
        else:
            mensaje = "Todos los campos son obligatorios."
    # Editar dispositivo
    if request.method == "POST" and request.form.get("accion") == "editar":
        id_disp = request.form.get("id")
        nombre = request.form.get("nombre")
        categoria = request.form.get("categoria")
        ubicacion = request.form.get("ubicacion")
        if id_disp and nombre and categoria and ubicacion:
            db.execute(
                "UPDATE devices SET name=?, category=?, location=? WHERE id=?",
                (nombre, categoria, ubicacion, id_disp)
            )
            db.commit()
            mensaje = "Dispositivo editado correctamente."
        else:
            mensaje = "Todos los campos son obligatorios para editar."
    # Eliminar dispositivo
    if request.method == "POST" and request.form.get("accion") == "eliminar":
        id_disp = request.form.get("id")
        if id_disp:
            db.execute("DELETE FROM devices WHERE id=?", (id_disp,))
            db.commit()
            mensaje = "Dispositivo eliminado."
    # Filtros y búsqueda
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    status = request.args.get('status', '')
    devices = query_devices(search, category, status)
    categories = CATEGORIAS_FIJAS
    statuses = get_statuses()
    return render_template(
        'devices.html',
        devices=devices,
        search=search,
        category=category,
        status=status,
        categories=categories,
        statuses=statuses,
        mensaje=mensaje
    )


@app.cli.command('init-db')
def initdb_command():
    """Inicializa la base de datos."""
    init_db()
    print('Base de datos inicializada.')


@app.route('/prestamos', methods=['GET', 'POST'])
def gestionar_prestamos():
    db = get_db()
    # Buscar dispositivos disponibles
    search = request.args.get('search', '')
    query = "SELECT * FROM devices WHERE status = 'Disponible'"
    params = []
    if search:
        query += " AND (name LIKE ? OR location LIKE ? OR category LIKE ? OR id LIKE ?)"
        params += [f"%{search}%"] * 4
    disponibles = db.execute(query, params).fetchall()

    # Carrito de préstamo en sesión
    if 'cart' not in session:
        session['cart'] = []
    cart = session['cart']

    # Obtener usuarios para el menú desplegable
    usuarios = get_all_users()

    # Agregar dispositivo al carrito
    if request.method == 'POST' and request.form.get('add_id'):
        add_id = int(request.form['add_id'])
        if add_id not in cart:
            cart.append(add_id)
            session['cart'] = cart
        return redirect(url_for('gestionar_prestamos', search=search))

    # Registrar préstamo
    if request.method == 'POST' and request.form.get('supervisor'):
        supervisor = request.form['supervisor']
        codigo_evento = request.form.get('codigo_evento')
        ubicacion_evento = request.form.get('ubicacion_evento')
        for device_id in cart:
            db.execute("UPDATE devices SET status = 'En uso', supervisor = ?, location = ? WHERE id = ?", (supervisor, ubicacion_evento, device_id))
            db.execute("INSERT INTO prestamos (device_id, supervisor, location, codigo_evento) VALUES (?, ?, ?, ?)", (device_id, supervisor, ubicacion_evento, codigo_evento))
        db.commit()
        session['cart'] = []
        return render_template('prestamo_exito.html', supervisor=supervisor, codigo_evento=codigo_evento, ubicacion_evento=ubicacion_evento)

    # Obtener info de dispositivos en carrito
    carrito_dispositivos = []
    if cart:
        placeholders = ','.join(['?']*len(cart))
        carrito_dispositivos = db.execute(f"SELECT * FROM devices WHERE id IN ({placeholders})", cart).fetchall()

    return render_template('prestamos.html', disponibles=disponibles, carrito=carrito_dispositivos, search=search, usuarios=usuarios)


@app.route('/prestamos/qr', methods=['POST'])
def agregar_por_qr():
    device_id = request.form.get('device_id')
    db = get_db()
    # Buscar por ID o nombre
    device = db.execute("SELECT * FROM devices WHERE (id = ? OR name = ?) AND status = 'Disponible'", (device_id, device_id)).fetchone()
    if device:
        if 'cart' not in session:
            session['cart'] = []
        cart = session['cart']
        if device['id'] not in cart:
            cart.append(device['id'])
            session['cart'] = cart
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'No existe o no disponible'})

@app.route('/devoluciones', methods=['GET', 'POST'])
def gestionar_devoluciones():
    db = get_db()
    # Filtros de búsqueda
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    query = "SELECT * FROM devices WHERE status = 'En uso'"
    params = []
    if search:
        query += " AND (name LIKE ? OR location LIKE ? OR supervisor LIKE ? OR id LIKE ?)"
        params += [f"%{search}%"] * 4
    if status:
        query += " AND status = ?"
        params.append(status)
    activos = db.execute(query, params).fetchall()

    # Carrito de devolución en sesión
    if 'return_cart' not in session:
        session['return_cart'] = []
    return_cart = session['return_cart']

    # Obtener usuarios para el menú desplegable
    usuarios = get_all_users()

    # Agregar dispositivo al carrito
    if request.method == 'POST' and request.form.get('add_id'):
        add_id = int(request.form['add_id'])
        if add_id not in return_cart:
            return_cart.append(add_id)
            session['return_cart'] = return_cart
        return redirect(url_for('gestionar_devoluciones', search=search, status=status))

    # Registrar devolución
    if request.method == 'POST' and request.form.get('devolver'):
        supervisor = request.form.get('supervisor')
        for device_id in return_cart:
            # Al devolver, la ubicación predeterminada es 'soporte'
            db.execute("UPDATE devices SET status = 'Disponible', supervisor = ?, location = 'soporte' WHERE id = ?", (supervisor, device_id))
            db.execute("INSERT INTO devoluciones (device_id, supervisor, location, codigo_evento) VALUES (?, ?, ?, '')", (device_id, supervisor, 'soporte'))
        db.commit()
        session['return_cart'] = []
        return render_template('devolucion_exito.html')

    # Obtener info de dispositivos en carrito
    carrito_dispositivos = []
    if return_cart:
        placeholders = ','.join(['?']*len(return_cart))
        carrito_dispositivos = db.execute(f"SELECT * FROM devices WHERE id IN ({placeholders})", return_cart).fetchall()

    # Métricas de devoluciones
    metricas = {'hoy': 0, 'totales': 0, 'pendientes': 0}
    try:
        metricas['totales'] = db.execute('SELECT COUNT(*) FROM devoluciones').fetchone()[0]
        metricas['hoy'] = db.execute('SELECT COUNT(*) FROM devoluciones WHERE fecha = ?', (date.today(),)).fetchone()[0]
    except Exception:
        metricas['totales'] = metricas['hoy'] = 0
    metricas['pendientes'] = db.execute("SELECT COUNT(*) FROM devices WHERE status = 'En uso'").fetchone()[0]

    return render_template('devoluciones.html', activos=activos, carrito=carrito_dispositivos, search=search, status=status, metricas=metricas, usuarios=usuarios)

@app.route('/devoluciones/qr', methods=['POST'])
def agregar_devolucion_qr():
    device_id = request.form.get('device_id')
    db = get_db()
    # Buscar por ID o nombre, solo dispositivos en uso
    device = db.execute("SELECT * FROM devices WHERE (id = ? OR name = ?) AND status = 'En uso'", (device_id, device_id)).fetchone()
    if device:
        if 'return_cart' not in session:
            session['return_cart'] = []
        return_cart = session['return_cart']
        if device['id'] not in return_cart:
            return_cart.append(device['id'])
            session['return_cart'] = return_cart
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'No existe o no está en uso'})

@app.route('/alertas', methods=['GET', 'POST'])
def alertas():
    db = get_db()
    mensaje = None
    # Agregar alerta
    if request.method == 'POST' and 'comentario' in request.form:
        dispositivo = request.form.get('dispositivo')
        comentario = request.form.get('comentario')
        boton_derecho = request.form.get('boton_derecho')
        boton_izquierdo = request.form.get('boton_izquierdo')
        mica_danada = request.form.get('mica_danada')
        if dispositivo and comentario:
            db.execute(
                "INSERT INTO alertas (dispositivo, comentario, boton_derecho, boton_izquierdo, mica_danada, fecha) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (dispositivo, comentario, boton_derecho, boton_izquierdo, mica_danada)
            )
            db.commit()
            mensaje = 'Alerta registrada correctamente.'
        else:
            mensaje = 'Debes seleccionar un dispositivo y escribir un comentario.'
    # Filtros GET
    search = request.args.get('search', '').strip()
    estado = request.args.get('estado', '')
    dispositivo_sel = request.args.get('dispositivo', '')
    query = 'SELECT * FROM alertas WHERE 1=1'
    params = []
    if search:
        query += ' AND (dispositivo LIKE ? OR comentario LIKE ? OR boton_derecho LIKE ? OR boton_izquierdo LIKE ? OR mica_danada LIKE ? OR fecha LIKE ? OR reparacion LIKE ?)' 
        params += [f'%{search}%'] * 7
    if estado in ['0', '1']:
        query += ' AND resuelto=?'
        params.append(int(estado))
    if dispositivo_sel:
        query += ' AND dispositivo=?'
        params.append(dispositivo_sel)
    query += ' ORDER BY fecha DESC'
    alertas = db.execute(query, params).fetchall()
    dispositivos = db.execute('SELECT name FROM devices').fetchall()
    return render_template('alertas.html', dispositivos=dispositivos, alertas=alertas, mensaje=mensaje)

@app.route('/alerta_reparar/<int:alerta_id>', methods=['POST'])
def alerta_reparar(alerta_id):
    if session.get('user_rol') == 'supervisor':
        flash('No estás autorizado para resolver alertas.', 'danger')
        return redirect(url_for('alertas'))
    db = get_db()
    if 'reparacion' in request.form:
        reparacion = request.form.get('reparacion')
        if reparacion:
            db.execute('UPDATE alertas SET reparacion=?, resuelto=1 WHERE id=?', (reparacion, alerta_id))
            db.commit()
    else:
        db.execute('DELETE FROM alertas WHERE id=?', (alerta_id,))
        db.commit()
    return redirect(url_for('alertas'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        correo = request.form['correo']
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM usuarios WHERE correo = ?', (correo,)).fetchone()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_nombre'] = user['nombre']
            session['user_rol'] = user['rol']
            # Si la contraseña es la por defecto, forzar cambio
            if check_password_hash(user['password'], '12345'):
                session['forzar_cambio'] = True
                return redirect(url_for('cambiar_password'))
            else:
                session.pop('forzar_cambio', None)
                return redirect(url_for('dashboard'))
        else:
            error = 'Correo o contraseña incorrectos.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/register_admin', methods=['GET', 'POST'])
def register_admin():
    error = None
    success = None
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        password = request.form['password']
        password2 = request.form['password2']
        if not (nombre and correo and password and password2):
            error = 'Todos los campos son obligatorios.'
        elif password != password2:
            error = 'Las contraseñas no coinciden.'
        else:
            db = get_db()
            existe = db.execute('SELECT * FROM usuarios WHERE correo = ?', (correo,)).fetchone()
            if existe:
                error = 'El correo ya está registrado.'
            else:
                hash_pw = generate_password_hash(password)
                db.execute('INSERT INTO usuarios (nombre, correo, password, rol) VALUES (?, ?, ?, ?)', (nombre, correo, hash_pw, 'admin'))
                db.commit()
                success = 'Administrador registrado correctamente. Ahora puedes iniciar sesión.'
    return render_template('register_admin.html', error=error, success=success)

# Nueva ruta para cambiar contraseña obligatoriamente
@app.route('/cambiar_password', methods=['GET', 'POST'])
def cambiar_password():
    if 'user_id' not in session or not session.get('forzar_cambio'):
        return redirect(url_for('login'))
    error = None
    success = None
    if request.method == 'POST':
        nueva = request.form['nueva']
        nueva2 = request.form['nueva2']
        if not nueva or not nueva2:
            error = 'Debes completar ambos campos.'
        elif nueva != nueva2:
            error = 'Las contraseñas no coinciden.'
        elif nueva == '12345':
            error = 'La nueva contraseña no puede ser la predeterminada.'
        else:
            db = get_db()
            hash_pw = generate_password_hash(nueva)
            db.execute('UPDATE usuarios SET password=? WHERE id=?', (hash_pw, session['user_id']))
            db.commit()
            session.pop('forzar_cambio', None)
            success = 'Contraseña cambiada correctamente. Ahora puedes usar el sistema.'
            return redirect(url_for('dashboard'))
    return render_template('cambiar_password.html', error=error, success=success)

@app.route('/historial')
def historial():
    db = get_db()
    # Consulta de movimientos (préstamos y devoluciones)
    query = '''
        SELECT 'Préstamo' as tipo, d.id as dispositivo_id, d.name as dispositivo, d.supervisor, d.location as ubicacion, p.codigo_evento, p.fecha as fecha, NULL as devuelto_por
        FROM prestamos p
        JOIN devices d ON p.device_id = d.id
        UNION ALL
        SELECT 'Devolución' as tipo, d.id as dispositivo_id, d.name as dispositivo, dv.supervisor, d.location as ubicacion, dv.codigo_evento, dv.fecha as fecha, dv.supervisor as devuelto_por
        FROM devoluciones dv
        JOIN devices d ON dv.device_id = d.id
        ORDER BY fecha DESC
    '''
    movimientos = db.execute(query).fetchall()
    # Filtros y búsqueda
    search = request.args.get('search', '')
    filtro_tipo = request.args.get('filtro_tipo', '')
    resultados = []
    for m in movimientos:
        coincide_tipo = (not filtro_tipo or m['tipo'].lower() == filtro_tipo.lower())
        coincide_search = (
            not search or
            search.lower() in str(m['dispositivo']).lower() or
            search.lower() in str(m['supervisor']).lower() or
            search.lower() in str(m['ubicacion']).lower() or
            search.lower() in str(m['codigo_evento']).lower() or
            (m['devuelto_por'] and search.lower() in str(m['devuelto_por']).lower())
        )
        if coincide_tipo and coincide_search:
            resultados.append(m)
    tipos = ['Préstamo', 'Devolución']
    return render_template('historial.html', movimientos=resultados, search=search, filtro_tipo=filtro_tipo, tipos=tipos)
