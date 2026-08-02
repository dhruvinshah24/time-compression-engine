'use client';
import { Sidebar } from './Sidebar';

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen w-full bg-background overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col h-full overflow-y-auto">
        <header className="h-16 flex-shrink-0 border-b border-border bg-[#09090b]/80 backdrop-blur-md flex items-center px-8 z-10 sticky top-0">
          <div className="text-sm text-muted font-medium">Time Compression Engine / Workspace</div>
          <div className="ml-auto flex items-center gap-4">
            <button className="text-sm text-white bg-white/10 hover:bg-white/20 px-4 py-1.5 rounded-full transition-colors border border-white/10">
              Documentation
            </button>
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-accent to-purple-500 border border-white/20"></div>
          </div>
        </header>
        <main className="flex-1 p-8">
          {children}
        </main>
      </div>
    </div>
  );
}
