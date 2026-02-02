from pickle import APPEND
from flask import Flask, render_template, request, redirect, session
from flask.cli import _app_option
import mysql.connector
import os
from flask import render_template_string


# =========================
# CONFIGURACIÓN GENERAL
# =========================
app = Flask(__name__)
app.secret_key = "clave_secreta_123"

UPLOAD_FOLDER = "static/comprobantes"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def conectar_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Rolando05",
        database="rutas_chingonas"
    )

# =========================
# INICIO
# =========================
@app.route("/")
def inicio():
    return render_template("index.html")

# =========================
# REGISTRO DE CORREDOR
# =========================
@app.route("/registrar", methods=["POST"])
def registrar():
    datos = request.form

    try:
        conexion = conectar_db()
        cursor = conexion.cursor()

        cursor.execute("""
            INSERT INTO corredores
            (evento, distancia, nombre, edad, correo, telefono, categoria, rama, playera, fecha_registro)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
        """, (
            datos["evento"],
            datos["distancia"],
            datos["nombre"],
            datos["edad"],
            datos["correo"],
            datos["telefono"],
            datos["categoria"],
            datos["rama"],
            datos["playera"]
        ))

        conexion.commit()
        id_registro = cursor.lastrowid
        folio = f"RC-{id_registro:05d}"

        cursor.execute(
            "UPDATE corredores SET folio=%s WHERE id=%s",
            (folio, id_registro)
        )
        conexion.commit()

        cursor.close()
        conexion.close()

        return f"""
        
        <h2>✅ Inscripción registrada</h2>
        <p><b>Folio del corredor:</b> {folio}</p>

        <h3>💰 Datos para transferencia</h3>
        <p>
        <b>Banco:</b> BBVA<br>
        <b>Nombre:</b> Rolando Sanchez Silvano<br>
        <b>CLABE:</b> 4152-3143-9029-0222<br>
        <b>Monto:</b> 14KM $400 MXN<br>
        <b>Monto:</b> 6KM $350 MXN<br>
        <b>Monto:</b> Infantil C/Playera $270 MXN<br>
        <b>Monto:</b> Infantil S/Playera $170 MXN<br>
        <b>Concepto:</b> Inscripción {folio}
        </p>

        <p>Después inicia sesión con tu folio para subir el comprobante.</p>
        <a href="/login">🔐 Subir comprobante</a>
        """

    except Exception as e:
        return f"<pre>{e}</pre>"

# =========================
# LOGIN CORREDOR
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        folio = request.form["folio"]

        conexion = conectar_db()
        cursor = conexion.cursor(dictionary=True)

        cursor.execute("SELECT * FROM corredores WHERE folio=%s", (folio,))
        corredor = cursor.fetchone()

        cursor.close()
        conexion.close()

        if corredor:
            return render_template("subir_comprobante.html", corredor=corredor)
        else:
            return "❌ Folio no encontrado"

    return render_template("login.html")

# =========================
# SUBIR COMPROBANTE
# =========================
@app.route("/subir_comprobante", methods=["POST"])
def subir_comprobante():
    folio = request.form["folio"]
    archivo = request.files["comprobante"]

    nombre = f"{folio}_{archivo.filename}"
    ruta = os.path.join(app.config["UPLOAD_FOLDER"], nombre)
    archivo.save(ruta)

    conexion = conectar_db()
    cursor = conexion.cursor()

    cursor.execute("""
        UPDATE corredores
        SET comprobante=%s, estado_pago='Pendiente'
        WHERE folio=%s
    """, (nombre, folio))

    conexion.commit()
    cursor.close()
    conexion.close()

    return """
<h2>✅ Comprobante enviado</h2>
<p>En revisión</p>

<br>

<a href="/" style="
    display:inline-block;
    padding:12px 22px;
    background:#28a745;
    color:white;
    text-decoration:none;
    border-radius:8px;
    font-weight:bold;
    font-size:16px;
">
    ⬅️ Regresar a la página principal
</a>
"""







