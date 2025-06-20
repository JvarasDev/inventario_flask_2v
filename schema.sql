-- Tabla de dispositivos para la app Flask
DROP TABLE IF EXISTS devices;
CREATE TABLE devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL,
    location TEXT NOT NULL,
    supervisor TEXT
);

INSERT INTO devices (name, category, status, location, supervisor) VALUES
('Laptop HP', 'Computadora', 'Disponible', 'Oficina 1', 'Juan Pérez'),
('Proyector Epson', 'Proyector', 'En uso', 'Sala de reuniones', 'Ana López'),
('Impresora Canon', 'Impresora', 'Mantenimiento', 'Oficina 2', 'Carlos Ruiz'),
('Tablet Samsung', 'Tablet', 'Disponible', 'Almacén', '');

-- Tabla de préstamos
DROP TABLE IF EXISTS prestamos;
CREATE TABLE prestamos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    supervisor TEXT NOT NULL,
    location TEXT NOT NULL,
    codigo_evento TEXT NOT NULL,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(device_id) REFERENCES devices(id)
);

-- Modifica devoluciones para guardar codigo_evento
DROP TABLE IF EXISTS devoluciones;
CREATE TABLE devoluciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    supervisor TEXT,
    location TEXT,
    codigo_evento TEXT,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(device_id) REFERENCES devices(id)
);

-- Tabla de usuarios
DROP TABLE IF EXISTS usuarios;
CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    correo TEXT NOT NULL,
    password TEXT NOT NULL, -- Contraseña encriptada
    rol TEXT NOT NULL -- 'admin' o 'usuario'
);

-- Tabla de alertas de dispositivos
DROP TABLE IF EXISTS alertas;
CREATE TABLE alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dispositivo TEXT NOT NULL,
    comentario TEXT NOT NULL,
    boton_derecho TEXT NOT NULL,
    boton_izquierdo TEXT NOT NULL,
    mica_danada TEXT NOT NULL,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    reparacion TEXT,
    resuelto INTEGER DEFAULT 0
);
