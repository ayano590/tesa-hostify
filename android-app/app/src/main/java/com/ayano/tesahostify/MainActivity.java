package com.ayano.tesahostify;

import android.app.Activity;
import android.graphics.Typeface;
import android.os.Bundle;
import android.text.InputType;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URISyntaxException;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private ApiTokenStore tokenStore;
    private EditText baseUrlInput;
    private EditText tokenInput;
    private TextView statusText;
    private LinearLayout resultsLayout;
    private Button locksButton;
    private Button reservationsButton;
    private Button saveButton;
    private String currentToken;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        tokenStore = new ApiTokenStore(this);
        buildHomeScreen();
        baseUrlInput.setText(tokenStore.getBaseUrl());
        try {
            currentToken = tokenStore.load();
        } catch (GeneralSecurityException e) {
            currentToken = null;
            setStatus(getString(R.string.status_token_unlocked_failed));
        }
        tokenInput.setHint(currentToken == null
                ? getString(R.string.hint_token_empty)
                : getString(R.string.hint_token_saved));
    }

    private void buildHomeScreen() {
        ScrollView scrollView = new ScrollView(this);
        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(24), dp(24), dp(24), dp(24));
        scrollView.addView(page);

        TextView title = new TextView(this);
        title.setText(R.string.title_home);
        title.setTextSize(28);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        page.addView(title, matchWrap());

        TextView subtitle = new TextView(this);
        subtitle.setText(R.string.subtitle_home);
        subtitle.setTextSize(16);
        subtitle.setPadding(0, dp(6), 0, dp(18));
        page.addView(subtitle, matchWrap());

        addLabel(page, getString(R.string.label_server_address));
        baseUrlInput = new EditText(this);
        baseUrlInput.setSingleLine(true);
        baseUrlInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        baseUrlInput.setHint(R.string.hint_server_address);
        page.addView(baseUrlInput, matchWrap());

        addLabel(page, getString(R.string.label_api_token));
        tokenInput = new EditText(this);
        tokenInput.setSingleLine(true);
        tokenInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        tokenInput.setHint(R.string.hint_token_empty);
        page.addView(tokenInput, matchWrap());

        saveButton = new Button(this);
        saveButton.setText(R.string.button_save_connection);
        saveButton.setOnClickListener(view -> saveConnection());
        page.addView(saveButton, matchWrap());

        locksButton = new Button(this);
        locksButton.setText(R.string.button_show_locks);
        locksButton.setOnClickListener(view -> requestData("/api/locks", true));
        LinearLayout.LayoutParams buttonParams = matchWrap();
        buttonParams.topMargin = dp(16);
        page.addView(locksButton, buttonParams);

        reservationsButton = new Button(this);
        reservationsButton.setText(R.string.button_show_reservations);
        reservationsButton.setOnClickListener(view -> requestData("/api/reservations", false));
        page.addView(reservationsButton, matchWrap());

        statusText = new TextView(this);
        statusText.setTextSize(15);
        statusText.setPadding(0, dp(14), 0, dp(8));
        page.addView(statusText, matchWrap());

        resultsLayout = new LinearLayout(this);
        resultsLayout.setOrientation(LinearLayout.VERTICAL);
        page.addView(resultsLayout, matchWrap());

        setContentView(scrollView);
    }

    private void addLabel(LinearLayout parent, String text) {
        TextView label = new TextView(this);
        label.setText(text);
        label.setTextSize(14);
        label.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        label.setPadding(0, dp(10), 0, 0);
        parent.addView(label, matchWrap());
    }

    private void saveConnection() {
        try {
            String baseUrl = validateBaseUrl(baseUrlInput.getText().toString());
            tokenStore.saveBaseUrl(baseUrl);
            String newToken = tokenInput.getText().toString().trim();
            if (!newToken.isEmpty()) {
                tokenStore.save(newToken);
                currentToken = newToken;
                tokenInput.setText("");
                tokenInput.setHint(R.string.hint_token_saved);
            } else if (currentToken == null || currentToken.isEmpty()) {
                currentToken = tokenStore.load();
            }
            if (currentToken == null || currentToken.isEmpty()) {
                setStatus(getString(R.string.status_enter_token));
                return;
            }
            setStatus(getString(R.string.status_saved));
        } catch (IllegalArgumentException e) {
            setStatus(e.getMessage());
        } catch (GeneralSecurityException e) {
            setStatus(getString(R.string.status_save_failed));
        }
    }

    private void requestData(String endpoint, boolean locks) {
        final String baseUrl;
        final String token;
        try {
            baseUrl = validateBaseUrl(baseUrlInput.getText().toString());
            tokenStore.saveBaseUrl(baseUrl);
            String newToken = tokenInput.getText().toString().trim();
            if (!newToken.isEmpty()) {
                tokenStore.save(newToken);
                currentToken = newToken;
                tokenInput.setText("");
                tokenInput.setHint(R.string.hint_token_saved);
            }
            if (currentToken == null || currentToken.isEmpty()) {
                currentToken = tokenStore.load();
            }
            if (currentToken == null || currentToken.isEmpty()) {
                setStatus(getString(R.string.status_enter_token));
                return;
            }
            token = currentToken;
        } catch (IllegalArgumentException e) {
            setStatus(e.getMessage());
            return;
        } catch (GeneralSecurityException e) {
            setStatus(getString(R.string.status_read_failed));
            return;
        }

        setBusy(true);
        resultsLayout.removeAllViews();
        setStatus(getString(R.string.status_loading));
        executor.execute(() -> {
            try {
                JSONObject response = getJson(baseUrl + endpoint, token);
                runOnUiThread(() -> {
                    setBusy(false);
                    setStatus(getString(locks ? R.string.status_current_locks : R.string.status_reservations));
                    if (locks) {
                        showLocks(response.optJSONArray("locks"));
                    } else {
                        showReservations(response.optJSONArray("reservations"));
                    }
                });
            } catch (IOException | JSONException e) {
                runOnUiThread(() -> {
                    setBusy(false);
                    setStatus(e.getMessage() == null ? getString(R.string.status_request_failed) : e.getMessage());
                });
            }
        });
    }

    private JSONObject getJson(String address, String token) throws IOException, JSONException {
        HttpURLConnection connection;
        try {
            connection = (HttpURLConnection) URI.create(address).toURL().openConnection();
        } catch (IllegalArgumentException e) {
            throw new IOException("The server address is invalid.", e);
        }
        try {
            connection.setRequestMethod("GET");
            connection.setConnectTimeout(15000);
            connection.setReadTimeout(30000);
            connection.setRequestProperty("Accept", "application/json");
            connection.setRequestProperty("Authorization", "Bearer " + token);
            connection.setRequestProperty("Cache-Control", "no-store");

            int statusCode = connection.getResponseCode();
            if (statusCode == HttpURLConnection.HTTP_UNAUTHORIZED) {
                throw new IOException("Access denied. Check the saved API token.");
            } else if (statusCode < 200 || statusCode >= 300) {
                throw new IOException("The server returned HTTP " + statusCode + ".");
            }
            try (InputStream stream = connection.getInputStream()) {
                return new JSONObject(new String(readAll(stream), StandardCharsets.UTF_8));
            }
        } finally {
            connection.disconnect();
        }
    }

    private byte[] readAll(InputStream input) throws IOException {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[4096];
        int count;
        while ((count = input.read(buffer)) != -1) {
            output.write(buffer, 0, count);
        }
        return output.toByteArray();
    }

    private void showLocks(JSONArray locks) {
        if (locks == null || locks.length() == 0) {
            addResultLine(getString(R.string.no_locks_returned));
            return;
        }
        for (int i = 0; i < locks.length(); i++) {
            JSONObject lock = locks.optJSONObject(i);
            if (lock != null) {
                addResultCard(
                        "Room " + lock.optString("room_number", "?") + " · " + lock.optString("provider", "Lock"),
                        "Door code: " + displayValue(lock.optString("door_code", ""))
                );
            }
        }
    }

    private void showReservations(JSONArray reservations) {
        if (reservations == null || reservations.length() == 0) {
            addResultLine(getString(R.string.no_reservations_found));
            return;
        }
        for (int i = 0; i < reservations.length(); i++) {
            JSONObject reservation = reservations.optJSONObject(i);
            if (reservation != null) {
                String details = "Check-in: " + displayValue(reservation.optString("check_in", ""))
                        + "\nCheck-out: " + displayValue(reservation.optString("check_out", ""))
                        + "\nStatus: " + displayValue(reservation.optString("lifecycle_status", ""))
                        + "\nDoor code: " + displayValue(reservation.optString("door_code", ""));
                addResultCard(
                        "Room " + reservation.optString("room_number", "?")
                                + " · " + reservation.optString("reservation_id", "Reservation"),
                        details
                );
            }
        }
    }

    private String displayValue(String value) {
        return value == null || value.trim().isEmpty() ? "—" : value;
    }

    private void addResultLine(String text) {
        TextView result = new TextView(this);
        result.setText(text);
        result.setTextSize(16);
        resultsLayout.addView(result, matchWrap());
    }

    private void addResultCard(String heading, String body) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(14), dp(12), dp(14), dp(12));
        card.setBackgroundColor(0xFFF1F4F8);

        TextView title = new TextView(this);
        title.setText(heading);
        title.setTextSize(17);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        card.addView(title, matchWrap());

        TextView details = new TextView(this);
        details.setText(body);
        details.setTextSize(16);
        details.setPadding(0, dp(6), 0, 0);
        card.addView(details, matchWrap());

        LinearLayout.LayoutParams params = matchWrap();
        params.bottomMargin = dp(10);
        resultsLayout.addView(card, params);
    }

    private void setStatus(String message) {
        statusText.setText(message);
    }

    private void setBusy(boolean busy) {
        locksButton.setEnabled(!busy);
        reservationsButton.setEnabled(!busy);
        saveButton.setEnabled(!busy);
    }

    private String validateBaseUrl(String value) {
        String baseUrl = value.trim().replaceAll("/+$", "");
        try {
            URI uri = new URI(baseUrl);
            if (!"https".equalsIgnoreCase(uri.getScheme())
                    || uri.getHost() == null
                    || uri.getUserInfo() != null
                    || uri.getQuery() != null
                    || uri.getFragment() != null) {
                throw new IllegalArgumentException("Enter a valid HTTPS server address.");
            }
            return baseUrl;
        } catch (URISyntaxException e) {
            throw new IllegalArgumentException("Enter a valid HTTPS server address.", e);
        }
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }
}
