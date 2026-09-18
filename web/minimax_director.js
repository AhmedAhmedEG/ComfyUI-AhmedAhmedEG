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

let cssInjected = false;
function injectCSS() {
  if (cssInjected) return;
  cssInjected = true;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  try {
    link.href = new URL("../css/minimax_director.css", import.meta.url).href;
  } catch (e) {
    try {
      link.href = new URL("css/minimax_director.css", import.meta.url).href;
    } catch (e2) {
      link.href = "/extensions/ComfyUI-AhmedAhmedEG/css/minimax_director.css";
    }
  }
  document.head.appendChild(link);
}


function mountDirectorUI(node) {
  if (!node || node.__mmxDirectorMounted) return;
  node.__mmxDirectorMounted = true;

  injectCSS();


      

      

      // Find widget references
      const modeWidget = node.widgets.find((w) => w.name === "mode");
      const durationWidget = node.widgets.find((w) => w.name === "duration");
      const promptWidget = node.widgets.find((w) => w.name === "prompt");
      const timelineWidget = node.widgets.find((w) => w.name === "timeline_data");
      const builderWidget = node.widgets.find((w) => w.name === "builder_state");

      // Hide raw serialized widgets
      if (timelineWidget) timelineWidget.type = "hidden";
      if (builderWidget) builderWidget.type = "hidden";

      // Parse current state or initialize
      let timelineState = {
        version: 1,
        items: [],
        clips: [{ id: "clip_1", name: "Shot 1", duration: 5.0, validated: false, prompt: "" }],
        refmods: [],
      };

      try {
        if (timelineWidget && timelineWidget.value) {
          const parsed = JSON.parse(timelineWidget.value);
          if (parsed && typeof parsed === "object") timelineState = { ...timelineState, ...parsed };
        }
      } catch (e) {}

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

      try {
        if (builderWidget && builderWidget.value) {
          const parsed = JSON.parse(builderWidget.value);
          if (parsed && typeof parsed === "object") builderState = { ...builderState, ...parsed };
        }
      } catch (e) {}

      const syncState = () => {
        if (timelineWidget) timelineWidget.value = JSON.stringify(timelineState);
        if (builderWidget) builderWidget.value = JSON.stringify(builderState);
      };

      // Create modern timeline root element
      const root = document.createElement("div");
      root.className = "mmx-director-root";

      // 1. Toolbar
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

      // Action buttons: Export Project, Import Project, Clear
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
          syncState();
          renderTracks();
          renderPromptDrawer();
        }
      };

      actionGroup.appendChild(exportBtn);
      actionGroup.appendChild(importBtn);
      actionGroup.appendChild(clearBtn);
      toolbar.appendChild(actionGroup);
      root.appendChild(toolbar);

      // 2. Timeline Tracks Container
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

      // Sequence / Clips Track
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

      // Render Tracks helper
      const renderTracks = () => {
        visualItems.innerHTML = "";
        audioItems.innerHTML = "";
        clipItems.innerHTML = "";

        let imgIndex = 1;
        let vidIndex = 1;
        let audIndex = 1;

        // Render media items
        timelineState.items.forEach((item, idx) => {
          if (item.type === "image" || item.type === "video") {
            const tile = document.createElement("div");
            tile.className = "mmx-tile";

            const badge = document.createElement("div");
            badge.className = "mmx-tile-badge";
            badge.textContent = item.type === "image" ? `Picture ${imgIndex++}` : `Video ${vidIndex++}`;
            tile.appendChild(badge);

            if (item.type === "video") {
              const streamPills = document.createElement("div");
              streamPills.className = "mmx-tile-stream-pills";
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
              tile.appendChild(streamPills);
            }

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

      // 3. Prompt Drawer
      const drawer = document.createElement("div");
      drawer.className = "mmx-drawer";
      root.appendChild(drawer);

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
            let vidC = timelineState.items.filter((i) => i.type === "video").length;
            let audC = timelineState.items.filter((i) => i.type === "audio").length;

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
            } else {
              builderState.imd = (builderState.imd || "") + tag;
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
          // Keyframe modes
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
              Saturation: <span id="sat-val">1.0</span>
            </label>
            <input type="range" id="sat-slider" min="0.5" max="1.5" step="0.05" value="${clip.color_sat || 1.0}" />
            <label style="font-size:11px;display:flex;justify-content:space-between;">
              Contrast: <span id="con-val">1.0</span>
            </label>
            <input type="range" id="con-slider" min="0.5" max="1.5" step="0.05" value="${clip.color_con || 1.0}" />
            <label style="font-size:11px;display:flex;justify-content:space-between;">
              Brightness: <span id="bri-val">1.0</span>
            </label>
            <input type="range" id="bri-slider" min="0.5" max="1.5" step="0.05" value="${clip.color_bri || 1.0}" />
          </div>
          <div class="mmx-modal-footer">
            <button class="mmx-action-btn primary" id="mmx-modal-save">Apply</button>
          </div>
        `;

        document.body.appendChild(backdrop);
        backdrop.appendChild(panel);

        const close = () => document.body.removeChild(backdrop);
        panel.querySelector("#mmx-modal-close").onclick = close;
        panel.querySelector("#mmx-modal-save").onclick = () => {
          clip.color_sat = parseFloat(panel.querySelector("#sat-slider").value);
          clip.color_con = parseFloat(panel.querySelector("#con-slider").value);
          clip.color_bri = parseFloat(panel.querySelector("#bri-slider").value);
          syncState();
          close();
        };
      }

      // Initial render
      renderTracks();
      renderPromptDrawer();

      // Attach DOM Widget to ComfyUI node
      node.addDOMWidget("master_director_ui", "custom_ui", root, {
        serialize: false,
        hideOnZoom: false,
      });

      

  // Attach DOM Widget to ComfyUI node with explicit size computation
  const domWidget = node.addDOMWidget("master_director_ui", "custom_ui", root, {
    serialize: false,
    hideOnZoom: false,
  });

  if (domWidget) {
    domWidget.computeSize = function (width) {
      return [width || 800, 540];
    };
  }

  node.setSize([Math.max(node.size?.[0] || 0, 840), Math.max(node.size?.[1] || 0, 780)]);
  if (node.setDirtyCanvas) node.setDirtyCanvas(true, true);
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
    nodeType.prototype.onConfigure = function () {
      if (onConfigure) onConfigure.apply(this, arguments);
      mountDirectorUI(this);
    };
  },

  nodeCreated(node) {
    if (node.comfyClass === "MiniMaxH3MasterDirector" || node.type === "MiniMaxH3MasterDirector") {
      mountDirectorUI(node);
    }
  },

  loadedGraphNode(node) {
    if (node.comfyClass === "MiniMaxH3MasterDirector" || node.type === "MiniMaxH3MasterDirector") {
      mountDirectorUI(node);
    }
  },
});
