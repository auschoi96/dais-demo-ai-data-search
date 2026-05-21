import { createBrowserRouter, RouterProvider, NavLink, Outlet } from 'react-router';
import { AgentsPage } from './pages/agents/AgentsPage';
import { BenchmarkPage } from './pages/benchmark/BenchmarkPage';
import { DataComparePage } from './pages/compare/DataComparePage';

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
    isActive
      ? 'bg-[#FF3621] text-white'
      : 'text-white/80 hover:bg-white/10 hover:text-white'
  }`;

function Layout() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="px-6 h-14 flex items-center gap-4 bg-[#1B3139] text-white shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-xl font-black tracking-tight">Yape</span>
          <span className="text-sm text-white/60 hidden sm:inline">AI-Ready Search Demo</span>
        </div>
        <nav className="flex gap-1 ml-auto">
          <NavLink to="/" end className={navLinkClass}>
            Agents
          </NavLink>
          <NavLink to="/compare" className={navLinkClass}>
            Data Compare
          </NavLink>
          <NavLink to="/benchmark" className={navLinkClass}>
            Benchmark
          </NavLink>
        </nav>
      </header>

      <div className="flex-1 min-h-0">
        <Outlet />
      </div>
    </div>
  );
}

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <AgentsPage /> },
      { path: '/compare', element: <DataComparePage /> },
      { path: '/benchmark', element: <BenchmarkPage /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
