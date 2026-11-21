// Live look editor for continuity frames.
// applyLookPixels mirrors core/look.py apply_look exactly, so the preview shows
// what generation receives.

export const LOOK_NEUTRAL = {exposure:0, contrast:1, black:0, saturation:1, temperature:0, tint:0};
export const LOOK_CONTROLS = [
  ["exposure","Brightness",-2,2,0.005,v=>`${v>0?"+":""}${v.toFixed(3)} EV`],
  ["contrast","Contrast",0.5,1.5,0.002,v=>`${(v*100).toFixed(1)}%`],
  ["black","Black level",-0.1,0.1,0.001,v=>`${v>0?"+":""}${(v*100).toFixed(1)}`],
  ["saturation","Saturation",0,2,0.005,v=>`${(v*100).toFixed(1)}%`],
  ["temperature","Temperature",-1,1,0.005,v=>Math.abs(v)<5e-4?"0":`${v>0?"warm":"cool"} ${Math.abs(v).toFixed(3)}`],
  ["tint","Tint",-1,1,0.005,v=>Math.abs(v)<5e-4?"0":`${v>0?"green":"magenta"} ${Math.abs(v).toFixed(3)}`],
];

export function lookIsNeutral(look) {
  return !look || Object.entries(LOOK_NEUTRAL).every(([k,n])=>Math.abs(Number(look[k] ?? n)-n)<1e-6);
}

export function applyLookPixels(data, look) {
  if (lookIsNeutral(look)) return data;
  const v = {...LOOK_NEUTRAL, ...look};
  const gain = 2 ** v.exposure, t = v.temperature, g = v.tint;
  const gr = gain*(1+0.1*t)*(1-0.05*g), gg = gain*(1+0.1*g), gb = gain*(1-0.1*t)*(1-0.05*g);
  const c = v.contrast, lift = v.black, s = v.saturation;
  for (let i = 0; i < data.length; i += 4) {
    let r = data[i]/255*gr, gn = data[i+1]/255*gg, b = data[i+2]/255*gb;
    r = (r-.5)*c+.5; gn = (gn-.5)*c+.5; b = (b-.5)*c+.5;
    r = lift+r*(1-lift); gn = lift+gn*(1-lift); b = lift+b*(1-lift);
    const l = .299*r+.587*gn+.114*b;
    r = l+(r-l)*s; gn = l+(gn-l)*s; b = l+(b-l)*s;
    data[i] = Math.max(0,Math.min(1,r))*255; data[i+1] = Math.max(0,Math.min(1,gn))*255; data[i+2] = Math.max(0,Math.min(1,b))*255;
  }
  return data;
}

// Calibration from a generated clip. ``target`` and ``result`` are
// {rgb:[r,g,b] 0..1, std} from /minimax_director/clip/calibration. Returns the
// look that, applied to the carried tail instead of ``used``, should move the
// next take's result onto the target: per-channel gains are inverted into
// exposure / temperature / tint with this module's grade, contrast from the
// luma spread. Saturation and black level are kept. One step; repeat if needed.
export function calibrateLook(used, target, result, {contrast = true} = {}) {
  const base = {...LOOK_NEUTRAL, ...(used || {})};
  // Contrast pivots around mid-grey, so it also moves the average: solve the
  // channel gains c and the contrast k together so that, after gain then
  // contrast (the order of applyLookPixels), mean and spread both match.
  //   target_i = 0.5 + (c_i * result_i - 0.5) * k
  //   target_std = result_std * lumaGain(c) * k
  let k = 1, c = [1, 1, 1];
  for (let pass = 0; pass < 6; pass++) {
    c = target.rgb.map((v, i) => Math.min(1.6, Math.max(.6, ((v - .5) / k + .5) / Math.max(1e-3, result.rgb[i]))));
    const gain = .299*c[0] + .587*c[1] + .114*c[2];
    if (contrast && result.std > 1e-4) k = Math.min(1.4, Math.max(.7, target.std / (result.std * gain)));
  }
  const rho = c[0] / c[2], t = 10 * (rho - 1) / (rho + 1);
  const m = Math.sqrt(Math.max(1e-6, (1 + .1*t) * (1 - .1*t)));
  const q = c[1] / Math.sqrt(c[0] * c[2]) * m, g = (q - 1) / (.1 + .05*q);
  const e = Math.log2(Math.max(1e-3, c[1] / (1 + .1*g)));
  // Keep calibrated values precise (not snapped to the slider step): a coarse
  // step left takes a few percent off in brightness.
  const clampTo = (key, v) => { const row = LOOK_CONTROLS.find(r => r[0] === key); return Math.min(row[3], Math.max(row[2], Math.round(v * 1000) / 1000)); };
  const next = {...base,
    exposure: clampTo("exposure", base.exposure + e),
    temperature: clampTo("temperature", base.temperature + t),
    tint: clampTo("tint", base.tint + g),
    contrast: clampTo("contrast", base.contrast * k)};
  for (const key of Object.keys(next)) next[key] = Number(next[key].toFixed(4));
  return next;
}

