# app/app.py
import os
from datetime import datetime
from pathlib import Path
from typing import List
from flask import Flask, render_template, abort, request, send_from_directory
from werkzeug.utils import secure_filename
from .content_loader import ContentStore, slugify

PROJECT_ROOT = Path(__file__).resolve().parents[1]     # /app
CONTENT_DIR   = PROJECT_ROOT / "content"                # /app/content
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}

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
    new_post_password = os.environ.get("NEW_POST_PASSWORD")

    app.config.update(
        POSTS_DIR=posts_dir,
        ASSETS_DIR=assets_dir,
        PAGE_SIZE=page_size,
        SITE_TITLE=site_title,
        NEW_POST_PASSWORD=new_post_password,
    )

    store = ContentStore(posts_dir, assets_url_prefix="/assets")

    def _list_asset_images() -> List[str]:
        images = []
        base = Path(assets_dir)
        if not base.exists():
            return images
        for root, _, files in os.walk(base):
            root_path = Path(root)
            for fname in files:
                ext = Path(fname).suffix.lower()
                if ext not in IMAGE_EXTS:
                    continue
                rel = (root_path / fname).relative_to(base).as_posix()
                images.append(rel)
        images.sort()
        return images

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

    @app.route("/new", methods=["GET", "POST"])
    def new_post_form():
        error = None
        success = None
        created_file = None
        created_slug = None
        uploaded_assets: list[str] = []

        if request.method == "POST":
            form_password = request.form.get("password", "")
            title = (request.form.get("title") or "").strip()
            date_str = (request.form.get("date") or "").strip()
            image = (request.form.get("image") or "").strip()
            body = (request.form.get("content") or "").strip()
            upload_files = request.files.getlist("upload_images") if request.files else []

            if not new_post_password:
                error = "Set NEW_POST_PASSWORD in your environment to enable this form."
            elif form_password != new_post_password:
                error = "Rangt lykilorð."
            else:
                # Handle image uploads first (if any)
                if upload_files:
                    dest_dir = Path(assets_dir) / "img" / "posts"
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    for file in upload_files:
                        if not file or not file.filename:
                            continue
                        ext = Path(file.filename).suffix.lower()
                        if ext not in IMAGE_EXTS:
                            continue
                        safe_name = secure_filename(file.filename) or "upload"
                        target = dest_dir / safe_name
                        counter = 2
                        while target.exists():
                            target = dest_dir / f"{target.stem}-{counter}{target.suffix}"
                            counter += 1
                        file.save(target)
                        rel = target.relative_to(assets_dir).as_posix()
                        uploaded_assets.append(f"{store.assets_url_prefix}/{rel}")

                if not title:
                    error = "Titill vantar."
                elif not body:
                    error = "Innihald vantar."
                else:
                    try:
                        date_obj = datetime.fromisoformat(date_str).date() if date_str else datetime.utcnow().date()
                    except ValueError:
                        date_obj = datetime.utcnow().date()

                base_slug = slugify(title) or "post"

                # Ensure unique slug
                existing_slugs = {p.slug for p in store.all_posts()}
                final_slug = base_slug
                n = 2
                while final_slug in existing_slugs:
                    final_slug = f"{base_slug}-{n}"
                    n += 1

                fname_base = f"{date_obj.isoformat()}-{final_slug}"
                posts_dir_path = Path(posts_dir)
                posts_dir_path.mkdir(parents=True, exist_ok=True)

                target_path = posts_dir_path / f"{fname_base}.md"
                i = 2
                while target_path.exists():
                    target_path = posts_dir_path / f"{fname_base}-{i}.md"
                    i += 1

                frontmatter_lines = [
                    "---",
                    f"title: {title}",
                    f"date: {date_obj.isoformat()}",
                    f"slug: {final_slug}",
                ]
                if image:
                    frontmatter_lines.append(f"image: {image}")
                frontmatter_lines.append("---\n")

                with open(target_path, "w", encoding="utf-8") as fh:
                    fh.write("\n".join(frontmatter_lines))
                    fh.write(body.rstrip() + "\n")

                success = True
                created_file = str(target_path)
                created_slug = final_slug

        return render_template(
            "new_post.html",
            site_title=site_title,
            error=error,
            success=success,
            created_file=created_file,
            created_slug=created_slug,
            uploaded_assets=uploaded_assets,
            assets_prefix=store.assets_url_prefix,
            existing_assets=_list_asset_images(),
            default_date=datetime.utcnow().date().isoformat(),
            disable_sidebar=True,
        )

    return app
