from flask import Flask, render_template, request, redirect, session
import mysql.connector
import os

# =========================
# CONFIGURACIÓN GENERAL
# =========================
app = Flask(__name__)
app.secret_key = "clave_secreta_123"

UPLOAD_FOLDER = "static/comprobantes"
PDF_FOLDER = "static/pdfs"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# =========================
# CONEXIÓN BASE DE DATOS (REMOTA)
# =========================
def conectar_db():
    return mysql.connector.connect(
        host="sql10.freesqldatabase.com",
        user="sql10816136",
        password="xXF34b6Xnd",
        database="sql10816136",
        port=3306
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
        <b>CLABE:</b> 4152314390290222<br>
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

    nombre_archivo = f"{folio}_{archivo.filename}"
    ruta = os.path.join(app.config["UPLOAD_FOLDER"], nombre_archivo)
    archivo.save(ruta)

    conexion = conectar_db()
    cursor = conexion.cursor()

    cursor.execute("""
        UPDATE corredores
        SET comprobante=%s, estatus='Pendiente'
        WHERE folio=%s
    """, (nombre_archivo, folio))

    conexion.commit()
    cursor.close()
    conexion.close()

    return """
    <h2>✅ Comprobante enviado</h2>
    <p>En revisión</p>

    <a href="/" style="
        display:inline-block;
        margin-top:20px;
        padding:12px 22px;
        background:#28a745;
        color:white;
        text-decoration:none;
        border-radius:8px;
        font-weight:bold;
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
        "UPDATE corredores SET estatus='Pagado' WHERE id=%s",
        (id,)
    )
    conexion.commit()

    cursor.close()
    conexion.close()

    return redirect("/admin/panel")

# =========================
# GENERAR PDF
# =========================
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

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

    c.showPage()
    c.save()

    return ruta

# =========================
# ENVIAR FOLIO POR WHATSAPP
# =========================
@app.route('/admin/enviar_folio/<int:id>')
def enviar_folio(id):
    conexion = conectar_db()
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

    link_pdf = f"https://TU_DOMINIO/static/pdfs/{folio}.pdf"

    mensaje = f"Hola {nombre}, tu folio es {folio}. Descarga tu ficha aquí: {link_pdf}"
    url = f"https://wa.me/52{telefono}?text={mensaje.replace(' ', '%20')}"

    return redirect(url)

# =========================
if __name__ == "__main__":
    app.run()