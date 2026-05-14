from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from datetime import datetime, date, timedelta
import json, os, uuid, io

app = Flask(__name__)
app.secret_key = "bebote_studio_secret_2024"

DATA_FILE = "data.json"
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "barbers": [
                {
                    "id": "barber1",
                    "name": "Bebote",
                    "email": "bebote@studio.com",
                    "password": "bebote123",
                    "schedule": {"start": "08:00", "end": "20:00"},
                    "bio": "Barbero profesional con más de 5 años de experiencia.",
                    "specialty": "Fade & Beard"
                }
            ],
            "appointments": [],
            "styles": [
                {"id": "s1", "name": "Fade Clásico", "desc": "Degradado limpio y preciso", "photo": None},
                {"id": "s2", "name": "Pompadour", "desc": "Estilo retro con volumen", "photo": None},
                {"id": "s3", "name": "Buzz Cut", "desc": "Corte al ras uniforme", "photo": None},
                {"id": "s4", "name": "Undercut", "desc": "Lados cortos, arriba largo", "photo": None},
                {"id": "s5", "name": "Taper Fade", "desc": "Degradado suave y elegante", "photo": None},
                {"id": "s6", "name": "Caesar Cut", "desc": "Corte romano clásico", "photo": None},
                {"id": "s7", "name": "Skin Fade", "desc": "Fade hasta la piel", "photo": None},
                {"id": "s8", "name": "Quiff", "desc": "Textura y volumen al frente", "photo": None},
            ],
            "cut_types": [
                "Corte de cabello",
                "Corte + barba",
                "Solo barba",
                "Corte + diseño",
                "Corte + barba + diseño",
            ]
        }
    with open(DATA_FILE) as f:
        data = json.load(f)
    for s in data.get("styles", []):
        if "photo" not in s:
            s["photo"] = None
    return data

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_barber(barber_id):
    data = load_data()
    return next((b for b in data["barbers"] if b["id"] == barber_id), None)

def get_appointments_for_barber(barber_id, target_date=None):
    data = load_data()
    appts = [a for a in data["appointments"] if a["barber_id"] == barber_id]
    if target_date:
        appts = [a for a in appts if a["date"] == target_date]
    return appts

# ─── Public routes ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    data = load_data()
    return render_template("index.html", barbers=data["barbers"], styles=data["styles"])

@app.route("/agendar", methods=["GET", "POST"])
def agendar():
    data = load_data()
    barbers = data["barbers"]
    styles = data["styles"]
    cut_types = data["cut_types"]

    if request.method == "POST":
        barber_id = request.form.get("barber_id")
        barber = get_barber(barber_id)
        if not barber:
            flash("Barbero no encontrado.", "error")
            return redirect(url_for("agendar"))

        client_name = request.form.get("client_name", "").strip()
        client_phone = request.form.get("client_phone", "").strip()
        appt_date = request.form.get("date", "").strip()
        appt_time = request.form.get("time", "").strip()
        cut_type = request.form.get("cut_type", "").strip()
        style_id = request.form.get("style_id", "").strip()
        payment_method = request.form.get("payment_method", "").strip()
        notes = request.form.get("notes", "").strip()

        if not all([client_name, client_phone, appt_date, appt_time, cut_type, style_id, payment_method]):
            flash("Por favor completa todos los campos obligatorios.", "error")
            return redirect(url_for("agendar"))

        existing = get_appointments_for_barber(barber_id, appt_date)
        confirmed_times = [a["time"] for a in existing if a["status"] in ("pending", "confirmed")]
        if appt_time in confirmed_times:
            flash("Ese horario ya está ocupado. Elige otra hora.", "error")
            return redirect(url_for("agendar"))

        style_name = next((s["name"] for s in styles if s["id"] == style_id), style_id)

        appt = {
            "id": str(uuid.uuid4())[:8],
            "barber_id": barber_id,
            "barber_name": barber["name"],
            "client_name": client_name,
            "client_phone": client_phone,
            "date": appt_date,
            "time": appt_time,
            "cut_type": cut_type,
            "style_id": style_id,
            "style_name": style_name,
            "payment_method": payment_method,
            "notes": notes,
            "status": "pending",
            "duration_hours": None,
            "created_at": datetime.now().isoformat()
        }

        data["appointments"].append(appt)
        save_data(data)
        return redirect(url_for("confirmacion", appt_id=appt["id"]))

    return render_template("agendar.html", barbers=barbers, styles=styles, cut_types=cut_types)

