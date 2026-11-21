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

// Calibrated tone curve (core/look.py CURVE_POINTS): one lookup table per
// channel, outputs for evenly spaced inputs 0..1, applied after the sliders.
export const CURVE_POINTS = 33;
export function curveIsIdentity(curve) {
  return !Array.isArray(curve) || curve.every(ch => ch.every((v, i) => Math.abs(v - i/(CURVE_POINTS-1)) < 1e-4));
}
export function lookIsNeutral(look) {
  return !look || (curveIsIdentity(look.curve) && Object.entries(LOOK_NEUTRAL).every(([k,n])=>Math.abs(Number(look[k] ?? n)-n)<1e-6));
}
const sampleCurve = (table, x) => {
  const pos = Math.max(0, Math.min(1, x)) * (CURVE_POINTS-1), lo = Math.min(CURVE_POINTS-2, Math.floor(pos)), f = pos - lo;
  return table[lo] + (table[lo+1] - table[lo]) * f;
};

// Fit the calibrated tone curve from a generated take: per channel, map the
// take's start tones onto the previous clip's end tones (histogram matching
// at TONE_QUANTILES), on top of the curve that take used. Darks, mids and
// whites are matched separately, so a sleeve that stays whiter is corrected
// even when the averages already agree.
export function fitToneCurve(usedCurve, startTones, targetTones) {
  return [0, 1, 2].map(c => {
    const xs = [], ys = [];
    for (let j = 0; j < startTones[c].length; j++) {
      const x = startTones[c][j], y = targetTones[c][j];
      if (xs.length && x <= xs[xs.length-1] + 1e-4) { ys[ys.length-1] = Math.max(ys[ys.length-1], y); continue; }
      xs.push(x); ys.push(y);
    }
    const correct = x => {
      if (!xs.length) return x;
      // Outside the measured range keep the end offsets (slope 1).
      if (x <= xs[0]) return ys[0] + (x - xs[0]);
      if (x >= xs[xs.length-1]) return ys[ys.length-1] + (x - xs[xs.length-1]);
      let k = 1; while (xs[k] < x) k++;
      return ys[k-1] + (ys[k] - ys[k-1]) * (x - xs[k-1]) / (xs[k] - xs[k-1]);
    };
    const used = Array.isArray(usedCurve) ? usedCurve[c] : null;
    let top = 0;
    return Array.from({length: CURVE_POINTS}, (_, i) => {
      const x = i/(CURVE_POINTS-1), before = used ? sampleCurve(used, x) : x;
      // A gentle limit keeps one odd take from bending the tail too far.
      const y = Math.max(0, Math.min(1, Math.max(before - .25, Math.min(before + .25, correct(before)))));
      top = Math.max(top, y);
      return Math.round(top * 10000) / 10000;
    });
  });
}

