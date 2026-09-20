import { HttpResponse } from '@angular/common/http';

/**
 * Save a blob response to disk.
 *
 * The filename comes from Content-Disposition when the server sent one, so the
 * name a recruiter sees matches what the API decided rather than being
 * reconstructed in two places.
 */
export function saveResponse(response: HttpResponse<Blob>, fallback: string): void {
  const body = response.body;
  if (!body) return;

  const url = URL.createObjectURL(body);
  const link = document.createElement('a');
  link.href = url;
  link.download = filenameFrom(response.headers.get('Content-Disposition')) || fallback;
  document.body.appendChild(link);
  link.click();
  link.remove();

  // Revoking immediately can cancel the download in some browsers.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Open a blob in a new tab — used for the offer letter, which is meant to be read. */
export function openResponse(response: HttpResponse<Blob>): void {
  if (!response.body) return;
  const url = URL.createObjectURL(response.body);
  window.open(url, '_blank');
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

function filenameFrom(header: string | null): string | null {
  if (!header) return null;
  // RFC 5987 form first (filename*=UTF-8''...), then the plain quoted form.
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1]);
    } catch {
      /* fall through to the plain form */
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header);
  return plain ? plain[1].trim() : null;
}