export function lookChanges(from, to) {
  const a = {...LOOK_NEUTRAL, ...(from || {})}, b = {...LOOK_NEUTRAL, ...(to || {})};
  return LOOK_CONTROLS.filter(([key]) => Math.abs(b[key] - a[key]) > 1e-6).map(([key, title, , , , format]) => `${title} ${format(b[key])}`);
}


export function frameStats(data) {
  let lum = 0, dark = 0, R = 0, G = 0, B = 0, n = 0;
  for (let i = 0; i < data.length; i += 16) {
    const r = data[i], g = data[i+1], b = data[i+2], l = .299*r+.587*g+.114*b;
    lum += l; if (l < 16) dark++; R += r; G += g; B += b; n++;
  }
  return {brightness: lum/n, dark: dark/n*100, warm: R/Math.max(1,G), cool: B/Math.max(1,G)};
}

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image(); img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Frame not available"));
    img.src = url;
  });
}

async function imagePixels(url, maxWidth = 560) {
  const img = await loadImage(url);
  const scale = Math.min(1, maxWidth / img.naturalWidth);
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(img.naturalWidth*scale)); canvas.height = Math.max(1, Math.round(img.naturalHeight*scale));
  const ctx = canvas.getContext("2d", {willReadFrequently: true});
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  return ctx.getImageData(0, 0, canvas.width, canvas.height);
}

/**
 * Build a look editor.
 * opts: {imageUrl, emptyText, look, onInput(look), onChange(look), anchorUrl, anchorLabel, beforeLabel, afterLabel,
 *        compareOriginal: readouts compare the adjusted frame with the unadjusted one}
 * The returned element has .actions (a row above the sliders, hidden until used) and .setLook(look).
 */
