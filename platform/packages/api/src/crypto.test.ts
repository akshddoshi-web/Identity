import { beforeEach, describe, expect, it } from "vitest";
import { decryptSecret, encryptSecret } from "./crypto";

describe("encryptSecret / decryptSecret", () => {
  beforeEach(() => {
    process.env.ENCRYPTION_KEY = "test-encryption-key-please-ignore";
  });

  it("round-trips a plaintext secret", () => {
    const plaintext = "access-sandbox-abc123";
    const encrypted = encryptSecret(plaintext);
    expect(encrypted).not.toContain(plaintext);
    expect(decryptSecret(encrypted)).toBe(plaintext);
  });

  it("produces a different ciphertext each time (random IV)", () => {
    const a = encryptSecret("same-value");
    const b = encryptSecret("same-value");
    expect(a).not.toBe(b);
  });

  it("throws when ENCRYPTION_KEY is missing", () => {
    delete process.env.ENCRYPTION_KEY;
    expect(() => encryptSecret("x")).toThrow();
  });

  it("throws on a tampered payload", () => {
    const encrypted = encryptSecret("value");
    const tampered = encrypted.slice(0, -4) + "abcd";
    expect(() => decryptSecret(tampered)).toThrow();
  });
});
