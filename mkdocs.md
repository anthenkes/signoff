# Guide to mkdocs

1. mkdocs is a python package so need a python instance to run it locally 
2. Can host the static site with cloudflare pages. Can also make them private so only people with greyhaven can access them
3. Can make a CI pipeline through github where anyone can edit the `docs` and it will push to the docs site

## Repo Layout for MkDocs
At the repo root:
```
.
├─ docs-site/
│  ├─ mkdocs.yml
│  ├─ requirements-docs.txt
│  ├─ docs/
│  │  ├─ index.md
│  │  └─ ...more md...
│  └─ overrides/           # optional (Material theme overrides)
│     └─ main.html
└─ (rest of your non-python project)
```
`docs-site/requirements-docs.txt`:
```
mkdocs
mkdocs-material
```

## Needs
### On Cloudflare
1. Create the Pages project (Git integration)
    - Cloudflare pages git integration will `auto-deploy` on every push (can even do PR previews)
    - https://developers.cloudflare.com/pages/configuration/git-integration/
    - Within the create a project wizard make sure to add your github before navigating to the pages setup link
    ```
    In Cloudflare Dashboard → Workers & Pages → Create a project → Find the "Looking to deploy Pages?" tip at the bottom of the wizard
    ```
    https://dash.cloudflare.com/e633f60e6e4e14828b82f24c326b4628/workers-and-pages/create/pages

2. Build settings (for /docs-site/)
Once you have selected the github repo:
1. Name the project whatever you like (ie `workbench-pro-docs`)
2. Keep **Production Branch** set to `main`
3. In build settings
- **Framwork preset** = None
- **Build Command**:
```
pip install -r requirements-docs.txt && mkdocs build --strict
```
- **Build output directory** = `site`
Under the `Root directory (adcanced)` tab
- **Path** = `docs-site`
Under the `Environment variables (advanced)`
- Add a variable `PYTHON_VERSION` = 3.12

#### Warning
    If you want docs to stay private, I recommend disabling preview deployments (otherwise Cloudflare can generate *.pages.dev preview URLs for branches/PRs). Cloudflare documents how preview deployments work and that PRs can get unique preview URLs. https://developers.cloudflare.com/pages/configuration/preview-deployments/

### After Deploy
Navigate to the project dashboard (The dashboard for the docs)
Here you should see the docs pages deployments
- There will be a **deployment** link you can view to preview the pages

#### Add Custom Domain
Click `set up custom domain`
enter:
```
docs.workbenchpro.io
```
- This will set up the dns record. So in the future team members can just navigate to `docs.workbenchpro.io` to view the docs for the project
- Click activate. Takes about 5-10 minutes to update the DNS setting

#### Specific settings in the settings tab
1. Click on **Branch control** -> set preview branch to None for now.
2. Set **Build watch paths** to `*`
(**exception** if later decide to pull from outside docs-site folder need to change the Build config to the root folder and specify the watch paths ie docs-site/*)
3. Scroll down to **General** and enable `Access Policy`
- After access policy is enabled navigate to the **Manage** link and see info below

#### Access Policy: Protects the docs from unwanted guests :)
May need to subscribe to the zero trust platform. This does not cost anything for less than 50 developers accessing the docs page (Gating behind email so ~6 right now)
After zero trust has been "bought" ($0)
1. Navigate to
```
Access controls -> Applications -> click on the application with `*.workbenchpro-docs.page.dev` in the application URL -> Click configure -> Policies
```
2. Click Create new policy
3. Set:
    - Action: Allow
    - Policy name: Allow greyhavengroup.com
4. Under Configure rules (wording varies slightly), add a rule like:
Include → Emails ending in:
- greyhavengroup.com
or
Include → Email → ends with
- @greyhavengroup.com
5. Save the policy, then make sure it’s above any broader allow policies (top-to-bottom order matters).
6. Navigate back to the policies page and add it to the policy (remove any others)

Better (if you use Google Workspace / Microsoft)
Enable Google/Microsoft as the identity provider, then the domain restriction is very clean and users won’t be typing OTPs constantly.
#### Need to Setup org-level login method for zero Trust
1) Enable One-time PIN at the Zero Trust org level

In one.dash.cloudflare.com (Zero Trust dashboard):
1. Go to Settings → Authentication (sometimes labeled “Login methods”)
2. Find Login methods
3. Click Add new (or “Add”) → select One-time PIN
4. Enable it and Save
There’s usually no extra configuration needed here—who can receive OTP is controlled by your Access policy (the email/domain allow rule).

2) Make your Docs application actually use One-time PIN
Go to Access → Applications → click your signoff-docs app → Login methods tab:
Turn OFF “Accept all identity providers” (if you see it)
Select One-time PIN as an allowed method
Save
(If you don’t pick it here, the app may not present OTP as an option even if it’s enabled globally.)

Don't know exactly what is needed from above. 
Ran into an issue when implementing all the necessary policy changes nothing was working.
This was because on `Zero Trust` within the application. The application url was not pointed to the actual domain (ie docs.workbenchpro.io) but to the name given by cloudflare.
To fix
1. Navigate:
```
Zero Trust -> Access controls -> Applications -> click three dots next to the SELF-HOSTED type -> select edit
```
2. Within **Public hostname** section. Input = default; Subdomain = docs; Domain = workbenchpro.io; No path setting
3. Click Save application

## CI Pipeline
To automatically update docs site when production docs are deployed to `main` branch.

### On GitHub
Cloudflare Pages Git integration = your CI pipeline
Once the repo is connected:
- Merging a PR into main triggers a new deployment automatically.
- No GitHub Actions needed.
- Your team reviews docs at https://docs.yourdomain.com (behind Access).
This is the lowest-overhead way.