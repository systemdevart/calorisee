import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { BarChart3, Upload, Calendar } from 'lucide-react';

const NAV = [
  { to: '/', label: 'Import', icon: Upload },
  { to: '/dashboard', label: 'Dashboard', icon: BarChart3 },
  { to: '/days', label: 'Days', icon: Calendar },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const [params] = useSearchParams();
  const ds = params.get('ds');

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-gray-200 px-3 sm:px-6 py-3 flex items-center gap-3 sm:gap-8">
        <Link to="/" className="text-lg sm:text-xl font-bold text-emerald-600 shrink-0 mr-auto">CaloriSee</Link>
        <nav className="flex gap-0.5 sm:gap-1 min-w-0">
          {NAV.map(({ to, label, icon: Icon }) => {
            const active = pathname === to || (to !== '/' && pathname.startsWith(to));
            const href = to === '/' ? to : ds ? `${to}?ds=${ds}` : to;
            return (
              <Link
                key={to}
                to={href}
                className={`flex items-center gap-1 px-2 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-colors whitespace-nowrap ${
                  active ? 'bg-emerald-50 text-emerald-700' : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <Icon size={16} className="shrink-0" />
                <span className="hidden sm:inline">{label}</span>
                <span className="sm:hidden">{label}</span>
              </Link>
            );
          })}
        </nav>
      </header>
      <main className="flex-1 p-6 max-w-7xl mx-auto w-full">{children}</main>
    </div>
  );
}
