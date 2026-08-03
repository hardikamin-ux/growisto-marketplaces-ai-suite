# Hosting the P&L Dashboard at one internal URL

The dashboard is a single static HTML file. All report processing happens locally in each
person's browser — **no data is ever sent to the host.** So hosting is safe and simple; you're
just serving one file. Pick whichever route matches who's setting it up.

---

## Recommended if you have IT / an intranet
Hand IT the file `Amazon_PnL_Dashboard.html` and ask them to place it on the company intranet
web server (or an internal SharePoint site configured to serve/render HTML). They give you a
link like `https://intranet.yourcompany.com/tools/pnl`. This is the cleanest "internal URL
behind the company login" outcome and needs no third-party account. To update: IT replaces the
one file.

## Recommended self-serve, access-controlled (no IT needed)
**Netlify with a site password** — live in ~5 minutes, one shared password for the whole team.
1. Go to app.netlify.com and create a free account (or log in).
2. Drag `Amazon_PnL_Dashboard.html` onto the deploy area. Netlify gives you a URL immediately.
   (Rename the file to `index.html` first so the URL is clean — optional.)
3. Site settings → **Access & security → Visitor access → Password protection** → set one
   password. Now only people with the link + password can open it. (Password protection is a
   paid Netlify feature; the free tier hosts it but without the password gate.)
4. Share the URL + password with the team.
   To update later: drag the new file onto the same site — the URL stays the same.

## Best native fit for a Microsoft 365 company (SSO, no extra password)
**Azure Static Web Apps** with Entra ID (Azure AD) sign-in — only your company accounts can open
it, using the logins people already have.
1. In the Azure portal, create a **Static Web App** (free tier).
2. Upload the file (via the portal, the SWA CLI, or a GitHub repo).
3. Add a `staticwebapp.config.json` that requires authentication (I can generate this for you).
4. You get a URL like `https://pnl.yourcompany.azurestaticapps.net`, gated by company sign-in.
This needs someone with Azure access, but it's the tidiest long-term "internal only" answer.

---

## What NOT to use for internal-only
- **GitHub Pages (free):** only serves *public* sites unless you have GitHub Enterprise. Fine if
  you don't mind it being reachable by URL; not truly internal.
- **Emailing the file around:** works, but you'll get version drift — people keep old copies.
  The version stamp in the header (`v1.0`) helps, but a single hosted URL avoids the problem.

## Two things the team should know
- **Each person's data is private to their browser.** Uploads persist only on that machine
  (localStorage); nothing is shared or centralised. The per-brand Excel file remains the source
  of truth — each person uploads it to view it.
- **Updating the tool = replace one file** at the host; everyone gets the new version on refresh.
  Confirm the build via the version number shown in the header.
