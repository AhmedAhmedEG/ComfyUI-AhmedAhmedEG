// Pointer-based shot reordering. Coordinates account for the graph's CSS zoom.
export function bindShotDrag({block, getGroups, scrollArea, move, select, setCleanup}) {
  let suppressClick = false;
  block.addEventListener("click", event => {
    if (suppressClick) { event.stopImmediatePropagation(); suppressClick = false; }
  }, true);
  block.addEventListener("pointerdown", event => {
    if (event.button !== 0 || event.target.closest("button,input,select,textarea,.mmx-clip-handle")) return;
    event.preventDefault(); event.stopPropagation();
    select();
    const startX = event.clientX;
    const width = block.getBoundingClientRect().width;
    const scale = width / (block.offsetWidth || width) || 1;
    const startScroll = scrollArea.scrollLeft;
    const groups = getGroups();
    const own = groups.find(group => group[0] === block);
    block.setPointerCapture?.(event.pointerId);
    let dragging = false, destination = -1;
    const clearMarks = () => groups.flat().forEach(el => el.classList.remove("mmx-drop-before", "mmx-drop-after"));
    const finish = cancelled => {
      window.removeEventListener("pointermove", onMove, true);
      window.removeEventListener("pointerup", onUp, true);
      window.removeEventListener("pointercancel", onCancel, true);
      window.removeEventListener("blur", onCancel);
      block.removeEventListener("lostpointercapture", onCancel);
      if (block.hasPointerCapture?.(event.pointerId)) block.releasePointerCapture(event.pointerId);
      clearMarks(); own.forEach(el => { el.style.transform = ""; el.classList.remove("mmx-dragging"); });
      setCleanup(null);
      suppressClick = dragging;
      if (!cancelled && dragging && destination >= 0) move(destination);
    };
    const onMove = current => {
      if (current.pointerId !== event.pointerId) return;
      current.preventDefault(); current.stopPropagation();
      const delta = current.clientX - startX;
      if (!dragging && Math.abs(delta) < 6) return;
      dragging = true;
      const bounds = scrollArea.getBoundingClientRect();
      // A drop outside the editor cancels instead of leaving translated cards
      // clipped out of view. Captured listeners also see events over the canvas.
      if (bounds.width > 0 && (current.clientX < bounds.left - 20 || current.clientX > bounds.right + 20 || current.clientY < bounds.top - 40 || current.clientY > bounds.bottom + 40)) {
        finish(true); return;
      }
      if (current.clientX > bounds.right - 35) scrollArea.scrollLeft += 12;
      if (current.clientX < bounds.left + 35) scrollArea.scrollLeft -= 12;
      own.forEach(el => { el.classList.add("mmx-dragging"); el.style.transform = `translateX(${delta / scale + scrollArea.scrollLeft - startScroll}px)`; });
      const others = groups.filter(group => group !== own);
      destination = others.findIndex(group => { const rect = group[0].getBoundingClientRect(); return current.clientX < rect.left + rect.width / 2; });
      if (destination < 0) destination = others.length;
      clearMarks();
      const marker = others[destination] || others[others.length - 1];
      marker?.forEach(el => el.classList.add(destination < others.length ? "mmx-drop-before" : "mmx-drop-after"));
    };
    const onUp = current => { if (current.pointerId === event.pointerId) { current.stopPropagation(); finish(false); } };
    const onCancel = () => finish(true);
    setCleanup(onCancel);
    window.addEventListener("pointermove", onMove, true);
    window.addEventListener("pointerup", onUp, true);
    window.addEventListener("pointercancel", onCancel, true);
    window.addEventListener("blur", onCancel);
    block.addEventListener("lostpointercapture", onCancel);
  });
}
