/**
 * upload.js — Drag & drop file upload zone
 * Handles file selection, drag-over states and file preview chips
 */

'use strict';

const Upload = (() => {

  const MAX_FILES    = 10;
  const MAX_SIZE_MB  = 20;
  const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/heic', 'image/webp'];

  const zone      = qs('#dropZone');
  const input     = qs('#fileInput');
  const listEl    = qs('#fileList');

  let selectedFiles = [];

  // ── Validate a single file ─────────────────────────────────

  const isValid = (file) => {
    if (!ALLOWED_TYPES.includes(file.type) && !file.name.match(/\.(jpe?g|png|heic|webp)$/i)) {
      alert(`El archivo "${file.name}" no es un formato de imagen admitido.`);
      return false;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      alert(`El archivo "${file.name}" supera el límite de ${MAX_SIZE_MB} MB.`);
      return false;
    }
    return true;
  };

  // ── Add files to selection ─────────────────────────────────

  const addFiles = (files) => {
    const incoming = Array.from(files);
    const remaining = MAX_FILES - selectedFiles.length;

    if (remaining <= 0) {
      alert(`Máximo ${MAX_FILES} archivos permitidos.`);
      return;
    }

    incoming.slice(0, remaining).forEach((file) => {
      if (!isValid(file)) return;
      // Avoid duplicates by name + size
      const exists = selectedFiles.some(
        (f) => f.name === file.name && f.size === file.size
      );
      if (!exists) selectedFiles.push(file);
    });

    renderList();
  };

  // ── Remove a file by index ─────────────────────────────────

  const removeFile = (index) => {
    selectedFiles.splice(index, 1);
    renderList();
  };

  // ── Render file chips ──────────────────────────────────────

  const renderList = () => {
    if (!listEl) return;
    listEl.innerHTML = '';

    selectedFiles.forEach((file, i) => {
      const chip = document.createElement('div');
      chip.className = 'upload-chip';
      chip.setAttribute('role', 'listitem');
      chip.innerHTML = `
        <span aria-hidden="true">🖼️</span>
        <span>${file.name.length > 28 ? file.name.substring(0, 26) + '…' : file.name}</span>
        <span class="upload-chip__size">${formatBytes(file.size)}</span>
        <button
          type="button"
          aria-label="Eliminar ${file.name}"
          style="margin-left:auto;background:none;border:none;cursor:pointer;color:var(--color-warm-gray);font-size:0.75rem;padding:0;"
          data-index="${i}"
        >✕</button>
      `;
      chip.querySelector('button').addEventListener('click', () => removeFile(i));
      listEl.appendChild(chip);
    });
  };

  // ── Drag & drop events ─────────────────────────────────────

  const init = () => {
    if (!zone || !input) return;

    // Click to open file picker
    zone.addEventListener('click', (e) => {
      if (e.target === zone || e.target.closest('.upload-zone')) {
        input.click();
      }
    });

    // Keyboard accessibility
    zone.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        input.click();
      }
    });

    // File input change
    input.addEventListener('change', () => {
      addFiles(input.files);
      input.value = ''; // reset so same file can be re-added if removed
    });

    // Drag events
    zone.addEventListener('dragover', (e) => {
      e.preventDefault();
      zone.classList.add('upload-zone--dragover');
    });

    zone.addEventListener('dragleave', (e) => {
      if (!zone.contains(e.relatedTarget)) {
        zone.classList.remove('upload-zone--dragover');
      }
    });

    zone.addEventListener('drop', (e) => {
      e.preventDefault();
      zone.classList.remove('upload-zone--dragover');
      addFiles(e.dataTransfer.files);
    });
  };

  // ── Public API ─────────────────────────────────────────────

  const getFiles = () => selectedFiles;

  return { init, getFiles };

})();
