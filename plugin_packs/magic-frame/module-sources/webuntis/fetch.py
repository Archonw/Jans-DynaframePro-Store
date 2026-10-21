"""WebUntis für Dynaframe's Magic Mirror.

Nachbau von MMM-Webuntis (HeikoGr, MIT): gleiche Anmeldung (QR-Code-Link aus
Untis Mobile oder Benutzer/Passwort) und dieselben REST-Endpunkte. Jeder Abruf
meldet sich an, holt Stundenplan, Prüfungen, Hausaufgaben und Mitteilungen
und meldet sich wieder ab, damit sich auf dem Server keine Sitzungen sammeln.
"""

import base64
import hashlib
import hmac
import html
import re
import struct
import time
from datetime import date, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import requests

TIMEOUT = 15
USER_AGENT = "DynaframeMagicMirror-WebUntis/1.0"
POSITIONS = [f"position{i}" for i in range(1, 8)]

TEXT = {
    "qr": ("Der QR-Code-Link ist unvollständig. Er beginnt mit untis://setschool?…",
           "The QR code link is incomplete. It starts with untis://setschool?…",
           "El enlace del código QR está incompleto. Empieza por untis://setschool?…"),
    "student": ("Kein Kind mit dem Namen „{name}“ in diesem Zugang. Gefunden: {all}",
                "No child named “{name}” in this account. Found: {all}",
                "No hay ningún hijo llamado «{name}» en esta cuenta. Encontrados: {all}"),
    "no-login": ("Trag den Text des QR-Codes ein oder Server, Schule, Benutzer und Passwort.",
                 "Enter the QR code text, or server, school, username and password.",
                 "Introduce el texto del código QR, o servidor, colegio, usuario y contraseña."),
    "no-student": ("WebUntis nennt zu diesem Zugang keinen Schüler.",
                   "WebUntis lists no student for this account.",
                   "WebUntis no indica ningún alumno para esta cuenta."),
}
LANGS = ("de", "en", "es")


def say(ctx, key, **values):
    lang = ctx.get("lang") if ctx.get("lang") in LANGS else "de"
    return TEXT[key][LANGS.index(lang)].format(**values)


# --------------------------------------------------------------------------
# Anmeldung
# --------------------------------------------------------------------------

def base_url(server):
    server = str(server or "").strip().rstrip("/")
    if not re.match(r"^https?://", server):
        server = "https://" + server
    return server


