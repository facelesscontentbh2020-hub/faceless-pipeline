# Cloud Setup — one-time, ~45 minutes

The pipeline runs free on GitHub Actions: daily at 12pm Central it renders a new
short from the script queue and posts to Instagram + YouTube. No laptop needed.

## 1. GitHub (10 min)

1. Create an account at github.com (use facelesscontentbh2020@gmail.com to keep it separate).
2. Create a new repository named `faceless-pipeline`, set it to **Public**
   (public = unlimited free Actions minutes + public video URLs for Instagram).
3. Install git locally if needed (`xcode-select --install` on macOS), then in Terminal:

```bash
cd ~/Desktop/Projects/FacelessContent/cloud
git init
git add .
git commit -m "faceless content pipeline"
git branch -M main
git remote add origin https://github.com/<YOUR_USERNAME>/faceless-pipeline.git
git push -u origin main
```

(Git will open a browser window to sign in the first time.)

## 2. Instagram API (20 min) — free

1. Go to https://developers.facebook.com → "Get Started" → create a developer account.
2. Create App → type **Business** → name it anything (e.g. "MoneyRewired Poster").
3. You need a Facebook Page linked to the IG account:
   - Create a Facebook Page (any name, e.g. "Money Rewired") at facebook.com/pages/create
   - In the Instagram app: Settings → Business tools → link the Facebook Page.
4. In the Meta app dashboard: add product **Instagram Graph API**.
5. Open Graph API Explorer (developers.facebook.com/tools/explorer):
   - Select your app, click "Generate Access Token"
   - Grant permissions: `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `business_management`
6. Exchange for a long-lived token (60 days) — run in Terminal:
   ```bash
   curl "https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id=<APP_ID>&client_secret=<APP_SECRET>&fb_exchange_token=<SHORT_TOKEN>"
   ```
7. Get your IG user ID:
   ```bash
   curl "https://graph.facebook.com/v21.0/me/accounts?access_token=<LONG_TOKEN>"   # note the PAGE id
   curl "https://graph.facebook.com/v21.0/<PAGE_ID>?fields=instagram_business_account&access_token=<LONG_TOKEN>"
   ```
   The `instagram_business_account.id` value is your IG_USER_ID.

⚠️ The long-lived token expires every ~60 days. Refreshing takes 2 minutes
(re-run step 6 with the current token). Put a calendar reminder, or ask Claude
to set a scheduled reminder.

## 3. YouTube API (15 min) — free

1. Create the YouTube channel first (youtube.com → profile → Create a channel,
   name: Money Rewired). Verify the channel with your phone at youtube.com/verify
   (removes upload limits).
2. Go to https://console.cloud.google.com → new project → enable **YouTube Data API v3**.
3. OAuth consent screen: External, add yourself as a test user. (Keep the app in
   "Testing" — tokens work fine for your own channel.)
4. Credentials → Create OAuth Client ID → Desktop app. Note client ID + secret.
5. Get a refresh token — easiest via this one-liner (needs python + google-auth-oauthlib):
   ```bash
   pip3 install google-auth-oauthlib
   python3 -c "
   from google_auth_oauthlib.flow import InstalledAppFlow
   f = InstalledAppFlow.from_client_config({'installed':{'client_id':'<CLIENT_ID>','client_secret':'<CLIENT_SECRET>','auth_uri':'https://accounts.google.com/o/oauth2/auth','token_uri':'https://oauth2.googleapis.com/token'}}, ['https://www.googleapis.com/auth/youtube.upload'])
   c = f.run_local_server(port=0)
   print('REFRESH TOKEN:', c.refresh_token)"
   ```

⚠️ Known caveat: YouTube sometimes locks API uploads from unverified projects to
private. If your first video shows "private (locked)", request an API audit
exemption in the Cloud console (takes a few days) — or keep YouTube manual until then.

## 4. GitHub secrets + switches (5 min)

Repo → Settings → Secrets and variables → Actions:

**Secrets** (add each):
- `IG_USER_ID`
- `META_ACCESS_TOKEN`
- `YT_CLIENT_ID`
- `YT_CLIENT_SECRET`
- `YT_REFRESH_TOKEN`

**Variables** (same page, "Variables" tab):
- `ENABLE_INSTAGRAM` = `true`
- `ENABLE_YOUTUBE` = `true`  (or `false` until the channel/API is ready)

## 5. Test

Repo → Actions → "Daily faceless short" → **Run workflow**. Watch the log.
A successful run posts to the enabled platforms and commits the day's entry
to `content/history.json`.

## Ongoing

- **Queue**: 41 scripts ≈ 6 weeks. Ask Claude to write a new batch and push.
- **Meta token**: refresh every ~60 days (step 2.6).
- **Failures**: GitHub emails you automatically when a run fails.
- **Change post time**: edit the cron line in `.github/workflows/daily.yml` (UTC).
