import json
import os
import sqlite3
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(ROOT)))
DB_PATH = DATA_DIR / "data_santiago.sqlite"


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        create table if not exists marks (
          id integer primary key autoincrement,
          lat real not null,
          lng real not null,
          status text not null check (status in ('azul','rojo','neutral')),
          seccion text,
          colonia text,
          cp text,
          created_at text not null
        )
        """
    )
    cols = {row[1] for row in conn.execute("pragma table_info(marks)").fetchall()}
    if "seccion" not in cols:
        conn.execute("alter table marks add column seccion text")
    if "colonia" not in cols:
        conn.execute("alter table marks add column colonia text")
    if "cp" not in cols:
        conn.execute("alter table marks add column cp text")
    conn.commit()
    conn.close()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json({"ok": True, "db_path": str(DB_PATH)})
            return
        if parsed.path == "/api/marks":
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "select id, lat, lng, status, seccion, colonia, cp, created_at from marks order by id desc"
            ).fetchall()
            conn.close()
            self._send_json([dict(row) for row in rows])
            return
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/marks":
          try:
            payload = self._read_json()
            lat = float(payload["lat"])
            lng = float(payload["lng"])
            status = payload["status"]
            seccion = payload.get("seccion")
            colonia = payload.get("colonia")
            cp = payload.get("cp")
            if status not in {"azul", "rojo", "neutral"}:
                raise ValueError("status inválido")
          except Exception as exc:
            self._send_json({"error": str(exc)}, status=400)
            return

          created_at = datetime.now(timezone.utc).isoformat()
          conn = sqlite3.connect(DB_PATH)
          cur = conn.execute(
              "insert into marks (lat, lng, status, seccion, colonia, cp, created_at) values (?, ?, ?, ?, ?, ?, ?)",
              (lat, lng, status, seccion, colonia, cp, created_at),
          )
          conn.commit()
          mark_id = cur.lastrowid
          conn.close()
          self._send_json(
              {
                  "ok": True,
                  "id": mark_id,
                  "lat": lat,
                  "lng": lng,
                  "status": status,
                  "seccion": seccion,
                  "colonia": colonia,
                  "cp": cp,
                  "created_at": created_at,
              },
              status=201,
          )
          return
        self._send_json({"error": "not_found"}, status=404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/marks/"):
            mark_id = parsed.path.rsplit("/", 1)[-1]
            conn = sqlite3.connect(DB_PATH)
            cur = conn.execute("delete from marks where id = ?", (mark_id,))
            conn.commit()
            conn.close()
            self._send_json({"ok": True, "deleted": cur.rowcount})
            return
        self._send_json({"error": "not_found"}, status=404)


def main():
    init_db()
    port = int(os.environ.get("PORT", "8081"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Serving Santiago on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
