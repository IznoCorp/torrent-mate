// The interface's words, loaded for a unit test that reads them.
//
// A pure function that says something reads `i18next`, and a runner has no
// shell to initialise it. Importing this module for its side effect runs the
// same bootstrap the shell runs (`i18n/index.ts`), so the words a test sees are
// the committed resources and nothing a test file retypes.
//
// IT LIVES IN `lib/` ON PURPOSE. A test that imported `i18n/fr.json` itself
// would count as one more feature reading the resources, and the boundaries'
// fan-in arm refuses a module that more than four features read; the frame
// reaches the bootstrap through `lib/` already, so a test going the same way
// adds no reader.
import i18next from "../i18n";

export default i18next;