export function applyLookPixels(data, look) {
  if (lookIsNeutral(look)) return data;
  const v = {...LOOK_NEUTRAL, ...look};
  const curve = curveIsIdentity(v.curve) ? null : v.curve;
  const gain = 2 ** v.exposure, t = v.temperature, g = v.tint;
  const gr = gain*(1+0.1*t)*(1-0.05*g), gg = gain*(1+0.1*g), gb = gain*(1-0.1*t)*(1-0.05*g);
  const c = v.contrast, lift = v.black, s = v.saturation;
  for (let i = 0; i < data.length; i += 4) {
    let r = data[i]/255*gr, gn = data[i+1]/255*gg, b = data[i+2]/255*gb;
    r = (r-.5)*c+.5; gn = (gn-.5)*c+.5; b = (b-.5)*c+.5;
    r = lift+r*(1-lift); gn = lift+gn*(1-lift); b = lift+b*(1-lift);
    const l = .299*r+.587*gn+.114*b;
    r = l+(r-l)*s; gn = l+(gn-l)*s; b = l+(b-l)*s;
    r = Math.max(0,Math.min(1,r)); gn = Math.max(0,Math.min(1,gn)); b = Math.max(0,Math.min(1,b));
    if (curve) { r = sampleCurve(curve[0], r); gn = sampleCurve(curve[1], gn); b = sampleCurve(curve[2], b); }
    data[i] = r*255; data[i+1] = gn*255; data[i+2] = b*255;
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

// Plain-words summary of a tone curve: how far it moves the darks, mids and
// whites (in % of full brightness) and the colour shift in the whites.
export function curveSummary(curve) {
  const at = x => [0, 1, 2].map(c => sampleCurve(curve[c], x) - x);
  const fmt = v => `${v > 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;
  const cls = v => Math.abs(v) < .005 ? "" : v > 0 ? "up" : "down";
  const parts = [["Darks", .15], ["Mids", .5], ["Whites", .85]].map(([label, x]) => {
    const d = at(x), luma = .299*d[0] + .587*d[1] + .114*d[2];
    return [label, fmt(luma), cls(luma)];
  });
  const w = at(.85), shift = (w[0] - w[2]);
  if (Math.abs(shift) >= .005) parts.push(["Whites", shift > 0 ? `warmer ${(Math.abs(shift)*100).toFixed(1)}%` : `cooler ${(Math.abs(shift)*100).toFixed(1)}%`, ""]);
  return parts;
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

// Decoded frames and compare positions survive the editor being rebuilt (the
// inspector redraws on many edits), so a redraw shows the same picture, zoom
// and region at once instead of "Loading frame…" and a reset view.
const pixelCache = new Map(), pixelReady = new Map(), savedViews = new Map();
function cachedPixels(url) {
  if (!pixelCache.has(url)) {
    if (pixelCache.size > 24) { const old = pixelCache.keys().next().value; pixelCache.delete(old); pixelReady.delete(old); }
    pixelCache.set(url, imagePixels(url).then(p => { pixelReady.set(url, p); return p; }, e => { pixelCache.delete(url); throw e; }));
  }
  return pixelCache.get(url);
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
 *        compareOriginal: readouts compare the adjusted frame with the unadjusted one,
 *        generatedUrl / generatedLabel / generatedNote: adds a third pane with that real frame (for example
 *        this clip's first frame as generated) next to the before image and the preview,
 *        viewKey: keeps the compare zoom and region across rebuilds of the same editor}
 * The returned element has .actions (a row above the sliders, hidden until used) and .setLook(look).
 */
export function createLookEditor(opts) {
  const look = {...LOOK_NEUTRAL, ...(opts.look || {})};
  const root = document.createElement("div"); root.className = "mmx-look";
  const stage = document.createElement("div"); stage.className = "mmx-look-stage";
  const canvas = document.createElement("canvas"); canvas.className = "mmx-look-canvas";
  // Compare view: the SAME zoomed region from every image side by side: the
  // before image, the adjusted preview and (when given) the real generated
  // frame. Drag to move the region; the wheel or the zoom box zooms freely.
  const view = opts.viewKey && savedViews.get(opts.viewKey) || {x: .5, y: .5, zoom: 1};
  if (opts.viewKey) savedViews.set(opts.viewKey, view);
  const panes = opts.generatedUrl ? 3 : 2;
  const ZOOM_MIN = 1, ZOOM_MAX = 64;
  const zoomBar = document.createElement("div"); zoomBar.className = "mmx-look-zoom";
  const zoomOut = document.createElement("button"); zoomOut.type = "button"; zoomOut.textContent = "−"; zoomOut.title = "Zoom out";
  const zoomBox = document.createElement("input"); zoomBox.type = "number"; zoomBox.min = String(ZOOM_MIN); zoomBox.step = "0.25";
  zoomBox.className = "mmx-look-zoom-box"; zoomBox.title = "Zoom (type a value, or scroll over the picture)"; zoomBox.setAttribute("aria-label", "Zoom");
  const zoomUnit = document.createElement("span"); zoomUnit.textContent = "×";
  const zoomIn = document.createElement("button"); zoomIn.type = "button"; zoomIn.textContent = "+"; zoomIn.title = "Zoom in";
  zoomBar.append(zoomOut, zoomBox, zoomUnit, zoomIn);
  for (const el of [zoomBar, zoomBox]) for (const ev of ["pointerdown", "mousedown"]) el.addEventListener(ev, e => e.stopPropagation());
  const setZoom = (z, focus) => {
    const next = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Number(z) || ZOOM_MIN));
    if (focus) {
      // Keep the point under the cursor in place.
      view.x = focus.px - (focus.u - .5) * (1 / panes / next);
      view.y = focus.py - (focus.v - .5) * (1 / next);
    }
    view.zoom = Math.round(next * 100) / 100; render();
  };
  zoomOut.onclick = e => { e.stopPropagation(); setZoom(view.zoom / 1.25); };
  zoomIn.onclick = e => { e.stopPropagation(); setZoom(view.zoom * 1.25); };
  zoomBox.onchange = () => setZoom(zoomBox.value);
  zoomBox.addEventListener("wheel", e => { e.preventDefault(); setZoom(view.zoom * (e.deltaY < 0 ? 1.1 : 1/1.1)); }, {passive: false});
  const labels = document.createElement("div"); labels.className = "mmx-look-labels";
  for (const text of [opts.beforeLabel || "Before", opts.afterLabel || "After", ...(panes === 3 ? [opts.generatedLabel || "Generated"] : [])]) {
    const span = document.createElement("span"); span.textContent = text; labels.append(span);
  }
  labels.style.gridTemplateColumns = `repeat(${panes}, 1fr)`;
  const empty = document.createElement("div"); empty.className = "mmx-look-empty"; empty.textContent = "Loading frame…";
  const notice = document.createElement("div"); notice.className = "mmx-look-notice"; notice.hidden = true;
  stage.classList.add("mmx-look-missing");
  stage.append(canvas, labels, zoomBar, empty, notice);
  stage.title = "Drag to move the compared region; scroll to zoom";
  if (opts.generatedNote) stage.title = opts.generatedNote + " Drag to move the region; scroll to zoom.";
  const readout = document.createElement("div"); readout.className = "mmx-look-readout";
  const controls = document.createElement("div"); controls.className = "mmx-look-controls";
  // Optional action row (for example Auto calibrate) right above the sliders.
  const actions = document.createElement("div"); actions.className = "mmx-look-actions"; actions.hidden = true;
  root.append(stage, readout, actions, controls);
  root.actions = actions;

  let original = null, anchor = null, generated = null, generatedState = opts.generatedUrl ? "loading" : "none";
  const render = () => {
    zoomBox.value = String(view.zoom);
    if (!original) return;
    const ctx = canvas.getContext("2d");
    const w = original.width, h = original.height;
    notice.hidden = panes < 3 || generatedState === "ready";
    notice.textContent = generatedState === "loading" ? "Loading the generated frame…" : "Generate this clip to see its real first frame.";
    const after = new ImageData(new Uint8ClampedArray(original.data), w, h);
    applyLookPixels(after.data, look);
    sources.after.getContext("2d").putImageData(after, 0, 0);
    let real = null;
    if (panes === 3 && generated) {
      const t = document.createElement("canvas"); t.width = generated.width; t.height = generated.height;
      t.getContext("2d").putImageData(generated, 0, 0);
      const g = sources.generated.getContext("2d", {willReadFrequently: true});
      g.imageSmoothingQuality = "high"; g.clearRect(0, 0, w, h); g.drawImage(t, 0, 0, w, h);
      real = g.getImageData(0, 0, w, h);
    }
    sources.before.getContext("2d").putImageData(original, 0, 0);
    // The same region of the frame in every pane, zoomed.
    const pw = w / panes, cw = pw / view.zoom, ch = h / view.zoom;
    const sx = Math.min(w - cw, Math.max(0, view.x * w - cw / 2)), sy = Math.min(h - ch, Math.max(0, view.y * h - ch / 2));
    view.x = (sx + cw / 2) / w; view.y = (sy + ch / 2) / h;
    ctx.imageSmoothingEnabled = view.zoom < 6; ctx.imageSmoothingQuality = "high";
    ctx.fillStyle = "#11161b"; ctx.fillRect(0, 0, w, h);
    const order = [sources.before, sources.after, ...(panes === 3 ? [real ? sources.generated : null] : [])];
    order.forEach((src, i) => { if (src) ctx.drawImage(src, sx, sy, cw, ch, Math.round(i * pw), 0, Math.round(pw), h); });
    ctx.fillStyle = "rgba(255,255,255,.9)";
    for (let i = 1; i < panes; i++) ctx.fillRect(Math.round(i * pw) - 1, 0, 2, h);
    const delta = (value, base, digits = 1, pct = false) => {
      if (base == null) return "";
      const d = pct ? (value/base-1)*100 : value - base;
      return ` <em class="${Math.abs(d) < (pct ? 1 : .5) ? "" : d > 0 ? "up" : "down"}">${d > 0 ? "+" : ""}${d.toFixed(digits)}${pct ? "%" : ""}</em>`;
    };
    const line = (title, st, a) =>
      `<div class="mmx-look-readout-line">${title ? `<i>${title}</i>` : ""}` +
      `<span title="Average brightness (0-255)">Brightness <b>${st.brightness.toFixed(1)}</b>${delta(st.brightness, a?.brightness, 1, true)}</span>` +
      `<span title="Share of pixels darker than 16/255">Near-black <b>${st.dark.toFixed(1)}%</b>${delta(st.dark, a?.dark)}</span>` +
      `<span title="Red vs green balance">Warm <b>${st.warm.toFixed(3)}</b>${delta(st.warm, a?.warm, 1, true)}</span>` +
      `<span title="Blue vs green balance">Cool <b>${st.cool.toFixed(3)}</b>${delta(st.cool, a?.cool, 1, true)}</span></div>`;
    const base = opts.compareOriginal || panes === 3 ? frameStats(original.data) : anchor ? frameStats(anchor.data) : null;
    if (panes === 3) {
      readout.innerHTML = line(opts.afterLabel || "Preview", frameStats(after.data), base) +
        (real ? line(opts.generatedLabel || "Generated", frameStats(real.data), base) : "") +
        `<small>Each vs. ${opts.beforeLabel ? opts.beforeLabel.toLowerCase() : "the before image"}</small>`;
    } else {
      readout.innerHTML = line("", frameStats(after.data), base) + (base ? `<small>${opts.anchorLabel || "Change vs. the chain's first clip"}</small>` : "");
    }
  };
  const sources = {before: document.createElement("canvas"), after: document.createElement("canvas"), generated: document.createElement("canvas")};
  let drag = null;
  canvas.addEventListener("pointerdown", event => { drag = {x: event.clientX, y: event.clientY, vx: view.x, vy: view.y}; canvas.setPointerCapture(event.pointerId); });
  canvas.addEventListener("pointermove", event => {
    if (!drag || !original) return;
    const rect = canvas.getBoundingClientRect();
    // Moving across one pane moves the region by its own width.
    view.x = drag.vx - (event.clientX - drag.x) / (rect.width / panes) / view.zoom / panes;
    view.y = drag.vy - (event.clientY - drag.y) / rect.height / view.zoom;
    render();
  });
  const endDrag = () => { drag = null; };
  canvas.addEventListener("pointerup", endDrag); canvas.addEventListener("pointercancel", endDrag);
  canvas.addEventListener("wheel", event => {
    if (!original) return;
    event.preventDefault();
    const rect = canvas.getBoundingClientRect(), paneW = rect.width / panes;
    const u = ((event.clientX - rect.left) % paneW) / paneW, v = (event.clientY - rect.top) / rect.height;
    const px = view.x + (u - .5) * (1 / panes / view.zoom), py = view.y + (v - .5) * (1 / view.zoom);
    setZoom(view.zoom * (event.deltaY < 0 ? 1.15 : 1/1.15), {u, v, px, py});
  }, {passive: false});

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
  // The calibrated tone curve, shown as one row in plain words (how much the
  // darks, mids and whites are moved, and any colour shift) with its own reset.
  const curveRow = document.createElement("div"); curveRow.className = "mmx-look-row mmx-look-curve-row changed";
  const curveName = document.createElement("span"); curveName.textContent = "Tone curve";
  const curveText = document.createElement("div"); curveText.className = "mmx-look-curve-text";
  const curveReset = document.createElement("button"); curveReset.type = "button"; curveReset.className = "mmx-look-reset"; curveReset.textContent = "↺";
  curveReset.title = "Remove the calibrated tone curve";
  curveRow.title = "Set by Auto calibrate from the last take. Applied after the sliders: it moves the darks, mids and whites separately so this clip starts the way the previous clip ended.";
  curveRow.append(curveName, curveText, curveReset);
  const drawCurve = () => {
    const on = !curveIsIdentity(look.curve);
    curveRow.hidden = !on; if (!on) return;
    curveText.replaceChildren(...curveSummary(look.curve).map(([label, text, cls]) => {
      const el = document.createElement("span"); el.className = cls; el.innerHTML = `${label} <b>${text}</b>`; return el;
    }));
  };
  curveReset.onclick = () => { delete look.curve; drawCurve(); render(); opts.onChange?.({...look}); };
  controls.append(curveRow); drawCurve();
  const resetAll = document.createElement("button"); resetAll.type = "button"; resetAll.className = "mmx-look-reset-all";
  resetAll.textContent = "Reset all";
  resetAll.onclick = () => { delete look.curve; drawCurve(); for (const key of Object.keys(LOOK_NEUTRAL)) { look[key] = LOOK_NEUTRAL[key]; } for (const [key, set] of Object.entries(inputs)) set(LOOK_NEUTRAL[key], false); opts.onChange?.({...look}); };
  controls.append(resetAll);
  // Set every slider (and the curve) in place: the preview, its zoom and drag
  // position stay as they are, so the change is visible right away. Commits once.
  root.setLook = next => {
    const target = {...LOOK_NEUTRAL, ...(next || {})};
    if (curveIsIdentity(target.curve)) delete look.curve; else look.curve = target.curve.map(ch => [...ch]);
    drawCurve();
    for (const [key, set] of Object.entries(inputs)) set(target[key], false);
    render(); opts.onChange?.({...look});
  };

  const show = pixels => {
    original = pixels; canvas.width = pixels.width; canvas.height = pixels.height;
    for (const c of Object.values(sources)) { c.width = pixels.width; c.height = pixels.height; }
    empty.hidden = true; stage.classList.remove("mmx-look-missing"); render();
  };
  if (opts.imageUrl) {
    if (opts.anchorUrl && pixelReady.has(opts.anchorUrl)) anchor = pixelReady.get(opts.anchorUrl);
    if (opts.generatedUrl && pixelReady.has(opts.generatedUrl)) { generated = pixelReady.get(opts.generatedUrl); generatedState = "ready"; }
    if (pixelReady.has(opts.imageUrl)) show(pixelReady.get(opts.imageUrl));
    else cachedPixels(opts.imageUrl).then(show).catch(() => { empty.textContent = opts.emptyText || "Frame not available yet."; stage.classList.add("mmx-look-missing"); });
    if (opts.anchorUrl && !anchor) cachedPixels(opts.anchorUrl).then(pixels => { anchor = pixels; render(); }).catch(() => {});
    if (opts.generatedUrl && !generated) cachedPixels(opts.generatedUrl).then(pixels => { generated = pixels; generatedState = "ready"; render(); }).catch(() => { generatedState = "missing"; render(); });
  } else { empty.textContent = opts.emptyText || "No frame to preview."; stage.classList.add("mmx-look-missing"); }
  render();
  return root;
}
