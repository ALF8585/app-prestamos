import sqlite3
import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from io import BytesIO
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import os

app = Flask(__name__)

# --- CONFIGURACIÓN DE SEGURIDAD ---
# Clave secreta para protección CSRF. ¡Cámbiala en un entorno de producción!
app.config['SECRET_KEY'] = os.urandom(24) 
# Inicializa la protección CSRF
csrf = CSRFProtect(app)
# Inicializa Talisman para cabeceras de seguridad.
# Content-Security-Policy (CSP) predeterminada es bastante estricta.
talisman = Talisman(app, content_security_policy=None) # Desactivamos CSP por simplicidad, pero se puede configurar.

# Define la ruta de la base de datos de forma robusta
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/initial-data')
def get_initial_data():
    conn = get_db_connection()
    usuarios = conn.execute('SELECT * FROM usuarios').fetchall()
    ubicaciones = conn.execute('SELECT * FROM ubicaciones ORDER BY nombre').fetchall()
    auxiliares = conn.execute('SELECT * FROM auxiliares ORDER BY nombre').fetchall()
    conn.close()
    return jsonify({
        'usuarios': [dict(row) for row in usuarios],
        'ubicaciones': [dict(row) for row in ubicaciones],
        'auxiliares': [dict(row) for row in auxiliares]
    })

@app.route('/api/equipos')
def get_equipos():
    conn = get_db_connection()
    equipos = conn.execute('SELECT * FROM equipos ORDER BY id').fetchall()
    conn.close()
    return jsonify([dict(row) for row in equipos])

@app.route('/api/prestamos', methods=['GET', 'POST'])
def handle_prestamos():
    conn = get_db_connection()
    if request.method == 'POST':
        try:
            data = request.json
            required_fields = ['fecha', 'identificacion', 'nombre', 'ubicacion', 'hora_inicio', 'prestado_por']
            if not all(k in data and data[k] for k in required_fields):
                return jsonify({'error': 'Faltan campos requeridos'}), 400

            conn.execute("""
                INSERT INTO prestamos (fecha, identificacion, nombre, area, pc, pc_numero, pc_pertenece, kit, aire, cabinas, consola, vbeam, ubicacion, edificio, hora_inicio, prestado_por, observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['fecha'], data['identificacion'], data['nombre'], data.get('area'),
                data.get('pc', False), data.get('pc_numero'), data.get('pc_pertenece'),
                data.get('kit', False), data.get('aire', False), data.get('cabinas', False),
                data.get('consola', False), data.get('vbeam', False), data['ubicacion'],
                data.get('edificio'), data['hora_inicio'], data['prestado_por'], data.get('observaciones')
            ))
            conn.commit()
            return jsonify({'success': 'Registro guardado correctamente'}), 201
        except sqlite3.Error as e:
            return jsonify({'error': f'Error en la base de datos: {e}'}), 500
        finally:
            conn.close()

    if request.method == 'GET':
        prestamos = conn.execute('SELECT * FROM prestamos WHERE hora_entrega IS NULL ORDER BY fecha DESC, hora_inicio DESC').fetchall()
        conn.close()
        return jsonify([dict(row) for row in prestamos])

@app.route('/api/prestamos/<int:prestamo_id>/devolver', methods=['POST'])
def devolver_prestamo(prestamo_id):
    data = request.json
    recibido_por = data.get('recibido_por')
    if not recibido_por:
        return jsonify({'error': 'Debe especificar quién recibe el equipo.'}), 400
    
    conn = get_db_connection()
    try:
        prestamo = conn.execute('SELECT hora_inicio, fecha FROM prestamos WHERE id = ?', (prestamo_id,)).fetchone()
        if not prestamo:
            return jsonify({'error': 'Préstamo no encontrado.'}), 404
            
        horas_utilizacion = None
        try:
            start_datetime_str = f"{prestamo['fecha']} {prestamo['hora_inicio']}"
            start_datetime = datetime.strptime(start_datetime_str, '%Y-%m-%d %H:%M')
            end_datetime = datetime.now()
            diferencia = end_datetime - start_datetime
            horas_utilizacion = round(diferencia.total_seconds() / 3600, 2)
        except (ValueError, TypeError):
            horas_utilizacion = None # Dejar como nulo si hay error de formato

        conn.execute(
            "UPDATE prestamos SET hora_entrega = ?, recibido_por = ?, horas_utilizacion = ? WHERE id = ?",
            (datetime.now().strftime('%H:%M:%S'), recibido_por, horas_utilizacion, prestamo_id)
        )
        conn.commit()
        return jsonify({'success': 'Devolución registrada correctamente.'})
    except sqlite3.Error as e:
        return jsonify({'error': f'Error en la base de datos: {e}'}), 500
    finally:
        conn.close()

@app.route('/export/excel')
def export_excel():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM prestamos", conn)
    conn.close()
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Prestamos')
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='historial_prestamos.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/export/pdf')
def export_pdf():
    conn = get_db_connection()
    data = conn.execute('SELECT * FROM prestamos ORDER BY fecha, hora_inicio').fetchall()
    conn.close()
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(letter))
    elements = [Paragraph("Reporte de Préstamos", getSampleStyleSheet()['h1'])]
    if not data:
        elements.append(Paragraph("No hay registros para mostrar.", getSampleStyleSheet()['Normal']))
    else:
        # Excluimos columnas muy anchas o innecesarias para el PDF
        column_names = [k for k in data[0].keys() if k not in ['observaciones', 'pc_pertenece']]
        table_data = [column_names] + [[str(row[key]) if row[key] is not None else "" for key in column_names] for row in data]
        
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7), # Tamaño de letra ajustado
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])
        table = Table(table_data, repeatRows=1)
        table.setStyle(style)
        elements.append(table)

    doc.build(elements)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='historial_prestamos.pdf', mimetype='application/pdf')