@app.route("/confirmacion/<appt_id>")
def confirmacion(appt_id):
    data = load_data()
    appt = next((a for a in data["appointments"] if a["id"] == appt_id), None)
    if not appt:
        return redirect(url_for("index"))
    return render_template("confirmacion.html", appt=appt)

@app.route("/api/ocupados")
def api_ocupados():
    barber_id = request.args.get("barber_id")
    target_date = request.args.get("date")
    if not barber_id or not target_date:
        return jsonify([])
    appts = get_appointments_for_barber(barber_id, target_date)
    occupied = []
    for a in appts:
        if a["status"] in ("pending", "confirmed"):
            h, m = map(int, a["time"].split(":"))
            duration = a.get("duration_hours") or 1
            for i in range(duration):
                slot_h = h + i
                if slot_h < 24:
                    occupied.append(f"{slot_h:02d}:{m:02d}")
    return jsonify(occupied)

# ─── Barber auth ───────────────────────────────────────────────────────────────

@app.route("/barbero/login", methods=["GET", "POST"])
def barber_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        data = load_data()
        barber = next((b for b in data["barbers"] if b["email"] == email and b["password"] == password), None)
        if barber:
            session["barber_id"] = barber["id"]
            session["barber_name"] = barber["name"]
            return redirect(url_for("barber_panel"))
        flash("Credenciales incorrectas.", "error")
    return render_template("barber_login.html")

@app.route("/barbero/logout")
def barber_logout():
    session.clear()
    return redirect(url_for("index"))

# ─── Panel principal ───────────────────────────────────────────────────────────

@app.route("/barbero/panel")
def barber_panel():
    if "barber_id" not in session:
        return redirect(url_for("barber_login"))
    barber_id = session["barber_id"]
    data = load_data()
    barber = get_barber(barber_id)

    filter_date = request.args.get("date", date.today().isoformat())
    filter_status = request.args.get("status", "all")

    appts = [a for a in data["appointments"] if a["barber_id"] == barber_id]
    appts_day = [a for a in appts if a["date"] == filter_date] if filter_date else appts
    if filter_status != "all":
        appts_day = [a for a in appts_day if a["status"] == filter_status]
    appts_day.sort(key=lambda x: x["time"])

    today = date.today().isoformat()
    today_appts = [a for a in appts if a["date"] == today]
    pending_count = sum(1 for a in appts if a["status"] == "pending")
    confirmed_today = sum(1 for a in today_appts if a["status"] == "confirmed")

    return render_template("barber_panel.html",
        barber=barber,
        appts=appts_day,
        filter_date=filter_date,
        filter_status=filter_status,
        pending_count=pending_count,
        confirmed_today=confirmed_today,
        today=today
    )

@app.route("/barbero/cita/<appt_id>/accion", methods=["POST"])
def appt_action(appt_id):
    if "barber_id" not in session:
        return redirect(url_for("barber_login"))

    action = request.form.get("action")
    data = load_data()
    appt = next((a for a in data["appointments"] if a["id"] == appt_id), None)

    if not appt or appt["barber_id"] != session["barber_id"]:
        flash("Cita no encontrada.", "error")
        return redirect(url_for("barber_panel"))

    if action == "confirm":
        duration = int(request.form.get("duration", 1))
        appt["status"] = "confirmed"
        appt["duration_hours"] = duration
        flash(f"Cita confirmada ({duration}h).", "success")
    elif action == "cancel":
        appt["status"] = "cancelled"
        flash("Cita cancelada.", "info")

    save_data(data)
    return redirect(url_for("barber_panel", date=appt["date"]))

