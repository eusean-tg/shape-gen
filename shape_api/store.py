"""Durable jobs and replayable events. One service process owns the worker."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

TERMINAL = {'succeeded', 'failed', 'canceled', 'interrupted'}


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.directory / 'jobs.sqlite3')
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
            request TEXT NOT NULL, record TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
            kind TEXT NOT NULL, data TEXT NOT NULL, created TEXT NOT NULL);
          CREATE INDEX IF NOT EXISTS job_events ON events(job_id,id);
          CREATE TABLE IF NOT EXISTS assets (id TEXT PRIMARY KEY, record TEXT NOT NULL);
        ''')
        self.db.commit()

    def get(self, job_id):
        row = self.db.execute('SELECT record FROM jobs WHERE id=?', (job_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def asset(self, asset_id):
        row = self.db.execute('SELECT record FROM assets WHERE id=?', (asset_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def add_asset(self, record):
        previous = self.asset(record['id'])
        if previous:
            return previous
        with self.db:
            self.db.execute('INSERT INTO assets VALUES (?,?)', (record['id'], json.dumps(record)))
        return record

    def jobs(self):
        return [json.loads(r[0]) for r in self.db.execute('SELECT record FROM jobs ORDER BY rowid')]

    def submit(self, request):
        encoded = json.dumps(request, sort_keys=True, separators=(',', ':'))
        previous = self.db.execute('SELECT request,record FROM jobs WHERE request_id=?',
                                   (request['request_id'],)).fetchone()
        if previous:
            if previous['request'] != encoded:
                raise ValueError('request_id already belongs to different parameters')
            return json.loads(previous['record']), False
        job_id = uuid4().hex
        record = {'id': job_id, 'request': request, 'state': 'queued', 'stage': None,
                  'created_at': now(), 'updated_at': now(), 'cancel_requested': False,
                  'error': None, 'process': None, 'validation': None, 'artifacts': []}
        with self.db:
            self.db.execute('INSERT INTO jobs VALUES (?,?,?,?)',
                            (job_id, request['request_id'], encoded, json.dumps(record)))
            self._event(job_id, 'status', {'state': 'queued', 'stage': None})
        return record, True

    def _event(self, job_id, kind, data):
        self.db.execute('INSERT INTO events(job_id,kind,data,created) VALUES (?,?,?,?)',
                        (job_id, kind, json.dumps(data), now()))

    def event(self, job_id, kind, data):
        with self.db:
            self._event(job_id, kind, data)

    def update(self, job_id, **changes):
        record = self.get(job_id)
        record.update(changes, updated_at=now())
        with self.db:
            self.db.execute('UPDATE jobs SET record=? WHERE id=?', (json.dumps(record), job_id))
            self._event(job_id, 'status', {k: record[k] for k in
                                         ('state', 'stage', 'cancel_requested', 'error', 'validation')})
        return record

    def events(self, job_id, after=0, limit=200):
        return [dict(id=r['id'], event=r['kind'], data=json.loads(r['data']), created_at=r['created'])
                for r in self.db.execute(
                    'SELECT * FROM events WHERE job_id=? AND id>? ORDER BY id LIMIT ?',
                    (job_id, after, limit))]
