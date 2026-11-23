# Bid Watcher

Emails you when a HiBid lot gets a new bid, when it is about to end, and when it closes.
Runs free on GitHub Actions every ~5 minutes. No server, no dependencies.

**Dashboard:** https://harshil3134.github.io/bid-watcher/

## Watch more listings
Add lot URLs to `lots.txt`, one per line (the dashboard's **Add / remove listings** button opens it
in GitHub's editor, which works on a phone). Delete a line to stop watching. The first check of a
new lot only records its current bid; alerts start from the next change.

## Setup (once)
1. Create a free account at https://resend.com and make an API key.
2. Repo secrets (Settings -> Secrets and variables -> Actions):
   - `RESEND_API_KEY` = your key
   - `ALERT_TO` = the email you signed up to Resend with
3. Actions tab -> "Watch bids" -> Run workflow, to test.
4. Dashboard: Settings -> Pages -> Deploy from branch `main`, folder `/docs`.

Resend's test sender (`onboarding@resend.dev`) only delivers to your own Resend account email.
To send anywhere else, verify a domain in Resend and change `EMAIL_FROM` in `watch.py`.

## Run locally
`python3 watch.py` (without the secrets it prints alerts instead of emailing).

## Notes
- Uses HiBid's public GraphQL endpoint (`/graphql`, `lot` query), the same one the site uses.
- The dashboard reads `state.json` from GitHub (cached up to ~5 min) and the latest run from the GitHub API.
- Keep the repo **public**: Actions minutes are unlimited for public repos. A private repo
  gets 2,000 free minutes/month, and every-5-minutes uses about 8,600.
- GitHub turns off scheduled workflows in repos with no activity for 60 days; re-enable in the Actions tab.
