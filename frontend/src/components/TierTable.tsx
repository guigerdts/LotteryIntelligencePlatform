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
  { matches: "5 números",   prize: "Premio fijo" },
  { matches: "4 + Superbalota",   prize: "Premio fijo" },
  { matches: "4 números",   prize: "Premio fijo" },
  { matches: "3 + Superbalota",   prize: "Premio fijo" },
  { matches: "3 números",   prize: "Premio fijo" },
   { matches: "2 + Superbalota", prize: "Pari-mutuel" },
   { matches: "0 + Superbalota", prize: "Reembolso de apuesta" },
];

/**
 * Static reference table of the eight official prize tiers. Rendered on the
 * Mis Números page regardless of pipeline state.
 */
export default function TierTable() {
  return (
    <table className="w-full border-collapse text-left text-sm">
      <caption className="sr-only">Categorías de premios</caption>
      <thead className="border-b border-border bg-surface-2 text-xs uppercase tracking-wide text-ink-2">
        <tr>
          <th scope="col" className="px-3 py-2 font-semibold">
             Aciertos
           </th>
          <th scope="col" className="px-3 py-2 font-semibold">
             Categoría oficial de premio
           </th>
        </tr>
      </thead>
      <tbody>
        {TIERS.map((tier) => (
          <tr key={tier.matches} className="border-b border-border">
            <td className="px-3 py-2 text-ink">{tier.matches}</td>
            <td className="px-3 py-2 text-ink">{tier.prize}</td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
            <td colSpan={2} className="px-3 py-2 text-xs text-ink-3">
            Referencia de las reglas oficiales únicamente — nunca una promesa de resultados.
          </td>
        </tr>
      </tfoot>
    </table>
  );
}
