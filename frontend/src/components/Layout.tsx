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
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-8">
        <Link to="/" className="text-xl font-bold text-emerald-600">CaloriSee</Link>
        <nav className="flex gap-1">
          {NAV.map(({ to, label, icon: Icon }) => {
            const active = pathname === to || (to !== '/' && pathname.startsWith(to));
            const href = to === '/' ? to : ds ? `${to}?ds=${ds}` : to;
            return (
              <Link
                key={to}
                to={href}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  active ? 'bg-emerald-50 text-emerald-700' : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <Icon size={16} />
                {label}
              </Link>
            );
          })}
        </nav>
      </header>
      <main className="flex-1 p-6 max-w-7xl mx-auto w-full">{children}</main>
    </div>
  );
}
