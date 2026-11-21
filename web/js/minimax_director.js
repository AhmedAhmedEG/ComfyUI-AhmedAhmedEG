import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { bindShotDrag } from "./minimax_timeline.js";
import {transferRequest,transferLabel} from "./minimax_transfer.js";
import {createLookEditor,lookIsNeutral,calibrateLook,lookChanges} from "./minimax_look.js";

const CONTINUITY_MODES={independent:"Independent (No Continuity)",motion:"Motion Context (Chained)",carry:"Latent Carry (Pinned)",frame:"Last Frame (Start Image)"};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}

const DIRECTOR_DRAFTS='minimax-director-drafts-v1';
// Browser drafts recover unsaved edits after a page reload. Within one page
// session the workflow itself is authoritative: ComfyUI's undo/redo rebuilds
// every node from an older graph snapshot, and re-applying the newer draft
// then silently cancelled the undo (and desynchronized the undo history).
const sessionMountedDirectors=new Set();
// The server revision this page last saved/opened per project. It is not an
// edit: undoing to a snapshot from before the last save must not make this
// tab's own next save look like a conflict.
const sessionRevisions=new Map();
function readDirectorDraft(state,owner){
  if(!state?.project_id)return null;
  try{
    const row=JSON.parse(localStorage.getItem(DIRECTOR_DRAFTS)||'{}')[`${state.project_id}::${owner}`];
    if(!row || row.updated_at<=Number(state.draft_updated_at || 0))return null;
    const timeline=JSON.parse(row.timeline);
    if(timeline.project_id!==state.project_id || !Array.isArray(timeline.clips))return null;
    return {...row,timeline};
  }catch{return null;}
}
function writeDirectorDraft(project,timeline,builder,updated_at){
  try{
    let drafts=JSON.parse(localStorage.getItem(DIRECTOR_DRAFTS)||'{}');
    if(!drafts || Array.isArray(drafts) || typeof drafts!=='object')drafts={};
    delete drafts[project];drafts[project]={timeline,builder,updated_at};
    const keys=Object.keys(drafts).sort((a,b)=>drafts[a].updated_at-drafts[b].updated_at);
    while(keys.length>1 && (keys.length>16 || JSON.stringify(drafts).length>1000000))delete drafts[keys.shift()];
    localStorage.setItem(DIRECTOR_DRAFTS,JSON.stringify(drafts));
  }catch{/* ComfyUI's workflow state remains available if browser storage is full. */}
}

// Embedded CSS
const embeddedCSS = `
/* Extender hides generation_mode globally; restore only this pack's native row. */
[data-node-id]:has(.mmx-director-root) .lg-node-widget:has(button[data-testid="widget-select-default-trigger"][aria-label="generation_mode"]) { display: grid !important; }
/* Modern, sleek timeline editor styling for MiniMax H3 Master Director */

.mmx-director-root,
.mmx-director-root * {
  box-sizing: border-box;
}

.mmx-director-root {
  color-scheme: dark;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  height: 100%;
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: var(--input-text, #dddddd);
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0 4px;
  user-select: none;
}

.mmx-director-root select,
.mmx-director-root button,
.mmx-director-root input {
  font-family: inherit;
}

.mmx-language-select {
  width: 100px;
  height: 24px;
  padding: 2px 6px;
  font-size: 11px;
  background: var(--comfy-input-bg, #333333);
  color: var(--input-text, #dddddd);
  border: 1px solid var(--border-color, #4a4a4a);
  border-radius: 4px;
}

/* Toolbar */
.mmx-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--comfy-input-bg, #333333);
}

.mmx-pill-group {
  display: flex;
  align-items: center;
  gap: 3px;
  background: var(--comfy-input-bg, #222222);
  padding: 3px;
  border-radius: 20px;
  border: 1px solid var(--comfy-input-bg, #333333);
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
  background: var(--comfy-input-bg, #333333);
  border: 1px solid var(--border-color, #4a4a4a);
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
  background: var(--border-color, #4a4a4a);
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

.mmx-action-btn.danger {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.4);
  color: #f87171;
}

.mmx-action-btn.danger:hover {
  background: #ef4444;
  border-color: #ef4444;
  color: #ffffff;
}

/* Timeline tracks area */
.mmx-timeline-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: var(--comfy-input-bg, #222222);
  border: 1px solid var(--comfy-input-bg, #333333);
  border-radius: 6px;
  padding: 8px;
  width: 100%;
  flex: 1;
  overflow-x: hidden;
  overflow-y: auto;
}

.mmx-track {
  display: flex;
  align-items: center;
  position: relative;
  min-height: 90px;
  width: 100%;
  flex: 1;
  background: var(--comfy-menu-bg, #282828);
  border: 1px solid var(--comfy-input-bg, #333333);
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
  height: 100%;
  padding-top: 14px;
  overflow-x: auto;
  overflow-y: hidden;
}

/* Media Item Tile */
.mmx-tile {
  position: relative;
  width: 96px;
  height: 64px;
  background: var(--comfy-input-bg, #333333);
  border: 1px solid var(--border-color, #4a4a4a);
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
  border: 1px dashed var(--border-color, #4a4a4a);
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
  background: var(--comfy-input-bg, #333333);
  border: 1px solid var(--border-color, #4a4a4a);
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
  background: var(--comfy-input-bg, #222222);
  border: 1px solid var(--comfy-input-bg, #333333);
  border-radius: 6px;
  padding: 10px;
  width: 100%;
  height: 100%;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
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
  background: var(--comfy-menu-bg, #282828);
  border: 1px solid var(--border-color, #4a4a4a);
  border-radius: 5px;
  color: #f8fafc;
  font-family: inherit;
  font-size: 11px;
  padding: 6px 8px;
  resize: vertical;
  min-height: 100px;
  height: 100%;
  flex: 1;
  overflow-y: auto;
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
  background: var(--comfy-menu-bg, #282828);
  border: 1px solid var(--border-color, #4a4a4a);
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
  border-bottom: 1px solid var(--comfy-input-bg, #333333);
  background: var(--comfy-input-bg, #222222);
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
  border-top: 1px solid var(--comfy-input-bg, #333333);
  background: var(--comfy-input-bg, #222222);
}

/* View Navigation Tabs */
.mmx-view-tabs {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0 6px 0;
  border-bottom: 1px solid var(--comfy-input-bg, #333333);
  margin-bottom: 4px;
}

.mmx-tab-btn {
  background: var(--comfy-input-bg, #333333);
  border: 1px solid var(--border-color, #4a4a4a);
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
  background: var(--border-color, #4a4a4a);
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
  background: var(--comfy-input-bg, #222222);
  border: 1px solid var(--comfy-input-bg, #333333);
  border-radius: 6px;
  padding: 10px;
  width: 100%;
  height: 100%;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
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
  background: var(--comfy-menu-bg, #282828);
  border: 1px solid var(--border-color, #4a4a4a);
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
  background: var(--comfy-input-bg, #333333);
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

/* Custom sleek scrollbars */
.mmx-timeline-panel::-webkit-scrollbar,
.mmx-drawer::-webkit-scrollbar,
.mmx-refmod-panel::-webkit-scrollbar,
.mmx-track-items::-webkit-scrollbar,
.mmx-inspector::-webkit-scrollbar,
.mmx-textarea::-webkit-scrollbar,
.mmx-multitrack-panel::-webkit-scrollbar,
.mmx-structured-grid::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.mmx-timeline-panel::-webkit-scrollbar-track,
.mmx-drawer::-webkit-scrollbar-track,
.mmx-refmod-panel::-webkit-scrollbar-track,
.mmx-track-items::-webkit-scrollbar-track,
.mmx-inspector::-webkit-scrollbar-track,
.mmx-textarea::-webkit-scrollbar-track,
.mmx-multitrack-panel::-webkit-scrollbar-track,
.mmx-structured-grid::-webkit-scrollbar-track {
  background: transparent;
}

.mmx-timeline-panel::-webkit-scrollbar-thumb,
.mmx-drawer::-webkit-scrollbar-thumb,
.mmx-refmod-panel::-webkit-scrollbar-thumb,
.mmx-track-items::-webkit-scrollbar-thumb,
.mmx-inspector::-webkit-scrollbar-thumb,
.mmx-textarea::-webkit-scrollbar-thumb,
.mmx-multitrack-panel::-webkit-scrollbar-thumb,
.mmx-structured-grid::-webkit-scrollbar-thumb {
  background: var(--border-color, #4a4a4a);
  border-radius: 3px;
}

.mmx-timeline-panel::-webkit-scrollbar-thumb:hover,
.mmx-drawer::-webkit-scrollbar-thumb:hover,
.mmx-refmod-panel::-webkit-scrollbar-thumb:hover,
.mmx-track-items::-webkit-scrollbar-thumb:hover,
.mmx-inspector::-webkit-scrollbar-thumb:hover,
.mmx-textarea::-webkit-scrollbar-thumb:hover,
.mmx-multitrack-panel::-webkit-scrollbar-thumb:hover,
.mmx-structured-grid::-webkit-scrollbar-thumb:hover {
  background: #6366f1;
}

/* Premiere-Style Time Ruler & Bar */
.mmx-ruler-bar {
  position: relative;
  width: 100%;
  height: 28px;
  background: var(--comfy-input-bg, #222222);
  border: 1px solid var(--comfy-input-bg, #333333);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 8px;
  user-select: none;
}

.mmx-ruler-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  z-index: 2;
}

.mmx-timecode-badge {
  font-family: monospace;
  font-size: 11px;
  font-weight: 700;
  color: #38bdf8;
  background: rgba(15, 23, 42, 0.8);
  padding: 2px 6px;
  border-radius: 3px;
  border: 1px solid var(--border-color, #4a4a4a);
}

.mmx-ruler-zoom {
  display: flex;
  align-items: center;
  gap: 4px;
  z-index: 2;
}

.mmx-zoom-btn {
  background: var(--comfy-input-bg, #333333);
  border: 1px solid var(--border-color, #4a4a4a);
  color: #94a3b8;
  width: 20px;
  height: 20px;
  border-radius: 3px;
  font-size: 11px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mmx-zoom-btn:hover {
  color: #f8fafc;
  border-color: #6366f1;
}

/* Multi-Subtimeline Architecture (Shots/Prompt, Ref Images, Ref Videos, Ref Audios) */
.mmx-multitrack-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 3px;
  background: #080c14;
  border: 1px solid var(--comfy-input-bg, #333333);
  border-radius: 6px;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 4px;
  width: 100%;
  min-height: 210px;
  flex-shrink: 0;
}

.mmx-track-row {
  display: flex;
  align-items: center;
  min-width: max-content;
  width: 100%;
  border-bottom: 1px solid rgba(30, 41, 59, 0.4);
  padding: 1px 0;
}

.mmx-track-row:last-child {
  border-bottom: none;
}

.mmx-track-header-cell {
  position: sticky;
  left: 0;
  z-index: 20;
  width: 130px;
  min-width: 130px;
  max-width: 130px;
  background: #0b1120;
  border-right: 1px solid var(--comfy-input-bg, #333333);
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  font-size: 10px;
  font-weight: 700;
  color: #94a3b8;
  letter-spacing: 0.3px;
  text-transform: uppercase;
  user-select: none;
  box-shadow: 2px 0 6px rgba(0, 0, 0, 0.4);
  box-sizing: border-box;
}

.mmx-track-lane-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 6px;
  flex: 1;
  min-width: max-content;
  position: relative;
}

/* Sub-timeline Clip Blocks */
.mmx-subtrack-block {
  position: relative;
  display: flex;
  flex-direction: row;
  align-items: center;
  background: var(--comfy-input-bg, #333333);
  border: 1px solid var(--border-color, #4a4a4a);
  border-radius: 5px;
  padding: 3px 6px;
  cursor: pointer;
  flex-shrink: 0;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
  user-select: none;
  overflow: hidden;
  box-sizing: border-box;
}

.mmx-subtrack-block:hover {
  border-color: #6366f1;
}

.mmx-subtrack-block.active {
  border-color: #6366f1;
  background: #1a233a;
  box-shadow: 0 0 0 1px #6366f1, 0 0 10px rgba(99, 102, 241, 0.35);
}

.mmx-subtrack-block.validated {
  border-color: rgba(16, 185, 129, 0.5);
}

.mmx-subtrack-block.validated.active {
  border-color: #10b981;
  box-shadow: 0 0 0 1px #10b981, 0 0 10px rgba(16, 185, 129, 0.35);
}

.mmx-shot-block {
  height: 52px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.mmx-shot-prompt-preview {
  font-size: 9px;
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-style: italic;
  line-height: 1.2;
}

.mmx-img-block {
  height: 48px;
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  justify-content: flex-start !important;
  gap: 6px;
  padding: 3px 6px;
  overflow-x: auto;
}

.mmx-vid-block {
  height: 48px;
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  justify-content: flex-start !important;
  gap: 6px;
  padding: 3px 6px;
  overflow-x: auto;
}

.mmx-aud-block {
  height: 40px;
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  justify-content: flex-start !important;
  gap: 6px;
  padding: 2px 6px;
  overflow-x: auto;
}

.mmx-clip-img-cell {
  flex: 0 0 38px;
  width: 38px;
  height: 38px;
  min-width: 38px;
  max-width: 38px;
  position: relative;
  overflow: hidden;
  background: var(--comfy-input-bg, #333333);
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
}

.mmx-clip-img-cell img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.mmx-clip-vid-cell {
  flex: 0 0 56px;
  width: 56px;
  height: 36px;
  min-width: 56px;
  max-width: 56px;
  position: relative;
  overflow: hidden;
  background: var(--comfy-input-bg, #333333);
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  cursor: pointer;
}

.mmx-clip-vid-cell video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.mmx-subtrack-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  color: #64748b;
  font-style: italic;
  width: 100%;
  height: 100%;
  border: 1px dashed rgba(51, 65, 85, 0.5);
  border-radius: 4px;
}

/* Timeline Sequential Clips Track (Legacy Fallback) */
.mmx-clips-track {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 105px;
  background: var(--comfy-input-bg, #222222);
  border: 1px solid var(--comfy-input-bg, #333333);
  border-radius: 6px;
  padding: 8px;
  overflow-x: auto;
  overflow-y: hidden;
  position: relative;
}

/* Premiere-like Clip Card */
.mmx-clip-card {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-width: 160px;
  height: 90px;
  background: var(--comfy-input-bg, #333333);
  border: 1px solid var(--border-color, #4a4a4a);
  border-radius: 6px;
  padding: 6px 8px;
  cursor: pointer;
  flex-shrink: 0;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
  user-select: none;
}

.mmx-clip-card:hover {
  border-color: #6366f1;
}

.mmx-clip-card.active {
  border-color: #6366f1;
  box-shadow: 0 0 0 1px #6366f1, 0 0 14px rgba(99, 102, 241, 0.4);
  background: #1a233a;
}

.mmx-clip-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.mmx-clip-mode-badge {
  font-size: 9px;
  font-weight: 800;
  padding: 2px 5px;
  border-radius: 3px;
  text-transform: uppercase;
  color: #ffffff;
  letter-spacing: 0.5px;
}

.mmx-badge-t2v { background: #2563eb; }
.mmx-badge-i2v { background: #059669; }
.mmx-badge-fl2v { background: #d97706; }
.mmx-badge-v2v { background: #7c3aed; }
.mmx-badge-ref2v { background: #0891b2; }
.mmx-badge-ref2va { background: #4f46e5; }
.mmx-badge-l2v {background:#b45309;}
.mmx-badge-rv2v {background:#be185d;}
.mmx-badge-video {background:#475569;}
.mmx-badge-img {background:#0e7490;}
.mmx-clip-mode-badge.mmx-badge-t2v {--mmx-mode-color:#2563eb;}
.mmx-clip-mode-badge.mmx-badge-i2v {--mmx-mode-color:#059669;}
.mmx-clip-mode-badge.mmx-badge-fl2v {--mmx-mode-color:#d97706;}
.mmx-clip-mode-badge.mmx-badge-v2v {--mmx-mode-color:#7c3aed;}
.mmx-clip-mode-badge.mmx-badge-ref2v {--mmx-mode-color:#0891b2;}
.mmx-clip-mode-badge.mmx-badge-l2v {--mmx-mode-color:#b45309;}
.mmx-clip-mode-badge.mmx-badge-rv2v {--mmx-mode-color:#be185d;}
.mmx-clip-mode-badge.mmx-badge-video {--mmx-mode-color:#475569;}
.mmx-clip-mode-badge.mmx-badge-img {--mmx-mode-color:#0e7490;}
.mmx-director-root .mmx-shot-top-bar .mmx-clip-mode-badge[class*="mmx-badge-"] {background:var(--mmx-mode-color);color:white;}
.mmx-clip-type-label.mmx-clip-mode-badge {color:white;border:1px solid #ffffff35;padding:6px 10px;}

.mmx-clip-title {
  display: none;
  font-size: 11px;
  font-weight: 600;
  color: #f1f5f9;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.mmx-clip-duration {
  font-size: 10px;
  font-weight: 700;
  color: #94a3b8;
  font-family: monospace;
}

.mmx-clip-body {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 9px;
  color: #94a3b8;
  overflow: hidden;
}

.mmx-clip-refs-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}

.mmx-clip-ref-pill {
  font-size: 8px;
  font-weight: 600;
  padding: 1px 4px;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid var(--border-color, #4a4a4a);
  border-radius: 3px;
  color: #cbd5e1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 90px;
}

.mmx-clip-continuity-badge {
  font-size: 8px;
  font-weight: 700;
  color: #10b981;
  display: flex;
  align-items: center;
  gap: 2px;
}

.mmx-clip-del-btn {
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.4);
  border-radius: 4px;
  color: #fca5a5;
  cursor: pointer;
  font-size: 11px;
  padding: 1px 5px;
  line-height: 1.2;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-left: 4px;
  transition: all 0.15s ease;
}

.mmx-clip-del-btn:hover {
  background: #ef4444;
  border-color: #ef4444;
  color: #ffffff;
  transform: scale(1.1);
}

.mmx-clip-dup-btn {
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.4);
  border-radius: 4px;
  color: #c7d2fe;
  cursor: pointer;
  font-size: 11px;
  padding: 1px 5px;
  line-height: 1.2;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-left: 4px;
  transition: all 0.15s ease;
}

.mmx-clip-dup-btn:hover {
  background: #6366f1;
  border-color: #6366f1;
  color: #ffffff;
  transform: scale(1.1);
}

/* Resize handles */
.mmx-clip-handle {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 6px;
  cursor: ew-resize;
  background: transparent;
  transition: background 0.1s;
}

.mmx-clip-handle:hover {
  background: rgba(99, 102, 241, 0.5);
}

.mmx-clip-handle-left {
  left: 0;
  border-top-left-radius: 5px;
  border-bottom-left-radius: 5px;
}

.mmx-clip-handle-right {
  right: 0;
  border-top-right-radius: 5px;
  border-bottom-right-radius: 5px;
}

/* Add Clip Button */
.mmx-add-clip-card {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 100px;
  height: 52px;
  border: 2px dashed var(--border-color, #4a4a4a);
  border-radius: 6px;
  background: rgba(30, 41, 59, 0.2);
  color: #94a3b8;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s ease;
  font-size: 11px;
  font-weight: 600;
  padding: 0 10px;
}

.mmx-add-clip-card:hover {
  border-color: #6366f1;
  color: #a5b4fc;
  background: rgba(99, 102, 241, 0.08);
}

.mmx-add-clip-icon {
  font-size: 20px;
  line-height: 1;
}

/* Active Clip Inspector */
.mmx-inspector {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #0b1120;
  border: 1px solid var(--comfy-input-bg, #333333);
  border-radius: 6px;
  padding: 10px;
  width: 100%;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.mmx-inspector-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--comfy-input-bg, #333333);
  flex-wrap: wrap;
  flex-shrink: 0;
}

.mmx-inspector-title {
  font-size: 12px;
  font-weight: 700;
  color: #f1f5f9;
  display: flex;
  align-items: center;
  gap: 8px;
}

.mmx-mode-select {
  background: var(--comfy-input-bg, #333333);
  border: 1px solid #475569;
  border-radius: 4px;
  color: #f8fafc;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 6px;
  cursor: pointer;
  outline: none;
}

.mmx-mode-select:focus {
  border-color: #6366f1;
}

.mmx-inspector-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.mmx-local-refs-pool {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  background: var(--comfy-menu-bg, #282828);
  border: 1px solid var(--comfy-input-bg, #333333);
  border-radius: 5px;
  padding: 8px 10px;
  flex-shrink: 0;
}

.mmx-local-refs-title {
  font-size: 10px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.mmx-local-refs-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.mmx-local-ref-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: var(--comfy-input-bg, #333333);
  border: 1px solid var(--border-color, #4a4a4a);
  border-radius: 4px;
  padding: 3px 8px;
  font-size: 10px;
  cursor: pointer;
  transition: all 0.15s ease;
  color: #94a3b8;
  user-select: none;
}

.mmx-local-ref-item:hover {
  border-color: #6366f1;
  color: var(--input-text, #dddddd);
}

.mmx-local-ref-item.checked {
  border-color: #6366f1;
  color: #ffffff;
  font-weight: 600;
}

.mmx-local-ref-item.checked.type-img {
  background: rgba(37, 99, 235, 0.35);
  border-color: #3b82f6;
  color: #bfdbfe;
}

.mmx-local-ref-item.checked.type-vid {
  background: rgba(124, 58, 237, 0.35);
  border-color: #8b5cf6;
  color: #ddd6fe;
}

.mmx-local-ref-item.checked.type-aud {
  background: rgba(16, 185, 129, 0.35);
  border-color: #10b981;
  color: #a7f3d0;
}

.mmx-local-ref-item.checked.type-mod {
  background: rgba(245, 158, 11, 0.35);
  border-color: #f59e0b;
  color: #fde68a;
}

/* Prompt Inspector Container */
.mmx-prompt-inspector {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  flex: 1;
  min-height: 140px;
}

.mmx-prompt-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.mmx-quick-tags {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.mmx-quick-tag-btn {
  background: var(--comfy-input-bg, #333333);
  border: 1px solid var(--border-color, #4a4a4a);
  color: #818cf8;
  font-size: 9px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.mmx-quick-tag-btn:hover {
  background: var(--border-color, #4a4a4a);
  color: #a5b4fc;
  border-color: #6366f1;
}

.mmx-prompt-char-count {
  font-size: 9px;
  color: #64748b;
  font-family: monospace;
}

/* LTX Director Style 24px Time Ruler */
.mmx-ruler-container {
  position: relative;
  width: 100%;
  height: 24px;
  background: var(--comfy-input-bg, #222222);
  border: 1px solid var(--comfy-input-bg, #333333);
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
}



.mmx-playhead-needle {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: #ef4444;
  box-shadow: 0 0 1px rgba(0, 0, 0, 0.8);
  pointer-events: none;
  z-index: 50;
  transform: translateX(-50%);
}

.mmx-playhead-handle {
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 11px;
  height: 14px;
  cursor: ew-resize;
  pointer-events: auto;
  z-index: 51;
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.8));
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

.mmx-playhead-handle::before {
  content: "";
  position: absolute;
  top: -4px;
  bottom: -4px;
  left: -6px;
  right: -6px;
  cursor: ew-resize;
}

.mmx-playhead-handle:empty {
  background: #ef4444;
  clip-path: polygon(0% 0%, 100% 0%, 100% 60%, 50% 100%, 0% 60%);
}

.mmx-playhead-handle svg {
  display: block;
  width: 11px;
  height: 14px;
  overflow: visible;
  pointer-events: none;
}

.mmx-playhead-handle svg path {
  fill: #ef4444;
  stroke: rgba(255, 255, 255, 0.5);
  stroke-width: 1;
  transition: fill 0.15s ease, stroke 0.15s ease;
}

.mmx-playhead-handle:hover svg path,
.mmx-playhead-handle:hover:empty {
  fill: #f87171;
  background: #f87171;
  stroke: #ffffff;
}

.mmx-playhead-handle:active svg path,
.mmx-playhead-handle:active:empty {
  fill: #dc2626;
  background: #dc2626;
}

/* LTX Director Toolbar Buttons */
.mmx-toolbar-left {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.mmx-toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.mmx-timecode-display {
  font-family: monospace;
  font-size: 11px;
  font-weight: 700;
  color: #38bdf8;
  background: var(--comfy-input-bg, #222222);
  border: 1px solid var(--comfy-input-bg, #333333);
  padding: 2px 6px;
  border-radius: 3px;
  user-select: none;
}

.mmx-zoom-slider-wrap {
  display: flex;
  align-items: center;
  gap: 4px;
}

.mmx-zoom-slider {
  width: 70px;
  height: 4px;
  accent-color: #6366f1;
  cursor: pointer;
}

.mmx-type-modal-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  padding: 10px 0;
}

.mmx-type-modal-btn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
  background: var(--comfy-input-bg, #333333);
  border: 1px solid var(--border-color, #4a4a4a);
  border-radius: 6px;
  padding: 10px 12px;
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: left;
}

.mmx-type-modal-btn:hover {
  background: #2a374a;
  border-color: #6366f1;
  transform: translateY(-1px);
}

.mmx-type-modal-btn-title {
  font-size: 12px;
  font-weight: 700;
  color: #f8fafc;
  display: flex;
  align-items: center;
  gap: 6px;
}

.mmx-type-modal-btn-desc {
  font-size: 10px;
  color: #94a3b8;
  line-height: 1.3;
}

/* Card grid and modular inspector layout */
.mmx-inspector-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 8px;
  width: 100%;
  flex-shrink: 0;
}

.mmx-inspector-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: var(--comfy-input-bg, #222222);
  border: 1px solid var(--comfy-input-bg, #333333);
  border-radius: 6px;
  padding: 7px 10px;
  min-width: 0;
}

.mmx-inspector-card-title {
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: flex;
  align-items: center;
  gap: 5px;
}

.mmx-inspector-card-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.mmx-ctrl-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.mmx-ctrl-item label {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 500;
}

.mmx-ctrl-unit {
  font-size: 10px;
  color: #64748b;
  font-weight: 600;
}

.mmx-validate-toggle {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 14px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  user-select: none;
  border: 1px solid var(--border-color, #4a4a4a);
  transition: all 0.15s ease;
}

.mmx-validate-toggle.validated {
  background: rgba(16, 185, 129, 0.15);
  border-color: #10b981;
  color: #34d399;
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.2);
}

.mmx-validate-toggle.unvalidated {
  background: var(--comfy-input-bg, #333333);
  border-color: var(--border-color, #4a4a4a);
  color: #94a3b8;
}

.mmx-validate-toggle:hover {
  filter: brightness(1.15);
}

/* Multi-Track Sub-Timelines Architecture */
.mmx-multitrack-panel {
  display: flex;
  flex-direction: column;
  gap: 3px;
  background: var(--comfy-input-bg, #222222);
  border: 1px solid var(--comfy-input-bg, #333333);
  border-radius: 6px;
  padding: 6px 8px;
  overflow-x: auto;
  overflow-y: hidden;
  position: relative;
  user-select: none;
  max-height: 235px;
}

.mmx-track-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  min-width: max-content;
  position: relative;
}

.mmx-track-header-cell {
  position: sticky;
  left: 0;
  z-index: 30;
  width: 124px;
  min-width: 124px;
  max-width: 124px;
  height: 100%;
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 2px 8px;
  font-size: 10px;
  font-weight: 700;
  color: #94a3b8;
  background: var(--comfy-input-bg, #222222);
  border-right: 1px solid var(--comfy-input-bg, #333333);
  box-shadow: 2px 0 6px rgba(0, 0, 0, 0.4);
  box-sizing: border-box;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  user-select: none;
}

.mmx-track-lane-cell {
  display: flex;
  align-items: center;
  gap: 4px;
  padding-left: 6px;
  flex: 1;
  min-width: max-content;
  box-sizing: border-box;
}

.mmx-ruler-lane {
  position: relative;
  height: 24px;
  cursor: pointer;
}

.mmx-subtrack-block {
  border-radius: 4px;
  background: #0b1120;
  border: 1px solid var(--comfy-input-bg, #333333);
  box-sizing: border-box;
  display: flex;
  align-items: center;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
  overflow: hidden;
  flex-shrink: 0;
  position: relative;
}

.mmx-subtrack-block:hover {
  border-color: var(--border-color, #4a4a4a);
  background: #0e172a;
}

.mmx-subtrack-block.active {
  border-color: #6366f1 !important;
  background: rgba(99, 102, 241, 0.08) !important;
  box-shadow: 0 0 6px rgba(99, 102, 241, 0.2);
}

.mmx-subtrack-block.validated {
  border-color: #059669;
}

.mmx-shot-block {
  height: 52px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 4px 6px;
}

.mmx-shot-top-bar {
  display: flex;
  align-items: center;
  gap: 5px;
  width: 100%;
  overflow: hidden;
}

.mmx-shot-prompt-preview {
  font-size: 9px;
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: inherit;
  line-height: 1.2;
  padding-top: 2px;
}

.mmx-img-block {
  height: 44px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 4px;
}

.mmx-vid-block {
  height: 44px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 4px;
}

.mmx-aud-block {
  height: 38px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
}

.mmx-subtrack-empty {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  color: #475569;
  font-style: italic;
  border: 1px dashed rgba(51, 65, 85, 0.4);
  border-radius: 3px;
  pointer-events: none;
}

/* Structured Prompt Grid */
.mmx-structured-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
  width: 100%;
  flex: 1;
  min-height: 140px;
  overflow-y: auto;
}

.mmx-structured-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mmx-structured-field.full-span {
  grid-column: span 2;
}

.mmx-structured-label {
  font-size: 10px;
  font-weight: 700;
  color: #a5b4fc;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  letter-spacing: 0.2px;
}

.mmx-structured-input {
  background: var(--comfy-input-bg, #333333);
  border: 1px solid var(--border-color, #4a4a4a);
  border-radius: 4px;
  color: #f8fafc;
  font-size: 11px;
  padding: 4px 6px;
  font-family: inherit;
}

.mmx-structured-input:focus,
.mmx-structured-textarea:focus {
  outline: none;
  border-color: #6366f1;
}

.mmx-structured-textarea {
  background: var(--comfy-input-bg, #333333);
  border: 1px solid var(--border-color, #4a4a4a);
  border-radius: 4px;
  color: #f8fafc;
  font-size: 11px;
  padding: 4px 6px;
  font-family: inherit;
  resize: vertical;
  min-height: 44px;
}

/* Prompt Mode Tabs (Raw vs Structured) */
.mmx-prompt-mode-tabs {
  display: inline-flex;
  align-items: center;
  background: var(--comfy-input-bg, #222222);
  padding: 2px 4px;
  border-radius: 20px;
  border: 1px solid var(--comfy-input-bg, #333333);
  gap: 3px;
}

.mmx-prompt-mode-tab {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 12px;
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.15s ease;
  outline: none;
}

.mmx-prompt-mode-tab:hover {
  color: #f1f5f9;
  background: rgba(255, 255, 255, 0.06);
}

.mmx-prompt-mode-tab.active {
  background: #6366f1;
  color: #ffffff;
  font-weight: 700;
  box-shadow: 0 0 10px rgba(99, 102, 241, 0.4);
}


.mmx-director-root [hidden] { display: none !important; }
.mmx-smart-preview { flex: 1; min-height: 0; display: flex; flex-direction: column; gap: 8px; }
.mmx-smart-preview video { width: 100%; flex: 1; min-height: 0; object-fit: contain; background: #000; border-radius: 4px; }
.mmx-preview-status { flex: 1; font-size: 12px; color: var(--input-text, #dddddd); }
.mmx-smart-preview label { font-size: 12px; white-space: nowrap; }
.mmx-preview-empty { flex: 1; display: grid; place-items: center; color: var(--descrip-text, #999); font-size: 14px; }
/* One continuous node surface; borders identify editable controls and selected shots. */
.mmx-director-root .mmx-inspector {
  background: transparent;
  border: 0;
  border-top: 1px solid var(--border-color, #4a4a4a);
  border-radius: 0;
  padding: 10px 0;
}
.mmx-director-root .mmx-inspector-card {
  background: transparent;
  border: 0;
  border-radius: 0;
  padding: 7px 0;
}
.mmx-director-root .mmx-multitrack-panel {
  border: 0;
  border-radius: 0;
  padding: 6px 0;
}
.mmx-director-root .mmx-track-header-cell { box-shadow: none; }
.mmx-director-root .mmx-action-btn { border-radius: 4px; }
.mmx-time-ruler { position: relative; height: 24px; flex: none; }
.mmx-time-tick {
  position: absolute; top: 0; bottom: 0;
  color: var(--input-text, #dddddd);
  font: 11px ui-monospace, Consolas, monospace;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  pointer-events: none;
}
.mmx-time-tick::after {
  content: ''; position: absolute; bottom: 0; left: 0;
  height: 6px; border-left: 1px solid var(--border-color, #4a4a4a);
}
.mmx-time-tick.major::after { height: 10px; }
.mmx-time-tick span { padding-left: 4px; }
.mmx-time-tick.endpoint { width:0; }
.mmx-time-tick.endpoint span { position:absolute; right:0; padding-left:0; padding-right:4px; }

/* Editor finish: one node surface, readable controls, restrained violet accents. */
.mmx-director-root {
  --mmx-accent: #a396ff;
  --mmx-line: color-mix(in srgb, var(--input-text, #ddd) 12%, transparent);
  --mmx-soft: color-mix(in srgb, var(--input-text, #ddd) 4%, transparent);
  font-size: 13px;
  gap: 12px;
  padding: 4px 8px 8px;
  accent-color: #9381f8;
  scrollbar-width: thin;
  scrollbar-color: #666176 transparent;
}
.mmx-director-root .mmx-toolbar {
  gap: 10px;
  padding-bottom: 10px;
  border-color: var(--mmx-line);
}
.mmx-director-root .mmx-toolbar-left,
.mmx-director-root .mmx-toolbar-right { gap: 8px; }
.mmx-director-root .mmx-toolbar-left { align-items: center; }
.mmx-director-root button,
.mmx-director-root select,
.mmx-director-root input:not([type=checkbox]):not([type=range]):not([type=file]) {
  font-size: 12px !important;
  min-height: 28px;
  border-radius: 6px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.mmx-director-root select,
.mmx-director-root input:not([type=checkbox]):not([type=range]):not([type=file]) {
  border: 1px solid var(--mmx-line) !important;
  color: var(--input-text, #e5e5e5) !important;
  background: var(--comfy-input-bg, #303030);
  padding: 4px 8px !important;
}
.mmx-director-root .mmx-action-btn {
  background: var(--mmx-soft);
  border: 1px solid var(--mmx-line);
  padding: 5px 10px;
  gap: 6px;
  color: var(--input-text, #ddd);
  transition: background .15s, border-color .15s;
}
.mmx-director-root .mmx-action-btn:hover { background: rgba(147,129,248,.12); border-color: #7666b5; }
.mmx-director-root .mmx-action-btn.danger { color: #f4a0a7; background: rgba(240,100,115,.06); border-color: rgba(240,100,115,.22); }
.mmx-director-root .mmx-pill-group,
.mmx-director-root .mmx-prompt-mode-tabs {
  padding: 3px;
  border: 1px solid var(--mmx-line);
  background: var(--mmx-soft);
  border-radius: 8px;
  gap: 3px;
}
.mmx-director-root .mmx-pill-btn,
.mmx-director-root .mmx-prompt-mode-tab { padding: 5px 13px; border-radius: 5px; }
.mmx-director-root .mmx-pill-btn.active,
.mmx-director-root .mmx-prompt-mode-tab.active {
  background: #7967d8;
  color: #fff;
  box-shadow: none;
}
.mmx-director-root .mmx-multitrack-panel {
  background: var(--mmx-soft);
  border-radius: 8px;
  padding: 8px 0;
  gap: 4px;
  flex-shrink: 0;
  max-height: 249px;
}
.mmx-director-root .mmx-track-header-cell {
  background: var(--comfy-menu-bg, #282828);
  border-right-color: var(--mmx-line);
  color: var(--descrip-text, #b3b0be);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: .025em;
}
.mmx-director-root .mmx-track-lane-cell {
  background-image: repeating-linear-gradient(to right, var(--mmx-line) 0 1px, transparent 1px var(--mmx-grid-step, 80px));
  background-position: 6px 0;
}
.mmx-director-root .mmx-subtrack-block {
  border-radius: 6px;
  border-color: var(--mmx-line);
  background: var(--comfy-menu-bg, #282828);
  box-shadow: none;
}
.mmx-director-root .mmx-subtrack-block.active {
  background: color-mix(in srgb, #9381f8 6%, var(--comfy-menu-bg, #282828)) !important;
  border-color: #625b7b !important;
  box-shadow: none;
}
.mmx-director-root .mmx-shot-block.active { border-color: var(--mmx-accent) !important; box-shadow: inset 3px 0 0 #9381f8; }
.mmx-director-root .mmx-subtrack-block.validated { border-color: #55a987 !important; }
.mmx-director-root .mmx-shot-block { padding: 7px 10px; height: 58px; }
.mmx-director-root .mmx-clip-title { font-size: 12px; font-weight: 650; }
.mmx-director-root .mmx-shot-prompt-preview { font-size: 11px; line-height: 1.4; color: var(--descrip-text, #b2adbd); }
.mmx-director-root .mmx-subtrack-empty {
  border: none;
  font-size: 11px;
  color: var(--descrip-text, #9e9aa8);
  font-style: normal;
}
.mmx-director-root .mmx-add-clip-card { height: 58px; border-radius: 6px; color: var(--descrip-text, #b9b4c5); border-color: #605972; }
.mmx-director-root .mmx-timecode-display { color: var(--mmx-accent); padding: 5px 8px; background: var(--mmx-soft); border-color: var(--mmx-line); border-radius: 5px; }
.mmx-director-root .mmx-inspector { gap: 12px; border-color: var(--mmx-line); padding-top: 12px; }
.mmx-director-root .mmx-inspector-header { padding-bottom: 10px; border-color: var(--mmx-line); }
.mmx-director-root .mmx-inspector-title { gap: 10px; }
.mmx-director-root .mmx-inspector-card-title,
.mmx-director-root .mmx-local-refs-title { color: var(--descrip-text, #b4afc3); font-size: 11px; letter-spacing: .045em; font-weight: 600; }
.mmx-director-root .mmx-inspector-card { gap: 9px; }
.mmx-director-root .mmx-ctrl-item label { color: var(--descrip-text, #b9b6c1); font-size: 12px; }
.mmx-director-root .mmx-local-refs-pool { padding: 10px 12px; background: var(--mmx-soft); border: 0; border-radius: 6px; }
.mmx-director-root .mmx-quick-tag-btn { min-height: 24px; padding: 3px 8px; color: var(--mmx-accent); font-size: 11px !important; background: rgba(147,129,248,.07); border-color: rgba(147,129,248,.18); }
.mmx-director-root textarea {
  font-family: inherit;
  font-size: 13px;
  line-height: 1.6;
  padding: 12px;
  background: var(--comfy-input-bg, #242424);
  color: var(--input-text, #e5e5e5);
  border: 1px solid var(--mmx-line);
  border-radius: 8px;
}
.mmx-director-root input:focus-visible,
.mmx-director-root textarea:focus-visible,
.mmx-director-root select:focus-visible,
.mmx-director-root button:focus-visible,
.mmx-director-root summary:focus-visible { outline: 2px solid var(--mmx-accent); outline-offset: 2px; }
.mmx-director-root .mmx-validate-toggle { box-shadow: none; font-size: 11px; border-radius: 6px; padding: 5px 9px; }
.mmx-director-root .mmx-validate-toggle.unvalidated { background: var(--mmx-soft); border-color: var(--mmx-line); color: var(--descrip-text, #bdb7c7); }
.mmx-director-root .mmx-smart-preview video { border-radius: 8px; }
.mmx-director-root .mmx-preview-empty { background: var(--mmx-soft); border-radius: 8px; }
.mmx-director-root details > summary { cursor: pointer; color: var(--descrip-text, #c0b9cd); padding: 3px 0; font-size: 12px; }
@media (prefers-reduced-motion: reduce) { .mmx-director-root * { transition: none !important; } }

.mmx-director-root .mmx-shot-sections { display: flex; gap: 6px 18px; flex-wrap: wrap; align-items: start; flex-shrink: 0; }
.mmx-director-root .mmx-shot-sections > details { min-width: 0; }
.mmx-director-root .mmx-shot-sections > details[open] { flex-basis: 100%; }
.mmx-director-root .mmx-shot-sections > details > summary { padding: 4px 0; }
.mmx-director-root .mmx-inspector { gap: 9px; }
.mmx-director-root .mmx-prompt-inspector { min-height: 160px; }
.mmx-director-root .mmx-track-lane-cell .mmx-clip-dup-btn { min-height: 22px; padding: 1px 5px; }
.mmx-director-root .mmx-aud-block { height: 34px; }

.mmx-director-root .mmx-shot-block { cursor: grab; touch-action: none; padding-right: 14px; }
.mmx-director-root .mmx-shot-top-bar { width: 100%; gap: 5px; min-width: 0; padding-right: 22px; box-sizing: border-box; min-height: 22px; }
.mmx-director-root .mmx-clip-title { display: block; min-width: 0; }
.mmx-director-root .mmx-clip-duration { white-space: nowrap; }
.mmx-director-root .mmx-clip-dup-btn { display: none; }
.mmx-director-root .mmx-clip-del-btn { position: absolute; top: 4px; right: 4px; width: 22px; height: 22px; min-height: 0; padding: 0; margin: 0; display: flex; align-items: center; justify-content: center; z-index: 3; }
.mmx-director-root .mmx-clip-del-btn:hover { transform: none; }
.mmx-director-root .mmx-clip-del-btn svg { width: 12px; height: 12px; display: block; pointer-events: none; }
/* The boundary is the resize target; no separate grip covers the clip. */
.mmx-director-root .mmx-clip-handle-right { width: 6px; border: 0; border-radius: 0; background: transparent; z-index: 2; }
.mmx-director-root .mmx-clip-handle-right:hover { background: transparent; box-shadow: inset -2px 0 #a6d7ee; }
.mmx-director-root .mmx-dragging { cursor: grabbing; opacity: .75; z-index: 4; box-shadow: 0 4px 14px #0006; }
.mmx-director-root .mmx-drop-before { border-left: 3px solid #b4a5ff; }
.mmx-director-root .mmx-drop-after { border-right: 3px solid #b4a5ff; }
.mmx-director-root .mmx-inspector-header { flex-wrap: wrap; }
.mmx-empty-timeline { color: var(--descrip-text, #aaa); padding: 18px 4px; }

/* Separators belong above lanes: hidden trailing tracks and the playhead must
   not leave a second bottom edge beneath the final visible lane. */
.mmx-director-root .mmx-track-row { border-bottom: 0; gap: 0; }
.mmx-director-root .mmx-track-row + .mmx-track-row { border-top: 1px solid var(--border-color,#444); }
.mmx-director-root .mmx-track-header-cell { background: #26282b; font-size: 11px; color: #c2c5ca; }
.mmx-director-root .mmx-subtrack-block { border-radius: 2px; }
.mmx-director-root .mmx-shot-block { background: #34384a; border-color: #687094; }
.mmx-director-root .mmx-subtrack-block.active { background: #3b4055; box-shadow: none; border-color: #a6b1df; }
.mmx-director-root .mmx-clip-img-cell { width: 64px; min-width: 64px; max-width: 64px; height: 44px; flex-basis:64px; }
.mmx-director-root .mmx-clip-img-cell img { width:100%;height:100%;object-fit:contain; background:#151515; }
.mmx-director-root .mmx-clip-vid-cell { width: 64px; min-width: 64px; max-width: 64px; height: 44px; flex-basis:64px; }
.mmx-director-root .mmx-clip-vid-cell video { width:100%;height:100%;object-fit:contain; background:#151515; }
.mmx-director-root .mmx-img-block, .mmx-director-root .mmx-vid-block, .mmx-director-root .mmx-aud-block { height:52px; }
.mmx-cache-button{font-size:9px;padding:1px 4px;border:1px solid #516779;border-radius:4px;background:#25343e;color:#a8d7cc;white-space:nowrap;cursor:pointer}
.mmx-cache-dialog{background:#1d2228;color:#e1e8ee;border:1px solid #3a444e;border-radius:12px;padding:0;width:min(460px,92vw);max-height:80vh;overflow:auto;font:13px system-ui;box-shadow:0 18px 50px rgba(0,0,0,.55)}
.mmx-cache-dialog::backdrop{background:rgba(8,10,13,.55)}
.mmx-cache-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:14px 16px 10px;border-bottom:1px solid #2c343d;position:sticky;top:0;background:#1d2228;z-index:1}
.mmx-cache-titles{display:flex;flex-direction:column;gap:2px}.mmx-cache-titles strong{font-size:14px}.mmx-cache-titles span{font-size:11.5px;color:#8ea2b4}
.mmx-cache-close{width:28px;height:28px;min-height:28px!important;padding:0!important;border:1px solid #3a444e!important;border-radius:7px!important;background:#262d35!important;color:#cfd8e0!important;font-size:16px!important;line-height:1;cursor:pointer}
.mmx-cache-close:hover{background:#323b45!important}
.mmx-cache-verdict{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin:12px 16px 4px;padding:10px 12px;border-radius:8px;border:1px solid #2f3a44;background:#232a31}
.mmx-cache-verdict strong{font-size:13px}.mmx-cache-verdict span{font-size:11.5px;color:#9fb0c0}
.mmx-cache-verdict.reused{border-color:#2f5446;background:#1c2a25}.mmx-cache-verdict.fresh{border-color:#5a4a2c;background:#2a251b}
.mmx-cache-group{margin:14px 16px 6px;font-size:10.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#7d8e9e}
.mmx-cache-list{margin:0 16px;border:1px solid #2c343d;border-radius:8px;overflow:hidden}
.mmx-cache-row{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:9px 12px;background:#20262d}
.mmx-cache-row+.mmx-cache-row{border-top:1px solid #2c343d}
.mmx-cache-text{display:flex;flex-direction:column;gap:2px;min-width:0}.mmx-cache-text strong{font-size:12.5px;font-weight:600}.mmx-cache-text small{font-size:11px;color:#8ea2b4;line-height:1.35}
.mmx-cache-pill{flex:none;font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:10px;letter-spacing:.02em}
.mmx-cache-pill.reused{background:#1f3d33;color:#7fd3b0}.mmx-cache-pill.fresh{background:#3d321c;color:#f0c674}.mmx-cache-pill.bypass{background:#2c333b;color:#9fb0c0}.mmx-cache-pill.partial{background:#24363d;color:#8cc7e0}
.mmx-cache-technical{margin:14px 16px 0}.mmx-cache-technical summary{cursor:pointer;font-size:12px;color:#b9c6d2}
.mmx-cache-technical .mmx-cache-group{margin:10px 0 4px}
.mmx-cache-technical table{border-collapse:collapse;width:100%;font-size:11.5px}.mmx-cache-technical th{font-weight:600;color:#7d8e9e;text-align:right;padding:4px 6px;border-bottom:1px solid #2c343d}.mmx-cache-technical th:first-child{text-align:left}
.mmx-cache-technical td{padding:4px 6px;border-bottom:1px solid #262d35;text-align:right;font-variant-numeric:tabular-nums}.mmx-cache-technical td:first-child{text-align:left;color:#cfd8e0}
.mmx-cache-technical td.zero{color:#4f5d6a}.mmx-cache-technical td.hit{color:#7fd3b0}.mmx-cache-technical td.miss{color:#f0c674}.mmx-cache-technical td.bypass{color:#9fb0c0}
.mmx-cache-technical p,.mmx-cache-foot{font-size:11px;color:#7d8e9e;line-height:1.45}
.mmx-cache-foot{margin:12px 16px 14px}
.mmx-director-root .mmx-clip-img-cell .mmx-ref-type-label { display:none; }

.mmx-reference-dialog { padding:16px;background:#24262b;color:#eee;border:1px solid #61697b;border-radius:8px;max-width:85vw; }
.mmx-reference-dialog::backdrop { background:#0009; }
.mmx-reference-dialog img { max-width:80vw;max-height:75vh;display:block;object-fit:contain; }
.mmx-director-root .mmx-track-row[hidden] { display:none; }
.mmx-director-root [hidden] { display:none!important; }

.mmx-director-root .mmx-multitrack-panel { min-height:0; padding:10px 12px 0; scrollbar-width:thin; border:1px solid #50565f; border-radius:7px; background:#25272b; }
.mmx-director-root .mmx-shot-top-bar .mmx-clip-mode-badge { display:none; }
.mmx-director-root .mmx-clip-val-badge { font-size:11px!important; }

.mmx-director-root .mmx-section { width:100%; box-sizing:border-box; border:1px solid #50565f; border-radius:7px; background:#262a30; margin:5px 0; }
.mmx-director-root .mmx-section > summary { display:flex; align-items:center; justify-content:space-between; padding:12px 14px; font-size:13px; font-weight:650; color:#ecedf0; cursor:pointer; list-style:none; }
.mmx-director-root .mmx-section > summary::after { content:'＋'; font-size:18px; color:#a7bed9; }
.mmx-director-root .mmx-section[open] > summary::after { content:'−'; }
.mmx-director-root .mmx-section-body { display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;padding:14px;border-top:1px solid #454c55; }
.mmx-director-root .mmx-section-intro { grid-column:1/-1;margin:0;color:#aeb8c5;font-size:12px;line-height:1.5; }
.mmx-director-root .mmx-section-body > details,.mmx-director-root .mmx-section-body > div,.mmx-director-root .mmx-section-body > fieldset { grid-column:1/-1; }
.mmx-director-root .mmx-field { display:flex; flex-direction:column; gap:6px; min-width:0; font-size:12px; color:#e1e7ef; }
.mmx-director-root .mmx-field small { color:#a8b3c2;line-height:1.45; }
.mmx-director-root .mmx-field > input:not([type=checkbox]),.mmx-director-root .mmx-field > select,.mmx-director-root .mmx-field > textarea { width:100%!important;min-width:0;box-sizing:border-box; }
.mmx-director-root .mmx-section input:not([type=checkbox]):not([type=range]),.mmx-director-root .mmx-section select,.mmx-director-root .mmx-section textarea { border:1px solid #58616e!important;background:#1d2229!important;color:#ecedf0!important;border-radius:5px!important;padding:8px!important; font:12px inherit; }
.mmx-director-root .mmx-section textarea { min-height:90px;resize:vertical; }
.mmx-director-root .mmx-section button { border:1px solid #596776;background:#323e4e;color:#ecedf0;border-radius:5px;padding:8px 11px;cursor:pointer; }
.mmx-director-root .mmx-section-body > button { align-self:start; }
.mmx-director-root .mmx-project-actions { display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;padding:14px;border-top:1px solid #454c55; }
.mmx-director-root .mmx-project-actions .mmx-field { padding:10px;background:#20252c;border:1px solid #454c55;border-radius:5px; }
.mmx-director-root .mmx-form-row { display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;align-items:end; }
.mmx-director-root .mmx-shot-sections { display:grid!important;grid-template-columns:1fr;gap:5px;align-items:stretch; }
.mmx-director-root .mmx-shot-sections > details[open] { flex-basis:auto; }
.mmx-director-root .mmx-shot-sections > details.mmx-section > summary { padding:12px 14px; }
.mmx-director-root .mmx-generation-bar { background:#293747;border:1px solid #607b96;border-radius:6px;padding:10px 14px; }
.mmx-director-root .mmx-generation-bar .mmx-field { display:grid;grid-template-columns:150px 200px 1fr;align-items:center; }
.mmx-director-root .mmx-generation-mode { padding:7px;border:1px solid #849eb8;border-radius:4px;background:#202b38;color:white; }
.mmx-director-root .mmx-shots-lane { position:relative; }
/* Compact editing desk: timeline first, readable segment prompt below. */
.mmx-director-root:not(.mmx-preview-node) { gap:8px; padding:8px; overflow-y:auto; }
.mmx-director-root:not(.mmx-preview-node) > * { flex-shrink:0; }
.mmx-director-root .mmx-multitrack-panel { max-height:none; }
.mmx-director-root .mmx-inspector { overflow:visible; }
.mmx-director-root .mmx-toolbar { gap:5px; }
.mmx-director-root .mmx-action-btn { padding:4px 7px; border-radius:3px; }
.mmx-director-root .mmx-track-header-cell { width:112px; min-width:112px; font-size:10px; }
.mmx-director-root .mmx-shot-block { height:152px; padding:7px 8px; background:#20262e; }
.mmx-director-root .mmx-shot-block.active { background:#263341!important; border-color:#92adc3!important; box-shadow:none; }
.mmx-director-root .mmx-shot-prompt-preview { white-space:normal; display:-webkit-box; -webkit-line-clamp:5; -webkit-box-orient:vertical; overflow:hidden; line-height:1.45; font-size:12px; }
.mmx-director-root .mmx-shot-cover { width:100%; height:54px; object-fit:contain; background:#15191e; flex-shrink:0; }
.mmx-director-root .mmx-shot-block:has(.mmx-shot-cover) .mmx-shot-prompt-preview { -webkit-line-clamp:2; }
.mmx-director-root .mmx-add-clip-card { height:152px; border-radius:2px; }
.mmx-director-root .mmx-inspector { flex:0 0 auto; gap:7px; }
.mmx-director-root .mmx-prompt-inspector { flex:0 0 auto; min-height:0; }
.mmx-director-root .mmx-prompt-inspector > .mmx-textarea { flex:none!important; height:136px!important; min-height:100px!important; max-height:300px; resize:vertical; border-radius:3px; padding:9px; font:12px/1.55 ui-monospace,Consolas,monospace; }
.mmx-director-root .mmx-prompt-mode-tabs { border-radius:3px; padding:1px; }
.mmx-director-root .mmx-prompt-mode-tab { border-radius:2px; padding:3px 9px; }
.mmx-director-root .mmx-prompt-mode-tab.active { background:#426780; }
.mmx-director-root .mmx-inspector-card-title { color:#afb6bf!important; font-size:10px; }
.mmx-director-root .mmx-timecode-display { color:#c5d7e4; background:#191d22; border-radius:2px; }
.mmx-director-root .mmx-local-refs-pool { border-radius:2px; padding:7px; }

/* Editing workspace: writing on the left, bounded tools on the right. */
.mmx-director-root:not(.mmx-preview-node) { container-type:inline-size; padding:14px;gap:14px;color:#e7edf5;background:#242628;font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif; }
.mmx-director-root button,.mmx-director-root select,.mmx-director-root input:not([type=range]):not([type=checkbox]) { font:inherit!important; }
.mmx-director-root button { transition:background .15s,border-color .15s; }
.mmx-director-root .mmx-action-btn { border:1px solid #454b53;border-radius:6px;background:#2e3238;color:#dce3ec;padding:7px 10px;min-height:32px; }
.mmx-director-root .mmx-action-btn:hover { background:#383f49;border-color:#687889; }
.mmx-director-root .mmx-action-btn.danger { background:transparent;color:#e79ba0;border-color:#664048; }
.mmx-director-root .mmx-toolbar { flex-direction:column;align-items:stretch;gap:8px;padding-bottom:0;border:0; }
.mmx-director-root .mmx-toolbar-left { gap:7px;flex-wrap:wrap; }
.mmx-director-root .mmx-toolbar-left label { font-size:13px!important; }
.mmx-director-root .mmx-toolbar-right { justify-content:flex-start;gap:14px; }
.mmx-director-root .mmx-toolbar-right > div:first-child { font-size:13px!important;color:#b9c9d9!important; }
.mmx-director-root .mmx-toolbar-right .mmx-language-select { margin-left:auto; }
.mmx-director-root .mmx-generation-bar { padding:10px 14px;background:#293139;border-color:#485967;border-left:3px solid #7eafcf; }
.mmx-director-root .mmx-generation-bar .mmx-field { grid-template-columns:155px 180px minmax(0,1fr);gap:14px; }
.mmx-director-root .mmx-generation-bar small { color:#bdc8d3;font-size:13px; }
.mmx-director-root .mmx-multitrack-panel { background:#1d2024;border-color:#4b525c;border-radius:8px; }
.mmx-director-root .mmx-track-header-cell { background:#20262d;color:#bfcbd8;font-size:12px;letter-spacing:.02em;align-self:stretch;height:auto;flex-shrink:0;z-index:60;box-shadow:-14px 0 0 #20262d; }
.mmx-director-root .mmx-track-row { border-color:#363d46; }
.mmx-director-root .mmx-shot-block { border-radius:5px;background:#29333e;border-color:#516373; }
.mmx-director-root .mmx-shot-block.active { background:#2c3b48!important;border-color:#86b8d8!important;box-shadow:inset 3px 0 #86b8d8; }
.mmx-director-root .mmx-shot-block.generation-selected { background:#25473a!important;border-color:#63b98a!important; }
.mmx-director-root .mmx-shot-block.generation-selected.active { box-shadow:inset 3px 0 #9ce0b5; }
.mmx-director-root .mmx-clip-selection { position:absolute;bottom:4px;right:4px;display:flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:0;background:transparent;border:0;cursor:pointer;z-index:3; }
.mmx-director-root .mmx-clip-selection input { margin:0;width:16px;height:16px;accent-color:#68ce91;cursor:pointer; }
.mmx-director-root .mmx-shot-prompt-preview { padding-right:32px; }
.mmx-director-root .mmx-clip-title { font-size:14px; }
.mmx-director-root .mmx-clip-duration { font-size:12px; }
.mmx-director-root .mmx-shot-top-bar .mmx-clip-mode-badge { display:inline-flex;background:#3b5367;color:#d9ebfa;font-size:10px;padding:2px 5px;border-radius:3px; }
.mmx-director-root .mmx-add-clip-card { border-radius:5px;color:#a5b7c8; }
.mmx-director-root .mmx-inspector { gap:14px;padding:0;background:transparent;border:0; }
.mmx-director-root .mmx-clip-name-row { display:flex;align-items:center;gap:10px;flex-wrap:wrap; }
.mmx-director-root .mmx-clip-header-actions { display:grid;grid-template-columns:repeat(2,minmax(120px,1fr));gap:8px;align-self:center; }
.mmx-director-root .mmx-clip-header-actions button { width:100%;min-height:38px; }
.mmx-director-root .mmx-inspector-header { gap:10px;padding:2px 0 12px;border-bottom:1px solid #444b53; }
.mmx-director-root .mmx-inspector-title { flex:1;gap:10px; }
.mmx-director-root .mmx-inspector-title > span { font-size:13px!important;color:#b5c3d2!important; }
.mmx-director-root .mmx-inspector-title input,.mmx-director-root .mmx-mode-select { padding:7px 9px!important;border-color:#4c5662!important;border-radius:5px!important; }
.mmx-director-root .mmx-validate-toggle { font-size:12px;padding:7px 9px;background:transparent!important;border:0; }
.mmx-director-root .mmx-edit-workspace { display:grid;grid-template-columns:minmax(0,1.5fr) minmax(380px,1fr);gap:18px;align-items:start; }
.mmx-director-root .mmx-edit-main { min-width:0;display:flex;flex-direction:column;gap:16px; }
.mmx-director-root .mmx-prompt-inspector { border:0;padding:0;gap:9px; }
.mmx-director-root .mmx-prompt-toolbar { padding:0;min-height:34px; }
.mmx-director-root .mmx-prompt-toolbar > div:first-child { color:#d6e3ef!important;font-size:14px!important;font-weight:650!important;letter-spacing:0;text-transform:none; }
.mmx-director-root .mmx-prompt-mode-tabs { background:#1e2227;border-radius:6px;padding:3px; }
.mmx-director-root .mmx-prompt-mode-tab { font-size:13px!important;padding:6px 10px;border-radius:4px;color:#b8c4d2; }
.mmx-director-root .mmx-prompt-mode-tab.active { background:#395b73;color:#f0f7ff; }
.mmx-director-root .mmx-prompt-inspector > .mmx-textarea { height:190px!important;min-height:140px!important;max-height:400px;padding:14px;font:15px/1.65 system-ui,sans-serif;border:1px solid #566371;border-radius:7px;background:#1c2025;color:#edf2f8; }
.mmx-director-root .mmx-prompt-char-count { font-size:12px;color:#a8b7c8; }
.mmx-director-root .mmx-structured-grid { height:260px;max-height:260px;min-height:200px!important;flex:none;gap:12px;scrollbar-width:thin; }
.mmx-director-root .mmx-structured-label { font:13px system-ui;color:#c6d6e6;letter-spacing:0; }
.mmx-director-root .mmx-structured-input,.mmx-director-root .mmx-structured-textarea { font:14px/1.5 system-ui;padding:9px;border-color:#536273; }
.mmx-director-root .mmx-basic-controls { border-top:1px solid #434b55;padding-top:14px;display:grid;gap:14px; }
.mmx-director-root .mmx-inspector-cards-grid { display:grid;grid-template-columns:1fr;gap:12px;margin:0; }
.mmx-director-root .mmx-inspector-card { padding:0;background:transparent;border:0;gap:6px; }
.mmx-director-root .mmx-inspector-card-title { font-size:12px!important;color:#b9c9d9!important;letter-spacing:.04em; }
.mmx-director-root .mmx-ctrl-item { flex-wrap:wrap;gap:8px; }
.mmx-director-root .mmx-ctrl-item label,.mmx-director-root .mmx-ctrl-unit { font-size:13px; }
.mmx-director-root .mmx-basic-controls input[type=text] { width:190px!important;font-family:ui-monospace,Consolas,monospace!important; }
.mmx-director-root .mmx-audio-control { display:flex;align-items:center;gap:12px;color:#c5d2df; }
.mmx-director-root .mmx-audio-control select { padding:6px 9px;border:1px solid #4c5662;border-radius:5px; }
.mmx-director-root .mmx-edit-tools { min-width:0;background:#202429;border:1px solid #46505b;border-radius:8px;overflow:hidden; }
.mmx-director-root .mmx-tools-heading { display:flex;justify-content:space-between;align-items:center;padding:12px 14px 9px;color:#d9e5f1;font-size:14px;font-weight:650; }
.mmx-director-root .mmx-tools-heading button { background:transparent;border:1px solid #4b5968;border-radius:5px;padding:3px 8px;color:#b9cbdc;font-size:12px!important;cursor:pointer; }
.mmx-director-root .mmx-tools-heading button[aria-pressed=true] { background:#354b5e;color:white; }
.mmx-director-root .mmx-edit-tools:not(.mmx-show-help) .mmx-field small { display:none; }
.mmx-director-root .mmx-edit-tools:not(.mmx-show-help) .mmx-project-actions .mmx-field small { display:block; }
.mmx-director-root .mmx-tool-tabs { display:flex;gap:2px;padding:0 9px 9px;border-bottom:1px solid #414a55; }
.mmx-director-root .mmx-tool-tabs button { flex:1;min-width:0;background:transparent;border:0;border-radius:5px;color:#b2c1d1;padding:8px 4px;font-size:13px!important;cursor:pointer; }
.mmx-director-root .mmx-tool-tabs button[aria-selected=true] { background:#354b5e;color:#f0f6fc;box-shadow:inset 0 -2px #87b6d7; }
.mmx-director-root .mmx-tool-tabs button:disabled { opacity:.4;cursor:default; }
.mmx-director-root .mmx-tool-content { display:block!important;max-height:440px;overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;scrollbar-color:#5d7186 #202429; }
.mmx-director-root .mmx-tool-content > .mmx-section { border:0;background:transparent;border-radius:0;margin:0; }
.mmx-director-root .mmx-tool-content > .mmx-section > summary { display:none; }
.mmx-director-root .mmx-tool-content > .mmx-section > .mmx-section-body { border:0;padding:14px;grid-template-columns:1fr;gap:16px; }
.mmx-director-root .mmx-section-intro { color:#c0cedc;font-size:13px;line-height:1.6; }
.mmx-director-root .mmx-field { font-size:14px;color:#e5edf6;gap:7px; }
.mmx-director-root .mmx-field small { font-size:12px;color:#aebdcd;line-height:1.6; }
.mmx-director-root .mmx-section input:not([type=checkbox]):not([type=range]),.mmx-director-root .mmx-section select,.mmx-director-root .mmx-section textarea { padding:9px!important;border-color:#536273!important; }
.mmx-director-root .mmx-form-row { grid-template-columns:1fr;gap:10px;margin-bottom:12px; }
.mmx-director-root .mmx-local-refs-pool { padding:12px;background:#2a3037;border:1px solid #485562;border-radius:7px; }
.mmx-director-root .mmx-quick-tag-btn { font-size:13px!important;min-height:28px; }
@container (max-width:1000px) { .mmx-edit-workspace { grid-template-columns:minmax(0,1fr) 310px!important;gap:12px!important; } .mmx-generation-bar .mmx-field { grid-template-columns:145px 160px!important; } .mmx-generation-bar small { grid-column:1/-1; } }
@container (max-width:780px) { .mmx-edit-workspace { grid-template-columns:1fr!important; } .mmx-tool-content { max-height:300px!important; } }
.mmx-director-root .mmx-toolbar { flex-direction:row;flex-wrap:wrap;align-items:center;gap:12px;padding:10px 12px;background:#20252b;border:1px solid #49545f;border-radius:8px; }
.mmx-director-root .mmx-toolbar-left { flex:0 0 auto; }
.mmx-director-root .mmx-toolbar-right { flex:1;flex-wrap:wrap;min-width:280px;gap:12px; }
.mmx-director-root .mmx-toolbar-right .mmx-language-select { margin-left:auto; }
.mmx-director-root .mmx-generation-bar { display:flex;flex-wrap:wrap;align-items:center;gap:12px; }
.mmx-director-root .mmx-generation-bar > .mmx-field { flex:1;min-width:280px; }
.mmx-director-root .mmx-generation-bar > label:not(.mmx-field) { border-left:1px solid #536473;padding-left:14px;font-size:13px!important;white-space:nowrap; }
.mmx-director-root .mmx-local-refs-title { align-items:center;gap:8px;flex-wrap:wrap; }
.mmx-director-root .mmx-local-refs-title button { margin-left:auto;font-size:12px!important;padding:4px 8px; }
.mmx-director-root .mmx-export-options { display:flex!important;flex-direction:row;flex-wrap:wrap;align-items:center;gap:8px!important; }
.mmx-director-root .mmx-export-options input { width:16px!important;min-width:16px;height:16px;accent-color:#7eafcf; }
.mmx-director-root .mmx-export-options small { flex-basis:100%; }
.mmx-director-root .mmx-project-workspace { border:1px solid #414e5a;border-radius:8px;background:#23292f; }
.mmx-director-root .mmx-project-workspace > summary { display:flex;align-items:center;gap:14px;padding:12px 14px;font-weight:600;cursor:pointer;list-style:none; }
.mmx-director-root .mmx-project-workspace > summary::after { content:'+';margin-left:auto;font-size:20px;color:#a9c5db; }
.mmx-director-root .mmx-project-workspace[open] > summary::after { content:'−'; }
.mmx-director-root .mmx-project-workspace > summary span { font-size:12px;font-weight:400;color:#b4c2cf; }
.mmx-director-root .mmx-project-workspace > summary [data-project-action="clear-vram"] { margin-left:auto;flex-shrink:0;width:auto;min-height:30px;padding:5px 10px; }
.mmx-director-root .mmx-project-workspace > summary:has([data-project-action="clear-vram"])::after { margin-left:0; }
.mmx-director-root .mmx-project-workspace > .mmx-section-body { display:grid;grid-template-columns:1fr;gap:16px;padding:16px;border-top:1px solid #414e5a; }
.mmx-director-root .mmx-project-workspace > .mmx-section-body > details { grid-column:1/-1;align-self:start;margin:0;border:0;border-top:1px solid #414e5a;border-radius:0;background:transparent; }
.mmx-director-root .mmx-timeline-audio { display:flex !important;flex-direction:row !important;align-items:center;flex-wrap:wrap;gap:20px !important;margin:10px 0 14px;padding:12px;border:1px solid #414e5a;border-radius:6px;background:var(--mmx-soft,#242a30); }
.mmx-director-root .mmx-timeline-audio .mmx-project-audio-fade { justify-content:flex-start; }
.mmx-director-root .mmx-inspector-header .mmx-validate-toggle { padding:7px 10px;border:1px solid #658675;background:#283b33;color:#bde8d0; }
.mmx-director-root .mmx-timecode-display { width:145px; }
.mmx-director-root .mmx-project-group { display:flex;flex-direction:column;gap:10px;min-width:0; }
.mmx-director-root .mmx-project-group + .mmx-project-group { border-left:1px solid #414e5a;padding-left:24px; }
.mmx-director-root .mmx-project-group > h3 { font-size:13px;margin:0;color:#c6d8e7; }
.mmx-director-root .mmx-clip-type-label { display:inline-flex;align-items:center;padding:5px 10px;border:1px solid #506477;border-radius:5px;background:#2b3a47;color:#cce0ef;font-size:13px; }
.mmx-director-root .mmx-project-group textarea { min-height:68px;height:68px;resize:vertical; }
.mmx-director-root .mmx-project-placement { flex-direction:row;align-items:center;gap:12px; }
.mmx-director-root .mmx-project-placement select { width:150px!important; }
.mmx-director-root .mmx-project-audio-fade { display:flex;align-items:center;justify-content:space-between;gap:12px; }
.mmx-director-root .mmx-project-audio-fade input { width:100px; }
.mmx-director-root .mmx-project-workspace small { display:none; }
.mmx-director-root .mmx-project-workspace .mmx-section-intro { display:none; }
.mmx-director-root .mmx-project-workspace .mmx-section > summary { padding:12px 0 0; }
.mmx-director-root .mmx-project-library button, .mmx-server-project-dialog-actions button { cursor:pointer;transition:background .15s,border-color .15s,box-shadow .15s; }
.mmx-director-root .mmx-project-library button:hover:not(:disabled), .mmx-server-project-dialog-actions button:hover:not(:disabled) { background:#435d76;border-color:#8ab9df;box-shadow:0 0 12px #78b7eb33; }
.mmx-director-root .mmx-project-library button:active:not(:disabled), .mmx-server-project-dialog-actions button:active:not(:disabled) { background:#263e53;box-shadow:inset 0 2px 5px #0006; }
.mmx-director-root .mmx-project-library button:focus-visible, .mmx-server-project-dialog-actions button:focus-visible { outline:2px solid #8ab9df;outline-offset:3px; }
.mmx-director-root .mmx-project-library button:disabled, .mmx-server-project-dialog-actions button:disabled { opacity:.65;cursor:wait; }
.mmx-director-root .mmx-project-actions button { cursor:pointer;transition:background .15s,border-color .15s,box-shadow .15s; }
.mmx-director-root .mmx-project-actions button:hover:not(:disabled) { background:#435d76;border-color:#8ab9df;box-shadow:0 0 12px #78b7eb33; }
.mmx-director-root .mmx-project-actions button:active:not(:disabled) { background:#263e53;box-shadow:inset 0 2px 5px #0006; }
.mmx-director-root .mmx-project-actions button:focus-visible { outline:2px solid #8ab9df;outline-offset:3px; }
.mmx-director-root .mmx-project-actions button:disabled { opacity:.65;cursor:wait; }
.mmx-picker-heading { color:#c6d8e7;font-size:12px;margin:14px 0 6px; }
.mmx-picker-intro { color:#adbac7;font-size:12px; }
.mmx-type-picker { width:min(880px,calc(100vw - 48px));max-width:880px;max-height:calc(100vh - 48px); }
.mmx-type-picker .mmx-modal-body { padding:14px 16px;gap:8px;scrollbar-color:#536171 #1b2127;scrollbar-width:thin; }
.mmx-type-picker .mmx-picker-heading { margin:6px 0 0;font-size:12px; }
.mmx-type-picker .mmx-picker-intro { margin:0 0 4px; }
.mmx-type-picker .mmx-type-modal-grid { gap:8px; }
.mmx-type-picker .mmx-type-modal-grid > button:last-child:nth-child(odd) { grid-column:1/-1; }
.mmx-type-picker .mmx-type-modal-btn { padding:10px 12px;background:#242b32;border-color:#4c5a67; }
.mmx-type-picker .mmx-type-modal-btn-title { font-size:13px; }
.mmx-type-picker .mmx-type-modal-btn-desc { font-size:12px;line-height:1.3;color:#b6c3d0; }
.mmx-video-input-resolution { border:1px solid #414e5a;padding:12px;border-radius:6px; }
.mmx-server-project-list { width:100%;min-height:140px;padding:8px;background:#1d2229;color:#ecedf0;border:1px solid #596979;border-radius:5px; }
.mmx-server-project-list option { padding:10px; }
.mmx-server-project-dialog-actions { display:flex;justify-content:flex-end;gap:12px;margin-top:16px; }
.mmx-director-root .mmx-shared-prompt { display:flex;flex-direction:column;gap:8px;flex-shrink:0;padding:0 0 14px;border-bottom:1px solid #414e5a; }
.mmx-director-root .mmx-shared-prompt-header { display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap; }
.mmx-director-root .mmx-shared-prompt-header h3 { margin:0;font-size:14px;color:#d1e1ec; }
.mmx-director-root .mmx-shared-prompt textarea { box-sizing:border-box;width:100%;height:72px;min-height:64px;resize:vertical;border:1px solid #4c5966;border-radius:6px;padding:10px 12px;background:#1d2229;color:#ecedf0;font:inherit; }
.mmx-director-root .mmx-shared-prompt-header .mmx-project-placement { font-size:12px; }
.mmx-director-root .mmx-project-workspace .mmx-project-group { flex-direction:row;align-items:center;flex-wrap:wrap;gap:24px; }
@container (max-width:600px) { .mmx-project-workspace > summary span { display:none; } }
/* Range rows in the clip tools: label and value on one line, slider below. */
.mmx-director-root .mmx-edit-tools .mmx-field:has(> input[type=range]) { display:grid!important;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:4px 10px;font-size:12px;color:#b9c6d2; }
.mmx-director-root .mmx-edit-tools .mmx-field:has(> input[type=range]) > input[type=range] { grid-column:1/-1;grid-row:2;width:100%;margin:0;accent-color:var(--mmx-accent,#a396ff); }
.mmx-director-root .mmx-edit-tools .mmx-field:has(> input[type=range]) > span { grid-column:2;grid-row:1;min-width:42px;padding:1px 6px;border:1px solid #39434d;border-radius:5px;background:#1b2026;color:#e8edf2;text-align:right;font-variant-numeric:tabular-nums;font-size:11.5px; }
/* Clip LoRA cards */
.mmx-director-root .mmx-settings-bar { display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px;padding:7px 12px;margin:0 0 8px;background:#1d2228;border:1px solid #333d47;border-radius:8px; }
.mmx-director-root .mmx-setting { display:inline-flex;align-items:center;gap:6px;margin:0;font-size:12px;color:#e1e7ef;white-space:nowrap; }
.mmx-director-root .mmx-setting > span:first-child { font-size:10.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:#8ea2b4; }
.mmx-director-root .mmx-setting select,.mmx-director-root .mmx-setting input { height:26px;min-height:26px;padding:0 6px!important;border:1px solid #46525e;border-radius:6px;background:#1b2026;color:#e8edf2;font-size:12px!important; }
.mmx-director-root .mmx-setting select { max-width:128px; }
.mmx-director-root .mmx-setting-size { display:inline-flex;align-items:center;gap:4px;color:#8ea2b4; }
.mmx-director-root .mmx-setting-divider { width:1px;height:20px;background:#3a444e; }
.mmx-director-root .mmx-setting-external select:disabled,.mmx-director-root .mmx-setting-external input:disabled { opacity:.45;cursor:not-allowed; }
.mmx-director-root .mmx-setting-pill { display:inline-flex;align-items:center;height:22px;padding:0 8px;border:1px dashed #4b5866;border-radius:11px;font-size:11px;color:#9fb0c0; }
.mmx-director-root .mmx-switch-row { display:grid;grid-template-columns:auto minmax(0,1fr);gap:10px;align-items:start;padding:8px 0;cursor:pointer; }
.mmx-director-root .mmx-switch-row.disabled { opacity:.55;cursor:default; }
.mmx-director-root .mmx-switch-row .mmx-lora-switch { margin-top:1px; }
.mmx-director-root .mmx-switch-text { display:flex;flex-direction:column;gap:2px;min-width:0; }
.mmx-director-root .mmx-switch-text strong { font-size:12.5px;color:#e8edf2;font-weight:600; }
.mmx-director-root .mmx-switch-text small { font-size:11.5px;color:#9fb0c0;line-height:1.4; }
.mmx-director-root .mmx-switch-group-title { display:flex;flex-direction:column;gap:2px;padding:6px 0 4px;border-bottom:1px solid #2c343d;margin-bottom:2px; }
.mmx-director-root .mmx-switch-group-title strong { font-size:12.5px;color:#e8edf2; }
.mmx-director-root .mmx-switch-group-title span { font-size:11px;color:#8ea2b4; }
.mmx-director-root .mmx-switch-group { display:flex;flex-direction:column;margin:6px 0 4px;padding:4px 12px;border:1px solid #333d47;border-radius:8px;background:#1d2228; }
.mmx-director-root .mmx-switch-group .mmx-continuity-mode-note { margin:2px 0 8px;padding-left:42px;font-size:11.5px;color:#9fb0c0;line-height:1.4; }
.mmx-director-root .mmx-form-grid { display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px 14px;margin:6px 0; }
.mmx-director-root .mmx-look-section { margin-top:12px;padding:10px 12px 12px;border:1px solid #333d47;border-radius:8px;background:#1d2228; }
.mmx-director-root .mmx-look-head { display:flex;align-items:center;gap:8px;margin-bottom:4px; }
.mmx-director-root .mmx-look-head strong { font-size:12.5px;color:#e8edf2; }
.mmx-director-root .mmx-look-badge { font-size:10px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#1b1530;background:var(--mmx-accent,#a396ff);border-radius:4px;padding:1px 6px; }
.mmx-director-root .mmx-look-section .mmx-continuity-mode-note { margin:0 0 8px;font-size:11.5px;color:#9fb0c0;line-height:1.4; }
.mmx-director-root .mmx-look-stage { position:relative;width:fit-content;max-width:100%;margin:0 auto;border-radius:6px;overflow:hidden;background:#111418;min-height:90px; }
.mmx-director-root .mmx-look-stage.mmx-look-missing { width:auto; }
.mmx-director-root .mmx-look-canvas { display:block;width:auto;height:auto;max-width:100%;max-height:300px; }
.mmx-director-root .mmx-look-canvas { cursor:grab;touch-action:none; }
.mmx-director-root .mmx-look-canvas:active { cursor:grabbing; }
.mmx-director-root .mmx-look-zoom { position:absolute;right:6px;bottom:6px;display:flex;gap:2px;padding:2px;border-radius:6px;background:rgba(0,0,0,.55); }
.mmx-director-root .mmx-look-zoom button { height:20px;min-width:26px;padding:0 5px!important;border:0!important;border-radius:4px!important;background:transparent!important;color:#dfe6ee!important;font-size:11px!important;font-weight:600;cursor:pointer; }
.mmx-director-root .mmx-look-zoom button.active { background:#3d4f63!important;color:#fff!important; }
.mmx-director-root .mmx-look-labels { position:absolute;left:0;right:0;top:6px;display:flex;justify-content:space-between;padding:0 8px;pointer-events:none; }
.mmx-director-root .mmx-look-labels span { font-size:10.5px;font-weight:600;color:#fff;background:rgba(0,0,0,.55);padding:2px 6px;border-radius:4px; }
.mmx-director-root .mmx-look-empty { display:flex;align-items:center;justify-content:center;min-height:90px;padding:14px;text-align:center;font-size:11.5px;color:#8ea2b4; }
.mmx-director-root .mmx-look-empty[hidden] { display:none; }
.mmx-director-root .mmx-look-missing .mmx-look-canvas,.mmx-director-root .mmx-look-missing .mmx-look-labels,.mmx-director-root .mmx-look-missing .mmx-look-zoom { display:none; }
.mmx-director-root .mmx-antiburn-note { margin:2px 0 8px;padding:6px 10px;border-left:3px solid #8b7bf0;border-radius:4px;background:#22232e;font-size:11.5px;color:#b9c3cf;line-height:1.4; }
.mmx-director-root .mmx-look-actions { display:flex;align-items:center;gap:10px;margin:2px 0 8px;flex-wrap:wrap; }
.mmx-director-root .mmx-calib-status { flex:1;min-width:180px;font-size:11px;color:#b9c3cf;line-height:1.4; }
.mmx-director-root .mmx-calib-btn { height:28px;padding:0 12px!important;border-radius:6px!important;border:1px solid #6b5a2a!important;background:#3a3220!important;color:#f6dfa4!important;font-size:12px!important;font-weight:600;cursor:pointer; }
.mmx-director-root .mmx-calib-btn:disabled { opacity:.6;cursor:default; }
.mmx-director-root .mmx-look-readout { display:flex;flex-wrap:wrap;gap:4px 14px;margin:8px 0 2px;font-size:11px;color:#9fb0c0;font-variant-numeric:tabular-nums; }
.mmx-director-root .mmx-look-readout:empty { display:none; }
.mmx-director-root .mmx-look-readout b { color:#e8edf2;font-weight:600; }
.mmx-director-root .mmx-look-readout em { font-style:normal;margin-left:3px;color:#9fb0c0; }
.mmx-director-root .mmx-look-readout em.up { color:#f0c674; }
.mmx-director-root .mmx-look-readout em.down { color:#7fb8e6; }
.mmx-director-root .mmx-look-readout small { flex-basis:100%;font-size:10.5px;color:#7d8e9e; }
.mmx-director-root .mmx-look-controls { display:flex;flex-direction:column;gap:2px;margin-top:8px; }
.mmx-director-root .mmx-look-row { display:grid;grid-template-columns:92px minmax(0,1fr) 92px 24px;align-items:center;gap:8px;font-size:11.5px;color:#b9c6d2; }
.mmx-director-root .mmx-look-row input[type=range] { width:100%;margin:0;accent-color:var(--mmx-accent,#a396ff); }
.mmx-director-root .mmx-look-row output { text-align:right;font-variant-numeric:tabular-nums;color:#8ea2b4;font-size:11px;white-space:nowrap; }
.mmx-director-root .mmx-look-row.changed span,.mmx-director-root .mmx-look-row.changed output { color:#e8edf2; }
.mmx-director-root .mmx-look-reset { width:24px!important;height:22px!important;min-height:22px!important;padding:0!important;border:1px solid transparent!important;border-radius:5px!important;background:transparent!important;color:#6f8090!important;cursor:pointer;font-size:13px!important;line-height:1;visibility:hidden; }
.mmx-director-root .mmx-look-row.changed .mmx-look-reset { visibility:visible;color:#dfe7ee!important;border-color:#4b5866!important; }
.mmx-director-root .mmx-look-row.changed .mmx-look-reset:hover { background:#2c343d!important; }
.mmx-director-root .mmx-look-reset-all { align-self:flex-end;margin-top:6px;height:26px!important;min-height:26px!important;padding:0 10px!important;border:1px solid #4b5866!important;border-radius:6px!important;background:#2c343d!important;color:#dfe7ee!important;font-size:11.5px!important;cursor:pointer; }
.mmx-director-root .mmx-lora-auto { border-left-color:#5fb39a; }
.mmx-director-root .mmx-lora-auto-name { display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 8px;min-width:0;font-size:12.5px;color:#e8edf2; }
.mmx-director-root .mmx-lora-auto-name small { flex-basis:100%;font-size:11px;color:#8ea2b4;overflow:hidden;text-overflow:ellipsis;white-space:nowrap; }
.mmx-director-root .mmx-auto-badge { font-size:10px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#0f2a22;background:#5fb39a;border-radius:4px;padding:1px 6px; }
.mmx-director-root .mmx-lora-auto .mmx-lora-card-head { grid-template-columns:auto minmax(0,1fr); }
.mmx-director-root .mmx-lora-auto-note { font-size:11px;color:#8ea2b4;line-height:1.4;padding-left:40px; }
.mmx-director-root .mmx-lora-missing .mmx-lora-auto-name small { color:#e6a36f;white-space:normal; }
.mmx-director-root .mmx-legacy-note { display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:10px;padding:8px 10px;border:1px dashed #6b5a3a;border-radius:6px;font-size:11.5px;color:#e6cf9f; }
.mmx-director-root .mmx-lora-list { display:flex;flex-direction:column;gap:8px;margin:4px 0 10px; }
.mmx-director-root .mmx-lora-empty { padding:12px;border:1px dashed #3f4953;border-radius:8px;color:#8ea2b4;font-size:12px;text-align:center; }
.mmx-director-root .mmx-lora-card { display:flex;flex-direction:column;gap:8px;padding:10px 12px;border:1px solid #39434d;border-left:3px solid var(--mmx-accent,#a396ff);border-radius:8px;background:#1f252b;transition:opacity .15s,border-color .15s; }
.mmx-director-root .mmx-lora-card[data-enabled="false"] { border-left-color:#4b5866;opacity:.6; }
.mmx-director-root .mmx-lora-card-head { display:grid;grid-template-columns:auto minmax(0,1fr) auto auto;align-items:center;gap:8px; }
.mmx-director-root .mmx-lora-switch { position:relative;display:inline-flex;width:32px;height:18px;flex:none;cursor:pointer; }
.mmx-director-root .mmx-lora-switch input { position:absolute;inset:0;width:100%!important;height:100%;margin:0;opacity:0;cursor:pointer;z-index:1; }
.mmx-director-root .mmx-lora-switch-track { width:32px;height:18px;border-radius:9px;background:#3a444e;transition:background .15s;position:relative; }
.mmx-director-root .mmx-lora-switch-track::after { content:'';position:absolute;top:2px;left:2px;width:14px;height:14px;border-radius:50%;background:#cfd8e0;transition:transform .15s; }
.mmx-director-root .mmx-lora-switch input:checked + .mmx-lora-switch-track { background:var(--mmx-accent,#a396ff); }
.mmx-director-root .mmx-lora-switch input:checked + .mmx-lora-switch-track::after { transform:translateX(14px);background:#fff; }
.mmx-director-root .mmx-lora-switch input:focus-visible + .mmx-lora-switch-track { outline:2px solid var(--mmx-accent,#a396ff);outline-offset:2px; }
.mmx-director-root .mmx-lora-card select.mmx-lora-file { width:100%;min-width:0;height:30px;min-height:30px;padding:0 6px!important;line-height:28px;font-size:12.5px!important;border:1px solid #46525e;border-radius:6px;background:#1b2026;color:#e8edf2;font-size:12.5px;text-overflow:ellipsis; }
.mmx-director-root .mmx-lora-icon { width:28px;height:28px;min-height:28px;padding:0;display:inline-flex;align-items:center;justify-content:center;border:1px solid #4b5866;border-radius:6px;background:#2c343d;color:#dfe7ee;font-size:13px;font-weight:700;line-height:1;cursor:pointer; }
.mmx-director-root .mmx-lora-icon:hover:not(:disabled) { border-color:#8ab9df;background:#36414c; }
.mmx-director-root .mmx-lora-icon:disabled { opacity:.4;cursor:default; }
.mmx-director-root .mmx-lora-remove { font-size:16px; }
.mmx-director-root .mmx-lora-remove:hover:not(:disabled) { border-color:#d0707d;background:#43272e;color:#ffe0e4; }
.mmx-director-root .mmx-lora-card-body { display:grid;grid-template-columns:auto minmax(0,1fr) 68px;align-items:center;gap:10px;padding-left:40px; }
.mmx-director-root .mmx-lora-strength-label { font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:#8ea2b4; }
.mmx-director-root .mmx-lora-slider { width:100%;margin:0;accent-color:var(--mmx-accent,#a396ff); }
.mmx-director-root .mmx-lora-card input.mmx-lora-strength { width:68px!important;height:28px;min-height:28px;padding:0 6px!important;line-height:26px;border:1px solid #46525e;border-radius:6px;background:#1b2026;color:#e8edf2;font-size:12.5px;text-align:right;font-variant-numeric:tabular-nums; }
.mmx-director-root .mmx-lora-info { display:flex;gap:10px;align-items:flex-start;padding:8px;border-top:1px dashed #39434d;max-height:220px;overflow:auto; }
.mmx-director-root .mmx-lora-info[hidden] { display:none; }
.mmx-director-root .mmx-lora-info img { max-width:140px;border-radius:6px; }
.mmx-director-root .mmx-lora-info pre { margin:0;white-space:pre-wrap;word-break:break-word;font-size:11px;color:#b9c6d2; }
.mmx-director-root .mmx-lora-add { width:100%;height:34px;border:1px dashed #4b5866;border-radius:8px;background:transparent;color:#c8d4de;font-size:12.5px;font-weight:600;cursor:pointer; }
.mmx-director-root .mmx-lora-add:hover:not(:disabled) { border-color:var(--mmx-accent,#a396ff);color:#fff;background:rgba(147,129,248,.07); }
.mmx-director-root .mmx-lora-add:disabled { opacity:.5;cursor:default; }
@container (max-width:420px) { .mmx-director-root .mmx-lora-card-body { padding-left:0; } }
/* Structured prompt: one card per official section, synced with the raw text */
.mmx-director-root .mmx-sp-bar { display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin:2px 0 8px; }
.mmx-director-root .mmx-sp-bar .mmx-quick-tags { display:flex;flex-wrap:wrap;gap:6px;min-width:0; }
.mmx-director-root .mmx-sp-fill { flex:none;height:28px;padding:0 12px;border:1px solid #4b5866;border-radius:6px;background:#2c343d;color:#dfe7ee;font-size:12px;font-weight:600;cursor:pointer;white-space:nowrap; }
.mmx-director-root .mmx-sp-fill:hover:not(:disabled) { border-color:var(--mmx-accent,#a396ff);background:#36414c; }
.mmx-director-root .mmx-sp-grid { display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;align-content:start;overflow:auto;min-height:0;flex:1; }
.mmx-director-root .mmx-sp-card { grid-column:1/-1;display:flex;flex-direction:column;gap:6px;padding:9px 11px 10px;border:1px solid #39434d;border-radius:8px;background:#1b2026;cursor:text;transition:border-color .12s,box-shadow .12s; }
.mmx-director-root .mmx-sp-card.mmx-sp-half { grid-column:auto; }
.mmx-director-root .mmx-sp-card:focus-within { border-color:var(--mmx-accent,#a396ff);box-shadow:0 0 0 2px rgba(163,150,255,.15); }
.mmx-director-root .mmx-sp-head { display:flex;align-items:baseline;justify-content:space-between;gap:8px; }
.mmx-director-root .mmx-sp-title { font-size:12.5px;font-weight:700;color:#e2e8f0; }
.mmx-director-root .mmx-sp-key { font:10.5px ui-monospace,Consolas,monospace;color:#7d90a1;background:none;padding:0; }
.mmx-director-root textarea.mmx-sp-input { width:100%;min-height:20px;padding:0!important;border:0!important;background:transparent!important;box-shadow:none!important;outline:none;resize:none;overflow:hidden;color:#e8edf2;font:13px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;user-select:text; }
.mmx-director-root textarea.mmx-sp-input::placeholder { color:#5f6f7e; }
.mmx-director-root .mmx-sp-hidden-note { grid-column:1/-1;margin:0;font-size:11.5px;color:#9fb2c3; }
.mmx-director-root .mmx-ref-slot { margin-left:4px;padding:1px 5px;border-radius:4px;background:rgba(0,0,0,.28);font:600 10px ui-monospace,Consolas,monospace;opacity:.9;white-space:nowrap; }
.mmx-director-root .mmx-local-ref-item.mmx-ref-memory { cursor:default;color:#bff0e3;background:rgba(45,180,150,.14)!important;border:1px solid rgba(45,180,150,.45)!important; }
.mmx-director-root .mmx-quick-tag-btn.mmx-tag-memory { color:#7fd8c4;background:rgba(45,180,150,.08);border-color:rgba(45,180,150,.3); }
.mmx-director-root .mmx-memory-auto-note { margin-top:8px;border:1px solid #2f5a52;border-radius:8px;background:#172522; }
.mmx-director-root .mmx-memory-auto-note summary { padding:6px 10px;font-size:12px;font-weight:600;color:#9fe3d2;cursor:pointer; }
.mmx-director-root .mmx-memory-auto-note pre, .mmx-director-root .mmx-memory-preview pre { margin:0;padding:8px 10px;white-space:pre-wrap;word-break:break-word;font:11.5px/1.5 ui-monospace,Consolas,monospace;color:#c6ece2;user-select:text; }
@container (max-width:900px) { .mmx-director-root .mmx-sp-grid { grid-template-columns:1fr; } }

/* Clip memory */
.mmx-director-root .mmx-memory { display:flex;flex-direction:column;gap:10px; }
.mmx-director-root .mmx-memory-card { display:flex;flex-direction:column;gap:8px;padding:10px 12px;border:1px solid #39434d;border-left:3px solid #2db496;border-radius:8px;background:#1f252b; }
.mmx-director-root .mmx-memory-card[data-enabled="false"] { opacity:.6;border-left-color:#4b5866; }
.mmx-director-root .mmx-memory-card.mmx-memory-invalid { border-left-color:#e06b7a; }
.mmx-director-root .mmx-memory-head { display:grid;grid-template-columns:auto auto minmax(0,1fr) auto;align-items:center;gap:8px; }
.mmx-director-root .mmx-memory-tag { font:600 11px ui-monospace,Consolas,monospace;color:#7fd8c4;background:rgba(45,180,150,.1);border:1px solid rgba(45,180,150,.35);border-radius:5px;padding:2px 6px;white-space:nowrap; }
.mmx-director-root .mmx-memory-card select.mmx-memory-source { width:100%;min-width:0;height:30px;min-height:30px;padding:0 6px!important;line-height:28px;font-size:12.5px!important;border:1px solid #46525e;border-radius:6px;background:#1b2026;color:#e8edf2; }
.mmx-director-root .mmx-memory-modes { display:inline-flex;align-self:flex-start;padding:2px;border:1px solid #39434d;border-radius:7px;background:#1b2026; }
.mmx-director-root .mmx-memory-modes button { height:26px;padding:0 12px;border:0;border-radius:5px;background:transparent;color:#9fb2c3;font-size:12px;font-weight:600;cursor:pointer; }
.mmx-director-root .mmx-memory-modes button.active { background:#2c4a44;color:#dff7f1; }
.mmx-director-root .mmx-memory-strip { position:absolute;inset:0;width:100%;height:100%;object-fit:fill;opacity:.85;pointer-events:none; }
.mmx-director-root .mmx-memory-pending { position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:11.5px;color:#e8c06a;pointer-events:none; }
.mmx-director-root .mmx-memory-track:has(.mmx-memory-strip) { height:46px; }
.mmx-director-root .mmx-memory-track:has(.mmx-memory-strip) .mmx-memory-window { background:rgba(45,180,150,.18);box-shadow:0 0 0 999px rgba(10,14,18,.55); }
.mmx-director-root .mmx-memory-track { position:relative;height:26px;border-radius:6px;background:repeating-linear-gradient(90deg,#252c33 0 10px,#222930 10px 20px);border:1px solid #39434d;overflow:hidden; }
.mmx-director-root .mmx-memory-window { position:absolute;top:0;bottom:0;background:rgba(45,180,150,.35);border-left:2px solid #2db496;border-right:2px solid #2db496;pointer-events:none; }
.mmx-director-root .mmx-memory-track:has(.mmx-memory-strip) input.mmx-memory-thumb::-webkit-slider-thumb { height:46px;margin-top:0; }
.mmx-director-root .mmx-memory-track:has(.mmx-memory-strip) input.mmx-memory-thumb::-moz-range-thumb { height:42px; }
.mmx-director-root input.mmx-memory-thumb { position:absolute;inset:0;width:100%;height:100%;margin:0;background:none;pointer-events:none;-webkit-appearance:none;appearance:none; }
.mmx-director-root input.mmx-memory-thumb::-webkit-slider-runnable-track { background:none;height:100%; }
.mmx-director-root input.mmx-memory-thumb::-webkit-slider-thumb { -webkit-appearance:none;pointer-events:auto;width:12px;height:26px;margin-top:0;border-radius:4px;background:#dff7f1;border:2px solid #2db496;cursor:ew-resize; }
.mmx-director-root input.mmx-memory-thumb::-moz-range-thumb { pointer-events:auto;width:10px;height:28px;border-radius:4px;background:#dff7f1;border:2px solid #2db496;cursor:ew-resize; }
.mmx-director-root input.mmx-memory-thumb::-moz-range-track { background:none; }
.mmx-director-root .mmx-memory-readout { font:11.5px ui-monospace,Consolas,monospace;color:#9fb2c3; }
.mmx-director-root .mmx-memory-card input.mmx-memory-note { width:100%;height:30px;min-height:30px;padding:0 8px!important;border:1px solid #46525e;border-radius:6px;background:#1b2026;color:#e8edf2;font-size:12.5px!important; }
.mmx-director-root .mmx-memory-problem { margin:0;font-size:12px;color:#ffc9cf; }
.mmx-director-root .mmx-memory-budget { font-size:12px;color:#9fb2c3; }
.mmx-director-root .mmx-memory-budget.over { color:#ffb36b; }
.mmx-director-root .mmx-memory-actions { display:flex;flex-direction:column;gap:6px; }
.mmx-director-root .mmx-memory-empty { margin:0;font-size:12px;color:#8ea2b4; }
.mmx-director-root .mmx-memory-preview { border:1px solid #2f5a52;border-radius:8px;background:#172522; }
.mmx-director-root .mmx-memory-preview-title { padding:6px 10px 0;font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:#7fd8c4; }
.mmx-director-root .mmx-memory-badge { flex:none;padding:1px 6px;border-radius:5px;background:rgba(45,180,150,.18);border:1px solid rgba(45,180,150,.45);color:#9fe3d2;font-size:10.5px;font-weight:700;white-space:nowrap; }
.mmx-director-root .mmx-tab-count { display:inline-flex;align-items:center;justify-content:center;min-width:16px;height:16px;margin-left:5px;padding:0 4px;border-radius:8px;background:#2db496;color:#08201b;font-size:10px;font-weight:800; }
/* Project panel (redesigned) */
.mmx-director-root .mmx-project-workspace > .mmx-section-body { gap:14px;padding:14px 16px 16px; }
.mmx-director-root .mmx-project-library { display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:0;border:0; }
.mmx-director-root .mmx-project-library .mmx-project-name-field { display:flex;flex-direction:row;align-items:center;gap:10px;flex:1;min-width:240px;padding:0;border:0;background:transparent; }
.mmx-director-root .mmx-project-library .mmx-project-name-field > span { font-size:12px;color:#9fb2c3;white-space:nowrap; }
.mmx-director-root .mmx-project-name-field input { flex:1;min-width:120px;height:34px;padding:0 10px;border:1px solid #46525e;border-radius:6px;background:#1b2026;color:#e8edf2;font-size:13px; }
.mmx-director-root .mmx-project-name-field input:focus { outline:none;border-color:#7eafcf;box-shadow:0 0 0 2px #7eafcf33; }
.mmx-director-root .mmx-project-library > button { height:34px;min-height:34px;padding:0 14px;border:1px solid #4b5866;border-radius:6px;background:#2c343d;color:#dfe7ee;font-size:12.5px;font-weight:600; }
.mmx-director-root .mmx-project-library > button.mmx-primary-action { background:#2f5574;border-color:#5f93bd;color:#eef6fc; }
.mmx-director-root .mmx-project-library > button.mmx-primary-action:hover:not(:disabled) { background:#3a6890;border-color:#8ab9df; }
.mmx-director-root .mmx-server-project-status { display:inline-flex;align-items:center;gap:6px;height:24px;padding:0 10px;border-radius:12px;font-size:11.5px;white-space:nowrap;background:#2a3036;color:#a9b6c2;border:1px solid #3f4953; }
.mmx-director-root .mmx-server-project-status::before { content:'';width:7px;height:7px;border-radius:50%;background:currentColor;opacity:.9; }
.mmx-director-root .mmx-server-project-status[data-state="saved"] { color:#8fd6ad;border-color:#3d6b52;background:#1f3128; }
.mmx-director-root .mmx-server-project-status[data-state="changed"] { color:#e8c06a;border-color:#6e5a2d;background:#2f2918; }
.mmx-director-root .mmx-project-feedback { flex-basis:100%;display:flex;align-items:center;flex-wrap:wrap;gap:8px 12px;padding:8px 12px;border:1px solid #3f4c58;border-left:3px solid #7eafcf;border-radius:6px;background:#1d242b;color:#c9dcec;font-size:12.5px;line-height:1.4; }
.mmx-director-root .mmx-project-feedback:empty { display:none; }
.mmx-director-root .mmx-project-feedback[data-state="success"] { color:#b6edcb;border-color:#38563f;border-left-color:#5fbf86;background:#1c2b22; }
.mmx-director-root .mmx-project-feedback[data-state="error"] { color:#ffc9cf;border-color:#5c3a40;border-left-color:#e06b7a;background:#2a1d21; }
.mmx-director-root .mmx-project-feedback[data-state="busy"] { border-left-color:#e8c06a; }
.mmx-server-project-note[data-state="error"] { color:#ffb9c2;border-color:#b95f6c; }
.mmx-director-root .mmx-feedback-actions { display:inline-flex;gap:8px;margin-left:auto; }
.mmx-director-root .mmx-feedback-actions button { height:28px;padding:0 10px;border:1px solid #5b6977;border-radius:5px;background:#2c343d;color:#e3eaf0;font-size:12px;cursor:pointer; }
.mmx-director-root .mmx-feedback-actions button:hover { border-color:#8ab9df;background:#36414c; }
.mmx-director-root .mmx-project-workspace .mmx-project-actions { display:grid;grid-template-columns:2fr 1fr 1.4fr;gap:12px;padding:0;border:0; }
.mmx-director-root .mmx-project-card { display:flex;flex-direction:column;gap:10px;min-width:0;padding:12px;border:1px solid #39434d;border-radius:8px;background:#1f252b; }
.mmx-director-root .mmx-project-card h4 { margin:0;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#8ea2b4; }
.mmx-director-root .mmx-project-card-buttons { display:flex;flex-wrap:wrap;gap:8px; }
.mmx-director-root .mmx-project-card-buttons button { flex:1 1 110px;height:34px;min-height:34px;padding:0 12px;border:1px solid #4b5866;border-radius:6px;background:#2c343d;color:#dfe7ee;font-size:12.5px;font-weight:600;white-space:nowrap;box-shadow:none; }
.mmx-director-root .mmx-project-card-buttons button[hidden] { display:none; }
.mmx-director-root .mmx-project-card-danger { border-color:#4a3338;background:#231d20; }
.mmx-director-root .mmx-project-card-danger h4 { color:#c98d96; }
.mmx-director-root .mmx-project-workspace .mmx-project-card-buttons button.mmx-project-danger { background:#2f2327;border-color:#6d4148;color:#f3c3ca;box-shadow:none; }
.mmx-director-root .mmx-project-workspace .mmx-project-card-buttons button.mmx-project-danger:hover:not(:disabled) { background:#43272e;border-color:#d0707d;color:#ffe0e4;box-shadow:none; }
.mmx-director-root .mmx-export-choices { display:flex;flex-direction:column;align-items:flex-start;gap:6px;padding-top:8px;border-top:1px dashed #39434d;font-size:12px;color:#9fb2c3; }
.mmx-director-root .mmx-export-choices > span { font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#7d90a1; }
.mmx-director-root .mmx-project-workspace .mmx-export-choices .mmx-field { display:inline-flex!important;flex-direction:row!important;align-items:center;gap:6px!important;margin:0;padding:0;border:0;background:transparent;font-size:12px;white-space:nowrap;cursor:pointer;color:#c8d4de; }
.mmx-director-root .mmx-project-workspace .mmx-export-choices input { width:14px!important;min-width:14px;height:14px;margin:0;accent-color:#7eafcf; }
@container (max-width:900px) { .mmx-director-root .mmx-project-workspace .mmx-project-actions { grid-template-columns:1fr 1fr; } .mmx-director-root .mmx-project-card-files { grid-column:1/-1; } }
@container (max-width:560px) { .mmx-director-root .mmx-project-workspace .mmx-project-actions { grid-template-columns:1fr; } }

/* Approval, inspection and execution have distinct visual states. */
.mmx-director-root .mmx-shot-block.validated {background:#244337!important;border-color:#66b38b!important;}
.mmx-director-root .mmx-shot-block.active,.mmx-director-root .mmx-shot-block.validated.active {outline:3px solid #f3cf78;outline-offset:-3px;box-shadow:inset 0 0 0 5px #15191ecc!important;}
.mmx-director-root .mmx-shot-block.generating {border-color:#65cfff!important;box-shadow:inset 0 0 0 2px #65cfff!important;}
.mmx-generating-badge {display:inline-flex;align-items:center;gap:5px;padding:2px 6px;background:#144a63;color:#cff2ff;border-radius:3px;font-size:10px;}
.mmx-saved-badge {flex:0 0 auto;color:#9cdee8;font-size:9px;font-weight:600;white-space:nowrap;}
.mmx-generating-badge::before {content:'';width:7px;height:7px;border-radius:50%;background:#7ee1ff;animation:mmx-generation-pulse 1s ease-in-out infinite alternate;}
.mmx-shot-block > .mmx-generating-badge {position:absolute;left:8px;bottom:6px;max-width:calc(100% - 44px);white-space:nowrap;overflow:hidden;pointer-events:none;}
@keyframes mmx-generation-pulse {to {opacity:.25;}}
@media (prefers-reduced-motion:reduce) {.mmx-saved-badge {flex:0 0 auto;color:#9cdee8;font-size:9px;font-weight:600;white-space:nowrap;}
.mmx-generating-badge::before {animation:none;}}
.mmx-director-root .mmx-clip-selection:has(input:disabled) {opacity:.4;cursor:not-allowed;}
.mmx-director-root .mmx-clip-selection input:disabled {cursor:not-allowed;}
.mmx-director-root .mmx-shot-prompt-preview {flex:1;display:-webkit-box;-webkit-line-clamp:5;line-height:1.5;padding:6px 0 26px;white-space:normal;text-align:left;align-self:stretch;color:#c5d0db!important;}
.mmx-director-root .mmx-timeline-audio {padding:4px 0;border:0;border-radius:0;background:transparent;display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin:0;}
.mmx-director-root .mmx-timeline-audio h3 {font-size:12px;color:#a9bac9;margin:0;}
.mmx-director-root .mmx-timeline-audio label {display:flex;gap:7px;align-items:center;}
.mmx-director-root .mmx-inspector-header {display:grid;grid-template-columns:minmax(360px,1fr) minmax(180px,240px);align-items:center;padding:16px;border:1px solid #45535f;border-radius:7px;background:#20272e;gap:16px;}
.mmx-director-root .mmx-inspector-title {width:100%;}
.mmx-director-root .mmx-inspector-title .mmx-ctrl-item {gap:10px;}
.mmx-director-root .mmx-inspector-title .mmx-ctrl-item:first-child > label {width:60px;flex-shrink:0;}
.mmx-director-root .mmx-inspector-title > div,.mmx-director-root .mmx-inspector-title > span {display:flex;align-items:center;gap:10px;min-height:34px;}
.mmx-director-root .mmx-inspector-title > div > span:first-child,.mmx-director-root .mmx-inspector-title > span > span:first-child {width:60px;flex-shrink:0;}
.mmx-director-root .mmx-clip-name-row input {width:min(300px,40vw)!important;flex:1;min-width:100px;}
.mmx-director-root .mmx-clip-header-actions {grid-template-columns:1fr 1fr;min-width:0;gap:8px;align-self:center;}
.mmx-director-root .mmx-clip-header-actions > button:first-child {grid-column:1/-1;}
.mmx-director-root .mmx-clip-header-actions button {display:flex;align-items:center;justify-content:center;text-align:center;}
.mmx-director-root .mmx-inspector-card-row {flex-wrap:wrap;}
.mmx-director-root .mmx-inspector-header .mmx-audio-control {display:flex;align-items:center;gap:10px;white-space:nowrap;}
@container (max-width:680px) {.mmx-director-root .mmx-inspector-header {grid-template-columns:1fr;}.mmx-director-root .mmx-clip-header-actions {grid-template-columns:repeat(3,1fr);}.mmx-director-root .mmx-clip-header-actions > button:first-child {grid-column:auto;}}

.mmx-director-root .mmx-continuity-link {position:absolute;top:64px;width:28px;height:24px;transform:translateX(-50%);display:flex;align-items:center;justify-content:center;z-index:6;color:#9fc4d9;background:transparent;border:0;pointer-events:auto;}
.lg-node-widgets:has(.mmx-director-root:not(.mmx-preview-node)) > .lg-node-widget:not(:has(.mmx-director-root,input,textarea,select,button,[role="combobox"])) {display:none!important;}
.mmx-director-root:not(.mmx-preview-node) > .mmx-inspector {flex:1 0 auto;min-height:480px;display:flex;flex-direction:column;}
.mmx-director-root .mmx-edit-workspace {flex:1;min-height:360px;align-items:stretch;}
.mmx-director-root .mmx-edit-main {min-height:0;}
.mmx-director-root .mmx-prompt-inspector {flex:1;min-height:260px;display:flex;flex-direction:column;}
.mmx-director-root .mmx-prompt-inspector > .mmx-textarea {flex:1 1 0!important;height:auto!important;max-height:none!important;min-height:180px!important;resize:none;}
.mmx-director-root .mmx-prompt-inspector .mmx-structured-grid {flex:1!important;height:auto!important;max-height:none!important;}
.mmx-director-root .mmx-edit-tools {display:flex;flex-direction:column;align-self:stretch;min-height:0;}
.mmx-director-root .mmx-tool-content {flex:1;min-height:0;max-height:none!important;overflow-y:auto;}

`;

function injectCSS() {
  if (document.getElementById("minimax-director-styles")) return;
  const style = document.createElement("style");
  style.id = "minimax-director-styles";
  style.textContent = embeddedCSS;
  document.head.appendChild(style);
}

function migrateClipApproval(state) {
  if(Number(state.approval_control_version || 0)<1) {
    // The old green checkbox was mistaken for approval. Preserve that intent
    // only when it was not being used with the explicit generation filter.
    for(const clip of state.clips || []) if(!state.run_selection && clip.selected===true)clip.validated=true;
  }
  for(const clip of state.clips || [])clip.selected=false;
  state.run_selection=false;state.approval_control_version=1;
}

function migrateContinuitySources(state) {
  const used=new Set((state.clips || []).map(clip=>clip.id)), clips=[];
  for(const clip of state.clips || []) {
    const source=clip.continuation_source;
    if(source && source.filename && Number.isFinite(Number(source.end)) && Number(source.end)>0) {
      let id=`context_${clip.id || clips.length}`;while(used.has(id))id+='_source';used.add(id);
      const end=Number(source.end),start=Math.max(0,end-56/24);
      clips.push({id,name:'Imported Context Video',type:'V2V',source:{filename:source.filename},source_start:start,source_end:end,duration:end-start,locked:true,audio_mode:'source',selected:false,continuity:false,prompt:'',ref_ids:[]});
      delete clip.continuation_source;
    }
    clips.push(clip);
  }
  state.clips=clips;
}

function mountDirectorUI(node) {
  node.__mmxDisposed = false;
  console.log("[DirectorUI] Attempting to mount:", node.id, node.type);
  if (!node || node.__mmxDirectorMounted) return;
  node.__mmxDirectorMounted = true;

  const getTopWidgetsHeight = (n) => {
    const maxSlots = Math.max(n?.inputs?.length || 0, n?.outputs?.length || 0);
    return maxSlots > 0 ? (maxSlots * 20 + 10) : 34;
  };

  node.widgets_start_y = getTopWidgetsHeight(node);
  node.onConnectionsChange = function () {
    resolveAvailableRefsFromGraph();
    syncState();
    renderTimeline();
    if (activeClipId) renderInspector();
  };

  injectCSS();

  // State initialization
  let domWidget = null;
  let playheadSeconds = 0.0;
  let zoomLevel = 3.0;
  let activeClipId = "clip_1";
  let activeToolTab = "Continuity";
  let showToolHelp = false;


  const getMinDomHeight = () => 700;

  const getAvailableDomHeight = (n, minH) => {
    if (!n || !n.size) return minH !== undefined ? minH : getMinDomHeight();
    const fallbackMin = minH !== undefined ? minH : getMinDomHeight();
    const topY = getTopWidgetsHeight(n);
    const avail = (n.size[1] || 0) - topY - 14 - (n.widgets?.some(w=>w.name==="generation_mode") ? 30 : 0);
    return Math.max(fallbackMin, Math.floor(avail));
  };

  const updateDomSize = () => {
    if (!domWidget || !domWidget.element) return;
    const topY = getTopWidgetsHeight(node);
    node.widgets_start_y = topY;
    if (domWidget) domWidget.last_y = topY + (generationWidget ? 30 : 0);
    const minH = getMinDomHeight();
    const availH = getAvailableDomHeight(node, minH);
    const nodeW = node.size?.[0] || 1200;
    const availW = Math.max(nodeW - 20, 880);

    domWidget.element.style.width = "calc(100% - 20px)";
    domWidget.element.style.marginLeft = "10px";
    domWidget.element.style.marginRight = "10px";
    domWidget.element.style.marginTop = "0px";
    domWidget.element.style.marginBottom = "0px";
    domWidget.element.style.height = `${availH}px`;
    domWidget.element.style.maxHeight = `${availH}px`;
    domWidget.element.style.flex = "1";

    if (domWidget.computeSize) {
      domWidget.computeSize = function (width) {
        return [width || availW, minH];
      };
    }
  };

  // Find widget references
  const durationWidget = node.widgets?.find((w) => w.name === "duration");
  const promptWidget = node.widgets?.find((w) => w.name === "prompt");
  const timelineWidget = node.widgets?.find((w) => w.name === "timeline_data");
  const builderWidget = node.widgets?.find((w) => w.name === "builder_state");
  // Older open workflows can retain the node definition from before this input existed.
  // Add the ordinary LiteGraph combo rather than leaving those nodes without a control.
  let generationWidget = node.widgets?.find(w => w.name === "generation_mode");
  if (!generationWidget && !node.inputs?.some(input=>input.name === "generation_mode")) {
    generationWidget = node.addWidget("combo", "generation_mode", "Next clip", null,
      {values:["Next clip","All clips","Conditioning only"]});
  }
  if (generationWidget && generationWidget.type === "hidden") {
    generationWidget.type = "combo"; generationWidget.hidden = false;
    generationWidget.options = {...generationWidget.options,values:["Next clip","All clips","Conditioning only"]};
    delete generationWidget.draw; delete generationWidget.computeSize;
  }
  const generationDisplay = value => ({"Next shot":"Next clip","All shots":"All clips"})[value] || value || "Next clip";

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
  hideWidget(durationWidget);

  // State
  let timelineState = {
    version: 2,
    clips: [
      {
        id: "clip_1",
        name: "Clip 1",
        type: "T2V",
        duration: 5.0,
        prompt: "",
        ref_ids: [],
        continuity: true, continuity_mode: "Independent (No Continuity)", context_length: 22, audio_context_length: 22,
      }
    ],
    refmods: [],
    available_refs: [],
  };
  let generatingClipId=null,generatingPhase='sampling';
  const freshApprovals=new Set(); // clips ticked since the last cache-status refresh
  let progressSequence=0,progressTimer=null,progressWatching=false,progressRequest=false;
  let cachedClipResults={},cacheStatusProject=null,cacheStatusRequest=0;
  const calibrationCache=new Map(); // measurement promises per take, so redraws do not re-measure
  let serverStatus=null, savedProjectSignature=null;
  let draftRestored=false,draftTimer=null,pendingDraft=null;
  const flushDraft=()=>{clearTimeout(draftTimer);draftTimer=null;if(pendingDraft){writeDirectorDraft(...pendingDraft);pendingDraft=null;}};
  const hideDraft=()=>{if(document.hidden)flushDraft();};
  window.addEventListener('pagehide',flushDraft);document.addEventListener('visibilitychange',hideDraft);
  const projectSignature=()=>JSON.stringify({timeline:{...timelineState,server_revision:undefined,draft_updated_at:undefined},builder:builderState});
  const updateServerStatus=()=>{
    if(serverStatus){
      const state=savedProjectSignature && savedProjectSignature===projectSignature() ? 'saved' : timelineState.server_revision ? 'changed' : 'unsaved';
      serverStatus.dataset.state=state;
      serverStatus.textContent=({saved:'Saved',changed:'Unsaved changes',unsaved:'Not saved on server'})[state];
    }
    if(serverStatus)projectScope.textContent=timelineState.project_name || 'All Clips · Projects & Files';
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

  const resolveAvailableRefsFromGraph = () => {
    try {
      if (typeof app === "undefined" || !app.graph) return;
      const refPackInput = node.inputs?.find((i) => i.name === "ref_pack");
      const link = (refPackInput && refPackInput.link != null) ? app.graph.links[refPackInput.link] : null;
      let upstreamNode = link ? app.graph.getNodeById(link.origin_id) : null;

      // If ref_pack input is disconnected or has no upstream node, clear discovered pack refs and clean up clip ref_ids
      if (!upstreamNode) {
        const customRefs = (timelineState.available_refs || []).filter(
          (r) => !r.id.startsWith("img_") && !r.id.startsWith("vid_") && !r.id.startsWith("aud_") && !r.id.startsWith("mod_") && !r.id.match(/^p\d+_/)
        );
        timelineState.available_refs = [];
        const validIds = new Set([...customRefs, ...(timelineState.references || [])].flatMap(r => [r.id, r.alt_id].filter(Boolean)));
        (timelineState.clips || []).forEach((c) => {
          if (Array.isArray(c.ref_ids)) {
            c.ref_ids = c.ref_ids.filter((id) => validIds.has(id));
          }
        });
        return;
      }

      // Follow any intermediate Reroute nodes
      let rerouteSteps = 0;
      while (upstreamNode && (upstreamNode.type === "Reroute" || upstreamNode.comfyClass === "Reroute") && rerouteSteps < 10) {
        const rInp = upstreamNode.inputs?.[0];
        if (rInp && rInp.link != null && app.graph?.links?.[rInp.link]) {
          upstreamNode = app.graph.getNodeById(app.graph.links[rInp.link].origin_id);
          rerouteSteps++;
        } else {
          break;
        }
      }
      if (!upstreamNode) {
        const customRefs = (timelineState.available_refs || []).filter(
          (r) => !r.id.startsWith("img_") && !r.id.startsWith("vid_") && !r.id.startsWith("aud_") && !r.id.startsWith("mod_") && !r.id.match(/^p\d+_/)
        );
        timelineState.available_refs = [];
        const validIds = new Set([...customRefs, ...(timelineState.references || [])].flatMap(r => [r.id, r.alt_id].filter(Boolean)));
        (timelineState.clips || []).forEach((c) => {
          if (Array.isArray(c.ref_ids)) {
            c.ref_ids = c.ref_ids.filter((id) => validIds.has(id));
          }
        });
        return;
      }

      const chain = [];
      let curr = upstreamNode;
      let depth = 0;
      while (curr && depth < 10) {
        chain.unshift(curr);
        const prevInput = curr.inputs?.find((i) => i.name === "ref_pack_optional");
        if (prevInput && prevInput.link != null) {
          const prevLink = app.graph.links[prevInput.link];
          if (prevLink) {
            let prevNode = app.graph.getNodeById(prevLink.origin_id);
            let prevReroute = 0;
            while (prevNode && (prevNode.type === "Reroute" || prevNode.comfyClass === "Reroute") && prevReroute < 10) {
              const rInp = prevNode.inputs?.[0];
              if (rInp && rInp.link != null && app.graph?.links?.[rInp.link]) {
                prevNode = app.graph.getNodeById(app.graph.links[rInp.link].origin_id);
                prevReroute++;
              } else {
                break;
              }
            }
            if (prevNode) {
              curr = prevNode;
              depth++;
              continue;
            }
          }
        }
        break;
      }

      const mediaRegex = /\.(png|jpe?g|webp|bmp|gif|mp4|webm|mov|mkv|avi|wav|mp3|ogg|flac|m4a)$/i;

      // Shared observers let several Masters use one pool without stale callbacks.
      const updateRefs = node.__mmxRefObserver ||= () => setTimeout(() => {
        if (node.__mmxDisposed) return;
        resolveAvailableRefsFromGraph(); syncState(); renderTimeline();
      }, 30);
      const subscribe = (target, method, key) => {
        if (!target[key]) {
          const observers = target[key] = new Set(), original = target[method];
          target[method] = function (...args) {
            const result = original?.apply(this, args);
            for (const observer of observers) observer();
            return result;
          };
        }
        target[key].add(updateRefs);
        (node.__mmxRefObserverSets ||= new Set()).add(target[key]);
      };
      const hookNodeChange = target => {
        for (const widget of target?.widgets || []) subscribe(widget,"callback","__mmxRefObservers");
        if (target) subscribe(target,"onConnectionsChange","__mmxRefConnectionObservers");
      };

      const discoveredRefs = [];
      chain.forEach((rpNode, pIdx) => {
        hookNodeChange(rpNode);
        const packNum = pIdx + 1;
        const prefix = chain.length > 1 ? `[P${packNum}] ` : "";
        const idPrefix = packNum === 1 ? "" : `p${packNum}_`;

        const getVal = (wName, fallback) => {
          const w = rpNode.widgets?.find((x) => x.name === wName);
          return (w && w.value && String(w.value).trim()) ? String(w.value).trim() : fallback;
        };

        const getConnectedAsset = (slotName) => {
          try {
            const inp = rpNode.inputs?.find((x) => x.name === slotName);
            if (!inp || inp.link == null || !app.graph?.links?.[inp.link]) return { url: null, filename: null };
            let originNode = app.graph.getNodeById(app.graph.links[inp.link].origin_id);
            if (!originNode) return { url: null, filename: null };

            // Follow any Reroute nodes upstream
            let rSteps = 0;
            while (originNode && (originNode.type === "Reroute" || originNode.comfyClass === "Reroute") && rSteps < 10) {
              const rInp = originNode.inputs?.[0];
              if (rInp && rInp.link != null && app.graph?.links?.[rInp.link]) {
                originNode = app.graph.getNodeById(app.graph.links[rInp.link].origin_id);
                rSteps++;
              } else {
                break;
              }
            }
            if (!originNode) return { url: null, filename: null };

            hookNodeChange(originNode);

            let fn = null;
            // 1. Check direct widgets
            if (originNode.widgets) {
              const wPriority = originNode.widgets.find((x) =>
                x.name === "image" || x.name === "audio" || x.name === "video" ||
                x.name === "upload" || x.name === "file" || x.name === "filename"
              );
              if (wPriority && wPriority.value && typeof wPriority.value === "string") {
                fn = wPriority.value;
              } else {
                for (const w of originNode.widgets) {
                  if (w.value && typeof w.value === "string" && mediaRegex.test(w.value)) {
                    fn = w.value;
                    break;
                  }
                }
              }
            }

            // 2. Check widgets_values array if fn not found
            if (!fn && Array.isArray(originNode.widgets_values)) {
              for (const v of originNode.widgets_values) {
                if (typeof v === "string" && mediaRegex.test(v)) {
                  fn = v;
                  break;
                }
              }
            }

            // 3. Check originNode.imgs preview
            if (originNode.imgs && originNode.imgs[0] && originNode.imgs[0].src) {
              return { url: originNode.imgs[0].src, filename: fn || originNode.imgs[0].name || null };
            }

            // 4. Construct ComfyUI view URL if filename found
            if (fn) {
              const cleanFn = fn.replace(/\\/g, "/");
              if (cleanFn.includes("/")) {
                const parts = cleanFn.split("/");
                const baseName = parts.pop();
                const subfolder = parts.join("/");
                return {
                  url: `/view?filename=${encodeURIComponent(baseName)}&subfolder=${encodeURIComponent(subfolder)}&type=input`,
                  filename: fn,
                };
              }
              return { url: `/view?filename=${encodeURIComponent(fn)}&type=input`, filename: fn };
            }
          } catch (err) {}
          return { url: null, filename: null };
        };

        let assetEditor={};try{assetEditor=JSON.parse(getVal('asset_edits','{}'));}catch{}
        // H3's per-clip maximum: 9 images, 3 videos, 3 audios (matches the Reference Pack sockets).
        const packSlots=[...Array.from({length:9},(_,i)=>[`image_${i+1}`,'image',`img_${i+1}`]),...Array.from({length:3},(_,i)=>[`video_${i+1}`,'video',`vid_${i+1}`]),...Array.from({length:3},(_,i)=>[`audio_${i+1}`,'audio',`aud_${i+1}`])];
        for (const [slot, type, short] of packSlots) {
          const input = rpNode.inputs?.find(row => row.name === slot);
          if (input?.link == null || !app.graph.links[input.link]) continue;
          const asset = getConnectedAsset(slot);
          const settings=assetEditor.assets?.[slot] || {};
          const preparedType=type==='video' && settings.media_mode==='frame'?'image':type==='video' && settings.media_mode==='audio'?'audio':type;
          discoveredRefs.push({id: `${idPrefix}${slot}`, alt_id: `${idPrefix}${short}`, name: `${prefix}${settings.name || getVal(slot+"_name",slot)}`, ...settings,type:preparedType,source_type:type, role:settings.role,description:settings.description,...asset});
        }
        for (const [slot, short] of [["refmod_1","mod_1"],["refmod_2","mod_2"]]) {
          const model = getVal(slot,"None");
          if (!model || model.toLowerCase() === "none") continue;
          discoveredRefs.push({id: `${idPrefix}${slot}`, alt_id: `${idPrefix}${short}`, name: `${prefix}${getVal(slot+"_name",slot)}`, type:"refmod", model});
        }
        for(const row of assetEditor.files || []) {
          const filename=row.filename.replace(/\\/g,'/'),parts=filename.split('/'),name=parts.pop();
          discoveredRefs.push({...row,type:row.type==='video' && row.media_mode==='audio'?'audio':row.type==='video' && row.media_mode==='frame'?'image':row.type,url:`/view?${new URLSearchParams({filename:name,subfolder:parts.join('/'),type:'input'})}`});
        }
        const libraryInput=rpNode.inputs?.find(input=>input.name==='refmod_library');
        const libraryLink=app.graph?.links?.[libraryInput?.link];const library=libraryLink && app.graph.getNodeById(libraryLink.origin_id);
        if(library){hookNodeChange(library);let rows=[];try{rows=JSON.parse(library.widgets?.find(w=>w.name==='library_data')?.value || '[]');}catch{}
          for(const row of rows)if(row.enabled!==false && row.id)discoveredRefs.push({id:idPrefix+row.id,type:'refmod',name:row.description || row.name,description:row.description,strength:row.strength,model:row.name});
        }
      });

      timelineState.available_refs = discoveredRefs;

      // Clean up any clip ref_ids that are no longer available in the graph, migrating any legacy alt_ids
      const validIds = new Set();
      discoveredRefs.forEach((d) => { validIds.add(d.id); if (d.alt_id) validIds.add(d.alt_id); });



      (timelineState.clips || []).forEach((c) => {
        if (Array.isArray(c.ref_ids)) {
          c.ref_ids = c.ref_ids.map((id) => {
            const found = discoveredRefs.find((d) => d.alt_id === id);
            return found ? found.id : id;
          }).filter((id) => validIds.has(id));
        }
      });
    } catch (e) {
      console.warn("Could not resolve RefPack references from graph:", e);
    }

  };

  const loadState = () => {
    resolveAvailableRefsFromGraph();
    try {
      if (timelineWidget && timelineWidget.value) {
        const parsed = typeof timelineWidget.value === "string" ? JSON.parse(timelineWidget.value) : timelineWidget.value;
        if (parsed && typeof parsed === "object") {
          const sessionKey=`${parsed.project_id}::${node.id}`;
          const draft=draftRestored || sessionMountedDirectors.has(sessionKey)?null:readDirectorDraft(parsed,String(node.id));
          draftRestored=true;if(parsed.project_id)sessionMountedDirectors.add(sessionKey);
          timelineState = { ...timelineState, ...(draft?.timeline || parsed) };
          const pid=timelineState.project_id;
          if(pid && sessionRevisions.has(pid))timelineState.server_revision=sessionRevisions.get(pid);
          else if(pid && timelineState.server_revision)sessionRevisions.set(pid,timelineState.server_revision);
          if(draft && builderWidget)builderWidget.value=draft.builder;
          if (!Array.isArray(timelineState.clips)) {
            timelineState.clips = [
              {
                id: "clip_1",
                name: "Clip 1",
                type: "T2V",
                duration: 5.0,
                tail_seconds: 0.5,
                seed: 0,
                seed_mode: "fixed",
                validated: false,
                prompt: "",
                ref_ids: [],
                continuity: true, continuity_mode: "Independent (No Continuity)", context_length: 22, audio_context_length: 22,
              }
            ];
          }
          if (!timelineState.preview_mode) timelineState.preview_mode = "full";
          // Unify any legacy REF2V clips into REF2VA and ensure defaults
          timelineState.clips.forEach((c) => {
            if (c.type === "REF2V") c.type = "REF2VA";
            if (c.tail_seconds === undefined) c.tail_seconds = 0.5;
            if (c.seed === undefined) c.seed = 0;
            if (c.seed_mode === undefined) c.seed_mode = "fixed";
            if (c.validated === undefined) c.validated = false;
            if (c.structured_prompt) {
              if (c.structured_prompt.soundscape && !c.structured_prompt.overall_soundscape) {
                c.structured_prompt.overall_soundscape = c.structured_prompt.soundscape;
              }
              if (c.structured_prompt.music && !c.structured_prompt.non_diegetic_music) {
                c.structured_prompt.non_diegetic_music = c.structured_prompt.music;
              }
            }
          });
          if (!Array.isArray(timelineState.refmods)) timelineState.refmods = [];
          if (!Array.isArray(timelineState.available_refs)) {
            timelineState.available_refs = [];
          }
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

    migrateClipApproval(timelineState);
    resolveAvailableRefsFromGraph();
    if (!activeClipId || !timelineState.clips.find((c) => c.id === activeClipId)) {
      activeClipId = timelineState.clips[0]?.id || "clip_1";
    }
  };

  loadState();

  const syncState = (acceptRuntime = false) => {
    timelineState.generation_mode ||= "Next shot";
    for (const clip of timelineState.clips || []) {
      clip.continuity_mode ||= "Independent (No Continuity)";
      clip.context_length ??= 22;
      clip.audio_context_length ??= clip.context_length;
      clip.selected ??= false;
    }
    migrateContinuitySources(timelineState);migrateClipApproval(timelineState);
    timelineState.project_id ||= `project_${crypto.randomUUID()}`;
    // Approval belongs to the user; settings edits never reject a saved take.
    timelineState.draft_updated_at=Math.max(Date.now(),Number(timelineState.draft_updated_at || 0)+1);
    const serializedTimeline=JSON.stringify(timelineState),serializedBuilder=JSON.stringify(builderState);
    if (timelineWidget) timelineWidget.value = serializedTimeline;
    if (builderWidget) builderWidget.value = serializedBuilder;
    pendingDraft=[`${timelineState.project_id}::${node.id}`,serializedTimeline,serializedBuilder,timelineState.draft_updated_at];
    clearTimeout(draftTimer);draftTimer=setTimeout(flushDraft,150);
    updateServerStatus();
    if (node.setDirtyCanvas) node.setDirtyCanvas(true, true);
    if (app.graph && app.graph.setDirtyCanvas) app.graph.setDirtyCanvas(true, true);
  };

  const mediaUrl = (filename) => {
    const parts = String(filename).replaceAll("\\", "/").split("/");
    return api.apiURL(`/view?${new URLSearchParams({ filename: parts.pop(), subfolder: parts.join("/"), type: "input" })}`);
  };
  const refreshFileRefs = () => {}; // Media is supplied by connected Reference Packs.
  const requestJson = async (url, body) => {
    const response = await api.fetchApi(url, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const result = await response.json();
    if (!response.ok) throw Object.assign(new Error(result.error || `Request failed (${response.status})`),{status:response.status,result});
    return result;
  };

  syncState();

  // Create modern timeline root element
  const root = document.createElement("div");
  root.className = "mmx-director-root";


  // Timeline navigation and footage insertion. Project files live in Project.
  const toolbar = document.createElement("div");
  toolbar.className = "mmx-toolbar";
  // Let nested fields/panels scroll without the graph treating the wheel as zoom.
  root.addEventListener("wheel",event=>event.stopPropagation(),{passive:true});

  // Left action buttons
  const toolbarLeft = document.createElement("div");
  toolbarLeft.className = "mmx-toolbar-left";

  const syncRefsBtn = document.createElement("button");
  syncRefsBtn.className = "mmx-action-btn";
  syncRefsBtn.textContent = "Refresh pool";
  syncRefsBtn.title = "Sync reference assets and labels directly from upstream RefPack and loaders without running the pipeline";
  syncRefsBtn.onclick = () => {
    resolveAvailableRefsFromGraph();
    syncState();
    renderTimeline();
    if (activeClipId) renderInspector();
    syncRefsBtn.innerHTML = "✓ Synced!";
    syncRefsBtn.style.borderColor = "#10b981";
    syncRefsBtn.style.color = "#10b981";
    setTimeout(() => {
      syncRefsBtn.textContent = "Refresh pool";
      syncRefsBtn.style.borderColor = "";
      syncRefsBtn.style.color = "";
    }, 1500);
  };


  const exportBtn = document.createElement("button");
  exportBtn.className = "mmx-action-btn";
  exportBtn.textContent = "Export Project";exportBtn.dataset.projectAction="export";
  exportBtn.title = "Save the timeline as JSON, or include source/reference files in a portable archive.";
  const includeMedia=document.createElement("input");includeMedia.type="checkbox";includeMedia.checked=false;
  includeMedia.className="mmx-export-media";
  const includeResults=document.createElement('input');includeResults.type='checkbox';includeResults.className='mmx-export-results';
  const cancelExport=document.createElement('button');cancelExport.textContent='Cancel download';cancelExport.hidden=true;
  cancelExport.onclick=()=>node.__mmxExportController?.abort();
  exportBtn.onclick = async () => {
    if(exportBtn.disabled)return;
    exportBtn.disabled=true;exportBtn.textContent='Exporting…';exportBtn.setAttribute('aria-busy','true');
    const controller=new AbortController();node.__mmxExportController=controller;cancelExport.hidden=false;
    showProjectFeedback('busy','Preparing Project Download…');
    try {
      if(includeMedia.checked || includeResults.checked){await exportPortable(controller.signal);showProjectFeedback('success',includeResults.checked?'Project Download Includes Generated Latents, Frames And Audio.':'Project Download Includes Source And Reference Media.');return;}
      const res = await api.fetchApi("/minimax_director/project/export", {
        method: "POST",
        signal:controller.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: timelineState.project_id || String(node.id ?? "default_director"),
          timeline: { ...timelineState, builder_state: builderWidget?.value || "{}" },
          name: timelineState.project_name || "MiniMaxProject",
          workflow:(app.rootGraph || app.graph)?.serialize?.(),master_node_id:node.id,
        }),
      });
      const data = await res.json();
      if(controller.signal.aborted)throw new DOMException('Download cancelled','AbortError');
      if (!res.ok || !data.ok) throw new Error(data.error || "Project export failed");
      if (data.ok) {
        const blob = new Blob([JSON.stringify(data.project, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `minimax_project_${Date.now()}.mmxproj.json`;
        a.click();
        URL.revokeObjectURL(url);
        showProjectFeedback('success','Project JSON Download Prepared. Media And Generated Results Stay On Server.');
      }
    } catch (err) {
      showProjectFeedback(err.name==='AbortError'?'idle':'error',err.name==='AbortError'?'Download Cancelled.':`Export Failed: ${err.message}`);
    } finally { cancelExport.hidden=true;node.__mmxExportController=null;exportBtn.disabled=false;exportBtn.textContent='Export Project';exportBtn.removeAttribute('aria-busy'); }
  };


  const importBtn = document.createElement("button");
  importBtn.className = "mmx-action-btn";
  importBtn.textContent = "Import Project";importBtn.dataset.projectAction="import";
  importBtn.title = "Load a JSON timeline or a portable archive; choose append or overwrite.";
  importBtn.onclick = () => {
    if(importBtn.disabled)return;
    showProjectFeedback('busy','Choose A Project File To Import.');
    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = ".json,.mmxproj,.zip";
    fileInput.oncancel=()=>showProjectFeedback('idle','Import Cancelled.');
    fileInput.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const policy = prompt("Import: append, overwrite (timeline into current workflow), or workflow (restore all nodes/settings)", "overwrite");
      if(!policy){showProjectFeedback('idle','Import Cancelled.');return;}
      if(!['append','overwrite','workflow'].includes(policy)){showProjectFeedback('error','Choose append, overwrite, or workflow.');return;}
      importBtn.disabled=true;importBtn.textContent='Importing…';importBtn.setAttribute('aria-busy','true');
      showProjectFeedback('busy','Importing Project…');
      try {
        if(!file.name.toLowerCase().endsWith(".json")){await importPortable(file,policy);showProjectFeedback('success','Project Archive Imported.');return;}
        const text = await file.text();
        const projectData = JSON.parse(text);
        const res = await api.fetchApi("/minimax_director/project/import", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project: projectData,reference_catalog:policy==='workflow'?undefined:timelineState.available_refs }),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) throw new Error(data.error || "Project import failed");
        if (data.ok && data.timeline) {
          if(policy==='workflow'){
            if(!data.workflow || !app.loadGraphData)throw Error('This older export has no saved workflow. Use overwrite to import its timeline.');
            await app.loadGraphData(data.workflow,true,true,'MiniMax Imported Project.json');return;
          }
          const merged = await requestJson("/minimax_director/project/merge", {current:timelineState,incoming:data.timeline,policy});
          timelineState = merged.timeline;
          if (timelineState.builder_state !== undefined) builderState = typeof timelineState.builder_state === "string" ? JSON.parse(timelineState.builder_state || "{}") : timelineState.builder_state;
          if (merged.missing?.length) alert(`Missing media files: ${merged.missing.join(", ")}`);
          // Unify REF2V into REF2VA
          if (Array.isArray(timelineState.clips)) {
            timelineState.clips.forEach((c) => {
              if (c.type === "REF2V") c.type = "REF2VA";
            });
          }
          refreshFileRefs(); syncState();
          activeClipId=timelineState.clips?.[0]?.id;renderTimeline();
          showProjectFeedback('success','Project Imported. Existing Results Reconnect Only When They Exist On This Server.');
        }
      } catch (err) {
        showProjectFeedback('error',`Import Failed: ${err.message}`);
      }
      finally{importBtn.disabled=false;importBtn.textContent='Import Project';importBtn.removeAttribute('aria-busy');}
    };
    fileInput.click();
  };


  const progressLabel = document.createElement("span"); progressLabel.className = "mmx-progress-label"; progressLabel.style.fontSize = "11px"; toolbarLeft.appendChild(progressLabel);
  const field = (title, control, help = "") => {
    const label = document.createElement("label"); label.className = "mmx-field";
    const caption = document.createElement("span"); caption.textContent = title;
    label.append(caption, control);
    if (help) { const note=document.createElement("small");note.textContent=help;label.append(note); }
    return label;
  };
  const finishSection = (section, description) => {
    section.classList.add("mmx-section");
    const summary=section.querySelector(":scope > summary");
    const body=document.createElement("div");body.className="mmx-section-body";
    const intro=document.createElement("p");intro.className="mmx-section-intro";intro.textContent=description;body.append(intro);
    for (const child of [...section.childNodes]) if (child!==summary) body.append(child);
    if (section===projectTools) {
      // Three labelled cards instead of a wall of equal full-width buttons:
      // files, recovery, and destructive actions kept apart.
      const actions=document.createElement("div");actions.className="mmx-project-actions";
      const buttons=[...body.children].filter(child=>child.tagName==='BUTTON' && child!==cancelExport);
      const cards=[['files','Files',['new','import','export']],['recovery','Recovery',['restore']],['danger','Clear',['reset','delete-results']]];
      for (const [key,title,names] of cards) {
        const card=document.createElement('section');card.className=`mmx-project-card mmx-project-card-${key}`;
        const heading=document.createElement('h4');heading.textContent=title;
        const row=document.createElement('div');row.className='mmx-project-card-buttons';
        for (const name of names) {
          const button=buttons.find(b=>b.dataset.projectAction===name);if(!button)continue;
          row.append(button);if(button===exportBtn)row.append(cancelExport);
        }
        card.append(heading,row);
        if(key==='files'){
          const choices=document.createElement('div');choices.className='mmx-export-choices';
          const caption=document.createElement('span');caption.textContent='Export includes';
          choices.append(caption,body.querySelector('.mmx-export-options'),body.querySelector('.mmx-export-result-options'));card.append(choices);
        }
        actions.append(card);
      }
      for (const button of buttons) if(button.parentElement===body)actions.querySelector('.mmx-project-card-buttons').append(button);
      body.append(actions);
    }
    section.append(body);
  };
  const projectTools = document.createElement("details");
  const projectHeading = document.createElement("summary"); projectHeading.textContent = "Project";
  const projectScope=document.createElement("span");projectScope.textContent="All Clips · Projects & Files";projectHeading.append(projectScope);
  projectTools.appendChild(projectHeading);
  const library=document.createElement('div');library.className='mmx-project-library';
  const projectName=document.createElement('input');projectName.type='text';projectName.maxLength=128;
  projectName.placeholder='Name Your Project';projectName.value=timelineState.project_name || '';
  projectName.setAttribute('aria-label','Project Name');
  projectName.oninput=()=>{timelineState.project_name=projectName.value;syncState();};
  const nameField=field('Project Name',projectName);nameField.classList.add('mmx-project-name-field');
  const projectFeedback=document.createElement('div');projectFeedback.className='mmx-project-feedback';
  projectFeedback.setAttribute('role','status');projectFeedback.setAttribute('aria-live','polite');
  const showProjectFeedback=(state,message)=>{projectFeedback.dataset.state=state;projectFeedback.textContent=message;};
  const saveProject=document.createElement('button');saveProject.textContent='Save Project';
  saveProject.title='Save the named timeline and workflow on this server. Latents stay in the existing server cache.';
  const saveProjectNow=async(overwriteRevision)=>{
    if(saveProject.disabled)return;
    if(!projectName.value.trim()){showProjectFeedback('error','Enter a project name before saving.');projectName.focus();return;}
    saveProject.disabled=true;saveProject.textContent='Saving…';saveProject.setAttribute('aria-busy','true');
    showProjectFeedback('busy','Saving project on server…');
    try{
      timelineState.project_name=projectName.value.trim();syncState();
      const graph=app.rootGraph || app.graph;
      if(!graph?.serialize)throw new Error('ComfyUI workflow serialization is unavailable.');
      const snapshot=JSON.parse(JSON.stringify({...timelineState,builder_state:builderState}));
      const capturedSignature=projectSignature();
      const result=await requestJson('/minimax_director/project/save',{
        project_id:snapshot.project_id,name:snapshot.project_name,timeline:snapshot,
        workflow:graph.serialize(),master_node_id:node.id,
        expected_revision:overwriteRevision ?? (snapshot.server_revision || null)});
      if(timelineState.project_id===snapshot.project_id){
        timelineState.server_revision=result.project.revision;sessionRevisions.set(snapshot.project_id,result.project.revision);savedProjectSignature=capturedSignature;syncState();
      }
      showProjectFeedback('success',`Saved “${snapshot.project_name}” on server · ${new Date().toLocaleTimeString()}`);
    }catch(error){
      const current=error.status===409 ? error.result?.current : null;
      if(current?.revision){
        // A newer save exists (another tab, an undo to before the last save,
        // or an older copy of the workflow). Let the user choose explicitly.
        const when=new Date(current.updated_at*1000).toLocaleString();
        // Same project ID (saved clips are attached to it), but this timeline
        // was not opened from that saved copy, so replacing it needs consent.
        const typedName=projectName.value.trim();
        showProjectFeedback('error',current.name!==typedName
          ? `This project ID already has a server save named “${current.name}” (${when}, ${current.clip_count} clips). Overwrite it to save as “${typedName}”; saved clips stay attached.`
          : `“${current.name}” was saved more recently on the server (${when}, ${current.clip_count} clips) than this timeline knows about.`);
        const choices=document.createElement('span');choices.className='mmx-feedback-actions';
        const overwrite=document.createElement('button');overwrite.textContent='Overwrite with this version';
        overwrite.onclick=()=>{if(confirm(`Replace the saved “${current.name}” (${when}) with the timeline shown here?`))void saveProjectNow(current.revision);};
        const reopen=document.createElement('button');reopen.textContent='Open saved version';reopen.onclick=()=>openProject.click();
        choices.append(overwrite,reopen);projectFeedback.append(choices);
      }else showProjectFeedback('error',`Save failed: ${error.message}`);
    }finally{saveProject.disabled=false;saveProject.textContent='Save Project';saveProject.removeAttribute('aria-busy');}
  };
  saveProject.onclick=()=>saveProjectNow();
  const openProject=document.createElement('button');openProject.textContent='Open Project';
  openProject.title='Choose a named project saved on this server and reopen its workflow and cached results.';
  openProject.onclick=async()=>{
    if(openProject.disabled)return;
    openProject.disabled=true;openProject.textContent='Loading Projects…';openProject.setAttribute('aria-busy','true');
    showProjectFeedback('busy','Loading Saved Projects From Server…');
    try{
      const {projects}=await requestJson('/minimax_director/project/list');
      if(node.__mmxDisposed)return;
      node.__mmxProjectDialog?.remove();
      const backdrop=document.createElement('div');backdrop.className='mmx-modal-backdrop';
      node.__mmxProjectDialog=backdrop;
      const panel=document.createElement('div');panel.className='mmx-modal-panel';panel.setAttribute('role','dialog');
      panel.setAttribute('aria-modal','true');panel.setAttribute('aria-label','Open Server Project');
      const heading=document.createElement('h3');heading.textContent='Open Server Project';
      const select=document.createElement('select');select.className='mmx-server-project-list';select.size=Math.min(8,Math.max(3,projects.length));
      select.setAttribute('aria-label','Saved Projects');
      for(const project of projects){const option=document.createElement('option');option.value=project.project_id;
        option.textContent=`${project.name} · ${project.clip_count} Clips · ${new Date(project.updated_at*1000).toLocaleString()}`;select.append(option);}
      if(projects.length)select.value=projects.some(p=>p.project_id===timelineState.project_id)?timelineState.project_id:projects[0].project_id;
      const note=document.createElement('p');note.className='mmx-server-project-note';note.setAttribute('role','status');note.textContent=projects.length
        ? 'Reopens the saved workflow. Media and large latent files stay on the server.' : 'No Saved Projects Yet. Enter a name and use Save Project.';
      const actions=document.createElement('div');actions.className='mmx-server-project-dialog-actions';
      const cancel=document.createElement('button');cancel.textContent='Cancel';cancel.onclick=()=>backdrop.remove();
      const load=document.createElement('button');load.textContent='Open Project';load.disabled=!projects.length;
      load.onclick=async()=>{
        if(load.disabled)return;
        load.disabled=true;load.textContent='Opening…';load.setAttribute('aria-busy','true');
        note.dataset.state='busy';note.textContent='Opening Saved Workflow…';
        try{
          const {project}=await requestJson(`/minimax_director/project/load?project_id=${encodeURIComponent(select.value)}`);
          if(project?.project_id && project.timeline?.server_revision)sessionRevisions.set(project.project_id,project.timeline.server_revision);
          const workflow=project.workflow;
          const master=workflow?.nodes?.find(row=>String(row.id)===String(project.master_node_id));
          if(!master || !app.loadGraphData)throw new Error('This saved project has no reopenable Master workflow.');
          const timeline=JSON.stringify(project.timeline),builder=typeof project.timeline.builder_state==='string'
            ? project.timeline.builder_state : JSON.stringify(project.timeline.builder_state || {});
          master.widgets_values_named={...master.widgets_values_named,timeline_data:timeline,builder_state:builder};
          const savedMode={"Next shot":"Next clip","All shots":"All clips"}[project.timeline.generation_mode] || project.timeline.generation_mode || 'Next clip';
          master.widgets_values_named.generation_mode=savedMode;
          master.widgets_values=[savedMode,timeline,builder];
          const filename=`MiniMax Project ${project.name.replace(/[\\/:*?"<>|]/g,'_')} ${project.project_id}.json`;
          const opened=await app.loadGraphData(workflow,true,true,filename);
          if(opened===false)throw new Error('ComfyUI could not open this project. Check the workflow loading error.');
          backdrop.remove();
        }catch(error){note.dataset.state='error';note.textContent=`Open Failed: ${error.message}`;}
        finally{load.disabled=false;load.textContent='Open Project';load.removeAttribute('aria-busy');}
      };
      backdrop.onkeydown=event=>{
        if(event.key==='Escape')backdrop.remove();
        if(event.key==='Tab'){
          const controls=[select,cancel,load].filter(control=>!control.disabled);
          const first=controls[0],last=controls.at(-1);
          if(event.shiftKey && document.activeElement===first){event.preventDefault();last.focus();}
          else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first.focus();}
        }
        event.stopPropagation();
      };
      backdrop.onclick=event=>{if(event.target===backdrop)backdrop.remove();};
      actions.append(cancel,load);panel.append(heading,note,select,actions);backdrop.append(panel);document.body.append(backdrop);select.focus();
      showProjectFeedback('success',projects.length ? 'Saved Projects Ready. Choose A Project In The Open Dialog.' : 'No Saved Projects Yet. Name Your Project And Save It First.');
    }catch(error){showProjectFeedback('error',`Could Not Load Projects: ${error.message}`);}finally{openProject.disabled=false;openProject.textContent='Open Project';openProject.removeAttribute('aria-busy');}
  };
  serverStatus=document.createElement('span');serverStatus.className='mmx-server-project-status';serverStatus.setAttribute('role','status');updateServerStatus();
  const clearVram=document.createElement('button');clearVram.textContent='Clear VRAM';
  clearVram.dataset.projectAction='clear-vram';
  clearVram.title='Unload GPU models when the queue is idle. Keeps saved clips, reference latents and project files. The next generation reloads the model.';
  clearVram.onclick=async(event)=>{
    event?.preventDefault();event?.stopPropagation();
    if(clearVram.disabled)return;
    clearVram.disabled=true;clearVram.textContent='Clearing…';clearVram.setAttribute('aria-busy','true');
    showProjectFeedback('busy','Requesting VRAM Release…');
    try{
      const result=await requestJson('/minimax_director/memory/release',{});
      showProjectFeedback('success',result.message);
    }catch(error){projectTools.open=true;showProjectFeedback('error',`Could Not Clear VRAM: ${error.message}`);}
    finally{clearVram.disabled=false;clearVram.textContent='Clear VRAM';clearVram.removeAttribute('aria-busy');}
  };
  projectHeading.append(clearVram);
  saveProject.classList.add('mmx-primary-action');library.append(nameField,serverStatus,saveProject,openProject,projectFeedback);projectTools.append(library);
  const addProjectAction = (label, handler) => {
    const button = document.createElement("button"); button.textContent = label;
    button.dataset.projectAction=({"Delete Saved Results":"delete-results","Restore Last Autosave":"restore","New Project":"new"})[label];
    if(label==="Delete Saved Results")button.classList.add("mmx-project-danger");
    button.title=({"Delete Saved Results":"Delete cached results and the last autosave for this project. Keep the current timeline and uploaded references.","Restore Last Autosave":"Replace the current timeline with the snapshot saved after the last generated clip. Does not resume rendering.","New Project":"Start a blank timeline with a new project ID and fresh shared/audio settings. Existing server-side saved results are kept."})[label] || label;
    button.onclick = async () => {
      if(button.disabled)return;
      button.disabled=true;button.textContent=({"Delete Saved Results":"Deleting…","Restore Last Autosave":"Restoring…","New Project":"Creating…"})[label] || `${label}…`;button.setAttribute('aria-busy','true');
      showProjectFeedback('busy',`${label}…`);
      try{const changed=await handler();showProjectFeedback(changed===false?'idle':'success',changed===false?`${label} Cancelled.`:({"Delete Saved Results":"Saved Results And Previews Deleted. Timeline And Uploaded References Kept.","Restore Last Autosave":"Last Generated Timeline Snapshot Restored. Rendering Has Not Started.","New Project":"New Unsaved Project Created. Previous Saved Results Kept."})[label]);}
      catch(error){showProjectFeedback('error',`${label} Failed: ${error.message}`);}
      finally{button.disabled=false;button.textContent=label;button.removeAttribute('aria-busy');}
    };
    projectTools.appendChild(button);
  };
  addProjectAction("Delete Saved Results", async () => {
    if (!confirm("Delete this project's cached results and last autosave? The current timeline and uploaded references are kept.")) return false;
    await requestJson("/minimax_director/project/clear_cache", {project_id: timelineState.project_id});
    cachedClipResults={};cacheStatusRequest++;
    timelineState.clips.forEach(clip => { clip.validated = false; }); syncState(); renderTimeline();
  });
  const exportPortable=async(signal)=>{
    const blob = await transferRequest('/minimax_director/project/portable/export',{body:{project_id:timelineState.project_id,timeline:{...timelineState,builder_state:builderState},
      workflow:(app.rootGraph || app.graph)?.serialize?.(),master_node_id:node.id,include_media:includeMedia.checked,include_results:includeResults.checked},signal,blob:true,onProgress:e=>showProjectFeedback('busy',transferLabel(e))});
    if(signal?.aborted)throw new DOMException('Download cancelled','AbortError');
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a"); link.href = url; link.download = "MiniMaxProject.mmxproj"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const importPortable=async(file,policy)=>{
        const data = new FormData(); data.append("project", file);
        const result=await transferRequest('/minimax_director/project/portable/import',{body:data,onProgress:e=>showProjectFeedback('busy',transferLabel(e))});
        if(policy==='workflow'){
          if(!result.workflow || !app.loadGraphData)throw Error('This archive has no saved workflow; use overwrite for its timeline.');
          await app.loadGraphData(result.workflow,true,true,'MiniMax Imported Project.json');return;
        }
          const rebound=result.project?await requestJson('/minimax_director/project/import',{project:result.project,reference_catalog:timelineState.available_refs}):result;
          const merged = await requestJson("/minimax_director/project/merge", { current: timelineState, incoming: rebound.timeline, policy });
        timelineState = merged.timeline;
        if (merged.missing?.length) alert(`Missing media files: ${merged.missing.join(", ")}`);
        builderState = typeof timelineState.builder_state === "string" ? JSON.parse(timelineState.builder_state || "{}") : timelineState.builder_state || builderState;activeClipId=timelineState.clips?.[0]?.id; refreshFileRefs(); syncState(); renderTimeline();
  };
  const exportOptions=field("Include source/reference media",includeMedia,"Includes input assets, not model weights or generated latents. Off by default.");exportOptions.classList.add("mmx-export-options");exportOptions.prepend(includeMedia);
  const resultOptions=field('Include generated results',includeResults,'Includes saved clip latents, frames and audio. Can be very large. Neither option checked: editable JSON only.');resultOptions.classList.add('mmx-export-result-options');resultOptions.prepend(includeResults);
  projectTools.append(exportBtn,cancelExport,importBtn,exportOptions,resultOptions);
  addProjectAction("Restore Last Autosave", async () => {
    const result = await requestJson(`/minimax_director/project/recover?project_id=${encodeURIComponent(timelineState.project_id || "default_director")}`);
    timelineState = result.timeline; builderState = timelineState.builder_state || builderState;
    refreshFileRefs(); syncState(); renderTimeline();
  });
  addProjectAction("New Project", async () => {
    timelineState = { version: 2, project_id: `project_${crypto.randomUUID()}`, clips: [{ id: "clip_1", name: "Clip 1", type: "T2V", duration: 5, prompt: "", seed: "0" }], references: [] };
    builderState = {}; activeClipId = "clip_1"; syncState(); renderTimeline();
  });
  const sharedPrompt = document.createElement("textarea"); sharedPrompt.placeholder = "Shared prompt for every clip";
  sharedPrompt.value = timelineState.shared_prompt || "";
  sharedPrompt.onchange = () => { timelineState.shared_prompt = sharedPrompt.value; syncState(); };
  projectTools.appendChild(field("Shared prompt",sharedPrompt,"Added to every clip; each clip keeps its own segment prompt."));
  const fadeLabel = document.createElement("label"); fadeLabel.textContent = "Join Fade (ms) ";
  fadeLabel.title="Softens the beginning and end of assembled clip audio to reduce clicks. Does not change generation context or overlap video frames.";
  const fade = document.createElement("input"); fade.type = "number"; fade.min = "0"; fade.max = "1000"; fade.value = timelineState.audio_fade_ms ?? 15;
  fade.onchange = () => { timelineState.audio_fade_ms = Math.max(0,Math.min(1000,Number(fade.value)||0)); syncState(); }; fadeLabel.appendChild(fade); projectTools.appendChild(fadeLabel);
  const gainLabel = document.createElement("label"); const gain = document.createElement("input"); gain.type = "checkbox"; gain.checked = timelineState.audio_gain_match ?? true;
  gain.onchange = () => { timelineState.audio_gain_match = gain.checked; syncState(); }; gainLabel.append(gain,document.createTextNode("Match audio gain between clips")); projectTools.appendChild(gainLabel);
  const sharedPolicy = document.createElement("select");
  for (const value of ["prepend", "append"]) { const option = document.createElement("option"); option.value = value; option.textContent = value; sharedPolicy.appendChild(option); }
  sharedPolicy.value = timelineState.shared_prompt_policy || "prepend";
  sharedPolicy.onchange = () => { timelineState.shared_prompt_policy = sharedPolicy.value; syncState(); }; projectTools.appendChild(field("Shared prompt placement",sharedPolicy));



  let cancelTimelineDrag = null;
  const unapproveChain = clip => {
    const index = timelineState.clips.indexOf(clip);
    for (let i=index; i>=0 && i<timelineState.clips.length; i++) {
      const item=timelineState.clips[i];
      if (i>index && (item.locked || item.source || item.continuity===false ||
          (item.continuity_mode || 'Independent (No Continuity)')==='Independent (No Continuity)' ||
          Number(item.tail_seconds ?? Number(item.tail_frames ?? 12)/24)<=0)) break;
      if (i>index) {
        // Dependent clips keep their approval and saved take until the new
        // take of this clip is actually saved; the Master then removes them
        // and the completed event unticks them. Cancelling keeps them.
        if (item.validated && !item.pending_upstream) item.pending_upstream=clip.id;
        continue;
      }
      item.validated=false; item.refine_approved=false; item.refine_pending=false;
      delete item.pending_upstream;
      item.invalidated_generation=cachedClipResults[item.id]?.generation || null;
    }
  };
  const deleteClip = clip => {
    if(node.inputs?.some(input=>input.name==='timeline' && input.link!=null))return;
    const index = timelineState.clips.indexOf(clip);
    if (index < 0 || !confirm(`Delete "${clip.name || "clip"}" from the timeline?`)) return;
    timelineState.clips.splice(index, 1);
    activeClipId = timelineState.clips[Math.min(index, timelineState.clips.length - 1)]?.id || null;
    syncState(); renderTimeline();
  };
  const moveClip = (clip, destination) => {
    const index = timelineState.clips.indexOf(clip);
    if (index < 0 || clip.locked) return;
    // A locked source stays in place; clips cannot cross it.
    let min = 0, max = timelineState.clips.length - 1;
    timelineState.clips.forEach((clip, position) => {
      if (clip.locked) { if (position < index) min = position + 1; else if (position > index) max = Math.min(max, position - 1); }
    });
    destination = Math.max(min, Math.min(max, destination));
    if (destination === index) return;
    timelineState.clips.splice(index, 1); timelineState.clips.splice(destination, 0, clip);
    activeClipId = clip.id;
    syncState(); renderTimeline();
  };

  // Helper: Deep Clone / Duplicate Clip
  const duplicateClip = (clipToClone) => {
    if (!clipToClone) return;
    const idx = timelineState.clips.indexOf(clipToClone);
    const newId = `clip_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
    const clonedClip = {
      ...JSON.parse(JSON.stringify(clipToClone)),
      id: newId,
      name: `${clipToClone.name || "Clip"} (Copy)`,
      selected: false,
      validated: false, // Reset validation so cloned clip generates
    };
    if (idx !== -1) {
      timelineState.clips.splice(idx + 1, 0, clonedClip);
    } else {
      timelineState.clips.push(clonedClip);
    }
    activeClipId = newId;
    syncState();
    renderTimeline();
    renderInspector();
  };

  const clearBtn = document.createElement("button");
  clearBtn.className = "mmx-action-btn mmx-project-danger";clearBtn.dataset.projectAction="reset";
  clearBtn.textContent = "Reset Timeline";
  clearBtn.title = "Replace all clips with one blank clip. Keep this project ID, shared prompt, audio settings and saved results.";
  clearBtn.onclick = () => {
    if (confirm("Reset timeline to a single default clip?")) {
      timelineState.clips = [
        {
          id: "clip_1",
          name: "Clip 1",
          type: "T2V",
          duration: 5.0,
          prompt: "",
          ref_ids: [],
          continuity: true, continuity_mode: "Independent (No Continuity)", context_length: 22, audio_context_length: 22,
        }
      ];
      activeClipId = "clip_1";
      playheadSeconds = 0.0;
      syncState();
      renderTimeline();
      showProjectFeedback('success','Timeline Reset To One Blank Clip. Saved Results And Project Settings Kept.');
    }else{showProjectFeedback('idle','Reset Timeline Cancelled.');}
  };
  projectTools.appendChild(clearBtn);

  // Preview Output Mode Selector
  toolbar.appendChild(toolbarLeft);

  // Right toolbar group: Duration, Timecode, Zoom
  const toolbarRight = document.createElement("div");
  toolbarRight.className = "mmx-toolbar-right";

  const durationTotal = document.createElement("div");
  durationTotal.style.fontSize = "11px";
  durationTotal.style.fontWeight = "600";
  durationTotal.style.color = "#94a3b8";
  durationTotal.textContent = "Total: 5.0s / 120f";
  toolbarRight.appendChild(durationTotal);

  const timecodeBadge = document.createElement("input");
  timecodeBadge.type = "text";
  timecodeBadge.setAttribute("aria-label", "Timeline Timecode");
  timecodeBadge.title = "Enter HH:MM:SS:FF (24 fps) or seconds to move the playhead.";
  timecodeBadge.className = "mmx-timecode-display";
  timecodeBadge.value = "00:00:00:00";
  toolbarRight.appendChild(timecodeBadge);

  const zoomWrap = document.createElement("div");
  zoomWrap.className = "mmx-zoom-slider-wrap";
  zoomWrap.title = "Timeline zoom";
  zoomWrap.innerHTML = `<span>Zoom</span>`;

  const zoomSlider = document.createElement("input");
  zoomSlider.type = "range";
  zoomSlider.min = "0.5";
  zoomSlider.max = "3.0";
  zoomSlider.step = "0.1";
  zoomLevel = Math.max(0.5,Math.min(3,Number(node.properties?.mmx_timeline_zoom) || 3));
  zoomSlider.value = String(zoomLevel);
  zoomSlider.className = "mmx-zoom-slider";zoomSlider.setAttribute("aria-label","Timeline zoom");
  zoomSlider.oninput = () => {
    zoomLevel = parseFloat(zoomSlider.value) || 1.0;
    node.properties ||= {}; node.properties.mmx_timeline_zoom = zoomLevel;
    renderTimeline();
  };
  ["mousedown", "pointerdown", "touchstart"].forEach((evt) => {
    zoomSlider.addEventListener(evt, (e) => e.stopPropagation());
  });
  zoomWrap.appendChild(zoomSlider);
  toolbarRight.appendChild(zoomWrap);


  toolbar.appendChild(toolbarRight);
  root.appendChild(toolbar);
  if(generationWidget) {
    generationWidget.value=generationDisplay(timelineState.generation_mode || generationWidget.value);
    const prior=generationWidget.callback;
    generationWidget.callback=function(value,...args){prior?.call(this,value,...args);timelineState.generation_mode=generationDisplay(value);syncState();};
  }

  finishSection(projectTools,"Named server projects, file backups and recovery. Canvas and sampling are set in the settings bar at the top of this node.");
  projectTools.classList.add("mmx-project-workspace");
  const group=(title,...controls)=>{const box=document.createElement("section");box.className="mmx-project-group";const heading=document.createElement("h3");heading.textContent=title;box.append(heading,...controls);return box;};
  const sharedPromptSection=document.createElement("section");sharedPromptSection.className="mmx-shared-prompt";
  const sharedPromptHeader=document.createElement("div");sharedPromptHeader.className="mmx-shared-prompt-header";
  const sharedPromptHeading=document.createElement("h3");sharedPromptHeading.textContent="Shared prompt";
  sharedPromptHeader.append(sharedPromptHeading,sharedPolicy.closest(".mmx-field"));
  const oldPromptField=sharedPrompt.closest(".mmx-field");
  sharedPromptSection.append(sharedPromptHeader,sharedPrompt);oldPromptField.remove();
  sharedPrompt.setAttribute("aria-label","Shared prompt");sharedPrompt.title="Applies to every clip. Placement controls whether it comes before or after the clip prompt.";
  sharedPolicy.closest(".mmx-field").classList.add("mmx-project-placement");
  fadeLabel.classList.add("mmx-project-audio-fade");
  const audioGroup=group("Output Audio",fadeLabel,gainLabel);
  audioGroup.classList.add("mmx-timeline-audio");
  audioGroup.title="Applies when joining completed clips: fades edges to reduce clicks and matches loudness. Separate from generation and continuity context.";
  // Canvas, sampler and output settings (formerly the separate Settings node).
  const settingsBar=document.createElement("section");settingsBar.className="mmx-settings-bar";
  let samplerChoices=null;
  const samplerChoicesReady=()=>samplerChoices ||= api.fetchApi("/object_info/KSampler").then(r=>r.json()).then(info=>{
    const req=info?.KSampler?.input?.required || {};
    return {samplers:req.sampler_name?.[0] || [],schedulers:req.scheduler?.[0] || []};
  }).catch(()=>({samplers:[],schedulers:[]}));
  const socketLinked=name=>node.inputs?.some(input=>input.name===name && input.link!=null);
  const renderSettingsBar=()=>{
    const st=timelineState.settings ||= {};
    const res=st.resolution ||= {mode:"manual",width:st.width ?? 1344,height:st.height ?? 768,megapixels:1,aspect:"16:9"};
    const save=()=>{if(res.mode==="manual"){st.width=Number(res.width);st.height=Number(res.height);}syncState();};
    settingsBar.replaceChildren();
    const item=(label,control,title="")=>{const wrap=document.createElement("label");wrap.className="mmx-setting";if(title)wrap.title=title;const cap=document.createElement("span");cap.textContent=label;wrap.append(cap,control);settingsBar.append(wrap);return wrap;};
    const select=(values,value,onchange)=>{const el=document.createElement("select");for(const [v,t] of values){const o=document.createElement("option");o.value=v;o.textContent=t;el.append(o);}
      if(value!=null && ![...el.options].some(o=>o.value===String(value))){const o=document.createElement("option");o.value=value;o.textContent=value;el.append(o);}el.value=String(value);el.onchange=()=>onchange(el.value);return el;};
    const number=(value,min,max,step,onchange,width=64)=>{const el=document.createElement("input");el.type="number";el.min=min;el.max=max;el.step=step;el.value=value;el.style.width=width+"px";
      el.onchange=()=>{let v=Number(el.value);if(!Number.isFinite(v))v=Number(min);v=Math.max(Number(min),Math.min(Number(max),v));if(step>=1)v=Math.round(v/step)*step;el.value=v;onchange(v);};return el;};
    item("Canvas",select([["manual","Manual"],["original","Original size"],["auto","Auto"]],res.mode||"manual",v=>{res.mode=v;save();renderSettingsBar();}),"Manual: width and height below. Original: follow the source video. Auto: megapixels and aspect.");
    if((res.mode||"manual")==="manual"){
      const size=document.createElement("span");size.className="mmx-setting-size";
      size.append(number(res.width ?? 1344,32,4096,32,v=>{res.width=v;save();},68),Object.assign(document.createElement("span"),{textContent:"×"}),number(res.height ?? 768,32,4096,32,v=>{res.height=v;save();},68));
      item("Size",size,"Pixels; multiples of 32.");
    } else if(res.mode==="auto"){
      item("MP",number(res.megapixels ?? 1,0.1,16,0.1,v=>{res.megapixels=v;save();},60));
      item("Aspect",select(["16:9","9:16","1:1","4:3","3:4","21:9","3:2","2:3","auto"].map(v=>[v,v]),res.aspect||"16:9",v=>{res.aspect=v;save();}));
    }
    const divider=()=>{const d=document.createElement("span");d.className="mmx-setting-divider";settingsBar.append(d);};
    divider();
    const sampler=select([[st.sampler||"res_multistep",st.sampler||"res_multistep"]],st.sampler||"res_multistep",v=>{st.sampler=v;save();});
    const scheduler=select([[st.scheduler||"simple",st.scheduler||"simple"]],st.scheduler||"simple",v=>{st.scheduler=v;save();});
    samplerChoicesReady().then(({samplers,schedulers})=>{
      for(const [el,list] of [[sampler,samplers],[scheduler,schedulers]]){const keep=el.value;for(const v of list)if(![...el.options].some(o=>o.value===v)){const o=document.createElement("option");o.value=v;o.textContent=v;el.append(o);}el.value=keep;}
    });
    item("Sampler",sampler,"Sampling method used for every clip.");
    item("CFG",number(st.cfg ?? 1,0,20,0.1,v=>{st.cfg=v;save();},54),"Guidance scale. 1.0 for distilled or Lightning setups.");
    const sigmas=socketLinked("sigmas"),stepsLinked=socketLinked("steps");
    const pill=text=>{const el=document.createElement("span");el.className="mmx-setting-pill";el.textContent=text;return el;};
    if(sigmas || stepsLinked)item("Steps",pill(sigmas?"from sigmas":"from input"),sigmas?"Steps come from the connected sigmas schedule.":"Steps come from the connected steps input.");
    else item("Steps",number(st.steps ?? 25,1,200,1,v=>{st.steps=v;save();},54),"Sampling steps.");
    if(sigmas)item("Scheduler",pill("from sigmas"),"The schedule comes from the connected sigmas input.");
    else item("Scheduler",scheduler,"Noise schedule.");
    divider();
    item("Output",select([["latest","Latest clip"],["full","Full sequence"]],st.decoded_output||"latest",v=>{st.decoded_output=v;save();}),
      "Latest returns the last generated clip as frames (all clips still save for Smart Preview and Project Video). Full assembles every clip.");
  };
  renderSettingsBar();
  root.append(settingsBar);
  root.append(projectTools);


  // 2. Multi-Track Timeline Panel (4 Sub-Tracks + Ruler)
  root.append(toolbar);
  const multitrackPanel = document.createElement("div");
  multitrackPanel.className = "mmx-multitrack-panel";

  // Shared Playhead Needle spanning all tracks
  const playheadNeedle = document.createElement("div");
  playheadNeedle.className = "mmx-playhead-needle";
  const playheadHandle = document.createElement("div");
  playheadHandle.className = "mmx-playhead-handle";
  playheadHandle.innerHTML = `<svg width="11" height="14" viewBox="0 0 11 14" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M 0.5 0.5 H 10.5 V 8.5 L 5.5 13.5 L 0.5 8.5 Z" fill="#ef4444" stroke="rgba(255, 255, 255, 0.5)" stroke-width="1"/></svg>`;
  playheadNeedle.appendChild(playheadHandle);

  // Row 0: Time Ruler
  const rulerRow = document.createElement("div");
  rulerRow.className = "mmx-track-row mmx-track-row-ruler";
  const rulerHeader = document.createElement("div");
  rulerHeader.className = "mmx-track-header-cell";
  rulerHeader.innerHTML = `<span>⏱️</span><span>Timecode</span>`;
  const rulerLane = document.createElement("div");
  rulerLane.className = "mmx-track-lane-cell mmx-ruler-lane";
  const rulerTicks = document.createElement("div");
  rulerTicks.className = "mmx-time-ruler";
  rulerLane.appendChild(rulerTicks);
  rulerRow.appendChild(rulerHeader);
  rulerRow.appendChild(rulerLane);
  multitrackPanel.appendChild(rulerRow);

  // Row 1: Clips Track (Clips + Prompt)
  const shotsRow = document.createElement("div");
  shotsRow.className = "mmx-track-row mmx-track-row-shots";
  const shotsHeader = document.createElement("div");
  shotsHeader.className = "mmx-track-header-cell";
  shotsHeader.innerHTML = `<span>▤</span><span>Clips</span>`;
  const shotsLane = document.createElement("div");
  shotsLane.className = "mmx-track-lane-cell mmx-shots-lane";
  shotsRow.appendChild(shotsHeader);
  shotsRow.appendChild(shotsLane);
  multitrackPanel.appendChild(shotsRow);

  // Row 2: Ref Images Track
  const imagesRow = document.createElement("div");
  imagesRow.className = "mmx-track-row mmx-track-row-images";
  const imagesHeader = document.createElement("div");
  imagesHeader.className = "mmx-track-header-cell";
  imagesHeader.innerHTML = `<span>🖼️</span><span>Images</span>`;
  const imagesLane = document.createElement("div");
  imagesLane.className = "mmx-track-lane-cell mmx-images-lane";
  imagesRow.appendChild(imagesHeader);
  imagesRow.appendChild(imagesLane);
  multitrackPanel.appendChild(imagesRow);

  // Row 3: Ref Videos Track
  const videosRow = document.createElement("div");
  videosRow.className = "mmx-track-row mmx-track-row-videos";
  const videosHeader = document.createElement("div");
  videosHeader.className = "mmx-track-header-cell";
  videosHeader.innerHTML = `<span>📹</span><span>Videos</span>`;
  const videosLane = document.createElement("div");
  videosLane.className = "mmx-track-lane-cell mmx-videos-lane";
  videosRow.appendChild(videosHeader);
  videosRow.appendChild(videosLane);
  multitrackPanel.appendChild(videosRow);

  // Row 4: Ref Audios Track
  const audiosRow = document.createElement("div");
  audiosRow.className = "mmx-track-row mmx-track-row-audios";
  const audiosHeader = document.createElement("div");
  audiosHeader.className = "mmx-track-header-cell";
  audiosHeader.innerHTML = `<span>🎵</span><span>Audio</span>`;
  const audiosLane = document.createElement("div");
  audiosLane.className = "mmx-track-lane-cell mmx-audios-lane";
  audiosRow.appendChild(audiosHeader);
  audiosRow.appendChild(audiosLane);
  multitrackPanel.appendChild(audiosRow);

  // Append Playhead Needle LAST so it floats ON TOP of all tracks
  multitrackPanel.appendChild(playheadNeedle);

  root.appendChild(multitrackPanel);
  sharedPromptSection.append(audioGroup);root.append(sharedPromptSection);

  // 3. Active Clip Inspector (Directly below timeline - 100% pure timeline!)
  const inspector = document.createElement("div");
  inspector.className = "mmx-inspector";
  root.appendChild(inspector);

  // Timecode formatting: seconds -> HH:MM:SS:FF (at 24fps)
  const formatTimecode = (sec, fps = 24) => {
    const totalFrames = Math.max(0, Math.round(sec * fps));
    const ff = totalFrames % fps;
    const totalSecs = Math.floor(totalFrames / fps);
    const ss = totalSecs % 60;
    const mm = Math.floor(totalSecs / 60) % 60;
    const hh = Math.floor(totalSecs / 3600);
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(hh)}:${pad(mm)}:${pad(ss)}:${pad(ff)}`;
  };

  // Share one time scale between clips, ruler and scrubbing. Round the visible
  // horizon to a labeled interval, rather than stopping labels at the last clip.
  const timelineGeometry = () => {
    const panelPadding=parseFloat(getComputedStyle(multitrackPanel).paddingLeft)||0;
    const origin = panelPadding + (rulerHeader.offsetWidth || 112) + 6;
    const viewport = Math.max(1, (multitrackPanel.clientWidth || 930) - origin - 6 - panelPadding);
    const duration = timelineState.clips.reduce((sum, clip) => sum + (parseFloat(clip.duration) || 5), 0);
    const nominalScale = 64 * zoomLevel;
    const majorStep = nominalScale > 40 ? 1 : 2;
    const width = Math.max(viewport, duration * nominalScale + 100);
    const end = Math.max(majorStep, Math.ceil(width / nominalScale / majorStep) * majorStep);
    return {origin, width, end, duration, majorStep, pxPerSec: width / end};
  };

  const drawRuler = () => {
    const {origin, width, end, majorStep, pxPerSec} = timelineGeometry();
    rulerTicks.style.width = `${width}px`;
    rulerTicks.replaceChildren();
    multitrackPanel.style.setProperty("--mmx-grid-step", `${majorStep * pxPerSec}px`);
    // Keep every reference lane aligned with the same clip boundaries.
    [shotsLane, imagesLane, videosLane, audiosLane].forEach(lane => {
      [...lane.querySelectorAll('.mmx-subtrack-block')].forEach((block, index) => {
        const clip = timelineState.clips[index];
        if (clip) block.style.width = `${(parseFloat(clip.duration) || 5) * pxPerSec - 4}px`;
      });
    });
    const stepSec = majorStep / 2;
    const ticks = document.createDocumentFragment();
    for (let index = 0; index <= Math.round(end / stepSec); index++) {
      const seconds = index * stepSec;
      const major = index % 2 === 0;
      const tick = document.createElement("div");
      tick.className = `mmx-time-tick${major ? " major" : ""}${seconds === end ? " endpoint" : ""}`;
      tick.style.left = `${seconds * pxPerSec}px`;
      if (major) {
        const label = document.createElement("span");
        label.textContent = `${seconds}s`;
        tick.appendChild(label);
      }
      ticks.appendChild(tick);
    }
    rulerTicks.appendChild(ticks);
    for (const link of shotsLane.querySelectorAll('.mmx-continuity-link')) link.style.left=`${4+Number(link.dataset.start)*pxPerSec}px`;
    const playheadX = Math.max(0, Math.min(width, playheadSeconds * pxPerSec));
    playheadNeedle.style.left = `${origin + playheadX}px`;
    // Anchor to the panel instead of inflating its scroll height when lanes hide.
    playheadNeedle.style.height = "auto";
    playheadNeedle.style.bottom = "0px";
    multitrackPanel.scrollTop = 0;
    if (document.activeElement !== timecodeBadge) timecodeBadge.value = formatTimecode(playheadSeconds, 24);
  };

  timecodeBadge.onchange = () => {
    const value = timecodeBadge.value.trim();
    const parts = /^(\d+):([0-5]\d):([0-5]\d):([0-2]\d)$/.exec(value);
    const seconds = parts && Number(parts[4]) < 24 ? Number(parts[1])*3600 + Number(parts[2])*60 + Number(parts[3]) + Number(parts[4])/24 : /^\d+(?:\.\d+)?$/.test(value) ? Number(value) : NaN;
    if (!Number.isFinite(seconds)) { timecodeBadge.setCustomValidity("Enter HH:MM:SS:FF with frames 00-23, or seconds."); timecodeBadge.reportValidity(); return; }
    timecodeBadge.setCustomValidity(""); playheadSeconds = Math.min(timelineGeometry().end, seconds);
    timecodeBadge.value = formatTimecode(playheadSeconds,24); drawRuler();
  };
  timecodeBadge.addEventListener("keydown", event => { if(event.key === "Enter") { timecodeBadge.onchange(); event.stopPropagation(); } });
  for(const event of ["pointerdown","mousedown","keydown"]) timecodeBadge.addEventListener(event,e=>e.stopPropagation());
  let isScrubbing = false;
  const updateScrubFromClientX = (clientX) => {
    const rect = rulerTicks.getBoundingClientRect();
    const {width, end, pxPerSec} = timelineGeometry();
    const x = Math.max(0, Math.min(width, (clientX - rect.left) * width / (rect.width || 1)));
    playheadSeconds = Math.max(0, Math.min(end, x / pxPerSec));
    drawRuler();
  };

  const startScrubbing = (e) => {
    e.stopPropagation();
    e.preventDefault();
    isScrubbing = true;
    updateScrubFromClientX(e.clientX);
    const onMove = (me) => { if (isScrubbing) updateScrubFromClientX(me.clientX); };
    const onUp = () => {
      isScrubbing = false;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  rulerLane.onmousedown = startScrubbing;
  playheadHandle.onmousedown = startScrubbing;

  [shotsLane, imagesLane, videosLane, audiosLane].forEach((lane) => {
    lane.addEventListener("mousedown", (e) => {
      if (e.target === lane) {
        startScrubbing(e);
      }
    });
  });

  // Helper: Open Type Picker Modal (Unified: REF2V merged into REF2VA!)
  const openTypePickerModal = () => {
    const backdrop = document.createElement("div");
    backdrop.className = "mmx-modal-backdrop";

    const panel = document.createElement("div");
    panel.className = "mmx-modal-panel mmx-type-picker";

    panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');panel.setAttribute('aria-label','Add Clip');
    panel.innerHTML = `
      <div class="mmx-modal-header"><span class="mmx-modal-title">Add Clip</span><button class="mmx-action-btn" id="modal-close-btn" aria-label="Close Add Clip">×</button></div>
      <div class="mmx-modal-body"><p class="mmx-picker-intro">Choose what this timeline clip does. Its type stays fixed after creation.</p>
      <h3 class="mmx-picker-heading">Existing Footage</h3><div class="mmx-type-modal-grid"><button class="mmx-type-modal-btn" data-action="import-video" data-type="VIDEO"><span class="mmx-type-modal-btn-title">Add Existing Video</span><span class="mmx-type-modal-btn-desc">Choose one Reference Pack video. Its existing frames are played without generation; later clips can continue from its ending.</span></button></div>
      <h3 class="mmx-picker-heading">Generate A New Video</h3><div class="mmx-type-modal-grid"><button class="mmx-type-modal-btn" data-type="T2V"><span class="mmx-type-modal-btn-title">Text To Video</span><span class="mmx-type-modal-btn-desc">Generate a new clip from a written prompt.</span></button><button class="mmx-type-modal-btn" data-type="I2V"><span class="mmx-type-modal-btn-title">Image To Video</span><span class="mmx-type-modal-btn-desc">Use a Reference Pack image as the opening frame.</span></button><button class="mmx-type-modal-btn" data-type="FL2V"><span class="mmx-type-modal-btn-title">First And Last Frame</span><span class="mmx-type-modal-btn-desc">Use two Reference Pack images as opening and ending frames.</span></button><button class="mmx-type-modal-btn" data-type="L2VA"><span class="mmx-type-modal-btn-title">Ending Image To Video</span><span class="mmx-type-modal-btn-desc">Generate motion ending at a Reference Pack image.</span></button><button class="mmx-type-modal-btn" data-type="REF2VA"><span class="mmx-type-modal-btn-title">Generate From References</span><span class="mmx-type-modal-btn-desc">Generate a new scene using Reference Pack images, videos or audio.</span></button></div>
      <h3 class="mmx-picker-heading">Edit Existing Media</h3><div class="mmx-type-modal-grid"><button class="mmx-type-modal-btn" data-type="V2V"><span class="mmx-type-modal-btn-title">Edit Video</span><span class="mmx-type-modal-btn-desc">Transform an existing source-video range using a prompt.</span></button><button class="mmx-type-modal-btn" data-type="RV2V"><span class="mmx-type-modal-btn-title">Edit Video With References</span><span class="mmx-type-modal-btn-desc">Transform a source-video range using a prompt and extra Reference Pack assets.</span></button><button class="mmx-type-modal-btn" data-type="Image Inpaint"><span class="mmx-type-modal-btn-title">Edit Still Image</span><span class="mmx-type-modal-btn-desc">Edit one Reference Pack image; returns one image instead of a video.</span></button></div></div>`;

    for (const button of panel.querySelectorAll('[data-type]')) {
      const badge=document.createElement('span');const code=clipCode({type:button.dataset.type,locked:button.dataset.type==='VIDEO'});
      badge.className=`mmx-clip-mode-badge mmx-badge-${code.toLowerCase()}`;badge.textContent=code;
      button.querySelector('.mmx-type-modal-btn-title').prepend(badge,document.createTextNode(' '));
    }
    document.body.appendChild(backdrop);
    backdrop.appendChild(panel);

    const close = () => {
      if (backdrop.parentNode) backdrop.parentNode.removeChild(backdrop);
    };

    panel.querySelector("#modal-close-btn").onclick = close;
    backdrop.onkeydown=event=>{if(event.key==="Escape")close();event.stopPropagation();};
    panel.querySelector("#modal-close-btn").focus();
    backdrop.onclick = (e) => {
      if (e.target === backdrop) close();
    };

    panel.querySelectorAll(".mmx-type-modal-btn[data-type]").forEach((btn) => {
      btn.onclick = () => {
        const type = btn.dataset.type;
        const newIndex = timelineState.clips.length + 1;
        const newClip = {
          id: `clip_${Date.now()}_${newIndex}`,
          name: `Clip ${newIndex}`,
          type: type === "VIDEO" ? "V2V" : type,
          locked: type === "VIDEO", audio_mode: type === "VIDEO" ? "source" : "generate",
          duration: 5.0,
          tail_seconds: 0.5,
          seed: Math.floor(Math.random() * 10000000000),
          seed_mode: "fixed",
          validated: false,
          prompt: "",
          prompt_mode: "raw",
          structured_prompt: {
            subject_definitions: "",
            summary: "",
            retention_analysis: "",
            detailed_description: "",
            overall_soundscape: "",
            soundscape: "",
            non_diegetic_music: "",
            music: "",
          },
          ref_ids: [],
          continuity: true, continuity_mode: "Independent (No Continuity)", context_length: 22, audio_context_length: 22,
        };
        timelineState.clips.push(newClip);
        activeClipId = newClip.id;
        syncState();
        renderTimeline();
        close();
      };
    });
  };

  // Video Preview Modal helper
  const openVideoPreviewModal = (videoUrl, videoName) => {
    const backdrop = document.createElement("div");
    backdrop.className = "mmx-modal-backdrop";
    const panel = document.createElement("div");
    panel.className = "mmx-modal-panel";
    panel.style.maxWidth = "600px";
    panel.innerHTML = `
      <div class="mmx-modal-header">
        <span class="mmx-modal-title">🎬 Video Preview: ${escapeHtml(videoName || "Reference Video")}</span>
        <button class="mmx-action-btn" id="vid-modal-close-btn">✕</button>
      </div>
      <div class="mmx-modal-body" style="padding: 10px 0;">
        <video src="${escapeHtml(videoUrl)}" controls autoplay style="width: 100%; max-height: 400px; border-radius: 6px; background: #000;"></video>
      </div>
    `;
    document.body.appendChild(backdrop);
    backdrop.appendChild(panel);
    const close = () => { if (backdrop.parentNode) backdrop.parentNode.removeChild(backdrop); };
    panel.querySelector("#vid-modal-close-btn").onclick = close;
    backdrop.onclick = (e) => { if (e.target === backdrop) close(); };
  };

  // Structured Prompt Scaffolding and Compilation Helpers
  const scaffoldStructuredPrompt = (clip) => {
    const assigned = clip.ref_ids || [];
    const assignedObjs = activeReferences(clip);
    const imgs = assignedObjs.filter((r) => r.type === "image" || r.type === "refmod");
    const vids = assignedObjs.filter((r) => r.type === "video");
    const auds = assignedObjs.filter((r) => r.type === "audio");

    const defs = [];
    const rets = [];
    const subjs = [];

    imgs.forEach((img, idx) => {
      const subj = `<Subject ${subjs.length + 1}>`;
      subjs.push(subj);
      const tag = img.type === "refmod" ? `<RefMod ${idx + 1}>` : `<Picture ${idx + 1}>`;
      defs.push(`${subj} is the main subject in ${tag} (${img.name}).`);
      defs.push(`${tag} defines the appearance and visual identity of ${subj}.`);
      rets.push(`${subj}: fully_preserved - appearance and costume are maintained.`);
    });

    vids.forEach((vid, idx) => {
      const subj = `<Subject ${subjs.length + 1}>`;
      subjs.push(subj);
      defs.push(`${subj} is the motion sequence from <Video ${ownVideoNumber(clip, idx)}> (${vid.name}).`);
      rets.push(`${subj}: attribute_transfer - camera dynamics and pacing are followed.`);
    });

    auds.forEach((aud, idx) => {
      defs.push(`<Audio ${idx + 1}> (${aud.name}) provides the voice and soundscape.`);
      rets.push(`<Audio ${idx + 1}>: reference - acoustics and speech are followed.`);
    });

    const summaryTask = "[reference generation" + (auds.length > 0 ? " + audio reference]" : "]");
    const summaryLine = `${summaryTask} ${clip.name} featuring ${subjs.slice(0, 2).join(" and ") || "the subject"} in dramatic cinematic lighting.`;

    return {
      subject_definitions: defs.join("\n"),
      summary: summaryLine,
      retention_analysis: rets.join("\n"),
      detailed_description: `${clip.name} opens with smooth camera tracking following the subject through the scene with realistic motion.`,
      overall_soundscape: "Natural environmental ambience and synchronized diegetic audio.",
      soundscape: "Natural environmental ambience and synchronized diegetic audio.",
      non_diegetic_music: "N/A",
      music: "N/A",
    };
  };

  const compileStructuredPrompt = (s) => {
    if (!s) return "";
    return [
      s.subject_definitions ? `subject_definitions:\n${s.subject_definitions}` : "",
      s.summary ? `summary:\n${s.summary}` : "",
      s.retention_analysis ? `retention_analysis:\n${s.retention_analysis}` : "",
      s.detailed_description ? `detailed_description:\n${s.detailed_description}` : "",
      (s.overall_soundscape || s.soundscape) ? `overall_soundscape:\n${s.overall_soundscape || s.soundscape}` : "",
      (s.non_diegetic_music || s.music) ? `non_diegetic_music:\n${s.non_diegetic_music || s.music}` : "",
    ].filter(Boolean).join("\n\n");
  };

  // The clip's prompt text is the single source of truth. The Structured
  // editor is a view of it: it parses the text into the official sections
  // (same rules as core/prompt_engine.parse_prompt_sections) and writes every
  // edit back into the text, so Raw and Structured can never disagree.
  const PROMPT_SECTION_KEYS = ["subject_definitions","summary","retention_analysis","detailed_description","integrated_multimodal_description","overall_soundscape","non_diegetic_music"];
  const PROMPT_SECTION_ALIASES = {soundscape:"overall_soundscape",music:"non_diegetic_music",imd:"integrated_multimodal_description"};
  const PROMPT_SECTION_RE = new RegExp(`^[ \\t]*(${[...PROMPT_SECTION_KEYS,...Object.keys(PROMPT_SECTION_ALIASES)].join("|")})[ \\t]*:[ \\t]*`, "gim");
  const parsePromptSections = (text) => {
    text = String(text || "");
    const hits = [...text.matchAll(PROMPT_SECTION_RE)];
    if (!hits.length) return {found:false, fields:{}, preamble:text.trim()};
    const fields = {};
    hits.forEach((hit, i) => {
      const raw = hit[1].toLowerCase(), key = PROMPT_SECTION_ALIASES[raw] || raw;
      const end = i + 1 < hits.length ? hits[i + 1].index : text.length;
      const body = text.slice(hit.index + hit[0].length, end).replace(/^\n+/, "").replace(/\n+$/, "").replace(/\s+$/, "");
      fields[key] = fields[key] ? `${fields[key]}\n${body}` : body;
    });
    return {found:true, fields, preamble:text.slice(0, hits[0].index).trim()};
  };
  const REFERENCE_SECTIONS = [
    {key:"subject_definitions", title:"Subjects", hint:"Who or what each reference is, e.g. <Subject 1> is the woman in <Picture 1>.", rows:3},
    {key:"summary", title:"Summary", hint:"One line: the task and the scene, e.g. [reference generation] A rainy street at night.", rows:2},
    {key:"retention_analysis", title:"Keep from references", hint:"What must stay as in the references, e.g. <Subject 1>: fully_preserved - face and costume.", rows:3},
    {key:"detailed_description", title:"Action and camera", hint:"The continuous action, camera moves and lighting, in order.", rows:6, main:true},
    {key:"overall_soundscape", title:"Sound", hint:"Diegetic sound: voices, ambience, effects.", rows:2, half:true},
    {key:"non_diegetic_music", title:"Music", hint:"Score style, or N/A.", rows:2, half:true},
  ];
  const KEYFRAME_SECTIONS = [
    {key:"integrated_multimodal_description", title:"Description", hint:"The action, camera moves, lighting and dialogue, in order.", rows:7, main:true},
    {key:"overall_soundscape", title:"Sound", hint:"Diegetic sound: voices, ambience, effects.", rows:2, half:true},
    {key:"non_diegetic_music", title:"Music", hint:"Score style, or N/A.", rows:2, half:true},
  ];
  const isReferencePromptMode = clip => ["REF2V","V2V","RV2V"].includes(clipCode(clip));
  const promptSectionsFor = clip => isReferencePromptMode(clip) ? REFERENCE_SECTIONS : KEYFRAME_SECTIONS;
  const structuredFieldsFromText = (text, sections) => {
    const {found, fields, preamble} = parsePromptSections(text);
    const main = sections.find(s => s.main).key;
    if (!found) return {[main]: preamble};
    if (preamble) fields[main] = [preamble, fields[main] || ""].filter(Boolean).join("\n");
    return fields;
  };
  const compilePromptSections = (fields) => PROMPT_SECTION_KEYS
    .filter(key => String(fields[key] || "").trim())
    .map(key => `${key}:\n${String(fields[key]).trim()}`).join("\n\n");
  const storedSections = fields => ({...fields, soundscape:fields.overall_soundscape || "", music:fields.non_diegetic_music || "", imd:fields.integrated_multimodal_description || ""});

  // Clip memory (see core/visual_memory.py): earlier clips, parts of them, or
  // single frames, passed as reference videos / pictures with a visible note
  // added to the prompt. Memory comes after the clip's own references, so the
  // numbers of the user's own videos and pictures never change.
  const MEMORY_INSTRUCTION = "These references are earlier moments of this same film. Keep the people, clothing, setting, lighting and style they show. The camera, framing and action of this clip follow its own description; do not replay those moments.";
  const MEMORY_MAX_SECONDS = 15;
  const memorySupported = clip => ["REF2V","RV2V"].includes(clipCode(clip));
  const memoryRows = clip => (Array.isArray(clip.memory) ? clip.memory : []).filter(row => row && row.enabled !== false && row.clip_id);
  const memoryKind = row => row?.kind === "image" ? "image" : "video";
  const ownCount = (clip, type) => activeReferences(clip).filter(row => row.type === type).length;
  const ownVideoNumber = (clip, k) => k + 1;
  // Prompt tag of an enabled memory row (<Video N> or <Picture N>), else null.
  const memoryTag = (clip, row) => {
    const rows = memoryRows(clip), pos = rows.indexOf(row);
    if (pos < 0) return null;
    const kind = memoryKind(row), n = rows.slice(0, pos).filter(r => memoryKind(r) === kind).length;
    return kind === "image" ? `<Picture ${ownCount(clip, "image") + 1 + n}>` : `<Video ${ownCount(clip, "video") + 1 + n}>`;
  };
  const memorySlots = (clip, kind) => kind === "image" ? Math.max(0, 9 - ownCount(clip, "image")) : Math.max(0, 3 - ownCount(clip, "video"));
  const clipById = id => timelineState.clips.find(c => c.id === id);
  const memoryWindowSeconds = row => { if (memoryKind(row) === "image") return 0; const src = clipById(row.clip_id); const total = Number(src?.duration) || 0; const start = Math.max(0, Number(row.start) || 0); const end = row.end == null ? total : Math.min(total, Number(row.end)); return Math.max(0, end - start); };
  const memoryNoteFor = clip => {
    const rows = memoryRows(clip);
    if (!rows.length || !memorySupported(clip)) return "";
    const lines = rows.map(row => {
      const note = String(row.note || "").split(/\s+/).filter(Boolean).join(" ").slice(0, 200);
      const src = clipById(row.clip_id);
      return `${memoryTag(clip, row)} is ${memoryKind(row) === "image" ? "a frame from an earlier moment" : "an earlier moment"} of this film (${note || src?.name || src?.id || row.clip_id || "an earlier clip"}).`;
    });
    return [...lines, MEMORY_INSTRUCTION].join("\n");
  };

  // Render Multi-Track Timeline & Clips
  const isStartImageClip = clip => ['I2VA','FL2VA','I2V','FL2V'].includes(String(clip?.type || '').toUpperCase()) && !clip?.locked;
  const effectiveContinuity = clip => {
    const M=CONTINUITY_MODES;
    let value=clip.continuity===false || clip.locked || clip.source ? M.independent : (clip.continuity_mode || M.independent);
    if(value==="FL2VA Tail Handoff")value=M.frame;
    if(value!==M.independent)value=isStartImageClip(clip)?M.frame:value===M.frame?M.carry:value;
    return value;
  };
  const antiburnText = burn => burn?.enabled===false ? "Anti-burn LoRA is switched off for this clip (LoRAs tab)." : `Continuing the previous clip adds the anti-burn LoRA automatically at strength ${Number(burn?.strength ?? .5).toFixed(2)}, whichever method or switches you use (change it in the LoRAs tab).`;
  const continuesFromLastFrame = clip => timelineState.clips.indexOf(clip)>0 && isStartImageClip(clip) && effectiveContinuity(clip)===CONTINUITY_MODES.frame;
  const clipCode = clip => clip.locked ? 'VIDEO' : ({T2VA:'T2V',I2VA:'I2V',FL2VA:'FL2V',L2VA:'L2V',REF2VA:'REF2V','Image Inpaint':'IMG','IMAGE INPAINT':'IMG'})[clip.type] || clip.type || 'T2V';
  const referenceTypes = clip => {
    const mode=clipCode(clip);
    if (mode==='T2V') return [];
    if (mode==='I2V' && continuesFromLastFrame(clip)) return [];
    if (['I2V','FL2V','L2V','IMG'].includes(mode)) return ['image'];
    if (['VIDEO','V2V'].includes(mode)) return ['video'];
    return ['image','video','audio','refmod'];
  };
  const selectionLimit = (clip,type) => {
    const code=clipCode(clip);
    if(['VIDEO','V2V','I2V','L2V','IMG'].includes(code)) return 1;
    if(code==='FL2V') return continuesFromLastFrame(clip) ? 1 : 2;
    return ({image:9,video:3,audio:3,refmod:12})[type] || 0;
  };
  const selectionHelp = clip => continuesFromLastFrame(clip) ? (clipCode(clip)==='FL2V' ? "Choose one end image. The start is the previous clip's last frame." : "Starts from the previous clip's last frame; no references are used.") : ({T2V:'Text only.',VIDEO:'Choose exactly one source video.',V2V:'Choose exactly one source video.',I2V:'Choose exactly one start image.',L2V:'Choose one ending image.',FL2V:'Choose two images in order: start, then end.',IMG:'Choose exactly one image to edit.'})[clipCode(clip)] || (clipCode(clip)==='RV2V' ? 'The first selected video is the source. Up to 9 images, 3 videos including the source, 3 audio tracks and 12 total assets.' : 'Up to 9 images, 3 videos, 3 audio tracks and 12 total assets. Audio needs a visual reference.');
  const activeReferences = clip => (clip.ref_ids || []).map(id=>(timelineState.available_refs || []).find(row=>row.id===id)).filter(row=>row && referenceTypes(clip).includes(row.type));
  const refreshClipResults = async () => {
    const project=timelineState.project_id,request=++cacheStatusRequest;
    cacheStatusProject=project;
    try {
      const status=await requestJson(`/minimax_director/project/cache/status?project_id=${encodeURIComponent(project)}`);
      if(node.__mmxDisposed || request!==cacheStatusRequest || project!==timelineState.project_id)return;
      cachedClipResults=status.clips || {};
      let changed=false;
      for(const clip of timelineState.clips){
        const saved=cachedClipResults[clip.id];
        // Missed the completed event: the upstream clip has a newer saved take.
        const upstreamSaved=clip.pending_upstream ? cachedClipResults[clip.pending_upstream] : null;
        if(clip.validated && clip.pending_upstream && upstreamSaved?.generation && upstreamSaved.generation!==timelineState.clips.find(c=>c.id===clip.pending_upstream)?.invalidated_generation){clip.validated=false;delete clip.validated_generation;delete clip.pending_upstream;changed=true;}
        if(saved?.cache_report?.updated_at>(clip.cache_report?.updated_at || 0)){clip.cache_report=saved.cache_report;changed=true;}
        if(saved?.generation && clip.saved_generation!==saved.generation){
          clip.saved_generation=saved.generation;
          if(saved.seed!=null){clip.last_seed=String(saved.seed);if(saved.authored_seed!=null && String(clip.seed)===String(saved.authored_seed) && saved.next_seed!=null)clip.seed=String(saved.next_seed);}
          changed=true;
        }
        if(clip.validated && !clip.validated_generation && saved?.generation){clip.validated_generation=saved.generation;changed=true;}
        if(clip.validated && clip.validated_generation && saved?.generation && clip.validated_generation!==saved.generation && clip.id!==generatingClipId){
          if(freshApprovals.has(clip.id)){
            // Just ticked: the user approved the take the server holds now
            // (the one Smart Preview shows), not an older cached status.
            clip.validated_generation=saved.generation;
          }else{
            // The approved take was replaced and its files removed. Untick it
            // for review instead of letting the next run fail.
            clip.validated=false;delete clip.validated_generation;delete clip.pending_upstream;
            progressLabel.textContent=`${clip.name || 'A clip'} has a newer take · review it and tick again`;
          }
          changed=true;
        }
        freshApprovals.delete(clip.id);
        if(typeof saved?.refine_pending==='boolean' && clip.id!==generatingClipId && saved.refine_pending!==!!clip.refine_pending){clip.refine_pending=saved.refine_pending;clip.refine_approved=false;changed=true;}
        if(clip.refine_approved && clip.refine_approved_generation && clip.refine_approved_generation!==saved?.first_pass_generation){clip.refine_approved=false;changed=true;}
      }
      if(changed)syncState(true);
      renderTimeline();
    } catch(error) {
      if(request===cacheStatusRequest)progressLabel.title=`Cannot confirm saved results: ${error.message}`;
    }
  };
  const renderTimeline = () => {
    if(cacheStatusProject!==timelineState.project_id){cachedClipResults={};void refreshClipResults();}
    cancelTimelineDrag?.();
    refreshFileRefs();
    shotsLane.innerHTML = "";
    imagesLane.innerHTML = "";
    videosLane.innerHTML = "";
    audiosLane.innerHTML = "";

    if(generationWidget) generationWidget.value=generationDisplay(timelineState.generation_mode);
    for (const clip of timelineState.clips) {
      clip.continuity_mode ||= "Independent (No Continuity)";
      clip.context_length ??= 22; clip.audio_context_length ??= clip.context_length;
    }
    // 1. Calculate Total Duration & Frames (at 24fps)
    const totalDuration = timelineState.clips.reduce((acc, c) => acc + (parseFloat(c.duration) || 5.0), 0);
    const totalFrames = Math.round(totalDuration * 24);
    durationTotal.textContent = `Total: ${totalDuration.toFixed(1)}s / ${totalFrames}f (${timelineState.clips.length} Clip${timelineState.clips.length === 1 ? "" : "s"})`;

    const clipTrackElements = [];

    const selectClip = (cid) => {
      activeClipId = cid;
      clipTrackElements.forEach(({ clip: c, shotBlock, imgBlock, vidBlock, audBlock }) => {
        const isActive = c.id === cid;
        shotBlock.classList.toggle("active", isActive);shotBlock.setAttribute("aria-current",String(isActive));
        imgBlock.classList.toggle("active", isActive);
        vidBlock.classList.toggle("active", isActive);
        audBlock.classList.toggle("active", isActive);
      });
      renderInspector();
    };

    // Context is borrowed from the preceding clip, not added to visible duration.
    let elapsed=0;
    timelineState.clips.forEach((clip,index)=>{
      const method=effectiveContinuity(clip);
      if (index>0 && method!==CONTINUITY_MODES.independent && !String(clip.type).includes("Inpaint")) {
        const external=false;
        const priorDuration=external?Number(clip.continuation_source.end || 0):Number(timelineState.clips[index-1].duration || 5);
        const rawFrames=Math.floor(priorDuration*24);
        const priorFrames=external || timelineState.clips[index-1]?.source?rawFrames:Math.max(5,5+Math.ceil((rawFrames-5)/17)*17);
        const grid=[56,39,22,5].find(count=>count<=priorFrames && count<=Number(clip.context_length || 22)) || 0;
        const video=method===CONTINUITY_MODES.frame?1:grid;
        const audio=method===CONTINUITY_MODES.frame?0:Number(clip.audio_context_length ?? video);
        if(video>0 || audio>0) {
          const link=document.createElement('span');link.className='mmx-continuity-link';link.dataset.start=elapsed;link.dataset.clipId=clip.id;
          link.dataset.videoFrames=video;link.dataset.audioFrames=audio;link.setAttribute('role','img');
          link.title=`${clip.name || 'Clip '+(index+1)} continues from the previous clip · ${method.split(' (')[0]} · Video ${(video/24).toFixed(2)}s · Audio ${(audio/24).toFixed(2)}s`;
          link.setAttribute('aria-label',link.title);
          link.innerHTML='<svg width="20" height="16" viewBox="0 0 24 18" fill="none" aria-hidden="true"><rect x="1" y="5" width="13" height="8" rx="4" stroke="currentColor" stroke-width="2"/><rect x="10" y="5" width="13" height="8" rx="4" stroke="currentColor" stroke-width="2"/></svg>';
          shotsLane.append(link);
        }
      }
      elapsed+=Number(clip.duration)||5;
    });
    // 2. Render Clips across all 4 Sub-Tracks
    timelineState.clips.forEach((clip, idx) => {
      const dur = parseFloat(clip.duration) || 5.0;
      const baseWidth = dur * timelineGeometry().pxPerSec - 4;
      const isActive = clip.id === activeClipId;
      const isValidated = !!clip.validated;

      // Filter assigned refs by type for this clip
      const assignedRefs = clip.ref_ids || [];
      const assignedObjs = activeReferences(clip);
      const imgRefs = assignedObjs.filter((r) => r.type === "image" || r.type === "refmod");
      const vidRefs = assignedObjs.filter((r) => r.type === "video");
      const audRefs = assignedObjs.filter((r) => r.type === "audio");

      // ============================================
      // Track 1: Clip Block (Header info + Prompt preview)
      // ============================================
      const shotBlock = document.createElement("div");
      shotBlock.className = `mmx-subtrack-block mmx-shot-block${isActive ? " active" : ""}${isValidated ? " validated" : ""}${clip.id===generatingClipId ? " generating" : ""}`;
      shotBlock.dataset.clipId=clip.id;shotBlock.setAttribute("aria-current",isActive ? "true" : "false");
      shotBlock.style.width = `${baseWidth}px`;
      shotBlock.title = `Clip ${idx + 1}: ${clip.name || "Untitled"} (${dur.toFixed(1)}s) - Click to inspect`;

      // Top Bar: Mode, Name, Duration, Auto-Tail, Validated, Delete
      const shotTopBar = document.createElement("div");
      shotTopBar.className = "mmx-shot-top-bar";

      const modeBadge = document.createElement("span");
      const typeLower = clipCode(clip).toLowerCase();
      modeBadge.className = `mmx-clip-mode-badge mmx-badge-${typeLower}`;
      modeBadge.textContent = clipCode(clip);

      const title = document.createElement("span");
      title.className = "mmx-clip-title";
      title.textContent = clip.name || `Clip ${idx + 1}`;

      const durTag = document.createElement("span");
      durTag.className = "mmx-clip-duration";
      durTag.textContent = `${dur.toFixed(1)}s`;

      shotTopBar.appendChild(modeBadge);
      shotTopBar.appendChild(title);
      shotTopBar.appendChild(durTag);
      const remembered = memorySupported(clip) ? memoryRows(clip) : [];
      if (remembered.length) {
        const mem = document.createElement("span"); mem.className = "mmx-memory-badge";
        mem.textContent = `◷ ${remembered.length}`;
        mem.title = "Remembers: " + remembered.map(r => clipById(r.clip_id)?.name || r.clip_id).join(", ");
        shotTopBar.appendChild(mem);
      }
      const savedResult=cachedClipResults[clip.id];
      if(savedResult?.has_latent){
        const saved=document.createElement('span');saved.className='mmx-saved-badge';
        saved.textContent='◆ Saved';
        saved.title='Generated latent saved on the server. Approval controls whether it is reused; Cache shows reuse details from the latest run.';
        saved.setAttribute('aria-label','Saved generated latent available');
        shotTopBar.append(saved);
      }
      // A continued clip whose saved take came from a different model than the
      // clip it continues: the look jumps at that seam (e.g. Fast H3 after Lightning).
      const continued=idx>0 && !clip.locked && !clip.source && clip.continuity!==false && (clip.continuity_mode || 'Independent (No Continuity)')!=='Independent (No Continuity)';
      const before=continued ? cachedClipResults[timelineState.clips[idx-1]?.id] : null;
      if(continued && savedResult?.model_id && before?.model_id && savedResult.model_id!==before.model_id){
        const warn=document.createElement('span');warn.className='mmx-model-mismatch-badge';
        warn.textContent='⚠ Model changed';
        warn.title=`This clip's saved take was made with ${savedResult.model_label || 'a different model'}, but it continues a clip made with ${before.model_label || 'another model'}. Mixing models in one chain changes the look at this seam. Regenerate the chain with one model.`;
        warn.setAttribute('aria-label',`${clip.name || 'Clip'}: continues a clip made with a different model`);
        warn.style.cssText='padding:1px 6px;border:1px solid #b9893a;border-radius:4px;background:#3a2d16;color:#f0c674;font-size:11px;white-space:nowrap';
        shotTopBar.append(warn);
      }
      if(clip.refine_pending) {const review=document.createElement('span');review.textContent=clip.refine_approved?'Ready To Refine':'Review First Pass';review.className='mmx-generating-badge';shotTopBar.append(review);}
      if(clip.cache_report && (Object.keys(clip.cache_report.stats || {}).length || Object.keys(clip.cache_report.run_preparation || {}).length)){
        const cache=document.createElement('button');cache.className='mmx-cache-button';cache.textContent='Cache';
        cache.title='Show caches reused, rebuilt or bypassed for this clip';
        cache.setAttribute('aria-label',`Cache report for ${clip.name || 'clip'}`);
        cache.onpointerdown=e=>e.stopPropagation();
        cache.onclick=e=>{
          e.stopPropagation();node.__mmxCacheDialog?.remove();
          const dialog=document.createElement('dialog');dialog.className='mmx-cache-dialog';node.__mmxCacheDialog=dialog;
          const el=(tag,cls,text)=>{const x=document.createElement(tag);if(cls)x.className=cls;if(text!=null)x.textContent=text;return x;};
          const explanations={
            'Saved clip':['Generated clip','The saved generation for this clip. Approval controls whether it is reused.'],
            'Text conditioning':['Prompt understanding','The text encoder’s reading of your prompt and visual references.'],
            'Reference preparation':['Reference preparation','The same references and encoding settings prepared before.'],
            'Reference latents':['Encoded references','Images, video and audio converted into model inputs (skips the VAE).'],
            'Model setup':['Model configuration','LoRA and sampling configuration. Not another copy of the model.'],
            'LoRA weights':['LoRA files','Recently used adapter weights kept in a small CPU cache.']
          };
          const report=clip.cache_report;
          const state=count=>count.hit && !count.miss && !count.bypass?'reused':count.hit?'partial':count.miss?'fresh':count.bypass?'bypass':'reused';
          const label={reused:'Reused',partial:'Partly reused',fresh:'Fresh',bypass:'Not reusable'};
          const head=el('div','mmx-cache-head');
          const titles=el('div','mmx-cache-titles');titles.append(el('strong',null,'Cache report'),el('span',null,clip.name || 'Clip'));
          const close=el('button','mmx-cache-close','×');close.type='button';close.title='Close';close.setAttribute('aria-label','Close cache report');close.onclick=()=>dialog.remove();
          head.append(titles,close);dialog.append(head);
          const rowsOf=rows=>Object.entries(rows || {}).filter(([name])=>explanations[name]);
          const all=[...rowsOf(report.stats),...rowsOf(report.run_preparation)];
          const reused=all.filter(([,c])=>state(c)==='reused').length;
          const savedRow=(report.stats || {})['Saved clip'];
          const verdict=el('div','mmx-cache-verdict '+(savedRow && state(savedRow)==='reused'?'reused':'fresh'));
          verdict.append(el('strong',null,savedRow && state(savedRow)==='reused'?'Saved result reused':'Generated this run'),
            el('span',null,`${reused} of ${all.length} caches reused`));
          dialog.append(verdict);
          const group=(rows,title)=>{
            const visible=rowsOf(rows);if(!visible.length)return;
            dialog.append(el('div','mmx-cache-group',title));
            const list=el('div','mmx-cache-list');
            for(const [name,count] of visible){
              const row=el('div','mmx-cache-row'),kind=state(count);
              const text=el('div','mmx-cache-text');text.append(el('strong',null,explanations[name][0]),el('small',null,explanations[name][1]));
              const pill=el('span','mmx-cache-pill '+kind,label[kind]);
              row.append(text,pill);list.append(row);
            }
            dialog.append(list);
          };
          group(report.stats,'This clip');group(report.run_preparation,'Shared run preparation');
          const technical=document.createElement('details');technical.className='mmx-cache-technical';
          const summary=document.createElement('summary');summary.textContent='Technical details';technical.append(summary);
          for(const [scope,rows] of [['This clip',report.stats],['Shared run preparation',report.run_preparation]]){
            if(!Object.keys(rows || {}).length)continue;
            technical.append(el('div','mmx-cache-group',scope));
            const table=document.createElement('table'),hr=document.createElement('tr');
            for(const text of ['Check','Reused','Fresh','Not reusable']){hr.append(el('th',null,text));}table.append(hr);
            for(const [name,count] of Object.entries(rows)){const tr=document.createElement('tr');
              tr.append(el('td',null,name));for(const [k,v] of [['hit',count.hit],['miss',count.miss],['bypass',count.bypass]])tr.append(el('td',v?'n '+k:'n zero',String(v || 0)));table.append(tr);}
            technical.append(table);
          }
          for(const [name,reason] of Object.entries(report.reasons || {}))technical.append(el('p',null,`${name}: ${reason}`));
          technical.append(el('p',null,'File fingerprints are small saved identity hashes. Tensor fingerprints check in-memory data; without a reliable change counter it must be read again. These checks store no extra copies of your media.'));
          dialog.append(technical);
          dialog.append(el('p','mmx-cache-foot','Counts are lookups, not numbers of assets, and reuse can come from earlier runs. Model configuration reuse does not guarantee the weights stayed in VRAM.'));
          dialog.onclick=event=>{if(event.target===dialog)dialog.remove();};
          dialog.onclose=()=>dialog.remove();document.body.append(dialog);if(dialog.showModal)dialog.showModal();else dialog.setAttribute('open','');
        };shotTopBar.append(cache);
      }
      if(clip.id===generatingClipId) {const running=document.createElement('span');running.className='mmx-generating-badge';running.textContent=({preparing:'Preparing',sampling:'Generating',refining:'Refining',decoding:'Decoding',face_refining:'Refining Faces'})[generatingPhase] || 'Generating';running.setAttribute('role','status');running.setAttribute('aria-label',`${clip.name || 'Clip '+(idx+1)}: ${running.textContent}`);shotBlock.append(running);}




      const delBtn = document.createElement("button");
      delBtn.className = "mmx-clip-del-btn";
      delBtn.innerHTML = '<svg viewBox="0 0 12 12" aria-hidden="true" focusable="false"><path d="M3 3l6 6M9 3l-6 6" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>';
      delBtn.title = `Delete ${clip.name || 'Clip '+(idx+1)}`;
      delBtn.setAttribute("aria-label", delBtn.title);
      delBtn.onclick = e => { e.stopPropagation(); deleteClip(clip); };
      shotBlock.appendChild(delBtn);

      shotBlock.appendChild(shotTopBar);

      // Bottom Bar: Prompt Preview Snippet
      const promptSnippet = document.createElement("div");
      promptSnippet.className = "mmx-shot-prompt-preview";
      const hasPrompt = !!(clip.prompt && clip.prompt.trim());
      promptSnippet.textContent = hasPrompt ? clip.prompt.trim() : "(No prompt set)";
      promptSnippet.style.color = hasPrompt ? "#94a3b8" : "#475569";
      promptSnippet.style.fontStyle = hasPrompt ? "normal" : "italic";
      shotBlock.appendChild(promptSnippet);
      const selectLabel=document.createElement('label');selectLabel.className='mmx-clip-selection';
      selectLabel.title='Approve Clip: reuse its saved result and skip generation. Uncheck to generate a new take.';
      const reviewPending=!!clip.refine_pending && !clip.validated;
      const selectInput=document.createElement('input');selectInput.type='checkbox';selectInput.checked=reviewPending ? !!clip.refine_approved : clip.validated===true;
      selectInput.disabled=reviewPending ? !cachedClipResults[clip.id]?.has_first_pass : !clip.validated && !cachedClipResults[clip.id]?.can_approve;
      if(selectInput.disabled)selectLabel.title='Generate this clip first. Approval requires a saved result or latent on the server.';
      // Its saved take is about to be replaced; approve after it finishes (or cancel the run).
      if(clip.id===generatingClipId && !clip.validated && !reviewPending){selectInput.disabled=true;selectLabel.title='This clip is generating. Its new take replaces the saved one when it finishes; cancel the run to keep and approve the current take.';}
      if(reviewPending)selectLabel.title='Review First Pass in Smart Preview, approve here, then Run to refine its saved latent. This does not approve a final take.';
      const upstream=!reviewPending && clip.validated && clip.pending_upstream ? timelineState.clips.find(c=>c.id===clip.pending_upstream) : null;
      if(upstream){
        const upstreamName=upstream.name || `Clip ${timelineState.clips.indexOf(upstream)+1}`;
        selectLabel.classList.add('mmx-pending-upstream');selectLabel.style.outline='1px dashed #f59e0b';selectLabel.style.outlineOffset='1px';
        selectLabel.title=`Kept until ${upstreamName}'s new take is saved, then regenerated because it continues from it. Cancelling the run keeps this take. To keep it even after ${upstreamName} changes, untick and tick it again.`;
      }
      selectInput.setAttribute('aria-label',`Approve ${reviewPending ? 'First Pass Of ' : ''}${clip.name || `Clip ${idx+1}`}`);
      selectInput.onchange=()=>{if(reviewPending){clip.refine_approved=selectInput.checked;clip.refine_approved_generation=cachedClipResults[clip.id]?.first_pass_generation;}else if(selectInput.checked){clip.validated=true;clip.validated_generation=cachedClipResults[clip.id]?.generation;delete clip.invalidated_generation;delete clip.pending_upstream;for(const other of timelineState.clips)if(other.pending_upstream===clip.id)delete other.pending_upstream;freshApprovals.add(clip.id);}else unapproveChain(clip);syncState();renderTimeline();if(selectInput.checked && !reviewPending)void refreshClipResults();};
      for(const event of ['pointerdown','mousedown','click'])selectLabel.addEventListener(event,e=>e.stopPropagation());
      selectLabel.append(selectInput);shotBlock.append(selectLabel);


      // Right resize handle (synchronously resizes all 4 track blocks)
      const rightHandle = document.createElement("div");
      rightHandle.className = "mmx-clip-handle mmx-clip-handle-right";

      let startX = 0;
      let startDuration = dur;

      rightHandle.title = "Drag to change duration";
      rightHandle.onmousedown = (e) => {
        e.stopPropagation();
        e.preventDefault();
        if (clip.locked || node.inputs?.some(input=>input.name==='timeline' && input.link!=null)) return;
        startX = e.clientX;
        startDuration = parseFloat(clip.duration) || 5.0;
        const scale = shotBlock.getBoundingClientRect().width / (shotBlock.offsetWidth || baseWidth) || 1;
        const resizeScale = timelineGeometry().pxPerSec;

        const onMouseMove = (moveEvt) => {
          const deltaX = moveEvt.clientX - startX;
          const newDur = Math.max(0.5, Math.min(60.0, Math.round((startDuration + deltaX / (scale * resizeScale)) * 10) / 10));
          clip.duration = newDur;
          durTag.textContent = `${newDur.toFixed(1)}s`;
          const newWidth = newDur * resizeScale - 4;

          // Synchronously resize all 4 track blocks in real time!
          shotBlock.style.width = `${newWidth}px`;
          imgBlock.style.width = `${newWidth}px`;
          vidBlock.style.width = `${newWidth}px`;
          audBlock.style.width = `${newWidth}px`;

          const tot = timelineState.clips.reduce((acc, c) => acc + (parseFloat(c.duration) || 5.0), 0);
          durationTotal.textContent = `Total: ${tot.toFixed(1)}s / ${Math.round(tot * 24)}f (${timelineState.clips.length} Clips)`;
          drawRuler();
        };

        const onMouseUp = () => {
          window.removeEventListener("mousemove", onMouseMove);
          window.removeEventListener("mouseup", onMouseUp);
          syncState();
          renderInspector();
          drawRuler();
        };

        window.addEventListener("mousemove", onMouseMove);
        window.addEventListener("mouseup", onMouseUp);
      };

      shotBlock.appendChild(rightHandle);
      shotBlock.onclick = () => selectClip(clip.id);

      // ============================================
      // Track 2: Ref Images Block
      // ============================================
      const imgBlock = document.createElement("div");
      imgBlock.className = `mmx-subtrack-block mmx-img-block${isActive ? " active" : ""}${isValidated ? " validated" : ""}`;
      imgBlock.style.width = `${baseWidth}px`;
      imgBlock.title = `Clip ${idx + 1} Ref Images (${imgRefs.length}) - Click to inspect`;
      imgBlock.onclick = () => selectClip(clip.id);

      if (imgRefs.length > 0) {
        imgRefs.forEach((r) => {
          const cell = document.createElement("div");
          cell.className = "mmx-clip-img-cell";
          cell.title = `${r.type === "refmod" ? "[RefMod]" : "[Image]"} ${r.name}`;

          if (r.url) {
            const imgEl = document.createElement("img");
            imgEl.src = r.url;
            imgEl.alt = r.name;
            cell.appendChild(imgEl);
          } else if (r.type === "refmod") {
            cell.innerHTML = `
              <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%; background: linear-gradient(135deg, #1e1b4b, #312e81); padding: 2px; text-align: center;">
                <span style="font-size: 10px;">💎</span>
                <span style="font-size: 8px; font-weight: 700; color: #fde68a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 90%;">${escapeHtml(r.name)}</span>
              </div>
            `;
          } else {
            cell.innerHTML = `
              <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%; background: var(--comfy-input-bg, #333333); padding: 2px; text-align: center;">
                <span style="font-size: 10px;">🖼️</span>
                <span style="font-size: 8px; font-weight: 600; color: #cbd5e1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 90%;">${escapeHtml(r.name)}</span>
              </div>
            `;
          }

          if (r.url) cell.onclick = event => {
            event.stopPropagation();
            const dialog = document.createElement("dialog"); dialog.className = "mmx-reference-dialog";
            const heading = document.createElement("p"); heading.textContent = r.name;
            const image = document.createElement("img"); image.src = r.url; image.alt = r.name;
            const close = document.createElement("button"); close.textContent = "Close"; close.onclick = () => dialog.close();
            dialog.append(heading,image,close); document.body.append(dialog);
            dialog.addEventListener("close",()=>dialog.remove(),{once:true}); dialog.showModal();
          };
          imgBlock.appendChild(cell);
        });
      } else {
        const empty = document.createElement("div");
        empty.className = "mmx-subtrack-empty";
        empty.textContent = "— No Image Refs —";
        imgBlock.appendChild(empty);
      }

      // ============================================
      // Track 3: Ref Videos Block
      // ============================================
      const vidBlock = document.createElement("div");
      vidBlock.className = `mmx-subtrack-block mmx-vid-block${isActive ? " active" : ""}${isValidated ? " validated" : ""}`;
      vidBlock.style.width = `${baseWidth}px`;
      vidBlock.title = `Clip ${idx + 1} Ref Videos (${vidRefs.length}) - Click to inspect`;
      vidBlock.onclick = () => selectClip(clip.id);

      if (vidRefs.length > 0) {
        vidRefs.forEach((r) => {
          const cell = document.createElement("div");
          cell.className = "mmx-clip-vid-cell";
          cell.title = `[Video] ${r.name} (Click to preview)`;

          if (r.url) {
            const vidEl = document.createElement("video");
            vidEl.src = r.url;
            vidEl.muted = true;
            vidEl.loop = true;
            cell.appendChild(vidEl);
            const overlay = document.createElement("div");
            overlay.className = "mmx-vid-play-overlay";
            overlay.innerHTML = `<span>▶</span>`;
            cell.appendChild(overlay);
            cell.onmouseenter = () => vidEl.play().catch(() => {});
            cell.onmouseleave = () => { vidEl.pause(); vidEl.currentTime = 0; };
            cell.onclick = (e) => {
              e.stopPropagation();
              openVideoPreviewModal(r.url, r.name);
            };
          } else {
            cell.innerHTML = `
              <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%; background: linear-gradient(135deg, #2e1065, #4c1d95); text-align: center;">
                <span style="font-size: 11px;">🎬</span>
                <span style="font-size: 8px; font-weight: 600; color: #ddd6fe; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 90%;">${escapeHtml(r.name)}</span>
              </div>
            `;
          }

          const badge = document.createElement("span");
          badge.className = "mmx-cell-badge";
          badge.style.color = "#c084fc";
          badge.textContent = "VID";
          cell.appendChild(badge);
          vidBlock.appendChild(cell);
        });
      } else {
        const empty = document.createElement("div");
        empty.className = "mmx-subtrack-empty";
        empty.textContent = "— No Video Refs —";
        vidBlock.appendChild(empty);
      }

      // ============================================
      // Track 4: Ref Audios Block
      // ============================================
      const audBlock = document.createElement("div");
      audBlock.className = `mmx-subtrack-block mmx-aud-block${isActive ? " active" : ""}${isValidated ? " validated" : ""}`;
      audBlock.style.width = `${baseWidth}px`;
      audBlock.title = `Clip ${idx + 1} Ref Audios (${audRefs.length}) - Click to inspect`;
      audBlock.onclick = () => selectClip(clip.id);

      if (audRefs.length > 0) {
        audRefs.forEach((r) => {
          const playBtn = document.createElement("button");
          playBtn.className = "mmx-clip-aud-btn";
          playBtn.innerHTML = "▶";
          playBtn.title = `Play ${r.name}`;

          const waveCanvas = document.createElement("canvas");
          waveCanvas.className = "mmx-clip-waveform-canvas";

          const audLabel = document.createElement("span");
          audLabel.style.fontSize = "8px";
          audLabel.style.fontWeight = "700";
          audLabel.style.color = "#6ee7b7";
          audLabel.style.whiteSpace = "nowrap";
          audLabel.style.maxWidth = "70px";
          audLabel.style.overflow = "hidden";
          audLabel.style.textOverflow = "ellipsis";
          audLabel.textContent = r.name;

          let audioPlayer = null;
          let isPlaying = false;
          let wavePeaks = [];
          if (r.filename) requestJson(`/minimax_director/media/waveform?filename=${encodeURIComponent(r.filename)}`).then(data => { wavePeaks = data.peaks; renderWave(); }).catch(error => { waveCanvas.title = error.message; });

          const renderWave = (progress = 0) => {
            const ctx = waveCanvas.getContext("2d");
            if (!ctx) return;
            const cw = waveCanvas.width = waveCanvas.clientWidth || 80;
            const ch = waveCanvas.height = 22;
            ctx.clearRect(0, 0, cw, ch);
            const bars = Math.max(10, Math.floor(cw / 3));
            for (let b = 0; b < bars; b++) {
              const norm = wavePeaks.length ? wavePeaks[Math.min(wavePeaks.length-1, Math.floor(b/bars*wavePeaks.length))] : 0;
              const bh = Math.max(2, norm * (ch - 4));
              const bx = b * 3;
              const by = (ch - bh) / 2;
              const past = (bx / cw) <= progress;
              ctx.fillStyle = past ? "#10b981" : (isPlaying ? "rgba(16, 185, 129, 0.6)" : "rgba(16, 185, 129, 0.3)");
              ctx.fillRect(bx, by, 2, bh);
            }
          };

          playBtn.onclick = (e) => {
            e.stopPropagation();
            if (isPlaying && audioPlayer) {
              audioPlayer.pause();
              isPlaying = false;
              playBtn.innerHTML = "▶";
              renderWave(0);
            } else {
              if (r.url) {
                if (!audioPlayer) {
                  audioPlayer = new Audio(r.url);
                  audioPlayer.ontimeupdate = () => {
                    const prog = audioPlayer.duration ? audioPlayer.currentTime / audioPlayer.duration : 0;
                    renderWave(prog);
                  };
                  audioPlayer.onended = () => {
                    isPlaying = false;
                    playBtn.innerHTML = "▶";
                    renderWave(0);
                  };
                }
                audioPlayer.play().catch(() => {});
                isPlaying = true;
                playBtn.innerHTML = "⏸";
              } else {
                isPlaying = !isPlaying;
                playBtn.innerHTML = isPlaying ? "⏸" : "▶";
                renderWave(isPlaying ? 0.5 : 0);
              }
            }
          };

          audBlock.appendChild(playBtn);
          audBlock.appendChild(waveCanvas);
          audBlock.appendChild(audLabel);
          setTimeout(() => renderWave(0), 10);
        });
      } else {
        const empty = document.createElement("div");
        empty.className = "mmx-subtrack-empty";
        empty.textContent = "— No Audio Refs —";
        audBlock.appendChild(empty);
      }

      if (!clip.locked) bindShotDrag({block: shotBlock, scrollArea: multitrackPanel,
        getGroups: () => clipTrackElements.map(row => [row.shotBlock, row.imgBlock, row.vidBlock, row.audBlock]),
        select: () => selectClip(clip.id), move: destination => moveClip(clip, destination),
        setCleanup: value => { cancelTimelineDrag = value; }});
      shotBlock.title += clip.locked ? " · Locked source" : " · Drag body to reorder; drag right edge to resize";
      // Record elements for synchronous actions
      clipTrackElements.push({ clip, shotBlock, imgBlock, vidBlock, audBlock });

      // Append blocks to their respective horizontal subtracks
      shotsLane.appendChild(shotBlock);
      imagesLane.appendChild(imgBlock);
      videosLane.appendChild(vidBlock);
      audiosLane.appendChild(audBlock);
    });

    const types = new Set(timelineState.clips.flatMap(clip => activeReferences(clip).map(row=>row.type)));
    imagesRow.hidden = !types.has("image") && !types.has("refmod");
    videosRow.hidden = !types.has("video"); audiosRow.hidden = false;
    // 3. Add Clip Button flush at end of Track 1 (Clips Lane)
    const addCard = document.createElement("div");
    addCard.className = "mmx-add-clip-card";
    addCard.innerHTML = `<span class="mmx-add-clip-icon">+</span><span>Add Clip</span>`;
    addCard.title = "Add a new clip to the timeline";
    addCard.onclick = openTypePickerModal;
    if(node.inputs?.some(input=>input.name==='timeline' && input.link!=null)){addCard.hidden=true;addCard.onclick=null;}
    shotsLane.appendChild(addCard);

    // 4. Render Active Clip Inspector
    renderInspector();

    // 5. Update Time Ruler
    drawRuler();

  };

  // Render Active Clip Inspector (Directly below timeline track!)
  const renderInspector = () => {
    projectName.value=timelineState.project_name || '';updateServerStatus();
    sharedPrompt.value=timelineState.shared_prompt || "";fade.value=timelineState.audio_fade_ms ?? 15;
    gain.checked=timelineState.audio_gain_match ?? true;sharedPolicy.value=timelineState.shared_prompt_policy || "prepend";
    inspector.innerHTML = "";
    const activeClip = timelineState.clips.find((c) => c.id === activeClipId) || timelineState.clips[0];
    if (!activeClip) {
      const empty = document.createElement("p"); empty.className = "mmx-empty-timeline";
      empty.textContent = "No clips. Click + Add Clip in the timeline to begin.";
      inspector.append(empty); return;
    }

    // Header: clip name and immutable task type.
    const header = document.createElement("div");
    header.className = "mmx-inspector-header";

    // Clip name and type chosen when it was created.
    const titleWrap = document.createElement("div");
    titleWrap.className = "mmx-inspector-title";

    const shotLabel = document.createElement("span");
    shotLabel.style.fontSize = "11px";
    shotLabel.style.color = "#94a3b8";
    const clipIdx = timelineState.clips.indexOf(activeClip) + 1;
    shotLabel.textContent = "Clip:";
    const nameRow=document.createElement("div");nameRow.className="mmx-clip-name-row";
    nameRow.appendChild(shotLabel);

    const nameInput = document.createElement("input");
    nameInput.style.background = "var(--comfy-input-bg, #333333)";
    nameInput.style.border = "1px solid var(--border-color, #4a4a4a)";
    nameInput.style.borderRadius = "4px";
    nameInput.style.color = "#f8fafc";
    nameInput.style.fontSize = "11px";
    nameInput.style.fontWeight = "600";
    nameInput.style.padding = "2px 6px";
    nameInput.style.width = "120px";
    nameInput.value = activeClip.name || `Clip ${clipIdx}`;
    const externallyAuthored=node.inputs?.some(input=>input.name==='timeline' && input.link!=null);
    nameInput.disabled=externallyAuthored;
    nameInput.title=externallyAuthored?'Name and authoring fields are owned by Timeline Builder':'Clip name';
    nameInput.oninput = () => {
      activeClip.name = nameInput.value;
      syncState();
      const cardTitle = shotsLane.querySelector(".mmx-subtrack-block.active .mmx-clip-title");
      if (cardTitle) cardTitle.textContent = activeClip.name;
    };
    nameRow.appendChild(nameInput);

    const clipTypeLabel = document.createElement("span");
    const code=clipCode(activeClip);
    clipTypeLabel.className = `mmx-clip-type-label mmx-clip-mode-badge mmx-badge-${code.toLowerCase()}`;
    clipTypeLabel.textContent=code;
    clipTypeLabel.dataset.type=activeClip.type;
    clipTypeLabel.title="Clip type is fixed. Use Add Clip to create a clip with a different type.";
    nameRow.appendChild(clipTypeLabel);titleWrap.appendChild(nameRow);
    titleWrap.style.cssText="display:flex;flex-direction:column;align-items:flex-start;gap:10px;flex:1;min-width:0";
    header.appendChild(titleWrap);

    // Clip actions; approval is available only on the timeline card.
    const headerActions = document.createElement("div");
    headerActions.className="mmx-clip-header-actions";



    // 2. Duplicate Clip Button in Inspector Header
    const dupShotBtn = document.createElement("button");
    dupShotBtn.className = "mmx-action-btn";
    dupShotBtn.textContent="Duplicate Clip";
    dupShotBtn.disabled=externallyAuthored;
    dupShotBtn.title = `Duplicate "${activeClip.name}" with all its prompt and reference settings`;
    dupShotBtn.onclick = () => duplicateClip(activeClip);
    headerActions.appendChild(dupShotBtn);

    if (!activeClip.locked) for (const [offset, label] of [[-1, "← Move Earlier"], [1, "Move Later →"]]) {
      const button = document.createElement("button"); button.className = "mmx-action-btn";
      button.textContent = label;
      const index = timelineState.clips.indexOf(activeClip), adjacent = timelineState.clips[index + offset];
      button.disabled = externallyAuthored || !adjacent || !!adjacent.locked;
      button.onclick = () => moveClip(activeClip, index + offset);
      headerActions.appendChild(button);
    }

    header.appendChild(headerActions);
    inspector.appendChild(header);

    // Main Inputs Area (Placeholder for fields if needed)
    // ...

    const audioLabel = document.createElement("label");
    audioLabel.textContent = "Clip Audio:";
    audioLabel.className="mmx-audio-control";
    audioLabel.title="Applies only to this clip. Join Fade finishes audio joins across the timeline after generation.";
    const audioMode = document.createElement("select");
    for (const [value, label] of [["generate", "Generate"], ["source", "Keep source audio"], ["mute", "Mute"]]) {
      if (value === "generate" && activeClip.locked) continue;
      if (value === "source" && !["V2V", "RV2V"].includes(String(activeClip.type).toUpperCase())) continue;
      const option = document.createElement("option"); option.value = value; option.textContent = label;
      audioMode.appendChild(option);
    }
    audioMode.value = activeClip.audio_mode || (activeClip.locked ? "source" : "generate");
    audioMode.onchange = () => { activeClip.audio_mode = audioMode.value; syncState(); };
    audioMode.setAttribute("aria-label","Clip Audio");
    audioLabel.appendChild(audioMode);

    const shotSections = document.createElement("div");
    shotSections.className = "mmx-shot-sections";
    inspector.appendChild(shotSections);
    const shotExtras = document.createElement("details"); const extrasTitle = document.createElement("summary"); extrasTitle.textContent = "Clip model and guides";
    shotExtras.appendChild(extrasTitle); shotSections.appendChild(shotExtras);
    const modelOverride = document.createElement("input"); modelOverride.placeholder = "Named model override";
    modelOverride.value = activeClip.model_override || "";
    modelOverride.onchange = () => { activeClip.model_override = modelOverride.value.trim(); syncState(); };
    shotExtras.appendChild(field("Model override name",modelOverride,"Optional key from Model Override Pack. Leave empty to use the connected model."));
    const guideAssets=(timelineState.available_refs || []).filter(row=>["image","video","audio"].includes(row.type));
    const guideRows = document.createElement("div"); shotExtras.appendChild(guideRows);
    const drawGuides = () => {
      guideRows.replaceChildren();
      (activeClip.guides || []).forEach((guide, index) => {
        const line = document.createElement("div");
        const reference = document.createElement("select");
        for (const row of guideAssets) {
          const option = document.createElement("option"); option.value = row.id; option.textContent = row.name || row.id; reference.appendChild(option);
        }
        reference.value = guide.ref_id || "";
        reference.onchange = () => { guide.ref_id = reference.value; syncState(); };
        const time = document.createElement("input"); time.type = "number"; time.min = "0"; time.step = ".041666667"; time.value = guide.time || 0; time.title = "Anchor time in seconds";
        time.onchange = () => { guide.time = Number(time.value); syncState(); };
        const remove = document.createElement("button"); remove.textContent = "Remove anchor";
        remove.onclick = () => { activeClip.guides.splice(index,1); syncState(); drawGuides(); };
        line.className="mmx-form-row"; line.append(field("Pool reference",reference),field("Anchor time (seconds)",time),remove); guideRows.appendChild(line);
      });
    };
    const addGuide = document.createElement("button"); addGuide.textContent = "Add interior anchor";
    addGuide.disabled=guideAssets.length===0;
    addGuide.title=guideAssets.length?"Place a connected reference at a time within this clip":"Connect image, video or audio assets through Reference Pack first";
    addGuide.onclick = () => { if(!guideAssets.length)return;(activeClip.guides ||= []).push({ ref_id: guideAssets[0].id, time: 0 }); syncState(); drawGuides(); };
    shotExtras.appendChild(addGuide); drawGuides();
    if (activeClip.color) {
      const legacy=document.createElement("div");legacy.className="mmx-legacy-note";
      legacy.textContent="This clip still has an older after-decode grade. Look adjustments now live in the Continuity tab.";
      const clear=document.createElement("button");clear.type="button";clear.textContent="Remove old grade";
      clear.onclick=()=>{delete activeClip.color;syncState();renderInspector();};legacy.append(clear);shotExtras.appendChild(legacy);
    }

    finishSection(shotExtras,"Optional changes for this clip: a model override and interior reference anchors.");

    if (["V2V", "RV2V"].includes(activeClip.type)) {
      const sourcePanel = document.createElement("fieldset");
      const legend = document.createElement("legend"); legend.textContent = "Source video range";
      sourcePanel.appendChild(legend); inspector.appendChild(sourcePanel);
      const sourceEntry=(timelineState.available_refs || []).find(row=>row.id===activeClip.source?.ref_id);
      const filename={value:sourceEntry?.filename || (typeof activeClip.source==='string' ? activeClip.source : activeClip.source?.filename) || ''};
      const sourceLabel=document.createElement('p');sourceLabel.textContent=sourceEntry ? `Source: ${sourceEntry.name}` : 'Choose the source video in Reference Pack Assets below.';sourcePanel.append(sourceLabel);
      let sourcePlayer = null;
      if (filename.value) {
        const video = document.createElement("video"); video.controls = true; video.preload = "metadata";
        sourcePlayer = video;
        video.style.cssText = "display:block;max-width:100%;max-height:200px;margin:8px 0";
        const parts = filename.value.replaceAll("\\", "/").split("/");
        video.src = api.apiURL(`/view?${new URLSearchParams({ filename: parts.pop(), subfolder: parts.join("/"), type: "input" })}`);
        video.onloadedmetadata = () => { video.currentTime = activeClip.source_start || 0; };
        sourcePanel.appendChild(video);
      }
      for (const [key, label, fallback] of [["source_start", "Start (s)", 0], ["source_end", "End (s)", (activeClip.source_start || 0) + (activeClip.duration || 5)]]) {
        const wrap = document.createElement("label"); wrap.textContent = `${label}: `;
        const input = document.createElement("input"); input.type = "number"; input.min = "0"; input.step = "0.041666667";
        input.value = activeClip[key] ?? fallback; input.style.width = "90px";
        if(key==='source_end' && activeClip.source?.ref_id && activeClip.source_end==null) {input.value='';input.placeholder='Whole Video';}
        input.onchange = () => {
          if(activeClip.source?.ref_id && ((key==='source_end' && input.value==='') || (key==='source_start' && activeClip.source_end==null))) {
            if(key==='source_end')delete activeClip.source_end;
            else {
              if(!Number.isFinite(Number(input.value)) || Number(input.value)<0) {input.setCustomValidity('Start must be non-negative seconds.');input.reportValidity();return;}
              activeClip.source_start=Number(input.value);
            }
            syncState();renderTimeline();return;
          }
          const start = key === "source_start" ? Number(input.value) : Number(activeClip.source_start || 0);
          const end = key === "source_end" ? Number(input.value) : Number(activeClip.source_end ?? (Number(activeClip.source_start || 0) + Number(activeClip.duration || 5)));
          if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start) {
            input.setCustomValidity("End must exceed start, and both must be finite non-negative seconds."); input.reportValidity(); return;
          }
          input.setCustomValidity(""); activeClip.source_start = start; activeClip.source_end = end;
          activeClip.duration = end - start; syncState(); renderTimeline();
        };
        wrap.appendChild(input); sourcePanel.appendChild(wrap);
      }
      const split = document.createElement("button"); split.textContent = "Split into equal ranges";
      split.onclick = () => {
        const count = Number(prompt("Number of equal source ranges", "2"));
        if (!Number.isInteger(count) || count < 2 || count > 100) return;
        const start = Number(activeClip.source_start || 0);
        const end = Number(activeClip.source_end ?? start + (activeClip.duration || 5));
        if (!Number.isFinite(end) || end <= start) return;
        const stamp = Date.now();
        const clips = Array.from({ length: count }, (_, index) => ({
          ...JSON.parse(JSON.stringify(activeClip)), id: `source_${stamp}_${index}`,
          name: `${activeClip.name || "Source"} ${index + 1}`,
          source_start: start + (end - start) * index / count,
          source_end: start + (end - start) * (index + 1) / count,
          duration: (end - start) / count, validated: false, selected: false,
        }));
        timelineState.clips.splice(timelineState.clips.indexOf(activeClip), 1, ...clips);
        activeClipId = clips[0].id; syncState(); renderTimeline();
      };
      sourcePanel.appendChild(split);
      const replaceSourceRanges = (cuts) => {
        const start = Number(activeClip.source_start || 0);
        const end = Number(activeClip.source_end ?? start+(activeClip.duration || 5));
        cuts = [...new Set(cuts)].filter(value => Number.isFinite(value) && value > start && value < end).sort((a,b) => a-b);
        if (!cuts.length) throw new Error("No split boundaries lie inside this source range.");
        const bounds = [start, ...cuts, end];
        const clips = bounds.slice(0,-1).map((value,index) => ({ ...JSON.parse(JSON.stringify(activeClip)),
          id: `source_${crypto.randomUUID()}`, name: `${activeClip.name || "Source"} ${index+1}`, source_start: value,
          source_end: bounds[index+1], duration: bounds[index+1]-value, validated: false, selected: false, locked: !!activeClip.locked }));
        timelineState.clips.splice(timelineState.clips.indexOf(activeClip), 1, ...clips);
        activeClipId = clips[0].id; syncState(); renderTimeline();
      };
      const splitAtCursor = document.createElement("button"); splitAtCursor.textContent = "Split at playhead";
      splitAtCursor.onclick = () => { try { replaceSourceRanges([sourcePlayer?.currentTime || 0]); } catch (error) { alert(error.message); } }; sourcePanel.appendChild(splitAtCursor);
      const smart = document.createElement("button"); smart.textContent = "Detect scene boundaries";
      smart.onclick = async () => {
        smart.disabled = true;
        try {
          const result = await requestJson("/minimax_director/smart_split", { filename: filename.value, threshold: 27 });
          if (!result.ok) throw new Error(result.error || "Scene detection failed");
          replaceSourceRanges(result.scenes.map(scene => scene.start));
        } catch (error) { alert(error.message); } finally { smart.disabled = false; }
      }; sourcePanel.appendChild(smart);
      const merge = document.createElement("button"); merge.textContent = "Remove next boundary / merge";
      merge.onclick = () => {
        const index = timelineState.clips.indexOf(activeClip); const next = timelineState.clips[index+1];
        const nextFile = next?.source?.ref_id || (typeof next?.source === "string" ? next.source : next?.source?.filename);
        if (!next || nextFile !== (activeClip.source?.ref_id || filename.value) || Math.abs(Number(activeClip.source_end)-Number(next.source_start)) > 1/24) { alert("The next clip must use the same source and a contiguous range."); return; }
        activeClip.source_end = next.source_end; activeClip.duration = activeClip.source_end-(activeClip.source_start || 0);
        activeClip.prompt = [activeClip.prompt, next.prompt].filter(Boolean).join("\n");
        activeClip.ref_ids = [...new Set([...(activeClip.ref_ids || []), ...(next.ref_ids || [])])];
        timelineState.clips.splice(index+1,1); syncState(); renderTimeline();
      }; sourcePanel.appendChild(merge);

      smart.disabled=!filename.value;
      smart.title=filename.value ? 'Detect cuts in the original video file.' : 'Scene detection needs a file-backed video.';
    }

    const loraPanel = document.createElement("details");
    const loraHeading = document.createElement("summary");
    loraHeading.textContent = "Clip LoRAs";
    loraPanel.appendChild(loraHeading);
    shotSections.appendChild(loraPanel);
    if (!Array.isArray(activeClip.loras)) activeClip.loras = [];
    const MAX_CLIP_LORAS = 8;
    const loraRows = document.createElement("div");
    loraRows.className = "mmx-lora-list";
    loraPanel.appendChild(loraRows);
    const commitLoRAEdit=()=>{
      syncState();renderTimeline();
    };
    const loraLabel = value => String(value || "").split(/[\\/]/).pop().replace(/\.safetensors$/i, "");
    let loraNamesPromise = null;
    const loraNamesReady = () => loraNamesPromise ||= api.fetchApi("/minimax_director/loras").then(async response => {
      const names = await response.json();
      if (!response.ok || !Array.isArray(names)) throw new Error(names.error || "Cannot list LoRAs");
      return names;
    });
    const addLora = document.createElement("button");
    addLora.type = "button"; addLora.className = "mmx-lora-add";
    const carriesPrevious = timelineState.clips.indexOf(activeClip)>0 && [CONTINUITY_MODES.motion,CONTINUITY_MODES.carry].includes(effectiveContinuity(activeClip));
    const drawAntiburn = () => {
      if (!carriesPrevious) return;
      const burn = activeClip.antiburn || {};
      const card = document.createElement("div"); card.className = "mmx-lora-card mmx-lora-auto";
      card.dataset.enabled = String(burn.enabled !== false);
      const head = document.createElement("div"); head.className = "mmx-lora-card-head";
      const toggle = document.createElement("label"); toggle.className = "mmx-lora-switch"; toggle.title = "Use the anti-burn LoRA on this clip";
      const enabled = document.createElement("input"); enabled.type = "checkbox"; enabled.checked = burn.enabled !== false; enabled.setAttribute("aria-label", "Anti-burn enabled");
      const knob = document.createElement("span"); knob.className = "mmx-lora-switch-track"; toggle.append(enabled, knob);
      const name = document.createElement("div"); name.className = "mmx-lora-auto-name";
      name.innerHTML = '<strong>Anti-burn</strong> <span class="mmx-auto-badge">Auto</span><small>Checking LoRA folder…</small>';
      loraNamesReady().then(names => {
        const file = names.map(n=>String(n).replaceAll("\\","/")).filter(n=>n.toLowerCase().replace(/[-_]/g,"").includes("antiburn")).sort((a,b)=>(!a.toLowerCase().includes("universal"))-(!b.toLowerCase().includes("universal")) || a.localeCompare(b))[0];
        const small = name.querySelector("small");
        small.textContent = file ? loraLabel(file) : "No anti-burn LoRA found in models/loras. This clip will run without it.";
        if (!file) card.classList.add("mmx-lora-missing");
      }).catch(() => {});
      head.append(toggle, name);
      const body = document.createElement("div"); body.className = "mmx-lora-card-body";
      const label = document.createElement("span"); label.className = "mmx-lora-strength-label"; label.textContent = "Strength";
      const slider = document.createElement("input"); slider.type = "range"; slider.min = "0"; slider.max = "1.5"; slider.step = "0.05"; slider.className = "mmx-lora-slider";
      const strength = document.createElement("input"); strength.type = "number"; strength.min = "0"; strength.max = "2"; strength.step = "0.05"; strength.className = "mmx-lora-strength";
      slider.value = strength.value = Number(burn.strength ?? .5).toFixed(2);
      const save = value => { const next = {...(activeClip.antiburn || {})}; Object.assign(next, value);
        if (next.enabled !== false) delete next.enabled; if (Number(next.strength ?? .5) === .5) delete next.strength;
        if (Object.keys(next).length) activeClip.antiburn = next; else delete activeClip.antiburn; syncState();
        const note = inspector.querySelector(".mmx-antiburn-note"); if (note) note.textContent = antiburnText(activeClip.antiburn); };
      enabled.onchange = () => { card.dataset.enabled = String(enabled.checked); save({enabled: enabled.checked}); };
      slider.oninput = () => { strength.value = Number(slider.value).toFixed(2); };
      slider.onchange = () => save({strength: Number(slider.value)});
      strength.onchange = () => { const v = Math.max(0, Math.min(2, Number(strength.value) || 0)); strength.value = v.toFixed(2); slider.value = Math.min(1.5, v); save({strength: v}); };
      body.append(label, slider, strength);
      const note = document.createElement("small"); note.className = "mmx-lora-auto-note";
      note.textContent = "Added automatically because this clip continues the previous one. Speed LoRAs such as Lightning stay in your workflow, outside the Master node.";
      card.append(head, body, note); loraRows.appendChild(card);
    };
    const drawLoras = () => {
      loraRows.replaceChildren();
      drawAntiburn();
      if (!activeClip.loras.length && !carriesPrevious) {
        const empty = document.createElement("div"); empty.className = "mmx-lora-empty";
        empty.textContent = "No LoRAs on this clip. The model runs as loaded in the workflow.";
        loraRows.appendChild(empty);
      }
      activeClip.loras.forEach((row, index) => {
        const card = document.createElement("div");
        card.className = "mmx-lora-card";
        const isOn = () => (row.enabled ?? row.active ?? true) !== false;
        card.dataset.enabled = String(isOn());

        // Header: on/off switch, file picker, info, remove.
        const head = document.createElement("div"); head.className = "mmx-lora-card-head";
        const toggle = document.createElement("label"); toggle.className = "mmx-lora-switch";
        toggle.title = "Use this LoRA on the clip";
        const enabled = document.createElement("input");
        enabled.type = "checkbox";
        enabled.checked = isOn();
        enabled.setAttribute("aria-label", "Enabled");
        enabled.onchange = () => { row.enabled = enabled.checked; delete row.active; card.dataset.enabled = String(enabled.checked); commitLoRAEdit(); };
        const knob = document.createElement("span"); knob.className = "mmx-lora-switch-track";
        toggle.append(enabled, knob);

        const name = document.createElement("select");
        name.className = "mmx-lora-file"; name.setAttribute("aria-label", "LoRA file");
        name.title = row.name || "Choose a LoRA";
        const current = document.createElement("option");
        current.value = row.name || ""; current.textContent = row.name ? loraLabel(row.name) : "Choose a LoRA…";
        name.appendChild(current);
        loraNamesReady().then(names => {
          for (const value of names) if (value !== row.name) {
            const option = document.createElement("option"); option.value = value; option.textContent = value; name.appendChild(option);
          }
        }).catch(error => { name.title = error.message; });
        name.onchange = () => { row.name = name.value; commitLoRAEdit(); drawLoras(); };

        const info = document.createElement("button");
        info.type = "button"; info.className = "mmx-lora-icon"; info.textContent = "i";
        info.title = "Show LoRA metadata"; info.setAttribute("aria-label", "Info"); info.disabled = !row.name;
        const remove = document.createElement("button");
        remove.type = "button"; remove.className = "mmx-lora-icon mmx-lora-remove"; remove.textContent = "×";
        remove.title = "Remove this LoRA"; remove.setAttribute("aria-label", "Remove");
        remove.onclick = () => { activeClip.loras.splice(index, 1); commitLoRAEdit(); drawLoras(); };
        head.append(toggle, name, info, remove);

        // Body: strength slider plus exact number.
        const body = document.createElement("div"); body.className = "mmx-lora-card-body";
        const strengthLabel = document.createElement("span"); strengthLabel.className = "mmx-lora-strength-label"; strengthLabel.textContent = "Strength";
        const slider = document.createElement("input");
        slider.type = "range"; slider.min = "-2"; slider.max = "2"; slider.step = "0.05";
        slider.className = "mmx-lora-slider"; slider.setAttribute("aria-label", "Model strength slider");
        const strength = document.createElement("input");
        strength.type = "number"; strength.min = "-10"; strength.max = "10"; strength.step = "0.05";
        strength.className = "mmx-lora-strength"; strength.setAttribute("aria-label", "Model strength");
        const setShown = amount => { strength.value = amount; slider.value = Math.max(-2, Math.min(2, amount)); };
        setShown(row.strength ?? 1);
        slider.oninput = () => { strength.value = Number(slider.value).toFixed(2); };
        slider.onchange = () => { row.strength = Number(slider.value); strength.setCustomValidity(""); commitLoRAEdit(); };
        strength.onchange = () => { const amount=Number(strength.value);if(!Number.isFinite(amount)||amount < -10 || amount > 10){strength.setCustomValidity("Enter a strength from -10 to 10.");strength.reportValidity();return;}strength.setCustomValidity("");row.strength = amount; slider.value = Math.max(-2, Math.min(2, amount)); commitLoRAEdit(); };
        body.append(strengthLabel, slider, strength);
        card.append(head, body);

        // Metadata drawer, toggled inside the card.
        const details = document.createElement("div"); details.className = "mmx-lora-info"; details.hidden = true;
        info.onclick = async () => {
          if (!details.hidden) { details.hidden = true; info.setAttribute("aria-expanded", "false"); return; }
          try {
            const result = await requestJson(`/minimax_director/loras/info?name=${encodeURIComponent(row.name || "")}`);
            details.replaceChildren();
            if (result.has_preview) { const preview = document.createElement("img"); preview.src = api.apiURL(`/minimax_director/loras/info?preview=1&name=${encodeURIComponent(row.name)}`); details.appendChild(preview); }
            const metadata = document.createElement("pre"); metadata.textContent = JSON.stringify(result.metadata, null, 2); details.appendChild(metadata);
            details.hidden = false; info.setAttribute("aria-expanded", "true");
          } catch (error) { alert(error.message); }
        };
        card.appendChild(details);
        loraRows.appendChild(card);
      });
      const count = activeClip.loras.length;
      addLora.textContent = count >= MAX_CLIP_LORAS ? `LoRA limit reached (${MAX_CLIP_LORAS})` : `+ Add LoRA  ·  ${count}/${MAX_CLIP_LORAS}`;
      addLora.disabled = count >= MAX_CLIP_LORAS;
      addLora.title = carriesPrevious ? `Your own LoRAs on this clip. The automatic anti-burn LoRA is extra and not counted in the ${MAX_CLIP_LORAS}.` : "";
    };
    addLora.onclick = () => {
      if (activeClip.loras.length >= MAX_CLIP_LORAS) return;
      activeClip.loras.push({ name: "", strength: 1, enabled: true }); commitLoRAEdit(); drawLoras();
    };
    loraPanel.appendChild(addLora); drawLoras();
    finishSection(loraPanel,"Optional model adapters applied only to this clip. Choose a compatible H3 LoRA and its strength.");

    // Memory: earlier clips (whole, or a part) shown to H3 as reference videos.
    const memoryPanel = document.createElement("details");
    const memoryHeading = document.createElement("summary"); memoryHeading.textContent = "Clip memory";
    memoryPanel.appendChild(memoryHeading); shotSections.appendChild(memoryPanel);
    if (!Array.isArray(activeClip.memory)) activeClip.memory = [];
    const memoryBody = document.createElement("div"); memoryBody.className = "mmx-memory";
    memoryPanel.appendChild(memoryBody);
    const fmtSec = v => `${(Math.round(Number(v) * 100) / 100).toFixed(2)} s`;
    const commitMemory = (redraw = true) => { syncState(); renderTimeline(); if (redraw) renderInspector(); };
    const drawMemory = () => {
      memoryBody.replaceChildren();
      const index = timelineState.clips.indexOf(activeClip);
      const earlier = timelineState.clips.slice(0, Math.max(0, index)).filter(c => !c.locked || Number(c.duration) > 0);
      if (!memorySupported(activeClip)) {
        const p = document.createElement("p"); p.className = "mmx-memory-empty";
        p.textContent = "Memory works on REF2V and RV2V clips: it passes earlier moments as reference videos or pictures.";
        memoryBody.appendChild(p); return;
      }
      const videoSlots = memorySlots(activeClip, "video"), imageSlots = memorySlots(activeClip, "image");
      const usedOf = kind => activeClip.memory.filter(r => memoryKind(r) === kind).length;
      activeClip.memory.forEach((row, i) => {
        const src = clipById(row.clip_id);
        const srcIndex = timelineState.clips.indexOf(src);
        const problem = !src ? "That clip was deleted." : srcIndex >= index ? "Move this clip after its memory source, or choose an earlier clip." : "";
        const card = document.createElement("div"); card.className = "mmx-memory-card" + (problem ? " mmx-memory-invalid" : "");
        card.dataset.enabled = String(row.enabled !== false);
        const head = document.createElement("div"); head.className = "mmx-memory-head";
        const tag = document.createElement("span"); tag.className = "mmx-memory-tag";
        const pos = memoryRows(activeClip).indexOf(row);
        tag.textContent = pos >= 0 ? memoryTag(activeClip, row) : "off";
        const pick = document.createElement("select"); pick.className = "mmx-memory-source"; pick.setAttribute("aria-label", "Remembered clip");
        if (!src) { const o = document.createElement("option"); o.value = row.clip_id; o.textContent = "Missing clip"; pick.appendChild(o); }
        for (const c of earlier) { const o = document.createElement("option"); o.value = c.id; o.textContent = `${timelineState.clips.indexOf(c) + 1} · ${c.name || c.id} · ${fmtSec(c.duration || 0)}`; pick.appendChild(o); }
        if (src && srcIndex >= index) { const o = document.createElement("option"); o.value = src.id; o.textContent = `${src.name || src.id} (after this clip)`; pick.appendChild(o); }
        pick.value = row.clip_id;
        pick.onchange = () => { row.clip_id = pick.value; row.start = 0; row.end = null; commitMemory(); };
        const toggle = document.createElement("label"); toggle.className = "mmx-lora-switch"; toggle.title = "Use this memory";
        const on = document.createElement("input"); on.type = "checkbox"; on.checked = row.enabled !== false; on.setAttribute("aria-label", "Use this memory");
        on.onchange = () => { row.enabled = on.checked; commitMemory(); };
        const knob = document.createElement("span"); knob.className = "mmx-lora-switch-track"; toggle.append(on, knob);
        const remove = document.createElement("button"); remove.type = "button"; remove.className = "mmx-lora-icon mmx-lora-remove"; remove.textContent = "×"; remove.title = "Forget this moment"; remove.setAttribute("aria-label", "Remove memory");
        remove.onclick = () => { activeClip.memory.splice(i, 1); commitMemory(); };
        head.append(toggle, tag, pick, remove);
        card.appendChild(head);

        // Whole clip, a part of it (reference video) or one frame (reference
        // picture), on a small track of the source clip.
        const total = Math.max(0.2, Number(src?.duration) || 0.2);
        const frameMode = memoryKind(row) === "image";
        const whole = !frameMode && row.end == null && !(Number(row.start) > 0);
        const current = frameMode ? "frame" : whole ? "whole" : "part";
        const modes = document.createElement("div"); modes.className = "mmx-memory-modes"; modes.setAttribute("role", "radiogroup");
        for (const [label, mode] of [["Whole clip", "whole"], ["Part of it", "part"], ["One frame", "frame"]]) {
          const b = document.createElement("button"); b.type = "button"; b.textContent = label; b.setAttribute("role", "radio");
          b.setAttribute("aria-checked", String(current === mode)); b.className = current === mode ? "active" : "";
          const wantKind = mode === "frame" ? "image" : "video";
          if (current !== mode && memoryKind(row) !== wantKind && usedOf(wantKind) >= memorySlots(activeClip, wantKind)) { b.disabled = true; b.title = wantKind === "image" ? "All picture slots are used." : "All video slots are used."; }
          b.onclick = () => {
            if (mode === "frame") { row.kind = "image"; row.start = Math.min(total, Number(row.end ?? total) - (row.end == null ? Math.min(total, 0.5) : 0)); row.start = Math.max(0, Math.round(row.start * 1000) / 1000); row.end = null; }
            else { delete row.kind; if (mode === "whole") { row.start = 0; row.end = null; } else if (current !== "part") { row.start = Math.max(0, total - Math.min(2, total)); row.end = total; } }
            commitMemory();
          };
          modes.appendChild(b);
        }
        card.appendChild(modes);
        const track = document.createElement("div"); track.className = "mmx-memory-track";
        const saved = src ? cachedClipResults[src.id] : null;
        if (saved?.has_frames) {
          const strip = document.createElement("img"); strip.className = "mmx-memory-strip"; strip.alt = ""; strip.draggable = false;
          strip.src = api.apiURL(`/minimax_director/clip/filmstrip?project_id=${encodeURIComponent(timelineState.project_id)}&clip_id=${encodeURIComponent(src.id)}&count=10&height=56&g=${encodeURIComponent(saved.generation ?? "")}`);
          strip.onerror = () => strip.remove();
          track.appendChild(strip);
        } else if (src) {
          const pending = document.createElement("span"); pending.className = "mmx-memory-pending"; pending.textContent = "Not generated yet · generate it before this clip";
          track.appendChild(pending);
        }
        const windowEl = document.createElement("div"); windowEl.className = "mmx-memory-window";
        track.appendChild(windowEl);
        const startIn = document.createElement("input"), endIn = document.createElement("input");
        for (const el of [startIn, endIn]) { el.type = "range"; el.min = "0"; el.max = String(total); el.step = String(1 / 24); el.className = "mmx-memory-thumb"; }
        startIn.setAttribute("aria-label", "Start of remembered part"); endIn.setAttribute("aria-label", "End of remembered part");
        startIn.value = String(Number(row.start) || 0); endIn.value = String(row.end == null ? total : Number(row.end));
        const readout = document.createElement("div"); readout.className = "mmx-memory-readout";
        const paint = () => {
          const s = Number(startIn.value), e = Number(endIn.value);
          if (frameMode) { windowEl.style.left = `calc(${s / total * 100}% - 1px)`; windowEl.style.width = "2px"; readout.textContent = `Frame at ${fmtSec(s)}  ·  passed as a picture`; return; }
          windowEl.style.left = `${(whole ? 0 : s) / total * 100}%`; windowEl.style.width = `${(whole ? total : Math.max(0, e - s)) / total * 100}%`;
          readout.textContent = whole ? `All ${fmtSec(total)}` : `${fmtSec(s)} → ${fmtSec(e)}  ·  ${fmtSec(Math.max(0, e - s))}`;
        };
        const settle = () => { if (frameMode) { row.start = Math.round(Number(startIn.value) * 1000) / 1000; paint(); return; } let s = Number(startIn.value), e = Number(endIn.value); if (e - s < 0.25) { if (document.activeElement === startIn) s = Math.max(0, e - 0.25); else e = Math.min(total, s + 0.25); } startIn.value = String(s); endIn.value = String(e); row.start = Math.round(s * 1000) / 1000; row.end = Math.round(e * 1000) / 1000; paint(); };
        startIn.oninput = endIn.oninput = () => { settle(); };
        startIn.onchange = endIn.onchange = () => { settle(); commitMemory(false); drawMemory(); };
        if (frameMode) { startIn.setAttribute("aria-label", "Remembered frame"); track.classList.add("mmx-memory-track-part"); track.append(startIn); }
        else if (!whole) { track.classList.add("mmx-memory-track-part"); track.append(startIn, endIn); }
        card.append(track, readout);
        paint();

        const note = document.createElement("input"); note.type = "text"; note.className = "mmx-memory-note"; note.maxLength = 200;
        note.placeholder = "What this moment shows, e.g. the living room, wide view (optional)";
        note.value = row.note || ""; note.setAttribute("aria-label", "Memory note");
        note.onchange = () => { row.note = note.value; commitMemory(); };
        card.appendChild(note);
        if (problem) { const warn = document.createElement("p"); warn.className = "mmx-memory-problem"; warn.textContent = problem; card.appendChild(warn); }
        memoryBody.appendChild(card);
      });

      const used = memoryRows(activeClip);
      const seconds = used.reduce((sum, row) => sum + memoryWindowSeconds(row), 0);
      const budget = document.createElement("div"); budget.className = "mmx-memory-budget" + (seconds > MEMORY_MAX_SECONDS ? " over" : "");
      const usedVideos = used.filter(r => memoryKind(r) === "video").length, usedImages = used.length - usedVideos;
      budget.textContent = `${usedVideos} of ${videoSlots} video slots` + (usedImages ? ` · ${usedImages} of ${imageSlots} picture slots` : "") + (usedVideos ? ` · ${fmtSec(seconds)} of ${MEMORY_MAX_SECONDS} s reference video time` : "") + (seconds > MEMORY_MAX_SECONDS ? " — shorten a part" : "");
      if (activeClip.memory.length) memoryBody.appendChild(budget);

      const actions = document.createElement("div"); actions.className = "mmx-memory-actions";
      const videoFull = usedOf("video") >= videoSlots, full = videoFull && usedOf("image") >= imageSlots;
      // New memories are videos while video slots remain, else single frames.
      const newRow = clipId => videoFull ? {clip_id: clipId, kind: "image", start: 0, end: null, note: "", enabled: true} : {clip_id: clipId, start: 0, end: null, note: "", enabled: true};
      const prev = earlier[earlier.length - 1];
      const addPrev = document.createElement("button"); addPrev.type = "button"; addPrev.className = "mmx-lora-add";
      addPrev.textContent = prev ? `+ Remember the previous clip (${prev.name || prev.id})` : "+ Remember the previous clip";
      addPrev.disabled = !prev || full;
      addPrev.onclick = () => { activeClip.memory.push(newRow(prev.id)); commitMemory(); };
      const addAny = document.createElement("button"); addAny.type = "button"; addAny.className = "mmx-lora-add";
      addAny.textContent = "+ Remember another earlier clip"; addAny.disabled = !earlier.length || full;
      addAny.onclick = () => { const pick = earlier.find(c => !activeClip.memory.some(r => r.clip_id === c.id)) || earlier[0]; activeClip.memory.push(newRow(pick.id)); commitMemory(); };
      actions.append(addPrev, addAny);
      if (!earlier.length) { const p = document.createElement("p"); p.className = "mmx-memory-empty"; p.textContent = "This is the first clip; memory needs an earlier clip."; actions.appendChild(p); }
      else if (full) { const p = document.createElement("p"); p.className = "mmx-memory-empty"; p.textContent = "All video and picture slots are used."; actions.appendChild(p); }
      else if (videoFull) { const p = document.createElement("p"); p.className = "mmx-memory-empty"; p.textContent = "Video slots are full; new memories are added as single frames (pictures)."; actions.appendChild(p); }
      memoryBody.appendChild(actions);

      const noteText = memoryNoteFor(activeClip);
      if (noteText) {
        const box = document.createElement("div"); box.className = "mmx-memory-preview";
        const title = document.createElement("div"); title.className = "mmx-memory-preview-title"; title.textContent = "Added to this clip's prompt automatically";
        const pre = document.createElement("pre"); pre.textContent = noteText;
        box.append(title, pre); memoryBody.appendChild(box);
      }
    };
    drawMemory();
    finishSection(memoryPanel, "Show H3 earlier moments of this film so people, places and style carry over: a whole earlier clip or a part of it becomes a reference video, or one frame becomes a reference picture, after this clip's own references. A note saying so is added to the prompt. The earlier clip must be generated first.");

    // Duration controls in the clip header.
    const timingRow = document.createElement("div");
    timingRow.className = "mmx-inspector-card-row";

    // 1. Duration Controls
    const durItem = document.createElement("div");
    durItem.className = "mmx-ctrl-item";
    const durLabel = document.createElement("label");
    durLabel.textContent = "Duration:";
    durItem.appendChild(durLabel);

    const durNum = document.createElement("input");
    durNum.type = "number";
    durNum.min = "0.5";
    durNum.max = "60.0";
    durNum.step = "0.1";
    durNum.value = String(activeClip.duration || 5.0);
    durNum.style.width = "140px";
    durNum.style.background = "var(--comfy-input-bg, #333333)";
    durNum.setAttribute("aria-label","Clip Duration");
    durNum.disabled=externallyAuthored;
    durNum.style.border = "1px solid var(--border-color, #4a4a4a)";
    durNum.style.borderRadius = "4px";
    durNum.style.color = "#f8fafc";
    durNum.style.fontSize = "11px";
    durNum.style.textAlign = "center";

    const durUnit = document.createElement("span");
    durUnit.className = "mmx-ctrl-unit";
    durUnit.textContent = "s";

    ["mousedown", "pointerdown", "touchstart"].forEach(evt => durNum.addEventListener(evt, e => e.stopPropagation()));

    durNum.onchange = () => {
      const v = Math.max(0.5, Math.min(60.0, parseFloat(durNum.value) || 5.0));
      activeClip.duration = v;
      durNum.value = String(v);
      syncState();
      renderTimeline();
      drawRuler();
    };

    durItem.appendChild(durNum);
    durItem.appendChild(durUnit);
    timingRow.appendChild(durItem);
    timingRow.appendChild(audioLabel);

    const continuityPanel=document.createElement("details");continuityPanel.open=true;
    continuityPanel.hidden=!!activeClip.locked || ["V2V","RV2V","IMAGE INPAINT","INPAINT"].includes(String(activeClip.type).toUpperCase());
    const continuityTitle=document.createElement("summary");continuityTitle.textContent="Continuity · context from previous clip";continuityPanel.append(continuityTitle);
    const MODE=CONTINUITY_MODES;
    const clipIndex=timelineState.clips.indexOf(activeClip), previousClip=timelineState.clips[clipIndex-1];
    const startImage=isStartImageClip(activeClip);
    const mode=effectiveContinuity(activeClip);
    const commitContinuity=(value,redraw=true)=>{activeClip.continuity=value!==MODE.independent;activeClip.continuity_mode=value;syncState();renderTimeline();if(redraw)renderInspector();};
    const switchRow=(title,checked,onchange,help,disabled=false)=>{
      const row=document.createElement("label");row.className="mmx-switch-row"+(disabled?" disabled":"");
      const toggle=document.createElement("span");toggle.className="mmx-lora-switch";
      const box=document.createElement("input");box.type="checkbox";box.checked=checked;box.disabled=disabled;box.onchange=()=>onchange(box.checked);
      const track=document.createElement("span");track.className="mmx-lora-switch-track";toggle.append(box,track);
      const text=document.createElement("span");text.className="mmx-switch-text";
      const strong=document.createElement("strong");strong.textContent=title;text.append(strong);
      if(help){const small=document.createElement("small");small.textContent=help;text.append(small);}
      row.append(toggle,text);return row;
    };
    const frameUrl=(clip,which,carried=false)=>clip?api.apiURL(`/minimax_director/clip/frame?${new URLSearchParams({project_id:timelineState.project_id || "",clip_id:clip.id,which,carried:carried?"1":"0",height:"540",g:String(cachedClipResults[clip.id]?.generation ?? "none")})}`):null;
    const chainStart=()=>{let j=clipIndex-1;while(j>0 && effectiveContinuity(timelineState.clips[j])!==MODE.independent && !isStartImageClip(timelineState.clips[j]))j--;return timelineState.clips[j];};
    const lookSection=(title,key,imageUrl,emptyText,extra={})=>{
      const box=document.createElement("div");box.className="mmx-look-section";
      const head=document.createElement("div");head.className="mmx-look-head";
      const h=document.createElement("strong");h.textContent=title;head.append(h);
      if(!lookIsNeutral(activeClip[key])){const badge=document.createElement("span");badge.className="mmx-look-badge";badge.textContent="Adjusted";head.append(badge);}
      box.append(head);
      if(extra.note){const p=document.createElement("p");p.className="mmx-continuity-mode-note";p.textContent=extra.note;box.append(p);}
      box.editor=createLookEditor({imageUrl,emptyText,look:activeClip[key],beforeLabel:extra.before || "Original",afterLabel:extra.after || "Adjusted",
        anchorUrl:extra.anchorUrl,anchorLabel:extra.anchorLabel,compareOriginal:extra.compareOriginal,
        onChange:look=>{if(lookIsNeutral(look))delete activeClip[key];else activeClip[key]=look;syncState();head.querySelector(".mmx-look-badge")?.remove();if(!lookIsNeutral(look)){const badge=document.createElement("span");badge.className="mmx-look-badge";badge.textContent="Adjusted";head.append(badge);}}});
      box.append(box.editor);
      return box;
    };
    // Auto calibrate: one button in the look editor's own block. It measures
    // the generated take (see /minimax_director/clip/calibration) and sets
    // the sliders in place, so the live compare keeps its zoom and position
    // and the change is visible immediately. Calibrate targets the Join row
    // only (start vs. previous end, both raw); the start follows the graded
    // tail almost 1:1, while drift toward the end is Hold look's job.
    const addAutoCalibrate=section=>{
      const editor=section.editor;if(!editor?.actions)return;
      const button=document.createElement("button");button.type="button";button.className="mmx-calib-btn";
      button.textContent="Auto calibrate";button.disabled=true;
      const status=document.createElement("small");status.className="mmx-calib-status";status.textContent="Measuring the generated take…";
      editor.actions.append(button,status);editor.actions.hidden=false;
      const generation=cachedClipResults[activeClip.id]?.generation ?? "none";
      const before=timelineState.clips.slice(0,clipIndex).map(c=>c.id).join(",");
      const cacheKey=[timelineState.project_id||"",activeClip.id,generation,cachedClipResults[previousClip?.id]?.generation ?? "none",before].join("|");
      const measured=calibrationCache.get(cacheKey) || requestJson(`/minimax_director/clip/calibration?${new URLSearchParams({project_id:timelineState.project_id||"",clip_id:activeClip.id,before})}`);
      calibrationCache.set(cacheKey,measured);
      const pctText=v=>`${v>0?"+":""}${v.toFixed(1)}%`;
      measured.then(m=>{
        const luma=s=>.299*s.rgb[0]+.587*s.rgb[1]+.114*s.rgb[2];
        const pct=(x,y)=>(x/Math.max(1e-6,y)-1)*100;
        const join=[["brightness",pct(luma(m.first),luma(m.previous_end))],["warm",pct(m.first.rgb[0]/m.first.rgb[1],m.previous_end.rgb[0]/m.previous_end.rgb[1])],["cool",pct(m.first.rgb[2]/m.first.rgb[1],m.previous_end.rgb[2]/m.previous_end.rgb[1])],["contrast",pct(m.first.std,m.previous_end.std)]];
        const summary="This take's start vs. the previous end: "+join.map(([k,v])=>`${k} ${pctText(v)}`).join(", ")+".";
        // Calibrate from the look this take actually used, not from edits made since.
        const current=activeClip.tail_look||null;
        const used=m.tail_look_known?(m.tail_look||null):(lookIsNeutral(current)?null:current);
        const next=calibrateLook(used,m.previous_end,m.first,{contrast:true});
        button.disabled=false;status.textContent=summary;
        button.title="Set the sliders so the next take starts the way the previous clip ended. Click again to go back to the calibrated values after editing.";
        button.onclick=()=>{
          editor.setLook(next);delete activeClip.calibrated_from;
          const changes=lookChanges(used,next);
          status.textContent=(changes.length?"Calibrated: "+changes.join(" · "):"The join already matches; sliders set to what this take used.")+" Regenerate this clip to use them.";
        };
      }).catch(error=>{
        calibrationCache.delete(cacheKey);
        if(error.status===404){status.textContent="Generate this clip once to auto calibrate from its take.";button.title="Needs a generated take of this clip";}
        else status.textContent=`Could not measure this take: ${error.message}`;
      });
    };
    if(startImage){
      const code=clipCode(activeClip);
      const on=mode===MODE.frame && clipIndex>0;
      continuityPanel.append(switchRow("Start from the previous clip's last frame",on,checked=>commitContinuity(checked?MODE.frame:MODE.independent),
        clipIndex===0?"The first clip has no previous clip.":on?"The previous clip's final frame becomes this clip's first frame. References are not used for the start.":
        code==="I2V"?"Off: choose exactly one start image in References.":"Off: choose a start image and an end image in References.",clipIndex===0));
      let url=null,empty="";
      if(on){url=frameUrl(previousClip,"last",true);empty="Generate the previous clip to preview its last frame. Adjustments you set here still apply.";}
      else{
        const first=activeReferences(activeClip).find(row=>row.type==="image");
        if(first?.filename){const parts=String(first.filename).replaceAll("\\","/").split("/");url=api.apiURL(`/view?${new URLSearchParams({filename:parts.pop(),subfolder:parts.join("/"),type:"input"})}`);}
        empty=first?"This reference has no file to preview. Adjustments still apply.":"Choose the start image in References to preview it.";
      }
      continuityPanel.append(lookSection("Start image look","start_look",url,empty,{note:"Adjust the start image before it is used. The preview shows exactly what the model receives."}));
    } else {
      const method=document.createElement("select");method.className="mmx-shot-continuity-mode";
      for(const [value,label] of [[MODE.independent,"Independent"],[MODE.motion,"Motion Context"],[MODE.carry,"Latent Carry"]]){const option=document.createElement("option");option.value=value;option.textContent=label;method.append(option);}
      method.value=mode;method.disabled=!!activeClip.locked;method.onchange=()=>commitContinuity(method.value);
      continuityPanel.append(field("Method",method,"Independent starts fresh. Motion Context guides the new clip with the previous clip's ending. Latent Carry continues the previous clip's ending directly (recommended: least drift)."));
      if(mode!==MODE.independent){
        const burnNote=document.createElement("p");burnNote.className="mmx-antiburn-note";
        burnNote.textContent=antiburnText(activeClip.antiburn);continuityPanel.append(burnNote);
      }
      if(mode===MODE.independent){
        const note=document.createElement('p');note.className='mmx-continuity-mode-note';note.textContent='Starts a fresh clip. No video or audio context is borrowed.';continuityPanel.append(note);
      } else {
        const grid=document.createElement("div");grid.className="mmx-form-grid";
        for (const [key,title,choices,fallback] of [["context_length","Video context",[5,22,39,56],22],["audio_context_length","Audio context",[0,5,22,24,39,56],22]]) {
          const input=document.createElement("select");input.className="mmx-shot-"+key;
          for (const value of choices){const option=document.createElement("option");option.value=value;option.textContent=value===0?"Off":`${(value/24).toFixed(2)} s (${value} frames)`;input.append(option);}
          input.value=activeClip[key] ?? fallback;input.disabled=!!activeClip.locked;
          input.onchange=()=>{activeClip[key]=Number(input.value);commitContinuity(mode,false);};
          grid.append(field(title,input,key==="audio_context_length"?"24 frames = 1 second. Off disables audio carry.":"Reused from the previous clip and removed from this clip's delivered frames."));
        }
        const policy=document.createElement("select");policy.className="mmx-shot-continuity-duration-policy";
        for (const [value,label] of [["new","Keep full clip length"],["total","Shorten by reused frames"]]) {const option=document.createElement("option");option.value=value;option.textContent=label;policy.append(option);}
        policy.value=activeClip.continuity_duration_policy || "new";
        policy.onchange=()=>{activeClip.continuity_duration_policy=policy.value;commitContinuity(mode,false);};
        grid.append(field("Clip length",policy,"Keep: generate the full requested length after the reused frames. Shorten: fit them inside it."));
        if(mode===MODE.carry){
          const redraw=document.createElement("input");redraw.type="number";redraw.min="0";redraw.max="0.95";redraw.step="0.05";redraw.value=activeClip.continuity_redraw ?? .1;
          redraw.onchange=()=>{activeClip.continuity_redraw=Number(redraw.value);commitContinuity(mode,false);};grid.append(field("Transition flexibility",redraw,"0 keeps the join closest to the previous clip; higher lets the model change more near the join."));
        }
        continuityPanel.append(grid);
        const fixes=document.createElement("div");fixes.className="mmx-switch-group";
        const fixesTitle=document.createElement("div");fixesTitle.className="mmx-switch-group-title";
        fixesTitle.innerHTML="<strong>Continuity corrections</strong><span>Each fixes a different thing; Auto calibrate below fixes how this clip starts.</span>";
        fixes.append(fixesTitle);
        fixes.append(switchRow("Prevent build-up at joins",activeClip.auto_fix!==false,checked=>{if(checked)delete activeClip.auto_fix;else activeClip.auto_fix=false;syncState();},
          "During generation. Stops sharpness, contrast and the model's slight blue cast from adding up clip after clip. Works with calibrated sliders too. Recommended."));
        fixes.append(switchRow("Keep colour on the chain's first clip",!!activeClip.hold_look,checked=>{if(checked)activeClip.hold_look=true;else delete activeClip.hold_look;syncState();},
          "After decoding. A colour-only correction that starts at zero at the join and grows toward the end, so colour does not drift along a long chain. Brightness is left as generated; Auto calibrate measures without it."));
        continuityPanel.append(fixes);
        const tailSection=lookSection("Start of this clip","tail_look",frameUrl(previousClip,"last",true),
          "Generate the previous clip to preview its last frame. Adjustments you set here still apply.",
          {note:"The same region of the frame, zoomed, from both images: left, the previous clip's last frame; right, how this clip will start. Drag the picture to move the region; 1× 2× 4× sets the zoom. The first second follows these sliders closely (within about 1% in tests); after that the model's own look takes over, so the sliders cannot fix drift later in the clip. When adjusted, the tail is re-encoded from these pixels (slightly softer join).",
           compareOriginal:true,anchorLabel:"Predicted start of this clip vs. the previous clip's end",
           before:"Previous clip's end",after:"Start of this clip"});
        continuityPanel.append(tailSection);
        if(previousClip)addAutoCalibrate(tailSection);
      }
    }
    shotSections.prepend(continuityPanel);
    finishSection(continuityPanel,clipIndex===0?"The first clip has no previous clip to continue from.":startImage?"Start-image clips can begin from the previous clip's last frame, with an optional look adjustment.":mode===MODE.independent?"Independent clips borrow no video or audio context.":"This clip continues the previous clip. Short previous clips limit the usable video and audio context.");
    titleWrap.appendChild(timingRow);

    // Seed controls in the clip header.
    const samplingRow = document.createElement("div");
    samplingRow.className = "mmx-inspector-card-row";

    // Seed Input + Dice Button
    const seedItem = document.createElement("div");
    seedItem.className = "mmx-ctrl-item";

    const seedLabel = document.createElement("label");
    seedLabel.textContent = "Seed:";
    seedItem.appendChild(seedLabel);

    const seedInput = document.createElement("input");
    seedInput.type = "text";
    seedInput.style.width = "200px";
    seedInput.setAttribute("aria-label","Clip Seed");
    seedInput.style.background = "var(--comfy-input-bg, #333333)";
    seedInput.style.border = "1px solid var(--border-color, #4a4a4a)";
    seedInput.style.borderRadius = "4px";
    seedInput.style.color = "#f8fafc";
    seedInput.style.fontSize = "11px";
    seedInput.style.fontFamily = "monospace";
    seedInput.style.textAlign = "center";
    const initSeed = activeClip.seed !== undefined ? activeClip.seed : 0;
    seedInput.value = String(initSeed);
    seedInput.onchange = () => {
      try {
        if (!/^\d+$/.test(seedInput.value.trim())) throw new Error();
        const value = BigInt(seedInput.value.trim());
        if (value > 0xffffffffffffffffn) throw new Error();
        activeClip.seed = value.toString(); seedInput.value = activeClip.seed; seedInput.setCustomValidity("");
      } catch { seedInput.setCustomValidity("Enter a decimal integer from 0 to 18446744073709551615."); seedInput.reportValidity(); return; }
      syncState();
    };
    seedItem.appendChild(seedInput);

    const diceBtn = document.createElement("button");
    diceBtn.className = "mmx-action-btn";
    diceBtn.style.padding = "2px 6px";
    diceBtn.style.fontSize = "12px";
    diceBtn.innerHTML = "🎲";
    diceBtn.title = "Generate new random seed";
    diceBtn.onclick = () => {
      const newSeed = Math.floor(Math.random() * 10000000000);
      activeClip.seed = String(newSeed);
      seedInput.value = String(newSeed);
      syncState();
    };
    seedItem.appendChild(diceBtn);
    samplingRow.appendChild(seedItem);

    // Seed Mode Select
    const modeItem = document.createElement("div");
    modeItem.className = "mmx-ctrl-item";

    const modeLabel = document.createElement("label");
    modeLabel.textContent = "Mode:";
    modeItem.appendChild(modeLabel);

    const seedModeSelect = document.createElement("select");
    seedModeSelect.className = "mmx-mode-select";
    seedModeSelect.setAttribute("aria-label","Clip Seed Mode");
    seedModeSelect.style.background = "var(--comfy-input-bg, #333333)";
    seedModeSelect.style.border = "1px solid var(--border-color, #4a4a4a)";
    seedModeSelect.style.borderRadius = "4px";
    seedModeSelect.style.color = "#cbd5e1";
    seedModeSelect.style.fontSize = "11px";
    seedModeSelect.style.padding = "2px 6px";
    seedModeSelect.title = "Seed behavior after execution (fixed, randomize, increment, decrement)";
    const seedModes = [
      { id: "fixed", label: "Fixed" },
      { id: "randomize", label: "Randomize" },
      { id: "increment", label: "Increment (+1)" },
      { id: "decrement", label: "Decrement (-1)" },
    ];
    seedModes.forEach((sm) => {
      const opt = document.createElement("option");
      opt.value = sm.id;
      opt.textContent = sm.label;
      if ((activeClip.seed_mode || "fixed") === sm.id) opt.selected = true;
      seedModeSelect.appendChild(opt);
    });
    seedModeSelect.onchange = () => {
      activeClip.seed_mode = seedModeSelect.value;
      syncState();
    };
    modeItem.appendChild(seedModeSelect);
    samplingRow.appendChild(modeItem);

    titleWrap.appendChild(samplingRow);


    // 1. Local References Pool Selector (Includes Images, Videos, Audios, RefMods)
    const refsPoolWrap = document.createElement("div");
    refsPoolWrap.className = "mmx-local-refs-pool";

    const refsTitle = document.createElement("div");
    refsTitle.className = "mmx-local-refs-title";
    refsTitle.innerHTML = `
      <span>REFERENCE PACK ASSETS</span>
      <span style="font-weight: 500; font-size: 9px; color: #64748b;">Click to assign to this clip</span>
    `;
    refsTitle.append(syncRefsBtn);refsPoolWrap.appendChild(refsTitle);
    const selectionNote=document.createElement('p');selectionNote.className='mmx-section-intro';selectionNote.textContent=selectionHelp(activeClip);refsPoolWrap.append(selectionNote);

    const refsList = document.createElement("div");
    refsList.className = "mmx-local-refs-list";

    if (!Array.isArray(activeClip.ref_ids)) activeClip.ref_ids = [];

    const allRefs = (timelineState.available_refs || []).filter(row=>referenceTypes(activeClip).includes(row.type));
    // Prompt tag each selected asset answers to, with memory slots in their real place.
    const slotTags = new Map(); { const n = {image:0, video:0, audio:0, refmod:0};
      for (const row of activeReferences(activeClip)) { const kind = ({image:"Picture",video:"Video",audio:"Audio",refmod:"RefMod"})[row.type]; slotTags.set(row.id, `<${kind} ${row.type === "video" ? ownVideoNumber(activeClip, n.video++) : ++n[row.type]}>`); } }
    refsPoolWrap.hidden = referenceTypes(activeClip).length === 0;
    if(!allRefs.length && !memoryRows(activeClip).length){const empty=document.createElement("span");empty.textContent="No compatible assets in the connected Reference Pack.";refsList.append(empty);}
    allRefs.forEach((r) => {
      const isChecked = activeClip.ref_ids.includes(r.id);
      const item = document.createElement("button");
      const rtype = r.type || "image";
      const typeClass = rtype === "video" ? "type-vid" : (rtype === "audio" ? "type-aud" : (rtype === "refmod" ? "type-mod" : "type-img"));
      item.className = "mmx-local-ref-item" + (isChecked ? ` checked ${typeClass}` : "");

      const icon = rtype === "image" ? "🖼️" : (rtype === "video" ? "📹" : (rtype === "audio" ? "🎵" : "🎛️"));
      const tag = rtype === "image" ? "[IMG]" : (rtype === "video" ? "[VID]" : (rtype === "audio" ? "[AUD]" : "[MOD]"));
      const fnHint = r.filename ? ` <span style="font-size: 8px; opacity: 0.55; max-width: 90px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: inline-block; vertical-align: middle;">(${escapeHtml(r.filename)})</span>` : "";
      item.innerHTML = `<span>${icon}</span><span style="font-weight: 700; opacity: 0.7;">${tag}</span><span>${escapeHtml(r.name)}</span>${fnHint}`;
      if (r.filename) item.title = `${r.name} (${r.filename})`;
      if (isChecked && slotTags.has(r.id)) { const slot = document.createElement("b"); slot.className = "mmx-ref-slot"; slot.textContent = slotTags.get(r.id); item.append(slot); }

      item.dataset.refId=r.id;
      const single=selectionLimit(activeClip,rtype)===1;
      const selected=activeReferences(activeClip);
      const imageFamily=['image','refmod'].includes(rtype);
      const atLimit=selected.filter(row=>imageFamily ? ['image','refmod'].includes(row.type) : row.type===rtype).length>=(imageFamily && ['REF2V','RV2V'].includes(clipCode(activeClip)) ? 9 : selectionLimit(activeClip,rtype)) || selected.length>=12;
      item.disabled=externallyAuthored || (!isChecked && !single && atLimit);
      if(item.disabled)item.title='Selection limit reached. Remove an asset before choosing another.';
      if(isChecked && ['FL2V','RV2V'].includes(clipCode(activeClip))) item.title=`Selection ${activeClip.ref_ids.indexOf(r.id)+1}${r.id===activeClip.source?.ref_id ? ' · Source Video' : ''}`;
      if(isChecked && (clipCode(activeClip)==='FL2V' || r.id===activeClip.source?.ref_id)) {
        const inheritedOpening=continuesFromLastFrame(activeClip);
        const role=document.createElement('strong');role.textContent=r.id===activeClip.source?.ref_id ? ' · Source Video' : activeClip.ref_ids.indexOf(r.id)===0 && !inheritedOpening ? ' · Opening Frame' : ' · Ending Frame';item.append(role);
      }
      item.onclick = async () => {
        if (isChecked) activeClip.ref_ids = activeClip.ref_ids.filter(id=>id!==r.id);
        else if(single) activeClip.ref_ids=[r.id];
        else activeClip.ref_ids.push(r.id);
        if(['VIDEO','V2V','RV2V'].includes(clipCode(activeClip))) {
          const source=activeReferences(activeClip).find(row=>row.type==='video');
          if(source?.id!==activeClip.source?.ref_id) {
            delete activeClip.source;delete activeClip.source_start;delete activeClip.source_end;
            if(source) {
              activeClip.source={ref_id:source.id};activeClip.source_start=0;
              // Filename metadata is only a UI estimate; execution uses the injected frame batch.
              if(source.filename) try {
                const info=await requestJson(`/minimax_director/source/info?filename=${encodeURIComponent(source.filename)}`);
                if(info.duration>0 && activeClip.source?.ref_id===source.id){activeClip.duration=info.duration;activeClip.source_end=info.duration;}
              } catch(error) { selectionNote.textContent=`Source selected. Could not read file metadata: ${error.message}`; }
            }
          }
        }
        syncState();renderTimeline();
      };
      refsList.appendChild(item);
    });

    // Memory fills the slots after the clip's own references.
    if (memorySupported(activeClip)) memoryRows(activeClip).forEach(row => {
      const src = clipById(row.clip_id), chip = document.createElement("span");
      chip.className = "mmx-local-ref-item checked mmx-ref-memory";
      const whole = row.end == null && !(Number(row.start) > 0), image = memoryKind(row) === "image";
      const range = image ? ` · frame at ${Number(row.start||0).toFixed(2)} s` : whole ? "" : ` · ${Number(row.start||0).toFixed(1)}–${Number(row.end).toFixed(1)} s`;
      chip.innerHTML = `<span>🧠</span><span style="font-weight:700;opacity:.7;">[MEM]</span><span>${escapeHtml(src?.name || row.clip_id)}${range}</span><b class="mmx-ref-slot">${escapeHtml(memoryTag(activeClip, row))}</b>`;
      chip.title = "Clip memory fills this video slot automatically. Change it in the Memory tab.";
      refsList.appendChild(chip);
    });
    refsPoolWrap.appendChild(refsList);
    inspector.appendChild(refsPoolWrap);

    // 2. Dedicated Per-Clip Clip Prompt (Raw Mode vs Structured Mode)
    const promptWrap = document.createElement("div");
    promptWrap.className = "mmx-prompt-inspector";

    const promptToolbar = document.createElement("div");
    promptToolbar.className = "mmx-prompt-toolbar";

    const promptTitle = document.createElement("div");
    promptTitle.style.fontSize = "10px";
    promptTitle.style.fontWeight = "700";
    promptTitle.style.color = "#818cf8";
    promptTitle.textContent = "Clip prompt";
    promptTitle.title = `Prompt for ${activeClip.name || activeClip.id || "this clip"}`;
    promptToolbar.appendChild(promptTitle);

    // Mode Selector: Raw Prompt vs Structured Prompt
    const modeTabs = document.createElement("div");
    modeTabs.className = "mmx-prompt-mode-tabs";

    if (!activeClip.prompt_mode) activeClip.prompt_mode = "raw";
    if (!activeClip.structured_prompt) {
      activeClip.structured_prompt = {
        subject_definitions: "",
        summary: "",
        retention_analysis: "",
        detailed_description: "",
        overall_soundscape: "",
        soundscape: "",
        non_diegetic_music: "",
        music: "",
      };
    } else {
      if (activeClip.structured_prompt.soundscape && !activeClip.structured_prompt.overall_soundscape) {
        activeClip.structured_prompt.overall_soundscape = activeClip.structured_prompt.soundscape;
      }
      if (activeClip.structured_prompt.music && !activeClip.structured_prompt.non_diegetic_music) {
        activeClip.structured_prompt.non_diegetic_music = activeClip.structured_prompt.music;
      }
    }

    const rawTab = document.createElement("button");
    rawTab.className = "mmx-prompt-mode-tab" + (activeClip.prompt_mode !== "structured" ? " active" : "");
    rawTab.textContent = "Raw Prompt";
    rawTab.onclick = () => {
      activeClip.prompt_mode = "raw";
      syncState();
      renderInspector();
    };

    const structTab = document.createElement("button");
    structTab.className = "mmx-prompt-mode-tab" + (activeClip.prompt_mode === "structured" ? " active" : "");
    structTab.textContent = "Structured Prompt";
    structTab.onclick = () => {
      activeClip.prompt_mode = "structured";
      syncState();
      renderInspector();
    };

    modeTabs.appendChild(rawTab);
    modeTabs.appendChild(structTab);
    promptToolbar.appendChild(modeTabs);
    promptWrap.appendChild(promptToolbar);

    if (activeClip.prompt_mode === "structured") {
      const sections = promptSectionsFor(activeClip);
      const fields = structuredFieldsFromText(activeClip.prompt || "", sections);
      activeClip.structured_prompt = storedSections(fields);
      const inputs = new Map();
      let lastInput = null;
      const writeBack = () => {
        activeClip.prompt = compilePromptSections(fields);
        activeClip.structured_prompt = storedSections(fields);
        syncState();
        if (promptWidget) promptWidget.value = activeClip.prompt;
        updatePromptCounters();
      };
      const grow = area => { area.style.height = "auto"; area.style.height = `${Math.max(area.scrollHeight, 20)}px`; };

      // Toolbar: reference tokens insert into the section you were editing.
      const bar = document.createElement("div"); bar.className = "mmx-sp-bar";
      const tagRow = document.createElement("div"); tagRow.className = "mmx-quick-tags";
      const counts = {image:0, video:0, audio:0, refmod:0};
      const tagList = activeReferences(activeClip).map(row => { const kind = ({image:"Picture",video:"Video",audio:"Audio",refmod:"RefMod"})[row.type]; const n = row.type === "video" ? ownVideoNumber(activeClip, counts.video++) : ++counts[row.type]; return {label:`${row.name} · <${kind} ${n}>`, tag:`<${kind} ${n}>`}; });
      memoryRows(activeClip).forEach(row => { const tag = memoryTag(activeClip, row); tagList.push({label:`Memory · ${tag}`, tag, memory:true}); });
      for (const t of tagList) {
        const b = document.createElement("button"); b.type = "button"; b.className = "mmx-quick-tag-btn" + (t.memory ? " mmx-tag-memory" : ""); b.textContent = t.label; b.title = `Insert ${t.tag}`;
        b.disabled = externallyAuthored;
        b.onmousedown = e => e.preventDefault();
        b.onclick = () => {
          const area = lastInput || inputs.get(sections.find(s => s.main).key); if (!area) return;
          const start = area.selectionStart ?? area.value.length, end = area.selectionEnd ?? start;
          area.value = area.value.slice(0, start) + t.tag + area.value.slice(end);
          area.selectionStart = area.selectionEnd = start + t.tag.length; area.focus(); area.oninput();
        };
        tagRow.appendChild(b);
      }
      bar.appendChild(tagRow);
      if (isReferencePromptMode(activeClip) && activeReferences(activeClip).length) {
        const fill = document.createElement("button"); fill.type = "button"; fill.className = "mmx-sp-fill";
        fill.textContent = "Fill empty sections from references";
        fill.title = "Writes a starting point into sections that are still empty. Sections you wrote are never changed.";
        fill.disabled = externallyAuthored;
        fill.onclick = () => {
          const scaffold = scaffoldStructuredPrompt(activeClip);
          for (const s of sections) if (!String(fields[s.key] || "").trim() && scaffold[s.key]) fields[s.key] = scaffold[s.key];
          writeBack(); renderInspector();
        };
        bar.appendChild(fill);
      }
      promptWrap.appendChild(bar);

      const grid = document.createElement("div"); grid.className = "mmx-sp-grid";
      for (const section of sections) {
        const card = document.createElement("label"); card.className = "mmx-sp-card" + (section.half ? " mmx-sp-half" : "");
        const head = document.createElement("span"); head.className = "mmx-sp-head";
        const title = document.createElement("span"); title.className = "mmx-sp-title"; title.textContent = section.title;
        const key = document.createElement("code"); key.className = "mmx-sp-key"; key.textContent = section.key;
        head.append(title, key);
        const area = document.createElement("textarea"); area.className = "mmx-sp-input"; area.rows = section.rows;
        area.placeholder = section.hint; area.value = fields[section.key] || ""; area.readOnly = externallyAuthored;
        area.spellcheck = true;
        area.onfocus = () => { lastInput = area; };
        area.oninput = () => { fields[section.key] = area.value; grow(area); writeBack(); };
        inputs.set(section.key, area);
        card.append(head, area); grid.appendChild(card);
        requestAnimationFrame(() => grow(area));
      }
      const hidden = Object.keys(fields).filter(k => String(fields[k] || "").trim() && !sections.some(s => s.key === k));
      if (hidden.length) {
        const note = document.createElement("p"); note.className = "mmx-sp-hidden-note";
        note.textContent = `Also kept in the prompt (not used by this clip type's sections): ${hidden.join(", ")}. Edit them in Raw.`;
        grid.appendChild(note);
      }
      promptWrap.appendChild(grid);
    } else {
      // Raw Prompt View with Quick Tags
      const rawSubToolbar = document.createElement("div");
      rawSubToolbar.className = "mmx-prompt-toolbar";

      const quickTags = document.createElement("div");
      quickTags.className = "mmx-quick-tags";

      const counts = {image:0, video:0, audio:0, refmod:0};
      const tags = activeReferences(activeClip).map(row => {
        const kind = {image:"Picture", video:"Video", audio:"Audio", refmod:"RefMod"}[row.type];
        const tag = `<${kind} ${row.type === "video" ? ownVideoNumber(activeClip, counts.video++) : ++counts[row.type]}>`;
        return {label: `${row.name} · ${tag}`, tag};
      });
      memoryRows(activeClip).forEach(row => { const tag = memoryTag(activeClip, row); tags.push({label:`Memory · ${tag}`, tag}); });

      tags.forEach((t) => {
        const tagBtn = document.createElement("button");
        tagBtn.className = "mmx-quick-tag-btn";
        tagBtn.textContent = t.label;
        tagBtn.title = `Insert ${t.tag} at cursor position`;
        tagBtn.onclick = () => {
          const start = promptArea.selectionStart || 0;
          const end = promptArea.selectionEnd || 0;
          const current = promptArea.value;
          const next = current.substring(0, start) + t.tag + current.substring(end);
          promptArea.value = next;
          activeClip.prompt = next;
          syncState();
          if (promptWidget) promptWidget.value = next;
          promptArea.focus();
          promptArea.selectionStart = promptArea.selectionEnd = start + t.tag.length;
          updatePromptCounters();
        };
        quickTags.appendChild(tagBtn);
      });

      rawSubToolbar.appendChild(quickTags);
      rawSubToolbar.hidden=tags.length===0;
      promptWrap.appendChild(rawSubToolbar);

      const promptArea = document.createElement("textarea");
      promptArea.className = "mmx-textarea";
      promptArea.style.flex = "1";
      promptArea.style.height = "100%";
      promptArea.style.minHeight = "100px";
      promptArea.placeholder = `Describe the action, camera movement and sound. Assign references from the connected pool to insert their tokens.`;
      promptArea.value = activeClip.prompt || "";
      promptArea.readOnly=externallyAuthored;
      promptArea.oninput = () => {
        activeClip.prompt = promptArea.value;
        syncState();
        if (promptWidget) promptWidget.value = promptArea.value;
        updatePromptCounters();
      };
      promptWrap.appendChild(promptArea);
    }

    // Prompt footer: Character and word counter
    const promptFooter = document.createElement("div");
    promptFooter.style.display = "flex";
    promptFooter.style.justifyContent = "flex-end";
    promptFooter.style.paddingTop = "2px";
    promptFooter.style.flexShrink = "0";

    const charCounter = document.createElement("span");
    charCounter.className = "mmx-prompt-char-count";
    const updatePromptCounters = () => {
      const text = activeClip.prompt || "";
      const chars = text.length;
      const words = text.trim() ? text.trim().split(/\s+/).length : 0;
      charCounter.textContent = `${chars} chars | ${words} words`;
      const snippet = shotsLane.querySelector(".mmx-subtrack-block.active .mmx-shot-prompt-preview");
      if (snippet) {
        const ptext = text.trim();
        snippet.textContent = ptext || "(No prompt set)";
        snippet.style.color = ptext ? "#94a3b8" : "#475569";
        snippet.style.fontStyle = ptext ? "normal" : "italic";
      }
    };
    updatePromptCounters();
    const autoNote = memoryNoteFor(activeClip);
    if (autoNote) {
      // Never silently injected: show exactly what H3 receives in addition.
      const box = document.createElement("details"); box.className = "mmx-memory-auto-note";
      const sum = document.createElement("summary"); sum.textContent = `Memory note · added to the prompt automatically (${memoryRows(activeClip).length})`;
      const pre = document.createElement("pre"); pre.textContent = autoNote;
      box.append(sum, pre); promptWrap.appendChild(box);
    }
    promptFooter.appendChild(charCounter);
    promptWrap.appendChild(promptFooter);

    inspector.appendChild(promptWrap);
    // The writing surface and its essential controls never move when tools
    // change. Tool panels scroll independently of the prompt and timeline.
    const workspace=document.createElement("div");workspace.className="mmx-edit-workspace";
    const writing=document.createElement("div");writing.className="mmx-edit-main";
    writing.append(refsPoolWrap,promptWrap);
    const sourcePanel=inspector.querySelector("fieldset");
    if(sourcePanel)writing.append(sourcePanel);
    const tools=document.createElement("aside");tools.className="mmx-edit-tools"+(showToolHelp?" mmx-show-help":"");
    const toolHeading=document.createElement("div");toolHeading.className="mmx-tools-heading";toolHeading.textContent="Clip controls";
    const helpButton=document.createElement("button");helpButton.textContent="Help";helpButton.title="Show explanations for each control";
    helpButton.setAttribute("aria-pressed",String(showToolHelp));
    helpButton.onclick=()=>{showToolHelp=!showToolHelp;tools.classList.toggle("mmx-show-help",showToolHelp);helpButton.setAttribute("aria-pressed",String(showToolHelp));};toolHeading.append(helpButton);
    const tabs=document.createElement("div");tabs.className="mmx-tool-tabs";tabs.setAttribute("role","tablist");tabs.setAttribute("aria-label","Clip controls");
    shotSections.className="mmx-shot-sections mmx-tool-content";
    const panels=[["Continuity",continuityPanel],["Guides",shotExtras],["LoRAs",loraPanel],["Memory",memoryPanel]];
    const canContinue=!continuityPanel.hidden;
    const unavailable=label=>(label==="Continuity"&&!canContinue) || ((label==="LoRAs"||label==="Memory")&&!!activeClip.locked) || (label==="Memory"&&!memorySupported(activeClip));
    if(activeToolTab==="Look")activeToolTab="Guides";
    if(unavailable(activeToolTab))activeToolTab="Guides";
    const selectTool=label=>{
      if(unavailable(label))return;
      activeToolTab=label;
      for(const [name,panel] of panels)panel.hidden=name!==label;
      for(const button of tabs.querySelectorAll("button")){
        button.setAttribute("aria-selected",String(button.dataset.tool===label));
        button.tabIndex=button.dataset.tool===label?0:-1;
      }
    };

    for(const [label,panel] of panels){
      const button=document.createElement("button");button.textContent=label;button.type="button";
      button.dataset.tool=label;button.tabIndex=label===activeToolTab?0:-1;
      button.setAttribute("role","tab");button.setAttribute("aria-selected",String(label===activeToolTab));
      const panelId=`mmx-${node.id}-${label.toLowerCase()}-panel`;button.id=panelId+"-tab";
      button.setAttribute("aria-controls",panelId);button.disabled=unavailable(label);
      if(label==="Memory"&&!memorySupported(activeClip))button.title="Memory works on REF2V and RV2V clips.";
      if(label==="Memory"&&memorySupported(activeClip)&&memoryRows(activeClip).length){const count=document.createElement("span");count.className="mmx-tab-count";count.textContent=String(memoryRows(activeClip).length);button.append(count);}
      panel.id=panelId;panel.setAttribute("role","tabpanel");panel.setAttribute("aria-labelledby",button.id);
      panel.open=true;panel.hidden=label!==activeToolTab;shotSections.append(panel);
      button.onclick=()=>selectTool(label);
      button.onkeydown=e=>{
        if(!["ArrowLeft","ArrowRight","Home","End"].includes(e.key))return;e.preventDefault();
        const enabled=[...tabs.querySelectorAll("button")].filter(b=>!b.disabled),i=enabled.indexOf(button);
        const next=e.key==="Home"?0:e.key==="End"?enabled.length-1:(i+(e.key==="ArrowRight"?1:-1)+enabled.length)%enabled.length;
        selectTool(enabled[next].dataset.tool);
        inspector.querySelector(`[role=tab][aria-selected=true]`)?.focus();
      };
      tabs.append(button);
    }
    tools.append(toolHeading,tabs,shotSections);workspace.append(writing,tools);inspector.append(workspace);
    selectTool(activeToolTab);
  };

  // Initial render
  renderTimeline();

  // Attach DOM Widget to ComfyUI node with dynamic size computation
  domWidget = node.addDOMWidget("master_director_ui", "custom_ui", root, {
    serialize: false,
    hideOnZoom: false,
    getMinHeight: () => getMinDomHeight(),
    getHeight: () => getAvailableDomHeight(node, getMinDomHeight()),
    onResize: () => {
      updateDomSize();
      drawRuler();
    },
  });

  if (domWidget) {
    // Keep the editor below the sockets, using the same offset in every hook.
    const origDomDraw = domWidget.draw;
    domWidget.draw = function (ctx, n, widget_width, y, widget_height) {
      const topY = getTopWidgetsHeight(n || node) + (generationWidget ? 30 : 0);
      this.last_y = topY;
      if (origDomDraw) origDomDraw.call(this, ctx, n, widget_width, topY, widget_height);
    };

    // Move domWidget to beginning of node.widgets (index 0) so hidden widgets don't push it down
    if (node.widgets) {
      const idx = node.widgets.indexOf(domWidget);
      if (idx > 0) {
        node.widgets.splice(idx, 1);
        node.widgets.unshift(domWidget);
        if(generationWidget) { node.widgets.splice(node.widgets.indexOf(generationWidget),1);node.widgets.unshift(generationWidget); }
      }
    }

    domWidget.computeSize = function (width) {
      const minH = getMinDomHeight();
      const nodeW = node.size?.[0] || 1200;
      return [width || Math.max(nodeW - 20, 880), minH];
    };
    updateDomSize();
  }

  // Hook node resize, computeSize, and onDrawForeground
  const origOnResize = node.onResize;
  node.onResize = function (size) {
    const topY = getTopWidgetsHeight(this);
    this.widgets_start_y = topY;
    if (domWidget) domWidget.last_y = topY + (generationWidget ? 30 : 0);
    const minH = getMinDomHeight();
    const minNodeH = topY + minH + 16;
    const minNodeW = 1200;

    if (size) {
      if (size[0] < minNodeW) size[0] = minNodeW;
      if (size[1] < minNodeH) size[1] = minNodeH;
    }

    if (origOnResize) origOnResize.apply(this, arguments);
    updateDomSize();
    drawRuler();
  };

  const origComputeSize = node.computeSize;
  node.computeSize = function (out) {
    const topY = getTopWidgetsHeight(this);
    this.widgets_start_y = topY;
    if (domWidget) domWidget.last_y = topY + (generationWidget ? 30 : 0);
    const minH = getMinDomHeight();
    const minNodeH = topY + minH + 16;
    const minNodeW = 1200;

    let sz = [minNodeW, minNodeH];
    if (out) {
      out[0] = sz[0];
      out[1] = sz[1];
      return out;
    }
    return sz;
  };
  // A freshly added Master starts at LiteGraph's default width, which squeezes
  // the editor into a narrow scrolling column. Saved workflows restore their
  // own size in onConfigure, which runs after this.
  if ((node.size?.[0] || 0) < 1200) {
    const fresh = node.computeSize();
    node.setSize?.([Math.max(1500, fresh[0]), Math.max(fresh[1], getTopWidgetsHeight(node) + 1300)]);
  }

  const origOnDrawForeground = node.onDrawForeground;
  node.onDrawForeground = function (ctx) {
    const topY = getTopWidgetsHeight(this);
    this.widgets_start_y = topY;
    if (domWidget) domWidget.last_y = topY + (generationWidget ? 30 : 0);
    if (origOnDrawForeground) origOnDrawForeground.apply(this, arguments);
  };

  const origOnConnectionsChange = node.onConnectionsChange;
  node.onConnectionsChange = function () {
    if (origOnConnectionsChange) origOnConnectionsChange.apply(this, arguments);
    renderSettingsBar();
    resolveAvailableRefsFromGraph();
    syncState();
    renderTimeline();
    void refreshClipResults();
    if (activeClipId) renderInspector();
  };

  // Ensure domWidget is positioned at the TOP of node.widgets (index 0) so it starts flush at widgets_start_y
  if (node.widgets && domWidget) {
    const topY = getTopWidgetsHeight(node);
    domWidget.last_y = topY + (generationWidget ? 30 : 0);
    const domIdx = node.widgets.indexOf(domWidget);
    if (domIdx > 0) {
      node.widgets.splice(domIdx, 1);
      node.widgets.unshift(domWidget);
        if(generationWidget) { node.widgets.splice(node.widgets.indexOf(generationWidget),1);node.widgets.unshift(generationWidget); }
    }
  }

  // Refresh callback when node configuration or graph is reloaded
  node.__mmxDirectorRefresh = () => {
    const topY = getTopWidgetsHeight(node);
    node.widgets_start_y = topY;
    if (domWidget) domWidget.last_y = topY + (generationWidget ? 30 : 0);
    hideWidget(timelineWidget);
    hideWidget(builderWidget);
    hideWidget(promptWidget);
    hideWidget(durationWidget);
    if (node.widgets && domWidget) {
      const domIdx = node.widgets.indexOf(domWidget);
      if (domIdx > 0) {
        node.widgets.splice(domIdx, 1);
        node.widgets.unshift(domWidget);
        if(generationWidget) { node.widgets.splice(node.widgets.indexOf(generationWidget),1);node.widgets.unshift(generationWidget); }
      }
    }
    loadState(); syncState(true);
    const savedZoom = Number(node.properties?.mmx_timeline_zoom);
    if(Number.isFinite(savedZoom) && savedZoom >= 0.5 && savedZoom <= 3) { zoomLevel=savedZoom; zoomSlider.value=String(savedZoom); }
    renderTimeline();
    void refreshClipResults();

  };

  const pollClipProgress=async()=>{
    if(!progressWatching || progressRequest || node.__mmxDisposed)return;
    progressRequest=true;
    try {
      const response=await api.fetchApi('/minimax_director/progress?'+new URLSearchParams({node:String(node.id),project_id:timelineState.project_id}),{cache:'no-store'});
      const result=await response.json();
      if(response.ok && progressWatching && !node.__mmxDisposed){
        if(result.active===false){if(generatingClipId!==null){generatingClipId=null;progressLabel.textContent='Idle';renderTimeline();void refreshClipResults();}return;}
        const needsRestore=result.state && generatingClipId!==result.state.clip_id && ['preparing','sampling','refining','decoding','face_refining'].includes(result.state.phase);
        if(result.state && (Number(result.state.sequence)>progressSequence || needsRestore))node.__mmxShotHandler?.({detail:result.state,snapshot:true});
      }
    } catch {} finally {progressRequest=false;}
  };
  const watchClipProgress=()=>{progressWatching=true;if(progressTimer===null)progressTimer=setInterval(pollClipProgress,2000);};
  const stopClipProgress=()=>{progressWatching=false;if(progressTimer!==null)clearInterval(progressTimer);progressTimer=null;};

  // Backend updates only the clip actually completed; clip-by-clip and selection
  // do not advance unrelated clip seeds.
  node.__mmxShotHandler = event => {
    const detail = event.detail;
    if (!detail || String(detail.node).split(':').at(-1) !== String(node.id) || detail.project_id !== timelineState.project_id) return;
    if(detail.sequence){if(Number(detail.sequence)<progressSequence || (Number(detail.sequence)===progressSequence && !event.snapshot))return;progressSequence=Number(detail.sequence);}
    const runningPhase=['preparing','sampling','refining','decoding','face_refining'].includes(detail.phase);
    if(runningPhase)watchClipProgress();
    if(detail.stale_clip_ids?.length){
      // The upstream clip's new take is saved. These clips continue from it,
      // so they regenerate next; their own saved takes stay until replaced.
      const invalidated=new Set(detail.stale_clip_ids);
      for(const clip of timelineState.clips){
        if(!invalidated.has(String(clip.id)))continue;
        // Only takes kept "until the upstream clip is saved" lose approval here;
        // a firmly approved take is a boundary and is never listed.
        if(clip.validated && clip.pending_upstream){clip.validated=false;delete clip.validated_generation;delete clip.pending_upstream;}
        if(!clip.validated){clip.refine_approved=false;clip.refine_pending=false;}
      }
      syncState(true);void refreshClipResults();
    }
    // The upstream take was replaced; anything still waiting on it was kept.
    if(detail.phase==='completed' && !detail.reused && detail.saved===true){
      let kept=false;
      for(const clip of timelineState.clips)if(clip.pending_upstream===detail.clip_id){delete clip.pending_upstream;kept=true;}
      if(kept){syncState(true);renderTimeline();}
    }
    if(detail.phase==='first_pass_ready') {const clip=timelineState.clips.find(c=>c.id===detail.clip_id);if(clip)clip.refine_pending=true;generatingClipId=null;progressLabel.textContent='First Pass Ready · Review And Approve';syncState(true);void refreshClipResults();renderTimeline();renderInspector();return;}
    if(detail.phase==='timeline_ready') { timelineState={...timelineState,...detail.timeline};syncState(true);renderTimeline();renderInspector();return; }
    const eventClip=timelineState.clips.find(value=>value.id===detail.clip_id);
    const phaseLabel=({preparing:'Preparing',sampling:'Generating',refining:'Refining',decoding:'Decoding',face_refining:'Refining Faces',completed:'Completed',source_ready:'Source Ready'})[detail.phase] || detail.phase;
    progressLabel.textContent = `${phaseLabel}: ${eventClip?.name || 'Clip '+(timelineState.clips.indexOf(eventClip)+1)}${detail.index ? ` (${detail.index}/${detail.total || timelineState.clips.length})` : ''}`;
    if(runningPhase) {const previous=generatingClipId;generatingClipId=detail.clip_id;generatingPhase=detail.phase;renderTimeline();if(previous!==null && previous!==detail.clip_id)void refreshClipResults();}
    if(detail.phase==='completed' && generatingClipId===detail.clip_id){generatingClipId=null;renderTimeline();}
    if(detail.phase==='source_ready') {
      const clip=timelineState.clips.find(value=>value.id===detail.clip_id);
      if(clip?.source?.ref_id===detail.ref_id && Number(clip.source_start || 0)===Number(detail.requested_start || 0) && (clip.source_end ?? null)===(detail.requested_end ?? null)) {
        clip.source_end=detail.end;clip.duration=detail.duration;syncState(true);renderTimeline();
      }
    }
    if (detail.phase === "completed") {
      void refreshClipResults();

      const clip = timelineState.clips.find(value => value.id === detail.clip_id);
      if (clip) {
        clip.refine_pending=false;clip.refine_approved=false;
        clip.last_seed = detail.seed;
        if (String(clip.seed ?? detail.authored_seed) === detail.authored_seed) clip.seed = detail.next_seed;
        syncState(true); renderInspector();
      }
    }
  };
  if (!node.__mmxShotListener) {
    const cacheUpdates=event=>{
      const detail=event.detail,report=detail?.cache_report;
      if(!report || String(detail.node).split(':').at(-1)!==String(node.id) || detail.project_id!==timelineState.project_id)return;
      const clip=timelineState.clips.find(row=>String(row.id)===String(detail.clip_id));
      if(!clip || clip.cache_report?.run_id===report.run_id && clip.cache_report?.revision===report.revision)return;
      clip.cache_report=report;syncState(true);renderTimeline();
    };
    api.addEventListener('minimax_director/stage',cacheUpdates);
    node.__mmxShotListener = event => node.__mmxShotHandler?.(event);
    api.addEventListener("minimax_director/shot", node.__mmxShotListener);
    const clearGenerating=event=>{
      const executingNode=typeof event.detail==='object'?event.detail?.node:event.detail;
      if(event.type==='executing' && String(executingNode)===String(node.id)){watchClipProgress();void pollClipProgress();return;}
      // ComfyUI emits executing.detail as a node ID, not a {node} object.
      // Only the terminal null event should clear the clip indicator.
      if(event?.type==='executing' && (typeof event.detail==='object' ? event.detail?.node : event.detail)!=null)return;
      if(event?.type==='execution_error' && event.detail?.node_id && String(event.detail.node_id)!==String(node.id))return;
      generatingClipId=null;renderTimeline();
    };
    for(const name of ['execution_error','execution_interrupted','executing'])api.addEventListener(name,clearGenerating);
    const removed = node.onRemoved;
    node.onRemoved = function (...args) {
      node.__mmxDisposed = true;node.__mmxExportController?.abort();stopClipProgress();
      flushDraft();window.removeEventListener('pagehide',flushDraft);document.removeEventListener('visibilitychange',hideDraft);
      for (const observers of node.__mmxRefObserverSets || []) observers.delete(node.__mmxRefObserver);
      node.__mmxRefObserverSets?.clear();
      cancelTimelineDrag?.();
      node.__mmxProjectDialog?.remove();
      node.__mmxCacheDialog?.remove();api.removeEventListener('minimax_director/stage',cacheUpdates);

          api.removeEventListener("minimax_director/shot", node.__mmxShotListener);
      for(const name of ['execution_error','execution_interrupted','executing'])api.removeEventListener(name,clearGenerating);
      node.__mmxShotHandler = null; node.__mmxShotListener = null;
      return removed?.apply(this, args);
    };
  }
  // Mounting/reconnecting mid-run must not depend on receiving the start event.
  watchClipProgress();void pollClipProgress();

}

// Dynamic RefPack widget visibility: hide unconnected label text boxes to avoid canvas clutter
// Dynamic RefPack widget visibility (no-op as label text boxes have been removed)
const updateRefPackWidgets = (node) => {};

// The Settings node is retired: its canvas, sampler and output values move into
// the Master's timeline "settings", a linked steps input moves to the Master's
// own steps socket, and the Settings node and its link are removed.
function retireSettingsNodes(graphData) {
  const nodes=graphData?.nodes || [], links=graphData?.links || [];
  const linkId=row=>Array.isArray(row)?row[0]:row.id;
  const origin=row=>Array.isArray(row)?row[1]:row.origin_id;
  const findLink=value=>links.find(row=>linkId(row)===value);
  const positional=["width","height","frame_rate","steps","cfg","sampler","scheduler","shift_video","shift_audio","canvas_policy","canvas_megapixels","canvas_aspect","decoded_output"];
  const removeLink=value=>{const row=findLink(value);if(!row)return;links.splice(links.indexOf(row),1);
    for(const n of nodes)for(const out of n.outputs || [])if(out.links)out.links=out.links.filter(id=>id!==value);};
  for(const settings of nodes.filter(n=>n.type==="MiniMaxH3DirectorSettings")){
    const values={...Object.fromEntries(positional.map((key,index)=>[key,settings.widgets_values?.[index]])),...(settings.widgets_values_named || {})};
    const outLinks=new Set(settings.outputs?.[0]?.links || []);
    const stepsLink=settings.inputs?.find(input=>input.name==="steps")?.link;
    for(const master of nodes.filter(n=>["MiniMaxH3MasterNode","MiniMaxH3MasterDirector"].includes(n.type))){
      const configInput=master.inputs?.find(input=>input.name==="config");
      if(!configInput || !outLinks.has(configInput.link))continue;
      try{
        const raw=master.widgets_values_named?.timeline_data ?? master.widgets_values?.find(value=>typeof value==="string" && value.trim().startsWith("{") && value.includes("\"clips\""));
        if(typeof raw==="string"){
          const state=JSON.parse(raw);
          if(!state.settings){
            const width=Number(values.width) || 1344,height=Number(values.height) || 768;
            state.settings={resolution:{mode:values.canvas_policy || "manual",width,height,megapixels:Number(values.canvas_megapixels) || 1,aspect:values.canvas_aspect || "16:9"},
              width,height,sampler:values.sampler || "res_multistep",cfg:Number(values.cfg ?? 1),steps:Number(values.steps) || 25,scheduler:values.scheduler || "simple",
              decoded_output:values.decoded_output || "latest"};
            const serialized=JSON.stringify(state);
            if(master.widgets_values){const index=master.widgets_values.indexOf(raw);if(index>=0)master.widgets_values[index]=serialized;}
            (master.widgets_values_named ||= {}).timeline_data=serialized;
          }
        }
      }catch(error){console.warn("[DirectorUI] Could not move Settings values into the Master node",error);}
      removeLink(configInput.link);
      master.inputs=master.inputs.filter(input=>input!==configInput);
      if(stepsLink!=null && findLink(stepsLink) && !master.inputs.some(input=>input.name==="steps" && input.link!=null)){
        const row=findLink(stepsLink);
        let stepsInput=master.inputs.find(input=>input.name==="steps");
        if(!stepsInput){stepsInput={name:"steps",type:"INT",link:null};master.inputs.push(stepsInput);}
        stepsInput.link=linkId(row);
        if(Array.isArray(row)){row[3]=master.id;}else{row.target_id=master.id;}
      }
      master.inputs.forEach((input,index)=>{const row=input.link!=null?findLink(input.link):null;if(row){if(Array.isArray(row))row[4]=index;else row.target_slot=index;}});
    }
    for(const input of settings.inputs || [])if(input.link!=null && input.link!==stepsLink)removeLink(input.link);
    if(stepsLink!=null){const row=findLink(stepsLink);if(row && (Array.isArray(row)?row[3]:row.target_id)===settings.id)removeLink(stepsLink);}
    for(const id of outLinks)removeLink(id);
    nodes.splice(nodes.indexOf(settings),1);
  }
}

function migrateMasterSockets(graphData) {
  const links=graphData.links || [];
  const id=row=>Array.isArray(row)?row[0]:row.id;
  const find=value=>links.find(row=>id(row)===value);
  let nextId=Math.max(Number(graphData.last_link_id)||0,...links.map(row=>Number(id(row))||0));
  for(const node of graphData.nodes || []) {
    if(!["MiniMaxH3MasterNode","MiniMaxH3MasterDirector"].includes(node.type) || !Array.isArray(node.inputs))continue;
    const generic=node.inputs.find(input=>input.name==="model"), oldLink=generic?.link!=null?find(generic.link):null;
    if(oldLink) {
      const families=["fl2va_model","ref2va_model"].map(name=>node.inputs.find(input=>input.name===name)).filter(input=>input && input.link==null);
      families.forEach((input,index)=>{
        const row=index===0?oldLink:(Array.isArray(oldLink)?[...oldLink]:{...oldLink,id:++nextId});
        if(index && Array.isArray(row))row[0]=++nextId;
        if(index){links.push(row);const sourceId=Array.isArray(row)?row[1]:row.origin_id, sourceSlot=Array.isArray(row)?row[2]:row.origin_slot;
          const output=graphData.nodes.find(source=>source.id===sourceId)?.outputs?.[sourceSlot];if(output)(output.links ||= []).push(id(row));}
        input.link=id(row);
      });
      if(!families.length){const index=links.indexOf(oldLink);links.splice(index,1);
        const sourceId=Array.isArray(oldLink)?oldLink[1]:oldLink.origin_id, sourceSlot=Array.isArray(oldLink)?oldLink[2]:oldLink.origin_slot;
        const output=graphData.nodes.find(source=>source.id===sourceId)?.outputs?.[sourceSlot];if(output)output.links=(output.links || []).filter(value=>value!==id(oldLink));}
    }
    node.inputs=node.inputs.filter(input=>{
      if(input.name==="model")return false;
      if(["i2v_groups","r2v_groups","prompt_text"].includes(input.name)){
        if(input.link==null)return false;
        input.label="Legacy " + input.name;
        return true; // Keep connected legacy graphs functional; never discard linked authored data.
      }
      if(input.name==="continuation")input.name="latent_checkpoint";
      return true;
    });
    node.inputs.forEach((input,index)=>{const row=input.link!=null?find(input.link):null;if(row){if(Array.isArray(row)){row[3]=node.id;row[4]=index;}else{row.target_id=node.id;row.target_slot=index;}}});
  }
  graphData.last_link_id=nextId;
}

app.registerExtension({
  name: "ComfyUI.MiniMaxH3MasterDirector",
  init: () => console.log("[DirectorUI] Extension initialized"),

  beforeConfigureGraph(graphData) {
    migrateMasterSockets(graphData);
    // Upgrade saved UI workflows before ComfyUI resolves node types.
    for (const node of graphData?.nodes || []) {
      if (node.type === "MiniMaxH3MasterDirector") node.type = "MiniMaxH3MasterNode";
      // Earlier examples omitted ComfyUI's workflow-only seed control.
      // Preserve the seed and all subsequent Settings fields during import.
      if (node.type === "MiniMaxH3DirectorSettings" && Array.isArray(node.widgets_values)) {
        const base = ["width","height","frame_rate","steps","cfg","sampler","scheduler","shift_video","shift_audio","seed"];
        const current = [...base,"control_after_generate","generation_mode","continuity_mode","context_length"];
        const legacy = [...base,"control_after_generate","execution_mode","prompt_mode","run_mode","continuity_mode","context_length","preview_mode"];
        const sampling = [...base,"control_after_generate"];
        const count = node.widgets_values.length;
        // Seed-free Settings already use the new positional layout.
        if (["manual","original","auto"].includes(node.widgets_values[9])) continue;
        if (["manual","original","auto"].includes(node.widgets_values[11])) {
          const fields=[...sampling,'canvas_policy','canvas_megapixels','canvas_aspect','decoded_output'];
          node.widgets_values_named={...Object.fromEntries(fields.slice(0,count).map((key,index)=>[key,node.widgets_values[index]])),...node.widgets_values_named};
          continue;
        }
        const fields = count === 17 ? legacy : count === 16 ? legacy.filter(key=>key!=="control_after_generate")
          : count === 14 ? current : count === 13 ? current.filter(key=>key!=="control_after_generate") : count === 11 ? sampling : null;
        if (fields) {
          const values = Object.fromEntries(fields.map((key,index)=>[key,node.widgets_values[index]]));
          Object.assign(values,node.widgets_values_named || {});
          values.control_after_generate ||= "fixed";
          if (!["Next shot","All shots","Conditioning only"].includes(values.generation_mode)) {
            values.generation_mode = values.execution_mode === "Conditioning Guide Output" ? "Conditioning only"
              : values.run_mode === "full_batch" ? "All shots" : "Next shot";
          }
          node.widgets_values = sampling.map(key=>values[key]);
          node.widgets_values_named = values;
        }
      }
      if (node.type === "MiniMaxH3VideoCombine" && Array.isArray(node.widgets_values)) {
        const current = ["frame_rate","codec","container","encoder_backend","bit_depth","quality",
          "pingpong","save_metadata","filename_prefix","save_output","crop_to_audio",
          "audio_codec","audio_bitrate","save_first_frame","save_last_frame"];
        const legacy = [...current];legacy.splice(6,0,"log_level");legacy.splice(11,0,"pass_frames");
        if(node.widgets_values.length >= 16 && !node.widgets_values_named
            && !["pyav","ffmpeg"].includes(node.widgets_values[3])) {
          // The original exporter used FFmpeg and had no backend widget.
          node.widgets_values.splice(3,0,"ffmpeg");
        }
        const fields=node.widgets_values.length >= 17 ? legacy : current;
        const values=Object.fromEntries(fields.map((name,index)=>[name,node.widgets_values[index]]));
        Object.assign(values,node.widgets_values_named || {});
        delete values.log_level;delete values.pass_frames;delete values.video_preview;
        node.widgets_values=current.map(name=>values[name]);
        node.widgets_values_named=values;
      }
    }
    // Transfer retired global controls into the connected Master's authoring state.
    for (const master of graphData?.nodes || []) if (["MiniMaxH3MasterDirector","MiniMaxH3MasterNode"].includes(master.type)) {
      const configLink=master.inputs?.find(input=>input.name==='config')?.link;
      const link=graphData.links?.find(row=>(Array.isArray(row)?row[0]:row.id)===configLink);
      const origin=Array.isArray(link)?link[1]:link?.origin_id;
      const configNode=graphData.nodes.find(row=>row.id===origin);
      const old=configNode?.widgets_values_named || {};
      try {
        const raw=master.widgets_values_named?.timeline_data ?? master.widgets_values?.find(value=>typeof value==="string" && value.trim().startsWith("{") && value.includes("\"clips\""));
        if (typeof raw!=='string') continue;
        const state=JSON.parse(raw);
        state.generation_mode ||= old.generation_mode || 'Next shot';
        if (state.resolution && configNode && !configNode.widgets_values_named?.canvas_policy) {
          const resolution=state.resolution;
          (configNode.widgets_values_named ||= {}).canvas_policy=resolution.mode || 'manual';
          configNode.widgets_values_named.canvas_megapixels=resolution.megapixels ?? 1;
          configNode.widgets_values_named.canvas_aspect=resolution.aspect || '16:9';
          if(resolution.mode==='manual')for(const [index,key] of [[0,'width'],[1,'height']]){
            if(resolution[key]!=null){configNode.widgets_values_named[key]=resolution[key];configNode.widgets_values[index]=resolution[key];}
          }
          configNode.widgets_values=[...configNode.widgets_values.slice(0,11),resolution.mode || 'manual',resolution.megapixels ?? 1,resolution.aspect || '16:9'];
          delete state.resolution;
        }
        for (const [index,clip] of (state.clips || []).entries()) {
          if(clip.seed==null && old.seed!=null)clip.seed=String(BigInt.asUintN(64,BigInt(old.seed)+BigInt(index)*1000n));
          clip.continuity_mode ||= clip.continuity===false?'Independent (No Continuity)':old.continuity_mode || 'Independent (No Continuity)';
          clip.context_length ??= Number(old.context_length || 22);
          clip.audio_context_length ??= clip.context_length;
          clip.selected ??= false;
        }
        const serialized=JSON.stringify(state);
        if (master.widgets_values) {const index=master.widgets_values.indexOf(raw);if(index>=0)master.widgets_values[index]=serialized;}
        (master.widgets_values_named ||= {}).timeline_data=serialized;
        master.widgets_values_named.generation_mode ||= ({"Next shot":"Next clip","All shots":"All clips"})[state.generation_mode] || state.generation_mode;
      } catch (error) { console.warn('[DirectorUI] Could not migrate timeline controls',error); }
    }
    retireSettingsNodes(graphData);
    // Retired global seed and its workflow-only randomization widget must not
    // shift canvas/output fields when saved workflows load into seed-free Settings.
    for(const node of graphData?.nodes || [])if(node.type==='MiniMaxH3DirectorSettings' && Array.isArray(node.widgets_values)){
      const values=node.widgets_values;
      if(typeof values[9]==='number' || typeof values[9]==='string' && /^\d+$/.test(values[9])){
        values.splice(9,['fixed','randomize','increment','decrement'].includes(values[10])?2:1);
      }
    }
  },

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name.startsWith("MiniMaxH3")) {
      // Persist values by name as well as LiteGraph's positional array. Adding
      // a widget must not shift existing values into unrelated input fields.
      const serialize = nodeType.prototype.onSerialize;
      nodeType.prototype.onSerialize = function (data) {
        serialize?.apply(this, arguments);
        data.widgets_values_named = {};
        for (const widget of this.widgets || []) {
          if (widget.serialize === false || !widget.name) continue;
          if (["string", "number", "boolean"].includes(typeof widget.value)) {
            data.widgets_values_named[widget.name] = widget.value;
          }
        }
      };
      const configure = nodeType.prototype.onConfigure;
      nodeType.prototype.onConfigure = function (info) {
        configure?.apply(this, arguments);
        for (const widget of this.widgets || []) {
          if (widget.serialize === false) continue;
          if (Object.hasOwn(info?.widgets_values_named || {}, widget.name)) {
            widget.value = info.widgets_values_named[widget.name];
          }
        }
      };
    }
    if (["MiniMaxH3VideoCombine", "MiniMaxH3ProjectVideo"].includes(nodeData.name)) {
      const removed=nodeType.prototype.onRemoved;
      nodeType.prototype.onRemoved=function(){
        this.__mmxVideoDownload?.abort();
        for(const video of this.__mmxVideoElement?.querySelectorAll("video") || []) {video.pause();video.removeAttribute("src");video.load();}
        return removed?.apply(this,arguments);
      };
      const executed = nodeType.prototype.onExecuted;
      nodeType.prototype.onExecuted = function (message) {
        executed?.apply(this, arguments);
        if (!Array.isArray(message?.video)) return;
        if (!this.__mmxVideoElement) {
          const element = document.createElement("div");
          element.style.cssText="width:100%;height:100%;min-height:0;display:flex;flex-direction:column;gap:8px;overflow:auto";
          this.__mmxVideoElement = element;
          const node=this;
          const widget=this.addDOMWidget("video_preview", "MMX_VIDEO_PREVIEW", element, {
            serialize:false,hideOnZoom:false,getMinHeight:()=>220,
            getHeight:()=>Math.max(220,(node.size?.[1] || 0)-(node.__mmxVideoWidget?.last_y || 0)-16),
          });
          this.__mmxVideoWidget=widget;
          widget.serialize=false;
          widget.computeSize=width=>[width,220];
        }
        this.__mmxVideoDownload?.abort();
        for(const video of this.__mmxVideoElement.querySelectorAll("video")) {video.pause();video.removeAttribute("src");video.load();}
        this.__mmxVideoElement.replaceChildren();
        for (const item of message.video) {
          const row=document.createElement("div");
          row.style.cssText="display:flex;flex-direction:column;flex:1 0 200px;min-height:200px;gap:6px";
          const video = document.createElement("video"); video.controls = true; video.preload = "auto";
          video.style.cssText = "width:100%;height:0;min-height:160px;flex:1 1 auto;object-fit:contain;background:#111";
          const query=new URLSearchParams({filename:item.filename,subfolder:item.subfolder || "",type:item.type || "output"});
          const source=`/view?${query}`;
          video.src = api.apiURL(source);
          video.onerror = () => {
            if (video.dataset.fallback) return;
            video.dataset.fallback = "1";
            video.src = api.apiURL(`/minimax_director/video/preview?${query}`);
          };
          const download=document.createElement("button");download.type="button";download.textContent="Download video";
          download.style.cssText="align-self:flex-end;flex-shrink:0;padding:6px 12px;cursor:pointer";
          download.onclick=async()=>{
            download.disabled=true;download.textContent="Downloading…";
            const controller=new AbortController();this.__mmxVideoDownload?.abort();this.__mmxVideoDownload=controller;
            let url;
            try {
              const response=await api.fetchApi(source,{signal:controller.signal});
              if(!response.ok)throw Error(`HTTP ${response.status}`);
              const blob=await response.blob();
              if(controller.signal.aborted)return;
              url=URL.createObjectURL(blob);
              const link=document.createElement("a");link.href=url;link.download=item.filename;
              document.body.append(link);link.click();link.remove();
              const completed=url;setTimeout(()=>URL.revokeObjectURL(completed),60000);url=null;
              download.textContent="Download video";
            } catch(error) {
              download.textContent=controller.signal.aborted?"Download video":"Download failed — retry";
              download.title=error.message;
            } finally {if(url)URL.revokeObjectURL(url);download.disabled=false;}
          };
          row.append(video,download);this.__mmxVideoElement.append(row);
        }
        this.setDirtyCanvas(true,true);
      };
      return;
    }
    if (nodeData.name === "MiniMaxH3RefPack") {
      const onNodeCreated = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function () {
        if (onNodeCreated) onNodeCreated.apply(this, arguments);
        updateRefPackWidgets(this);
      };

      const onConnectionsChange = nodeType.prototype.onConnectionsChange;
      nodeType.prototype.onConnectionsChange = function () {
        if (onConnectionsChange) onConnectionsChange.apply(this, arguments);
        updateRefPackWidgets(this);
        if (app.graph && Array.isArray(app.graph._nodes)) {
          app.graph._nodes.forEach((n) => {
            if (n && (n.comfyClass === "MiniMaxH3MasterDirector" || n.type === "MiniMaxH3MasterDirector" || n.comfyClass === "MiniMaxH3MasterNode" || n.type === "MiniMaxH3MasterNode")) {
              if (n.__mmxDirectorRefresh) {
                setTimeout(() => n.__mmxDirectorRefresh(), 50);
              }
            }
          });
        }
      };

      const onConfigure = nodeType.prototype.onConfigure;
      nodeType.prototype.onConfigure = function () {
        if (onConfigure) onConfigure.apply(this, arguments);
        updateRefPackWidgets(this);
      };
      return;
    }

    if (nodeData.name !== "MiniMaxH3MasterDirector" && nodeData.name !== "MiniMaxH3MasterNode") return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      if (onNodeCreated) onNodeCreated.apply(this, arguments);
      mountDirectorUI(this);
    };

    const onConnectionsChange = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
      if (onConnectionsChange) onConnectionsChange.apply(this, arguments);
      if (this.__mmxDirectorRefresh) {
        this.__mmxDirectorRefresh();
      }
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (info) {
      if (onConfigure) onConfigure.apply(this, arguments);

      // Protect against any array-shift during deserialization
      if (info && this.widgets) {
        const named = info.widgets_values_named || {};
        const values = Array.isArray(info.widgets_values) ? info.widgets_values : [];

        // Robust deserialization supporting both new streamlined format and legacy workflows
        if (named["timeline_data"] !== undefined) {
          const w = this.widgets.find((x) => x.name === "timeline_data");
          if (w) w.value = named["timeline_data"];
        } else {
          const serialized=values.find(value=>typeof value==="string" && value.trim().startsWith("{") && (()=>{try{return Array.isArray(JSON.parse(value).clips);}catch{return false;}})());
          const w=this.widgets.find(x=>x.name==="timeline_data");if(w && serialized)w.value=serialized;
          const builder=this.widgets.find(x=>x.name==="builder_state");
          if(builder && serialized){const index=values.indexOf(serialized);builder.value=values[index+1] || "{}";}
        }
        const generation=this.widgets.find(x=>x.name==="generation_mode");
        if(generation){
          const timeline=this.widgets.find(x=>x.name==="timeline_data");
          let state={};try{state=JSON.parse(timeline?.value || "{}");}catch{}
          generation.value=({"Next shot":"Next clip","All shots":"All clips"})[named.generation_mode || state.generation_mode] || named.generation_mode || state.generation_mode || "Next clip";
          state.generation_mode=generation.value;if(timeline)timeline.value=JSON.stringify(state);
        }

        if (named["builder_state"] !== undefined) {
          const w = this.widgets.find((x) => x.name === "builder_state");
          if (w) w.value = named["builder_state"];
        }
      }

      // Ensure widgets are ready before mounting UI
      if (this.widgets && this.widgets.length > 0) {
        if (this.__mmxDirectorRefresh) {
          this.__mmxDirectorRefresh();
        } else {
          mountDirectorUI(this);
        }
      } else {
        // Fallback: retry if widgets not ready
        setTimeout(() => this.onConfigure(info), 100);
      }
    };
  },

  nodeCreated(node) {
    if (node.comfyClass === "MiniMaxH3MasterDirector" || node.type === "MiniMaxH3MasterDirector" || node.comfyClass === "MiniMaxH3MasterNode" || node.type === "MiniMaxH3MasterNode") {
      mountDirectorUI(node);
    } else if (node.comfyClass === "MiniMaxH3RefPack" || node.type === "MiniMaxH3RefPack") {
      updateRefPackWidgets(node);
    }
  },

  loadedGraphNode(node) {
    if (node.comfyClass === "MiniMaxH3MasterDirector" || node.type === "MiniMaxH3MasterDirector" || node.comfyClass === "MiniMaxH3MasterNode" || node.type === "MiniMaxH3MasterNode") {
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
    } else if (node.comfyClass === "MiniMaxH3RefPack" || node.type === "MiniMaxH3RefPack") {
      updateRefPackWidgets(node);
    }
  },
});
