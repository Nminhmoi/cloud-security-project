(() => {
  "use strict";

  const config = window.cloudBoxWorkspace || {};
  const viewInfo = {
    mine: ["Tài liệu của tôi", "Quản lý, tải xuống và chia sẻ tài liệu của bạn."],
    favorite: ["Tài liệu yêu thích", "Những tài liệu quan trọng bạn đã đánh dấu."],
    shared: ["Tài liệu chia sẻ", "Tài liệu người khác đã chia sẻ với bạn."],
    deleted: ["Tài liệu đã xóa", "Khôi phục những tài liệu bạn còn cần."]
  };
  const dialog = document.getElementById("share-dialog");
  if (!dialog) return;

  const uploadInput = document.getElementById("document-upload");
  const uploadZone = document.querySelector("[data-upload-zone]");
  const uploadPreview = document.getElementById("upload-preview");
  const uploadFilename = document.getElementById("upload-filename");
  const uploadMetadata = document.getElementById("upload-metadata");
  const uploadSubmit = document.getElementById("upload-submit");
  const clearUpload = document.getElementById("clear-upload");

  const form = document.getElementById("share-form");
  const filename = document.getElementById("share-filename");
  const search = document.getElementById("people-search-input");
  const results = document.getElementById("people-results");
  const selected = document.getElementById("selected-person");
  const recipient = document.getElementById("selected-recipient");
  const submit = document.getElementById("share-submit");
  const review = document.getElementById("share-review");
  const reviewCopy = document.getElementById("share-review-copy");
  const shareError = document.getElementById("share-error");
  const accessList = document.getElementById("current-access-list");
  const shareCount = document.getElementById("share-count");
  let activeDocument;
  let activeIndex = -1;
  let searchTimer;
  let searchController;
  let dialogTrigger;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  const escapeHtml = (value) => {
    const node = document.createElement("span");
    node.textContent = String(value ?? "");
    return node.innerHTML;
  };

  const formatFileSize = (bytes) => {
    if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / (1024 ** index);
    return `${value.toLocaleString("vi-VN", { maximumFractionDigits: index ? 1 : 0 })} ${units[index]}`;
  };

  function resetUpload() {
    uploadInput.value = "";
    uploadPreview.hidden = true;
    uploadSubmit.disabled = true;
    uploadFilename.textContent = "";
    uploadMetadata.textContent = "";
    uploadZone.classList.remove("has-file");
    uploadInput.focus();
  }

  function renderSelectedFile() {
    const file = uploadInput.files?.[0];
    if (!file) return resetUpload();
    uploadFilename.textContent = file.name;
    uploadMetadata.textContent = `${file.type || "Không xác định định dạng"} · ${formatFileSize(file.size)}`;
    uploadPreview.hidden = false;
    uploadSubmit.disabled = false;
    uploadZone.classList.add("has-file");
  }

  uploadInput.addEventListener("change", renderSelectedFile);
  clearUpload.addEventListener("click", resetUpload);

  ["dragenter", "dragover"].forEach((eventName) => uploadZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    if ([...event.dataTransfer.types].includes("Files")) uploadZone.classList.add("is-dragging");
  }));
  ["dragleave", "drop"].forEach((eventName) => uploadZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    if (eventName === "dragleave" && uploadZone.contains(event.relatedTarget)) return;
    uploadZone.classList.remove("is-dragging");
  }));
  uploadZone.addEventListener("drop", (event) => {
    const files = event.dataTransfer.files;
    if (!files.length) return;
    const transfer = new DataTransfer();
    transfer.items.add(files[0]);
    uploadInput.files = transfer.files;
    renderSelectedFile();
  });

  const uploadSuccess = document.querySelector("[data-upload-success]");
  if (uploadSuccess) {
    const cleanUrl = new URL(window.location.href);
    cleanUrl.searchParams.delete("uploaded");
    history.replaceState(null, "", `${cleanUrl.pathname}${cleanUrl.search}${cleanUrl.hash}`);
    uploadSuccess.querySelector("[data-dismiss-success]")?.addEventListener("click", () => uploadSuccess.remove());
  }

  function applyView(view) {
    const current = viewInfo[view] ? view : "mine";
    document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === current));
    document.querySelectorAll(".view-panel").forEach((panel) => panel.classList.toggle("active", panel.dataset.panel === current));
    document.getElementById("view-title").textContent = viewInfo[current][0];
    document.getElementById("view-description").textContent = viewInfo[current][1];
    history.replaceState(null, "", `?view=${current}`);
  }

  function showView(view, animate = true) {
    if (animate && document.startViewTransition && !reduceMotion.matches) {
      document.startViewTransition(() => applyView(view));
      return;
    }
    applyView(view);
  }

  function clearPerson() {
    recipient.value = "";
    selected.hidden = true;
    review.hidden = true;
    submit.disabled = true;
    shareError.hidden = true;
  }

  function selectPerson(user) {
    recipient.value = user.username;
    selected.innerHTML = `<span class="selected-avatar">${escapeHtml(user.username.slice(0, 1).toUpperCase())}</span><span><strong>${escapeHtml(user.username)}</strong><small>${escapeHtml(user.email || "Không có email")}</small></span><button type="button" aria-label="Bỏ chọn người nhận">×</button>`;
    selected.hidden = false;
    reviewCopy.textContent = `Chia sẻ “${activeDocument.name}” với ${user.username} với quyền tải xuống.`;
    review.hidden = false;
    submit.disabled = false;
    results.hidden = true;
    search.setAttribute("aria-expanded", "false");
    search.removeAttribute("aria-activedescendant");
    selected.querySelector("button").addEventListener("click", () => {
      clearPerson();
      search.focus();
    });
  }

  async function searchUsers(query) {
    searchController?.abort();
    searchController = new AbortController();
    try {
      const response = await fetch(`${config.searchUrl}?q=${encodeURIComponent(query)}`, { signal: searchController.signal });
      if (!response.ok) throw new Error();
      const data = await response.json();
      results.innerHTML = "";
      const users = Array.isArray(data.users) ? data.users : [];
      if (!users.length) {
        results.innerHTML = '<div class="search-status">Không tìm thấy người phù hợp. Hãy kiểm tra tên hoặc email.</div>';
        return;
      }
      users.forEach((user) => {
        const option = document.createElement("button");
        option.type = "button";
        option.className = "person-result";
        option.id = `person-option-${user.id}`;
        option.setAttribute("role", "option");
        option.setAttribute("aria-selected", "false");
        option.innerHTML = `<span class="selected-avatar">${escapeHtml(user.username.slice(0, 1).toUpperCase())}</span><span><strong>${escapeHtml(user.username)}</strong><small>${escapeHtml(user.email || "Không có email")}</small></span>`;
        option.addEventListener("click", () => selectPerson(user));
        results.appendChild(option);
      });
      activeIndex = -1;
    } catch (error) {
      if (error.name !== "AbortError") results.innerHTML = '<div class="search-status">Không thể tìm kiếm lúc này. Hãy kiểm tra kết nối và thử lại.</div>';
    }
  }

  async function loadAccess() {
    accessList.innerHTML = '<p class="search-status">Đang tải quyền truy cập…</p>';
    try {
      const response = await fetch(`/api/v1/documents/${activeDocument.id}/shares`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Không thể tải quyền truy cập");
      const users = Array.isArray(data.data) ? data.data : [];
      shareCount.textContent = `${users.length} người`;
      accessList.innerHTML = users.length ? "" : '<p class="access-empty">Chưa chia sẻ với ai.</p>';
      users.forEach((user) => {
        const row = document.createElement("div");
        row.className = "access-person";
        row.innerHTML = `<span><strong>${escapeHtml(user.username)}</strong><small>${escapeHtml(user.email || "Không có email")}</small></span><button type="button">Thu hồi</button>`;
        row.querySelector("button").addEventListener("click", async () => {
          if (!confirm(`Thu hồi quyền tải xuống của ${user.username} đối với “${activeDocument.name}”?`)) return;
          const response = await fetch(`/api/v1/documents/${activeDocument.id}/shares/${user.id}`, { method: "DELETE" });
          if (!response.ok) return alert("Không thể thu hồi quyền. Vui lòng thử lại.");
          loadAccess();
        });
        accessList.appendChild(row);
      });
    } catch (error) {
      accessList.innerHTML = `<p class="access-error">${escapeHtml(error.message)}. <button type="button">Thử lại</button></p>`;
      accessList.querySelector("button").addEventListener("click", loadAccess);
    }
  }

  function openDialog(button) {
    dialogTrigger = button;
    activeDocument = { id: button.dataset.shareDocument, name: button.dataset.shareFilename };
    form.action = `/share/${activeDocument.id}`;
    filename.textContent = activeDocument.name;
    search.value = "";
    clearPerson();
    results.hidden = true;
    dialog.showModal();
    if (dialog.animate && !reduceMotion.matches) {
      const source = button.getBoundingClientRect();
      const target = dialog.getBoundingClientRect();
      const sourceX = source.left + source.width / 2;
      const sourceY = source.top + source.height / 2;
      const targetX = target.left + target.width / 2;
      const targetY = target.top + target.height / 2;
      dialog.animate([
        {
          clipPath: "inset(42% 18% 42% 18% round 12px)",
          transform: `translate(${sourceX - targetX}px, ${sourceY - targetY}px) scale(.72)`,
          filter: "blur(5px)",
          opacity: .28
        },
        { clipPath: "inset(0 round 16px)", transform: "translate(0) scale(1)", filter: "blur(0)", opacity: 1 }
      ], { duration: 420, easing: "cubic-bezier(.16, 1, .3, 1)" });
    }
    loadAccess();
    search.focus();
  }

  function closeDialog() {
    searchController?.abort();
    if (!dialog.animate || reduceMotion.matches) return dialog.close();
    const animation = dialog.animate([
      { clipPath: "inset(0 round 16px)", opacity: 1 },
      { clipPath: "inset(46% 18% 46% 18% round 12px)", opacity: 0 }
    ], { duration: 180, easing: "cubic-bezier(.4, 0, 1, 1)" });
    animation.addEventListener("finish", () => dialog.close(), { once: true });
  }

  document.querySelectorAll(".nav-item").forEach((item) => item.addEventListener("click", () => showView(item.dataset.view)));
  document.querySelectorAll("[data-trigger-upload]").forEach((button) => button.addEventListener("click", () => uploadInput.click()));
  document.querySelectorAll("[data-go-view]").forEach((button) => button.addEventListener("click", () => showView(button.dataset.goView)));
  document.querySelectorAll("[data-share-document]").forEach((button) => button.addEventListener("click", () => openDialog(button)));
  document.querySelectorAll("[data-close-share]").forEach((button) => button.addEventListener("click", closeDialog));
  dialog.addEventListener("click", (event) => { if (event.target === dialog) closeDialog(); });
  dialog.addEventListener("close", () => {
    clearPerson();
    dialogTrigger?.focus();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!recipient.value || submit.disabled) return;
    submit.disabled = true;
    submit.textContent = "Đang chia sẻ…";
    shareError.hidden = true;
    try {
      const response = await fetch(`/api/v1/documents/${activeDocument.id}/shares`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ recipient: recipient.value })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Không thể chia sẻ tài liệu");
      const sharedWith = recipient.value;
      clearPerson();
      search.value = "";
      shareError.textContent = `Đã chia sẻ “${activeDocument.name}” với ${sharedWith}.`;
      shareError.classList.add("success");
      shareError.hidden = false;
      dialog.classList.remove("is-confirmed");
      requestAnimationFrame(() => dialog.classList.add("is-confirmed"));
      window.setTimeout(() => dialog.classList.remove("is-confirmed"), 700);
      await loadAccess();
    } catch (error) {
      shareError.classList.remove("success");
      shareError.textContent = `${error.message}. Kiểm tra người nhận và thử lại.`;
      shareError.hidden = false;
      submit.disabled = false;
    } finally {
      submit.textContent = "Chia sẻ tài liệu";
    }
  });

  search.addEventListener("input", () => {
    clearTimeout(searchTimer);
    const query = search.value.trim();
    clearPerson();
    if (query.length < 2) {
      searchController?.abort();
      results.hidden = true;
      search.setAttribute("aria-expanded", "false");
      return;
    }
    results.innerHTML = '<div class="search-status">Đang tìm…</div>';
    results.hidden = false;
    search.setAttribute("aria-expanded", "true");
    searchTimer = setTimeout(() => searchUsers(query), 250);
  });

  search.addEventListener("keydown", (event) => {
    const options = [...results.querySelectorAll('[role="option"]')];
    if ((event.key === "ArrowDown" || event.key === "ArrowUp") && options.length) {
      event.preventDefault();
      activeIndex = event.key === "ArrowDown" ? (activeIndex + 1) % options.length : (activeIndex - 1 + options.length) % options.length;
      options.forEach((option, index) => option.setAttribute("aria-selected", index === activeIndex ? "true" : "false"));
      search.setAttribute("aria-activedescendant", options[activeIndex].id);
      options[activeIndex].scrollIntoView({ block: "nearest" });
    } else if (event.key === "Enter" && activeIndex >= 0 && options[activeIndex]) {
      event.preventDefault();
      options[activeIndex].click();
    } else if (event.key === "Escape") {
      results.hidden = true;
      search.setAttribute("aria-expanded", "false");
      search.removeAttribute("aria-activedescendant");
    }
  });

  showView(config.activeView, false);
})();
