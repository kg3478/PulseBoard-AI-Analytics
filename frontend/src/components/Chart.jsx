import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

/**
 * Chart.jsx — Recharts wrapper that auto-selects bar / line / pie / table
 * based on the `chartType` prop returned by the backend.
 */

const COLORS = ['#6366F1', '#34D399', '#FBBF24', '#F87171', '#60A5FA', '#A78BFA', '#34D399', '#FB923C'];

const CHART_STYLE = {
  background: 'transparent',
};

const tooltipStyle = {
  backgroundColor: '#161B22',
  border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: '10px',
  color: '#E2E8F0',
  fontSize: '13px',
};

const axisStyle = {
  fill: '#64748B',
  fontSize: 11,
  fontFamily: 'Inter, sans-serif',
};

function truncateLabel(label, max = 14) {
  if (!label) return '';
  const str = String(label);
  return str.length > max ? str.slice(0, max) + '…' : str;
}

function BarChartView({ rows, columns }) {
  const labelCol = columns.find(c => c.type === 'text' || c.type === 'date')?.name || columns[0]?.name;
  const valueCol = columns.find(c => c.type === 'numeric')?.name || columns[1]?.name;

  if (!labelCol || !valueCol) return <TableView rows={rows} columns={columns} />;

  const data = rows.map(r => ({
    name: truncateLabel(r[labelCol]),
    [valueCol]: Number(r[valueCol]) || 0,
    _full: r[labelCol],
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} style={CHART_STYLE} barCategoryGap="30%">
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
        <XAxis dataKey="name" tick={axisStyle} axisLine={false} tickLine={false} />
        <YAxis tick={axisStyle} axisLine={false} tickLine={false} width={60}
          tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(1)}k` : v} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(99,102,241,0.08)' }} />
        <Bar dataKey={valueCol} fill="#6366F1" radius={[6, 6, 0, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function LineChartView({ rows, columns }) {
  const dateCol = columns.find(c => c.type === 'date')?.name || columns[0]?.name;
  const numericCols = columns.filter(c => c.type === 'numeric').map(c => c.name);

  if (!dateCol || numericCols.length === 0) return <TableView rows={rows} columns={columns} />;

  const data = rows.map(r => {
    const point = { name: truncateLabel(r[dateCol], 10) };
    numericCols.forEach(col => { point[col] = Number(r[col]) || 0; });
    return point;
  });

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} style={CHART_STYLE}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
        <XAxis dataKey="name" tick={axisStyle} axisLine={false} tickLine={false} />
        <YAxis tick={axisStyle} axisLine={false} tickLine={false} width={60}
          tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(1)}k` : v} />
        <Tooltip contentStyle={tooltipStyle} />
        {numericCols.slice(0, 3).map((col, i) => (
          <Line
            key={col}
            type="monotone"
            dataKey={col}
            stroke={COLORS[i]}
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 5, fill: COLORS[i] }}
          />
        ))}
        {numericCols.length > 1 && <Legend wrapperStyle={{ color: '#94A3B8', fontSize: 12 }} />}
      </LineChart>
    </ResponsiveContainer>
  );
}

