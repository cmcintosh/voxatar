import { NavLink, Link } from "react-router-dom";
import { LayoutDashboard, Phone, BookOpen, Settings, Mic } from "lucide-react";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/dashboard", label: "Calls", icon: Phone },
  { to: "/knowledge", label: "Knowledge", icon: BookOpen },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-64 bg-slate-800 border-r border-slate-700 flex-col">
        <div className="px-6 py-5 border-b border-slate-700">
          <Link to="/dashboard" className="flex items-center gap-2">
            <Mic className="w-6 h-6 text-indigo-500" />
            <span className="text-lg font-bold text-slate-100">Voxatar</span>
          </Link>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item, i) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={`${item.to}-${i}`}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-indigo-500 text-white"
                      : "text-slate-300 hover:bg-slate-700 hover:text-slate-100"
                  }`
                }
              >
                <Icon className="w-5 h-5" />
                {item.label}
              </NavLink>
            );
          })}
        </nav>

        <div className="px-6 py-4 border-t border-slate-700">
          <p className="text-xs text-slate-400">Agent</p>
          <p className="text-sm font-medium text-slate-200">Default Agent</p>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="md:hidden bg-slate-800 border-b border-slate-700 px-4 py-3 flex items-center justify-between">
        <Link to="/dashboard" className="flex items-center gap-2">
          <Mic className="w-5 h-5 text-indigo-500" />
          <span className="text-base font-bold text-slate-100">Voxatar</span>
        </Link>
        <nav className="flex items-center gap-1">
          {navItems.map((item, i) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={`mobile-${item.to}-${i}`}
                to={item.to}
                className={({ isActive }) =>
                  `p-2 rounded-lg transition-colors ${
                    isActive
                      ? "bg-indigo-500 text-white"
                      : "text-slate-400 hover:text-slate-100"
                  }`
                }
              >
                <Icon className="w-5 h-5" />
              </NavLink>
            );
          })}
        </nav>
      </div>
    </>
  );
}