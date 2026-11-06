const hadPluginBridge = !!window.AstrBotPluginView;

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
const settingsBtn = document.getElementById("settingsBtn");
const settingsEl = document.getElementById("settings");
const settingsForm = document.getElementById("settingsForm");
const settingsClose = document.getElementById("settingsClose");
const settingsCancel = document.getElementById("settingsCancel");
const variantList = document.getElementById("variantList");
const variantAdd = document.getElementById("variantAdd");
const onboardingBanner = document.getElementById("onboardingBanner");
const onboardBtn = document.getElementById("onboardBtn");
const demoBtn = document.getElementById("demoBtn");
const doctorBtn = document.getElementById("doctorBtn");
const doctorList = document.getElementById("doctorList");

let toastTimer = null;
let angleOptions = [];
let onboardingData = null;

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
    const angleLabel = draft.angle_label || draft.angle || "随机";
    meta.innerHTML = `<span>${esc(draft.created_at || "")}</span><span>#${esc(draft.id)} · ${esc(angleLabel)}</span>`;

    const text = document.createElement("div");
    text.className = "text";
    text.textContent = draft.text || "";

    card.append(tape, tag, meta, text);

    if (draft.issues && draft.issues.length && !(draft.details && draft.details.length)) {
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

    if (draft.details && draft.details.length) {
      const report = document.createElement("details");
      report.className = "privacy-report";
      const summary = document.createElement("summary");
      summary.textContent = `隐私报告 · ${draft.details.length} 条`;
      report.appendChild(summary);
      if (draft.issues && draft.issues.length) report.open = true;
      const list = document.createElement("ul");
      const labels = {
        entity: "实体命中",
        regex: "号码/邮箱",
        deny: "禁用词",
        llm: "模型判断",
        length: "长度",
        similarity: "重复",
        tone: "AI 腔",
        publish: "发布",
        text: "文本",
      };
      for (const item of draft.details) {
        const li = document.createElement("li");
        li.textContent = `${labels[item.source] || item.source || "检查"}：${item.detail}`;
        list.appendChild(li);
      }
      report.appendChild(list);
      card.appendChild(report);
    }

    if (draft.used && draft.used.length) {
      const details = document.createElement("details");
      details.className = "memories";
      const summary = document.createElement("summary");
      summary.textContent = `用了 ${draft.used.length} 条记忆`;
      details.appendChild(summary);
      const list = document.createElement("ul");
      for (const item of draft.used) {
        const li = document.createElement("li");
        li.textContent = item;
        list.appendChild(li);
      }
      details.appendChild(list);
      card.appendChild(details);
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

    const editBtn = button("编辑", "btn ghost", () => {
      if (card.querySelector(".edit-box")) return;
      const box = document.createElement("div");
      box.className = "edit-box";
      const area = document.createElement("textarea");
      area.value = draft.text || "";
      area.rows = 3;
      const save = button("保存", "btn primary", async () => {
        save.disabled = true;
        try {
          const result = await bridge.apiPost("drafts/update", { id: draft.id, text: area.value });
          if (result && result.ok) {
            toast("已保存");
            await load();
          } else {
            toast("没保存：" + ((result && result.issues) || []).join("；"), true);
            save.disabled = false;
          }
        } catch (error) {
          toast("保存失败：" + error.message, true);
          save.disabled = false;
        }
      });
      const cancel = button("取消", "btn ghost", () => box.remove());
      const actions = document.createElement("div");
      actions.className = "edit-actions";
      actions.append(save, cancel);
      box.append(area, actions);
      card.appendChild(box);
    });

    const angleSelect = document.createElement("select");
    angleSelect.className = "angle-select";
    angleSelect.innerHTML = '<option value="">随机写法</option>' + angleOptions
      .map((a) => `<option value="${esc(a.id)}">${esc(a.label)}</option>`)
      .join("");
    if (draft.angle) angleSelect.value = draft.angle;

    const rewriteBtn = button("换个写法", "btn ghost", async () => {
      rewriteBtn.disabled = true;
      rewriteBtn.textContent = "重写中…";
      try {
        const result = await bridge.apiPost("drafts/regenerate", { id: draft.id, angle: angleSelect.value });
        if (result && result.ok) {
          toast("换了个写法");
          await load();
        } else if (result && result.skipped) {
          toast("今天没素材，先不硬写", true);
        } else {
          toast("没重写：" + ((result && result.issues) || []).join("；"), true);
        }
      } catch (error) {
        toast("重写失败：" + error.message, true);
      } finally {
        rewriteBtn.disabled = false;
        rewriteBtn.textContent = "换个写法";
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

    row.append(publishBtn, editBtn, angleSelect, rewriteBtn, copyBtn, deleteBtn);
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

function addVariantCard(variant = {}) {
  const card = document.createElement("div");
  card.className = "variant-card";
  const name = document.createElement("input");
  name.className = "variant-name";
  name.type = "text";
  name.placeholder = "形象名，例如 小鲸鱼";
  name.value = variant.name || "";
  const desc = document.createElement("textarea");
  desc.className = "variant-desc";
  desc.rows = 2;
  desc.placeholder = "外形、气质、说话方式";
  desc.value = variant.desc || "";
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "variant-remove";
  remove.textContent = "删除";
  remove.addEventListener("click", () => card.remove());
  card.append(name, desc, remove);
  variantList.appendChild(card);
}

function renderVariants(list) {
  variantList.innerHTML = "";
  for (const item of list || []) addVariantCard(item);
}

function readVariants() {
  const out = [];
  for (const card of variantList.querySelectorAll(".variant-card")) {
    const name = card.querySelector(".variant-name").value.trim();
    const desc = card.querySelector(".variant-desc").value.trim();
    if (name && desc) out.push({ name, desc });
  }
  return out;
}

function fillSettings(cfg) {
  for (const el of settingsForm.querySelectorAll("[data-key]")) {
    const key = el.dataset.key;
    if (key === "images_api_key") {
      el.value = "";
      continue;
    }
    if (key === "self_image_variants") continue;
    const value = cfg[key];
    if (el.type === "checkbox") {
      el.checked = Boolean(value);
    } else {
      el.value = value ?? "";
    }
  }
  renderVariants(cfg.self_image_variants || []);
}

async function openSettings() {
  try {
    const data = await bridge.apiGet("config");
    fillSettings(data.config || {});
    settingsEl.hidden = false;
  } catch (error) {
    toast("打开设置失败：" + error.message, true);
  }
}

function closeSettings() {
  settingsEl.hidden = true;
}

async function saveSettings(event) {
  event.preventDefault();
  const payload = { self_image_variants: readVariants() };
  for (const el of settingsForm.querySelectorAll("[data-key]")) {
    const key = el.dataset.key;
    if (key === "images_api_key" && !el.value.trim()) continue;
    if (key === "self_image_variants") continue;
    if (el.type === "checkbox") {
      payload[key] = el.checked;
    } else if (el.type === "number") {
      payload[key] = Number(el.value);
    } else {
      payload[key] = el.value;
    }
  }
  const saveBtn = document.getElementById("settingsSave");
  saveBtn.disabled = true;
  saveBtn.textContent = "保存中…";
  try {
    const result = await bridge.apiPost("config", payload);
    fillSettings(result.config || {});
    closeSettings();
    toast("设置已保存");
    await load();
  } catch (error) {
    toast("保存失败：" + error.message, true);
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = "保存";
  }
}

if (!hadPluginBridge) {
  settingsBtn.hidden = true;
  onboardingBanner.hidden = true;
} else {
  settingsBtn.addEventListener("click", openSettings);
  settingsClose.addEventListener("click", closeSettings);
  settingsCancel.addEventListener("click", closeSettings);
  for (const mask of settingsEl.querySelectorAll("[data-close]")) {
    mask.addEventListener("click", closeSettings);
  }
  settingsForm.addEventListener("submit", saveSettings);
  variantAdd.addEventListener("click", () => addVariantCard());
  onboardBtn.addEventListener("click", autoConfigure);
  doctorBtn.addEventListener("click", runDoctor);
  demoBtn.addEventListener("click", showDemo);
}

async function autoConfigure() {
  const candidates = (onboardingData && onboardingData.candidates) || {};
  const payload = {};
  for (const key of ["memory_file", "diary_dir", "persona_file"]) {
    const list = candidates[key] || [];
    if (list.length) payload[key] = list[0];
  }
  if (!Object.keys(payload).length) {
    openSettings();
    return;
  }
  try {
    await bridge.apiPost("onboarding/apply", payload);
    toast("已经自动填好，接着补剩下的一两项就行");
    await checkOnboarding();
    await openSettings();
  } catch (error) {
    toast("自动配置失败：" + error.message, true);
    openSettings();
  }
}

async function showDemo() {
  try {
    const data = await bridge.apiGet("demo");
    const text = (data.examples || []).map((item) => `【${item.label}】\n${item.text}`).join("\n\n");
    await ask("她写出来是这样", text || "暂无示例", "知道了", true);
  } catch (error) {
    toast("示例加载失败：" + error.message, true);
  }
}

async function runDoctor() {
  doctorBtn.disabled = true;
  doctorBtn.textContent = "检查中…";
  try {
    const data = await bridge.apiGet("doctor");
    doctorList.innerHTML = "";
    const labels = { green: "正常", yellow: "注意", red: "要修" };
    for (const item of data.items || []) {
      const row = document.createElement("div");
      row.className = `doctor-row ${item.status}`;
      const dot = document.createElement("span");
      dot.className = "doctor-dot";
      const text = document.createElement("div");
      text.className = "doctor-text";
      text.innerHTML = `<strong>${esc(item.label)}</strong><span>${esc(item.detail)}</span>`;
      row.append(dot, text);
      if (item.action === "auto") {
        const fix = button("自动找", "btn ghost small", autoConfigure);
        row.appendChild(fix);
      } else if (item.action === "settings") {
        row.appendChild(button("去设置", "btn ghost small", openSettings));
      }
      doctorList.appendChild(row);
      row.title = labels[item.status] || "";
    }
  } catch (error) {
    doctorList.textContent = "检查失败：" + error.message;
  } finally {
    doctorBtn.disabled = false;
    doctorBtn.textContent = "检查配置";
  }
}

async function loadAngles() {
  try {
    const data = await bridge.apiGet("angles");
    angleOptions = data.angles || [];
  } catch {
    angleOptions = [];
  }
}

async function checkOnboarding() {
  if (!hadPluginBridge) return;
  try {
    const data = await bridge.apiGet("onboarding/status");
    onboardingData = data;
    onboardingBanner.hidden = Boolean(data.ready);
    onboardingBanner.style.display = data.ready ? "none" : "flex";
  } catch {
    onboardingData = null;
    onboardingBanner.hidden = true;
    onboardingBanner.style.display = "none";
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
    if (result && result.skipped) {
      toast("今天没素材，先不硬写");
    } else {
      toast(result && result.ok ? "已生成草稿" : "生成失败：" + ((result && result.issues) || []).join("；"), !(result && result.ok));
    }
    await load();
  } catch (error) {
    toast("生成失败：" + error.message, true);
  } finally {
    generateBtn.disabled = false;
    label.textContent = original;
  }
});

await bridge.ready();
await loadAngles();
await checkOnboarding();
await load();
