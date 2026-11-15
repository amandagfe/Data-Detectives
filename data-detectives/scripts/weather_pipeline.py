#!/usr/bin/env python3
"""Pipeline rastreável para uma nova coleta POWER; não treina modelos.

Comandos:
  prepare  cria ledger, candidatos e exclusões a partir do catálogo v2;
  collect  coleta células em processo separado, com cache, retentativa e retomada;
  reconcile prova que todo candidato está em exatamente um estado terminal/pendente.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
import sqlite3
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NON_WEATHER = {"earthquake", "mining", "construction", "dam_embankment_collapse", "leaking_pipe", "vibration", "volcano", "other"}
ACCURACY = {"exact", "1km", "5km", "10km", "25km"}
PARAMETERS = ("PRECTOTCORR", "GWETTOP", "GWETROOT")
STATUSES = ("pending", "collecting", "valid", "excluded", "failed")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def connect(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path, timeout=60)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def schema(db: sqlite3.Connection) -> None:
    db.executescript("""
    CREATE TABLE IF NOT EXISTS runs(
      run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, catalog_sha256 TEXT NOT NULL,
      rule_version TEXT NOT NULL, target_definition TEXT NOT NULL, time_standard TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS cells(
      cell_id TEXT PRIMARY KEY, lat REAL NOT NULL, lon REAL NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
      last_error TEXT, cache_file TEXT, cache_sha256 TEXT, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS candidates(
      candidate_id TEXT PRIMARY KEY, cell_id TEXT NOT NULL REFERENCES cells(cell_id), event_date TEXT NOT NULL,
      event_ids TEXT NOT NULL, triggers TEXT NOT NULL, status TEXT NOT NULL,
      collection_status TEXT NOT NULL, product TEXT, api_version TEXT, reference_start TEXT,
      reference_end TEXT, time_standard TEXT, validation TEXT, exclusion_reason TEXT,
      attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS attempts(
      id INTEGER PRIMARY KEY AUTOINCREMENT, cell_id TEXT NOT NULL, attempt INTEGER NOT NULL,
      started_at TEXT NOT NULL, finished_at TEXT, outcome TEXT NOT NULL, http_url TEXT,
      error TEXT, response_sha256 TEXT
    );
    CREATE INDEX IF NOT EXISTS candidates_cell ON candidates(cell_id);
    CREATE INDEX IF NOT EXISTS candidates_status ON candidates(status);
    """)


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def cell_for(lat: float, lon: float) -> tuple[str, float, float]:
    lat_index, lon_index = round(lat / 0.5), round(lon / 0.625)
    return f"{lat_index}_{lon_index}", lat_index * 0.5, lon_index * 0.625


def candidate_id(cell_id: str, date: str) -> str:
    return hashlib.sha256(f"power-lst-v1|{cell_id}|{date}".encode()).hexdigest()[:24]


def prepare(args) -> dict:
    args.run_dir.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    if catalog.get("schema_version") != 2:
        raise ValueError("weather_pipeline exige catalog.json schema_version=2")
    groups: dict[tuple[str, str], dict] = {}
    cells = {}
    source_rows = eligible_rows = 0
    for event in catalog["events"]:
        source_rows += 1
        date = event.get("event_date")
        accuracy = event.get("location_accuracy")
        lat, lon = event.get("latitude"), event.get("longitude")
        if not date or not ("2007-01-01" <= date <= "2017-12-31") or accuracy not in ACCURACY or lat is None or lon is None:
            continue
        eligible_rows += 1
        cell_id, cell_lat, cell_lon = cell_for(lat, lon)
        cells[cell_id] = (cell_lat, cell_lon)
        group = groups.setdefault((cell_id, date), {"event_ids": [], "triggers": set()})
        group["event_ids"].append(event["event_id"])
        group["triggers"].add((event.get("landslide_trigger") or "unknown").strip().lower())

    ledger = args.run_dir / "ledger.sqlite"
    db = connect(ledger)
    schema(db)
    run_id = args.run_dir.name
    with db:
        db.execute("INSERT OR IGNORE INTO runs VALUES (?,?,?,?,?,?)", (
            run_id, now(), file_hash(args.catalog), "power-predictive-d-minus-1/v1",
            "evento na data civil D; atributos usam somente valores POWER LST até D-1 porque a hora/fuso do evento não é confiável",
            "LST",
        ))
        for cell_id, (lat, lon) in sorted(cells.items()):
            db.execute("INSERT OR IGNORE INTO cells(cell_id,lat,lon,updated_at) VALUES (?,?,?,?)", (cell_id, lat, lon, now()))
        for (cell_id, date), group in sorted(groups.items()):
            triggers = sorted(group["triggers"])
            excluded = all(trigger in NON_WEATHER for trigger in triggers)
            status = "excluded" if excluded else "pending"
            reason = "all_linked_records_have_explicit_non_weather_trigger" if excluded else None
            db.execute("""INSERT OR REPLACE INTO candidates
              (candidate_id,cell_id,event_date,event_ids,triggers,status,collection_status,exclusion_reason,updated_at)
              VALUES (?,?,?,?,?,?,?,?,?)""", (
                candidate_id(cell_id, date), cell_id, date, json.dumps(sorted(group["event_ids"])),
                json.dumps(triggers), status, "not_requested" if excluded else "pending", reason, now(),
            ))
    report = reconcile_db(db)
    report.update({"source_rows": source_rows, "eligible_rows_before_trigger": eligible_rows, "cells_before_trigger": len(cells)})
    write_json(args.run_dir / "preparation.json", report)
    db.close()
    return report


def power_url(lat: float, lon: float) -> str:
    params = {
        "parameters": ",".join(PARAMETERS), "community": "AG", "longitude": f"{lon:.4f}",
        "latitude": f"{lat:.4f}", "start": "20010101", "end": "20171231",
        "time-standard": "LST", "format": "JSON",
    }
    return "https://power.larc.nasa.gov/api/temporal/daily/point?" + urllib.parse.urlencode(params)


def collect_cell(ledger: Path, cache_dir: Path, row: dict, retries: int) -> tuple[str, str]:
    cell_id, lat, lon = row["cell_id"], row["lat"], row["lon"]
    url = power_url(lat, lon)
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"{cell_id}.json"
    for attempt in range(1, retries + 1):
        started = now()
        db = connect(ledger)
        with db:
            db.execute("UPDATE cells SET status='collecting',attempts=attempts+1,updated_at=? WHERE cell_id=?", (started, cell_id))
            db.execute("UPDATE candidates SET status='collecting',collection_status='requesting',attempts=attempts+1,updated_at=? WHERE cell_id=? AND status NOT IN ('excluded','valid')", (started, cell_id))
            cursor = db.execute("INSERT INTO attempts(cell_id,attempt,started_at,outcome,http_url) VALUES (?,?,?,?,?)", (cell_id, attempt, started, "started", url))
            attempt_id = cursor.lastrowid
        db.close()
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "DataDetectivesWeatherPipeline/1.0"})
            with urllib.request.urlopen(request, timeout=180) as response:
                body = response.read()
            payload = json.loads(body)
            parameters = payload["properties"]["parameter"]
            if not set(PARAMETERS) <= set(parameters):
                raise ValueError("missing_required_parameter")
            header = payload.get("header", {})
            if header.get("time_standard") != "LST":
                raise ValueError(f"unexpected_time_standard:{header.get('time_standard')}")
            digest = hashlib.sha256(body).hexdigest()
            temporary = target.with_suffix(".json.tmp")
            with temporary.open("wb") as stream:
                stream.write(body); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, target)
            products = ",".join(header.get("sources", [])) or "not_reported"
            api_version = header.get("api", {}).get("version")
            validation = validate_candidates(ledger, cell_id, parameters, products, api_version)
            db = connect(ledger)
            with db:
                db.execute("UPDATE cells SET status=?,cache_file=?,cache_sha256=?,last_error=NULL,updated_at=? WHERE cell_id=?", ("valid" if validation["valid"] else "excluded", str(target), digest, now(), cell_id))
                db.execute("UPDATE attempts SET finished_at=?,outcome='success',response_sha256=? WHERE id=?", (now(), digest, attempt_id))
            db.close()
            return cell_id, "valid" if validation["valid"] else "excluded"
        except Exception as exc:
            error = f"{type(exc).__name__}:{exc}"[:1000]
            db = connect(ledger)
            with db:
                db.execute("UPDATE attempts SET finished_at=?,outcome='failed',error=? WHERE id=?", (now(), error, attempt_id))
                db.execute("UPDATE cells SET last_error=?,updated_at=? WHERE cell_id=?", (error, now(), cell_id))
                db.execute("UPDATE candidates SET collection_status='retry_pending',last_error=?,updated_at=? WHERE cell_id=? AND status='collecting'", (error, now(), cell_id))
            db.close()
            if attempt < retries:
                time.sleep(min(30, 2 ** attempt))
    db = connect(ledger)
    with db:
        db.execute("UPDATE cells SET status='failed',updated_at=? WHERE cell_id=?", (now(), cell_id))
        db.execute("UPDATE candidates SET status='failed',collection_status='failed',exclusion_reason='collection_failed_after_retries',updated_at=? WHERE cell_id=? AND status='collecting'", (now(), cell_id))
    db.close()
    return cell_id, "failed"


def value(series: dict, date: dt.date):
    return series.get(date.strftime("%Y%m%d"))


def predictive_reference(event_date: dt.date) -> tuple[dt.date, dt.date, list[dt.date]]:
    """Janela disponível no instante conservador: termina no dia LST anterior."""
    cutoff = event_date - dt.timedelta(days=1)
    rain_dates = [cutoff - dt.timedelta(days=offset) for offset in range(29, -1, -1)]
    return rain_dates[0], cutoff, rain_dates


def validate_candidates(ledger: Path, cell_id: str, parameters: dict, product: str, api_version: str | None) -> dict:
    db = connect(ledger)
    rows = db.execute("SELECT candidate_id,event_date FROM candidates WHERE cell_id=? AND status='collecting'", (cell_id,)).fetchall()
    valid = excluded = 0
    with db:
        for row in rows:
            event_date = dt.date.fromisoformat(row["event_date"])
            _, cutoff, rain_dates = predictive_reference(event_date)
            rain = [value(parameters["PRECTOTCORR"], date) for date in rain_dates]
            top = value(parameters["GWETTOP"], cutoff)
            root = value(parameters["GWETROOT"], cutoff)
            missing = ["rain_30d"] if any(item in (None, -999) for item in rain) else []
            if top in (None, -999): missing.append("gwettop_d_minus_1")
            if root in (None, -999): missing.append("gwetroot_d_minus_1")
            is_valid = not missing
            status = "valid" if is_valid else "excluded"
            reason = None if is_valid else "missing_power:" + ",".join(missing)
            db.execute("""UPDATE candidates SET status=?,collection_status='collected',product=?,api_version=?,
              reference_start=?,reference_end=?,time_standard='LST',validation=?,exclusion_reason=?,last_error=NULL,updated_at=?
              WHERE candidate_id=?""", (
                status, product, api_version, rain_dates[0].isoformat(), cutoff.isoformat(),
                "predictive_d_minus_1_complete" if is_valid else "predictive_d_minus_1_incomplete",
                reason, now(), row["candidate_id"],
            ))
            valid += int(is_valid); excluded += int(not is_valid)
    db.close()
    return {"valid": valid, "excluded": excluded}


def collect(args) -> dict:
    ledger = args.run_dir / "ledger.sqlite"
    db = connect(ledger)
    schema(db)
    # Interrupções anteriores voltam a pendente; o histórico da tentativa permanece.
    with db:
        db.execute("UPDATE cells SET status='pending' WHERE status='collecting'")
        db.execute("UPDATE candidates SET status='pending',collection_status='resume_pending' WHERE status='collecting'")
    rows = [dict(row) for row in db.execute("""SELECT DISTINCT c.cell_id,c.lat,c.lon FROM cells c
      JOIN candidates e ON e.cell_id=c.cell_id WHERE e.status IN ('pending','failed') ORDER BY c.cell_id""")]
    db.close()
    if args.limit_cells is not None:
        rows = rows[:args.limit_cells]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(collect_cell, ledger, args.run_dir / "cache", row, args.retries) for row in rows]
        for future in concurrent.futures.as_completed(futures):
            cell_id, status = future.result()
            print(json.dumps({"cell_id": cell_id, "status": status}), flush=True)
    db = connect(ledger)
    report = reconcile_db(db)
    write_json(args.run_dir / "reconciliation.json", report)
    db.close()
    return report


def reconcile_db(db: sqlite3.Connection) -> dict:
    counts = {status: db.execute("SELECT count(*) FROM candidates WHERE status=?", (status,)).fetchone()[0] for status in STATUSES}
    total = db.execute("SELECT count(*) FROM candidates").fetchone()[0]
    linked_rows = db.execute("SELECT event_ids FROM candidates").fetchall()
    event_links = sum(len(json.loads(row[0])) for row in linked_rows)
    active_cells = db.execute("SELECT count(DISTINCT cell_id) FROM candidates WHERE status!='excluded' OR collection_status='collected'").fetchone()[0]
    return {
        "generated_at": now(), "candidate_total": total, "status_counts": counts,
        "reconciled": sum(counts.values()) == total, "silent_loss": total - sum(counts.values()),
        "linked_event_rows": event_links, "candidate_cells": active_cells,
        "rule": "predictive features end at POWER LST D-1; same-day D is excluded because event time/zone is not reliable",
    }


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--catalog", type=Path, default=ROOT / "data" / "catalog.json")
    prep.add_argument("--run-dir", type=Path, required=True)
    get = sub.add_parser("collect")
    get.add_argument("--run-dir", type=Path, required=True)
    get.add_argument("--workers", type=int, default=3)
    get.add_argument("--retries", type=int, default=5)
    get.add_argument("--limit-cells", type=int)
    rec = sub.add_parser("reconcile")
    rec.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare": result = prepare(args)
    elif args.command == "collect": result = collect(args)
    else:
        db = connect(args.run_dir / "ledger.sqlite"); result = reconcile_db(db); db.close()
        write_json(args.run_dir / "reconciliation.json", result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("reconciled", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
