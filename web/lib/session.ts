const encoder = new TextEncoder();

function hex(buffer: ArrayBuffer) {
  return [...new Uint8Array(buffer)].map((value) => value.toString(16).padStart(2, "0")).join("");
}

export async function signSession(secret: string, expiresAt: number) {
  const payload = `v1.${expiresAt}`;
  const key = await crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(payload));
  return `${payload}.${hex(signature)}`;
}

export async function verifySession(token: string | undefined, secret: string) {
  if (!token || !secret) return false;
  const parts = token.split(".");
  if (parts.length !== 3) return false;
  const expiresAt = Number(parts[1]);
  if (parts[0] !== "v1" || !Number.isFinite(expiresAt) || expiresAt < Date.now()) return false;
  const expected = await signSession(secret, expiresAt);
  const left = encoder.encode(token);
  const right = encoder.encode(expected);
  if (left.length !== right.length) return false;
  let diff = 0;
  for (let index = 0; index < left.length; index += 1) diff |= left[index] ^ right[index];
  return diff === 0;
}

export function passwordsMatch(given: string, expected: string) {
  const left = encoder.encode(given);
  const right = encoder.encode(expected);
  if (!expected || left.length !== right.length) return false;
  let diff = 0;
  for (let index = 0; index < left.length; index += 1) diff |= left[index] ^ right[index];
  return diff === 0;
}
