# app/app.py
import os
from datetime import datetime
from pathlib import Path
from typing import List
import frontmatter
from flask import Flask, render_template, abort, request, send_from_directory
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from .content_loader import ContentStore, slugify

PROJECT_ROOT = Path(__file__).resolve().parents[1]     # /app
CONTENT_DIR   = PROJECT_ROOT / "content"                # /app/content
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}

load_dotenv(PROJECT_ROOT / ".env")

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

    def _save_post_uploads(upload_files):
        uploaded_assets_local: list[str] = []
        if not upload_files:
            return uploaded_assets_local

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
            uploaded_assets_local.append(f"{store.assets_url_prefix}/{rel}")

        return uploaded_assets_local

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
                uploaded_assets.extend(_save_post_uploads(upload_files))

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

                target_path = posts_dir_path / f"{fname_base}.markdown"
                i = 2
                while target_path.exists():
                    target_path = posts_dir_path / f"{fname_base}-{i}.markdown"
                    i += 1

                metadata = {
                    "title": title,
                    "date": date_obj.isoformat(),
                    "slug": final_slug,
                }
                if image:
                    metadata["image"] = image

                fm_post = frontmatter.Post(body.rstrip() + "\n", **metadata)
                rendered = frontmatter.dumps(fm_post).rstrip() + "\n"

                with open(target_path, "w", encoding="utf-8") as fh:
                    fh.write(rendered)

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

    @app.route("/pistlar/<slug>/edit/", methods=["GET", "POST"])
    @app.route("/pistlar/<slug>/edit", methods=["GET", "POST"])
    def edit_post(slug):
        error = None
        success = None
        uploaded_assets: list[str] = []

        post_obj = store.by_slug(slug)
        if not post_obj:
            abort(404)

        try:
            fm = frontmatter.load(post_obj.source_path)
        except Exception:
            # Fall back if frontmatter is malformed: strip any leading fm block and seed metadata from the post object
            with open(post_obj.source_path, "r", encoding="utf-8") as fh:
                raw = fh.read()

            raw_lines = raw.splitlines()
            body_lines = raw_lines
            if raw_lines and raw_lines[0].strip() == "---":
                try:
                    end_idx = raw_lines[1:].index("---") + 1
                    body_lines = raw_lines[end_idx + 1 :]
                except ValueError:
                    body_lines = raw_lines[1:]
            fallback_body = "\n".join(body_lines).strip("\n") + "\n"

            fallback_meta = {
                "title": post_obj.title,
                "slug": post_obj.slug,
                "date": getattr(post_obj.date, "date", lambda: post_obj.date)().isoformat() if post_obj.date else datetime.utcnow().date().isoformat(),
            }
            if post_obj.image:
                fallback_meta["image"] = post_obj.image

            fm = frontmatter.Post(fallback_body, **fallback_meta)

        image_key = "image" if "image" in fm.metadata else ("img" if "img" in fm.metadata else "image")

        def _coerce_date_str(val) -> str:
            if isinstance(val, datetime):
                return val.date().isoformat()
            try:
                return val.isoformat()
            except Exception:
                try:
                    return datetime.fromisoformat(str(val)).date().isoformat()
                except Exception:
                    return datetime.utcnow().date().isoformat()

        base_title = fm.metadata.get("title") or post_obj.title
        base_date = _coerce_date_str(fm.metadata.get("date") or post_obj.date)
        base_image = fm.metadata.get(image_key) or ""
        base_content = fm.content or ""

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
                uploaded_assets.extend(_save_post_uploads(upload_files))

                if not title:
                    error = "Titill vantar."
                elif not body:
                    error = "Innihald vantar."
                else:
                    try:
                        date_obj = datetime.fromisoformat(date_str).date() if date_str else datetime.utcnow().date()
                    except ValueError:
                        date_obj = datetime.utcnow().date()

                    fm.metadata["title"] = title
                    fm.metadata["slug"] = post_obj.slug
                    fm.metadata["date"] = date_obj.isoformat()
                    if image:
                        fm.metadata[image_key] = image
                    else:
                        fm.metadata.pop(image_key, None)
                    fm.content = body

                    with open(post_obj.source_path, "w", encoding="utf-8") as fh:
                        fh.write(frontmatter.dumps(fm).rstrip() + "\n")

                    store._fingerprint = ""
                    success = True
                    base_title = title
                    base_date = date_obj.isoformat()
                    base_image = image
                    base_content = body

        return render_template(
            "edit_post.html",
            site_title=site_title,
            post=post_obj,
            error=error,
            success=success,
            uploaded_assets=uploaded_assets,
            assets_prefix=store.assets_url_prefix,
            existing_assets=_list_asset_images(),
            form_title=request.form.get("title") or base_title,
            form_date=request.form.get("date") or base_date,
            form_image=request.form.get("image") or base_image,
            form_content=request.form.get("content") or base_content,
            disable_sidebar=True,
        )

    return app
