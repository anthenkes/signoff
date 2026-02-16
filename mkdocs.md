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
In the cloudflare dashboard:
```
Workers & Pages -> Create application -> Pages -> Import an exisiting Git repository
```
**Build Setings (MKDocs)**
---
- Build command: 
```
pip install -r requirements-docs.txt && mkdocs build --strict
```
- Build output directory: `site`

!!! tip "Fast tip"
    After deploy, you’ll get a *.pages.dev URL.

## Attach Custom Domain
In Pages project:
```
Custom domains -> Set up a custom domain -> `docs.example.com`
```
!!! warning
    - Cloudflare’s “Custom domains” doc notes:
    If your zone is already on Cloudflare, the needed DNS record can be added automatically after you add the domain in Pages.
    - Don’t manually CNAME it without first associating it in the Pages dashboard (that can cause resolution errors like 522)

## Make the docs private: Protect the `docs.example.com` with Cloudflare access
!!! warning
    Pages are public by default unless you add Access in front.

Go to:
```
Cloudflare Zero Trust → Access → Applications → Add an application → Self-hosted
```
set the hostname to `docs.example.com`. Cloudflare's Access app creation steps can be found here: https://developers.cloudflare.com/learning-paths/clientless-access/access-application/create-access-app/

The add an **Allow** poilcy 
!!! tip "FYI"
    Access apps are "deny by default" until an Allow policy matches.

Typical Policy examples:
```
- Allow emails in your domain: @yourcompany.com
- r allow a list of specific emails
- Or require login via Google Workspace / GitHub / Okta, etc.
```
You can also scope policies to paths/subdomians if you ever want (Access "application paths").

## CI Pipeline
To automatically update docs site when production docs are deployed to `main` branch.

### On Cloudflare
1. Create the Pages project (Git integration)
    - Cloudflare pages git integration will `auto-deploy` on every push (can even do PR previews)
    - https://developers.cloudflare.com/pages/configuration/git-integration/
    ```
    In Cloudflare Dashboard → Workers & Pages → Pages → Create a project → Connect to Git
    ```
2. Build settings (for /docs-site/)
Once you have selected the github repo:
1. Name the project whatever you like (ie `workbench-pro-docs`)
2. Unclick the **Builds for non-production
If `Pages` has "Root Directory"
- Root directory: `docs-site`
- Build command:
```
pip install -r requirements-docs.txt && mkdocs build --strict
```
- Build output directory: `site`
If `Pages` does **NOT** have "Root directory"
- Build command: 
```
pip install -r docs-site/requirements-docs.txt && mkdocs build -f docs-site/mkdocs.yml -d docs-site/site --strict
```
- Build output directory: `docs-site/site`
3. Branch Control (**IMPORTANT**)
set **Production Branch** = `Main`

!!! warning
    If you want docs to stay private, I recommend disabling preview deployments (otherwise Cloudflare can generate *.pages.dev preview URLs for branches/PRs). Cloudflare documents how preview deployments work and that PRs can get unique preview URLs. https://developers.cloudflare.com/pages/configuration/preview-deployments/

### On GitHub
Cloudflare Pages Git integration = your CI pipeline
Once the repo is connected:
- Merging a PR into main triggers a new deployment automatically.
- No GitHub Actions needed.
- Your team reviews docs at https://docs.yourdomain.com (behind Access).
This is the lowest-overhead way.