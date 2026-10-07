import type { CertificateFont } from "@/features/workshop-exams/api/workshop-exams-api";

/** How each certificate font looks in the browser (the PDF uses the same fonts), shared by the designer and the review. */
export const FONT_CSS: Record<CertificateFont, { family: string; style: string; weight: number; label: string; script: boolean }> = {
  sans_bold: { family: "Helvetica, Arial, sans-serif", style: "normal", weight: 700, label: "Sans-serif bold", script: false },
  serif_bold: { family: "'Times New Roman', Times, serif", style: "normal", weight: 700, label: "Serif bold", script: false },
  serif_bold_italic: { family: "'Times New Roman', Times, serif", style: "italic", weight: 700, label: "Serif bold italic", script: false },
  great_vibes: { family: "'Great Vibes', cursive", style: "normal", weight: 400, label: "Great Vibes (elegant script)", script: true },
  allura: { family: "Allura, cursive", style: "normal", weight: 400, label: "Allura (flowing script)", script: true },
  alex_brush: { family: "'Alex Brush', cursive", style: "normal", weight: 400, label: "Alex Brush (brush script)", script: true },
  pinyon_script: { family: "'Pinyon Script', cursive", style: "normal", weight: 400, label: "Pinyon Script (formal)", script: true },
  parisienne: { family: "Parisienne, cursive", style: "normal", weight: 400, label: "Parisienne (casual script)", script: true },
};
export const PLAIN_FONTS = (Object.keys(FONT_CSS) as CertificateFont[]).filter((key) => !FONT_CSS[key].script);
export const SCRIPT_FONTS = (Object.keys(FONT_CSS) as CertificateFont[]).filter((key) => FONT_CSS[key].script);


let measureContext: CanvasRenderingContext2D | null | undefined;

/** Width and vertical metrics of `text` in the given font, to place the preview exactly where the PDF draws it. */
export function measureText(text: string, key: CertificateFont, sizePx: number) {
  if (measureContext === undefined) measureContext = document.createElement("canvas").getContext("2d");
  const font = FONT_CSS[key];
  if (!measureContext || sizePx <= 0) return { width: 0, ascent: sizePx * 0.8, descent: sizePx * 0.2 };
  measureContext.font = `${font.style} ${font.weight} ${sizePx}px ${font.family}`;
  const m = measureContext.measureText(text);
  return {
    width: m.width,
    ascent: m.fontBoundingBoxAscent ?? sizePx * 0.8,
    descent: m.fontBoundingBoxDescent ?? sizePx * 0.2,
  };
}

/** Distance from the top of a line box (line-height 1) down to the text baseline. */
export const baselineOffset = (sizePx: number, ascent: number, descent: number) => (sizePx - (ascent + descent)) / 2 + ascent;
