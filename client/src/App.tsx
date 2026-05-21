import { createBrowserRouter, RouterProvider, NavLink, Outlet } from 'react-router';
import { Card, CardContent, CardHeader, CardTitle } from '@databricks/appkit-ui/react';
import { SearchPage } from './pages/search/SearchPage';
import { BenchmarkPage } from './pages/benchmark/BenchmarkPage';
import { DataComparePage } from './pages/compare/DataComparePage';

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
    isActive
      ? 'bg-[#742284] text-white'
      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
  }`;

function Layout() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="border-b px-6 py-3 flex items-center gap-4 bg-[#742284] text-white">
        <div className="flex items-center gap-2">
          <span className="text-2xl font-black tracking-tight">Yape</span>
          <span className="text-sm opacity-80 hidden sm:inline">AI-Ready Search Demo</span>
        </div>
        <nav className="flex gap-1 ml-auto">
          <NavLink to="/" end className={navLinkClass}>
            Home
          </NavLink>
          <NavLink to="/search" className={navLinkClass}>
            Search
          </NavLink>
          <NavLink to="/benchmark" className={navLinkClass}>
            Benchmark
          </NavLink>
          <NavLink to="/compare" className={navLinkClass}>
            Data Compare
          </NavLink>
        </nav>
      </header>

      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/search', element: <SearchPage /> },
      { path: '/benchmark', element: <BenchmarkPage /> },
      { path: '/compare', element: <DataComparePage /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}

function HomePage() {
  return (
    <div className="max-w-3xl mx-auto space-y-6 mt-8">
      <div className="text-center">
        <h2 className="text-3xl font-bold mb-2 text-foreground">
          Vibe Coding vs AI-Ready Data
        </h2>
        <p className="text-lg text-muted-foreground">
          Search improves when structured data is semantic, governed, and vectorized — not just when you add a better agent.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="shadow-lg border-[#742284]/20">
          <CardHeader>
            <CardTitle>Four search tiers</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground space-y-2">
            <p>T0: keyword on raw catalog</p>
            <p>T1: Vector Search on raw UC table</p>
            <p>T2: Vector Search on enriched AI-ready data</p>
            <p>T3: Supervisor API + Opus 4.7 on raw index</p>
          </CardContent>
        </Card>

        <Card className="shadow-lg border-[#742284]/20">
          <CardHeader>
            <CardTitle>Hero queries</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground space-y-2">
            <p><strong>I want to save money</strong> → Yape Savings Fund (s08)</p>
            <p><strong>quiero ahorrar</strong> → same intent in Spanish</p>
            <p>Both fail on raw data; Tier 2 resolves them.</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
