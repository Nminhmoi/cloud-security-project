(() => {
  "use strict";

  const main = document.querySelector("main");
  if (main && !main.id) main.id = "main-content";

  const status = document.getElementById("connection-status");
  const updateConnection = () => {
    if (!status) return;
    const offline = !navigator.onLine;
    status.hidden = !offline;
    status.textContent = offline
      ? "Bạn đang ngoại tuyến. Kiểm tra kết nối trước khi thử lại."
      : "Đã kết nối lại.";
    if (!offline) window.setTimeout(() => { status.hidden = true; }, 2400);
  };
  window.addEventListener("offline", updateConnection);
  window.addEventListener("online", updateConnection);
  updateConnection();

  const resetForm = (form) => {
    form.removeAttribute("aria-busy");
    form.querySelectorAll("[data-submit-label]").forEach((button) => {
      button.disabled = false;
      button.textContent = button.dataset.submitLabel;
      delete button.dataset.submitLabel;
    });
  };

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (form.dataset.submitting === "true") {
      event.preventDefault();
      return;
    }
    form.dataset.submitting = "true";
    form.setAttribute("aria-busy", "true");
    form.querySelectorAll('button[type="submit"], button:not([type])').forEach((button) => {
      button.dataset.submitLabel = button.textContent.trim();
      button.disabled = true;
      button.textContent = "Đang xử lý…";
    });
    window.setTimeout(() => {
      delete form.dataset.submitting;
      resetForm(form);
    }, 12000);
  });

  window.addEventListener("pageshow", () => {
    document.querySelectorAll('form[data-submitting="true"]').forEach((form) => {
      delete form.dataset.submitting;
      resetForm(form);
    });
  });
})();
