import Link from "next/link";

export default function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between px-6">
        <Link href="/" className="text-xl font-bold text-slate-900">
          Legal<span className="text-blue-600">Flow</span>
        </Link>

        <nav className="hidden items-center gap-6 md:flex">
          <a href="#features" className="text-sm text-slate-600 hover:text-slate-900">
            Caracteristicas
          </a>
          <a href="#how" className="text-sm text-slate-600 hover:text-slate-900">
            Flujo
          </a>
          <Link href="/demo" className="text-sm text-slate-600 hover:text-slate-900">
            Workflow Demo
          </Link>
          <Link
            href="/dashboard"
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          >
            Ir al Dashboard
          </Link>
        </nav>
      </div>
    </header>
  );
}
