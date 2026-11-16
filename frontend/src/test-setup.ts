// The specs assert the French texts: the browser of the test runs in French.
Object.defineProperty(navigator, 'language', { value: 'fr-FR', configurable: true });
// A language chosen by one test must not leak into the next.
beforeEach(() => localStorage.clear());
