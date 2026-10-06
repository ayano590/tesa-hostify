package com.ayano.tesahostify;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.PopupMenu;
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
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final int PAGE_HOME = 0;
    private static final int PAGE_CREDENTIALS = 1;
    private static final int PAGE_DISCORD = 2;

    private static final DateTimeFormatter RESERVATION_DATE_FORMAT =
            DateTimeFormatter.ofPattern("d. MMMM, HH:mm", Locale.ENGLISH);

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private ApiTokenStore tokenStore;
    private boolean isDarkMode;

    private ScrollView scrollView;
    private LinearLayout homePage;
    private LinearLayout credentialsPage;
    private LinearLayout discordPage;

    private EditText baseUrlInput;
    private EditText tokenInput;

    private TextView statusText;
    private TextView credentialsStatusText;
    private TextView discordStatusText;
    private LinearLayout resultsLayout;

    private Button ttlockCodesButton;
    private Button tesaPinsButton;
    private Button reservationsButton;
    private Button sendReportButton;
    private Button saveButton;

    private Button homeThemeButton;
    private Button credentialsThemeButton;
    private Button discordThemeButton;
    private Button settingsButton;

    private String currentToken;

    private static final class AppTheme {
        final boolean isDark;
        final int pageBg;
        final int cardBg;
        final int titleText;
        final int subtitleText;
        final int labelText;
        final int inputBg;
        final int inputText;
        final int inputHint;
        final int buttonBg;
        final int buttonText;

        AppTheme(boolean isDark) {
            this.isDark = isDark;
            if (isDark) {
                pageBg = 0xFF111827;
                cardBg = 0xFF1F2937;
                titleText = 0xFFF9FAFB;
                subtitleText = 0xFF9CA3AF;
                labelText = 0xFFE5E7EB;
                inputBg = 0xFF1F2937;
                inputText = 0xFFF9FAFB;
                inputHint = 0xFF6B7280;
                buttonBg = 0xFF374151;
                buttonText = 0xFFF9FAFB;
            } else {
                pageBg = 0xFFFFFFFF;
                cardBg = 0xFFF1F4F8;
                titleText = 0xFF111827;
                subtitleText = 0xFF4B5563;
                labelText = 0xFF1F2937;
                inputBg = 0xFFF3F4F8;
                inputText = 0xFF111827;
                inputHint = 0xFF9CA3AF;
                buttonBg = 0xFFE5E7EB;
                buttonText = 0xFF1F2937;
            }
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        tokenStore = new ApiTokenStore(this);
        tokenStore.clearTtlockSettings();
        isDarkMode = tokenStore.isDarkMode();

        try {
            currentToken = tokenStore.load();
        } catch (GeneralSecurityException e) {
            currentToken = null;
        }

        scrollView = new ScrollView(this);
        buildAllPages();
        showPage(PAGE_HOME);
        setContentView(scrollView);
    }

    private void toggleTheme() {
        isDarkMode = !isDarkMode;
        tokenStore.setDarkMode(isDarkMode);
        applyTheme();
    }

    private void buildAllPages() {
        buildHomePage();
        buildCredentialsPage();
        buildDiscordPage();
        applyTheme();
    }

    private void showPage(int page) {
        scrollView.removeAllViews();
        if (page == PAGE_HOME) {
            scrollView.addView(homePage);
        } else if (page == PAGE_CREDENTIALS) {
            baseUrlInput.setText(tokenStore.getBaseUrl());
            tokenInput.setText("");
            tokenInput.setHint(currentToken == null || currentToken.isEmpty()
                    ? getString(R.string.hint_token_empty)
                    : getString(R.string.hint_token_saved));
            credentialsStatusText.setText("");
            scrollView.addView(credentialsPage);
        } else if (page == PAGE_DISCORD) {
            discordStatusText.setText("");
            scrollView.addView(discordPage);
        }
        applyTheme();
    }

    private void buildHomePage() {
        homePage = new LinearLayout(this);
        homePage.setOrientation(LinearLayout.VERTICAL);
        homePage.setPadding(dp(24), dp(24), dp(24), dp(24));

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);

        TextView title = new TextView(this);
        title.setText(R.string.title_home);
        title.setTextSize(26);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.0f);
        header.addView(title, titleParams);

        homeThemeButton = new Button(this);
        homeThemeButton.setTextSize(18);
        homeThemeButton.setPadding(dp(8), dp(4), dp(8), dp(4));
        homeThemeButton.setMinimumWidth(0);
        homeThemeButton.setMinimumHeight(0);
        homeThemeButton.setOnClickListener(v -> toggleTheme());
        LinearLayout.LayoutParams themeBtnParams = wrapWrap();
        themeBtnParams.rightMargin = dp(4);
        header.addView(homeThemeButton, themeBtnParams);

        settingsButton = new Button(this);
        settingsButton.setText(R.string.button_settings);
        settingsButton.setTextSize(18);
        settingsButton.setPadding(dp(8), dp(4), dp(8), dp(4));
        settingsButton.setMinimumWidth(0);
        settingsButton.setMinimumHeight(0);
        settingsButton.setOnClickListener(this::showSettingsMenu);
        header.addView(settingsButton, wrapWrap());

        homePage.addView(header, matchWrap());

        TextView subtitle = new TextView(this);
        subtitle.setText(R.string.subtitle_home);
        subtitle.setTextSize(15);
        subtitle.setPadding(0, dp(6), 0, dp(18));
        homePage.addView(subtitle, matchWrap());

        ttlockCodesButton = new Button(this);
        ttlockCodesButton.setText(R.string.button_show_ttlock_codes);
        ttlockCodesButton.setOnClickListener(view -> requestData("/api/ttlock-pins", true, false));
        homePage.addView(ttlockCodesButton, matchWrapWithBottomMargin(14));

        tesaPinsButton = new Button(this);
        tesaPinsButton.setText(R.string.button_show_tesa_pins);
        tesaPinsButton.setOnClickListener(view -> requestData("/api/tesa-pins", true, false));
        homePage.addView(tesaPinsButton, matchWrapWithBottomMargin(14));

        reservationsButton = new Button(this);
        reservationsButton.setText(R.string.button_show_reservations);
        reservationsButton.setOnClickListener(view -> requestData("/api/reservations", false, false));
        homePage.addView(reservationsButton, matchWrapWithBottomMargin(14));

        statusText = new TextView(this);
        statusText.setTextSize(15);
        statusText.setPadding(0, dp(14), 0, dp(8));
        homePage.addView(statusText, matchWrap());

        resultsLayout = new LinearLayout(this);
        resultsLayout.setOrientation(LinearLayout.VERTICAL);
        homePage.addView(resultsLayout, matchWrap());

        View bottomSpacer = new View(this);
        homePage.addView(bottomSpacer, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                dp(40)
        ));
    }

    private void showSettingsMenu(View anchor) {
        PopupMenu popup = new PopupMenu(this, anchor);
        popup.getMenu().add(0, 1, 0, R.string.title_credentials);
        popup.getMenu().add(0, 2, 1, R.string.title_discord_report);
        popup.setOnMenuItemClickListener(item -> {
            if (item.getItemId() == 1) {
                showPage(PAGE_CREDENTIALS);
                return true;
            } else if (item.getItemId() == 2) {
                showPage(PAGE_DISCORD);
                return true;
            }
            return false;
        });
        popup.show();
    }

    private void buildCredentialsPage() {
        credentialsPage = new LinearLayout(this);
        credentialsPage.setOrientation(LinearLayout.VERTICAL);
        credentialsPage.setPadding(dp(24), dp(24), dp(24), dp(24));

        LinearLayout topBar = new LinearLayout(this);
        topBar.setOrientation(LinearLayout.HORIZONTAL);
        topBar.setGravity(Gravity.CENTER_VERTICAL);

        Button backButton = new Button(this);
        backButton.setText(R.string.button_back_home);
        backButton.setOnClickListener(v -> showPage(PAGE_HOME));
        LinearLayout.LayoutParams backParams = new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.0f);
        topBar.addView(backButton, backParams);

        credentialsThemeButton = new Button(this);
        credentialsThemeButton.setTextSize(18);
        credentialsThemeButton.setPadding(dp(8), dp(4), dp(8), dp(4));
        credentialsThemeButton.setMinimumWidth(0);
        credentialsThemeButton.setMinimumHeight(0);
        credentialsThemeButton.setOnClickListener(v -> toggleTheme());
        topBar.addView(credentialsThemeButton, wrapWrap());

        credentialsPage.addView(topBar, matchWrap());

        TextView title = new TextView(this);
        title.setText(R.string.title_credentials);
        title.setTextSize(24);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        title.setPadding(0, dp(12), 0, 0);
        credentialsPage.addView(title, matchWrap());

        TextView subtitle = new TextView(this);
        subtitle.setText(R.string.subtitle_credentials);
        subtitle.setTextSize(15);
        subtitle.setPadding(0, dp(4), 0, dp(16));
        credentialsPage.addView(subtitle, matchWrap());

        addLabel(credentialsPage, getString(R.string.label_server_address));
        baseUrlInput = new EditText(this);
        baseUrlInput.setSingleLine(true);
        baseUrlInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        baseUrlInput.setHint(R.string.hint_server_address);
        credentialsPage.addView(baseUrlInput, matchWrap());

        addLabel(credentialsPage, getString(R.string.label_api_token));
        tokenInput = new EditText(this);
        tokenInput.setSingleLine(true);
        tokenInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        tokenInput.setHint(R.string.hint_token_empty);
        credentialsPage.addView(tokenInput, matchWrap());

        saveButton = new Button(this);
        saveButton.setText(R.string.button_save_connection);
        saveButton.setOnClickListener(view -> saveConnection());
        credentialsPage.addView(saveButton, matchWrap());

        credentialsStatusText = new TextView(this);
        credentialsStatusText.setTextSize(15);
        credentialsStatusText.setPadding(0, dp(14), 0, dp(8));
        credentialsPage.addView(credentialsStatusText, matchWrap());
    }

    private void buildDiscordPage() {
        discordPage = new LinearLayout(this);
        discordPage.setOrientation(LinearLayout.VERTICAL);
        discordPage.setPadding(dp(24), dp(24), dp(24), dp(24));

        LinearLayout topBar = new LinearLayout(this);
        topBar.setOrientation(LinearLayout.HORIZONTAL);
        topBar.setGravity(Gravity.CENTER_VERTICAL);

        Button backButton = new Button(this);
        backButton.setText(R.string.button_back_home);
        backButton.setOnClickListener(v -> showPage(PAGE_HOME));
        LinearLayout.LayoutParams backParams = new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.0f);
        topBar.addView(backButton, backParams);

        discordThemeButton = new Button(this);
        discordThemeButton.setTextSize(18);
        discordThemeButton.setPadding(dp(8), dp(4), dp(8), dp(4));
        discordThemeButton.setMinimumWidth(0);
        discordThemeButton.setMinimumHeight(0);
        discordThemeButton.setOnClickListener(v -> toggleTheme());
        topBar.addView(discordThemeButton, wrapWrap());

        discordPage.addView(topBar, matchWrap());

        TextView title = new TextView(this);
        title.setText(R.string.title_discord_report);
        title.setTextSize(24);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        title.setPadding(0, dp(12), 0, 0);
        discordPage.addView(title, matchWrap());

        TextView subtitle = new TextView(this);
        subtitle.setText(R.string.subtitle_discord_report);
        subtitle.setTextSize(15);
        subtitle.setPadding(0, dp(4), 0, dp(16));
        discordPage.addView(subtitle, matchWrap());

        sendReportButton = new Button(this);
        sendReportButton.setText(R.string.button_send_reservation_report);
        sendReportButton.setOnClickListener(view -> requestData("/api/reservations/report", false, true));
        discordPage.addView(sendReportButton, matchWrap());

        discordStatusText = new TextView(this);
        discordStatusText.setTextSize(15);
        discordStatusText.setPadding(0, dp(14), 0, dp(8));
        discordPage.addView(discordStatusText, matchWrap());
    }

    private void addLabel(LinearLayout parent, String text) {
        TextView label = new TextView(this);
        label.setText(text);
        label.setTextSize(14);
        label.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        label.setPadding(0, dp(10), 0, 0);
        parent.addView(label, matchWrap());
    }

    private void applyTheme() {
        AppTheme theme = new AppTheme(isDarkMode);
        String symbol = isDarkMode ? "🌙" : "☀️";

        scrollView.setBackgroundColor(theme.pageBg);
        if (homePage != null) homePage.setBackgroundColor(theme.pageBg);
        if (credentialsPage != null) credentialsPage.setBackgroundColor(theme.pageBg);
        if (discordPage != null) discordPage.setBackgroundColor(theme.pageBg);

        if (homeThemeButton != null) {
            homeThemeButton.setText(symbol);
            styleButton(homeThemeButton, theme);
        }
        if (credentialsThemeButton != null) {
            credentialsThemeButton.setText(symbol);
            styleButton(credentialsThemeButton, theme);
        }
        if (discordThemeButton != null) {
            discordThemeButton.setText(symbol);
            styleButton(discordThemeButton, theme);
        }

        applyContainerTheme(homePage, theme);
        applyContainerTheme(credentialsPage, theme);
        applyContainerTheme(discordPage, theme);

        if (baseUrlInput != null) {
            baseUrlInput.setBackgroundColor(theme.inputBg);
            baseUrlInput.setTextColor(theme.inputText);
            baseUrlInput.setHintTextColor(theme.inputHint);
        }
        if (tokenInput != null) {
            tokenInput.setBackgroundColor(theme.inputBg);
            tokenInput.setTextColor(theme.inputText);
            tokenInput.setHintTextColor(theme.inputHint);
        }

        if (resultsLayout != null) {
            for (int i = 0; i < resultsLayout.getChildCount(); i++) {
                View child = resultsLayout.getChildAt(i);
                if (child instanceof TextView) {
                    ((TextView) child).setTextColor(theme.titleText);
                } else if (child instanceof LinearLayout) {
                    LinearLayout card = (LinearLayout) child;
                    card.setBackgroundColor(theme.cardBg);
                    for (int j = 0; j < card.getChildCount(); j++) {
                        View cardChild = card.getChildAt(j);
                        if (cardChild instanceof TextView) {
                            TextView tv = (TextView) cardChild;
                            if (j == 0) {
                                tv.setTextColor(theme.titleText);
                            } else {
                                tv.setTextColor(theme.subtitleText);
                            }
                        }
                    }
                }
            }
        }
    }

    private void applyContainerTheme(LinearLayout container, AppTheme theme) {
        if (container == null) return;
        for (int i = 0; i < container.getChildCount(); i++) {
            View v = container.getChildAt(i);
            applyViewTheme(v, theme);
        }
    }

    private void applyViewTheme(View v, AppTheme theme) {
        if (v instanceof Button) {
            styleButton((Button) v, theme);
        } else if (v instanceof EditText) {
            EditText et = (EditText) v;
            et.setBackgroundColor(theme.inputBg);
            et.setTextColor(theme.inputText);
            et.setHintTextColor(theme.inputHint);
        } else if (v instanceof TextView) {
            TextView tv = (TextView) v;
            if (tv == statusText || tv == credentialsStatusText || tv == discordStatusText) {
                tv.setTextColor(theme.titleText);
            } else if (tv.getTextSize() >= dp(20)) {
                tv.setTextColor(theme.titleText);
            } else {
                tv.setTextColor(theme.subtitleText);
            }
        } else if (v instanceof LinearLayout) {
            LinearLayout layout = (LinearLayout) v;
            for (int i = 0; i < layout.getChildCount(); i++) {
                applyViewTheme(layout.getChildAt(i), theme);
            }
        }
    }

    private boolean isHeaderButton(Button button) {
        return button == homeThemeButton
                || button == credentialsThemeButton
                || button == discordThemeButton
                || button == settingsButton;
    }

    private void styleButton(Button button, AppTheme theme) {
        if (isHeaderButton(button)) {
            button.setBackgroundColor(Color.TRANSPARENT);
            button.setTextColor(theme.titleText);
        } else {
            button.setBackgroundColor(theme.buttonBg);
            button.setTextColor(theme.buttonText);
        }
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
                setPageStatus(PAGE_CREDENTIALS, getString(R.string.status_enter_token));
                return;
            }
            setPageStatus(PAGE_CREDENTIALS, getString(R.string.status_saved));
        } catch (IllegalArgumentException e) {
            setPageStatus(PAGE_CREDENTIALS, e.getMessage());
        } catch (GeneralSecurityException e) {
            setPageStatus(PAGE_CREDENTIALS, getString(R.string.status_save_failed));
        }
    }

    private void requestData(String endpoint, boolean locks, boolean post) {
        final String baseUrl = tokenStore.getBaseUrl();
        final String token;

        if (baseUrl == null || baseUrl.isEmpty()) {
            setPageStatus(post ? PAGE_DISCORD : PAGE_HOME, getString(R.string.status_enter_token));
            return;
        }

        try {
            if (currentToken == null || currentToken.isEmpty()) {
                currentToken = tokenStore.load();
            }
            if (currentToken == null || currentToken.isEmpty()) {
                setPageStatus(post ? PAGE_DISCORD : PAGE_HOME, getString(R.string.status_enter_token));
                return;
            }
            token = currentToken;
        } catch (GeneralSecurityException e) {
            setPageStatus(post ? PAGE_DISCORD : PAGE_HOME, getString(R.string.status_read_failed));
            return;
        }

        setBusy(true);
        if (!post) {
            resultsLayout.removeAllViews();
        }
        setPageStatus(post ? PAGE_DISCORD : PAGE_HOME, getString(R.string.status_loading));

        executor.execute(() -> {
            try {
                JSONObject response = requestJson(baseUrl + endpoint, token, post);
                runOnMainIfActive(() -> {
                    setBusy(false);
                    if (post) {
                        setPageStatus(PAGE_DISCORD, getString(R.string.status_reservation_report_sent));
                        return;
                    }
                    setPageStatus(PAGE_HOME, getString(locks
                            ? R.string.status_current_locks
                            : R.string.status_reservations));
                    if (locks) {
                        showProviderReadErrors(response.optJSONArray("provider_errors"));
                        showDoorCodes(response.optJSONArray("locks"));
                    } else {
                        showReservations(response.optJSONArray("reservations"));
                    }
                });
            } catch (IOException | JSONException e) {
                if (Thread.currentThread().isInterrupted()) {
                    return;
                }
                runOnMainIfActive(() -> {
                    setBusy(false);
                    setPageStatus(post ? PAGE_DISCORD : PAGE_HOME,
                            e.getMessage() == null ? getString(R.string.status_request_failed) : e.getMessage());
                });
            }
        });
    }

    private void runOnMainIfActive(Runnable action) {
        runOnUiThread(() -> {
            if (!isDestroyed() && !isFinishing()) {
                action.run();
            }
        });
    }

    private JSONObject requestJson(String address, String token, boolean post) throws IOException, JSONException {
        HttpURLConnection connection;
        try {
            connection = (HttpURLConnection) URI.create(address).toURL().openConnection();
        } catch (IllegalArgumentException e) {
            throw new IOException("The server address is invalid.", e);
        }
        try {
            connection.setRequestMethod(post ? "POST" : "GET");
            connection.setConnectTimeout(15000);
            connection.setReadTimeout(30000);
            connection.setRequestProperty("Accept", "application/json");
            connection.setRequestProperty("Authorization", "Bearer " + token);
            connection.setRequestProperty("Cache-Control", "no-store");
            if (post) {
                connection.setFixedLengthStreamingMode(0);
            }

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

    private void showProviderReadErrors(JSONArray errors) {
        if (errors == null) {
            return;
        }
        for (int i = 0; i < errors.length(); i++) {
            JSONObject error = errors.optJSONObject(i);
            if (error != null) {
                String provider = error.optString("provider", "provider");
                String roomNumber = error.optString("room_number", "");
                String roomSuffix = roomNumber.isEmpty() ? "" : " for room " + roomNumber;
                String errorCode = error.optString("error_code", "");
                String errorSuffix = errorCode.isEmpty() ? "" : " (" + errorCode + ")";
                addResultLine(getString(
                        R.string.lock_provider_read_failed,
                        provider,
                        roomSuffix,
                        errorSuffix
                ));
            }
        }
    }

    private void showDoorCodes(JSONArray locks) {
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
                String details = "Check-in: " + formatReservationDate(reservation.optString("check_in", ""))
                        + "\nCheck-out: " + formatReservationDate(reservation.optString("check_out", ""))
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

    private String formatReservationDate(String value) {
        if (value == null || value.trim().isEmpty()) {
            return "—";
        }
        try {
            return LocalDateTime.parse(value).format(RESERVATION_DATE_FORMAT);
        } catch (java.time.format.DateTimeParseException e1) {
            try {
                return OffsetDateTime.parse(value).format(RESERVATION_DATE_FORMAT);
            } catch (java.time.format.DateTimeParseException e2) {
                return value;
            }
        }
    }

    private void addResultLine(String text) {
        AppTheme theme = new AppTheme(isDarkMode);
        TextView result = new TextView(this);
        result.setText(text);
        result.setTextSize(16);
        result.setTextColor(theme.titleText);
        resultsLayout.addView(result, matchWrap());
    }

    private void addResultCard(String heading, String body) {
        AppTheme theme = new AppTheme(isDarkMode);
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(14), dp(12), dp(14), dp(12));
        card.setBackgroundColor(theme.cardBg);

        TextView title = new TextView(this);
        title.setText(heading);
        title.setTextSize(17);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        title.setTextColor(theme.titleText);
        card.addView(title, matchWrap());

        TextView details = new TextView(this);
        details.setText(body);
        details.setTextSize(16);
        details.setTextColor(theme.subtitleText);
        details.setPadding(0, dp(6), 0, 0);
        card.addView(details, matchWrap());

        LinearLayout.LayoutParams params = matchWrap();
        params.bottomMargin = dp(10);
        resultsLayout.addView(card, params);
    }

    private void setPageStatus(int page, String message) {
        if (page == PAGE_HOME && statusText != null) {
            statusText.setText(message);
        } else if (page == PAGE_CREDENTIALS && credentialsStatusText != null) {
            credentialsStatusText.setText(message);
        } else if (page == PAGE_DISCORD && discordStatusText != null) {
            discordStatusText.setText(message);
        }
    }

    private void setBusy(boolean busy) {
        if (ttlockCodesButton != null) ttlockCodesButton.setEnabled(!busy);
        if (tesaPinsButton != null) tesaPinsButton.setEnabled(!busy);
        if (reservationsButton != null) reservationsButton.setEnabled(!busy);
        if (sendReportButton != null) sendReportButton.setEnabled(!busy);
        if (saveButton != null) saveButton.setEnabled(!busy);
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

    private LinearLayout.LayoutParams matchWrapWithBottomMargin(int bottomMarginDp) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        params.bottomMargin = dp(bottomMarginDp);
        return params;
    }

    private LinearLayout.LayoutParams wrapWrap() {
        return new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
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
