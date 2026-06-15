"""Minimal Flask demo app standing in for the app-under-test (Stage 2).

Implements the "Basic Information Input" screen used by
testcases/basic-information-input.yaml: Usage buttons, cascading
Prefecture->Municipality dropdowns, validation, XSS-safe echo, login + roles.

Run:  ./.venv/Scripts/python.exe demo/app.py   (serves on 127.0.0.1:5005)
"""
from __future__ import annotations
from markupsafe import escape
from flask import (Flask, request, session, redirect, jsonify,
                   render_template_string, abort)

USERS = {
    "admin@example.com": {"password": "admin", "role": "admin"},
    "a@example.com": {"password": "a", "role": "user"},
    "b@example.com": {"password": "b", "role": "user"},
    "noperm@example.com": {"password": "n", "role": "guest"},
}

PREFECTURES = {"13": "Tokyo", "27": "Osaka"}
MUNICIPALITIES = {
    "13": ["Chiyoda", "Shibuya"],
    "27": ["Kita", "Chuo"],
}

# in-memory submitted records keyed by owner email
RECORDS: dict[str, dict] = {}

SCREEN_HTML = """
<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Basic Information Input</title></head><body>
<h1>Basic Information Input</h1>
<form id="biForm">
  <fieldset><legend>Usage</legend>
    <button type="button" id="usageResidential" data-usage="Residential">Residential</button>
    <button type="button" id="usageIndustrial" data-usage="Industrial">Industrial</button>
  </fieldset>
  <label>Prefecture
    <select id="prefecture"><option value="">--</option>
      {% for k, v in prefectures.items() %}<option value="{{ k }}">{{ v }}</option>{% endfor %}
    </select>
  </label>
  <label>Municipality
    <select id="municipality" disabled><option value="">--</option></select>
  </label>
  <button type="submit" id="submitBtn">Submit</button>
</form>
<p id="error" role="alert"></p>
<p id="result"></p>
<script>
let usage = "";
document.querySelectorAll('[data-usage]').forEach(b =>
  b.addEventListener('click', () => { usage = b.dataset.usage;
    document.querySelectorAll('[data-usage]').forEach(x=>x.removeAttribute('aria-pressed'));
    b.setAttribute('aria-pressed','true'); }));
const pref = document.getElementById('prefecture');
const muni = document.getElementById('municipality');
pref.addEventListener('change', async () => {
  muni.innerHTML = '<option value="">--</option>'; muni.value = '';
  if (!pref.value) { muni.disabled = true; return; }
  const r = await fetch('/api/municipalities?prefecture=' + pref.value);
  const d = await r.json();
  d.municipalities.forEach(m => { const o = document.createElement('option');
    o.value = m; o.textContent = m; muni.appendChild(o); });
  muni.disabled = false;
});
let submitting = false;
document.getElementById('biForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (submitting) return; submitting = true;
  document.getElementById('error').textContent = '';
  const body = { usage, prefecture: pref.value, municipality: muni.value };
  const r = await fetch('/api/basic-info',
    { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
  const d = await r.json();
  if (!r.ok) { document.getElementById('error').textContent = d.error || 'Error'; }
  else { document.getElementById('result').textContent = 'Saved: ' + d.echo; }
  submitting = false;
});
</script>
</body></html>
"""

LOGIN_HTML = """
<!doctype html><html><head><meta charset="utf-8"><title>Login</title></head><body>
<h1>Login</h1>
{% if err %}<p role="alert">{{ err }}</p>{% endif %}
<form method="post" action="/login">
  <input name="email" placeholder="email">
  <input name="password" type="password" placeholder="password">
  <button type="submit">Login</button>
</form></body></html>
"""


def create_app():
    app = Flask(__name__)
    app.secret_key = "demo-secret-key"

    @app.get("/login")
    def login_form():
        return render_template_string(LOGIN_HTML, err=None)

    @app.post("/login")
    def login():
        email = request.form.get("email", "")
        pw = request.form.get("password", "")
        u = USERS.get(email)
        if not u or u["password"] != pw:
            return render_template_string(LOGIN_HTML, err="Invalid credentials"), 401
        session["user"] = email
        session["role"] = u["role"]
        return redirect("/")

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect("/login")

    @app.get("/")
    def screen():
        if "user" not in session:
            return redirect("/login")
        if session.get("role") == "guest":
            return "Ban khong co quyen truy cap man hinh nay", 403
        return render_template_string(SCREEN_HTML, prefectures=PREFECTURES)

    @app.get("/api/municipalities")
    def municipalities():
        if "user" not in session:
            abort(401)
        pref = request.args.get("prefecture", "")
        return jsonify({"municipalities": MUNICIPALITIES.get(pref, [])})

    @app.post("/api/basic-info")
    def basic_info():
        if "user" not in session:
            abort(401)
        data = request.get_json(silent=True) or {}
        missing = [k for k in ("usage", "prefecture", "municipality") if not data.get(k)]
        if missing:
            return jsonify({"error": f"Thieu truong bat buoc: {', '.join(missing)}"}), 400
        RECORDS[session["user"]] = data
        return jsonify({"ok": True, "echo": str(escape(data["municipality"]))})

    @app.get("/api/basic-info")
    def read_basic_info():
        if "user" not in session:
            abort(401)
        owner = request.args.get("owner", session["user"])
        if owner != session["user"]:
            abort(403)
        return jsonify({"record": RECORDS.get(owner)})

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5005)
