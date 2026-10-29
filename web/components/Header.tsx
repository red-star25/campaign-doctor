export function Header() {
  return (
    <header className="border-b border-line">
      <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-5 py-3 md:px-8">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="font-serif text-2xl tracking-tight text-ink">Campaign Doctor</h1>
          <p className="text-sm text-ink">Campaign reliability investigation</p>
        </div>
        <p className="inline-flex w-fit shrink-0 items-center gap-2 whitespace-nowrap rounded-full border border-line-strong bg-raised px-3 py-1 font-mono text-xs font-medium uppercase tracking-[0.12em] text-copper">
          <span className="size-1.5 rounded-full bg-copper" aria-hidden />
          Independent demo · Synthetic data
        </p>
      </div>
    </header>
  );
}