# =========================
# LOGIN ADMIN
# =========================
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form["usuario"] == "admin" and request.form["password"] == "1234":
            session["admin"] = True
            return redirect("/admin/panel")
        else:
            return "❌ Credenciales incorrectas"

    return """
    <h2>Login Administrador</h2>
    <form method="POST">
        Usuario: <input name="usuario"><br><br>
        Contraseña: <input type="password" name="password"><br><br>
        <button>Entrar</button>
    </form>
    """

# =========================
# PANEL ADMIN
# =========================
@app.route("/admin/panel")
def admin_panel():
    if not session.get("admin"):
        return redirect("/admin")

    conexion = conectar_db()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute("SELECT * FROM corredores")
    corredores = cursor.fetchall()

    cursor.close()
    conexion.close()

    return render_template("admin_panel.html", corredores=corredores)

# =========================
# APROBAR PAGO
# =========================
@app.route("/admin/aprobar/<int:id>")
def aprobar_pago(id):
    if not session.get("admin"):
        return redirect("/admin")

    conexion = conectar_db()
    cursor = conexion.cursor()

    cursor.execute(
        "UPDATE corredores SET estado_pago='Pagado' WHERE id=%s",
        (id,)
    )
    conexion.commit()

    cursor.close()
    conexion.close()

    return redirect("/admin/panel")

@app.route("/admin/eliminar/<int:id>")
def eliminar_corredor(id):
    if not session.get("admin"):
        return redirect("/admin")

    conexion = conectar_db()
    cursor = conexion.cursor()

    cursor.execute("DELETE FROM corredores WHERE id=%s", (id,))
    conexion.commit()

    cursor.close()
    conexion.close()

    return redirect("/admin/panel")


# =========================
# LOGOUT ADMIN
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/admin")

# =========================

# ===============================
# GENERAR PDF DEL FOLIO
# ===============================
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

PDF_FOLDER = "static/pdfs"
os.makedirs(PDF_FOLDER, exist_ok=True)

def generar_pdf(corredor):
    ruta = f"{PDF_FOLDER}/{corredor['folio']}.pdf"

    c = canvas.Canvas(ruta, pagesize=letter)

    c.setFont("Helvetica-Bold", 22)
    c.drawString(50, 750, "RUTAS CHINGONAS")

    c.setFont("Helvetica", 12)
    c.drawString(50, 700, f"Nombre: {corredor['nombre']}")
    c.drawString(50, 680, f"Evento: {corredor['evento']}")
    c.drawString(50, 660, f"Distancia: {corredor['distancia']}")

    c.setFont("Helvetica-Bold", 28)
    c.drawString(50, 610, f"FOLIO: {corredor['folio']}")

    c.setFont("Helvetica", 10)
    c.drawString(50, 560, "Presenta este folio el día del evento para reclamar tu kit.")

    c.showPage()
    c.save()

    return ruta


# ===============================
# ENVIAR FOLIO POR WHATSAPP
# ===============================
@app.route('/admin/enviar_folio/<int:id>')
def enviar_folio(id):
    conexion = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Rolando05",
        database="rutas_chingonas"
    )
    cursor = conexion.cursor(dictionary=True)

    cursor.execute("SELECT * FROM corredores WHERE id=%s", (id,))
    corredor = cursor.fetchone()

    cursor.close()
    conexion.close()

    if not corredor:
        return "❌ Corredor no encontrado"

    generar_pdf(corredor)

    telefono = corredor['telefono']
    folio = corredor['folio']
    nombre = corredor['nombre']

    link_pdf = f"http://localhost:5000/static/pdfs/{folio}.pdf"

    mensaje = (
        f"Hola {nombre}, tu folio para el evento es {folio}. "
        f"Descarga tu ficha aquí: {link_pdf}"
    )

    url = f"https://wa.me/52{telefono}?text={mensaje.replace(' ', '%20')}"

    return redirect(url)


if __name__ == "__main__":
    app.run()