@app.route("/barbero/horario", methods=["GET", "POST"])
def barber_schedule():
    if "barber_id" not in session:
        return redirect(url_for("barber_login"))

    data = load_data()
    barber = next((b for b in data["barbers"] if b["id"] == session["barber_id"]), None)

    if request.method == "POST":
        start = request.form.get("start")
        end = request.form.get("end")
        if start and end:
            barber["schedule"] = {"start": start, "end": end}
            save_data(data)
            flash("Horario actualizado.", "success")
        return redirect(url_for("barber_schedule"))

    return render_template("barber_schedule.html", barber=barber)

# ─── Gestión de estilos ────────────────────────────────────────────────────────

@app.route("/barbero/estilos")
def manage_styles():
    if "barber_id" not in session:
        return redirect(url_for("barber_login"))
    data = load_data()
    barber = get_barber(session["barber_id"])
    pending_count = sum(1 for a in data["appointments"] if a["barber_id"] == session["barber_id"] and a["status"] == "pending")
    return render_template("manage_styles.html", styles=data["styles"], barber=barber, pending_count=pending_count)

@app.route("/barbero/estilos/agregar", methods=["POST"])
def add_style():
    if "barber_id" not in session:
        return redirect(url_for("barber_login"))

    name = request.form.get("name", "").strip()
    desc = request.form.get("desc", "").strip()
    photo_file = request.files.get("photo")

    if not name:
        flash("El nombre del estilo es obligatorio.", "error")
        return redirect(url_for("manage_styles"))

    photo_path = None
    if photo_file and photo_file.filename:
        ext = photo_file.filename.rsplit(".", 1)[-1].lower()
        if ext in ("jpg", "jpeg", "png", "webp", "gif"):
            fname = f"style_{uuid.uuid4().hex[:8]}.{ext}"
            photo_file.save(os.path.join(UPLOAD_FOLDER, fname))
            photo_path = f"/static/uploads/{fname}"

    data = load_data()
    data["styles"].append({"id": f"s{uuid.uuid4().hex[:6]}", "name": name, "desc": desc, "photo": photo_path})
    save_data(data)
    flash(f"Estilo '{name}' agregado.", "success")
    return redirect(url_for("manage_styles"))

@app.route("/barbero/estilos/<style_id>/foto", methods=["POST"])
def update_style_photo(style_id):
    if "barber_id" not in session:
        return redirect(url_for("barber_login"))

    photo_file = request.files.get("photo")
    if not photo_file or not photo_file.filename:
        flash("No se seleccionó foto.", "error")
        return redirect(url_for("manage_styles"))

    ext = photo_file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
        flash("Formato no soportado.", "error")
        return redirect(url_for("manage_styles"))

    data = load_data()
    style = next((s for s in data["styles"] if s["id"] == style_id), None)
    if not style:
        flash("Estilo no encontrado.", "error")
        return redirect(url_for("manage_styles"))

    fname = f"style_{uuid.uuid4().hex[:8]}.{ext}"
    photo_file.save(os.path.join(UPLOAD_FOLDER, fname))
    style["photo"] = f"/static/uploads/{fname}"
    save_data(data)
    flash(f"Foto actualizada para '{style['name']}'.", "success")
    return redirect(url_for("manage_styles"))

@app.route("/barbero/estilos/<style_id>/eliminar", methods=["POST"])
def delete_style(style_id):
    if "barber_id" not in session:
        return redirect(url_for("barber_login"))
    data = load_data()
    data["styles"] = [s for s in data["styles"] if s["id"] != style_id]
    save_data(data)
    flash("Estilo eliminado.", "info")
    return redirect(url_for("manage_styles"))

# ─── Gestión de barberos ───────────────────────────────────────────────────────

@app.route("/barbero/barberos")
def manage_barbers():
    if "barber_id" not in session:
        return redirect(url_for("barber_login"))
    data = load_data()
    barber = get_barber(session["barber_id"])
    pending_count = sum(1 for a in data["appointments"] if a["barber_id"] == session["barber_id"] and a["status"] == "pending")
    return render_template("manage_barbers.html", barbers=data["barbers"], barber=barber, pending_count=pending_count)

