/** Single drawn number at its 1-based position. */
export interface DrawNumber {
  position: number;
  number: number;
}

/** Draw read model — mirrors backend DrawRead. */
export interface Draw {
  id: number;
  lottery_id: number;
  draw_number: number;
  draw_date: string;
  jackpot: string | null;
  winners: number | null;
  is_deleted: boolean;
  created_at: string;
  numbers: DrawNumber[];
  super_number: number | null;
}
