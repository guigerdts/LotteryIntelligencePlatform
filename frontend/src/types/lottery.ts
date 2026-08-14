/** Lottery read model — mirrors backend LotteryRead. */
export interface Lottery {
  id: number;
  code: string;
  name: string;
  country: string;
  description: string | null;
  min_number: number;
  max_number: number;
  numbers_to_select: number;
  super_number_min: number | null;
  super_number_max: number | null;
  created_at: string;
}

/** Lightweight option for the global selector. */
export interface LotteryOption {
  id: number;
  code: string;
  name: string;
  country: string;
}
