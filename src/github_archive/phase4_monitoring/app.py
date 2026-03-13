"""
Pipeline Monitoring Dashboard — Cloud Run Service

Serves a lightweight HTML dashboard showing pipeline health metrics.
Queries BigQuery (log sink export) on each page load.
No frontend framework — plain HTML tables rendered server-side.
"""

import os
import logging
from flask import Flask, render_template
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv('PROJECT_ID')
DATASET_ID = os.getenv('DATASET_ID', 'pipeline_logs')

app = Flask(__name__)
bq_client = bigquery.Client(project=PROJECT_ID)


def _run_query(query_name: str) -> list[dict]:
    """Load and run a SQL query file, return rows as list of dicts."""
    query_path = os.path.join(os.path.dirname(__file__), 'queries', f'{query_name}.sql')
    with open(query_path) as f:
        sql = f.read().replace('PROJECT_ID', PROJECT_ID)

    rows = bq_client.query(sql).result()
    return [dict(row) for row in rows]


@app.route('/')
def dashboard():
    """Main dashboard page."""
    daily = _run_query('daily_throughput')
    errors = _run_query('pipeline_errors')
    return render_template('dashboard.html', daily=daily, errors=errors)


@app.route('/phase2')
def phase2_detail():
    """Phase 2 processing detail."""
    files = _run_query('phase2_processing_summary')
    return render_template('phase2.html', files=files)


@app.route('/phase3')
def phase3_detail():
    """Phase 3 BQ load detail."""
    loads = _run_query('phase3_bq_load_summary')
    return render_template('phase3.html', loads=loads)


@app.route('/health')
def health():
    return {'status': 'healthy'}, 200


if __name__ == '__main__':
    port = int(os.getenv('PORT', '8080'))
    app.run(host='0.0.0.0', port=port, debug=False)
