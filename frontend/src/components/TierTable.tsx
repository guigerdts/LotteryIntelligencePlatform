interface PrizeTier {
  matches: string;
  prize: string;
}

/**
 * The eight official Baloto prize tiers (5+SB jackpot … 0+SB bet refund),
 * presented as a static official-rules reference — never as an outcome
 * promise (R5).
 */
const TIERS: PrizeTier[] = [
  { matches: "5 + Superbalota", prize: "Jackpot" },
  { matches: "5 numbers", prize: "Fixed prize" },
  { matches: "4 + Superbalota", prize: "Fixed prize" },
  { matches: "4 numbers", prize: "Fixed prize" },
  { matches: "3 + Superbalota", prize: "Fixed prize" },
  { matches: "3 numbers", prize: "Fixed prize" },
  { matches: "2 + Superbalota", prize: "Paramutual" },
  { matches: "0 + Superbalota", prize: "Bet refund" },
];

/**
 * Static reference table of the eight official prize tiers. Rendered on the
 * Mis Números page regardless of pipeline state.
 */
export default function TierTable() {
  return (
    <table className="w-full border-collapse text-left text-sm">
      <caption className="sr-only">Prize tiers</caption>
      <thead className="border-b border-gray-200 bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
        <tr>
          <th scope="col" className="px-3 py-2 font-semibold">
            Match
          </th>
          <th scope="col" className="px-3 py-2 font-semibold">
            Official prize category
          </th>
        </tr>
      </thead>
      <tbody>
        {TIERS.map((tier) => (
          <tr key={tier.matches} className="border-b border-gray-100">
            <td className="px-3 py-2 text-gray-900">{tier.matches}</td>
            <td className="px-3 py-2 text-gray-900">{tier.prize}</td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <td colSpan={2} className="px-3 py-2 text-xs text-gray-500">
            Official-rules reference only — never a promise of outcomes.
          </td>
        </tr>
      </tfoot>
    </table>
  );
}
