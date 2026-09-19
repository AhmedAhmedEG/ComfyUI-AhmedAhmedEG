// Resilient import of app and api across ComfyUI versions and paths
let app = window.comfyAPI?.app?.app;
let api = window.comfyAPI?.api?.api;

if (!app) {
  try {
    const mod = await import("../../scripts/app.js");
    app = mod.app;
  } catch (e1) {
    try {
      const mod = await import("../../../scripts/app.js");
      app = mod.app;
    } catch (e2) {
      const mod = await import("/scripts/app.js");
      app = mod.app;
    }
  }
}

if (!api) {
  try {
    const mod = await import("../../scripts/api.js");
    api = mod.api;
  } catch (e1) {
    try {
      const mod = await import("../../../scripts/api.js");
      api = mod.api;
    } catch (e2) {
      const mod = await import("/scripts/api.js");
      api = mod.api;
    }
  }
}

const INLINED_CSS = `/* Modern, sleek timeline editor styling for MiniMax H3 Master Director */

.mmx-director-root {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  min-width: 680px;
  box-sizing: border-box;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: #e2e8f0;
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 8px;
  padding: 10px;
  user-select: none;
}

/* Toolbar */
.mmx-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  padding-bottom: 6px;
  border-bottom: 1px solid #1e293b;
}

.mmx-pill-group {
  display: flex;
  align-items: center;
  gap: 3px;
  background: #090d16;
  padding: 3px;
  border-radius: 20px;
  border: 1px solid #1e293b;
}

.mmx-pill-btn {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 11px;
  font-weight: 500;
  padding: 3px 10px;
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.mmx-pill-btn:hover {
  color: #f1f5f9;
  background: rgba(255, 255, 255, 0.05);
}

.mmx-pill-btn.active {
  background: #6366f1;
  color: #ffffff;
  font-weight: 600;
  box-shadow: 0 0 10px rgba(99, 102, 241, 0.4);
}

.mmx-action-btn {
  background: #1e293b;
  border: 1px solid #334155;
  color: #cbd5e1;
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  transition: all 0.15s ease;
}

.mmx-action-btn:hover {
  background: #334155;
  color: #f8fafc;
  border-color: #475569;
}

.mmx-action-btn.primary {
  background: rgba(99, 102, 241, 0.2);
  border-color: #6366f1;
  color: #a5b4fc;
}

.mmx-action-btn.primary:hover {
  background: #6366f1;
  color: #ffffff;
}

/* Timeline tracks area */
.mmx-timeline-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: #090d16;
  border: 1px solid #1e293b;
  border-radius: 6px;
  padding: 8px;
  overflow-x: auto;
}

.mmx-track {
  display: flex;
  align-items: center;
  position: relative;
  min-height: 84px;
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 6px;
  padding: 4px 8px;
  gap: 8px;
}

.mmx-track-header {
  position: absolute;
  top: 4px;
  left: 6px;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: #64748b;
  text-transform: uppercase;
  pointer-events: none;
  z-index: 2;
}

.mmx-track-items {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding-top: 14px;
  overflow-x: auto;
}

/* Media Item Tile */
.mmx-tile {
  position: relative;
  width: 96px;
  height: 64px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 5px;
  overflow: hidden;
  cursor: pointer;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  transition: transform 0.1s ease, border-color 0.15s ease;
}

.mmx-tile:hover {
  border-color: #6366f1;
  transform: translateY(-1px);
}

.mmx-tile.selected {
  border-color: #38bdf8;
  box-shadow: 0 0 0 1px #38bdf8, 0 0 12px rgba(56, 189, 248, 0.3);
}

.mmx-tile-thumb {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.75;
}

.mmx-tile-badge {
  position: absolute;
  top: 3px;
  left: 4px;
  background: rgba(0, 0, 0, 0.7);
  color: #38bdf8;
  font-size: 9px;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 3px;
  z-index: 3;
}

.mmx-tile-stream-pills {
  position: absolute;
  top: 3px;
  right: 4px;
  display: flex;
  gap: 2px;
  z-index: 3;
}

.mmx-stream-pill {
  font-size: 8px;
  font-weight: 700;
  padding: 1px 3px;
  background: rgba(0, 0, 0, 0.6);
  color: #94a3b8;
  border-radius: 2px;
  border: none;
  cursor: pointer;
}

.mmx-stream-pill.active {
  background: #6366f1;
  color: #ffffff;
}

.mmx-tile-label {
  position: relative;
  z-index: 2;
  background: rgba(15, 23, 42, 0.85);
  font-size: 9px;
  padding: 2px 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #cbd5e1;
}

/* Audio waveform canvas */
.mmx-waveform-canvas {
  width: 100%;
  height: 50px;
  border-radius: 4px;
}

/* Plus add slot button */
.mmx-add-slot {
  width: 38px;
  height: 64px;
  border: 1px dashed #334155;
  border-radius: 5px;
  background: rgba(30, 41, 59, 0.4);
  color: #64748b;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 18px;
  flex-shrink: 0;
  transition: all 0.15s ease;
}

.mmx-add-slot:hover {
  border-color: #6366f1;
  color: #a5b4fc;
  background: rgba(99, 102, 241, 0.1);
}

/* Sequence track clip card */
.mmx-clip-block {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-width: 130px;
  height: 46px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 5px;
  padding: 4px 8px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.mmx-clip-block:hover {
  border-color: #6366f1;
}

.mmx-clip-block.validated {
  border-color: #10b981;
  background: rgba(16, 185, 129, 0.1);
}

.mmx-clip-block.active {
  box-shadow: 0 0 0 1px #6366f1, 0 0 10px rgba(99, 102, 241, 0.3);
}

.mmx-clip-title {
  font-size: 11px;
  font-weight: 600;
  color: #f1f5f9;
}

.mmx-clip-meta {
  font-size: 9px;
  color: #94a3b8;
}

/* Drawer / Prompt area */
.mmx-drawer {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #090d16;
  border: 1px solid #1e293b;
  border-radius: 6px;
  padding: 10px;
}

.mmx-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
}

.mmx-textarea {
  width: 100%;
  box-sizing: border-box;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 5px;
  color: #f8fafc;
  font-family: inherit;
  font-size: 11px;
  padding: 6px 8px;
  resize: vertical;
  min-height: 54px;
}

.mmx-textarea:focus {
  outline: none;
  border-color: #6366f1;
}

/* Modal overlays */
.mmx-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.mmx-modal-panel {
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 10px;
  width: min(720px, 92vw);
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.8);
}

.mmx-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #1e293b;
  background: #090d16;
}

.mmx-modal-title {
  font-size: 14px;
  font-weight: 700;
  color: #f8fafc;
}

.mmx-modal-body {
  padding: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mmx-modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 16px;
  border-top: 1px solid #1e293b;
  background: #090d16;
}

/* View Navigation Tabs */
.mmx-view-tabs {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0 6px 0;
  border-bottom: 1px solid #1e293b;
  margin-bottom: 4px;
}

.mmx-tab-btn {
  background: #1e293b;
  border: 1px solid #334155;
  color: #94a3b8;
  font-size: 11px;
  font-weight: 600;
  padding: 5px 12px;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  transition: all 0.15s ease;
}

.mmx-tab-btn:hover {
  background: #334155;
  color: #f8fafc;
  border-color: #475569;
}

.mmx-tab-btn.active {
  background: rgba(99, 102, 241, 0.25);
  border-color: #6366f1;
  color: #c7d2fe;
  box-shadow: 0 0 10px rgba(99, 102, 241, 0.3);
}

.mmx-track-empty-notice {
  font-size: 10px;
  color: #64748b;
  font-style: italic;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 8px;
  height: 64px;
}

/* RefMod Panel */
.mmx-refmod-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #090d16;
  border: 1px solid #1e293b;
  border-radius: 6px;
  padding: 10px;
}

.mmx-refmod-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
}

.mmx-refmod-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mmx-refmod-row {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 6px 10px;
}

.mmx-refmod-slot-badge {
  background: #6366f1;
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  white-space: nowrap;
}

.mmx-refmod-input {
  flex: 1;
  background: #1e293b;
  border: 1px solid #475569;
  border-radius: 4px;
  color: #f8fafc;
  font-size: 11px;
  padding: 3px 6px;
}

.mmx-refmod-input:focus {
  outline: none;
  border-color: #6366f1;
}

.mmx-refmod-slider-group {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 140px;
}

.mmx-refmod-slider {
  width: 90px;
  cursor: pointer;
}

.mmx-refmod-val {
  font-size: 10px;
  font-weight: 600;
  color: #38bdf8;
  width: 32px;
  text-align: right;
}

.mmx-refmod-note {
  font-size: 10px;
  color: #64748b;
  line-height: 1.4;
  padding: 4px 6px;
  background: rgba(30, 41, 59, 0.5);
  border-radius: 4px;
  border-left: 3px solid #6366f1;
}

`;

