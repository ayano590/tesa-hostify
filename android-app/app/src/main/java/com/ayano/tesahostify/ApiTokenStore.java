package com.ayano.tesahostify;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

final class ApiTokenStore {
    private static final String KEY_ALIAS = "hostify_read_api_token";
    private static final String PREFS_NAME = "connection_settings";
    private static final String TOKEN_KEY = "encrypted_api_token";

    private final SharedPreferences preferences;

    ApiTokenStore(Context context) {
        preferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    void save(String token) throws GeneralSecurityException {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey());
        byte[] iv = cipher.getIV();
        byte[] encrypted = cipher.doFinal(token.getBytes(StandardCharsets.UTF_8));
        ByteBuffer packed = ByteBuffer.allocate(1 + iv.length + encrypted.length);
        packed.put((byte) iv.length);
        packed.put(iv);
        packed.put(encrypted);
        preferences.edit()
                .putString(TOKEN_KEY, Base64.encodeToString(packed.array(), Base64.NO_WRAP))
                .apply();
    }

    String load() throws GeneralSecurityException {
        String encoded = preferences.getString(TOKEN_KEY, null);
        if (encoded == null) {
            return null;
        }

        byte[] packedBytes;
        try {
            packedBytes = Base64.decode(encoded, Base64.NO_WRAP);
        } catch (IllegalArgumentException e) {
            throw new GeneralSecurityException("Stored token is invalid.", e);
        }
        if (packedBytes.length < 2) {
            throw new GeneralSecurityException("Stored token is invalid.");
        }

        ByteBuffer packed = ByteBuffer.wrap(packedBytes);
        int ivLength = Byte.toUnsignedInt(packed.get());
        if (ivLength == 0 || packed.remaining() <= ivLength) {
            throw new GeneralSecurityException("Stored token is invalid.");
        }
        byte[] iv = new byte[ivLength];
        packed.get(iv);
        byte[] encrypted = new byte[packed.remaining()];
        packed.get(encrypted);

        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(), new GCMParameterSpec(128, iv));
        return new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8);
    }

    String getBaseUrl() {
        return preferences.getString("base_url", "");
    }

    void saveBaseUrl(String baseUrl) {
        preferences.edit().putString("base_url", baseUrl).apply();
    }

    private SecretKey getOrCreateKey() throws GeneralSecurityException {
        try {
            KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
            keyStore.load(null);
            java.security.Key existing = keyStore.getKey(KEY_ALIAS, null);
            if (existing instanceof SecretKey) {
                return (SecretKey) existing;
            }

            KeyGenerator generator = KeyGenerator.getInstance(
                    KeyProperties.KEY_ALGORITHM_AES,
                    "AndroidKeyStore"
            );
            generator.init(new KeyGenParameterSpec.Builder(
                    KEY_ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT
            )
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setRandomizedEncryptionRequired(true)
                    .build());
            return generator.generateKey();
        } catch (java.io.IOException | java.security.KeyStoreException
                 | java.security.NoSuchAlgorithmException
                 | java.security.UnrecoverableKeyException
                 | java.security.cert.CertificateException
                 | java.security.InvalidAlgorithmParameterException e) {
            throw new GeneralSecurityException("Unable to access secure token storage.", e);
        }
    }
}