@app.route("/barbero/barberos/agregar", methods=["POST"])
def add_barber():
    if "barber_id" not in session:
        return redirect(url_for("barber_login"))

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()
    specialty = request.form.get("specialty", "").strip()
    bio = request.form.get("bio", "").strip()
    start = request.form.get("start", "08:00").strip()
    end = request.form.get("end", "20:00").strip()

    if not all([name, email, password]):
        flash("Nombre, email y contraseña son obligatorios.", "error")
        return redirect(url_for("manage_barbers"))

    data = load_data()
    if any(b["email"] == email for b in data["barbers"]):
        flash("Ya existe un barbero con ese email.", "error")
        return redirect(url_for("manage_barbers"))

    data["barbers"].append({
        "id": f"barber_{uuid.uuid4().hex[:6]}",
        "name": name,
        "email": email,
        "password": password,
        "schedule": {"start": start, "end": end},
        "bio": bio,
        "specialty": specialty
    })
    save_data(data)
    flash(f"Barbero '{name}' agregado.", "success")
    return redirect(url_for("manage_barbers"))

@app.route("/barbero/barberos/<bid>/eliminar", methods=["POST"])
def delete_barber(bid):
    if "barber_id" not in session:
        return redirect(url_for("barber_login"))
    if bid == session["barber_id"]:
        flash("No puedes eliminarte a ti mismo.", "error")
        return redirect(url_for("manage_barbers"))
    data = load_data()
    data["barbers"] = [b for b in data["barbers"] if b["id"] != bid]
    save_data(data)
    flash("Barbero eliminado.", "info")
    return redirect(url_for("manage_barbers"))

# ─── Export / Import citas ─────────────────────────────────────────────────────

@app.route("/barbero/citas/exportar")
def export_appointments():
    if "barber_id" not in session:
        return redirect(url_for("barber_login"))
    data = load_data()
    json_bytes = json.dumps(data["appointments"], indent=2, ensure_ascii=False).encode("utf-8")
    filename = f"citas_{date.today().isoformat()}.json"
    return send_file(io.BytesIO(json_bytes), mimetype="application/json",
                     as_attachment=True, download_name=filename)

@app.route("/barbero/citas/importar", methods=["POST"])
def import_appointments():
    if "barber_id" not in session:
        return redirect(url_for("barber_login"))

    f = request.files.get("appts_file")
    mode = request.form.get("import_mode", "merge")

    if not f or not f.filename.endswith(".json"):
        flash("Selecciona un archivo .json válido.", "error")
        return redirect(url_for("barber_panel"))

    try:
        incoming = json.loads(f.read().decode("utf-8"))
        if not isinstance(incoming, list):
            raise ValueError("El JSON debe ser una lista de citas.")
    except Exception as e:
        flash(f"Error al leer JSON: {e}", "error")
        return redirect(url_for("barber_panel"))

    data = load_data()
    if mode == "replace":
        data["appointments"] = incoming
        flash(f"Citas reemplazadas ({len(incoming)} citas cargadas).", "success")
    else:
        existing_ids = {a["id"] for a in data["appointments"]}
        added = sum(1 for appt in incoming if appt.get("id") not in existing_ids)
        data["appointments"] += [a for a in incoming if a.get("id") not in existing_ids]
        flash(f"Importadas {added} citas nuevas (duplicadas ignoradas).", "success")

    save_data(data)
    return redirect(url_for("barber_panel"))

if __name__ == "__main__":
    import threading, random, time, requests as _req
    from datetime import datetime as _dt

    def _keep_alive():
        url = "https://barberiastudio.onrender.com"
        while True:
            try:
                r = _req.get(url, timeout=10)
                print(f"[keep-alive {_dt.now().strftime('%H:%M:%S')}] {r.status_code}")
            except Exception as e:
                print(f"[keep-alive {_dt.now().strftime('%H:%M:%S')}] ERROR: {e}")
            import random as _r; time.sleep(_r.randint(45, 90))

    threading.Thread(target=_keep_alive, daemon=True).start()
    app.run(debug=True, port=5000)
