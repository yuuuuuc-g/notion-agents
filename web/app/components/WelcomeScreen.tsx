"use client";

export default function WelcomeScreen() {
  return (
    <div className="flex flex-col items-center justify-center h-[60vh] space-y-8 text-center animate-in fade-in zoom-in duration-700">
      <div className="w-24 h-24 bg-gradient-to-tr from-slate-50 to-slate-100 rounded-[2.5rem] flex items-center justify-center shadow-lg border border-slate-100 relative overflow-hidden">
        <div className="absolute inset-0 bg-emerald-500/5 blur-xl rounded-full"></div>
        <span className="text-5xl filter grayscale-[0.2] opacity-80 relative z-10">🌱</span>
      </div>
      <div className="space-y-2">
        <h2 className="text-2xl font-bold tracking-tight text-slate-700">GOODGOODSTUDYDAYDAYUP</h2>
        <p className="text-slate-500 text-sm font-medium tracking-wide">Ready to learn something new?</p>
      </div>
    </div>
  );
}
