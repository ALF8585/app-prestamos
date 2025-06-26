import sqlite3
import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file
from io import BytesIO
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph

app = Flask(__name__)


def get_db_connection():
    conn = sqlite3.connect('database.db')
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
        data = request.json
        if not all(k in data and data[k] for k in
                   ['fecha', 'identificacion', 'nombre', 'ubicacion', 'hora_inicio', 'prestado_por']):
            return jsonify({'error': 'Faltan campos requeridos'}), 400

        # <<< MODIFICADO: Se añade pc_pertenece al INSERT
        conn.execute("""
            INSERT INTO prestamos (fecha, identificacion, nombre, area, pc, pc_numero, pc_pertenece, kit, aire, cabinas, consola, vbeam, ubicacion, edificio, hora_inicio, prestado_por, observaciones)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['fecha'], data['identificacion'], data['nombre'], data.get('area'),
            data.get('pc', False), data.get('pc_numero'), data.get('pc_pertenece'),  # <-- Nuevo valor
            data.get('kit', False), data.get('aire', False),
            data.get('cabinas', False), data.get('consola', False), data.get('vbeam', False),
            data['ubicacion'], data.get('edificio'), data['hora_inicio'], data['prestado_por'],
            data.get('observaciones')
        ))
        conn.commit()
        conn.close()
        return jsonify({'success': 'Registro guardado correctamente'}), 201

    if request.method == 'GET':
        prestamos = conn.execute(
            'SELECT * FROM prestamos WHERE hora_entrega IS NULL ORDER BY fecha DESC, hora_inicio DESC').fetchall()
        conn.close()
        return jsonify([dict(row) for row in prestamos])


@app.route('/api/prestamos/<int:prestamo_id>/devolver', methods=['POST'])
def devolver_prestamo(prestamo_id):
    data = request.json
    recibido_por = data.get('recibido_por')
    if not recibido_por:
        return jsonify({'error': 'Debe especificar quién recibe el equipo.'}), 400

    conn = get_db_connection()
    prestamo = conn.execute('SELECT hora_inicio, fecha FROM prestamos WHERE id = ?', (prestamo_id,)).fetchone()
    horas_utilizacion = None
    if prestamo:
        try:
            start_datetime_str = f"{prestamo['fecha']} {prestamo['hora_inicio']}"
            start_datetime = datetime.strptime(start_datetime_str, '%Y-%m-%d %H:%M')
            end_datetime = datetime.now()
            diferencia = end_datetime - start_datetime
            horas_utilizacion = round(diferencia.total_seconds() / 3600, 2)
        except (ValueError, TypeError):
            horas_utilizacion = None

    conn.execute("""
        UPDATE prestamos SET hora_entrega = ?, recibido_por = ?, horas_utilizacion = ? WHERE id = ?
    """, (datetime.now().strftime('%H:%M:%S'), recibido_por, horas_utilizacion, prestamo_id))

    conn.commit()
    conn.close()
    return jsonify({'success': 'Devolución registrada correctamente.'})


# --- Rutas de exportación (recogen la nueva columna automáticamente) ---
@app.route('/export/excel')
def export_excel():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM prestamos", conn)
    conn.close()
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Prestamos')
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='historial_prestamos.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


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
        table_data = [list(data[0].keys())] + [[str(item) if item is not None else "" for item in row] for row in data]
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])
        table = Table(table_data, repeatRows=1)
        table.setStyle(style)
        elements.append(table)

    doc.build(elements)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='historial_prestamos.pdf', mimetype='application/pdf')


if __name__ == '__main__':
    app.run(debug=True)