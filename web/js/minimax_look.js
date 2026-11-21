// Live look editor for continuity frames.
// applyLookPixels mirrors core/look.py apply_look exactly, so the preview shows
// what generation receives.

export const LOOK_NEUTRAL = {exposure:0, contrast:1, black:0, saturation:1, temperature:0, tint:0};
export const LOOK_CONTROLS = [
  ["exposure","Brightness",-2,2,0.05,v=>`${v>0?"+":""}${v.toFixed(2)} EV`],
  ["contrast","Contrast",0.5,1.5,0.01,v=>`${Math.round(v*100)}%`],
  ["black","Black level",-0.1,0.1,0.005,v=>`${v>0?"+":""}${(v*100).toFixed(1)}`],
  ["saturation","Saturation",0,2,0.01,v=>`${Math.round(v*100)}%`],
  ["temperature","Temperature",-1,1,0.02,v=>v===0?"0":`${v>0?"warm":"cool"} ${Math.abs(v).toFixed(2)}`],
  ["tint","Tint",-1,1,0.02,v=>v===0?"0":`${v>0?"green":"magenta"} ${Math.abs(v).toFixed(2)}`],
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

// Browser estimate of what "Automatic join fix" and "Hold look" do downstream,
// steering the frame back toward the chain start (anchor). Uses the bounds of
// core/continuity.py anchor_chain_contrast (2% deadband, 10% max) and
// core/look.py hold_target (per-channel gain 0.75..1.33). Returns a summary.
export function steerToAnchor(data, anchor, {contrast = false, hold = false} = {}) {
  if (!anchor || (!contrast && !hold)) return [];
  const moments = px => {
    let R = 0, G = 0, B = 0, L = 0, L2 = 0, n = 0;
    for (let i = 0; i < px.length; i += 16) { const r = px[i], g = px[i+1], b = px[i+2], l = .299*r+.587*g+.114*b; R += r; G += g; B += b; L += l; L2 += l*l; n++; }
    const m = L/n; return {rgb: [R/n, G/n, B/n], std: Math.sqrt(Math.max(0, L2/n - m*m))};
  };
  const a = moments(anchor), steps = [];
  if (contrast) {
    const s = moments(data), ratio = a.std / Math.max(1e-3, s.std);
    let k = Math.abs(ratio - 1) <= .02 ? 1 : ratio > 1 ? ratio - .02 : ratio + .02;
    k = Math.min(1.1, Math.max(.9, k));
    if (Math.abs(k - 1) > 1e-3) {
      const [mr, mg, mb] = s.rgb;
      for (let i = 0; i < data.length; i += 4) { data[i] = mr+(data[i]-mr)*k; data[i+1] = mg+(data[i+1]-mg)*k; data[i+2] = mb+(data[i+2]-mb)*k; }
    }
    steps.push(`Join fix · contrast ×${k.toFixed(2)}`);
  }
  if (hold) {
    const s = moments(data), gain = s.rgb.map((v, c) => Math.min(1.33, Math.max(.75, a.rgb[c] / Math.max(1, v))));
    for (let i = 0; i < data.length; i += 4) { data[i] *= gain[0]; data[i+1] *= gain[1]; data[i+2] *= gain[2]; }
    steps.push(`Hold look · R×${gain[0].toFixed(2)} G×${gain[1].toFixed(2)} B×${gain[2].toFixed(2)}`);
  }
  return steps;
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
 *        steer(): {contrast, hold} read on every render, stepsNote}
 * The returned element has refresh() to redraw after outside settings change.
 */
export function createLookEditor(opts) {
  const look = {...LOOK_NEUTRAL, ...(opts.look || {})};
  const root = document.createElement("div"); root.className = "mmx-look";
  const stage = document.createElement("div"); stage.className = "mmx-look-stage";
  const canvas = document.createElement("canvas"); canvas.className = "mmx-look-canvas";
  const split = document.createElement("input"); split.type = "range"; split.min = "0"; split.max = "100"; split.value = "50";
  split.className = "mmx-look-split"; split.setAttribute("aria-label", "Compare before and after");
  const labels = document.createElement("div"); labels.className = "mmx-look-labels";
  labels.innerHTML = `<span>${opts.beforeLabel || "Before"}</span><span>${opts.afterLabel || "After"}</span>`;
  const empty = document.createElement("div"); empty.className = "mmx-look-empty"; empty.textContent = "Loading frame…";
  stage.classList.add("mmx-look-missing");
  stage.append(canvas, labels, split, empty);
  const readout = document.createElement("div"); readout.className = "mmx-look-readout";
  const steps = document.createElement("div"); steps.className = "mmx-look-steps";
  const controls = document.createElement("div"); controls.className = "mmx-look-controls";
  root.append(stage, steps, readout, controls);

  let original = null, anchor = null;
  const render = () => {
    if (!original) return;
    const ctx = canvas.getContext("2d");
    const after = new ImageData(new Uint8ClampedArray(original.data), original.width, original.height);
    applyLookPixels(after.data, look);
    const steer = opts.steer ? opts.steer() : {};
    const applied = steerToAnchor(after.data, anchor?.data, steer);
    labels.lastElementChild.textContent = opts.afterLabelFor ? opts.afterLabelFor(steer) : (opts.afterLabel || "After");
    if (applied.length) steps.innerHTML = `<span>${applied.join("</span><span>")}</span>${opts.stepsNote ? `<small>${opts.stepsNote}</small>` : ""}`;
    else if (!anchor && Object.values(steer).some(Boolean)) steps.innerHTML = `<small>The join fix and hold preview appear once the chain's first clip is generated.</small>`;
    else steps.innerHTML = "";
    const cut = Math.round(original.width * Number(split.value) / 100);
    ctx.putImageData(original, 0, 0);
    ctx.putImageData(after, 0, 0, cut, 0, original.width - cut, original.height);
    ctx.fillStyle = "rgba(255,255,255,.9)"; ctx.fillRect(Math.max(0, cut - 1), 0, 2, original.height);
    const s = frameStats(after.data);
    const delta = (value, base, digits = 1, pct = false) => {
      if (base == null) return "";
      const d = pct ? (value/base-1)*100 : value - base;
      return ` <em class="${Math.abs(d) < (pct ? 1 : .5) ? "" : d > 0 ? "up" : "down"}">${d > 0 ? "+" : ""}${d.toFixed(digits)}${pct ? "%" : ""}</em>`;
    };
    const a = anchor ? frameStats(anchor.data) : null;
    readout.innerHTML =
      `<span title="Average brightness of the adjusted frame (0-255)">Brightness <b>${s.brightness.toFixed(1)}</b>${delta(s.brightness, a?.brightness, 1, true)}</span>` +
      `<span title="Share of pixels darker than 16/255">Near-black <b>${s.dark.toFixed(1)}%</b>${delta(s.dark, a?.dark)}</span>` +
      `<span title="Red vs green balance">Warm <b>${s.warm.toFixed(3)}</b>${delta(s.warm, a?.warm, 1, true)}</span>` +
      `<span title="Blue vs green balance">Cool <b>${s.cool.toFixed(3)}</b>${delta(s.cool, a?.cool, 1, true)}</span>` +
      (a ? `<small>${opts.anchorLabel || "Change vs. the chain's first clip"}</small>` : "");
  };
  split.oninput = render;

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

  if (opts.imageUrl) {
    imagePixels(opts.imageUrl).then(pixels => {
      original = pixels; canvas.width = pixels.width; canvas.height = pixels.height;
      empty.hidden = true; stage.classList.remove("mmx-look-missing"); render();
    }).catch(() => { empty.textContent = opts.emptyText || "Frame not available yet."; stage.classList.add("mmx-look-missing"); });
    if (opts.anchorUrl) imagePixels(opts.anchorUrl).then(pixels => { anchor = pixels; render(); }).catch(() => {});
  } else { empty.textContent = opts.emptyText || "No frame to preview."; stage.classList.add("mmx-look-missing"); }
  root.refresh = render;
  return root;
}