function injectCSS() {
  if (document.getElementById("mmx-director-styles")) return;
  const style = document.createElement("style");
  style.id = "mmx-director-styles";
  style.textContent = INLINED_CSS;
  document.head.appendChild(style);
}

function mountDirectorUI(node) {
  if (!node || node.__mmxDirectorMounted) return;
  node.__mmxDirectorMounted = true;

  injectCSS();

  // Find widget references
  const modeWidget = node.widgets?.find((w) => w.name === "mode");
  const durationWidget = node.widgets?.find((w) => w.name === "duration");
  const promptWidget = node.widgets?.find((w) => w.name === "prompt");
  const timelineWidget = node.widgets?.find((w) => w.name === "timeline_data");
  const builderWidget = node.widgets?.find((w) => w.name === "builder_state");

  // Fully hide raw serialized widgets and prompt textarea from canvas
  const hideWidget = (w) => {
    if (!w) return;
    w.hidden = true;
    w.type = "hidden";
    w.computeSize = () => [0, -4];
    w.draw = () => {};
  };
  hideWidget(timelineWidget);
  hideWidget(builderWidget);
  hideWidget(promptWidget);

  // State
  let timelineState = {
    version: 1,
    items: [],
    clips: [{ id: "clip_1", name: "Shot 1", duration: 5.0, validated: false, prompt: "" }],
    refmods: [],
  };

  let builderState = {
    ref: {
      subject_definitions: "",
      summary: "",
      retention_analysis: "",
      detailed_description: "",
      soundscape: "",
      music: "",
    },
    imd: "",
    soundscape: "",
    music: "",
  };

  const loadState = () => {
    try {
      if (timelineWidget && timelineWidget.value) {
        const parsed = typeof timelineWidget.value === "string" ? JSON.parse(timelineWidget.value) : timelineWidget.value;
        if (parsed && typeof parsed === "object") {
          timelineState = { ...timelineState, ...parsed };
          if (!Array.isArray(timelineState.items)) timelineState.items = [];
          if (!Array.isArray(timelineState.clips) || timelineState.clips.length === 0) {
            timelineState.clips = [{ id: "clip_1", name: "Shot 1", duration: 5.0, validated: false, prompt: "" }];
          }
          if (!Array.isArray(timelineState.refmods)) timelineState.refmods = [];
        }
      }
    } catch (e) {}

    try {
      if (builderWidget && builderWidget.value) {
        const parsed = typeof builderWidget.value === "string" ? JSON.parse(builderWidget.value) : builderWidget.value;
        if (parsed && typeof parsed === "object") {
          builderState = { ...builderState, ...parsed };
          if (!builderState.ref) builderState.ref = {};
        }
      }
    } catch (e) {}
  };

  loadState();

  const syncState = () => {
    if (timelineWidget) timelineWidget.value = JSON.stringify(timelineState);
    if (builderWidget) builderWidget.value = JSON.stringify(builderState);
  };

  // Create modern timeline root element
  const root = document.createElement("div");
  root.className = "mmx-director-root";

  // 1. Toolbar (Mode selector & Project Export/Import/Clear)
  const toolbar = document.createElement("div");
  toolbar.className = "mmx-toolbar";

  const modePills = document.createElement("div");
  modePills.className = "mmx-pill-group";

  const modes = ["REF2VA", "FL2VA", "I2VA", "T2VA", "L2VA", "V2V", "Image Inpaint"];
  modes.forEach((m) => {
    const btn = document.createElement("button");
    btn.className = "mmx-pill-btn" + ((modeWidget?.value || "REF2VA") === m ? " active" : "");
    btn.textContent = m;
    btn.onclick = () => {
      modePills.querySelectorAll(".mmx-pill-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      if (modeWidget) {
        modeWidget.value = m;
        if (modeWidget.callback) modeWidget.callback(m);
      }
      renderPromptDrawer();
    };
    modePills.appendChild(btn);
  });
  toolbar.appendChild(modePills);

  const actionGroup = document.createElement("div");
  actionGroup.style.display = "flex";
  actionGroup.style.gap = "6px";

  const exportBtn = document.createElement("button");
  exportBtn.className = "mmx-action-btn primary";
  exportBtn.innerHTML = "💾 Export Project";
  exportBtn.title = "Export lightweight project archive (latents remain cached on server)";
  exportBtn.onclick = async () => {
    try {
      const res = await api.fetchApi("/minimax_director/project/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: String(node.id || "default"),
          timeline: timelineState,
          name: "MiniMaxProject",
        }),
      });
      const data = await res.json();
      if (data.ok) {
        const blob = new Blob([JSON.stringify(data.project, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `minimax_project_${Date.now()}.mmxproj.json`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      alert("Failed to export project: " + err);
    }
  };

  const importBtn = document.createElement("button");
  importBtn.className = "mmx-action-btn";
  importBtn.innerHTML = "📂 Import Project";
  importBtn.onclick = () => {
    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = ".json,.mmxproj";
    fileInput.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        const text = await file.text();
        const projectData = JSON.parse(text);
        const res = await api.fetchApi("/minimax_director/project/import", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project: projectData }),
        });
        const data = await res.json();
        if (data.ok && data.timeline) {
          timelineState = { ...timelineState, ...data.timeline };
          syncState();
          renderTracks();
          renderPromptDrawer();
          renderRefmods();
          alert("Project imported successfully! Connected to server cache.");
        }
      } catch (err) {
        alert("Failed to import project: " + err);
      }
    };
    fileInput.click();
  };

  const clearBtn = document.createElement("button");
  clearBtn.className = "mmx-action-btn";
  clearBtn.innerHTML = "🗑️ Clear";
  clearBtn.onclick = () => {
    if (confirm("Clear all references and prompt blocks?")) {
      timelineState.items = [];
      timelineState.clips = [{ id: "clip_1", name: "Shot 1", duration: 5.0, validated: false, prompt: "" }];
      timelineState.refmods = [];
      syncState();
      renderTracks();
      renderPromptDrawer();
      renderRefmods();
    }
  };

  actionGroup.appendChild(exportBtn);
  actionGroup.appendChild(importBtn);
  actionGroup.appendChild(clearBtn);
  toolbar.appendChild(actionGroup);
  root.appendChild(toolbar);

  // 2. View Tabs
  let activeTab = "timeline"; // "timeline" | "prompts" | "refmods"

  const viewTabs = document.createElement("div");
  viewTabs.className = "mmx-view-tabs";

  const tabsConfig = [
    { id: "timeline", label: "🎬 Visual & Audio Timeline" },
    { id: "prompts", label: "📝 Prompt Builder" },
    { id: "refmods", label: "🎛️ RefMods" },
  ];

  const tabButtons = [];

  tabsConfig.forEach((cfg) => {
    const btn = document.createElement("button");
    btn.className = "mmx-tab-btn" + (activeTab === cfg.id ? " active" : "");
    btn.textContent = cfg.label;
    btn.dataset.tab = cfg.id;
    btn.onclick = () => {
      activeTab = cfg.id;
      switchTab(activeTab);
    };
    tabButtons.push(btn);
    viewTabs.appendChild(btn);
  });
  root.appendChild(viewTabs);

  // 3. Timeline Panel
  const timelinePanel = document.createElement("div");
  timelinePanel.className = "mmx-timeline-panel";

  // Visual Track
  const visualTrack = document.createElement("div");
  visualTrack.className = "mmx-track";
  const visualHeader = document.createElement("div");
  visualHeader.className = "mmx-track-header";
  visualHeader.textContent = "Visual References (Images & Videos)";
  const visualItems = document.createElement("div");
  visualItems.className = "mmx-track-items";
  visualTrack.appendChild(visualHeader);
  visualTrack.appendChild(visualItems);

  // Audio Track
  const audioTrack = document.createElement("div");
  audioTrack.className = "mmx-track";
  const audioHeader = document.createElement("div");
  audioHeader.className = "mmx-track-header";
  audioHeader.textContent = "Audio References";
  const audioItems = document.createElement("div");
  audioItems.className = "mmx-track-items";
  audioTrack.appendChild(audioHeader);
  audioTrack.appendChild(audioItems);

  // Clip Sequence Track
  const clipTrack = document.createElement("div");
  clipTrack.className = "mmx-track";
  const clipHeader = document.createElement("div");
  clipHeader.className = "mmx-track-header";
  clipHeader.textContent = "Clip Sequence & Continuity";
  const clipItems = document.createElement("div");
  clipItems.className = "mmx-track-items";
  clipTrack.appendChild(clipHeader);
  clipTrack.appendChild(clipItems);

  timelinePanel.appendChild(visualTrack);
  timelinePanel.appendChild(audioTrack);
  timelinePanel.appendChild(clipTrack);
  root.appendChild(timelinePanel);

  // 4. Prompt Drawer Panel
  const drawer = document.createElement("div");
  drawer.className = "mmx-drawer";
  root.appendChild(drawer);

  // 5. RefMod Panel
  const refmodPanel = document.createElement("div");
  refmodPanel.className = "mmx-refmod-panel";
  root.appendChild(refmodPanel);

  // Tab switching helper
  const switchTab = (tabId) => {
    tabButtons.forEach((b) => {
      b.classList.toggle("active", b.dataset.tab === tabId);
    });

    timelinePanel.style.display = tabId === "timeline" ? "flex" : "none";
    drawer.style.display = tabId === "prompts" ? "flex" : "none";
    refmodPanel.style.display = tabId === "refmods" ? "flex" : "none";

    let desiredHeight = 360;
    if (tabId === "prompts") desiredHeight = 520;
    else if (tabId === "refmods") desiredHeight = 360;

    if (domWidget) {
      domWidget.computeSize = function (width) {
        return [width || 920, desiredHeight];
      };
    }

    const currentW = Math.max(node.size?.[0] || 0, 960);
    const minNodeH = desiredHeight + 420;
    node.setSize([currentW, Math.max(node.size?.[1] || 0, minNodeH)]);
    if (node.setDirtyCanvas) node.setDirtyCanvas(true, true);
  };

  // Render Tracks helper
  const renderTracks = () => {
    visualItems.innerHTML = "";
    audioItems.innerHTML = "";
    clipItems.innerHTML = "";

    let imgIndex = 1;
    let vidIndex = 1;
    let audIndex = 1;

    const visualMedia = timelineState.items.filter((i) => i.type === "image" || i.type === "video");
    const audioMedia = timelineState.items.filter((i) => i.type === "audio");

    // Empty state notices
    if (visualMedia.length === 0) {
      const notice = document.createElement("div");
      notice.className = "mmx-track-empty-notice";
      notice.innerHTML = "🖼️ No visual references added. Click <b>[+]</b> to attach images or videos.";
      visualItems.appendChild(notice);
    }

    if (audioMedia.length === 0) {
      const notice = document.createElement("div");
      notice.className = "mmx-track-empty-notice";
      notice.innerHTML = "🎵 No audio references added. Click <b>[+]</b> to attach audio clips.";
      audioItems.appendChild(notice);
    }

    // Render media items
    timelineState.items.forEach((item, idx) => {
      if (item.type === "image" || item.type === "video") {
        const tile = document.createElement("div");
        tile.className = "mmx-tile";

        const badge = document.createElement("div");
        badge.className = "mmx-tile-badge";
        badge.textContent = item.type === "image" ? `Picture ${imgIndex++}` : `Video ${vidIndex++}`;
        tile.appendChild(badge);

        const streamPills = document.createElement("div");
        streamPills.className = "mmx-tile-stream-pills";

        if (item.type === "video") {
          ["V", "A", "V+A"].forEach((modeVal) => {
            const sp = document.createElement("button");
            sp.className = "mmx-stream-pill" + ((item.media_mode || "video") === (modeVal === "V" ? "video" : modeVal === "A" ? "audio" : "video_audio") ? " active" : "");
            sp.textContent = modeVal;
            sp.onclick = (e) => {
              e.stopPropagation();
              item.media_mode = modeVal === "V" ? "video" : modeVal === "A" ? "audio" : "video_audio";
              syncState();
              renderTracks();
            };
            streamPills.appendChild(sp);
          });
        }

        const delBtn = document.createElement("button");
        delBtn.className = "mmx-stream-pill";
        delBtn.textContent = "✕";
        delBtn.title = "Remove reference";
        delBtn.onclick = (e) => {
          e.stopPropagation();
          timelineState.items.splice(idx, 1);
          syncState();
          renderTracks();
        };
        streamPills.appendChild(delBtn);
        tile.appendChild(streamPills);

        const label = document.createElement("div");
        label.className = "mmx-tile-label";
        label.textContent = item.value || "media";
        tile.appendChild(label);

        visualItems.appendChild(tile);
      } else if (item.type === "audio") {
        const tile = document.createElement("div");
        tile.className = "mmx-tile";
        tile.style.width = "140px";

        const badge = document.createElement("div");
        badge.className = "mmx-tile-badge";
        badge.textContent = `Audio ${audIndex++}`;
        tile.appendChild(badge);

        const streamPills = document.createElement("div");
        streamPills.className = "mmx-tile-stream-pills";
        const delBtn = document.createElement("button");
        delBtn.className = "mmx-stream-pill";
        delBtn.textContent = "✕";
        delBtn.title = "Remove reference";
        delBtn.onclick = (e) => {
          e.stopPropagation();
          timelineState.items.splice(idx, 1);
          syncState();
          renderTracks();
        };
        streamPills.appendChild(delBtn);
        tile.appendChild(streamPills);

        const canvas = document.createElement("canvas");
        canvas.className = "mmx-waveform-canvas";
        canvas.width = 140;
        canvas.height = 40;
        drawWaveform(canvas);
        tile.appendChild(canvas);

        const label = document.createElement("div");
        label.className = "mmx-tile-label";
        label.textContent = item.value || "audio";
        tile.appendChild(label);

        audioItems.appendChild(tile);
      }
    });

    // Add visual slot button (+)
    const addVisual = document.createElement("div");
    addVisual.className = "mmx-add-slot";
    addVisual.innerHTML = "+";
    addVisual.title = "Add Image or Video Reference";
    addVisual.onclick = () => {
      const fileInput = document.createElement("input");
      fileInput.type = "file";
      fileInput.accept = "image/*,video/*";
      fileInput.onchange = (e) => {
        const f = e.target.files[0];
        if (!f) return;
        const isVid = f.type.startsWith("video/");
        timelineState.items.push({
          type: isVid ? "video" : "image",
          value: f.name,
          media_mode: isVid ? "video" : undefined,
          trim_start: 0.0,
          trim_end: isVid ? 5.0 : undefined,
          enabled: true,
        });
        syncState();
        renderTracks();
      };
      fileInput.click();
    };
    visualItems.appendChild(addVisual);

    // Add audio slot button (+)
    const addAudio = document.createElement("div");
    addAudio.className = "mmx-add-slot";
    addAudio.innerHTML = "+";
    addAudio.title = "Add Audio Reference";
    addAudio.onclick = () => {
      const fileInput = document.createElement("input");
      fileInput.type = "file";
      fileInput.accept = "audio/*";
      fileInput.onchange = (e) => {
        const f = e.target.files[0];
        if (!f) return;
        timelineState.items.push({
          type: "audio",
          value: f.name,
          trim_start: 0.0,
          trim_end: 5.0,
          enabled: true,
        });
        syncState();
        renderTracks();
      };
      fileInput.click();
    };
    audioItems.appendChild(addAudio);

    // Render clip sequence blocks
    timelineState.clips.forEach((clip, cIdx) => {
      const clipBlock = document.createElement("div");
      clipBlock.className = "mmx-clip-block" + (clip.validated ? " validated" : "");

      const left = document.createElement("div");
      const title = document.createElement("div");
      title.className = "mmx-clip-title";
      title.textContent = clip.name || `Shot ${cIdx + 1}`;
      const meta = document.createElement("div");
      meta.className = "mmx-clip-meta";
      meta.textContent = `${clip.duration || 5.0}s`;
      left.appendChild(title);
      left.appendChild(meta);
      clipBlock.appendChild(left);

      const right = document.createElement("div");
      right.style.display = "flex";
      right.style.alignItems = "center";
      right.style.gap = "4px";

      // Color palette button
      const colorBtn = document.createElement("button");
      colorBtn.className = "mmx-stream-pill";
      colorBtn.innerHTML = "🎨";
      colorBtn.title = "Color Adjustment";
      colorBtn.onclick = (e) => {
        e.stopPropagation();
        openColorEditor(clip);
      };
      right.appendChild(colorBtn);

      // Validation checkbox
      const valCheck = document.createElement("input");
      valCheck.type = "checkbox";
      valCheck.checked = !!clip.validated;
      valCheck.title = "Validated & Locked";
      valCheck.onchange = (e) => {
        e.stopPropagation();
        clip.validated = valCheck.checked;
        syncState();
        renderTracks();
      };
      right.appendChild(valCheck);

      clipBlock.appendChild(right);
      clipItems.appendChild(clipBlock);
    });

    // Add clip button (+)
    const addClip = document.createElement("div");
    addClip.className = "mmx-add-slot";
    addClip.style.height = "46px";
    addClip.innerHTML = "+";
    addClip.title = "Add Clip / Shot";
    addClip.onclick = () => {
      timelineState.clips.push({
        id: `clip_${timelineState.clips.length + 1}`,
        name: `Shot ${timelineState.clips.length + 1}`,
        duration: 5.0,
        validated: false,
        prompt: "",
      });
      syncState();
      renderTracks();
    };
    clipItems.appendChild(addClip);
  };

  // Render Prompt Drawer
  const renderPromptDrawer = () => {
    drawer.innerHTML = "";
    const curMode = modeWidget?.value || "REF2VA";

    const header = document.createElement("div");
    header.className = "mmx-drawer-header";
    header.innerHTML = `<span>Prompt Builder (${curMode})</span>`;

    // Helper buttons
    const helpers = document.createElement("div");
    helpers.style.display = "flex";
    helpers.style.gap = "6px";

    if (curMode === "REF2VA") {
      const prefillBtn = document.createElement("button");
      prefillBtn.className = "mmx-action-btn";
      prefillBtn.textContent = "⚡ Prefill Scaffolding";
      prefillBtn.onclick = () => {
        let imgC = timelineState.items.filter((i) => i.type === "image").length;
        let defs = [];
        for (let i = 1; i <= Math.max(1, imgC); i++) {
          defs.push(`<Subject ${i}> is the person in <Picture ${i}> with natural motion.`);
          defs.push(`<Picture ${i}> defines identity and appearance.`);
        }
        builderState.ref.subject_definitions = defs.join("\n");
        builderState.ref.summary = `[reference generation] Cinematic scene starring the subjects.`;
        builderState.ref.retention_analysis = `<Subject 1>: fully_preserved - appearance is consistent.`;
        builderState.ref.detailed_description = `[Shot 1] The scene begins with smooth tracking camera.`;
        builderState.ref.soundscape = `Natural environmental acoustics.`;
        builderState.ref.music = `N/A`;
        syncState();
        renderPromptDrawer();
        if (promptWidget) promptWidget.value = builderState.ref.detailed_description;
      };
      helpers.appendChild(prefillBtn);
    }

    const shotBtn = document.createElement("button");
    shotBtn.className = "mmx-action-btn";
    shotBtn.textContent = "➕ Insert [Shot N]";
    shotBtn.onclick = () => {
      const n = prompt("Enter shot number:", "2");
      if (n) {
        const timeStr = prompt("Enter cut timestamp (e.g. 00:04.500):", "00:04.500");
        const tag = timeStr ? `\n[Shot ${n}] At ${timeStr}, ` : `\n[Shot ${n}] `;
        if (curMode === "REF2VA") {
          builderState.ref.detailed_description = (builderState.ref.detailed_description || "") + tag;
          if (promptWidget) promptWidget.value = builderState.ref.detailed_description;
        } else {
          builderState.imd = (builderState.imd || "") + tag;
          if (promptWidget) promptWidget.value = builderState.imd;
        }
        syncState();
        renderPromptDrawer();
      }
    };
    helpers.appendChild(shotBtn);

    header.appendChild(helpers);
    drawer.appendChild(header);

    if (curMode === "REF2VA") {
      const fields = [
        { key: "subject_definitions", label: "subject_definitions:" },
        { key: "summary", label: "summary:" },
        { key: "retention_analysis", label: "retention_analysis:" },
        { key: "detailed_description", label: "detailed_description:" },
        { key: "soundscape", label: "overall_soundscape:" },
        { key: "music", label: "non_diegetic_music:" },
      ];

      fields.forEach((f) => {
        const lbl = document.createElement("div");
        lbl.style.fontSize = "10px";
        lbl.style.fontWeight = "700";
        lbl.style.color = "#818cf8";
        lbl.textContent = f.label;
        drawer.appendChild(lbl);

        const ta = document.createElement("textarea");
        ta.className = "mmx-textarea";
        ta.value = builderState.ref[f.key] || "";
        ta.oninput = () => {
          builderState.ref[f.key] = ta.value;
          syncState();
          if (f.key === "detailed_description" && promptWidget) promptWidget.value = ta.value;
        };
        drawer.appendChild(ta);
      });
    } else {
      const fields = [
        { key: "imd", label: "integrated_multimodal_description:" },
        { key: "soundscape", label: "overall_soundscape:" },
        { key: "music", label: "non_diegetic_music:" },
      ];

      fields.forEach((f) => {
        const lbl = document.createElement("div");
        lbl.style.fontSize = "10px";
        lbl.style.fontWeight = "700";
        lbl.style.color = "#818cf8";
        lbl.textContent = f.label;
        drawer.appendChild(lbl);

        const ta = document.createElement("textarea");
        ta.className = "mmx-textarea";
        ta.value = builderState[f.key] || "";
        ta.oninput = () => {
          builderState[f.key] = ta.value;
          syncState();
          if (f.key === "imd" && promptWidget) promptWidget.value = ta.value;
        };
        drawer.appendChild(ta);
      });
    }
  };

  // Render RefMods Panel
  const renderRefmods = () => {
    refmodPanel.innerHTML = "";

    const header = document.createElement("div");
    header.className = "mmx-refmod-header";
    header.innerHTML = `<span>RefMod Conditioners (${timelineState.refmods.length}/8)</span>`;

    const addBtn = document.createElement("button");
    addBtn.className = "mmx-action-btn primary";
    addBtn.textContent = "➕ Add RefMod Slot";
    addBtn.onclick = () => {
      if (timelineState.refmods.length >= 8) {
        alert("Maximum of 8 RefMod slots supported.");
        return;
      }
      const nextSlot = timelineState.refmods.length + 1;
      timelineState.refmods.push({
        slot: nextSlot,
        name: "",
        strength: 1.0,
        enabled: true,
        description: "",
      });
      syncState();
      renderRefmods();
    };
    header.appendChild(addBtn);
    refmodPanel.appendChild(header);

    const note = document.createElement("div");
    note.className = "mmx-refmod-note";
    note.innerHTML = "💡 Reference <code>&lt;refmod_1&gt;</code> through <code>&lt;refmod_8&gt;</code> in your prompts to anchor character identities, styles, or specific motions.";
    refmodPanel.appendChild(note);

    const list = document.createElement("div");
    list.className = "mmx-refmod-list";

    if (timelineState.refmods.length === 0) {
      const empty = document.createElement("div");
      empty.className = "mmx-track-empty-notice";
      empty.style.height = "auto";
      empty.style.padding = "16px";
      empty.textContent = "No RefMod conditioners configured. Click [+ Add RefMod Slot] above to add character or style anchors.";
      list.appendChild(empty);
    } else {
      timelineState.refmods.forEach((rm, idx) => {
        const row = document.createElement("div");
        row.className = "mmx-refmod-row";

        const badge = document.createElement("span");
        badge.className = "mmx-refmod-slot-badge";
        badge.textContent = `<refmod_${rm.slot || idx + 1}>`;
        row.appendChild(badge);

        const nameInput = document.createElement("input");
        nameInput.className = "mmx-refmod-input";
        nameInput.placeholder = "RefMod safetensors name or tag (e.g. hero_face)";
        nameInput.value = rm.name || "";
        nameInput.oninput = () => {
          rm.name = nameInput.value;
          syncState();
        };
        row.appendChild(nameInput);

        const sliderGroup = document.createElement("div");
        sliderGroup.className = "mmx-refmod-slider-group";

        const slider = document.createElement("input");
        slider.type = "range";
        slider.className = "mmx-refmod-slider";
        slider.min = "0.0";
        slider.max = "1.0";
        slider.step = "0.05";
        slider.value = rm.strength ?? 1.0;

        const valSpan = document.createElement("span");
        valSpan.className = "mmx-refmod-val";
        valSpan.textContent = Number(slider.value).toFixed(2);

        slider.oninput = () => {
          rm.strength = parseFloat(slider.value);
          valSpan.textContent = rm.strength.toFixed(2);
          syncState();
        };

        sliderGroup.appendChild(slider);
        sliderGroup.appendChild(valSpan);
        row.appendChild(sliderGroup);

        const enableCheck = document.createElement("input");
        enableCheck.type = "checkbox";
        enableCheck.checked = rm.enabled !== false;
        enableCheck.title = "Enable / Disable this RefMod";
        enableCheck.onchange = () => {
          rm.enabled = enableCheck.checked;
          syncState();
        };
        row.appendChild(enableCheck);

        const delBtn = document.createElement("button");
        delBtn.className = "mmx-action-btn";
        delBtn.innerHTML = "✕";
        delBtn.title = "Delete RefMod slot";
        delBtn.onclick = () => {
          timelineState.refmods.splice(idx, 1);
          timelineState.refmods.forEach((r, i) => {
            r.slot = i + 1;
          });
          syncState();
          renderRefmods();
        };
        row.appendChild(delBtn);

        list.appendChild(row);
      });
    }

    refmodPanel.appendChild(list);
  };

  // Waveform rendering helper
  function drawWaveform(canvas) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#38bdf8";
    const bars = 25;
    for (let i = 0; i < bars; i++) {
      const h = 5 + Math.random() * 28;
      ctx.fillRect(i * 5 + 2, (canvas.height - h) / 2, 3, h);
    }
  }

  // Color grading modal helper
  function openColorEditor(clip) {
    const backdrop = document.createElement("div");
    backdrop.className = "mmx-modal-backdrop";

    const panel = document.createElement("div");
    panel.className = "mmx-modal-panel";
    panel.style.maxWidth = "420px";

    panel.innerHTML = `
      <div class="mmx-modal-header">
        <span class="mmx-modal-title">Color Adjustment — ${clip.name}</span>
        <button class="mmx-action-btn" id="mmx-modal-close">✕</button>
      </div>
      <div class="mmx-modal-body">
        <label style="font-size:11px;display:flex;justify-content:space-between;">
          Saturation: <span id="sat-val">${clip.color_sat || 1.0}</span>
        </label>
        <input type="range" id="sat-slider" min="0.5" max="1.5" step="0.05" value="${clip.color_sat || 1.0}" />
        <label style="font-size:11px;display:flex;justify-content:space-between;">
          Contrast: <span id="con-val">${clip.color_con || 1.0}</span>
        </label>
        <input type="range" id="con-slider" min="0.5" max="1.5" step="0.05" value="${clip.color_con || 1.0}" />
        <label style="font-size:11px;display:flex;justify-content:space-between;">
          Brightness: <span id="bri-val">${clip.color_bri || 1.0}</span>
        </label>
        <input type="range" id="bri-slider" min="0.5" max="1.5" step="0.05" value="${clip.color_bri || 1.0}" />
      </div>
      <div class="mmx-modal-footer">
        <button class="mmx-action-btn primary" id="mmx-modal-save">Apply</button>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.appendChild(panel);

    const close = () => {
      if (document.body.contains(backdrop)) {
        document.body.removeChild(backdrop);
      }
    };
    panel.querySelector("#mmx-modal-close").onclick = close;
    panel.querySelector("#sat-slider").oninput = (e) => {
      panel.querySelector("#sat-val").textContent = e.target.value;
    };
    panel.querySelector("#con-slider").oninput = (e) => {
      panel.querySelector("#con-val").textContent = e.target.value;
    };
    panel.querySelector("#bri-slider").oninput = (e) => {
      panel.querySelector("#bri-val").textContent = e.target.value;
    };
    panel.querySelector("#mmx-modal-save").onclick = () => {
      clip.color_sat = parseFloat(panel.querySelector("#sat-slider").value);
      clip.color_con = parseFloat(panel.querySelector("#con-slider").value);
      clip.color_bri = parseFloat(panel.querySelector("#bri-slider").value);
      syncState();
      close();
    };
  }

  // Initial renders
  renderTracks();
  renderPromptDrawer();
  renderRefmods();

  // Attach DOM Widget to ComfyUI node with explicit size computation (single call)
  const domWidget = node.addDOMWidget("master_director_ui", "custom_ui", root, {
    serialize: false,
    hideOnZoom: false,
  });

  if (domWidget) {
    domWidget.computeSize = function (width) {
      return [width || 920, 360];
    };
  }

  // Move domWidget to the very TOP of node.widgets (index 0) so the Timeline is at the top of the node!
  if (node.widgets && domWidget) {
    const domIdx = node.widgets.indexOf(domWidget);
    if (domIdx > 0) {
      node.widgets.splice(domIdx, 1);
      node.widgets.unshift(domWidget);
    }
  }

  // Apply initial tab display
  switchTab(activeTab);

  // Refresh callback when node configuration or graph is reloaded
  node.__mmxDirectorRefresh = () => {
    hideWidget(timelineWidget);
    hideWidget(builderWidget);
    hideWidget(promptWidget);
    loadState();
    renderTracks();
    renderPromptDrawer();
    renderRefmods();
    switchTab(activeTab);
  };
}

app.registerExtension({
  name: "ComfyUI.MiniMaxH3MasterDirector",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "MiniMaxH3MasterDirector") return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      if (onNodeCreated) onNodeCreated.apply(this, arguments);
      mountDirectorUI(this);
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (info) {
      if (onConfigure) onConfigure.apply(this, arguments);

      // Protect against any array-shift during deserialization
      if (info && this.widgets) {
        const named = info.widgets_values_named || {};
        const values = Array.isArray(info.widgets_values) ? info.widgets_values : [];
        const offset = (values.length > 0 && values[0] === null) ? 1 : 0;

        const standardOrder = [
          "mode", "execution_mode", "width", "height", "duration", "frame_rate",
          "prompt", "prompt_mode", "run_mode", "continuity_mode", "context_length",
          "steps", "cfg", "sampler", "scheduler", "shift_video", "shift_audio", "seed",
          "control_after_generate", "timeline_data", "builder_state"
        ];

        standardOrder.forEach((name, idx) => {
          const w = this.widgets.find((x) => x.name === name);
          if (!w) return;

          if (named[name] !== undefined) {
            w.value = named[name];
          } else if (values[idx + offset] !== undefined) {
            w.value = values[idx + offset];
          }
        });
      }

      if (this.__mmxDirectorRefresh) {
        this.__mmxDirectorRefresh();
      } else {
        mountDirectorUI(this);
      }
    };
  },

  nodeCreated(node) {
    if (node.comfyClass === "MiniMaxH3MasterDirector" || node.type === "MiniMaxH3MasterDirector") {
      mountDirectorUI(node);
    }
  },

  loadedGraphNode(node) {
    if (node.comfyClass === "MiniMaxH3MasterDirector" || node.type === "MiniMaxH3MasterDirector") {
      if (node.widgets && node.widgets_values_named) {
        for (const [name, val] of Object.entries(node.widgets_values_named)) {
          const w = node.widgets.find((x) => x.name === name);
          if (w) w.value = val;
        }
      }
      if (node.__mmxDirectorRefresh) {
        node.__mmxDirectorRefresh();
      } else {
        mountDirectorUI(node);
      }
    }
  },
});
