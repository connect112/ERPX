import { z } from "zod";

/**
 * `z.coerce.number()` for form fields, typed the way Zod 3 typed it.
 *
 * Zod 4 declares the input of every coerced schema as `unknown`. react-hook-form's resolver types are
 * built from that input type, so a form whose schema uses `z.coerce.number()` stops type-checking
 * (the field's type can no longer be inferred). Zod 3 declared the input as `number`, and every form
 * in this app is typed that way, so the input type is pinned back to `number` here.
 *
 * Runtime behaviour is exactly that of `z.coerce.number()` (it calls `Number(value)`, so the text an
 * `<input>` yields is converted when validating); only the declared type differs. Chain `.min()`,
 * `.int()`, `.default()` and friends as usual.
 */
export const coerceNumber = (params?: Parameters<typeof z.coerce.number>[0]) => z.coerce.number<number>(params);