export function createLookEditor(opts) {
  const look = {...LOOK_NEUTRAL, ...(opts.look || {})};
  const root = document.createElement("div"); root.className = "mmx-look";
  const stage = document.createElement("div"); stage.className = "mmx-look-stage";
  const canvas = document.createElement("canvas"); canvas.className = "mmx-look-canvas";
  // Compare view: the SAME zoomed region from both images side by side (before
  // left, after right). Drag the picture to move the region; 1x/2x/4x zoom.
  const view = {x: .5, y: .5, zoom: 2};
  const zoomBar = document.createElement("div"); zoomBar.className = "mmx-look-zoom";
  for (const z of [1, 2, 4]) {
    const b = document.createElement("button"); b.type = "button"; b.textContent = `${z}×`; b.dataset.zoom = z;
    b.title = z === 1 ? "Whole width of each half" : `Zoom ${z}×`;
    b.onclick = event => { event.stopPropagation(); view.zoom = z; render(); };
    zoomBar.append(b);
  }
  const labels = document.createElement("div"); labels.className = "mmx-look-labels";
  labels.innerHTML = `<span>${opts.beforeLabel || "Before"}</span><span>${opts.afterLabel || "After"}</span>`;
  const empty = document.createElement("div"); empty.className = "mmx-look-empty"; empty.textContent = "Loading frame…";
  stage.classList.add("mmx-look-missing");
  stage.append(canvas, labels, zoomBar, empty);
  stage.title = "Drag to move the compared region";
  const readout = document.createElement("div"); readout.className = "mmx-look-readout";
  const controls = document.createElement("div"); controls.className = "mmx-look-controls";
  // Optional action row (for example Auto calibrate) right above the sliders.
  const actions = document.createElement("div"); actions.className = "mmx-look-actions"; actions.hidden = true;
  root.append(stage, readout, actions, controls);
  root.actions = actions;

  let original = null, anchor = null;
  const render = () => {
    if (!original) return;
    const ctx = canvas.getContext("2d");
    const after = new ImageData(new Uint8ClampedArray(original.data), original.width, original.height);
    applyLookPixels(after.data, look);
    // The same region of the frame twice, zoomed: before left, after right.
    const w = original.width, h = original.height, half = Math.max(1, Math.round(w / 2));
    const cw = half / view.zoom, ch = h / view.zoom;
    const sx = Math.min(w - cw, Math.max(0, view.x * w - cw / 2)), sy = Math.min(h - ch, Math.max(0, view.y * h - ch / 2));
    view.x = (sx + cw / 2) / w; view.y = (sy + ch / 2) / h;
    sources.before.getContext("2d").putImageData(original, 0, 0);
    sources.after.getContext("2d").putImageData(after, 0, 0);
    ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = "high";
    ctx.drawImage(sources.before, sx, sy, cw, ch, 0, 0, half, h);
    ctx.drawImage(sources.after, sx, sy, cw, ch, half, 0, w - half, h);
    ctx.fillStyle = "rgba(255,255,255,.9)"; ctx.fillRect(half - 1, 0, 2, h);
    for (const b of zoomBar.children) b.classList.toggle("active", Number(b.dataset.zoom) === view.zoom);
    const s = frameStats(after.data);
    const delta = (value, base, digits = 1, pct = false) => {
      if (base == null) return "";
      const d = pct ? (value/base-1)*100 : value - base;
      return ` <em class="${Math.abs(d) < (pct ? 1 : .5) ? "" : d > 0 ? "up" : "down"}">${d > 0 ? "+" : ""}${d.toFixed(digits)}${pct ? "%" : ""}</em>`;
    };
    const a = opts.compareOriginal ? frameStats(original.data) : anchor ? frameStats(anchor.data) : null;
    readout.innerHTML =
      `<span title="Average brightness of the adjusted frame (0-255)">Brightness <b>${s.brightness.toFixed(1)}</b>${delta(s.brightness, a?.brightness, 1, true)}</span>` +
      `<span title="Share of pixels darker than 16/255">Near-black <b>${s.dark.toFixed(1)}%</b>${delta(s.dark, a?.dark)}</span>` +
      `<span title="Red vs green balance">Warm <b>${s.warm.toFixed(3)}</b>${delta(s.warm, a?.warm, 1, true)}</span>` +
      `<span title="Blue vs green balance">Cool <b>${s.cool.toFixed(3)}</b>${delta(s.cool, a?.cool, 1, true)}</span>` +
      (a ? `<small>${opts.anchorLabel || "Change vs. the chain's first clip"}</small>` : "");
  };
  const sources = {before: document.createElement("canvas"), after: document.createElement("canvas")};
  let drag = null;
  canvas.addEventListener("pointerdown", event => { drag = {x: event.clientX, y: event.clientY, vx: view.x, vy: view.y}; canvas.setPointerCapture(event.pointerId); });
  canvas.addEventListener("pointermove", event => {
    if (!drag || !original) return;
    const rect = canvas.getBoundingClientRect();
    // Moving across one half of the screen moves the region by its own width.
    view.x = drag.vx - (event.clientX - drag.x) / (rect.width / 2) / view.zoom / 2;
    view.y = drag.vy - (event.clientY - drag.y) / rect.height / view.zoom;
    render();
  });
  const endDrag = () => { drag = null; };
  canvas.addEventListener("pointerup", endDrag); canvas.addEventListener("pointercancel", endDrag);

  const inputs = {};
  for (const [key, title, min, max, step, format] of LOOK_CONTROLS) {
    const row = document.createElement("label"); row.className = "mmx-look-row";
    const name = document.createElement("span"); name.textContent = title;
    const slider = document.createElement("input"); slider.type = "range"; slider.min = min; slider.max = max; slider.step = step;
    slider.value = look[key]; slider.setAttribute("aria-label", title);
    const value = document.createElement("output"); value.textContent = format(Number(look[key]));
    const reset = document.createElement("button"); reset.type = "button"; reset.className = "mmx-look-reset"; reset.textContent = "↺";
    reset.title = `Reset ${title.toLowerCase()}`;
    const set = (amount, commit) => {
      look[key] = Number(amount); slider.value = look[key]; value.textContent = format(look[key]);
      row.classList.toggle("changed", Math.abs(look[key] - LOOK_NEUTRAL[key]) > 1e-6);
      render(); opts.onInput?.({...look}); if (commit) opts.onChange?.({...look});
    };
    slider.oninput = () => set(slider.value, false);
    slider.onchange = () => set(slider.value, true);
    slider.ondblclick = () => set(LOOK_NEUTRAL[key], true);
    reset.onclick = () => set(LOOK_NEUTRAL[key], true);
    row.classList.toggle("changed", Math.abs(look[key] - LOOK_NEUTRAL[key]) > 1e-6);
    row.append(name, slider, value, reset); controls.append(row); inputs[key] = set;
  }
  const resetAll = document.createElement("button"); resetAll.type = "button"; resetAll.className = "mmx-look-reset-all";
  resetAll.textContent = "Reset all";
  resetAll.onclick = () => { for (const key of Object.keys(LOOK_NEUTRAL)) { look[key] = LOOK_NEUTRAL[key]; } for (const [key, set] of Object.entries(inputs)) set(LOOK_NEUTRAL[key], false); opts.onChange?.({...look}); };
  controls.append(resetAll);
  // Set every slider in place: the preview, its zoom and drag position stay
  // as they are, so the change is visible right away. Commits once.
  root.setLook = next => {
    const target = {...LOOK_NEUTRAL, ...(next || {})};
    for (const [key, set] of Object.entries(inputs)) set(target[key], false);
    opts.onChange?.({...look});
  };

  if (opts.imageUrl) {
    imagePixels(opts.imageUrl).then(pixels => {
      original = pixels; canvas.width = pixels.width; canvas.height = pixels.height;
      for (const c of Object.values(sources)) { c.width = pixels.width; c.height = pixels.height; }
      empty.hidden = true; stage.classList.remove("mmx-look-missing"); render();
    }).catch(() => { empty.textContent = opts.emptyText || "Frame not available yet."; stage.classList.add("mmx-look-missing"); });
    if (opts.anchorUrl) imagePixels(opts.anchorUrl).then(pixels => { anchor = pixels; render(); }).catch(() => {});
  } else { empty.textContent = opts.emptyText || "No frame to preview."; stage.classList.add("mmx-look-missing"); }
  return root;
}
