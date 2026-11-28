"use client";

import type { BadgeLayout } from "@/lib/types";

/**
 * Предпросмотр карточки прямо в браузере: viewBox задан в миллиметрах, поэтому
 * координаты разметки подставляются в SVG как есть.
 *
 * Рисуется по несохранённому состоянию формы — админ видит результат, пока
 * двигает числа, без похода на сервер. Серверный предпросмотр
 * (GET /badges/preview) показывает, что нарисует настоящий рендерер.
 */

/** Кегль задан в пунктах при печати; 1 pt = 25,4/72 мм. */
function ptToMm(pt: number) {
  return (pt * 25.4) / 72;
}

/**
 * Оценка ширины строки — та же средняя ширина глифа, что в мок-бэкенде
 * (backend/badgepdf.go). Точные метрики шрифта здесь не нужны: предпросмотр
 * показывает расположение, а не типографику.
 */
function estWidth(s: string, sizeMm: number) {
  return s.length * sizeMm * 0.58;
}

/** Повторяет автоподбор кегля из pdf-generation/main.go: сначала перенос, потом уменьшение. */
function fitLines(text: string, boxW: number, cfg: BadgeLayout["name"]) {
  const tryWrap = (sizePt: number): string[] | null => {
    const sizeMm = ptToMm(sizePt);
    if (!cfg.wrap) return estWidth(text, sizeMm) <= boxW ? [text] : null;

    const words = text.split(/\s+/).filter(Boolean);
    if (words.length === 0) return [""];

    const lines = [words[0]];
    for (const word of words.slice(1)) {
      const last = lines.length - 1;
      const candidate = `${lines[last]} ${word}`;
      if (estWidth(candidate, sizeMm) <= boxW) lines[last] = candidate;
      else lines.push(word);
    }
    if (lines.length > cfg.max_lines) return null;
    // Одно слово шире окна переносом уже не спасти.
    if (lines.some((l) => estWidth(l, sizeMm) > boxW)) return null;
    return lines;
  };

  for (let size = cfg.max_font_pt; size > cfg.min_font_pt; size--) {
    const lines = tryWrap(size);
    if (lines) return { sizePt: size, lines };
  }
  return { sizePt: cfg.min_font_pt, lines: tryWrap(cfg.min_font_pt) ?? [text] };
}

export default function BadgePreview({
  layout,
  name,
  backgroundUrl,
  className,
}: {
  layout: BadgeLayout;
  name: string;
  backgroundUrl?: string;
  className?: string;
}) {
  const { badge, photo, name: nameCfg } = layout;
  const w = badge.width_mm || 1;
  const h = badge.height_mm || 1;

  const startX = w * nameCfg.x_start_fraction;
  const endX = w * nameCfg.x_end_fraction;
  const boxW = Math.max(endX - startX, 1);
  const centerX = (startX + endX) / 2;

  const { sizePt, lines } = fitLines(name, boxW, nameCfg);
  const sizeMm = ptToMm(sizePt);
  const lineH = sizeMm * nameCfg.line_spacing;
  const firstY = h * nameCfg.y_fraction - ((lines.length - 1) * lineH) / 2;

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className={className}
      style={{ width: "100%", maxWidth: 420, height: "auto" }}
      role="img"
      aria-label="Предпросмотр бейджа"
    >
      {backgroundUrl ? (
        <image href={backgroundUrl} x={0} y={0} width={w} height={h} preserveAspectRatio="none" />
      ) : (
        <>
          {/* Стандартный фон: светлое поле + тёмная шапка */}
          <rect x={0} y={0} width={w} height={h} fill="#f4f5f7" />
          <rect x={0} y={0} width={w} height={h * 0.22} fill="#1a1a2e" />
          <text
            x={w / 2}
            y={h * 0.11}
            fill="#ffffff"
            fontSize={h * 0.09}
            fontWeight="bold"
            textAnchor="middle"
            dominantBaseline="central"
            fontFamily="Segoe UI, Arial, sans-serif"
          >
            АККРЕДИТАЦИЯ
          </text>
        </>
      )}

      {/* Рамка карточки — линия реза */}
      <rect x={0} y={0} width={w} height={h} fill="none" stroke="#cbd5e1" strokeWidth={0.2} />

      {photo.enabled && (
        <rect
          x={photo.x_mm}
          y={photo.y_mm}
          width={photo.width_mm}
          height={photo.height_mm}
          rx={photo.corner_radius_mm}
          fill="#d8dae0"
          stroke="#94a3b8"
          strokeWidth={0.2}
          strokeDasharray="1 0.6"
        />
      )}

      {/* Границы окна ФИО — служебная подсказка, на печать не идёт */}
      <rect
        x={startX}
        y={firstY - lineH}
        width={boxW}
        height={lines.length * lineH + lineH * 0.5}
        fill="none"
        stroke="#94a3b8"
        strokeWidth={0.15}
        strokeDasharray="0.8 0.8"
        opacity={0.6}
      />

      {lines.map((line, i) => (
        <text
          key={i}
          x={centerX}
          y={firstY + i * lineH}
          fill={nameCfg.color}
          fontSize={sizeMm}
          fontWeight="bold"
          textAnchor="middle"
          dominantBaseline="central"
          fontFamily="Segoe UI, Arial, sans-serif"
        >
          {line}
        </text>
      ))}
    </svg>
  );
}
