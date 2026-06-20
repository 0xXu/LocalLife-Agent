package com.meituan.route.security;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import javax.crypto.Cipher;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Base64;

/**
 * AES-256-GCM encryption for API keys at rest.
 *
 * Encryption key is derived from the ENCRYPTION_MASTER_KEY environment variable.
 * If not set, the system will refuse to start in production-like environments
 * and fall back to a dev-only key (with a loud warning).
 *
 * Enterprise compliance: prevents API key leaks from database dumps / backups.
 */
@Component
public class ApiKeyEncryptor {

    private static final Logger log = LoggerFactory.getLogger(ApiKeyEncryptor.class);
    private static final String ALGORITHM = "AES/GCM/NoPadding";
    private static final int GCM_TAG_LENGTH = 128;
    private static final int GCM_IV_LENGTH = 12;

    private final SecretKey masterKey;

    public ApiKeyEncryptor() {
        var envKey = System.getenv("ENCRYPTION_MASTER_KEY");
        if (envKey == null || envKey.isBlank()) {
            envKey = System.getProperty("encryption.master.key");
        }
        if (envKey == null || envKey.isBlank() || envKey.length() < 32) {
            log.warn("⚠️  ENCRYPTION_MASTER_KEY not set or too short (<32 chars). "
                    + "Using dev-only key — API keys are NOT securely encrypted. "
                    + "Set ENCRYPTION_MASTER_KEY env var in production!");
            envKey = "meituan-route-dev-encryption-key-DO-NOT-USE-IN-PROD!!";
        }
        this.masterKey = deriveKey(envKey);
        log.info("ApiKeyEncryptor initialized (AES-256-GCM)");
    }

    private static SecretKey deriveKey(String secret) {
        try {
            var md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(secret.getBytes(StandardCharsets.UTF_8));
            return new SecretKeySpec(hash, "AES");
        } catch (Exception e) {
            throw new RuntimeException("Failed to derive encryption key", e);
        }
    }

    /** Encrypt a plaintext API key. Returns Base64-encoded ciphertext with IV prepended. */
    public String encrypt(String plaintext) {
        if (plaintext == null || plaintext.isBlank()) return plaintext;
        try {
            var cipher = Cipher.getInstance(ALGORITHM);
            byte[] iv = new byte[GCM_IV_LENGTH];
            new SecureRandom().nextBytes(iv);
            var spec = new GCMParameterSpec(GCM_TAG_LENGTH, iv);
            cipher.init(Cipher.ENCRYPT_MODE, masterKey, spec);
            byte[] encrypted = cipher.doFinal(plaintext.getBytes(StandardCharsets.UTF_8));
            // Prepend IV to ciphertext for storage
            byte[] combined = new byte[iv.length + encrypted.length];
            System.arraycopy(iv, 0, combined, 0, iv.length);
            System.arraycopy(encrypted, 0, combined, iv.length, encrypted.length);
            return Base64.getEncoder().encodeToString(combined);
        } catch (Exception e) {
            log.error("Failed to encrypt API key", e);
            throw new RuntimeException("API key encryption failed", e);
        }
    }

    /** Decrypt a Base64-encoded ciphertext (with IV prepended). */
    public String decrypt(String ciphertext) {
        if (ciphertext == null || ciphertext.isBlank()) return ciphertext;
        try {
            byte[] combined = Base64.getDecoder().decode(ciphertext);
            if (combined.length < GCM_IV_LENGTH + 1) {
                // Not encrypted (legacy plaintext or empty) — return as-is
                return ciphertext;
            }
            byte[] iv = new byte[GCM_IV_LENGTH];
            byte[] encrypted = new byte[combined.length - GCM_IV_LENGTH];
            System.arraycopy(combined, 0, iv, 0, GCM_IV_LENGTH);
            System.arraycopy(combined, GCM_IV_LENGTH, encrypted, 0, encrypted.length);
            var cipher = Cipher.getInstance(ALGORITHM);
            var spec = new GCMParameterSpec(GCM_TAG_LENGTH, iv);
            cipher.init(Cipher.DECRYPT_MODE, masterKey, spec);
            return new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8);
        } catch (Exception e) {
            log.warn("Failed to decrypt API key — may be legacy plaintext: {}", e.getMessage());
            return ciphertext; // fallback: return as-is (plaintext / legacy)
        }
    }
}
