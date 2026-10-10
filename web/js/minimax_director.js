import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { installLocale } from "./minimax_locale.js";
import { bindShotDrag } from "./minimax_timeline.js";

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}

// Embedded CSS
const embeddedCSS = `/* Modern, sleek timeline editor styling for MiniMax H3 Master Director */

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
.mmx-director-root .mmx-shot-top-bar { width: 100%; gap: 5px; min-width: 0; }
.mmx-director-root .mmx-clip-title { display: block; min-width: 0; }
.mmx-director-root .mmx-clip-duration { white-space: nowrap; }
.mmx-director-root .mmx-clip-dup-btn { display: none; }
.mmx-director-root .mmx-clip-del-btn { flex: 0 0 22px; height: 22px; padding: 0; margin-left: auto; font: 18px/1 system-ui; }
.mmx-director-root .mmx-clip-handle-right { width: 10px; border-left: 1px solid #ffffff18; background: #ffffff08; }
.mmx-director-root .mmx-dragging { cursor: grabbing; opacity: .75; z-index: 4; box-shadow: 0 4px 14px #0006; }
.mmx-director-root .mmx-drop-before { border-left: 3px solid #b4a5ff; }
.mmx-director-root .mmx-drop-after { border-right: 3px solid #b4a5ff; }
.mmx-director-root .mmx-inspector-header { flex-wrap: wrap; }
.mmx-empty-timeline { color: var(--descrip-text, #aaa); padding: 18px 4px; }

.mmx-director-root .mmx-track-row { border-bottom: 1px solid var(--border-color,#444); gap: 0; }
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

.mmx-director-root .mmx-multitrack-panel { min-height:0; padding:0; border-radius:2px; background:#25272b; }
.mmx-director-root .mmx-shot-top-bar .mmx-clip-mode-badge { display:none; }
.mmx-director-root .mmx-clip-val-badge { font-size:11px!important; }

/* Compact editing desk: timeline first, readable segment prompt below. */
.mmx-director-root:not(.mmx-preview-node) { gap:8px; padding:8px; }
.mmx-director-root .mmx-toolbar { gap:5px; }
.mmx-director-root .mmx-action-btn { padding:4px 7px; border-radius:3px; }
.mmx-director-root .mmx-track-header-cell { width:112px; min-width:112px; font-size:10px; }
.mmx-director-root .mmx-shot-block { height:112px; padding:7px 8px; background:#20262e; }
.mmx-director-root .mmx-shot-block.active { background:#263341!important; border-color:#92adc3!important; box-shadow:none; }
.mmx-director-root .mmx-shot-prompt-preview { white-space:normal; display:-webkit-box; -webkit-line-clamp:5; -webkit-box-orient:vertical; overflow:hidden; line-height:1.45; font-size:12px; }
.mmx-director-root .mmx-shot-cover { width:100%; height:54px; object-fit:contain; background:#15191e; flex-shrink:0; }
.mmx-director-root .mmx-shot-block:has(.mmx-shot-cover) .mmx-shot-prompt-preview { -webkit-line-clamp:2; }
.mmx-director-root .mmx-add-clip-card { height:112px; border-radius:2px; }
.mmx-director-root .mmx-inspector { flex:0 0 auto; gap:7px; }
.mmx-director-root .mmx-prompt-inspector { flex:0 0 auto; min-height:0; }
.mmx-director-root .mmx-prompt-inspector > .mmx-textarea { flex:none!important; height:136px!important; min-height:100px!important; max-height:300px; resize:vertical; border-radius:3px; padding:9px; font:12px/1.55 ui-monospace,Consolas,monospace; }
.mmx-director-root .mmx-prompt-mode-tabs { border-radius:3px; padding:1px; }
.mmx-director-root .mmx-prompt-mode-tab { border-radius:2px; padding:3px 9px; }
.mmx-director-root .mmx-prompt-mode-tab.active { background:#426780; }
.mmx-director-root .mmx-inspector-card-title { color:#afb6bf!important; font-size:10px; }
.mmx-director-root .mmx-timecode-display { color:#c5d7e4; background:#191d22; border-radius:2px; }
.mmx-director-root .mmx-local-refs-pool { border-radius:2px; padding:7px; }
`;

