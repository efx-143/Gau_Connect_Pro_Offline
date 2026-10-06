import json, sqlite3, os, re, html
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent
DB = BASE / "gauconnect.db"
UPLOADS = BASE / "uploads"
UPLOADS.mkdir(exist_ok=True)

ADMIN_USER = "admin"
ADMIN_PASS = "gauconnect"

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS farmers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, phone TEXT NOT NULL, area TEXT NOT NULL,
        cows INTEGER NOT NULL DEFAULT 0, notes TEXT, photo TEXT, created_at TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS surveys(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, area TEXT NOT NULL, cows INTEGER NOT NULL DEFAULT 0,
        water TEXT, clean TEXT, feed TEXT, notes TEXT, photo TEXT, created_at TEXT NOT NULL)""")
    con.commit()
    return con

def save_upload(field, body, boundary):
    # Parse one multipart field from the complete request body.
    marker = b"--" + boundary
    for part in body.split(marker):
        if b"Content-Disposition:" not in part:
            continue
        head, sep, data = part.partition(b"\r\n\r\n")
        if not sep:
            continue
        m = re.search(br'name="([^"]+)"(?:;\s*filename="([^"]*)")?', head)
        if not m or m.group(1).decode(errors="ignore") != field:
            continue
        filename = (m.group(2) or b"").decode("utf-8", "ignore")
        data = data.rstrip(b"\r\n-")
        return filename, data
    return "", b""

def multipart_fields(body, boundary):
    fields = {}
    marker = b"--" + boundary
    for part in body.split(marker):
        if b"Content-Disposition:" not in part:
            continue
        head, sep, data = part.partition(b"\r\n\r\n")
        if not sep:
            continue
        m = re.search(br'name="([^"]+)"(?:;\s*filename="([^"]*)")?', head)
        if not m:
            continue
        name = m.group(1).decode("utf-8","ignore")
        filename = (m.group(2) or b"").decode("utf-8","ignore")
        data = data.rstrip(b"\r\n-")
        fields[name] = (filename, data)
    return fields

class Handler(BaseHTTPRequestHandler):
    def send_json(self, obj, status=200):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/api/stats":
            con=db()
            farmers=con.execute("SELECT COUNT(*) n FROM farmers").fetchone()["n"]
            cows=con.execute("SELECT COALESCE(SUM(cows),0) n FROM farmers").fetchone()["n"]
            surveys=con.execute("SELECT COUNT(*) n FROM surveys").fetchone()["n"]
            con.close()
            return self.send_json({"farmers":farmers,"cows":cows,"surveys":surveys})
        if p == "/api/farmers":
            con=db(); rows=[dict(x) for x in con.execute("SELECT * FROM farmers ORDER BY id DESC")]; con.close()
            return self.send_json(rows)
        if p == "/api/surveys":
            con=db(); rows=[dict(x) for x in con.execute("SELECT * FROM surveys ORDER BY id DESC")]; con.close()
            return self.send_json(rows)
        if p.startswith("/uploads/"):
            fp = BASE / p.lstrip("/")
            if fp.exists() and fp.is_file():
                data=fp.read_bytes()
                ext=fp.suffix.lower()
                ctype={".jpg":"image/jpeg",".jpeg":"image/jpeg",".png":"image/png",".webp":"image/webp"}.get(ext,"application/octet-stream")
                self.send_response(200); self.send_header("Content-Type",ctype); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
            else: self.send_error(404)
            return
        fp = BASE / ("index.html" if p=="/" else p.lstrip("/"))
        if not fp.exists() or not fp.is_file():
            self.send_error(404); return
        data=fp.read_bytes()
        ctype="text/html; charset=utf-8" if fp.suffix==".html" else "text/css; charset=utf-8" if fp.suffix==".css" else "application/javascript; charset=utf-8"
        self.send_response(200); self.send_header("Content-Type",ctype); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_POST(self):
        p=urlparse(self.path).path
        length=int(self.headers.get("Content-Length","0"))
        body=self.rfile.read(length)
        if p=="/api/login":
            try:
                x=json.loads(body.decode())
                ok=x.get("username")==ADMIN_USER and x.get("password")==ADMIN_PASS
                return self.send_json({"ok":ok}, 200 if ok else 401)
            except: return self.send_json({"ok":False},400)
        ctype=self.headers.get("Content-Type","")
        if not ctype.startswith("multipart/form-data"):
            return self.send_json({"error":"multipart/form-data required"},400)
        m=re.search(r'boundary="?([^";]+)"?',ctype)
        if not m: return self.send_json({"error":"missing boundary"},400)
        fields=multipart_fields(body,m.group(1).encode())
        now=datetime.now().isoformat(timespec="seconds")
        def val(k): return fields.get(k,("",b""))[1].decode("utf-8","ignore")
        def photo(k,prefix):
            fn,data=fields.get(k,("",b""))
            if not fn or not data: return ""
            ext=Path(fn).suffix.lower()
            if ext not in [".jpg",".jpeg",".png",".webp"]: return ""
            safe=re.sub(r"[^a-zA-Z0-9_.-]","_",fn)
            name=f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{safe}"
            (UPLOADS/name).write_bytes(data)
            return "/uploads/"+name
        con=db()
        if p=="/api/farmers":
            name=val("name").strip(); phone=val("phone").strip(); area=val("area").strip()
            cows=int(val("cows") or 0); notes=val("notes"); ph=photo("photo","farmer")
            if not name or not phone or not area: return self.send_json({"error":"Name, phone and area are required"},400)
            con.execute("INSERT INTO farmers(name,phone,area,cows,notes,photo,created_at) VALUES(?,?,?,?,?,?,?)",(name,phone,area,cows,notes,ph,now))
            con.commit(); con.close(); return self.send_json({"ok":True})
        if p=="/api/surveys":
            name=val("name").strip(); area=val("area").strip(); cows=int(val("cows") or 0)
            water=val("water"); clean=val("clean"); feed=val("feed"); notes=val("notes"); ph=photo("photo","survey")
            if not name or not area: return self.send_json({"error":"Name and area are required"},400)
            con.execute("INSERT INTO surveys(name,area,cows,water,clean,feed,notes,photo,created_at) VALUES(?,?,?,?,?,?,?, ?,?)",(name,area,cows,water,clean,feed,notes,ph,now))
            con.commit(); con.close(); return self.send_json({"ok":True})
        return self.send_json({"error":"Unknown endpoint"},404)

    def do_DELETE(self):
        p=urlparse(self.path).path
        qs=parse_qs(urlparse(self.path).query)
        rid=qs.get("id",[""])[0]
        if not rid.isdigit(): return self.send_json({"error":"Invalid id"},400)
        table="farmers" if p=="/api/farmers" else "surveys" if p=="/api/surveys" else None
        if not table: return self.send_json({"error":"Unknown endpoint"},404)
        con=db(); row=con.execute(f"SELECT photo FROM {table} WHERE id=?",(rid,)).fetchone()
        if row and row["photo"]:
            try: (BASE/row["photo"].lstrip("/")).unlink(missing_ok=True)
            except: pass
        con.execute(f"DELETE FROM {table} WHERE id=?",(rid,)); con.commit(); con.close()
        return self.send_json({"ok":True})

if __name__=="__main__":
    db().close()
    print("Gau Connect Pro is running at http://localhost:8000")
    print("Database: gauconnect.db")
    print("Uploaded photos: uploads/")
    ThreadingHTTPServer(("127.0.0.1",8000),Handler).serve_forever()
