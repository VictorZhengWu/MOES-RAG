/**
 * Document upload API functions.
 *
 * WHAT: Uploads a file to M8's /api/v1/documents/upload endpoint which
 *       proxies to M1 for parsing. Returns the parse result including
 *       markdown, tables, and metadata.
 *
 * WHY: M6 frontend has drag-and-drop UI but needs a real API call to
 *      actually parse and store documents. Previously this was a P10
 *      placeholder — the UI worked but files were never processed.
 */

import type { FileAttachment } from '@/types';

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export interface UploadResult {
  filename: string;
  parse_result: {
    success: boolean;
    doc_id: string;
    markdown: string;
    page_count: number;
    table_count: number;
    metadata: Record<string, unknown>;
    m2_status: string;
  };
}

export async function uploadDocument(
  file: File,
  token?: string,
): Promise<UploadResult> {
  const formData = new FormData();
  formData.append('file', file, file.name);
  formData.append('output_dir', './output');

  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}/api/v1/documents/upload`, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Upload failed: ${res.status}`);
  }

  return res.json();
}

/**
 * Upload multiple files and return their parse results.
 * Updates each attachment's status field during the upload.
 */
export async function uploadDocuments(
  attachments: FileAttachment[],
  token?: string,
  onProgress?: (idx: number, status: FileAttachment['status']) => void,
): Promise<UploadResult[]> {
  const results: UploadResult[] = [];

  for (let i = 0; i < attachments.length; i++) {
    const att = attachments[i];
    if (!att.file) continue;

    onProgress?.(i, 'uploading');
    try {
      const result = await uploadDocument(att.file, token);
      att.status = 'uploaded';
      results.push(result);
      onProgress?.(i, 'uploaded');
    } catch {
      att.status = 'error';
      onProgress?.(i, 'error');
    }
  }

  return results;
}
