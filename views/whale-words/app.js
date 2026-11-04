if (!window.AstrBotPluginView) {
  const request = async (method, endpoint, params, body) => {
    const url = new URL("/v1/" + endpoint, location.origin);
    for (const [key, value] of Object.entries(params || {})) {
      if (value !== undefined && value !== null) url.searchParams.set(key, value);
    }
    const response = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) throw new Error((await response.text()) || `HTTP ${response.status}`);
    return response.json();
  };
  window.AstrBotPluginView = {
    ready: async () => ({}),
    apiGet: (endpoint, params) => request("GET", endpoint, params),
    apiPost: (endpoint, body) => request("POST", endpoint, null, body || {}),
  };
}

const bridge = window.AstrBotPluginView;
const listEl = document.getElementById("list");
const emptyEl = document.getElementById("empty");
const adapterChip = document.getElementById("adapterChip");
const countChip = document.getElementById("countChip");
const listHint = document.getElementById("listHint");
const refreshBtn = document.getElementById("refresh");
const generateBtn = document.getElementById("generate");
const modal = document.getElementById("modal");
const modalTitle = document.getElementById("modalTitle");
const modalText = document.getElementById("modalText");
const modalOk = document.getElementById("modalOk");
const modalCancel = document.getElementById("modalCancel");
const toastEl = document.getElementById("toast");

let toastTimer = null;

function esc(text) {
  return String(text ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}

function toast(text, isError = false) {
  toastEl.textContent = text;
  toastEl.style.background = isError ? "linear-gradient(135deg,#ff6482,#ff8f9e)" : "";
  toastEl.style.color = "#fff";
  toastEl.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastEl.hidden = true; }, 3200);
}

function ask(title, text, okLabel = "确定", danger = true) {
  return new Promise((resolve) => {
    modalTitle.textContent = title;
    modalText.textContent = text;
    modalOk.textContent = okLabel;
    modalOk.className = danger ? "btn danger" : "btn primary";
    modal.hidden = false;
    const close = (value) => {
      modal.hidden = true;
      modalOk.removeEventListener("click", onOk);
      modalCancel.removeEventListener("click", onCancel);
      resolve(value);
    };
    const onOk = () => close(true);
    const onCancel = () => close(false);
    modalOk.addEventListener("click", onOk);
    modalCancel.addEventListener("click", onCancel);
  });
}

function button(label, cls, handler) {
  const el = document.createElement("button");
  el.type = "button";
  el.className = cls;
  el.textContent = label;
  el.addEventListener("click", handler);
  return el;
}

async function load() {
  try {
    const data = await bridge.apiGet("drafts");
    adapterChip.textContent = data.adapter === "qzone_native" ? "Cookie 直连" : data.adapter || "—";
    const drafts = data.drafts || [];
    countChip.textContent = `${drafts.length} 条草稿`;
    listHint.textContent = drafts.length ? `${drafts.length} 条等你过目` : "暂时空空的";
    render(drafts);
  } catch (error) {
    toast("加载失败：" + error.message, true);
  }
}

function render(drafts) {
  listEl.innerHTML = "";
  emptyEl.hidden = drafts.length > 0;
  for (const draft of drafts) {
    const card = document.createElement("article");
    card.className = "card";

    const tape = document.createElement("span");
    tape.className = "tape";
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = "草稿";

    const meta = document.createElement("div");
    meta.className = "meta";
    meta.innerHTML = `<span>${esc(draft.created_at || "")}</span><span>#${esc(draft.id)}</span>`;

    const text = document.createElement("div");
    text.className = "text";
    text.textContent = draft.text || "";

    card.append(tape, tag, meta, text);

    if (draft.issues && draft.issues.length) {
      const issues = document.createElement("div");
      issues.className = "issues";
      for (const issue of draft.issues) {
        const tag = document.createElement("span");
        tag.className = "issue";
        tag.textContent = issue;
        issues.appendChild(tag);
      }
      card.appendChild(issues);
    }

    const row = document.createElement("div");
    row.className = "row";

    const publishBtn = button("发布", "btn primary", async () => {
      const ok = await ask("发布这条说说？", draft.text, "发布", false);
      if (!ok) return;
      publishBtn.disabled = true;
      publishBtn.textContent = "发布中…";
      try {
        const result = await bridge.apiPost("drafts/publish", { id: draft.id });
        if (result && result.ok) {
          toast("已发布");
          await load();
        } else {
          toast("没有发布：" + ((result && result.issues) || []).join("；"), true);
          publishBtn.disabled = false;
          publishBtn.textContent = "发布";
        }
      } catch (error) {
        toast("发布失败：" + error.message, true);
        publishBtn.disabled = false;
        publishBtn.textContent = "发布";
      }
    });

    const copyBtn = button("复制", "btn ghost", async () => {
      try {
        await navigator.clipboard.writeText(draft.text || "");
        toast("已复制");
      } catch {
        toast("复制失败", true);
      }
    });

    const deleteBtn = button("删除", "btn danger", async () => {
      const ok = await ask("删除这条草稿？", draft.text, "删除");
      if (!ok) return;
      deleteBtn.disabled = true;
      try {
        await bridge.apiPost("drafts/delete", { id: draft.id });
        toast("已删除");
        await load();
      } catch (error) {
        toast("删除失败：" + error.message, true);
        deleteBtn.disabled = false;
      }
    });

    row.append(publishBtn, copyBtn, deleteBtn);
    card.appendChild(row);

    if (draft.image) {
      const img = document.createElement("img");
      img.className = "thumb";
      img.alt = "配图";
      img.loading = "lazy";
      card.appendChild(img);
      bridge.apiGet("drafts/image", { id: draft.id })
        .then((data) => { if (data && data.data) img.src = data.data; })
        .catch(() => {});
    }

    listEl.appendChild(card);
  }
}

refreshBtn.addEventListener("click", load);
generateBtn.addEventListener("click", async () => {
  generateBtn.disabled = true;
  const label = generateBtn.querySelector(".btn-label");
  const original = label.textContent;
  label.textContent = "生成中…";
  try {
    const result = await bridge.apiPost("generate", {});
    toast(result && result.ok ? "已生成草稿" : "生成失败：" + ((result && result.issues) || []).join("；"), !(result && result.ok));
    await load();
  } catch (error) {
    toast("生成失败：" + error.message, true);
  } finally {
    generateBtn.disabled = false;
    label.textContent = original;
  }
});

await bridge.ready();
await load();
