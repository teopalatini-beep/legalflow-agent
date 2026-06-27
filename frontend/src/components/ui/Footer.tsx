export default function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-2 px-6 py-8 text-sm text-slate-500 md:flex-row md:items-center md:justify-between">
        <p>&copy; {new Date().getFullYear()} LegalFlow. All rights reserved.</p>
        <p>LegalTech AI Workflow Platform</p>
      </div>
    </footer>
  );
}
