import LotterySelector from "./LotterySelector";

/** Top bar with the global lottery selector and brand title. */
export default function Header() {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between gap-4 border-b border-gray-200 bg-white px-4 sm:px-6">
      <h1 className="text-base font-semibold text-gray-900 sm:text-lg">
        Lottery Intelligence Platform
      </h1>
      <LotterySelector />
    </header>
  );
}