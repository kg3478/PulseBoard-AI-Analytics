from flask import Flask, request, jsonify
import pandas as pd
import numpy as np
import duckdb
import io
import os
import google.generativeai as genai

app = Flask(__name__)


def detect_schema(df):
    columns = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        if 'float' in dtype or 'int' in dtype:
            col_type = 'numeric'
        else:
            try:
                pd.to_datetime(df[col].dropna().iloc[:3], infer_datetime_format=True)
                col_type = 'date'
            except Exception:
                col_type = 'text'
        columns.append({'name': col, 'type': col_type})
    return {'columns': columns, 'row_count': len(df)}


def suggest_questions(schema):
    num = [c['name'] for c in schema['columns'] if c['type'] == 'numeric']
    dat = [c['name'] for c in schema['columns'] if c['type'] == 'date']
    q = []
    if num:
        q.append(f"What is the sum of {num[0]}?")
    if len(num) >= 2:
        q.append(f"Compare {num[0]} and {num[1]}")
    if dat and num:
        q.append(f"Which date has the highest {num[0]}?")
        q.append(f"Show me {num[0]} by {dat[0]}")
    q.append("Show me the top 10 rows")
    return q[:5]


def infer_chart_type(columns, rows):
    date_cols = [c for c in columns if c['type'] == 'date']
    num_cols = [c for c in columns if c['type'] == 'numeric']
    txt_cols = [c for c in columns if c['type'] == 'text']
    if len(rows) <= 1:
        return 'table'
    if date_cols and num_cols:
        return 'line'
    if txt_cols and num_cols and len(rows) <= 8:
        return 'pie'
    if txt_cols and num_cols:
        return 'bar'
    return 'table'


def run_nl_to_sql(question, schema, df, error_context=''):
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise Exception('GEMINI_API_KEY not configured on Vercel.')
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    cols = '\n'.join(f"  - {c['name']} ({c['type']})" for c in schema['columns'])
    error_hint = f'\nPrevious attempt failed with: {error_context}\nFix the error.' if error_context else ''
    prompt = f"""You are a SQL expert. Generate a DuckDB SQL query.
Table name: csv_data
Columns:
{cols}
{error_hint}
Rules: Return ONLY raw SQL. No markdown. No backticks.
Question: {question}
SQL:"""
    response = model.generate_content(prompt)
    sql = response.text.strip().replace('```sql', '').replace('```', '').strip()
    return sql


def execute_query(sql, df):
    con = duckdb.connect(':memory:')
    con.register('csv_data', df)
    result_df = con.execute(sql).fetchdf()
    con.close()
    columns = []
    for col in result_df.columns:
        dtype = str(result_df[col].dtype)
        col_type = 'numeric' if ('float' in dtype or 'int' in dtype) else 'text'
        columns.append({'name': col, 'type': col_type})
    rows = result_df.where(pd.notnull(result_df), None).values.tolist()
    return columns, rows


@app.route('/api/upload', methods=['POST', 'OPTIONS'])
def upload():
    if request.method == 'OPTIONS':
        return _cors('', 204)
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    content = file.read().decode('utf-8')
    df = pd.read_csv(io.StringIO(content))
    schema = detect_schema(df)
    return jsonify({
        'session_id': 'local',
        'filename': file.filename,
        'schema': schema,
        'starter_questions': suggest_questions(schema),
        'csv_content': content,
    })


@app.route('/api/query', methods=['POST', 'OPTIONS'])
def query():
    if request.method == 'OPTIONS':
        return _cors('', 204)
    data = request.json or {}
    question = data.get('question', '')
    csv_content = data.get('csv_content', '')
    schema = data.get('schema', {})
    if not question or not csv_content:
        return jsonify({'success': False, 'error': 'Missing question or csv_content'}), 400
    df = pd.read_csv(io.StringIO(csv_content))
    try:
        sql = run_nl_to_sql(question, schema, df)
        columns, rows = execute_query(sql, df)
        attempts = 1
    except Exception as e1:
        try:
            sql = run_nl_to_sql(question, schema, df, error_context=str(e1))
            columns, rows = execute_query(sql, df)
            attempts = 2
        except Exception as e2:
            return jsonify({'success': False, 'error': str(e2), 'sql': sql}), 422
    chart_type = infer_chart_type(columns, rows)
    return jsonify({
        'success': True,
        'question': question,
        'sql': sql,
        'result': {'columns': columns, 'rows': rows, 'chart_type': chart_type},
        'attempts': attempts,
    })


