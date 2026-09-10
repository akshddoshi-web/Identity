import { createCipheriv, createDecipheriv, randomBytes, scryptSync } from "node:crypto";

/**
 * AES-256-GCM encryption at rest for sensitive tokens (Plaid access tokens,
 * third-party API keys stored per-user). Never log or return the plaintext
 * outside this module. ENCRYPTION_KEY must be a 32+ char secret; derived
 * into a proper 256-bit key via scrypt with a fixed salt (acceptable here
 * because the *key* itself, not a password, is the high-entropy secret).
 */
const ALGORITHM = "aes-256-gcm";

function deriveKey(): Buffer {
  const secret = process.env.ENCRYPTION_KEY;
  if (!secret || secret.length < 16) {
    throw new Error(
      "ENCRYPTION_KEY env var must be set to a random secret of at least 16 characters",
    );
  }
  return scryptSync(secret, "identity-platform-static-salt", 32);
}

export function encryptSecret(plaintext: string): string {
  const key = deriveKey();
  const iv = randomBytes(12);
  const cipher = createCipheriv(ALGORITHM, key, iv);
  const encrypted = Buffer.concat([cipher.update(plaintext, "utf8"), cipher.final()]);
  const authTag = cipher.getAuthTag();
  return [iv.toString("base64"), authTag.toString("base64"), encrypted.toString("base64")].join(
    ".",
  );
}

export function decryptSecret(payload: string): string {
  const [ivB64, authTagB64, encryptedB64] = payload.split(".");
  if (!ivB64 || !authTagB64 || !encryptedB64) {
    throw new Error("malformed encrypted payload");
  }
  const key = deriveKey();
  const decipher = createDecipheriv(ALGORITHM, key, Buffer.from(ivB64, "base64"));
  decipher.setAuthTag(Buffer.from(authTagB64, "base64"));
  const decrypted = Buffer.concat([
    decipher.update(Buffer.from(encryptedB64, "base64")),
    decipher.final(),
  ]);
  return decrypted.toString("utf8");
}
