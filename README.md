# Bid Watcher

Emails you when a HiBid lot gets a new bid, when it is about to end, and when it closes.
Runs free on GitHub Actions every ~5 minutes. No server, no dependencies.

## Watch a lot
Add its URL to `LOTS` at the top of `watch.py`, commit, push. The first check only records
the current bid (no email); alerts start from the next change.

## Setup (once)
1. Create a free account at https://resend.com and make an API key.
2. In this GitHub repo: Settings -> Secrets and variables -> Actions -> New repository secret:
   - `RESEND_API_KEY` = your key
   - `ALERT_TO` = the email you signed up to Resend with
3. Actions tab -> "Watch bids" -> Run workflow, to test.

Resend's test sender (`onboarding@resend.dev`) only delivers to your own Resend account email.
To send anywhere else, verify a domain in Resend and change `EMAIL_FROM`.

## Run locally
`python3 watch.py` (without the secrets it prints alerts instead of emailing).

## Notes
- Uses HiBid's public GraphQL endpoint (`/graphql`, `lot` query), the same one the site uses.
- Keep the repo **public**: Actions minutes are unlimited for public repos. A private repo
  gets 2,000 free minutes/month, and every-5-minutes uses about 8,600.
- GitHub turns off scheduled workflows in repos with no activity for 60 days; re-enable in the Actions tab.