@app.route('/api/anomalies', methods=['POST', 'OPTIONS'])
def anomalies():
    if request.method == 'OPTIONS':
        return _cors('', 204)
    data = request.json or {}
    csv_content = data.get('csv_content', '')
    if not csv_content:
        return jsonify({'alerts': [], 'total': 0})
    df = pd.read_csv(io.StringIO(csv_content))
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    alerts = []
    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) < 7:
            continue
        window = series.iloc[-31:-1] if len(series) >= 31 else series.iloc[:-1]
        latest = float(series.iloc[-1])
        mean = float(window.mean())
        std = float(window.std())
        if std == 0:
            continue
        z = (latest - mean) / std
        if abs(z) > 2.0:
            direction = 'spike' if z > 0 else 'drop'
            pct = round((latest - mean) / mean * 100, 1) if mean != 0 else 0
            severity = 'critical' if abs(z) > 3.0 else 'warning'
            emoji = '🚨' if severity == 'critical' else '⚠️'
            alerts.append({
                'column': col, 'current_value': round(latest, 2),
                'baseline_mean': round(mean, 2), 'z_score': round(z, 2),
                'severity': severity, 'direction': direction, 'pct_change': pct,
                'message': f'{emoji} {col} {("jumped" if direction == "spike" else "dropped")} {abs(pct):.1f}% from the 30-day baseline.',
            })
    alerts.sort(key=lambda x: (0 if x['severity'] == 'critical' else 1, -abs(x['z_score'])))
    return jsonify({'alerts': alerts, 'total': len(alerts)})


@app.route('/api/insights', methods=['POST', 'OPTIONS'])
def insights():
    if request.method == 'OPTIONS':
        return _cors('', 204)
    data = request.json or {}
    csv_content = data.get('csv_content', '')
    if not csv_content:
        return jsonify({'bullets': ['Upload a CSV to generate insights.'], 'deltas': {}})
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return jsonify({'bullets': ['Set GEMINI_API_KEY in Vercel environment variables.'], 'deltas': {}})
    df = pd.read_csv(io.StringIO(csv_content))
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    mid = len(df) // 2
    this_week = df.iloc[mid:][numeric_cols].mean()
    last_week = df.iloc[:mid][numeric_cols].mean()
    deltas = {}
    delta_lines = []
    for col in numeric_cols[:6]:
        lw = last_week[col]
        tw = this_week[col]
        pct = round((tw - lw) / lw * 100, 1) if lw != 0 else 0
        deltas[col] = {'this_period': round(tw, 2), 'last_period': round(lw, 2), 'pct_change': pct}
        arrow = '↑' if pct > 0 else '↓'
        delta_lines.append(f"- {col}: {arrow} {abs(pct)}%")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""You are a startup analytics advisor. Here are week-over-week metric changes:
{chr(10).join(delta_lines)}
Write 3-5 plain-English bullet points (start each with •) for a non-technical founder.
Be specific, actionable, and encouraging. Focus on what matters most."""
    try:
        response = model.generate_content(prompt)
        bullets = [b.strip().lstrip('•').strip() for b in response.text.strip().split('\n') if b.strip()]
    except Exception as e:
        bullets = [f'Insight generation failed: {str(e)}']
    return jsonify({'bullets': bullets, 'deltas': deltas})


@app.route('/api/root-cause', methods=['POST', 'OPTIONS'])
def root_cause():
    if request.method == 'OPTIONS':
        return _cors('', 204)
    data = request.json or {}
    csv_content = data.get('csv_content', '')
    column = data.get('column', '')
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key or not csv_content:
        return jsonify({'analysis': 'Configure GEMINI_API_KEY and upload a CSV first.'})
    df = pd.read_csv(io.StringIO(csv_content))
    summary = df.describe().to_string()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""A startup founder asks: "Why did {column} change?"
Dataset statistics:
{summary}
Give 2-3 specific, actionable reasons. Number each reason (1. 2. 3.). Use simple language."""
    try:
        response = model.generate_content(prompt)
        return jsonify({'analysis': response.text.strip()})
    except Exception as e:
        return jsonify({'analysis': f'Analysis failed: {str(e)}'})


def _cors(body, status=200):
    from flask import make_response
    resp = make_response(body, status)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return resp


@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response
