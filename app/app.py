# app/app.py
import os
from pathlib import Path
from flask import Flask, render_template, abort, request, send_from_directory
from .content_loader import ContentStore

PROJECT_ROOT = Path(__file__).resolve().parents[1]     # /app
CONTENT_DIR   = PROJECT_ROOT / "content"                # /app/content

def create_app():
    # templates live at repo root: /pistlar/templates  -> /app/templates
    app = Flask(
        __name__,
        static_folder="static",      # /app/app/static
        template_folder="templates"  # /app/app/templates  ✅
    )

    # resolve dirs first (env wins, else defaults under /app/content)
    posts_dir  = os.environ.get("POSTS_DIR")  or str(CONTENT_DIR / "posts")
    assets_dir = os.environ.get("ASSETS_DIR") or str(CONTENT_DIR / "assets")
    page_size  = int(os.environ.get("PAGE_SIZE", "10"))
    site_title = os.environ.get("SITE_TITLE", "Pistlar")

    app.config.update(
        POSTS_DIR=posts_dir,
        ASSETS_DIR=assets_dir,
        PAGE_SIZE=page_size,
        SITE_TITLE=site_title,
    )

    store = ContentStore(posts_dir, assets_url_prefix="/assets")

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/assets/<path:path>")
    def assets(path):
        return send_from_directory(assets_dir, path)

    @app.get("/pistlar/<slug>/")
    def post(slug):
        p = store.by_slug(slug)
        if not p:
            abort(404)
        return render_template("article.html", site_title=site_title, post=p)

    @app.get("/")
    def index():
        page = max(int(request.args.get("page", 1) or 1), 1)
        page_size_local = page_size
        posts = store.all_posts()
        total = len(posts)
        start = (page - 1) * page_size_local
        end = start + page_size_local
        page_posts = posts[start:end]

        most_recent = page_posts[0] if (page == 1 and page_posts) else None
        rest = page_posts[1:] if (page == 1 and page_posts) else page_posts
        sidebar_posts = posts[:10]
        prev_page = page - 1 if page > 1 else None
        next_page = page + 1 if end < total else None

        return render_template(
            "index.html",
            site_title=site_title,
            most_recent=most_recent,
            rest=rest,
            sidebar_posts=sidebar_posts,
            page=page,
            prev_page=prev_page,
            next_page=next_page,
        )

    return app
