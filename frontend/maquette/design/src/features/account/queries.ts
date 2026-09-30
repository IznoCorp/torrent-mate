// What Compte asks the server for — the account's read lives in `lib/account.ts`,
// where every surface that draws by rights reads it too.
export { accountQuery, heldRights, useAccount, useRights, type Account } from "../../lib/account";
