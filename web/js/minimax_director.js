import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { bindShotDrag } from "./minimax_timeline.js";
import {transferRequest,transferLabel} from "./minimax_transfer.js";

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
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
  height: 44px;
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
  height: 42px;
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
.mmx-director-root .mmx-img-block, .mmx-director-root .mmx-vid-block, .mmx-director-root .mmx-aud-block { height: 34px; }

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
.mmx-director-root .mmx-img-block { height:52px; }
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
.mmx-director-root .mmx-track-header-cell { background:transparent;color:#bfcbd8;font-size:12px;letter-spacing:.02em; }
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
.mmx-director-root .mmx-edit-workspace { display:grid;grid-template-columns:minmax(0,1fr) 350px;gap:18px;align-items:start; }
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
.mmx-director-root .mmx-project-workspace .mmx-project-actions { grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;padding:0;border:0; }
.mmx-director-root .mmx-project-workspace .mmx-project-actions > .mmx-field { padding:0;border:0;background:transparent;justify-content:flex-start; }
.mmx-director-root .mmx-project-workspace .mmx-project-actions button { display:flex;align-items:center;justify-content:center;text-align:center;width:100%;box-sizing:border-box;min-height:40px; }
.mmx-director-root .mmx-project-workspace button.mmx-project-danger { background:#3b2329;border-color:#bf5967;color:#ffd0d6;box-shadow:0 0 12px #e45c6d2b,inset 0 0 10px #e45c6d0d; }
.mmx-director-root .mmx-project-workspace button.mmx-project-danger:hover { background:#512932;border-color:#f0808d;box-shadow:0 0 16px #e45c6d55; }
.mmx-director-root .mmx-project-workspace small { display:none; }
.mmx-director-root .mmx-project-workspace .mmx-export-control { display:flex;align-items:stretch;min-height:40px;border:1px solid #596979;border-radius:5px;background:#344353;overflow:hidden; }
.mmx-director-root .mmx-project-workspace .mmx-export-control button { flex:1;min-width:0;border:0;border-radius:0;background:transparent; }
.mmx-director-root .mmx-project-workspace .mmx-export-control button:hover { background:#405267; }
.mmx-director-root .mmx-project-workspace .mmx-export-options { display:flex;flex-direction:row;align-items:center;justify-content:center;gap:7px;margin:0;padding:0 10px;border:0;border-left:1px solid #596979;border-radius:0;background:transparent;font-size:12px;white-space:nowrap;cursor:pointer; }
.mmx-director-root .mmx-project-workspace .mmx-export-options input { margin:0;flex-shrink:0; }
.mmx-director-root .mmx-project-workspace .mmx-section-intro { display:none; }
.mmx-director-root .mmx-project-workspace .mmx-section > summary { padding:12px 0 0; }
.mmx-director-root .mmx-project-library { display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:0;border:0; }
.mmx-director-root .mmx-project-library .mmx-project-name-field { display:flex;flex-direction:row;align-items:center;gap:12px;flex:1;min-width:260px;padding:0;border:0;background:transparent; }
.mmx-director-root .mmx-project-name-field input { flex:1;min-width:120px; }
.mmx-director-root .mmx-project-library button { min-height:40px;padding:0 18px; }
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
.mmx-director-root .mmx-project-actions button.mmx-project-danger:hover:not(:disabled) { background:#512932;border-color:#f0808d;box-shadow:0 0 16px #e45c6d55; }
.mmx-director-root .mmx-project-feedback { flex-basis:100%;padding:9px 12px;border:1px solid #596979;border-radius:5px;background:#1d2833;color:#c9e5fa;font-size:13px; }
.mmx-director-root .mmx-project-feedback:empty { display:none; }
.mmx-director-root .mmx-project-feedback[data-state="success"] { color:#b6edcb;border-color:#4e9270;background:#20382c; }
.mmx-director-root .mmx-project-feedback[data-state="error"], .mmx-server-project-note[data-state="error"] { color:#ffb9c2;border-color:#b95f6c; }
.mmx-director-root .mmx-server-project-status { flex-basis:100%;font-size:12px;color:#9fb5c7; }
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
@container (max-width:800px) { .mmx-director-root .mmx-project-workspace > .mmx-section-body { grid-template-columns:1fr; } .mmx-director-root .mmx-project-group + .mmx-project-group { border-left:0;border-top:1px solid #414e5a;padding:14px 0 0; } .mmx-director-root .mmx-project-workspace .mmx-project-actions { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@container (max-width:600px) { .mmx-project-workspace > summary span { display:none; } }

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
  let progressSequence=0,progressTimer=null,progressWatching=false,progressRequest=false;
  let cachedClipResults={},cacheStatusProject=null,cacheStatusRequest=0;
  let serverStatus=null, savedProjectSignature=null;
  const projectSignature=()=>JSON.stringify({timeline:{...timelineState,server_revision:undefined},builder:builderState});
  const updateServerStatus=()=>{
    if(serverStatus)serverStatus.textContent=savedProjectSignature && savedProjectSignature===projectSignature()
      ? "Saved On Server" : timelineState.server_revision ? "Server Project · Save Your Changes" : "Not Saved On Server";
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
        for (const [slot, type, short] of [["image_1","image","img_1"],["image_2","image","img_2"],["image_3","image","img_3"],["image_4","image","img_4"],["video_1","video","vid_1"],["video_2","video","vid_2"],["audio_1","audio","aud_1"],["audio_2","audio","aud_2"]]) {
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

  let generationBaseline = null;
  const loadState = () => {
    generationBaseline = null;
    resolveAvailableRefsFromGraph();
    try {
      if (timelineWidget && timelineWidget.value) {
        const parsed = typeof timelineWidget.value === "string" ? JSON.parse(timelineWidget.value) : timelineWidget.value;
        if (parsed && typeof parsed === "object") {
          timelineState = { ...timelineState, ...parsed };
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
    // All generation edits pass through this boundary. Runtime notifications
    // explicitly accept their own seed/source updates without rejecting takes.
    const keys = ['type','duration','prompt','prompt_mode','structured_prompt','ref_ids',
      'continuity','continuity_mode','context_length','audio_context_length','continuity_redraw','continuity_duration_policy',
      'tail_seconds','tail_frames','seed','seed_mode','audio_mode','model_override','guides',
      'loras','color','source','source_start','source_end','group'];
    const shared = JSON.stringify([timelineState.shared_prompt || '', timelineState.shared_prompt_policy || 'prepend', timelineState.shared_ref_ids || [], builderState]);
    const current = {project:timelineState.project_id, shared, clips:new Map(timelineState.clips.map(c=>[c.id,JSON.stringify(keys.map(k=>c[k]))]))};
    let approvalsChanged=false;
    if (!acceptRuntime && generationBaseline?.project === current.project) {
      const allChanged = generationBaseline.shared !== shared;
      for (const clip of timelineState.clips) {
        if (allChanged || generationBaseline.clips.has(clip.id) && generationBaseline.clips.get(clip.id) !== current.clips.get(clip.id)) {unapproveChain(clip);approvalsChanged=true;}
      }
    }
    generationBaseline = current;
    if (timelineWidget) timelineWidget.value = JSON.stringify(timelineState);
    if (builderWidget) builderWidget.value = JSON.stringify(builderState);
    updateServerStatus();
    if (approvalsChanged) renderTimeline();
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
    if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
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
  const includeMedia=document.createElement("input");includeMedia.type="checkbox";includeMedia.checked=true;
  includeMedia.className="mmx-export-media";
  exportBtn.onclick = async () => {
    if(exportBtn.disabled)return;
    exportBtn.disabled=true;exportBtn.textContent='Exporting…';exportBtn.setAttribute('aria-busy','true');
    showProjectFeedback('busy','Preparing Project Download…');
    try {
      if(includeMedia.checked){await exportPortable();showProjectFeedback('success','Project Download Prepared With Source And Reference Media. Generated Results Stay On Server.');return;}
      const res = await api.fetchApi("/minimax_director/project/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: timelineState.project_id || String(node.id ?? "default_director"),
          timeline: { ...timelineState, builder_state: builderWidget?.value || "{}" },
          name: timelineState.project_name || "MiniMaxProject",
        }),
      });
      const data = await res.json();
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
      showProjectFeedback('error',`Export Failed: ${err.message}`);
    } finally { exportBtn.disabled=false;exportBtn.textContent='Export Project';exportBtn.removeAttribute('aria-busy'); }
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
      const policy = prompt("Import policy: append or overwrite", "overwrite");
      if(!policy){showProjectFeedback('idle','Import Cancelled.');return;}
      if(!['append','overwrite'].includes(policy)){showProjectFeedback('error','Import Policy Must Be append Or overwrite.');return;}
      importBtn.disabled=true;importBtn.textContent='Importing…';importBtn.setAttribute('aria-busy','true');
      showProjectFeedback('busy','Importing Project…');
      try {
        if(!file.name.toLowerCase().endsWith(".json")){await importPortable(file,policy);showProjectFeedback('success','Project Imported With Media. Generated Results Are Not Included In Portable Archives.');return;}
        const text = await file.text();
        const projectData = JSON.parse(text);
        const res = await api.fetchApi("/minimax_director/project/import", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project: projectData }),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) throw new Error(data.error || "Project import failed");
        if (data.ok && data.timeline) {
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


  const progressLabel = document.createElement("span"); progressLabel.style.fontSize = "11px"; toolbarLeft.appendChild(progressLabel);
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
      const actions=document.createElement("div");actions.className="mmx-project-actions";
      const actionOrder=["new","import","export","restore","reset","delete-results"];
      const buttons=[...body.children].filter(child=>child.tagName==='BUTTON').sort((a,b)=>actionOrder.indexOf(a.dataset.projectAction)-actionOrder.indexOf(b.dataset.projectAction));
      for (const button of buttons) {
        const card=document.createElement("div");card.className="mmx-field";
        const help=document.createElement("small");help.textContent=button.title || "Clear the current timeline after confirmation.";
        card.append(button,help);actions.append(card);
        if(button===exportBtn){
          const exportControl=document.createElement('div');exportControl.className='mmx-export-control';
          exportControl.append(button,body.querySelector('.mmx-export-options'));card.prepend(exportControl);
        }
      }
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
  saveProject.onclick=async()=>{
    if(saveProject.disabled)return;
    if(!projectName.value.trim()){showProjectFeedback('error','Enter A Project Name Before Saving.');projectName.focus();return;}
    saveProject.disabled=true;saveProject.textContent='Saving…';saveProject.setAttribute('aria-busy','true');
    showProjectFeedback('busy','Saving Project On Server…');
    try{
      timelineState.project_name=projectName.value.trim();syncState();
      const graph=app.rootGraph || app.graph;
      if(!graph?.serialize)throw new Error('ComfyUI workflow serialization is unavailable.');
      const snapshot=JSON.parse(JSON.stringify({...timelineState,builder_state:builderState}));
      const capturedSignature=projectSignature();
      const result=await requestJson('/minimax_director/project/save',{
        project_id:snapshot.project_id,name:snapshot.project_name,timeline:snapshot,
        workflow:graph.serialize(),master_node_id:node.id,expected_revision:snapshot.server_revision || null});
      if(timelineState.project_id===snapshot.project_id){
        timelineState.server_revision=result.project.revision;savedProjectSignature=capturedSignature;syncState();
      }
      showProjectFeedback('success',`Saved “${snapshot.project_name}” On Server · ${new Date().toLocaleTimeString()}`);
    }catch(error){showProjectFeedback('error',`Save Failed: ${error.message}`);}finally{saveProject.disabled=false;saveProject.textContent='Save Project';saveProject.removeAttribute('aria-busy');}
  };
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
  library.append(nameField,saveProject,openProject,serverStatus,projectFeedback);projectTools.append(library);
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
  const exportPortable=async()=>{
    const blob = await transferRequest('/minimax_director/project/portable/export',{body:{project_id:timelineState.project_id,timeline:{...timelineState,builder_state:builderState}},blob:true,onProgress:e=>showProjectFeedback('busy',transferLabel(e))});
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a"); link.href = url; link.download = "MiniMaxProject.mmxproj"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const importPortable=async(file,policy)=>{
        const data = new FormData(); data.append("project", file);
        const result=await transferRequest('/minimax_director/project/portable/import',{body:data,onProgress:e=>showProjectFeedback('busy',transferLabel(e))});
          const merged = await requestJson("/minimax_director/project/merge", { current: timelineState, incoming: result.timeline, policy });
        timelineState = merged.timeline;
        if (merged.missing?.length) alert(`Missing media files: ${merged.missing.join(", ")}`);
        builderState = typeof timelineState.builder_state === "string" ? JSON.parse(timelineState.builder_state || "{}") : timelineState.builder_state || builderState;activeClipId=timelineState.clips?.[0]?.id; refreshFileRefs(); syncState(); renderTimeline();
  };
  const exportOptions=field("Include Media",includeMedia,"On: portable archive with source/reference files. Off: lightweight JSON that points to existing files.");exportOptions.classList.add("mmx-export-options");exportOptions.prepend(includeMedia);exportOptions.title="Include source and reference files in the exported project.";
  projectTools.append(exportBtn,importBtn,exportOptions);
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
          (item.continuity_mode || 'Independent (No Continuity)')==='Independent (No Continuity)')) break;
      item.validated=false; item.refine_approved=false; item.refine_pending=false;
      item.invalidated_generation=cachedClipResults[item.id]?.generation || null;
    }
  };
  const invalidateFrom = index => {
    timelineState.clips.slice(index).forEach(clip => { if (!clip.locked) clip.validated = false; });
  };
  const deleteClip = clip => {
    if(node.inputs?.some(input=>input.name==='timeline' && input.link!=null))return;
    const index = timelineState.clips.indexOf(clip);
    if (index < 0 || !confirm(`Delete "${clip.name || "clip"}" from the timeline?`)) return;
    timelineState.clips.splice(index, 1); invalidateFrom(index);
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
    invalidateFrom(Math.min(index, destination)); activeClipId = clip.id;
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

  finishSection(projectTools,"Named server projects, file backups and recovery. Canvas and sampling are configured in the connected Settings node.");
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
      defs.push(`${subj} is the motion sequence from <Video ${idx + 1}> (${vid.name}).`);
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

  // Render Multi-Track Timeline & Clips
  const clipCode = clip => clip.locked ? 'VIDEO' : ({T2VA:'T2V',I2VA:'I2V',FL2VA:'FL2V',L2VA:'L2V',REF2VA:'REF2V','Image Inpaint':'IMG','IMAGE INPAINT':'IMG'})[clip.type] || clip.type || 'T2V';
  const referenceTypes = clip => {
    const mode=clipCode(clip);
    if (mode==='T2V') return [];
    if (['I2V','FL2V','L2V','IMG'].includes(mode)) return ['image'];
    if (['VIDEO','V2V'].includes(mode)) return ['video'];
    return ['image','video','audio','refmod'];
  };
  const selectionLimit = (clip,type) => {
    const code=clipCode(clip);
    if(['VIDEO','V2V','I2V','L2V','IMG'].includes(code)) return 1;
    if(code==='FL2V') return 2;
    return ({image:9,video:3,audio:3,refmod:12})[type] || 0;
  };
  const selectionHelp = clip => ({T2V:'Text only.',VIDEO:'Choose exactly one source video.',V2V:'Choose exactly one source video.',I2V:'Choose one opening image.',L2V:'Choose one ending image.',FL2V:'Choose two images in order: opening, then ending. With continuity, one image can supply the ending.',IMG:'Choose exactly one image to edit.'})[clipCode(clip)] || (clipCode(clip)==='RV2V' ? 'The first selected video is the source. Up to 9 images, 3 videos including the source, 3 audio tracks and 12 total assets.' : 'Up to 9 images, 3 videos, 3 audio tracks and 12 total assets. Audio needs a visual reference.');
  const activeReferences = clip => (clip.ref_ids || []).map(id=>(timelineState.available_refs || []).find(row=>row.id===id)).filter(row=>row && referenceTypes(clip).includes(row.type));
  const refreshClipResults = async () => {
    const project=timelineState.project_id,request=++cacheStatusRequest;
    cacheStatusProject=project;
    try {
      const status=await requestJson(`/minimax_director/project/cache/status?project_id=${encodeURIComponent(project)}`);
      if(node.__mmxDisposed || request!==cacheStatusRequest || project!==timelineState.project_id)return;
      cachedClipResults=status.clips || {};renderTimeline();
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
      const method=clip.continuity_mode || "Independent (No Continuity)";
      if (index>0 && clip.continuity!==false && !clip.locked && !clip.source && method!=="Independent (No Continuity)" && !String(clip.type).includes("Inpaint")) {
        const external=false;
        const priorDuration=external?Number(clip.continuation_source.end || 0):Number(timelineState.clips[index-1].duration || 5);
        const rawFrames=Math.floor(priorDuration*24);
        const priorFrames=external || timelineState.clips[index-1]?.source?rawFrames:Math.max(5,5+Math.ceil((rawFrames-5)/17)*17);
        const grid=[56,39,22,5].find(count=>count<=priorFrames && count<=Number(clip.context_length || 22)) || 0;
        const video=method==="FL2VA Tail Handoff"?1:grid;
        const audio=method==="FL2VA Tail Handoff"?0:Number(clip.audio_context_length ?? video);
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
      const savedResult=cachedClipResults[clip.id];
      if(savedResult?.has_latent){
        const saved=document.createElement('span');saved.className='mmx-saved-badge';
        const previous=clip.id===generatingClipId || Boolean(clip.invalidated_generation && clip.invalidated_generation===savedResult.generation);
        saved.textContent=previous?'◆ Previous':'◆ Saved';
        saved.title=previous?'Previous saved latent; generate a replacement for the current clip settings.':'Generated latent saved on the server. Review this take and approve it to reuse it.';
        saved.setAttribute('aria-label',previous?'Previous saved latent available':'Saved generated latent available');
        shotTopBar.append(saved);
      }
      if(clip.refine_pending) {const review=document.createElement('span');review.textContent=clip.refine_approved?'Ready To Refine':'Review First Pass';review.className='mmx-generating-badge';shotTopBar.append(review);}
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
      const selectInput=document.createElement('input');selectInput.type='checkbox';selectInput.checked=clip.refine_pending ? !!clip.refine_approved : clip.validated===true;
      selectInput.disabled=clip.refine_pending ? !cachedClipResults[clip.id]?.has_first_pass : !clip.validated && !cachedClipResults[clip.id]?.can_approve;
      if(selectInput.disabled)selectLabel.title='Generate this clip first. Approval requires a saved result or latent on the server.';
      if(clip.refine_pending)selectLabel.title='Review First Pass in Smart Preview, approve here, then Run to refine its saved latent. This does not approve a final take.';
      selectInput.setAttribute('aria-label',`Approve ${clip.refine_pending ? 'First Pass Of ' : ''}${clip.name || `Clip ${idx+1}`}`);
      selectInput.onchange=()=>{if(clip.refine_pending)clip.refine_approved=selectInput.checked;else if(selectInput.checked){clip.validated=true;delete clip.invalidated_generation;}else unapproveChain(clip);syncState();renderTimeline();};
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
          if (newDur !== startDuration) invalidateFrom(idx);
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
    videosRow.hidden = !types.has("video"); audiosRow.hidden = !types.has("audio");
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
    const shotExtras = document.createElement("details"); const extrasTitle = document.createElement("summary"); extrasTitle.textContent = "Clip models, guides and grading";
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
    for (const [key, label, low, high, fallback] of [["exposure","Exposure",-10,10,0],["contrast","Contrast",0,4,1],["saturation","Saturation",0,4,1]]) {
      const wrap = document.createElement("label"); wrap.className="mmx-field"; wrap.textContent = label;
      const input = document.createElement("input"); input.type = "range"; input.min = low; input.max = high; input.step = ".05"; input.value = activeClip.color?.[key] ?? fallback;
      const value = document.createElement("span"); value.textContent = input.value;
      input.oninput = () => { (activeClip.color ||= {})[key] = Number(input.value); value.textContent = input.value; syncState(); };
      wrap.append(input,value); shotExtras.appendChild(wrap);
    }

    finishSection(shotExtras,"Optional changes for this clip: a model override, interior reference anchors, and grading after decode.");

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
            activeClip.validated=false;syncState();renderTimeline();return;
          }
          const start = key === "source_start" ? Number(input.value) : Number(activeClip.source_start || 0);
          const end = key === "source_end" ? Number(input.value) : Number(activeClip.source_end ?? (Number(activeClip.source_start || 0) + Number(activeClip.duration || 5)));
          if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start) {
            input.setCustomValidity("End must exceed start, and both must be finite non-negative seconds."); input.reportValidity(); return;
          }
          input.setCustomValidity(""); activeClip.source_start = start; activeClip.source_end = end;
          activeClip.duration = end - start; activeClip.validated = false; syncState(); renderTimeline();
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
        activeClip.validated = false; timelineState.clips.splice(index+1,1); syncState(); renderTimeline();
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
    const loraRows = document.createElement("div");
    loraPanel.appendChild(loraRows);
    const commitLoRAEdit=()=>{
      unapproveChain(activeClip);
      syncState();renderTimeline();
    };
    const drawLoras = () => {
      loraRows.replaceChildren();
      activeClip.loras.forEach((row, index) => {
        const controls = document.createElement("div");
        controls.style.cssText = "display:flex;gap:6px;margin:6px 0;align-items:center";
        const enabled = document.createElement("input");
        enabled.type = "checkbox";
        enabled.checked = (row.enabled ?? row.active ?? true) !== false;
        enabled.onchange = () => { row.enabled = enabled.checked; commitLoRAEdit(); };
        const name = document.createElement("select");
        name.style.cssText = "flex:1;min-width:0";
        const current = document.createElement("option");
        current.value = row.name || ""; current.textContent = row.name || "Choose a LoRA";
        name.appendChild(current);
        api.fetchApi("/minimax_director/loras").then(async response => {
          const names = await response.json();
          if (!response.ok || !Array.isArray(names)) throw new Error(names.error || "Cannot list LoRAs");
          for (const value of names) if (value !== row.name) {
            const option = document.createElement("option"); option.value = value; option.textContent = value; name.appendChild(option);
          }
        }).catch(error => { name.title = error.message; });
        name.onchange = () => { row.name = name.value; commitLoRAEdit(); };
        const info = document.createElement("button"); info.textContent = "Info";
        info.onclick = async () => {
          try {
            const result = await requestJson(`/minimax_director/loras/info?name=${encodeURIComponent(row.name || "")}`);
            const details = document.createElement("details"); details.open = true;
            const summary = document.createElement("summary"); summary.textContent = result.name; details.appendChild(summary);
            const metadata = document.createElement("pre"); metadata.style.whiteSpace = "pre-wrap"; metadata.textContent = JSON.stringify(result.metadata, null, 2); details.appendChild(metadata);
            if (result.has_preview) { const preview = document.createElement("img"); preview.style.maxWidth = "200px"; preview.src = api.apiURL(`/minimax_director/loras/info?preview=1&name=${encodeURIComponent(row.name)}`); details.appendChild(preview); }
            loraPanel.appendChild(details);
          } catch (error) { alert(error.message); }
        };
        const strength = document.createElement("input");
        strength.type = "number"; strength.min = "-10"; strength.max = "10"; strength.step = "0.05";
        strength.value = row.strength ?? 1; strength.style.width = "65px";
        strength.onchange = () => { const amount=Number(strength.value);if(!Number.isFinite(amount)||amount < -10 || amount > 10){strength.setCustomValidity("Enter a strength from -10 to 10.");strength.reportValidity();return;}strength.setCustomValidity("");row.strength = amount; commitLoRAEdit(); };
        const remove = document.createElement("button"); remove.textContent = "Remove";
        remove.onclick = () => { activeClip.loras.splice(index, 1); commitLoRAEdit(); drawLoras(); };
        controls.className="mmx-form-row";controls.style.cssText="";controls.append(field("Enabled",enabled),field("LoRA file",name),field("Model strength",strength),info,remove); loraRows.appendChild(controls);
      });
    };
    const addLora = document.createElement("button"); addLora.textContent = "Add LoRA";
    addLora.onclick = () => {
      if (activeClip.loras.length >= 8) return;
      activeClip.loras.push({ name: "", strength: 1, enabled: true }); commitLoRAEdit(); drawLoras();
    };
    loraPanel.appendChild(addLora); drawLoras();
    finishSection(loraPanel,"Optional model adapters applied only to this clip. Choose a compatible H3 LoRA and its strength.");

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
      activeClip.duration = v; activeClip.validated = false;
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
    const continuityModes=["Independent (No Continuity)","Motion Context (Chained)","Latent Carry (Pinned)","FL2VA Tail Handoff"];
    const continuityMode=document.createElement("select");continuityMode.className="mmx-shot-continuity-mode";
    for (const method of continuityModes) {const option=document.createElement("option");option.value=method;option.textContent=method.replace(/ \(.*\)$/, "");continuityMode.append(option);}
    continuityMode.value=activeClip.continuity_mode || "Independent (No Continuity)";
    const commitContinuity=()=>{activeClip.continuity=continuityMode.value!==continuityModes[0];activeClip.continuity_mode=continuityMode.value;activeClip.validated=false;syncState();renderTimeline();};
    continuityMode.onchange=commitContinuity;
    continuityPanel.append(field("Method",continuityMode,"Independent starts fresh. Motion Context uses saved audiovisual latent guides, with decoded footage as a fallback. Latent Carry copies the tail into the sample with tapered redraw masks. FL2VA hands off one final frame."));
    if([continuityModes[1],continuityModes[2]].includes(continuityMode.value)) for (const [key,title,choices,fallback] of [["context_length","Video Context (Seconds)",[5,22,39,56],22],["audio_context_length","Audio Context (Seconds)",[0,5,22,24,39,56],22]]) {
      const input=document.createElement("select");input.className="mmx-shot-"+key;
      for (const value of choices){const option=document.createElement("option");option.value=value;option.textContent=value===0?"Off":`${(value/24).toFixed(2)} s (${value} frames)`;input.append(option);}
      input.value=activeClip[key] ?? fallback;input.disabled=!!activeClip.locked || [continuityModes[0],continuityModes[3]].includes(continuityMode.value);
      input.onchange=()=>{activeClip[key]=Number(input.value);commitContinuity();};
      continuityPanel.append(field(title,input,key==="audio_context_length"?"Audio is independent of video context: 24 frames = 1 second. Off disables audio carry.":"Context is sampled before the new clip and removed from its delivered frames."));
    }
    if ([continuityModes[1],continuityModes[2]].includes(continuityMode.value)) {
      const policy=document.createElement("select");policy.className="mmx-shot-continuity-duration-policy";
      for (const [value,label] of [["new","Duration = new footage"],["total","Duration includes context (Extender)"]]) {
        const option=document.createElement("option");option.value=value;option.textContent=label;policy.append(option);
      }
      policy.value=activeClip.continuity_duration_policy || "new";
      policy.onchange=()=>{activeClip.continuity_duration_policy=policy.value;commitContinuity();};
      continuityPanel.append(field("Duration",policy,"New footage preserves the requested visible length. Extender includes the borrowed context, so the delivered clip is shorter. Frame counts snap to H3's temporal grid."));
    }
    if (continuityMode.value===continuityModes[2]){
      const redraw=document.createElement("input");redraw.type="number";redraw.min="0";redraw.max="0.95";redraw.step="0.05";redraw.value=activeClip.continuity_redraw ?? .1;
      redraw.onchange=()=>{activeClip.continuity_redraw=Number(redraw.value);commitContinuity();};continuityPanel.append(field("Seam redraw strength",redraw,"Tapered redraw near the seam: 0 holds the seam most strongly; higher values allow more redraw (maximum 0.95)."));
    }
    if(continuityMode.value===continuityModes[0]) {
      const note=document.createElement('p');note.className='mmx-continuity-mode-note';note.textContent='Starts a fresh clip. No video or audio context is borrowed.';continuityPanel.append(note);
    }
    if(continuityMode.value===continuityModes[3]) {
      const note=document.createElement('p');note.className='mmx-continuity-mode-note';note.textContent='Uses the preceding clip’s final image (0.04 s). Audio context is off. No context-length settings apply.';continuityPanel.append(note);
    }
    continuityMode.disabled=!!activeClip.locked;
    shotSections.prepend(continuityPanel);
    finishSection(continuityPanel,continuityMode.value===continuityModes[0]?"Independent clips borrow no video or audio context.":timelineState.clips.indexOf(activeClip)===0?"There is no preceding clip. Add a video or generate an earlier clip on the timeline to provide context.":"The chain between clips shows continuity from the preceding clip. Short previous clips limit the usable video and audio context.");
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
        activeClip.seed = value.toString(); activeClip.validated = false; seedInput.value = activeClip.seed; seedInput.setCustomValidity("");
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
      activeClip.seed = String(newSeed); activeClip.validated = false;
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
    refsPoolWrap.hidden = referenceTypes(activeClip).length === 0;
    if(!allRefs.length){const empty=document.createElement("span");empty.textContent="No compatible assets in the connected Reference Pack.";refsList.append(empty);}
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

      item.dataset.refId=r.id;
      const single=selectionLimit(activeClip,rtype)===1;
      const selected=activeReferences(activeClip);
      const imageFamily=['image','refmod'].includes(rtype);
      const atLimit=selected.filter(row=>imageFamily ? ['image','refmod'].includes(row.type) : row.type===rtype).length>=(imageFamily && ['REF2V','RV2V'].includes(clipCode(activeClip)) ? 9 : selectionLimit(activeClip,rtype)) || selected.length>=12;
      item.disabled=externallyAuthored || (!isChecked && !single && atLimit);
      if(item.disabled)item.title='Selection limit reached. Remove an asset before choosing another.';
      if(isChecked && ['FL2V','RV2V'].includes(clipCode(activeClip))) item.title=`Selection ${activeClip.ref_ids.indexOf(r.id)+1}${r.id===activeClip.source?.ref_id ? ' · Source Video' : ''}`;
      if(isChecked && (clipCode(activeClip)==='FL2V' || r.id===activeClip.source?.ref_id)) {
        const inheritedOpening=timelineState.clips.indexOf(activeClip)>0 && activeClip.continuity_mode!=='Independent (No Continuity)' && selected.length===1;
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
        activeClip.validated=false;syncState();renderTimeline();
      };
      refsList.appendChild(item);
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
      // Structured Prompt Sub-Toolbar (Scaffold from Refs & Clear)
      const structToolbar = document.createElement("div");
      structToolbar.style.display = "flex";
      structToolbar.style.justifyContent = "space-between";
      structToolbar.style.alignItems = "center";
      structToolbar.style.padding = "4px 0";

      const scaffoldBtn = document.createElement("button");
      scaffoldBtn.className = "mmx-action-btn primary";
      scaffoldBtn.style.fontSize = "10px";
      scaffoldBtn.style.padding = "2px 8px";
      scaffoldBtn.innerHTML = "✨ Scaffold from Refs";
      scaffoldBtn.title = "Automatically prefill structured fields based on assigned references";
      scaffoldBtn.disabled=externallyAuthored;
      scaffoldBtn.onclick = () => {
        const scaffold = scaffoldStructuredPrompt(activeClip);
        activeClip.structured_prompt = scaffold;
        activeClip.prompt = compileStructuredPrompt(scaffold);
        syncState();
        if (promptWidget) promptWidget.value = activeClip.prompt;
        renderInspector();
      };
      structToolbar.appendChild(scaffoldBtn);

      const clearStructBtn = document.createElement("button");
      clearStructBtn.className = "mmx-action-btn";
      clearStructBtn.style.fontSize = "10px";
      clearStructBtn.style.padding = "2px 8px";
      clearStructBtn.innerHTML = "Clear All";
      clearStructBtn.disabled=externallyAuthored;
      clearStructBtn.onclick = () => {
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
        activeClip.prompt = "";
        syncState();
        if (promptWidget) promptWidget.value = "";
        renderInspector();
      };
      structToolbar.appendChild(clearStructBtn);
      promptWrap.appendChild(structToolbar);

      // 6-Section Structured Fields Grid (Verbatim Official MiniMax H3 Section Names)
      const grid = document.createElement("div");
      grid.className = "mmx-structured-grid";
      grid.style.flex = "1";
      grid.style.minHeight = "140px";
      grid.style.overflowY = "auto";

      const createField = (key, label, isTextarea = true, fullSpan = false, placeholder = "") => {
        const field = document.createElement("div");
        field.className = "mmx-structured-field" + (fullSpan ? " full-span" : "");

        const lbl = document.createElement("span");
        lbl.className = "mmx-structured-label";
        lbl.textContent = label;
        field.appendChild(lbl);

        const input = document.createElement(isTextarea ? "textarea" : "input");
        input.className = isTextarea ? "mmx-structured-textarea" : "mmx-structured-input";
        input.placeholder = placeholder;
        const rawVal = activeClip.structured_prompt[key] || (key === "overall_soundscape" ? activeClip.structured_prompt.soundscape : (key === "non_diegetic_music" ? activeClip.structured_prompt.music : "")) || "";
        input.value = rawVal;
        input.readOnly=externallyAuthored;
        input.oninput = () => {
          activeClip.structured_prompt[key] = input.value;
          if (key === "overall_soundscape") {
            activeClip.structured_prompt.soundscape = input.value;
          } else if (key === "non_diegetic_music") {
            activeClip.structured_prompt.music = input.value;
          }
          activeClip.prompt = compileStructuredPrompt(activeClip.structured_prompt);
          syncState();
          if (promptWidget) promptWidget.value = activeClip.prompt;
          updatePromptCounters();
        };
        field.appendChild(input);
        return field;
      };

      grid.appendChild(createField("subject_definitions", "subject_definitions:", true, false, "Describe the subjects and assigned references."));
      grid.appendChild(createField("summary", "summary:", false, false, "[reference generation] Cinematic sequence for this clip with atmospheric lighting..."));
      grid.appendChild(createField("retention_analysis", "retention_analysis:", true, false, "Describe which assigned subjects or features should stay unchanged."));
      grid.appendChild(createField("detailed_description", "detailed_description:", true, false, "Describe continuous action, choreography, camera movements (pan, tilt, push-in), and lighting..."));
      grid.appendChild(createField("overall_soundscape", "overall_soundscape:", false, false, "Diegetic audio: wind ambience, footsteps, mechanical hums, natural reverberation..."));
      grid.appendChild(createField("non_diegetic_music", "non_diegetic_music:", false, false, "N/A or musical soundtrack style, e.g. Ambient orchestral cello drone..."));

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
        const tag = `<${kind} ${++counts[row.type]}>`;
        return {label: `${row.name} · ${tag}`, tag};
      });

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
    const panels=[["Continuity",continuityPanel],["Look",shotExtras],["LoRAs",loraPanel]];
    const canContinue=!continuityPanel.hidden;
    if((activeToolTab==="Continuity"&&!canContinue) || (activeToolTab==="LoRAs"&&activeClip.locked))activeToolTab="Look";
    const selectTool=label=>{
      if((label==="Continuity"&&!canContinue) || (label==="LoRAs"&&activeClip.locked))return;
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
      button.setAttribute("aria-controls",panelId);button.disabled=(label==="Continuity"&&!canContinue) || (label==="LoRAs"&&!!activeClip.locked);
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
    if(detail.invalidated_clip_ids?.length){
      const invalidated=new Set(detail.invalidated_clip_ids);
      for(const clip of timelineState.clips)if(invalidated.has(String(clip.id))){clip.validated=false;clip.refine_approved=false;clip.refine_pending=false;}
      syncState(true);void refreshClipResults();
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
      node.__mmxDisposed = true;stopClipProgress();
      for (const observers of node.__mmxRefObserverSets || []) observers.delete(node.__mmxRefObserver);
      node.__mmxRefObserverSets?.clear();
      cancelTimelineDrag?.();
      node.__mmxProjectDialog?.remove();

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
        if (count === 14 && ["manual","original","auto"].includes(node.widgets_values[11])) continue;
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
      if (node.type === "MiniMaxH3VideoCombine" && Array.isArray(node.widgets_values)
          && node.widgets_values.length === 16 && !node.widgets_values_named) {
        // The pre-consolidation exporter used FFmpeg and had no backend widget.
        node.widgets_values.splice(3, 0, "ffmpeg");
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
        for (const clip of state.clips || []) {
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
      const executed = nodeType.prototype.onExecuted;
      nodeType.prototype.onExecuted = function (message) {
        executed?.apply(this, arguments);
        if (!Array.isArray(message?.video)) return;
        if (!this.__mmxVideoElement) {
          const element = document.createElement("div"); element.style.width = "100%";
          this.__mmxVideoElement = element;
          this.addDOMWidget("video_preview", "MMX_VIDEO_PREVIEW", element, { serialize: false });
        }
        this.__mmxVideoElement.replaceChildren();
        for (const item of message.video) {
          const video = document.createElement("video"); video.controls = true; video.preload = "metadata";
          video.style.cssText = "width:100%;max-height:280px";
          video.src = api.apiURL(`/view?${new URLSearchParams({ filename: item.filename, subfolder: item.subfolder || "", type: item.type || "output" })}`);
          video.onerror = () => {
            if (video.dataset.fallback) return;
            video.dataset.fallback = "1";
            video.src = api.apiURL(`/minimax_director/video/preview?${new URLSearchParams({ filename: item.filename, subfolder: item.subfolder || "", type: item.type || "output" })}`);
          };
          this.__mmxVideoElement.appendChild(video);
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
