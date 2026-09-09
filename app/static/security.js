(() => {
  "use strict";

  const token = document.querySelector('meta[name="csrf-token"]')?.content;
  const originalFetch = window.fetch.bind(window);
  const safeMethods = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);

  window.fetch = (input, init = {}) => {
    const method = String(init.method || input?.method || "GET").toUpperCase();
    const rawUrl =
      typeof input === "string" || input instanceof URL ? input : input.url;
    const url = new URL(rawUrl, window.location.href);
    if (token && !safeMethods.has(method) && url.origin === window.location.origin) {
      const headers = new Headers(
        init.headers || (input instanceof Request ? input.headers : undefined)
      );
      headers.set("X-CSRFToken", token);
      init = { ...init, headers };
    }
    return originalFetch(input, init);
  };
})();
