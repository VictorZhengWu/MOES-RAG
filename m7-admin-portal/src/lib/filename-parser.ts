/**
 * Parse structured filenames into document metadata.
 *
 * Expected format: [SocietyCode][CategoryCode][SectionCode][DocumentName][YYYYMM]
 * Examples:
 *   [DNV][RU-SHIP][Pt.1-Ch.1][General regulations][202507]
 *   [DNV][OS][D201][Electrical installations][202507]
 *   [ABS][Pt.5B][Sec.3-2][Fatigue assessment][202501]
 *
 * WHY: Filenames carry structured metadata, eliminating the need for
 * a separate directory/catalog. Parsing happens client-side before
 * upload so the user can review and confirm the extracted metadata.
 */

export interface ParsedDocument {
  /** Raw filename (without extension) */
  raw: string;
  /** Whether the filename matched the expected pattern */
  valid: boolean;
  /** Classification society code, e.g. "DNV", "ABS", "CCS" */
  society?: string;
  /** Category/rule-set code, e.g. "RU-SHIP", "OS", "CG-0040" */
  category?: string;
  /** Section/chapter code, e.g. "Pt.1-Ch.1", "D201" */
  section?: string;
  /** Human-readable document name */
  name?: string;
  /** Version as YYYYMM string, e.g. "202507" */
  version?: string;
  /** Parse error message if invalid */
  error?: string;
}

const RE_FILENAME = /\[([A-Z]+)\]\[([A-Z\-0-9]+)\]\[([^\]]+)\]\[([^\]]+)\]\[(\d{6})\]/;

/** Supported file formats for upload */
export const SUPPORTED_FORMATS = ['.pdf', '.docx', '.doc', '.md', '.html', '.htm', '.txt'];
export const SUPPORTED_FORMATS_DISPLAY = 'PDF, DOCX, DOC, MD, HTML, TXT';

/** Max file size: 500MB */
export const MAX_FILE_SIZE = 500 * 1024 * 1024;

export interface ParseResult {
  valid: boolean;
  parsed?: ParsedDocument;
  errors: string[];
}

/**
 * Parse a filename string into structured metadata.
 * Strips file extension before parsing. Checks format support.
 *
 * WHY: Two-phase validation — first check the extension is supported,
 * then check the filename pattern. Separate errors for each.
 */
export function parseFilename(filename: string): ParsedDocument {
  // Check file extension
  const dotIndex = filename.lastIndexOf('.');
  const ext = dotIndex > 0 ? filename.substring(dotIndex).toLowerCase() : '';
  const raw = dotIndex > 0 ? filename.substring(0, dotIndex) : filename;

  if (ext && !SUPPORTED_FORMATS.includes(ext)) {
    return {
      raw: filename,
      valid: false,
      error: `Unsupported file format "${ext}". Supported: ${SUPPORTED_FORMATS_DISPLAY}`,
    };
  }

  const match = raw.match(RE_FILENAME);

  if (!match) {
    return {
      raw: filename,
      valid: false,
      error: `Filename does not match expected pattern: [Society][Category][Section][Name][YYYYMM]${ext || '.pdf'}`,
    };
  }

  const [, society, category, section, name, version] = match;

  return {
    raw: filename,
    valid: true,
    society,
    category,
    section,
    name,
    version,
  };
}

/**
 * Batch parse a list of filenames.
 * Returns valid and invalid results separately for easy handling.
 */
export function batchParse(filenames: string[]): {
  valid: ParsedDocument[];
  invalid: ParsedDocument[];
} {
  const results = filenames.map(parseFilename);
  return {
    valid: results.filter((r) => r.valid),
    invalid: results.filter((r) => !r.valid),
  };
}

/**
 * Format version YYYYMM → display string.
 * e.g. "202507" → "2025-07"
 */
export function formatVersion(version?: string): string {
  if (!version || version.length !== 6) return version || '—';
  return `${version.substring(0, 4)}-${version.substring(4, 6)}`;
}