function PieChartView({ rows, columns }) {
  const labelCol = columns.find(c => c.type === 'text')?.name || columns[0]?.name;
  const valueCol = columns.find(c => c.type === 'numeric')?.name || columns[1]?.name;

  if (!labelCol || !valueCol) return <BarChartView rows={rows} columns={columns} />;

  const data = rows.map(r => ({
    name: String(r[labelCol]),
    value: Math.abs(Number(r[valueCol]) || 0),
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          outerRadius={110}
          innerRadius={55}
          dataKey="value"
          paddingAngle={3}
          label={({ name, percent }) => `${truncateLabel(name, 10)} ${(percent * 100).toFixed(0)}%`}
          labelLine={false}
        >
          {data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip contentStyle={tooltipStyle} />
      </PieChart>
    </ResponsiveContainer>
  );
}

function TableView({ rows, columns }) {
  if (!rows?.length) return <p className="text-slate-500 text-sm">No data to display.</p>;

  return (
    <div className="overflow-x-auto max-h-72 overflow-y-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-navy-800">
          <tr>
            {columns.map(col => (
              <th key={col.name} className="text-left text-slate-500 font-medium px-4 py-2.5 whitespace-nowrap border-b border-white/5">
                {col.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 100).map((row, i) => (
            <tr key={i} className={`border-b border-white/5 last:border-0 ${i % 2 === 0 ? '' : 'bg-white/[0.015]'}`}>
              {columns.map(col => (
                <td key={col.name} className="px-4 py-2.5 text-slate-300 whitespace-nowrap font-mono text-xs">
                  {String(row[col.name] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 100 && (
        <p className="text-center text-slate-600 text-xs py-3">Showing 100 of {rows.length} rows</p>
      )}
    </div>
  );
}


function FunnelView({ rows }) {
  if (!rows?.length) return <TableView rows={rows} columns={[]} />;
  const maxUsers = rows[0]?.users || 1;

  return (
    <div className="space-y-3 py-2">
      {rows.map((row, i) => {
        const pct = Math.round((row.users / maxUsers) * 100);
        return (
          <div key={i}>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-slate-300 font-medium capitalize">{row.step}</span>
              <div className="flex items-center gap-3 text-slate-500">
                <span className="font-mono text-white">{row.users?.toLocaleString()} users</span>
                <span className="text-emerald-400 font-semibold">{row.conversion_rate}%</span>
                {i > 0 && <span className="text-rose-400">-{row.drop_off}%</span>}
              </div>
            </div>
            <div className="h-8 bg-white/5 rounded-lg overflow-hidden">
              <div
                className="h-full rounded-lg transition-all duration-500"
                style={{
                  width: `${pct}%`,
                  background: `linear-gradient(90deg, ${COLORS[i % COLORS.length]}cc, ${COLORS[i % COLORS.length]}66)`,
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function CohortView({ rows, columns }) {
  if (!rows?.length) return <TableView rows={rows} columns={columns} />;
  const weekCols = columns.filter(c => c.name.startsWith('week_'));

  const cellColor = (val) => {
    if (val === undefined || val === null) return 'transparent';
    const v = parseFloat(val);
    if (v >= 70) return 'rgba(52,211,153,0.35)';
    if (v >= 50) return 'rgba(52,211,153,0.2)';
    if (v >= 30) return 'rgba(251,191,36,0.2)';
    if (v >= 10) return 'rgba(248,113,113,0.2)';
    return 'rgba(248,113,113,0.1)';
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-white/5">
            <th className="text-left text-slate-500 font-medium px-3 py-2 whitespace-nowrap">Cohort</th>
            <th className="text-right text-slate-500 font-medium px-3 py-2">Size</th>
            {weekCols.map(c => (
              <th key={c.name} className="text-right text-slate-500 font-medium px-3 py-2">
                {c.name.replace('_', ' ').toUpperCase()}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-white/5 last:border-0">
              <td className="px-3 py-2 text-slate-300 font-mono whitespace-nowrap">{row.cohort}</td>
              <td className="px-3 py-2 text-right text-slate-400">{row.cohort_size?.toLocaleString()}</td>
              {weekCols.map(c => (
                <td key={c.name} className="px-3 py-2 text-right font-semibold"
                    style={{ backgroundColor: cellColor(row[c.name]) }}>
                  <span style={{ color: parseFloat(row[c.name]) >= 50 ? '#34D399' :
                                        parseFloat(row[c.name]) >= 20 ? '#FBBF24' : '#F87171' }}>
                    {row[c.name] != null ? `${row[c.name]}%` : '—'}
                  </span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Chart({ columns, rows, chartType }) {
  if (!rows?.length || !columns?.length) {
    return (
      <div className="flex items-center justify-center h-40 text-slate-500 text-sm">
        No results to display.
      </div>
    );
  }

  const chartMap = {
    bar:    <BarChartView rows={rows} columns={columns} />,
    line:   <LineChartView rows={rows} columns={columns} />,
    pie:    <PieChartView rows={rows} columns={columns} />,
    table:  <TableView rows={rows} columns={columns} />,
    funnel: <FunnelView rows={rows} columns={columns} />,
    cohort: <CohortView rows={rows} columns={columns} />,
  };

  return (
    <div>
      {/* Chart type badge */}
      <div className="flex justify-end mb-3">
        <span className="text-xs text-slate-600 font-mono bg-navy-900/50 px-2.5 py-1 rounded-lg border border-white/5">
          {chartType} chart · {rows.length} rows
        </span>
      </div>
      {chartMap[chartType] || <BarChartView rows={rows} columns={columns} />}
    </div>
  );
}
