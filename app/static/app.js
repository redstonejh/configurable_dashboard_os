function showGlobalToast(message, tone = "success") {
  const stack = document.querySelector(".toast-stack");
  if (!stack) {
    console.warn(message);
    return;
  }
  const toast = document.createElement("div");
  toast.className = `toast toast-${tone}`;
  toast.textContent = message;
  stack.appendChild(toast);
  window.setTimeout(() => toast.classList.add("show"), 20);
  window.setTimeout(() => {
    toast.classList.remove("show");
    window.setTimeout(() => toast.remove(), 180);
  }, 3200);
}

async function postAction(url, button) {
  const oldText = button.textContent;
  button.disabled = true;
  button.textContent = "Working...";
  try {
    const response = await fetch(url, { method: "POST" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Request failed");
    showGlobalToast(payload.message + (payload.detail ? " " + JSON.stringify(payload.detail) : ""));
    if (url.includes("run-parser")) window.location.reload();
  } catch (error) {
    showGlobalToast(error.message, "warn");
  } finally {
    button.disabled = false;
    button.textContent = oldText;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const panelStoragePrefix = "dashboard-panel-layout:v2:";
  const panelThemes = {
    azure: { accent: "#60a5fa", header: "#19375d", surface: "#101a2c", border: "#75b9ff", glow: "rgba(103,169,255,.16)" },
    cyan: { accent: "#22d3ee", header: "#123947", surface: "#0c2028", border: "#67e8f9", glow: "rgba(34,211,238,.15)" },
    emerald: { accent: "#34d399", header: "#143526", surface: "#0f1f1c", border: "#86efac", glow: "rgba(52,211,153,.14)" },
    lime: { accent: "#a3e635", header: "#263811", surface: "#18210d", border: "#d9f99d", glow: "rgba(163,230,53,.14)" },
    rose: { accent: "#fb7185", header: "#3b1821", surface: "#24121a", border: "#ff8d99", glow: "rgba(251,113,133,.15)" },
    pink: { accent: "#f472b6", header: "#421833", surface: "#261322", border: "#f9a8d4", glow: "rgba(244,114,182,.15)" },
    amber: { accent: "#fbbf24", header: "#3a2a10", surface: "#21190d", border: "#fde68a", glow: "rgba(251,191,36,.14)" },
    orange: { accent: "#fb923c", header: "#3d2512", surface: "#24160d", border: "#fed7aa", glow: "rgba(251,146,60,.14)" },
    violet: { accent: "#a78bfa", header: "#261a45", surface: "#171225", border: "#c4b5fd", glow: "rgba(167,139,250,.15)" },
    indigo: { accent: "#818cf8", header: "#1f2a5a", surface: "#11162e", border: "#a5b4fc", glow: "rgba(129,140,248,.15)" },
  };
  const textThemes = {
    frost: "#f8fbff",
    black: "#020617",
    sky: "#bfdbfe",
    cyan: "#a5f3fc",
    mint: "#bbf7d0",
    lime: "#d9f99d",
    rose: "#fecdd3",
    pink: "#fbcfe8",
    amber: "#fde68a",
    orange: "#fed7aa",
    violet: "#ddd6fe",
  };

  const confirmAction = ({ title = "Confirm action", message = "Continue?", confirmLabel = "Continue", cancelLabel = "Cancel" } = {}) => (
    new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.className = "modal-backdrop";
      overlay.innerHTML = `
        <section class="app-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-modal-title">
          <div class="app-modal-copy">
            <h2 id="confirm-modal-title"></h2>
            <p></p>
          </div>
          <div class="app-modal-actions">
            <button class="cmd-btn cmd-btn-ghost modal-cancel" type="button"></button>
            <button class="cmd-btn cmd-btn-danger modal-confirm" type="button"></button>
          </div>
        </section>
      `;
      overlay.querySelector("h2").textContent = title;
      overlay.querySelector("p").textContent = message;
      overlay.querySelector(".modal-cancel").textContent = cancelLabel;
      overlay.querySelector(".modal-confirm").textContent = confirmLabel;
      document.body.appendChild(overlay);
      const cancel = overlay.querySelector(".modal-cancel");
      const confirm = overlay.querySelector(".modal-confirm");
      const close = (value) => {
        overlay.classList.remove("modal-open");
        window.setTimeout(() => overlay.remove(), 160);
        resolve(value);
      };
      window.requestAnimationFrame(() => overlay.classList.add("modal-open"));
      cancel.focus();
      cancel.addEventListener("click", () => close(false));
      confirm.addEventListener("click", () => close(true));
      overlay.addEventListener("click", (event) => {
        if (event.target === overlay) close(false);
      });
      overlay.addEventListener("keydown", (event) => {
        if (event.key === "Escape") close(false);
      });
    })
  );

  const defaultThemeForPanel = (panel) => {
    if (panel.dataset.panelTheme && panel.dataset.panelTheme !== "default") return panel.dataset.panelTheme;
    if (panel.querySelector(".db-panel-hd-analytics")) return "emerald";
    if (panel.querySelector(".db-panel-hd-notifications")) return "rose";
    return "azure";
  };
  const panelKey = (panel) => {
    const layout = panel.closest(".panel-layout");
    return `${panelStoragePrefix}${layout?.dataset.layoutKey || "default"}:${panel.dataset.panelKey || "panel"}`;
  };
  const readPanelState = (panel) => {
    try {
      return JSON.parse(localStorage.getItem(panelKey(panel)) || "null") || {};
    } catch {
      return {};
    }
  };
  const writePanelState = (panel, patch = {}) => {
    try {
      const current = readPanelState(panel);
      const title = panel.querySelector(".db-panel-title")?.textContent?.trim() || "";
      localStorage.setItem(panelKey(panel), JSON.stringify({
        ...current,
        title,
        theme: panel.dataset.panelTheme || defaultThemeForPanel(panel),
        text: panel.dataset.panelText || "frost",
        collapsed: panel.classList.contains("db-panel-collapsed"),
        pinned: panel.classList.contains("panel-pinned"),
        deleted: panel.classList.contains("panel-deleted"),
        ...patch,
      }));
    } catch {}
  };
  const applyPanelTheme = (panel, themeKey = defaultThemeForPanel(panel), textKey = "frost") => {
    const safeTheme = panelThemes[themeKey] ? themeKey : defaultThemeForPanel(panel);
    const safeText = textThemes[textKey] ? textKey : "frost";
    const theme = panelThemes[safeTheme];
    panel.dataset.panelTheme = safeTheme;
    panel.dataset.panelText = safeText;
    panel.classList.add("panel-custom-theme");
    panel.style.setProperty("--panel-accent", theme.accent);
    panel.style.setProperty("--panel-header", theme.header);
    panel.style.setProperty("--panel-surface", theme.surface);
    panel.style.setProperty("--panel-border", theme.border);
    panel.style.setProperty("--panel-glow", theme.glow);
    panel.style.setProperty("--panel-text-custom", textThemes[safeText]);
  };
  const refreshPanelMotionMetrics = (panel) => {
    const body = panel?.querySelector?.(".db-panel-body");
    if (!body) return;
    panel.style.setProperty("--panel-body-max", `${Math.max(120, body.scrollHeight + 32)}px`);
  };
  const refreshAllPanelMotionMetrics = () => {
    document.querySelectorAll(".panel-layout > .db-panel").forEach(refreshPanelMotionMetrics);
  };
  const layoutMotionItems = (layout) => {
    if (!layout) return [];
    return [...layout.children].filter((item) => (
      item.classList.contains("db-panel-placeholder")
      || (
        item.classList.contains("db-panel")
        && !item.classList.contains("db-panel-dragging")
        && !item.classList.contains("panel-deleted")
      )
    ));
  };
  const animateLayoutShift = (layout, mutate) => {
    if (!layout) {
      mutate();
      return;
    }
    const items = layoutMotionItems(layout);
    const first = new Map(items.map((item) => [item, item.getBoundingClientRect()]));
    mutate();
    const nextItems = layoutMotionItems(layout);
    nextItems.forEach((item) => {
      const start = first.get(item);
      if (!start) return;
      const end = item.getBoundingClientRect();
      const dx = start.left - end.left;
      const dy = start.top - end.top;
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
      item.style.transition = "none";
      item.style.transform = `translate3d(${dx}px, ${dy}px, 0)`;
      item.getBoundingClientRect();
      requestAnimationFrame(() => {
        item.style.transition = "transform .30s cubic-bezier(.22, 1, .36, 1)";
        item.style.transform = "";
      });
      window.setTimeout(() => {
        item.style.transition = "";
        item.style.transform = "";
      }, 340);
    });
  };

  const applyThemeMode = (theme) => {
    const dark = theme === "dark";
    document.documentElement.dataset.theme = dark ? "dark" : "";
    if (!dark) delete document.documentElement.dataset.theme;
    document.querySelectorAll(".theme-toggle").forEach((button) => {
      button.classList.toggle("is-dark", dark);
      button.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
      button.title = dark ? "Switch to light mode" : "Switch to dark mode";
      button.setAttribute("aria-pressed", dark.toString());
    });
  };
  try {
    const requestedTheme = new URLSearchParams(window.location.search).get("theme");
    applyThemeMode(requestedTheme || localStorage.getItem("dashboard-theme") || "");
  } catch {
    applyThemeMode("");
  }
  document.querySelectorAll(".theme-toggle").forEach((button) => {
    button.addEventListener("click", () => {
      const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      try {
        if (nextTheme === "dark") localStorage.setItem("dashboard-theme", "dark");
        else localStorage.removeItem("dashboard-theme");
      } catch {}
      applyThemeMode(nextTheme);
    });
  });

  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", () => postAction(button.dataset.action, button));
  });

  document.querySelectorAll(".range-custom").forEach((form) => {
    const startInput = form.querySelector('input[name="start"]');
    const endInput = form.querySelector('input[name="end"]');
    const trigger = form.querySelector(".range-custom-trigger");
    const openPicker = (input) => {
      if (!input) return;
      if (typeof input.showPicker === "function") input.showPicker();
      else {
        input.focus();
        input.click();
      }
    };
    trigger?.addEventListener("click", () => openPicker(startInput));
    startInput?.addEventListener("change", () => window.setTimeout(() => openPicker(endInput), 120));
    endInput?.addEventListener("change", () => {
      if (startInput?.value && endInput?.value) form.requestSubmit();
    });
  });

  const switcherToggle = document.getElementById("dash-switcher-toggle");
  const switcherMenu = document.getElementById("dash-switch-menu");
  if (switcherToggle && switcherMenu) {
    const switcher = switcherToggle.closest(".dash-switcher");
    let closeTimer;
    const openSwitcher = () => {
      window.clearTimeout(closeTimer);
      switcherMenu.classList.add("open");
      switcherToggle.setAttribute("aria-expanded", "true");
    };
    const closeSwitcher = () => {
      switcherMenu.classList.remove("open");
      switcherToggle.setAttribute("aria-expanded", "false");
    };
    const scheduleClose = () => {
      window.clearTimeout(closeTimer);
      closeTimer = window.setTimeout(closeSwitcher, 140);
    };
    switcher?.addEventListener("mouseenter", openSwitcher);
    switcher?.addEventListener("mouseleave", scheduleClose);
    switcherToggle.addEventListener("focus", openSwitcher);
    switcherToggle.addEventListener("click", (event) => {
      event.stopPropagation();
      const open = switcherMenu.classList.toggle("open");
      switcherToggle.setAttribute("aria-expanded", open.toString());
    });
    switcherMenu.addEventListener("mouseenter", openSwitcher);
    switcherMenu.addEventListener("mouseleave", scheduleClose);
    switcherMenu.addEventListener("click", (event) => event.stopPropagation());
    document.addEventListener("click", closeSwitcher);
  }

  document.querySelectorAll(".panel-layout > .db-panel").forEach((panel, index) => {
    panel.dataset.defaultOrder = String(index);
    const state = readPanelState(panel);
    panel.style.order = String(state.order ?? index);
    if (state.gridColumn) panel.style.gridColumn = state.gridColumn;
    else if (state.span || panel.dataset.defaultSpan) panel.style.gridColumn = `span ${Number(state.span || panel.dataset.defaultSpan || 4)}`;
    panel.dataset.currentSpan = String(state.span || panel.dataset.defaultSpan || 4);
    if (state.height) {
      panel.dataset.expandedHeight = `${Math.max(96, Number(state.height))}px`;
      if (!state.collapsed) panel.style.height = panel.dataset.expandedHeight;
    }
    if (state.deleted) panel.classList.add("panel-deleted");
    if (state.collapsed) panel.classList.add("db-panel-collapsed");
    if (state.pinned) panel.classList.add("panel-pinned");
    if (state.title && panel.querySelector(".db-panel-title")) {
      panel.querySelector(".db-panel-title").textContent = state.title;
    }
    applyPanelTheme(panel, state.theme || defaultThemeForPanel(panel), state.text || "frost");
    refreshPanelMotionMetrics(panel);
    const header = panel.querySelector(".db-panel-hd");
    if (header) {
      header.setAttribute("role", "button");
      header.setAttribute("tabindex", "0");
      header.setAttribute("aria-expanded", (!panel.classList.contains("db-panel-collapsed")).toString());
      const togglePanel = () => {
        const layout = panel.closest(".panel-layout");
        animateLayoutShift(layout, () => {
          const collapsed = panel.classList.toggle("db-panel-collapsed");
          if (collapsed) {
            if (panel.style.height) panel.dataset.expandedHeight = panel.style.height;
            panel.style.height = "";
          } else if (panel.dataset.expandedHeight) {
            panel.style.height = panel.dataset.expandedHeight;
          }
          header.setAttribute("aria-expanded", (!collapsed).toString());
          refreshPanelMotionMetrics(panel);
          writePanelState(panel, { collapsed });
        });
      };
      header.addEventListener("click", (event) => {
        if (event.target.closest("button, input, .panel-menu, .panel-customizer")) return;
        togglePanel();
      });
      header.addEventListener("keydown", (event) => {
        if (event.target.closest("button, input, .panel-menu, .panel-customizer")) return;
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        togglePanel();
      });
    }
  });
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      document.documentElement.classList.remove("layout-hydrating");
    });
  });
  window.addEventListener("resize", () => {
    window.requestAnimationFrame(refreshAllPanelMotionMetrics);
  });

  const savePanelOrder = (layout) => {
    [...layout.querySelectorAll(":scope > .db-panel:not(.panel-deleted)")].forEach((panel, index) => {
      panel.style.order = String(index);
      writePanelState(panel, {
        order: index,
        span: Number(panel.dataset.currentSpan || panel.dataset.defaultSpan || 4),
        gridColumn: panel.style.gridColumn || "",
        height: panel.style.height ? parseFloat(panel.style.height) : null,
      });
    });
  };

  const startPanelMove = (panel, event) => {
    if (panel.classList.contains("panel-pinned")) {
      showGlobalToast("Pinned panels are locked.", "warn");
      return;
    }
    const layout = panel.closest(".panel-layout");
    if (!layout) return;
    event.preventDefault();
    event.stopPropagation();
    const handle = event.currentTarget || event.target;
    handle.setPointerCapture?.(event.pointerId);
    const rect = panel.getBoundingClientRect();
    const offsetX = event.clientX - rect.left;
    const offsetY = event.clientY - rect.top;
    const placeholder = document.createElement("div");
    placeholder.className = "db-panel-placeholder";
    placeholder.style.gridColumn = panel.style.gridColumn || `span ${panel.dataset.currentSpan || panel.dataset.defaultSpan || 4}`;
    placeholder.style.height = `${Math.max(80, rect.height)}px`;
    layout.insertBefore(placeholder, panel);
    document.body.classList.add("panel-interacting");
    panel.classList.add("db-panel-dragging");
    panel.style.width = `${rect.width}px`;
    panel.style.height = `${rect.height}px`;
    panel.style.left = `${rect.left}px`;
    panel.style.top = `${rect.top}px`;
    panel.style.transform = "translate3d(0, 0, 0)";

    let active = true;
    let frame = 0;
    let latestPointer = event;
    const updateMove = () => {
      frame = 0;
      if (!active) return;
      const moveEvent = latestPointer;
      if (moveEvent.pointerType === "mouse" && moveEvent.buttons === 0) {
        end(moveEvent);
        return;
      }
      const maxLeft = Math.max(8, window.innerWidth - 48);
      const maxTop = Math.max(8, window.innerHeight - 48);
      const nextLeft = Math.max(8, Math.min(maxLeft, moveEvent.clientX - offsetX));
      const nextTop = Math.max(8, Math.min(maxTop, moveEvent.clientY - offsetY));
      panel.style.transform = `translate3d(${nextLeft - rect.left}px, ${nextTop - rect.top}px, 0)`;
      const hitX = Math.max(0, Math.min(window.innerWidth - 1, moveEvent.clientX));
      const hitY = Math.max(0, Math.min(window.innerHeight - 1, moveEvent.clientY));
      panel.style.pointerEvents = "none";
      const target = document.elementFromPoint(hitX, hitY)?.closest?.(".db-panel");
      panel.style.pointerEvents = "";
      if (!target || target === panel || target.parentElement !== layout || target.classList.contains("panel-pinned")) return;
      const targetRect = target.getBoundingClientRect();
      const before = moveEvent.clientY < targetRect.top + targetRect.height / 2;
      const reference = before ? target : target.nextSibling;
      if (reference === placeholder || placeholder.nextSibling === reference) return;
      animateLayoutShift(layout, () => {
        layout.insertBefore(placeholder, reference);
      });
    };
    const move = (moveEvent) => {
      latestPointer = moveEvent;
      if (!frame) frame = requestAnimationFrame(updateMove);
    };
    const end = () => {
      active = false;
      if (frame) cancelAnimationFrame(frame);
      panel.classList.remove("db-panel-dragging");
      document.body.classList.remove("panel-interacting");
      panel.style.left = "";
      panel.style.top = "";
      panel.style.width = "";
      panel.style.height = "";
      panel.style.transform = "";
      panel.style.pointerEvents = "";
      animateLayoutShift(layout, () => {
        layout.insertBefore(panel, placeholder);
        placeholder.remove();
      });
      refreshPanelMotionMetrics(panel);
      savePanelOrder(layout);
      handle.releasePointerCapture?.(event.pointerId);
      document.removeEventListener("pointermove", move, true);
      document.removeEventListener("pointerup", end, true);
      document.removeEventListener("pointercancel", end, true);
    };
    document.addEventListener("pointermove", move, true);
    document.addEventListener("pointerup", end, true);
    document.addEventListener("pointercancel", end, true);
  };

  const startPanelResize = (panel, event) => {
    if (panel.classList.contains("panel-pinned")) {
      showGlobalToast("Pinned panels are locked.", "warn");
      return;
    }
    const layout = panel.closest(".panel-layout");
    if (!layout) return;
    event.preventDefault();
    event.stopPropagation();
    const rect = panel.getBoundingClientRect();
    const layoutRect = layout.getBoundingClientRect();
    const startX = event.clientX;
    const startY = event.clientY;
    const startSpan = Number(panel.dataset.currentSpan || panel.dataset.defaultSpan || 4);
    const col = Math.max(1, layoutRect.width / 12);
    const minSpan = panel.closest(".top-panel-layout") ? 2 : 3;
    const handle = event.currentTarget || event.target;
    handle.setPointerCapture?.(event.pointerId);
    document.body.classList.add("panel-interacting");
    panel.classList.add("db-panel-resizing");
    let frame = 0;
    let latestPointer = event;
    const updateResize = () => {
      frame = 0;
      const moveEvent = latestPointer;
      const nextSpan = Math.max(minSpan, Math.min(12, Math.round(startSpan + (moveEvent.clientX - startX) / col)));
      const nextHeight = Math.max(120, Math.round(rect.height + (moveEvent.clientY - startY)));
      panel.style.gridColumn = `span ${nextSpan}`;
      panel.dataset.currentSpan = String(nextSpan);
      panel.style.height = `${nextHeight}px`;
      refreshPanelMotionMetrics(panel);
    };
    const move = (moveEvent) => {
      latestPointer = moveEvent;
      if (!frame) frame = requestAnimationFrame(updateResize);
    };
    const end = () => {
      if (frame) cancelAnimationFrame(frame);
      panel.classList.remove("db-panel-resizing");
      document.body.classList.remove("panel-interacting");
      if (panel.style.height) panel.dataset.expandedHeight = panel.style.height;
      refreshPanelMotionMetrics(panel);
      writePanelState(panel, {
        span: Number(panel.dataset.currentSpan || panel.dataset.defaultSpan || 4),
        height: panel.style.height ? parseFloat(panel.style.height) : null,
        gridColumn: panel.style.gridColumn || "",
      });
      handle.releasePointerCapture?.(event.pointerId);
      document.removeEventListener("pointermove", move, true);
      document.removeEventListener("pointerup", end, true);
      document.removeEventListener("pointercancel", end, true);
    };
    document.addEventListener("pointermove", move, true);
    document.addEventListener("pointerup", end, true);
    document.addEventListener("pointercancel", end, true);
  };

  document.addEventListener("pointerdown", (event) => {
    const moveButton = event.target.closest('[data-panel-action="move"]');
    const resizeButton = event.target.closest('[data-panel-action="resize"]');
    if (!moveButton && !resizeButton) return;
    const customizer = event.target.closest(".panel-customizer");
    if (!customizer?.classList.contains("panel-menu-open")) return;
    const panel = event.target.closest(".db-panel");
    if (!panel) return;
    if (moveButton) startPanelMove(panel, event);
    if (resizeButton) startPanelResize(panel, event);
  }, true);

  const setPanelCustomizerOpen = (customizer, open) => {
    if (!customizer) return;
    customizer.classList.toggle("panel-menu-open", open);
    if (!open) customizer.classList.remove("panel-palette-open");
    customizer.querySelector(".panel-gear")?.setAttribute("aria-expanded", open.toString());
  };
  const closePanelCustomizer = (customizer) => setPanelCustomizerOpen(customizer, false);
  const closeOtherPanelCustomizers = (activeCustomizer = null) => {
    document.querySelectorAll(".panel-customizer.panel-menu-open").forEach((customizer) => {
      if (customizer !== activeCustomizer) closePanelCustomizer(customizer);
    });
  };

  document.addEventListener("click", async (event) => {
    const actionButton = event.target.closest("[data-panel-action]");
    if (actionButton) {
      const customizer = actionButton.closest(".panel-customizer");
      if (!customizer?.classList.contains("panel-menu-open")) return;
      const panel = actionButton.closest(".db-panel");
      if (!panel) return;
      event.preventDefault();
      event.stopPropagation();
      const action = actionButton.dataset.panelAction;
      if (action === "move" || action === "resize") return;
      if (action === "pin") {
        const pinned = !panel.classList.contains("panel-pinned");
        panel.classList.toggle("panel-pinned", pinned);
        actionButton.setAttribute("aria-pressed", pinned.toString());
        writePanelState(panel, { pinned });
      }
      if (action === "title") {
        const title = panel.querySelector(".db-panel-title");
        if (!title || panel.querySelector(".panel-title-input")) return;
        const input = document.createElement("input");
        input.className = "panel-title-input";
        input.value = title.textContent.trim();
        input.setAttribute("aria-label", "Panel title");
        title.replaceWith(input);
        input.focus();
        input.select();
        const finish = (save = true) => {
          const next = (save ? input.value.trim() : title.textContent.trim()) || "Panel";
          title.textContent = next;
          input.replaceWith(title);
          writePanelState(panel, { title: next });
        };
        input.addEventListener("keydown", (keyEvent) => {
          if (keyEvent.key === "Enter") finish(true);
          if (keyEvent.key === "Escape") finish(false);
        });
        input.addEventListener("blur", () => finish(true), { once: true });
      }
      if (action === "palette") {
        const customizer = panel.querySelector(".panel-customizer");
        const open = !customizer?.classList.contains("panel-palette-open");
        customizer?.classList.toggle("panel-palette-open", open);
        setPanelCustomizerOpen(customizer, open);
      }
      if (action === "delete") {
        const confirmed = await confirmAction({
          title: "Delete panel",
          message: "This removes the panel from the dashboard. Reset restores the default layout.",
          confirmLabel: "Delete panel",
        });
        if (confirmed) {
          panel.classList.add("panel-deleted");
          writePanelState(panel, { deleted: true });
        }
      }
      return;
    }

    const themeChoice = event.target.closest("[data-panel-theme-choice]");
    const textChoice = event.target.closest("[data-panel-text-choice]");
    if (themeChoice || textChoice) {
      const customizer = event.target.closest(".panel-customizer");
      if (!customizer?.classList.contains("panel-palette-open")) return;
      const panel = event.target.closest(".db-panel");
      if (!panel) return;
      event.preventDefault();
      event.stopPropagation();
      const nextTheme = themeChoice?.dataset.panelThemeChoice || panel.dataset.panelTheme || defaultThemeForPanel(panel);
      const nextText = textChoice?.dataset.panelTextChoice || panel.dataset.panelText || "frost";
      applyPanelTheme(panel, nextTheme, nextText);
      writePanelState(panel, { theme: nextTheme, text: nextText });
    }
  });

  document.querySelectorAll(".panel-customizer").forEach((customizer) => {
    const gear = customizer.querySelector(".panel-gear");
    const menu = customizer.querySelector(".panel-menu");
    let closeTimer;
    const closeSoon = (delay = 160) => {
      window.clearTimeout(closeTimer);
      closeTimer = window.setTimeout(() => closePanelCustomizer(customizer), delay);
    };
    gear?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const open = !customizer.classList.contains("panel-menu-open");
      closeOtherPanelCustomizers(customizer);
      setPanelCustomizerOpen(customizer, open);
    });
    customizer.addEventListener("mouseenter", () => window.clearTimeout(closeTimer));
    customizer.addEventListener("mouseleave", () => closeSoon());
    menu?.addEventListener("mouseenter", () => window.clearTimeout(closeTimer));
    menu?.addEventListener("mouseleave", () => closeSoon());
  });

  try {
    if (new URLSearchParams(window.location.search).get("visual_modal") === "1") {
      window.setTimeout(() => {
        confirmAction({
          title: "Delete panel",
          message: "This removes the panel from the dashboard. Reset restores the default layout.",
          confirmLabel: "Delete panel",
        });
      }, 250);
    }
  } catch {}

  document.addEventListener("click", (event) => {
    const activeCustomizer = event.target.closest(".panel-customizer");
    closeOtherPanelCustomizers(activeCustomizer);
  });

  document.querySelectorAll(".panel-reset-button").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      try {
        Object.keys(localStorage)
          .filter((key) => key.startsWith("dashboard-panel-layout:"))
          .forEach((key) => localStorage.removeItem(key));
      } catch {}
      showGlobalToast("Default layout restored.");
      window.setTimeout(() => {
        window.location.href = button.getAttribute("href") || "/dashboard?reset_layout=1";
      }, 80);
    });
  });

  const form = document.getElementById("settings-form");
  const dashboardBtn = document.getElementById("settings-dashboard-btn");
  const saveButton = document.getElementById("settings-save-btn");
  const dirtyNote = document.getElementById("settings-dirty-note");

  document.querySelectorAll(".secret-toggle").forEach((button) => {
    button.addEventListener("click", () => {
      const input = button.closest(".secret-control")?.querySelector("[data-secret]");
      if (!input) return;
      const revealing = input.type === "password";
      input.type = revealing ? "text" : "password";
      button.textContent = revealing ? "Hide" : "Show";
      button.classList.toggle("revealed", revealing);
    });
  });
  document.querySelectorAll(".secret-copy").forEach((button) => {
    button.addEventListener("click", async () => {
      const value = button.closest(".secret-control")?.querySelector("[data-secret]")?.value || "";
      if (!value) {
        showGlobalToast("Enter a value before copying.", "warn");
        return;
      }
      try {
        await navigator.clipboard.writeText(value);
        showGlobalToast("Copied to clipboard.");
      } catch {
        showGlobalToast("Clipboard copy was blocked by the browser.", "warn");
      }
    });
  });

  const validators = {
    guid: (value) => !value || /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value),
    email: (value) => !value || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
    url: (value) => !value || /^https?:\/\/.+/i.test(value),
  };
  const validationMessages = {
    guid: "Use a valid identifier.",
    email: "Use a valid email address.",
    url: "Use a valid URL.",
  };
  const validateField = (input) => {
    const type = input.dataset.validate;
    if (!type || !validators[type]) return true;
    const valid = validators[type](input.value.trim());
    const error = input.closest("label")?.querySelector(".field-error");
    input.classList.toggle("input-invalid", !valid);
    input.setCustomValidity(valid ? "" : validationMessages[type]);
    if (error) error.textContent = valid ? "" : validationMessages[type];
    return valid;
  };
  document.querySelectorAll("[data-validate]").forEach((input) => {
    input.addEventListener("input", () => validateField(input));
    input.addEventListener("blur", () => validateField(input));
  });

  const previewButton = document.getElementById("score-preview-btn");
  previewButton?.addEventListener("click", async () => {
    const result = document.getElementById("score-preview-result");
    result.textContent = "Calculating...";
    const payload = {
      title: document.getElementById("preview-title")?.value || "",
      source: document.getElementById("preview-source")?.value || "",
      category: document.getElementById("preview-category")?.value || "",
      status: document.getElementById("preview-status")?.value || "",
      resource: document.getElementById("preview-resource")?.value || "",
      config: {},
    };
    if (form) {
      [
        "default_score",
        "score_critical_threshold",
        "score_high_threshold",
        "score_medium_threshold",
        "repeat_window_hours",
        "repeat_1_adjustment",
        "repeat_2_adjustment",
        "repeat_3_adjustment",
        "source_volume_window_hours",
        "source_volume_threshold",
        "source_volume_adjustment",
        "notification_min_score",
        "score_rules",
      ].forEach((name) => {
        const input = form.elements.namedItem(name);
        if (input) payload.config[name] = input.type === "checkbox" ? input.checked : input.value;
      });
    }
    try {
      const response = await fetch("/api/rule-preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Preview failed");
      const reasons = data.reasons?.length ? data.reasons.join("; ") : "No context adjustments.";
      result.textContent = `${data.label} (${data.score}) - base ${data.base_score}, context ${data.context_adjustment}. ${reasons}`;
    } catch (error) {
      result.textContent = error.message;
    }
  });

  if (!form || !dashboardBtn) return;
  const serialize = (targetForm) => [...new FormData(targetForm).entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
    .join("&");
  const initialState = serialize(form);
  const isDirty = () => serialize(form) !== initialState;
  const updateDirtyState = () => {
    const dirty = isDirty();
    form.classList.toggle("is-dirty", dirty);
    if (dirtyNote) {
      dirtyNote.textContent = dirty
        ? "Unsaved changes pending. Save to rescore historical records."
        : "Background polling stays disabled until you enable it; rescoring runs after save.";
    }
  };
  form.addEventListener("input", updateDirtyState);
  form.addEventListener("change", updateDirtyState);
  window.addEventListener("beforeunload", (event) => {
    if (!isDirty() || form.dataset.submitting === "true") return;
    event.preventDefault();
    event.returnValue = "";
  });
  dashboardBtn.addEventListener("click", (event) => {
    if (!isDirty()) return;
    event.preventDefault();
    if (window.confirm("You have unsaved settings changes. OK to save and go back to Dashboard, or Cancel to discard changes and go back.")) {
      form.submit();
    } else {
      window.location.href = dashboardBtn.dataset.href || "/dashboard";
    }
  });
  form.addEventListener("submit", (event) => {
    let valid = true;
    form.querySelectorAll("[data-validate]").forEach((input) => {
      if (!validateField(input)) valid = false;
    });
    const critical = Number(form.elements.namedItem("score_critical_threshold")?.value || 0);
    const high = Number(form.elements.namedItem("score_high_threshold")?.value || 0);
    const medium = Number(form.elements.namedItem("score_medium_threshold")?.value || 0);
    if (critical && high && medium && !(critical > high && high > medium)) {
      valid = false;
      showGlobalToast("Severity thresholds must descend: Critical > High > Medium.", "warn");
    }
    if (!valid) {
      event.preventDefault();
      return;
    }
    form.dataset.submitting = "true";
    saveButton?.classList.add("is-saving");
    if (saveButton) saveButton.disabled = true;
  });
});
