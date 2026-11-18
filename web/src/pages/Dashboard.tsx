import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  Phone,
  Clock,
  TrendingUp,
  Users,
  ArrowLeft,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { format, subDays, parseISO } from "date-fns";
import type { CallRecord } from "../types";

interface DashboardData {
  calls: CallRecord[];
  total_calls: number;
  avg_duration: number;
  recent_count: number;
  active_agents: number;
}

interface ChartDataPoint {
  date: string;
  label: string;
  calls: number;
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/calls")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch calls");
        return res.json();
      })
      .then((d: DashboardData) => setData(d))
      .catch((err) => {
        console.error("Dashboard fetch error:", err);
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-slate-400">Loading dashboard...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-300">
        <p>Error loading dashboard: {error}</p>
        <p className="text-sm mt-2 text-red-400">
          Make sure the API server is running on localhost:8080
        </p>
      </div>
    );
  }

  const calls = data?.calls ?? [];
  const totalCalls = data?.total_calls ?? calls.length;
  const avgDuration = data?.avg_duration ?? 0;
  const recentCount = data?.recent_count ?? 0;
  const activeAgents = data?.active_agents ?? 0;

  // Build chart data for last 7 days
  const chartData: ChartDataPoint[] = [];
  for (let i = 6; i >= 0; i--) {
    const day = subDays(new Date(), i);
    const dayStr = format(day, "yyyy-MM-dd");
    const dayCalls = calls.filter((c) => c.started_at.startsWith(dayStr)).length;
    chartData.push({
      date: dayStr,
      label: format(day, "EEE"),
      calls: dayCalls,
    });
  }

  const stats = [
    {
      label: "Total Calls",
      value: totalCalls.toString(),
      icon: Phone,
      color: "text-indigo-400",
    },
    {
      label: "Avg Duration",
      value: `${Math.floor(avgDuration / 60)}m ${Math.round(avgDuration % 60)}s`,
      icon: Clock,
      color: "text-emerald-400",
    },
    {
      label: "Recent (7 days)",
      value: recentCount.toString(),
      icon: TrendingUp,
      color: "text-amber-400",
    },
    {
      label: "Active Agents",
      value: activeAgents.toString(),
      icon: Users,
      color: "text-purple-400",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Back to call link */}
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Call
      </Link>

      <h1 className="text-2xl font-bold text-slate-100">Dashboard</h1>

      {/* Stats cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.label}
              className="dark-card rounded-xl p-5 border"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm text-slate-400">{stat.label}</span>
                <Icon className={`w-5 h-5 ${stat.color}`} />
              </div>
              <p className="text-2xl font-bold text-slate-100">{stat.value}</p>
            </div>
          );
        })}
      </div>

      {/* Chart */}
      <div className="dark-card rounded-xl p-6 border">
        <h2 className="text-lg font-semibold text-slate-100 mb-4">
          Calls per Day (Last 7 Days)
        </h2>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="label" stroke="#94a3b8" fontSize={12} />
            <YAxis stroke="#94a3b8" fontSize={12} allowDecimals={false} />
            <Tooltip
              contentStyle={{
                backgroundColor: "#1e293b",
                border: "1px solid #334155",
                borderRadius: "8px",
                color: "#f1f5f9",
              }}
            />
            <Bar dataKey="calls" fill="#6366f1" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Call history table */}
      <div className="dark-card rounded-xl border overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-700">
          <h2 className="text-lg font-semibold text-slate-100">Call History</h2>
        </div>
        {calls.length === 0 ? (
          <div className="px-6 py-12 text-center text-slate-400">
            <Phone className="w-8 h-8 mx-auto mb-3 opacity-50" />
            <p>No calls yet. Start a call from the call page.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400 text-left">
                  <th className="px-6 py-3 font-medium">Date</th>
                  <th className="px-6 py-3 font-medium">Agent</th>
                  <th className="px-6 py-3 font-medium">Duration</th>
                  <th className="px-6 py-3 font-medium">Summary</th>
                  <th className="px-6 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {calls.map((call) => (
                  <tr
                    key={call.id}
                    className="border-b border-slate-700/50 hover:bg-slate-700/30 transition-colors"
                  >
                    <td className="px-6 py-3 text-slate-300">
                      {format(parseISO(call.started_at), "MMM d, yyyy HH:mm")}
                    </td>
                    <td className="px-6 py-3 text-slate-300">{call.agent}</td>
                    <td className="px-6 py-3 text-slate-300">
                      {Math.floor(call.duration_seconds / 60)}m{" "}
                      {call.duration_seconds % 60}s
                    </td>
                    <td className="px-6 py-3 text-slate-400 max-w-xs truncate">
                      {call.summary || "—"}
                    </td>
                    <td className="px-6 py-3">
                      <StatusBadge status={call.status} />
                    </td>
                    <td className="px-6 py-3">
                      <Link
                        to={`/calls/${call.id}`}
                        className="text-indigo-400 hover:text-indigo-300 font-medium"
                      >
                        View →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    failed: "bg-red-500/20 text-red-400 border-red-500/30",
    in_progress: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  };
  const cls = colors[status] || colors.completed;
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${cls}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}