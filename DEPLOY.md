# Deploying to GitHub Pages (content only, no build scripts)

This setup deploys only the built site (HTML, section PDFs, full book) to a **single public repo** that has no build scripts.

## One-time setup

1. Create a **new empty public repo** on GitHub (e.g. `my-book`).

2. Set the deploy URL in `config/config.json`:
   ```json
   "deploy-repo": "https://github.com/YOUR_USERNAME/YOUR_REPO.git"
   ```

3. Run deploy (clones the repo into `site/` on first run):
   ```bash
   python build.py deploy --push
   ```

4. In GitHub repo **Settings > Pages**: Set source to **Deploy from a branch**, branch **main**, folder **/ (root)**.

5. **Custom domain** (optional): In `config/config.json`, add:
   ```json
   "deploy-domain": "my-book.example.com"
   ```
   The deploy adds a `CNAME` file so GitHub Pages serves at your domain. In **Settings > Pages**, enter the custom domain and follow GitHub's DNS instructions (CNAME record or A records).

## Deploy workflow

```bash
python build.py deploy --push
```

`deploy` builds everything and runs `./build.py check` first; it copies nothing if either fails.
To push somewhere other than the clone's `origin` (for example over SSH when the HTTPS remote
has no stored credentials), set `"deploy-push-url"` in `config/config.json`.

Or split into steps:
```bash
python build.py deploy          # Build and copy to site/
cd site && git add -A && git commit -m "Deploy" && git push
```

## Result

- **Public repo** contains only: `index.html`, `styles.css`, `main.js`, chapter folders, `pdf/`, `book/`, search/navigation JSON.
- **No** `build/`, `src/`, `templates/`, or config in the public repo.
- GitHub Pages serves the site from the root.