def b32decode(secret):
    """Base32 wie Authenticator-Apps: Groß/klein, Leerzeichen und = egal."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    buffer = bits = 0
    out = bytearray()
    for char in re.sub(r"[\s=]", "", secret.upper()):
        value = alphabet.find(char)
        if value < 0:
            raise ValueError("Base32")
        buffer = (buffer << 5) | value
        bits += 5
        if bits >= 8:
            bits -= 8
            out.append((buffer >> bits) & 0xFF)
    return bytes(out)


def totp(secret, at_ms):
    # wie im Original auf 26 Zeichen auffüllen ("A" ist eine Null in Base32)
    secret = secret if len(secret) >= 26 else secret.ljust(26, "A")
    counter = struct.pack(">Q", int(at_ms / 1000 / 30))
    digest = hmac.new(b32decode(secret), counter, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % 1_000_000).zfill(6)


class Untis:
    def __init__(self, ctx, base, school):
        self.ctx, self.base, self.school = ctx, base, school
        self.http = requests.Session()
        self.http.headers["User-Agent"] = USER_AGENT
        self.token = self.tenant = self.year = None
        self.person = None
        self.app = {}

    def call(self, method, url, **kwargs):
        SourceError = self.ctx["SourceError"]
        try:
            response = self.http.request(method, url, timeout=TIMEOUT, **kwargs)
        except requests.exceptions.SSLError as exc:
            raise SourceError("ssl", str(exc)) from exc
        except requests.RequestException as exc:
            raise SourceError("unreachable", str(exc)) from exc
        if response.status_code in (401, 403):
            raise SourceError("key", f"HTTP {response.status_code}")
        if response.status_code == 429:
            raise SourceError("quota")
        if response.status_code >= 400:
            raise SourceError(f"http:{response.status_code}")
        return response

    def json(self, response):
        try:
            return response.json()
        except ValueError as exc:
            raise self.ctx["SourceError"]("format", "keine JSON-Antwort") from exc

    def login_qr(self, user, secret):
        now_ms = int(time.time() * 1000)
        body = {"jsonrpc": "2.0", "id": 1, "method": "getUserData2017",
                "params": [{"auth": {"clientTime": now_ms, "user": user, "otp": totp(secret, now_ms)}}]}
        answer = self.json(self.call("POST", f"{self.base}/WebUntis/jsonrpc_intern.do",
                                     params={"m": "getUserData2017", "school": self.school, "v": "i2.2"}, json=body))
        if answer.get("error"):
            raise self.ctx["SourceError"]("login", str(answer["error"].get("message") or ""))
        self.http.cookies.set("schoolname", "_" + base64.b64encode(self.school.encode()).decode())
        config = self.json(self.call("GET", f"{self.base}/WebUntis/api/app/config"))
        user_data = ((config.get("data") or {}).get("loginServiceConfig") or {}).get("user") or {}
        self.person = user_data.get("personId")
        if not self.person:
            raise self.ctx["SourceError"]("login", "kein personId")

    def login_password(self, user, password):
        body = {"jsonrpc": "2.0", "id": 1, "method": "authenticate",
                "params": {"user": user, "password": password, "client": "App"}}
        answer = self.json(self.call("POST", f"{self.base}/WebUntis/jsonrpc.do",
                                     params={"school": self.school}, json=body))
        result = answer.get("result")
        if not result:
            raise self.ctx["SourceError"]("login", str((answer.get("error") or {}).get("message") or ""))
        self.person = result.get("personId")

    def start_rest(self):
        token = self.call("GET", f"{self.base}/WebUntis/api/token/new").text.strip()
        if not token or token[0] in "<{":
            raise self.ctx["SourceError"]("login", "kein Token")
        self.token = token
        self.app = self.json(self.call("GET", f"{self.base}/WebUntis/api/rest/view/v1/app/data",
                                       headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}))
        self.tenant = (self.app.get("tenant") or {}).get("id")
        self.year = (self.app.get("currentSchoolYear") or {}).get("id")

    def rest(self, path, params):
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        if self.tenant:
            headers["Tenant-Id"] = str(self.tenant)
        if self.year:
            headers["X-Webuntis-Api-School-Year-Id"] = str(self.year)
        return self.json(self.call("GET", f"{self.base}{path}", params=params, headers=headers))

    def logout(self):
        try:
            self.http.post(f"{self.base}/WebUntis/jsonrpc.do", params={"school": self.school}, timeout=5,
                           json={"jsonrpc": "2.0", "id": 2, "method": "logout", "params": {}})
        except requests.RequestException:
            pass


def connect(config, ctx):
    SourceError = ctx["SourceError"]
    if config.get("login") == "password":
        server, school = str(config.get("server") or "").strip(), str(config.get("school") or "").strip()
        user, password = str(config.get("username") or "").strip(), str(config.get("password") or "")
        if not (server and school and user and password):
            raise SourceError(say(ctx, "no-login"))
        untis = Untis(ctx, base_url(server), school)
        untis.login_password(user, password)
    else:
        link = str(config.get("qrcode") or "").strip()
        if not link:
            raise SourceError(say(ctx, "no-login"))
        query = {k: v[0] for k, v in parse_qs(urlparse(link).query).items()}
        if not all(query.get(k) for k in ("url", "school", "user", "key")):
            raise SourceError(say(ctx, "qr"))
        untis = Untis(ctx, base_url(query["url"]), query["school"])
        try:
            untis.login_qr(query["user"], query["key"])
        except ValueError as exc:
            raise SourceError(say(ctx, "qr")) from exc
    untis.start_rest()
    return untis


def pick_student(untis, wanted, ctx):
    """Eltern-Zugang: das Kind nach Namen (oder das erste); sonst man selbst."""
    students = [s for s in ((untis.app.get("user") or {}).get("students") or []) if isinstance(s, dict)]
    names = [(s.get("id"), str(s.get("displayName") or s.get("name") or "")) for s in students if s.get("id")]
    typed = str(wanted or "").strip()
    wanted = typed.lower()
    if wanted and names:
        for sid, name in names:
            if wanted == name.lower() or wanted in name.lower():
                return sid, name, True
        raise ctx["SourceError"](say(ctx, "student", name=typed, all=", ".join(n for _, n in names)))
    if untis.person and (not names or untis.person in [sid for sid, _ in names]):
        own = next((n for sid, n in names if sid == untis.person), "")
        if not own:
            person = (untis.app.get("user") or {}).get("person") or {}
            own = str(person.get("displayName") or "")
        return untis.person, own, False
    if names:
        return names[0][0], names[0][1], True
    raise ctx["SourceError"](say(ctx, "no-student"))


# --------------------------------------------------------------------------
# Daten
# --------------------------------------------------------------------------

def ymd(day):
    return day.strftime("%Y%m%d")


def iso_day(value):
    """20261020, "2026-10-20" oder "2026-10-20T00:00" -> "2026-10-20"."""
    text = str(value or "")
    if re.match(r"^\d{8}$", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", text) else ""


def hhmm(value):
    """830, "0830", "08:30" oder "2026-10-20T08:30" -> "08:30"."""
    text = str(value if value is not None else "")
    if "T" in text:
        text = text.split("T", 1)[1]
    if re.match(r"^\d{1,2}:\d{2}", text):
        hours, minutes = text.split(":")[:2]
        return f"{int(hours):02d}:{minutes[:2]}"
    if re.match(r"^\d{3,4}$", text):
        return f"{int(text) // 100:02d}:{int(text) % 100:02d}"
    return ""


def plain(text, keep_lines=False):
    text = str(text or "")
    text = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h\d)>", "\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    if keep_lines:
        return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())[:600]
    return " ".join(text.split())[:300]


def element(raw):
    return {"short": str(raw.get("shortName") or raw.get("name") or ""),
            "long": str(raw.get("longName") or raw.get("displayName") or "")}


def lesson(entry, day):
    fields = {"SUBJECT": [], "TEACHER": [], "ROOM": [], "INFO": []}
    removed = {"SUBJECT": [], "TEACHER": [], "ROOM": []}
    for key in POSITIONS:
        for pos in entry.get(key) or []:
            if not isinstance(pos, dict):
                continue
            current, old = pos.get("current") or {}, pos.get("removed") or {}
            if current.get("type") in fields:
                fields[current["type"]].append(element(current))
            if old.get("type") in removed and old.get("shortName"):
                removed[old["type"]].append(element(old))
    duration = entry.get("duration") or {}
    return {
        "date": day,
        "start": hhmm(duration.get("start")),
        "end": hhmm(duration.get("end")),
        "status": str(entry.get("status") or "REGULAR").upper(),
        "type": str(entry.get("type") or "").upper(),
        "subject": fields["SUBJECT"],
        "teacher": fields["TEACHER"],
        "room": fields["ROOM"],
        "oldSubject": removed["SUBJECT"],
        "oldTeacher": removed["TEACHER"],
        "oldRoom": removed["ROOM"],
        "text": plain(entry.get("substitutionText") or ""),
        "info": plain(entry.get("lessonInfo") or "") or " ".join(i["long"] or i["short"] for i in fields["INFO"]),
    }


def timetable(untis, student, today, school_days):
    """Die nächsten Schultage mit Stunden, ab heute (höchstens drei Wochen voraus)."""
    answer = untis.rest("/WebUntis/api/rest/view/v1/timetable/entries", {
        "start": today.isoformat(), "end": (today + timedelta(days=20)).isoformat(),
        "resourceType": "STUDENT", "resources": str(student), "timetableType": "MY_TIMETABLE"})
    if not isinstance(answer.get("days"), list):
        raise untis.ctx["SourceError"]("format", "Stundenplan ohne days")
    days = []
    for day in answer["days"]:
        when = iso_day(day.get("date"))
        lessons = [lesson(e, when) for e in day.get("gridEntries") or [] if isinstance(e, dict)]
        if when and lessons:
            lessons.sort(key=lambda x: (x["start"], x["end"]))
            days.append({"date": when, "lessons": lessons})
    days.sort(key=lambda d: d["date"])
    # heute zählt mit, auch wenn die Schule schon aus ist (die Szene springt dann weiter)
    return days[:school_days + 1]


def exams(untis, student, today, ahead):
    answer = untis.rest("/WebUntis/api/exams", {
        "startDate": ymd(today), "endDate": ymd(today + timedelta(days=ahead)),
        "studentId": student, "klasseId": -1, "withGrades": "true"})
    rows = ((answer.get("data") or {}).get("exams") if isinstance(answer.get("data"), dict) else None) \
        or answer.get("exams") or []
    out = []
    for exam in rows:
        assigned = exam.get("assignedStudents")
        if isinstance(assigned, list) and assigned and \
                not any(str(s.get("id")) == str(student) for s in assigned if isinstance(s, dict)):
            continue
        subject = exam.get("subject") or exam.get("lessonName") or ""
        out.append({"date": iso_day(exam.get("examDate") or exam.get("date")),
                    "start": hhmm(exam.get("startTime")), "end": hhmm(exam.get("endTime")),
                    "subject": plain(subject if isinstance(subject, str) else (subject or {}).get("name")),
                    "name": plain(exam.get("name") or exam.get("examType") or ""),
                    "text": plain(exam.get("text") or exam.get("description") or "")})
    return sorted([e for e in out if e["date"]], key=lambda e: (e["date"], e["start"]))[:12]


def homework(untis, student, today, ahead):
    answer = untis.rest("/WebUntis/api/homeworks/lessons", {
        "startDate": ymd(today - timedelta(days=30)), "endDate": ymd(today + timedelta(days=ahead))})
    data = answer.get("data") if isinstance(answer.get("data"), dict) else answer
    lessons = {row.get("id"): row for row in data.get("lessons") or [] if isinstance(row, dict)}
    owners = {row.get("homeworkId"): row.get("elementIds") or [] for row in data.get("records") or []
              if isinstance(row, dict)}
    first, last = today.isoformat(), (today + timedelta(days=ahead)).isoformat()
    out, seen = [], set()
    for hw in data.get("homeworks") or []:
        if not isinstance(hw, dict) or hw.get("completed") or hw.get("id") in seen:
            continue
        seen.add(hw.get("id"))
        owner = owners.get(hw.get("id"))
        if owner and str(student) not in [str(x) for x in owner]:
            continue
        due = iso_day(hw.get("dueDate") or hw.get("date"))
        if not (first <= due <= last):
            continue
        lesson_row = lessons.get(hw.get("lessonId")) or {}
        subject = lesson_row.get("subject") or ""
        out.append({"date": due, "subject": plain(subject if isinstance(subject, str) else subject.get("name")),
                    "text": plain(hw.get("text") or hw.get("remark") or "", keep_lines=True)})
    return sorted(out, key=lambda h: h["date"])[:12]


def messages(untis, today):
    answer = untis.rest("/WebUntis/api/public/news/newsWidgetData", {"date": ymd(today)})
    data = answer.get("data") if isinstance(answer.get("data"), dict) else answer
    out = []
    for row in data.get("messagesOfDay") or []:
        if isinstance(row, dict):
            out.append({"subject": plain(row.get("subject")), "text": plain(row.get("text"), keep_lines=True)})
    return out[:5]


def holiday(app, today):
    """Laufende oder in den nächsten 3 Tagen beginnende Ferien."""
    for row in app.get("holidays") or []:
        if not isinstance(row, dict):
            continue
        start, end = iso_day(row.get("start") or row.get("startDate")), iso_day(row.get("end") or row.get("endDate"))
        if start and end and start <= (today + timedelta(days=3)).isoformat() and end >= today.isoformat():
            return {"name": plain(row.get("longName") or row.get("name")), "start": start, "end": end}
    return None


def fetch(config, ctx):
    today = date.today()
    untis = connect(config, ctx)
    try:
        student, name, parent = pick_student(untis, config.get("student"), ctx)
        out = {"student": name, "parent": parent, "today": today.isoformat(), "fetched": datetime.now().isoformat(),
               "days": [], "exams": [], "homework": [], "messages": [], "problems": [],
               "holiday": holiday(untis.app, today)}
        school_days = int(config.get("days") or 0)
        if school_days:
            out["days"] = timetable(untis, student, today, school_days)
        # Was zusätzlich fehlt (manche Schulen sperren Prüfungen oder Hausaufgaben),
        # soll den Stundenplan nicht verdecken.
        for key, wanted, job in (
                ("exams", int(config.get("exams") or 0), lambda: exams(untis, student, today, int(config["exams"]))),
                ("homework", int(config.get("homework") or 0),
                 lambda: homework(untis, student, today, int(config["homework"]))),
                ("messages", bool(config.get("messages")), lambda: messages(untis, today))):
            if not wanted:
                continue
            try:
                out[key] = job()
            except Exception as exc:  # noqa: BLE001
                out["problems"].append(key)
                ctx["log"](f"WebUntis {key}: {exc}")
        return out
    finally:
        untis.logout()
