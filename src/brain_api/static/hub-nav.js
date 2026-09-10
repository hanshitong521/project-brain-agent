/** Stack hub nav — served by Brain API (no :18888 dependency). */
(function () {
  const STYLE =
    "position:fixed;top:0;left:0;right:0;z-index:9999;display:flex;align-items:center;gap:12px;" +
    "padding:8px 16px;font:13px/1.4 'Segoe UI','PingFang SC',sans-serif;" +
    "background:rgba(7,11,18,.92);border-bottom:1px solid rgba(148,163,184,.2);backdrop-filter:blur(8px);";
  const LINK =
    "color:#94a3b8;text-decoration:none;padding:4px 10px;border-radius:8px;border:1px solid transparent;";
  const ACTIVE = "color:#60a5fa;background:rgba(96,165,250,.12);border-color:rgba(96,165,250,.35);";

  function mount(nav) {
    if (document.getElementById("brain-hub-nav")) return;
    const path = location.pathname.replace(/\/$/, "") || "/";
    const bar = document.createElement("nav");
    bar.id = "brain-hub-nav";
    bar.setAttribute("aria-label", "控制台导航");
    bar.style.cssText = STYLE;
    const items = [
      { href: nav.home || "/", label: "导航首页" },
      { href: nav.dashboard || "/dashboard", label: "记忆看板" },
      { href: nav.lessons || "/lessons", label: "教训库" },
      { href: nav.mcp_lab || "/mcp-lab", label: "MCP 实验室" },
    ];
    if (nav.contextmind_dashboard) {
      items.push({ href: nav.contextmind_dashboard, label: "CTX 看板", external: true });
    }
    if (nav.contextmind_prompt_lab) {
      items.push({ href: nav.contextmind_prompt_lab, label: "Prompt Lab", external: true });
    }
    items.forEach((it) => {
      const a = document.createElement("a");
      a.href = it.href;
      a.textContent = it.label;
      a.style.cssText = LINK;
      if (it.external) a.target = "_blank";
      const norm = (it.href || "").replace(/^https?:\/\/[^/]+/, "");
      if (!it.external && (path === norm || (norm !== "/" && path.startsWith(norm)))) {
        a.style.cssText = LINK + ACTIVE;
      }
      bar.appendChild(a);
    });
    const brand = document.createElement("span");
    brand.textContent = "Project Brain";
    brand.style.cssText = "color:#f1f5f9;font-weight:600;margin-right:8px;";
    bar.insertBefore(brand, bar.firstChild);
    document.body.prepend(bar);
    const h = bar.getBoundingClientRect().height;
    document.body.style.paddingTop = `${Math.ceil(h + 4)}px`;
  }

  function run() {
    fetch("/api/nav")
      .then((r) => (r.ok ? r.json() : {}))
      .then(mount)
      .catch(() =>
        mount({
          home: "/",
          dashboard: "/dashboard",
          lessons: "/lessons",
          mcp_lab: "/mcp-lab",
        }),
      );
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run);
  else run();
})();