function injectCSS() {
  if (document.getElementById("minimax-director-styles")) return;
  const style = document.createElement("style");
  style.id = "minimax-director-styles";
  style.textContent = embeddedCSS;
  document.head.appendChild(style);
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

  const getMinDomHeight = () => 480;

  const getAvailableDomHeight = (n, minH) => {
    if (!n || !n.size) return minH !== undefined ? minH : getMinDomHeight();
    const fallbackMin = minH !== undefined ? minH : getMinDomHeight();
    const topY = getTopWidgetsHeight(n);
    const avail = (n.size[1] || 0) - topY - 14;
    return Math.max(fallbackMin, Math.floor(avail));
  };

  const updateDomSize = () => {
    if (!domWidget || !domWidget.element) return;
    const topY = getTopWidgetsHeight(node);
    node.widgets_start_y = topY;
    if (domWidget) domWidget.last_y = topY;
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
        name: "Shot 1",
        type: "T2V",
        duration: 5.0,
        prompt: "",
        ref_ids: [],
        continuity: true,
      }
    ],
    refmods: [],
    available_refs: [],
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

        for (const [slot, type, short] of [["image_1","image","img_1"],["image_2","image","img_2"],["image_3","image","img_3"],["image_4","image","img_4"],["video_1","video","vid_1"],["video_2","video","vid_2"],["audio_1","audio","aud_1"],["audio_2","audio","aud_2"]]) {
          const input = rpNode.inputs?.find(row => row.name === slot);
          if (input?.link == null || !app.graph.links[input.link]) continue;
          const asset = getConnectedAsset(slot);
          discoveredRefs.push({id: `${idPrefix}${slot}`, alt_id: `${idPrefix}${short}`, name: `${prefix}${getVal(slot+"_name",slot)}`, type, ...asset});
        }
        for (const [slot, short] of [["refmod_1","mod_1"],["refmod_2","mod_2"]]) {
          const model = getVal(slot,"None");
          if (!model || model.toLowerCase() === "none") continue;
          discoveredRefs.push({id: `${idPrefix}${slot}`, alt_id: `${idPrefix}${short}`, name: `${prefix}${getVal(slot+"_name",slot)}`, type:"refmod", model});
        }
      });

      const customRefs = [];
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
          timelineState = { ...timelineState, ...parsed };
          if (!Array.isArray(timelineState.clips)) {
            timelineState.clips = [
              {
                id: "clip_1",
                name: "Shot 1",
                type: "T2V",
                duration: 5.0,
                tail_seconds: 0.5,
                seed: 0,
                seed_mode: "fixed",
                validated: false,
                prompt: "",
                ref_ids: [],
                continuity: true,
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

    resolveAvailableRefsFromGraph();
    if (!activeClipId || !timelineState.clips.find((c) => c.id === activeClipId)) {
      activeClipId = timelineState.clips[0]?.id || "clip_1";
    }
  };

  loadState();

  const syncState = () => {
    timelineState.project_id ||= node.id >= 0 ? String(node.id) : `project_${crypto.randomUUID()}`;
    if (timelineWidget) timelineWidget.value = JSON.stringify(timelineState);
    if (builderWidget) builderWidget.value = JSON.stringify(builderState);
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
  node.__mmxLocaleCleanup?.();
  node.__mmxLocaleCleanup = installLocale(root);

  // 1. LTX Director Style Top Toolbar
  const toolbar = document.createElement("div");
  toolbar.className = "mmx-toolbar";

  // Left action buttons
  const toolbarLeft = document.createElement("div");
  toolbarLeft.className = "mmx-toolbar-left";

  const syncRefsBtn = document.createElement("button");
  syncRefsBtn.className = "mmx-action-btn";
  syncRefsBtn.innerHTML = "🔄 Sync Refs";
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
      syncRefsBtn.innerHTML = "🔄 Sync Refs";
      syncRefsBtn.style.borderColor = "";
      syncRefsBtn.style.color = "";
    }, 1500);
  };
  toolbarLeft.appendChild(syncRefsBtn);

  const exportBtn = document.createElement("button");
  exportBtn.className = "mmx-action-btn";
  exportBtn.innerHTML = "💾 Export";
  exportBtn.title = "Export lightweight project archive";
  exportBtn.onclick = async () => {
    try {
      const res = await api.fetchApi("/minimax_director/project/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: timelineState.project_id || String(node.id ?? "default_director"),
          timeline: { ...timelineState, builder_state: builderWidget?.value || "{}" },
          name: "MiniMaxProject",
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
      }
    } catch (err) {
      alert("Failed to export project: " + err);
    }
  };
  toolbarLeft.appendChild(exportBtn);

  const importBtn = document.createElement("button");
  importBtn.className = "mmx-action-btn";
  importBtn.innerHTML = "📂 Import";
  importBtn.title = "Import project archive";
  importBtn.onclick = () => {
    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = ".json";
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
        if (!res.ok || !data.ok) throw new Error(data.error || "Project import failed");
        if (data.ok && data.timeline) {
          const policy = prompt("Import policy: append or overwrite", "overwrite"); if (!policy) return;
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
          renderTimeline();
          alert("Project imported successfully!");
        }
      } catch (err) {
        alert("Failed to import project: " + err);
      }
    };
    fileInput.click();
  };
  toolbarLeft.appendChild(importBtn);

  const selectionLabel = document.createElement("label");
  selectionLabel.style.cssText = "display:flex;gap:6px;align-items:center;font-size:11px";
  const runSelection = document.createElement("input");
  runSelection.type = "checkbox";
  runSelection.checked = !!timelineState.run_selection;
  runSelection.onchange = () => { timelineState.run_selection = runSelection.checked; syncState(); };
  selectionLabel.append(runSelection, document.createTextNode("Generate selected shots"));
  selectionLabel.title = "Other shots reuse matching cache or their original source video.";
  toolbarLeft.appendChild(selectionLabel);
  const progressLabel = document.createElement("span"); progressLabel.style.fontSize = "11px"; toolbarLeft.appendChild(progressLabel);

  const projectTools = document.createElement("details");
  const projectHeading = document.createElement("summary"); projectHeading.textContent = "Project tools";
  projectTools.appendChild(projectHeading); toolbarLeft.appendChild(projectTools);
  const addProjectAction = (label, handler) => {
    const button = document.createElement("button"); button.textContent = label;
    button.onclick = async () => { button.disabled = true; try { await handler(); } catch (error) { alert(error.message); } finally { button.disabled = false; } };
    projectTools.appendChild(button);
  };
  addProjectAction("Create project exporter", async () => {
    const exporter = LiteGraph.createNode("MiniMaxH3ProjectVideo");
    if (!exporter) throw new Error("Project Video node is unavailable; reload ComfyUI after installing the update.");
    exporter.pos = [(node.pos?.[0] || 0) + (node.size?.[0] || 1200) + 40, node.pos?.[1] || 0];
    app.graph.add(exporter); node.connect(9, exporter, 0);
  });
  addProjectAction("Clear current project cache", async () => {
    if (!confirm("Delete saved takes and cached outputs for this project? Uploaded reference files are retained.")) return;
    await requestJson("/minimax_director/project/clear_cache", {project_id: timelineState.project_id});
    timelineState.clips.forEach(shot => { shot.validated = false; }); syncState(); renderTimeline();
  });
  addProjectAction("Export with media", async () => {
    const response = await api.fetchApi("/minimax_director/project/portable/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: timelineState.project_id, timeline: { ...timelineState, builder_state: builderState } }) });
    if (!response.ok) throw new Error((await response.json()).error || "Export failed");
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a"); link.href = url; link.download = "MiniMaxProject.mmxproj"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  addProjectAction("Import media pack", async () => {
    const input = document.createElement("input"); input.type = "file"; input.accept = ".mmxproj,.zip";
    input.onchange = async () => {
      try {
        if (!input.files?.[0]) return;
        const data = new FormData(); data.append("project", input.files[0]);
        const response = await api.fetchApi("/minimax_director/project/portable/import", { method: "POST", body: data });
        const result = await response.json(); if (!response.ok) throw new Error(result.error || "Import failed");
        const policy = prompt("Import policy: append or overwrite", "append"); if (!policy) return;
        const merged = await requestJson("/minimax_director/project/merge", { current: timelineState, incoming: result.timeline, policy });
        timelineState = { ...merged.timeline, project_id: timelineState.project_id };
        if (merged.missing?.length) alert(`Missing media files: ${merged.missing.join(", ")}`);
        builderState = timelineState.builder_state || builderState; refreshFileRefs(); syncState(); renderTimeline();
      } catch (error) { alert(error.message); }
    }; input.click();
  });
  addProjectAction("Recover saved run", async () => {
    const result = await requestJson(`/minimax_director/project/recover?project_id=${encodeURIComponent(timelineState.project_id || "default_director")}`);
    timelineState = result.timeline; builderState = timelineState.builder_state || builderState;
    refreshFileRefs(); syncState(); renderTimeline();
  });
  addProjectAction("Choose saved take for continuation", async () => {
    const rows = await requestJson(`/minimax_director/project/takes?project_id=${encodeURIComponent(timelineState.project_id || "default_director")}`);
    const panel = document.createElement("details"); panel.open = true;
    const heading = document.createElement("summary"); heading.textContent = "Saved takes — choose explicitly"; panel.appendChild(heading);
    for (const take of rows) {
      const button = document.createElement("button");
      button.textContent = `${take.clip_id} · seed ${take.seed || "unknown"} · ${new Date(take.updated_at*1000).toLocaleString()}`;
      button.title = take.take_id;
      button.onclick = () => {
        const checkpoint = LiteGraph.createNode("MiniMaxH3Checkpoint");
        if (!checkpoint) { alert("Checkpoint node is unavailable; restart ComfyUI after installing this version."); return; }
        app.graph.add(checkpoint); checkpoint.pos = [node.pos[0]-340, node.pos[1]];
        for (const [name, value] of Object.entries({ project_id: timelineState.project_id || "default_director", clip_id: take.clip_id, take_id: take.take_id })) {
          const widget = checkpoint.widgets?.find(value => value.name === name); if (widget) widget.value = value;
        }
        const target = node.inputs?.findIndex(input => input.name === "continuation");
        if (target >= 0) checkpoint.connect(0, node, target);
        app.graph.setDirtyCanvas(true,true); panel.remove();
      }; panel.appendChild(button);
    }
    if (!rows.length) panel.appendChild(document.createTextNode("No completed takes saved for this project."));
    projectTools.appendChild(panel);
  });
  addProjectAction("New project", async () => {
    timelineState = { version: 2, project_id: `project_${crypto.randomUUID()}`, clips: [{ id: "clip_1", name: "Shot 1", type: "T2V", duration: 5, prompt: "", seed: "0" }], references: [] };
    builderState = {}; activeClipId = "clip_1"; syncState(); renderTimeline();
  });
  const sharedPrompt = document.createElement("textarea"); sharedPrompt.placeholder = "Shared prompt for every shot";
  sharedPrompt.value = timelineState.shared_prompt || "";
  sharedPrompt.onchange = () => { timelineState.shared_prompt = sharedPrompt.value; syncState(); };
  projectTools.appendChild(sharedPrompt);
  const fadeLabel = document.createElement("label"); fadeLabel.textContent = "Audio seam fade (ms) ";
  const fade = document.createElement("input"); fade.type = "number"; fade.min = "0"; fade.max = "1000"; fade.value = timelineState.audio_fade_ms ?? 15;
  fade.onchange = () => { timelineState.audio_fade_ms = Math.max(0,Math.min(1000,Number(fade.value)||0)); syncState(); }; fadeLabel.appendChild(fade); projectTools.appendChild(fadeLabel);
  const gainLabel = document.createElement("label"); const gain = document.createElement("input"); gain.type = "checkbox"; gain.checked = timelineState.audio_gain_match ?? true;
  gain.onchange = () => { timelineState.audio_gain_match = gain.checked; syncState(); }; gainLabel.append(gain,document.createTextNode("Match audio gain between shots")); projectTools.appendChild(gainLabel);
  const canvasMode = document.createElement("select");
  for (const mode of ["config", "original", "auto", "manual"]) { const option = document.createElement("option"); option.value = mode; option.textContent = `Canvas: ${mode}`; canvasMode.appendChild(option); }
  canvasMode.value = timelineState.resolution?.mode || "config";
  canvasMode.onchange = () => { if (canvasMode.value === "config") delete timelineState.resolution; else timelineState.resolution = { ...(timelineState.resolution || {}), mode: canvasMode.value }; syncState(); };
  projectTools.appendChild(canvasMode);
  for (const [key, placeholder, fallback] of [["width", "Manual width", 1344], ["height", "Manual height", 768], ["megapixels", "Auto megapixels", 1]]) {
    const input = document.createElement("input"); input.type = "number"; input.placeholder = placeholder; input.value = timelineState.resolution?.[key] ?? fallback;
    input.onchange = () => { timelineState.resolution ||= { mode: "manual" }; timelineState.resolution[key] = Number(input.value); syncState(); }; projectTools.appendChild(input);
  }
  const aspect = document.createElement("select");
  for (const value of ["auto", "16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "3:2", "2:3"]) { const option = document.createElement("option"); option.value = value; option.textContent = value; aspect.appendChild(option); }
  aspect.value = timelineState.resolution?.aspect || "16:9";
  aspect.onchange = () => { timelineState.resolution ||= { mode: "auto" }; timelineState.resolution.aspect = aspect.value; syncState(); }; projectTools.appendChild(aspect);
  const sharedPolicy = document.createElement("select");
  for (const value of ["prepend", "append"]) { const option = document.createElement("option"); option.value = value; option.textContent = value; sharedPolicy.appendChild(option); }
  sharedPolicy.value = timelineState.shared_prompt_policy || "prepend";
  sharedPolicy.onchange = () => { timelineState.shared_prompt_policy = sharedPolicy.value; syncState(); }; projectTools.appendChild(sharedPolicy);

  const forgePanel = document.createElement("details"); const forgeHeading = document.createElement("summary"); forgeHeading.textContent = "Prompt Forge — draft and review";
  forgePanel.appendChild(forgeHeading); projectTools.appendChild(forgePanel);
  const forgeBackend = document.createElement("select");
  for (const value of ["ollama", "compatible", "local"]) { const option = document.createElement("option"); option.value = value; option.textContent = value; forgeBackend.appendChild(option); }
  const localBackend = document.createElement("select");
  for (const value of ["transformers","gguf"]) { const option = document.createElement("option"); option.value = value; option.textContent = `Local: ${value}`; localBackend.appendChild(option); }
  const localProjection = document.createElement("input"); localProjection.placeholder = "GGUF vision projection in models/LLM (optional)";
  const forgeEndpoint = document.createElement("input"); forgeEndpoint.placeholder = "Provider endpoint"; forgeEndpoint.value = "http://localhost:11434";
  const forgeModel = document.createElement("input"); forgeModel.placeholder = "Model name";
  const forgeKey = document.createElement("input"); forgeKey.type = "password"; forgeKey.placeholder = "API key (kept in this panel only)";
  const forgeCount = document.createElement("input"); forgeCount.type = "number"; forgeCount.min = "1"; forgeCount.max = "100"; forgeCount.value = "1";
  const forgeInstruction = document.createElement("textarea"); forgeInstruction.placeholder = "Describe the shots, identities and details to retain";
  const forgeVision = document.createElement("input"); forgeVision.type = "checkbox";
  const visionLabel = document.createElement("label"); visionLabel.append(forgeVision, document.createTextNode("Use assigned Reference Pack media for vision review"));
  const forgeReview = document.createElement("div");
  let reviewedDraft = null;
  const drawDraft = draft => {
    reviewedDraft = draft; forgeReview.replaceChildren();
    draft.shots.forEach((shot,index) => {
      const card = document.createElement("fieldset");
      const heading = document.createElement("legend"); heading.textContent = `Shot ${index+1}`; card.appendChild(heading);
      const prompt = document.createElement("textarea"); prompt.value = shot.prompt; prompt.style.cssText = "display:block;width:95%;min-height:80px";
      prompt.oninput = () => { shot.prompt = prompt.value; }; card.appendChild(prompt);
      const duration = document.createElement("input"); duration.type = "number"; duration.min = ".01"; duration.max = "150"; duration.step = ".01"; duration.value = shot.duration || 5;
      duration.onchange = () => { shot.duration = Number(duration.value); }; card.appendChild(duration);
      const mode = document.createElement("select");
      for (const value of ["T2VA","I2VA","FL2VA","L2VA","REF2VA","V2V","RV2V","Image Inpaint"]) {
        const option = document.createElement("option"); option.value = value; option.textContent = value; mode.appendChild(option);
      }
      mode.value = shot.type || "T2VA"; mode.onchange = () => { shot.type = mode.value; }; card.appendChild(mode);
      forgeReview.appendChild(card);
    });
  };
  const forgeDraft = document.createElement("button"); forgeDraft.textContent = "Create draft";
  forgeDraft.onclick = async () => {
    forgeDraft.disabled = true;
    try {
      const result = await requestJson("/minimax_director/forge/draft", { timeline: timelineState, instruction: forgeInstruction.value,
        backend: forgeBackend.value, endpoint: forgeEndpoint.value, model: forgeModel.value, api_key: forgeKey.value, count: Number(forgeCount.value),
        local_backend: localBackend.value, projection: localProjection.value,
        vision_ids: forgeVision.checked ? (timelineState.references || []).filter(row => ["image", "video"].includes(row.type)).map(row => row.id) : [] });
      drawDraft(result);
    } catch (error) { alert(error.message); } finally { forgeDraft.disabled = false; }
  };
  const forgeApply = document.createElement("button"); forgeApply.textContent = "Apply reviewed draft";
  forgeApply.onclick = async () => {
    try {
      const draft = reviewedDraft; if (!draft) throw new Error("Create a draft before applying.");
      const result = await requestJson("/minimax_director/forge/apply", { timeline: timelineState, draft });
      timelineState = result.timeline; syncState(); renderTimeline();
    } catch (error) { alert(error.message); }
  };
  forgePanel.append(forgeBackend, forgeEndpoint, forgeModel, forgeKey, localBackend, localProjection, forgeCount, forgeInstruction, visionLabel, forgeDraft, forgeReview, forgeApply);

  const refmodLibrary = document.createElement("details"); const refmodHeading = document.createElement("summary"); refmodHeading.textContent = "RefMod library and descriptions";
  refmodLibrary.appendChild(refmodHeading); projectTools.appendChild(refmodLibrary);
  const refmodRows = document.createElement("div"); refmodLibrary.appendChild(refmodRows);
  let refmodCatalog = [];
  const drawRefmods = () => {
    refmodRows.replaceChildren();
    for (const row of timelineState.refmods || []) {
      const card = document.createElement("fieldset");
      const legend = document.createElement("legend"); legend.textContent = `<RefMod ${row.slot}>`; card.appendChild(legend);
      const enabled = document.createElement("input"); enabled.type = "checkbox"; enabled.checked = row.enabled !== false;
      enabled.onchange = () => { row.enabled = enabled.checked; syncState(); }; card.appendChild(enabled);
      const name = document.createElement("select");
      for (const entry of [{ name: row.name || "", description: "Select RefMod" }, ...refmodCatalog.filter(entry => entry.name !== row.name)]) {
        const option = document.createElement("option"); option.value = entry.name; option.textContent = `${entry.name || "Select RefMod"} ${entry.kind || ""}`; option.title = entry.description || ""; name.appendChild(option);
      }
      name.value = row.name || "";
      name.onchange = () => { row.name = name.value; row.description ||= refmodCatalog.find(entry => entry.name === row.name)?.description || ""; syncState(); drawRefmods(); }; card.appendChild(name);
      const description = document.createElement("textarea"); description.placeholder = "Description saved with this workflow"; description.value = row.description || "";
      description.onchange = () => { row.description = description.value; syncState(); }; card.appendChild(description);
      const strength = document.createElement("input"); strength.type = "number"; strength.min = "0"; strength.max = "1"; strength.step = ".05"; strength.value = row.strength ?? 1;
      strength.onchange = () => { row.strength = Number(strength.value); syncState(); }; card.appendChild(strength);
      const remove = document.createElement("button"); remove.textContent = "Remove"; remove.onclick = () => { timelineState.refmods = timelineState.refmods.filter(item => item !== row); syncState(); drawRefmods(); }; card.appendChild(remove);
      refmodRows.appendChild(card);
    }
  };
  refmodLibrary.ontoggle = async () => {
    if (!refmodLibrary.open) return;
    try { refmodCatalog = await requestJson("/minimax_director/refmods"); drawRefmods(); }
    catch (error) { refmodRows.textContent = error.message; }
  };
  const addRefmod = document.createElement("button"); addRefmod.textContent = "Add RefMod";
  addRefmod.onclick = () => {
    const used = new Set((timelineState.refmods || []).map(row => row.slot)); const slot = Array.from({length:8},(_,i)=>i+1).find(value => !used.has(value));
    if (!slot) return;
    (timelineState.refmods ||= []).push({ slot, name: "", description: "", strength: 1, enabled: true }); syncState(); drawRefmods();
  }; refmodLibrary.appendChild(addRefmod); drawRefmods();

  let cancelTimelineDrag = null;
  const invalidateFrom = index => {
    timelineState.clips.slice(index).forEach(shot => { if (!shot.locked) shot.validated = false; });
  };
  const deleteClip = clip => {
    const index = timelineState.clips.indexOf(clip);
    if (index < 0 || !confirm(`Delete "${clip.name || "shot"}" from the timeline?`)) return;
    timelineState.clips.splice(index, 1); invalidateFrom(index);
    activeClipId = timelineState.clips[Math.min(index, timelineState.clips.length - 1)]?.id || null;
    syncState(); renderTimeline();
  };
  const moveClip = (clip, destination) => {
    const index = timelineState.clips.indexOf(clip);
    if (index < 0 || clip.locked) return;
    // A locked source stays in place; shots cannot cross it.
    let min = 0, max = timelineState.clips.length - 1;
    timelineState.clips.forEach((shot, position) => {
      if (shot.locked) { if (position < index) min = position + 1; else if (position > index) max = Math.min(max, position - 1); }
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
      name: `${clipToClone.name || "Shot"} (Copy)`,
      validated: false, // Reset validation so cloned shot generates
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
  clearBtn.className = "mmx-action-btn";
  clearBtn.innerHTML = "🗑️ Reset";
  clearBtn.title = "Reset timeline to default shot";
  clearBtn.onclick = () => {
    if (confirm("Reset timeline to a single default shot?")) {
      timelineState.clips = [
        {
          id: "clip_1",
          name: "Shot 1",
          type: "T2V",
          duration: 5.0,
          prompt: "",
          ref_ids: [],
          continuity: true,
        }
      ];
      activeClipId = "clip_1";
      playheadSeconds = 0.0;
      syncState();
      renderTimeline();
    }
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

  const timecodeBadge = document.createElement("div");
  timecodeBadge.className = "mmx-timecode-display";
  timecodeBadge.textContent = "00:00:00:00";
  toolbarRight.appendChild(timecodeBadge);

  const zoomWrap = document.createElement("div");
  zoomWrap.className = "mmx-zoom-slider-wrap";
  zoomWrap.title = "Timeline zoom";
  zoomWrap.innerHTML = `<span style="font-size: 10px; color: #94a3b8;">🔍</span>`;

  const zoomSlider = document.createElement("input");
  zoomSlider.type = "range";
  zoomSlider.min = "0.5";
  zoomSlider.max = "3.0";
  zoomSlider.step = "0.1";
  zoomSlider.value = "3.0";
  zoomSlider.className = "mmx-zoom-slider";
  zoomSlider.oninput = () => {
    zoomLevel = parseFloat(zoomSlider.value) || 1.0;
    renderTimeline();
  };
  ["mousedown", "pointerdown", "touchstart"].forEach((evt) => {
    zoomSlider.addEventListener(evt, (e) => e.stopPropagation());
  });
  zoomWrap.appendChild(zoomSlider);
  toolbarRight.appendChild(zoomWrap);
  toolbarRight.appendChild(root.querySelector(".mmx-language-select"));

  toolbar.appendChild(toolbarRight);
  root.appendChild(toolbar);

  // 2. Multi-Track Timeline Panel (4 Sub-Tracks + Ruler)
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

  // Row 1: Shots Track (Shots + Prompt)
  const shotsRow = document.createElement("div");
  shotsRow.className = "mmx-track-row mmx-track-row-shots";
  const shotsHeader = document.createElement("div");
  shotsHeader.className = "mmx-track-header-cell";
  shotsHeader.innerHTML = `<span>🎬</span><span>Shots / Prompt</span>`;
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
  imagesHeader.innerHTML = `<span>🖼️</span><span>Ref Images</span>`;
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
  videosHeader.innerHTML = `<span>📹</span><span>Ref Videos</span>`;
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
  audiosHeader.innerHTML = `<span>🎵</span><span>Ref Audios</span>`;
  const audiosLane = document.createElement("div");
  audiosLane.className = "mmx-track-lane-cell mmx-audios-lane";
  audiosRow.appendChild(audiosHeader);
  audiosRow.appendChild(audiosLane);
  multitrackPanel.appendChild(audiosRow);

  // Append Playhead Needle LAST so it floats ON TOP of all tracks
  multitrackPanel.appendChild(playheadNeedle);

  root.appendChild(multitrackPanel);

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

  // Draw 24px Time Ruler
  const drawRuler = () => {
    const totalClipsWidth = timelineState.clips.reduce((acc, c) => {
      const dur = parseFloat(c.duration) || 5.0;
      return acc + Math.max(32, Math.round(dur * 64 * zoomLevel)) + 4;
    }, 0);
    // Measure the viewport, not the ruler child, to avoid resize feedback.
    const laneW = Math.max(1, (multitrackPanel.clientWidth || 930) - 130);
    const w = Math.max(laneW, totalClipsWidth + 100);
    rulerTicks.style.width = `${w}px`;
    rulerTicks.replaceChildren();

    const totalDuration = timelineState.clips.reduce((acc, c) => acc + (parseFloat(c.duration) || 5.0), 0);
    const effectiveTotal = Math.max(totalDuration, 1.0);
    const pxPerSec = totalClipsWidth > 0 ? (totalClipsWidth / effectiveTotal) : (w / effectiveTotal);
    multitrackPanel.style.setProperty("--mmx-grid-step", `${pxPerSec}px`);

    const stepSec = pxPerSec > 80 ? 0.5 : (pxPerSec > 40 ? 1.0 : 2.0);
    const ticks = document.createDocumentFragment();
    for (let seconds = 0; seconds <= effectiveTotal; seconds += stepSec) {
      const x = Math.round(seconds * pxPerSec);
      if (x > w) break;
      const major = Math.abs(seconds - Math.round(seconds)) < 0.01;
      const tick = document.createElement("div");
      tick.className = `mmx-time-tick${major ? " major" : ""}`;
      tick.style.left = `${x}px`;
      if (major) {
        const label = document.createElement("span");
        label.textContent = `${Math.round(seconds)}s`;
        tick.appendChild(label);
      }
      ticks.appendChild(tick);
    }
    rulerTicks.appendChild(ticks);

    // Update playhead needle position (offset by sticky header 124px + lane padding 6px = 130px)
    const playheadX = Math.max(0, Math.min(w, playheadSeconds * pxPerSec));
    playheadNeedle.style.left = `${130 + playheadX}px`;
    playheadNeedle.style.height = `${multitrackPanel.scrollHeight || 215}px`;
    timecodeBadge.textContent = formatTimecode(playheadSeconds, 24);
  };

  // Ruler & Playhead scrub interaction (Premiere-style full timeline scrubbing)
  let isScrubbing = false;
  const updateScrubFromClientX = (clientX) => {
    const rect = rulerTicks.getBoundingClientRect();
    // Convert screen pixels back to node coordinates at any graph/browser zoom.
    const laneWidth = parseFloat(rulerTicks.style.width) || rect.width;
    const x = Math.max(0, Math.min(laneWidth, (clientX - rect.left) * laneWidth / (rect.width || 1)));
    const totalDuration = timelineState.clips.reduce((acc, c) => acc + (parseFloat(c.duration) || 5.0), 0);
    const effectiveTotal = Math.max(totalDuration, 1.0);
    const totalClipsWidth = timelineState.clips.reduce((acc, c) => {
      const dur = parseFloat(c.duration) || 5.0;
      return acc + Math.max(32, Math.round(dur * 64 * zoomLevel)) + 4;
    }, 0);
    const pxPerSec = totalClipsWidth > 0 ? (totalClipsWidth / effectiveTotal) : (laneWidth / effectiveTotal);
    playheadSeconds = Math.max(0, Math.min(totalDuration, x / pxPerSec));
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
    panel.className = "mmx-modal-panel";

    panel.innerHTML = `
      <div class="mmx-modal-header">
        <span class="mmx-modal-title">➕ Add New Timeline Shot</span>
        <button class="mmx-action-btn" id="modal-close-btn">✕</button>
      </div>
      <div class="mmx-modal-body">
        <div style="font-size: 11px; color: #94a3b8;">
          Choose the generation mode for this shot. Each shot can independently utilize text, start/end frames, guide videos, or multi-modal character references:
        </div>
        <div class="mmx-type-modal-grid">
          <button class="mmx-type-modal-btn" data-type="T2V">
            <span class="mmx-type-modal-btn-title">
              <span class="mmx-clip-mode-badge mmx-badge-t2v">T2V</span> Text to Video
            </span>
            <span class="mmx-type-modal-btn-desc">Pure text prompt generation. Seamlessly chains from previous shot tail when continuity is enabled.</span>
          </button>
          <button class="mmx-type-modal-btn" data-type="I2V">
            <span class="mmx-type-modal-btn-title">
              <span class="mmx-clip-mode-badge mmx-badge-i2v">I2V</span> Image to Video
            </span>
            <span class="mmx-type-modal-btn-desc">Starts from a selected reference image (or inherited previous shot tail frame).</span>
          </button>
          <button class="mmx-type-modal-btn" data-type="FL2V">
            <span class="mmx-type-modal-btn-title">
              <span class="mmx-clip-mode-badge mmx-badge-fl2v">FL2V</span> First & Last Frame
            </span>
            <span class="mmx-type-modal-btn-desc">Interpolates smoothly between a start frame and an end frame keyframe pair.</span>
          </button>
          <button class="mmx-type-modal-btn" data-type="V2V">
            <span class="mmx-type-modal-btn-title">
              <span class="mmx-clip-mode-badge mmx-badge-v2v">V2V</span> Video to Video
            </span>
            <span class="mmx-type-modal-btn-desc">Guide video for motion transfer, style translation, or reenactment.</span>
          </button>
          <button class="mmx-type-modal-btn" data-type="REF2VA">
            <span class="mmx-type-modal-btn-title">
              <span class="mmx-clip-mode-badge mmx-badge-ref2va">REF2VA</span> Ref to Video + Audio (Multi-Modal)
            </span>
            <span class="mmx-type-modal-btn-desc">Full multi-modal reference generation with character identity images, audio tracks, and RefMods.</span>
          </button>
          <button class="mmx-type-modal-btn" data-type="L2VA">
            <span class="mmx-type-modal-btn-title">L2VA · Last Frame</span>
            <span class="mmx-type-modal-btn-desc">Generate a take ending at the selected image.</span>
          </button>
          <button class="mmx-type-modal-btn" data-type="RV2V">
            <span class="mmx-type-modal-btn-title">RV2V · Reference Video Edit</span>
            <span class="mmx-type-modal-btn-desc">Guide a source video using additional image and audio references.</span>
          </button>
          <button class="mmx-type-modal-btn" data-type="Image Inpaint">
            <span class="mmx-type-modal-btn-title">Image Inpaint · Still Image</span>
            <span class="mmx-type-modal-btn-desc">One reference image, a five-frame H3 pass, and one generated output image.</span>
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.appendChild(panel);

    const close = () => {
      if (backdrop.parentNode) backdrop.parentNode.removeChild(backdrop);
    };

    panel.querySelector("#modal-close-btn").onclick = close;
    backdrop.onclick = (e) => {
      if (e.target === backdrop) close();
    };

    panel.querySelectorAll(".mmx-type-modal-btn").forEach((btn) => {
      btn.onclick = () => {
        const type = btn.dataset.type;
        const newIndex = timelineState.clips.length + 1;
        const newClip = {
          id: `clip_${Date.now()}_${newIndex}`,
          name: `Shot ${newIndex}`,
          type: type,
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
          continuity: true,
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
    const assignedObjs = assigned.map((id) => timelineState.available_refs?.find((r) => r.id === id)).filter(Boolean);
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
  const renderTimeline = () => {
    cancelTimelineDrag?.();
    refreshFileRefs();
    shotsLane.innerHTML = "";
    imagesLane.innerHTML = "";
    videosLane.innerHTML = "";
    audiosLane.innerHTML = "";

    // 1. Calculate Total Duration & Frames (at 24fps)
    const totalDuration = timelineState.clips.reduce((acc, c) => acc + (parseFloat(c.duration) || 5.0), 0);
    const totalFrames = Math.round(totalDuration * 24);
    durationTotal.textContent = `Total: ${totalDuration.toFixed(1)}s / ${totalFrames}f (${timelineState.clips.length} Shot${timelineState.clips.length === 1 ? "" : "s"})`;

    const clipTrackElements = [];

    const selectClip = (cid) => {
      activeClipId = cid;
      clipTrackElements.forEach(({ clip: c, shotBlock, imgBlock, vidBlock, audBlock }) => {
        const isActive = c.id === cid;
        shotBlock.classList.toggle("active", isActive);
        imgBlock.classList.toggle("active", isActive);
        vidBlock.classList.toggle("active", isActive);
        audBlock.classList.toggle("active", isActive);
      });
      renderInspector();
    };

    // 2. Render Clips across all 4 Sub-Tracks
    timelineState.clips.forEach((clip, idx) => {
      const dur = parseFloat(clip.duration) || 5.0;
      const baseWidth = Math.max(32, Math.round(dur * 64 * zoomLevel));
      const isActive = clip.id === activeClipId;
      const isValidated = !!clip.validated;

      // Filter assigned refs by type for this shot
      const assignedRefs = clip.ref_ids || [];
      const assignedObjs = assignedRefs.map((rid) => timelineState.available_refs?.find((r) => r.id === rid)).filter(Boolean);
      const imgRefs = assignedObjs.filter((r) => r.type === "image" || r.type === "refmod");
      const vidRefs = assignedObjs.filter((r) => r.type === "video");
      const audRefs = assignedObjs.filter((r) => r.type === "audio");

      // ============================================
      // Track 1: Shot Block (Header info + Prompt preview)
      // ============================================
      const shotBlock = document.createElement("div");
      shotBlock.className = `mmx-subtrack-block mmx-shot-block${isActive ? " active" : ""}${isValidated ? " validated" : ""}`;
      shotBlock.style.width = `${baseWidth}px`;
      shotBlock.title = `Shot ${idx + 1}: ${clip.name || "Untitled"} (${dur.toFixed(1)}s) - Click to inspect`;

      // Top Bar: Mode, Name, Duration, Auto-Tail, Validated, Delete
      const shotTopBar = document.createElement("div");
      shotTopBar.className = "mmx-shot-top-bar";

      const modeBadge = document.createElement("span");
      const typeLower = (clip.type || "T2V").toLowerCase();
      modeBadge.className = `mmx-clip-mode-badge mmx-badge-${typeLower}`;
      modeBadge.textContent = clip.type || "T2V";

      const title = document.createElement("span");
      title.className = "mmx-clip-title";
      title.textContent = clip.name || `Shot ${idx + 1}`;

      const durTag = document.createElement("span");
      durTag.className = "mmx-clip-duration";
      durTag.textContent = `${dur.toFixed(1)}s`;

      shotTopBar.appendChild(modeBadge);
      shotTopBar.appendChild(title);
      shotTopBar.appendChild(durTag);

      if (clip.continuity && idx > 0) {
        const contIcon = document.createElement("span");
        contIcon.style.fontSize = "10px";
        contIcon.title = "Auto-Tail Continuity from previous shot";
        contIcon.textContent = "🔗";
        shotTopBar.appendChild(contIcon);
      }

      if (clip.validated) {
        const valBadge = document.createElement("span");
        valBadge.className = "mmx-clip-val-badge";
        valBadge.style.fontSize = "9px";
        valBadge.style.color = "#34d399";
        valBadge.style.fontWeight = "bold";
        valBadge.style.background = "rgba(16, 185, 129, 0.15)";
        valBadge.style.border = "1px solid rgba(16, 185, 129, 0.4)";
        valBadge.style.borderRadius = "3px";
        valBadge.style.padding = "1px 4px";
        valBadge.textContent = "✓";
        valBadge.title = "Shot is validated (cached and skipped on re-render)";
        shotTopBar.appendChild(valBadge);
      }

      const delBtn = document.createElement("button");
      delBtn.className = "mmx-clip-del-btn";
      delBtn.textContent = "×";
      delBtn.title = `Delete ${clip.name || "shot"}`;
      delBtn.setAttribute("aria-label", delBtn.title);
      delBtn.onclick = e => { e.stopPropagation(); deleteClip(clip); };
      shotTopBar.appendChild(delBtn);

      shotBlock.appendChild(shotTopBar);

      const coverRef = imgRefs.find(ref => ref.type === "image" && ref.url);
      if (coverRef) {
        const cover = document.createElement("img");
        cover.className = "mmx-shot-cover";
        cover.src = coverRef.url;
        cover.alt = coverRef.name;
        cover.draggable = false;
        shotBlock.appendChild(cover);
      }

      // Bottom Bar: Prompt Preview Snippet
      const promptSnippet = document.createElement("div");
      promptSnippet.className = "mmx-shot-prompt-preview";
      const hasPrompt = !!(clip.prompt && clip.prompt.trim());
      promptSnippet.textContent = hasPrompt ? clip.prompt.trim() : "(No prompt set)";
      promptSnippet.style.color = hasPrompt ? "#94a3b8" : "#475569";
      promptSnippet.style.fontStyle = hasPrompt ? "normal" : "italic";
      shotBlock.appendChild(promptSnippet);

      // Right resize handle (synchronously resizes all 4 track blocks)
      const rightHandle = document.createElement("div");
      rightHandle.className = "mmx-clip-handle mmx-clip-handle-right";

      let startX = 0;
      let startDuration = dur;

      rightHandle.title = "Drag to change duration";
      rightHandle.onmousedown = (e) => {
        e.stopPropagation();
        e.preventDefault();
        startX = e.clientX;
        startDuration = parseFloat(clip.duration) || 5.0;
        const scale = shotBlock.getBoundingClientRect().width / (shotBlock.offsetWidth || baseWidth) || 1;

        const onMouseMove = (moveEvt) => {
          const deltaX = moveEvt.clientX - startX;
          const newDur = Math.max(0.5, Math.min(60.0, Math.round((startDuration + deltaX / (scale * 64 * zoomLevel)) * 10) / 10));
          clip.duration = newDur;
          if (newDur !== startDuration) invalidateFrom(idx);
          durTag.textContent = `${newDur.toFixed(1)}s`;
          const newWidth = Math.max(32, Math.round(newDur * 64 * zoomLevel));

          // Synchronously resize all 4 track blocks in real time!
          shotBlock.style.width = `${newWidth}px`;
          imgBlock.style.width = `${newWidth}px`;
          vidBlock.style.width = `${newWidth}px`;
          audBlock.style.width = `${newWidth}px`;

          const tot = timelineState.clips.reduce((acc, c) => acc + (parseFloat(c.duration) || 5.0), 0);
          durationTotal.textContent = `Total: ${tot.toFixed(1)}s / ${Math.round(tot * 24)}f (${timelineState.clips.length} Shots)`;
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
      imgBlock.title = `Shot ${idx + 1} Ref Images (${imgRefs.length}) - Click to inspect`;
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
      vidBlock.title = `Shot ${idx + 1} Ref Videos (${vidRefs.length}) - Click to inspect`;
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
      audBlock.title = `Shot ${idx + 1} Ref Audios (${audRefs.length}) - Click to inspect`;
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

    const types = new Set(timelineState.clips.flatMap(shot => (shot.ref_ids || []).map(id => timelineState.available_refs.find(row => row.id === id)?.type)));
    imagesRow.hidden = !types.has("image") && !types.has("refmod");
    videosRow.hidden = !types.has("video"); audiosRow.hidden = !types.has("audio");
    // 3. Add Shot Button flush at end of Track 1 (Shots Lane)
    const addCard = document.createElement("div");
    addCard.className = "mmx-add-clip-card";
    addCard.innerHTML = `<span class="mmx-add-clip-icon">+</span><span>Add Shot</span>`;
    addCard.title = "Add a new shot to the timeline";
    addCard.onclick = openTypePickerModal;
    shotsLane.appendChild(addCard);

    // 4. Render Active Clip Inspector
    renderInspector();

    // 5. Update Time Ruler
    drawRuler();

  };

  // Render Active Clip Inspector (Directly below timeline track!)
  const renderInspector = () => {
    inspector.innerHTML = "";
    const activeClip = timelineState.clips.find((c) => c.id === activeClipId) || timelineState.clips[0];
    if (!activeClip) {
      const empty = document.createElement("p"); empty.className = "mmx-empty-timeline";
      empty.textContent = "No shots. Click + Add Shot in the timeline to begin.";
      inspector.appendChild(empty); return;
    }

    // Header: Shot Name + Mode Dropdown + Duration + Auto-Tail
    const header = document.createElement("div");
    header.className = "mmx-inspector-header";

    // Shot Name Input & Mode Select
    const titleWrap = document.createElement("div");
    titleWrap.className = "mmx-inspector-title";

    const shotLabel = document.createElement("span");
    shotLabel.style.fontSize = "11px";
    shotLabel.style.color = "#94a3b8";
    const clipIdx = timelineState.clips.indexOf(activeClip) + 1;
    shotLabel.textContent = "Shot:";
    titleWrap.appendChild(shotLabel);

    const nameInput = document.createElement("input");
    nameInput.style.background = "var(--comfy-input-bg, #333333)";
    nameInput.style.border = "1px solid var(--border-color, #4a4a4a)";
    nameInput.style.borderRadius = "4px";
    nameInput.style.color = "#f8fafc";
    nameInput.style.fontSize = "11px";
    nameInput.style.fontWeight = "600";
    nameInput.style.padding = "2px 6px";
    nameInput.style.width = "120px";
    nameInput.value = activeClip.name || `Shot ${clipIdx}`;
    nameInput.oninput = () => {
      activeClip.name = nameInput.value;
      syncState();
      const cardTitle = shotsLane.querySelector(".mmx-subtrack-block.active .mmx-clip-title");
      if (cardTitle) cardTitle.textContent = activeClip.name;
    };
    titleWrap.appendChild(nameInput);

    // Mode Dropdown Selector (Unified: REF2V merged into REF2VA!)
    const modeSelect = document.createElement("select");
    modeSelect.className = "mmx-mode-select";
    const modes = [
      { id: "T2V", label: "T2V (Text to Video)" },
      { id: "I2V", label: "I2V (Image to Video)" },
      { id: "FL2V", label: "FL2V (First & Last Frame)" },
      { id: "V2V", label: "V2V (Video to Video)" },
      { id: "REF2VA", label: "REF2VA (Ref to Video + Audio)" },
      { id: "L2VA", label: "L2VA (Last Frame)" },
      { id: "RV2V", label: "RV2V (Reference Video Edit)" },
      { id: "Image Inpaint", label: "Image Inpaint (Single Image)" },
    ];
    modes.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m.id;
      opt.textContent = m.label;
      if (activeClip.type === m.id) opt.selected = true;
      modeSelect.appendChild(opt);
    });
    modeSelect.onchange = () => {
      activeClip.type = modeSelect.value;
      syncState();
      renderTimeline();
    };
    titleWrap.appendChild(modeSelect);
    header.appendChild(titleWrap);

    // Actions group in Inspector Header (Validated Toggle + Delete Shot)
    const headerActions = document.createElement("div");
    headerActions.style.display = "flex";
    headerActions.style.alignItems = "center";
    headerActions.style.gap = "8px";
    headerActions.style.flexWrap = "wrap";

    const selectedLabel = document.createElement("label");
    const selected = document.createElement("input");
    selected.type = "checkbox"; selected.checked = activeClip.selected !== false;
    selected.onchange = () => { activeClip.selected = selected.checked; syncState(); };
    selectedLabel.append(selected, document.createTextNode("Selected"));
    headerActions.appendChild(selectedLabel);

    // 1. Validated Toggle Badge in Header (Prevents re-generation, reuses cached output)
    const valBtn = document.createElement("div");
    valBtn.className = "mmx-validate-toggle " + (activeClip.validated ? "validated" : "unvalidated");
    valBtn.title = "Mark shot as validated. Validated shots reuse cached output and skip re-generation.";
    valBtn.innerHTML = activeClip.validated ? "<span>✅</span><span>Validated (Skip Gen)</span>" : "<span>⭕</span><span>Unvalidated (Will Gen)</span>";
    valBtn.onclick = () => {
      activeClip.validated = !activeClip.validated;
      syncState();
      renderTimeline();
      renderInspector();
    };
    headerActions.appendChild(valBtn);

    // 2. Duplicate Shot Button in Inspector Header
    const dupShotBtn = document.createElement("button");
    dupShotBtn.className = "mmx-action-btn";
    dupShotBtn.innerHTML = "<span>📋</span><span>Duplicate Shot</span>";
    dupShotBtn.title = `Duplicate "${activeClip.name}" with all its prompt and reference settings`;
    dupShotBtn.onclick = () => duplicateClip(activeClip);
    headerActions.appendChild(dupShotBtn);

    // 3. Dedicated Delete Shot Button in Inspector Header
    const delShotBtn = document.createElement("button");
    delShotBtn.className = "mmx-action-btn danger";
    delShotBtn.textContent = "Delete Shot";
    delShotBtn.onclick = () => deleteClip(activeClip);
    headerActions.appendChild(delShotBtn);
    if (!activeClip.locked) for (const [offset, label] of [[-1, "← Move earlier"], [1, "Move later →"]]) {
      const button = document.createElement("button"); button.className = "mmx-action-btn";
      button.textContent = label;
      const index = timelineState.clips.indexOf(activeClip), adjacent = timelineState.clips[index + offset];
      button.disabled = !adjacent || !!adjacent.locked;
      button.onclick = () => moveClip(activeClip, index + offset);
      headerActions.appendChild(button);
    }

    header.appendChild(headerActions);
    inspector.appendChild(header);

    // Main Inputs Area (Placeholder for fields if needed)
    // ...

    // Cards Grid: Card 1 (Timing & Seam Continuity) and Card 2 (Seed & Generation Parameters)
    const cardsGrid = document.createElement("div");
    cardsGrid.className = "mmx-inspector-cards-grid";
    inspector.appendChild(cardsGrid);

    const audioLabel = document.createElement("label");
    audioLabel.textContent = "Shot audio: ";
    const audioMode = document.createElement("select");
    for (const [value, label] of [["generate", "Generate"], ["source", "Keep source audio"], ["mute", "Mute"]]) {
      const option = document.createElement("option"); option.value = value; option.textContent = label;
      audioMode.appendChild(option);
    }
    audioMode.value = activeClip.audio_mode || "generate";
    audioMode.onchange = () => { activeClip.audio_mode = audioMode.value; syncState(); };
    audioLabel.appendChild(audioMode); inspector.appendChild(audioLabel);

    const shotSections = document.createElement("div");
    shotSections.className = "mmx-shot-sections";
    inspector.appendChild(shotSections);
    modeSelect.disabled = !!activeClip.locked;
    const shotExtras = document.createElement("details"); const extrasTitle = document.createElement("summary"); extrasTitle.textContent = "Shot models, guides and grading";
    shotExtras.appendChild(extrasTitle); shotSections.appendChild(shotExtras);
    const modelOverride = document.createElement("input"); modelOverride.placeholder = "Named model override";
    modelOverride.value = activeClip.model_override || "";
    modelOverride.onchange = () => { activeClip.model_override = modelOverride.value.trim(); syncState(); };
    shotExtras.appendChild(modelOverride);
    const guideRows = document.createElement("div"); shotExtras.appendChild(guideRows);
    const drawGuides = () => {
      guideRows.replaceChildren();
      (activeClip.guides || []).forEach((guide, index) => {
        const line = document.createElement("div");
        const reference = document.createElement("select");
        for (const row of timelineState.available_refs || []) {
          const option = document.createElement("option"); option.value = row.id; option.textContent = row.name || row.id; reference.appendChild(option);
        }
        reference.value = guide.ref_id || "";
        reference.onchange = () => { guide.ref_id = reference.value; syncState(); };
        const time = document.createElement("input"); time.type = "number"; time.min = "0"; time.step = ".041666667"; time.value = guide.time || 0; time.title = "Anchor time in seconds";
        time.onchange = () => { guide.time = Number(time.value); syncState(); };
        const remove = document.createElement("button"); remove.textContent = "Remove anchor";
        remove.onclick = () => { activeClip.guides.splice(index,1); syncState(); drawGuides(); };
        line.append(reference,time,remove); guideRows.appendChild(line);
      });
    };
    const addGuide = document.createElement("button"); addGuide.textContent = "Add interior anchor";
    addGuide.onclick = () => { (activeClip.guides ||= []).push({ ref_id: timelineState.available_refs?.[0]?.id || "", time: 0 }); syncState(); drawGuides(); };
    shotExtras.appendChild(addGuide); drawGuides();
    for (const [key, label, low, high, fallback] of [["exposure","Exposure",-10,10,0],["contrast","Contrast",0,4,1],["saturation","Saturation",0,4,1]]) {
      const wrap = document.createElement("label"); wrap.textContent = label;
      const input = document.createElement("input"); input.type = "range"; input.min = low; input.max = high; input.step = ".05"; input.value = activeClip.color?.[key] ?? fallback;
      const value = document.createElement("span"); value.textContent = input.value;
      input.oninput = () => { (activeClip.color ||= {})[key] = Number(input.value); value.textContent = input.value; syncState(); };
      wrap.append(input,value); shotExtras.appendChild(wrap);
    }

    if (["V2V", "RV2V"].includes(activeClip.type)) {
      const sourcePanel = document.createElement("fieldset");
      const legend = document.createElement("legend"); legend.textContent = "Source video range";
      sourcePanel.appendChild(legend); inspector.appendChild(sourcePanel);
      const filename = document.createElement("select");
      const blank = document.createElement("option"); blank.value = ""; blank.textContent = "Choose a video from Reference Pack"; filename.append(blank);
      const currentSource = typeof activeClip.source === "string" ? activeClip.source : activeClip.source?.filename || "";
      const videos = (timelineState.available_refs || []).filter(row => row.type === "video" && row.filename);
      if (currentSource && !videos.some(row => row.filename === currentSource)) videos.push({filename:currentSource,name:"Saved source (legacy project)"});
      for (const row of videos) {const option=document.createElement("option");option.value=row.filename;option.textContent=row.name;filename.append(option);}
      filename.value=currentSource;
      filename.onchange=async()=>{
        if (!filename.value) return;
        const info=await requestJson(`/minimax_director/source/info?filename=${encodeURIComponent(filename.value)}`);
        activeClip.source={filename:filename.value};activeClip.source_start=0;
        if (info.duration>0) {activeClip.source_end=info.duration;activeClip.duration=info.duration;}
        activeClip.validated=false;syncState();renderTimeline();
      };
      sourcePanel.append(filename);
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
        input.onchange = () => {
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
        const shots = Array.from({ length: count }, (_, index) => ({
          ...JSON.parse(JSON.stringify(activeClip)), id: `source_${stamp}_${index}`,
          name: `${activeClip.name || "Source"} ${index + 1}`,
          source_start: start + (end - start) * index / count,
          source_end: start + (end - start) * (index + 1) / count,
          duration: (end - start) / count, validated: false,
        }));
        timelineState.clips.splice(timelineState.clips.indexOf(activeClip), 1, ...shots);
        activeClipId = shots[0].id; syncState(); renderTimeline();
      };
      sourcePanel.appendChild(split);
      const replaceSourceRanges = (cuts) => {
        const start = Number(activeClip.source_start || 0);
        const end = Number(activeClip.source_end ?? start+(activeClip.duration || 5));
        cuts = [...new Set(cuts)].filter(value => Number.isFinite(value) && value > start && value < end).sort((a,b) => a-b);
        if (!cuts.length) throw new Error("No split boundaries lie inside this source range.");
        const bounds = [start, ...cuts, end];
        const shots = bounds.slice(0,-1).map((value,index) => ({ ...JSON.parse(JSON.stringify(activeClip)),
          id: `source_${crypto.randomUUID()}`, name: `${activeClip.name || "Source"} ${index+1}`, source_start: value,
          source_end: bounds[index+1], duration: bounds[index+1]-value, validated: false, locked: false }));
        timelineState.clips.splice(timelineState.clips.indexOf(activeClip), 1, ...shots);
        activeClipId = shots[0].id; syncState(); renderTimeline();
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
        const nextFile = typeof next?.source === "string" ? next.source : next?.source?.filename;
        if (!next || nextFile !== filename.value || Math.abs(Number(activeClip.source_end)-Number(next.source_start)) > 1/24) { alert("The next shot must use the same source and a contiguous range."); return; }
        activeClip.source_end = next.source_end; activeClip.duration = activeClip.source_end-(activeClip.source_start || 0);
        activeClip.prompt = [activeClip.prompt, next.prompt].filter(Boolean).join("\n");
        activeClip.ref_ids = [...new Set([...(activeClip.ref_ids || []), ...(next.ref_ids || [])])];
        activeClip.validated = false; timelineState.clips.splice(index+1,1); syncState(); renderTimeline();
      }; sourcePanel.appendChild(merge);

      if (activeClip.locked) for (const control of sourcePanel.querySelectorAll("input,button")) control.disabled = control !== pickFrame;
    }

    const loraPanel = document.createElement("details");
    const loraHeading = document.createElement("summary");
    loraHeading.textContent = "Shot LoRAs";
    loraPanel.appendChild(loraHeading);
    shotSections.appendChild(loraPanel);
    if (!Array.isArray(activeClip.loras)) activeClip.loras = [];
    const loraRows = document.createElement("div");
    loraPanel.appendChild(loraRows);
    const drawLoras = () => {
      loraRows.replaceChildren();
      activeClip.loras.forEach((row, index) => {
        const controls = document.createElement("div");
        controls.style.cssText = "display:flex;gap:6px;margin:6px 0;align-items:center";
        const enabled = document.createElement("input");
        enabled.type = "checkbox";
        enabled.checked = row.enabled !== false;
        enabled.onchange = () => { row.enabled = enabled.checked; syncState(); };
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
        name.onchange = () => { row.name = name.value; syncState(); };
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
        strength.onchange = () => { row.strength = Number(strength.value); syncState(); };
        const remove = document.createElement("button"); remove.textContent = "Remove";
        remove.onclick = () => { activeClip.loras.splice(index, 1); syncState(); drawLoras(); };
        controls.append(enabled, name, strength, info, remove); loraRows.appendChild(controls);
      });
    };
    const addLora = document.createElement("button"); addLora.textContent = "Add LoRA";
    addLora.onclick = () => {
      if (activeClip.loras.length >= 8) return;
      activeClip.loras.push({ name: "", strength: 1, enabled: true }); syncState(); drawLoras();
    };
    loraPanel.appendChild(addLora); drawLoras();

    // Card 1: Timing & Seam Continuity
    const cardTiming = document.createElement("div");
    cardTiming.className = "mmx-inspector-card";

    const timingHeader = document.createElement("div");
    timingHeader.className = "mmx-inspector-card-title";
    timingHeader.innerHTML = "<span>⏱️</span><span>Timing & Seam Continuity</span>";
    cardTiming.appendChild(timingHeader);

    const timingRow = document.createElement("div");
    timingRow.className = "mmx-inspector-card-row";

    // 1. Duration Controls
    const durItem = document.createElement("div");
    durItem.className = "mmx-ctrl-item";
    const durLabel = document.createElement("label");
    durLabel.textContent = "Duration:";
    durItem.appendChild(durLabel);

    const durSlider = document.createElement("input");
    durSlider.type = "range";
    durSlider.min = "0.5";
    durSlider.max = "30.0";
    durSlider.step = "0.1";
    durSlider.value = String(activeClip.duration || 5.0);
    durSlider.style.width = "75px";

    const durNum = document.createElement("input");
    durNum.type = "number";
    durNum.min = "0.5";
    durNum.max = "60.0";
    durNum.step = "0.1";
    durNum.value = String(activeClip.duration || 5.0);
    durNum.style.width = "56px";
    durNum.style.background = "var(--comfy-input-bg, #333333)";
    durNum.style.border = "1px solid var(--border-color, #4a4a4a)";
    durNum.style.borderRadius = "4px";
    durNum.style.color = "#f8fafc";
    durNum.style.fontSize = "11px";
    durNum.style.textAlign = "center";

    const durUnit = document.createElement("span");
    durUnit.className = "mmx-ctrl-unit";
    durUnit.textContent = "s";

    const durFramesBadge = document.createElement("span");
    durFramesBadge.style.fontSize = "10px";
    durFramesBadge.style.color = "#94a3b8";
    durFramesBadge.style.marginLeft = "2px";
    durFramesBadge.textContent = `(${Math.round((activeClip.duration || 5.0) * 24)}f)`;

    ["mousedown", "pointerdown", "touchstart"].forEach((evt) => {
      durSlider.addEventListener(evt, (e) => e.stopPropagation());
      durNum.addEventListener(evt, (e) => e.stopPropagation());
    });

    durSlider.oninput = () => {
      const v = Math.max(0.5, Math.min(60.0, parseFloat(durSlider.value) || 5.0));
      activeClip.duration = v;
      durNum.value = String(v);
      durFramesBadge.textContent = `(${Math.round(v * 24)}f)`;
      const activeBlock = shotsLane.querySelector(`.mmx-subtrack-block.active`);
      if (activeBlock) {
        const baseW = Math.max(160, Math.min(450, Math.round(v * 32 * zoomLevel)));
        activeBlock.style.width = `${baseW}px`;
      }
    };

    durSlider.onchange = () => {
      syncState();
      renderTimeline();
      drawRuler();
    };

    durNum.onchange = () => {
      const v = Math.max(0.5, Math.min(60.0, parseFloat(durNum.value) || 5.0));
      activeClip.duration = v;
      durSlider.value = String(v);
      durFramesBadge.textContent = `(${Math.round(v * 24)}f)`;
      syncState();
      renderTimeline();
      drawRuler();
    };

    durItem.appendChild(durSlider);
    durItem.appendChild(durNum);
    durItem.appendChild(durUnit);
    durItem.appendChild(durFramesBadge);
    timingRow.appendChild(durItem);

    // 2. Seam Overlap Controls (Canonical MiniMax H3 17k+5 Options + Custom)
    const tailItem = document.createElement("div");
    tailItem.className = "mmx-ctrl-item";
    tailItem.title = "Seam continuity overlap in frames (MiniMax H3 17k+5 grid). 0f disables continuity (hard cut).";

    const tailLabel = document.createElement("label");
    tailLabel.textContent = "Seam Overlap:";
    tailItem.appendChild(tailLabel);

    // Determine current frames value
    let currentFrames = 22;
    if (activeClip.continuity === false) {
      currentFrames = 0;
    } else if (activeClip.tail_frames !== undefined) {
      currentFrames = parseInt(activeClip.tail_frames, 10);
    } else if (activeClip.tail_seconds !== undefined) {
      currentFrames = Math.round(parseFloat(activeClip.tail_seconds) * 24);
    }

    const canonicalChoices = [
      { val: 0, label: "0f (Off - Hard Cut)" },
      { val: 5, label: "5f (~0.2s - Quick Blend)" },
      { val: 22, label: "22f (~0.9s - Default)" },
      { val: 39, label: "39f (~1.6s - Deep Blend)" },
      { val: 56, label: "56f (~2.3s - Extended)" },
    ];

    const tailSelect = document.createElement("select");
    tailSelect.className = "mmx-select mmx-continuity-select";
    tailSelect.style.fontSize = "11px";
    tailSelect.style.padding = "2px 6px";
    tailSelect.style.background = "var(--comfy-input-bg, #333333)";
    tailSelect.style.border = "1px solid var(--border-color, #4a4a4a)";
    tailSelect.style.borderRadius = "4px";
    tailSelect.style.color = "#f8fafc";

    let isCanonical = false;
    canonicalChoices.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = String(c.val);
      opt.textContent = c.label;
      if (c.val === currentFrames) {
        opt.selected = true;
        isCanonical = true;
      }
      tailSelect.appendChild(opt);
    });

    const customOpt = document.createElement("option");
    customOpt.value = "custom";
    customOpt.textContent = `Custom (${currentFrames}f)...`;
    if (!isCanonical) customOpt.selected = true;
    tailSelect.appendChild(customOpt);

    const tailNum = document.createElement("input");
    tailNum.type = "number";
    tailNum.min = "0";
    tailNum.max = "240";
    tailNum.step = "1";
    tailNum.value = String(currentFrames);
    tailNum.style.width = "56px";
    tailNum.style.background = "var(--comfy-input-bg, #333333)";
    tailNum.style.border = "1px solid var(--border-color, #4a4a4a)";
    tailNum.style.borderRadius = "4px";
    tailNum.style.color = "#f8fafc";
    tailNum.style.fontSize = "11px";
    tailNum.style.textAlign = "center";
    tailNum.style.marginLeft = "4px";
    tailNum.style.display = isCanonical ? "none" : "inline-block";

    ["mousedown", "pointerdown", "touchstart"].forEach((evt) => {
      tailSelect.addEventListener(evt, (e) => e.stopPropagation());
      tailNum.addEventListener(evt, (e) => e.stopPropagation());
    });

    const setContinuity = (f) => {
      activeClip.continuity = f > 0;
      activeClip.tail_frames = f;
      activeClip.tail_seconds = f / 24.0;
      syncState();
      renderTimeline();
    };

    tailSelect.onchange = () => {
      const val = tailSelect.value;
      if (val === "custom") {
        tailNum.style.display = "inline-block";
        tailNum.focus();
      } else {
        tailNum.style.display = "none";
        const f = parseInt(val, 10) || 0;
        tailNum.value = String(f);
        setContinuity(f);
      }
    };

    tailNum.onchange = () => {
      const f = Math.max(0, parseInt(tailNum.value, 10) || 0);
      tailNum.value = String(f);
      customOpt.textContent = `Custom (${f}f)...`;
      customOpt.selected = true;
      setContinuity(f);
    };

    tailItem.appendChild(tailSelect);
    tailItem.appendChild(tailNum);
    timingRow.appendChild(tailItem);
    cardTiming.appendChild(timingRow);
    cardsGrid.appendChild(cardTiming);

    // Card 2: Seed & Generation Parameters
    const cardSampling = document.createElement("div");
    cardSampling.className = "mmx-inspector-card";

    const samplingHeader = document.createElement("div");
    samplingHeader.className = "mmx-inspector-card-title";
    samplingHeader.innerHTML = "<span>🎲</span><span>Seed & Advance Mode</span>";
    cardSampling.appendChild(samplingHeader);

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
    seedInput.style.width = "90px";
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
      activeClip.seed = newSeed;
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

    cardSampling.appendChild(samplingRow);
    cardsGrid.appendChild(cardSampling);

    inspector.appendChild(cardsGrid);

    // 1. Local References Pool Selector (Includes Images, Videos, Audios, RefMods)
    const refsPoolWrap = document.createElement("div");
    refsPoolWrap.className = "mmx-local-refs-pool";

    const refsTitle = document.createElement("div");
    refsTitle.className = "mmx-local-refs-title";
    refsTitle.innerHTML = `
      <span>LOCAL REFERENCES (FROM REF PACK):</span>
      <span style="font-weight: 500; font-size: 9px; color: #64748b;">Click to assign to this shot</span>
    `;
    refsPoolWrap.appendChild(refsTitle);

    const refsList = document.createElement("div");
    refsList.className = "mmx-local-refs-list";

    if (!Array.isArray(activeClip.ref_ids)) activeClip.ref_ids = [];

    const allRefs = timelineState.available_refs || [];
    refsPoolWrap.hidden = allRefs.length === 0;
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

      item.onclick = () => {
        if (isChecked) {
          activeClip.ref_ids = activeClip.ref_ids.filter((id) => id !== r.id);
        } else {
          activeClip.ref_ids.push(r.id);
        }
        syncState();
        renderTimeline();
      };
      refsList.appendChild(item);
    });

    refsPoolWrap.appendChild(refsList);
    inspector.appendChild(refsPoolWrap);

    // 2. Dedicated Per-Clip Shot Prompt (Raw Mode vs Structured Mode)
    const promptWrap = document.createElement("div");
    promptWrap.className = "mmx-prompt-inspector";

    const promptToolbar = document.createElement("div");
    promptToolbar.className = "mmx-prompt-toolbar";

    const promptTitle = document.createElement("div");
    promptTitle.style.fontSize = "10px";
    promptTitle.style.fontWeight = "700";
    promptTitle.style.color = "#818cf8";
    promptTitle.textContent = `PROMPT FOR ${String(activeClip.name || activeClip.id || "Shot").toUpperCase()}:`;
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
      grid.appendChild(createField("summary", "summary:", false, false, "[reference generation] Cinematic sequence for this shot with atmospheric lighting..."));
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
      const tags = (activeClip.ref_ids || []).map(id => (timelineState.available_refs || []).find(row => row.id === id)).filter(Boolean).map(row => {
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
      promptWrap.appendChild(rawSubToolbar);

      const promptArea = document.createElement("textarea");
      promptArea.className = "mmx-textarea";
      promptArea.style.flex = "1";
      promptArea.style.height = "100%";
      promptArea.style.minHeight = "100px";
      promptArea.placeholder = `Describe the action, camera movement and sound. Assign references from the connected pool to insert their tokens.`;
      promptArea.value = activeClip.prompt || "";
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
      const topY = getTopWidgetsHeight(n || node);
      this.last_y = topY;
      if (origDomDraw) origDomDraw.call(this, ctx, n, widget_width, topY, widget_height);
    };

    // Move domWidget to beginning of node.widgets (index 0) so hidden widgets don't push it down
    if (node.widgets) {
      const idx = node.widgets.indexOf(domWidget);
      if (idx > 0) {
        node.widgets.splice(idx, 1);
        node.widgets.unshift(domWidget);
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
    if (domWidget) domWidget.last_y = topY;
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
    if (domWidget) domWidget.last_y = topY;
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
    if (domWidget) domWidget.last_y = topY;
    if (origOnDrawForeground) origOnDrawForeground.apply(this, arguments);
  };

  const origOnConnectionsChange = node.onConnectionsChange;
  node.onConnectionsChange = function () {
    if (origOnConnectionsChange) origOnConnectionsChange.apply(this, arguments);
    resolveAvailableRefsFromGraph();
    syncState();
    renderTimeline();
    if (activeClipId) renderInspector();
  };

  // Ensure domWidget is positioned at the TOP of node.widgets (index 0) so it starts flush at widgets_start_y
  if (node.widgets && domWidget) {
    const topY = getTopWidgetsHeight(node);
    domWidget.last_y = topY;
    const domIdx = node.widgets.indexOf(domWidget);
    if (domIdx > 0) {
      node.widgets.splice(domIdx, 1);
      node.widgets.unshift(domWidget);
    }
  }

  // Refresh callback when node configuration or graph is reloaded
  node.__mmxDirectorRefresh = () => {
    const topY = getTopWidgetsHeight(node);
    node.widgets_start_y = topY;
    if (domWidget) domWidget.last_y = topY;
    hideWidget(timelineWidget);
    hideWidget(builderWidget);
    hideWidget(promptWidget);
    hideWidget(durationWidget);
    if (node.widgets && domWidget) {
      const domIdx = node.widgets.indexOf(domWidget);
      if (domIdx > 0) {
        node.widgets.splice(domIdx, 1);
        node.widgets.unshift(domWidget);
      }
    }
    loadState();
    renderTimeline();

  };

  // Backend updates only the shot actually completed; clip-by-clip and selection
  // do not advance unrelated shot seeds.
  node.__mmxShotHandler = event => {
    const detail = event.detail;
    if (!detail || String(detail.node) !== String(node.id) || detail.project_id !== timelineState.project_id) return;
    progressLabel.textContent = `${detail.phase} · ${detail.clip_id} · ${detail.index || ""}/${detail.total || ""}`;
    if (detail.phase === "completed") {

      const shot = timelineState.clips.find(value => value.id === detail.clip_id);
      if (shot) {
        shot.last_seed = detail.seed;
        if (String(shot.seed ?? detail.authored_seed) === detail.authored_seed) shot.seed = detail.next_seed;
        syncState(); renderInspector();
      }
    }
  };
  if (!node.__mmxShotListener) {
    node.__mmxShotListener = event => node.__mmxShotHandler?.(event);
    api.addEventListener("minimax_director/shot", node.__mmxShotListener);
    const removed = node.onRemoved;
    node.onRemoved = function (...args) {
      node.__mmxDisposed = true;
      for (const observers of node.__mmxRefObserverSets || []) observers.delete(node.__mmxRefObserver);
      node.__mmxRefObserverSets?.clear();
      cancelTimelineDrag?.();

      node.__mmxLocaleCleanup?.();
      api.removeEventListener("minimax_director/shot", node.__mmxShotListener);
      node.__mmxShotHandler = null; node.__mmxShotListener = null;
      return removed?.apply(this, args);
    };
  }

}

// Dynamic RefPack widget visibility: hide unconnected label text boxes to avoid canvas clutter
// Dynamic RefPack widget visibility (no-op as label text boxes have been removed)
const updateRefPackWidgets = (node) => {};

app.registerExtension({
  name: "ComfyUI.MiniMaxH3MasterDirector",
  init: () => console.log("[DirectorUI] Extension initialized"),

  beforeConfigureGraph(graphData) {
    // Upgrade saved UI workflows before ComfyUI resolves node types.
    for (const node of graphData?.nodes || []) {
      if (node.type === "MiniMaxH3MasterDirector") node.type = "MiniMaxH3MasterNode";
      // Earlier examples omitted ComfyUI's workflow-only seed control.
      // Preserve the seed and all subsequent Settings fields during import.
      if (node.type === "MiniMaxH3DirectorSettings" && Array.isArray(node.widgets_values)
          && node.widgets_values.length === 16 && !node.widgets_values_named) {
        node.widgets_values.splice(10, 0, "fixed");
      }
      if (node.type === "MiniMaxH3DirectorSettings" && Array.isArray(node.widgets_values) && node.widgets_values.length === 17) {
        const old = node.widgets_values, mode = old[11] === "Conditioning Guide Output" ? "Conditioning only" : old[13] === "full_batch" ? "All shots" : "Next shot";
        node.widgets_values = [...old.slice(0,11), mode, old[14], old[15]];
        if (node.widgets_values_named) {
          node.widgets_values_named.generation_mode = mode;
          for (const key of ["execution_mode","run_mode","prompt_mode","preview_mode"]) delete node.widgets_values_named[key];
        }
      }
      if (node.type === "MiniMaxH3VideoCombine" && Array.isArray(node.widgets_values)
          && node.widgets_values.length === 16 && !node.widgets_values_named) {
        // The pre-consolidation exporter used FFmpeg and had no backend widget.
        node.widgets_values.splice(3, 0, "ffmpeg");
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
        } else if (values.length === 2) {
          const w1 = this.widgets.find((x) => x.name === "timeline_data");
          if (w1) w1.value = values[0];
          const w2 = this.widgets.find((x) => x.name === "builder_state");
          if (w2) w2.value = values[1];
        } else if (values.length > 2) {
          const w1 = this.widgets.find((x) => x.name === "timeline_data");
          if (w1) w1.value = values[values.length - 2];
          const w2 = this.widgets.find((x) => x.name === "builder_state");
          if (w2) w2.value = values[values.length - 1];
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
