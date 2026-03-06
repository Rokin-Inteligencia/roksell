"use client";

import { useState, useRef, useCallback, useEffect } from "react";

const BANNER_WIDTH = 1200;
const BANNER_HEIGHT = 400;
const ASPECT = BANNER_WIDTH / BANNER_HEIGHT;

type BannerCropModalProps = {
  file: File;
  onConfirm: (file: File) => void;
  onCancel: () => void;
};

export function BannerCropModal({ file, onConfirm, onCancel }: BannerCropModalProps) {
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    setObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const handleConfirm = useCallback(() => {
    const img = imgRef.current;
    const container = containerRef.current;
    const overlay = overlayRef.current;
    if (!img || !container || !overlay || !objectUrl) return;

    const naturalW = img.naturalWidth;
    const naturalH = img.naturalHeight;
    const overlayRect = overlay.getBoundingClientRect();
    const imgElRect = img.getBoundingClientRect();
    const scaleX = naturalW / imgElRect.width;
    const scaleY = naturalH / imgElRect.height;

    const sx = (overlayRect.left - imgElRect.left) * scaleX;
    const sy = (overlayRect.top - imgElRect.top) * scaleY;
    const sW = overlayRect.width * scaleX;
    const sH = overlayRect.height * scaleY;

    const canvas = document.createElement("canvas");
    canvas.width = BANNER_WIDTH;
    canvas.height = BANNER_HEIGHT;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.drawImage(img, sx, sy, sW, sH, 0, 0, BANNER_WIDTH, BANNER_HEIGHT);

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const croppedFile = new File([blob], file.name, { type: file.type });
        onConfirm(croppedFile);
      },
      file.type || "image/jpeg",
      0.92
    );
  }, [file, objectUrl, onConfirm]);

  const onMouseDown = (e: React.MouseEvent) => {
    setDragging(true);
    setDragStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
  };
  const onMouseMove = (e: React.MouseEvent) => {
    if (!dragging) return;
    setOffset({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  };
  const onMouseUp = () => setDragging(false);

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        <div className="p-4 border-b border-slate-200">
          <h3 className="text-lg font-semibold text-slate-900">Ajustar imagem do banner</h3>
          <p className="text-sm text-slate-600 mt-1">
            Dimensões da plataforma: <strong>{BANNER_WIDTH} × {BANNER_HEIGHT} px</strong>. Use o zoom e arraste a imagem para enquadrar na área roxa.
          </p>
        </div>
        <div
          ref={containerRef}
          className="relative flex-1 min-h-[280px] bg-slate-100 overflow-hidden flex items-center justify-center"
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseUp}
        >
          {objectUrl && (
            <div
              className="absolute inset-0 flex items-center justify-center cursor-move"
              onMouseDown={onMouseDown}
              style={{ touchAction: "none" }}
            >
              <img
                ref={imgRef}
                src={objectUrl}
                alt="Banner"
                className="max-w-none select-none pointer-events-none object-contain"
                style={{
                  maxWidth: "100%",
                  maxHeight: "100%",
                  transform: `scale(${zoom}) translate(${offset.x / zoom}px, ${offset.y / zoom}px)`,
                }}
                draggable={false}
              />
            </div>
          )}
          <div
            ref={overlayRef}
            className="absolute pointer-events-none border-4 border-[#6320ee] border-dashed rounded-lg bg-[#6320ee]/5"
            style={{
              aspectRatio: String(ASPECT),
              maxHeight: "calc(100% - 2rem)",
              maxWidth: "calc(100% - 2rem)",
              width: "min(100% - 2rem, (100% - 2rem) * 3)",
              height: "min(100% - 2rem, (100% - 2rem) / 3)",
            }}
          />
        </div>
        <div className="p-4 border-t border-slate-200 flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <span className="text-slate-600">Zoom:</span>
            <input
              type="range"
              min={0.5}
              max={3}
              step={0.1}
              value={zoom}
              onChange={(e) => setZoom(Number(e.target.value))}
              className="w-32"
            />
            <span className="font-mono text-slate-700">{Math.round(zoom * 100)}%</span>
          </label>
          <div className="flex-1" />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              className="px-4 py-2 rounded-lg bg-[#6320ee] text-white font-semibold hover:brightness-95"
            >
              Aplicar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
