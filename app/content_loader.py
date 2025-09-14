# pistlar/app/content_loader.py
import os, re, datetime, unicodedata, frontmatter, markdown, bleach, hashlib
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import timezone, time

ALLOWED_TAGS = list(bleach.sanitizer.ALLOWED_TAGS) + ["p","img","h1","h2","h3","h4","h5","h6","figure","figcaption","pre","code","blockquote"]
ALLOWED_ATTRIBUTES = {**bleach.sanitizer.ALLOWED_ATTRIBUTES, "img": ["src","alt","title","loading"]}

md = markdown.Markdown(extensions=["extra","abbr","attr_list","admonition","sane_lists","toc","tables","fenced_code"])

POST_EXTS = (".md", ".markdown", ".mdown", ".mkdn")

def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii","ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9\-\s]", "", value).strip().lower()
    value = re.sub(r"[\s\_]+", "-", value)
    return value

def _to_aware_utc(dt) -> datetime.datetime:
    if isinstance(dt, datetime.datetime):
        pass
    elif isinstance(dt, datetime.date):
        dt = datetime.datetime.combine(dt, time(12, 0, 0))
    else:
        s = str(dt).strip().replace("Z", "+00:00").replace("+0000", "+00:00")
        try:
            dt = datetime.datetime.fromisoformat(s)
        except Exception:
            m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
            if m:
                y, mo, d = map(int, m.groups())
                dt = datetime.datetime(y, mo, d, 12, 0, 0)
            else:
                dt = datetime.datetime.now()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt

@dataclass(order=True)
class Post:
    sort_index: datetime.datetime = field(init=False, repr=False)
    title: str
    slug: str
    date: datetime.datetime
    summary_html: str
    html: str
    image: Optional[str]
    source_path: str
    def __post_init__(self):
        self.sort_index = self.date

def _parse_date_from_filename(name: str) -> Optional[datetime.datetime]:
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})-", name)
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    return datetime.datetime(y, mo, d, 12, 0, 0, tzinfo=timezone.utc)

def _first_paragraph_html(rendered: str) -> str:
    m = re.search(r"<p[\s\S]*?</p>", rendered, flags=re.IGNORECASE)
    return m.group(0) if m else (rendered.split("</p>")[0] + "</p>" if "</p>" in rendered else rendered)

# ---------- NEW: recursive traversal + robust fingerprint ----------
def _iter_post_files(posts_dir: str):
    try:
        for root, dirs, files in os.walk(posts_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if fname.lower().endswith(POST_EXTS):
                    yield os.path.join(root, fname)
    except FileNotFoundError:
        return

def _calc_fingerprint_for_dir(posts_dir: str) -> str:
    items = []
    for fpath in _iter_post_files(posts_dir):
        try:
            st = os.stat(fpath)
            rel = os.path.relpath(fpath, posts_dir)
            items.append(f"{rel}:{int(st.st_mtime)}:{st.st_size}")
        except FileNotFoundError:
            continue
    items.sort()
    return hashlib.sha256(("|".join(items)).encode("utf-8")).hexdigest()
# ------------------------------------------------------------------

class ContentStore:
    def __init__(self, posts_dir: str, assets_url_prefix: str = "/assets"):
        self.posts_dir = posts_dir
        self.assets_url_prefix = assets_url_prefix
        self._fingerprint = ""
        self._posts: List[Post] = []

    def _calc_fingerprint(self) -> str:
        return _calc_fingerprint_for_dir(self.posts_dir)

    def _load(self):
        import logging
        logging.getLogger().setLevel(logging.INFO)
        
        new_fp = self._calc_fingerprint()
        if new_fp == self._fingerprint and self._posts:
            return

        logging.info("past fingerprint")

        posts: List[Post] = []
        if not os.path.isdir(self.posts_dir):
            self._posts = []
            self._fingerprint = new_fp
            return

        logging.info("past post list")

        for fpath in _iter_post_files(self.posts_dir):
            fname = os.path.basename(fpath)
            try:
                fm = frontmatter.load(fpath)
            except Exception:
                with open(fpath, "r", encoding="utf-8") as fh:
                    raw = fh.read()
                fm = frontmatter.Post(raw, **{})

            title = fm.get("title") or os.path.splitext(fname)[0]

            logging.info("Post title: %s", title)


            dval = fm.get("date")
            date = _to_aware_utc(dval) if dval is not None else (_parse_date_from_filename(fname) or _to_aware_utc(datetime.datetime.now()))

            slug = fm.get("slug") or slugify(title)

            # accept multiple keys
            image = fm.get("image") or fm.get("img") or fm.get("cover") or fm.get("thumbnail")

            def _normalize_image(image_str: str, assets_url_prefix: str) -> str:
                s = str(image_str).strip()

                # strip optional leading ":" shorthand
                if s.startswith(":"):
                    s = s[1:]

                # absolute or data/url → leave as-is
                if s.startswith(("http://", "https://", "data:")):
                    return s

                # normalize any leading slashes
                s = s.lstrip("/")

                # if author wrote "assets/..." or "/assets/..."
                if s.startswith("assets/"):
                    return f"/{s}"

                # if author wrote "img/..." or "images/..." under assets root
                if s.startswith(("img/", "images/")):
                    return f"{assets_url_prefix}/{s}"

                # fallback: treat as a filename in the posts bucket
                return f"{assets_url_prefix}/img/posts/{s}"

            if image:
                image = _normalize_image(image, self.assets_url_prefix)

            html = md.reset().convert(fm.content)
            html = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=False)
            summary_html = _first_paragraph_html(html)

            posts.append(Post(
                title=title, slug=slug, date=date,
                summary_html=summary_html, html=html,
                image=image, source_path=fpath
            ))

        posts.sort(key=lambda p: p.date, reverse=True)
        self._posts = posts

        logging.info("ContentStore: scanning %s", self.posts_dir)
        logging.info("ContentStore: %d posts loaded", len(posts))
        if posts:
            logging.info("ContentStore: first=%s (%s)", posts[0].title, posts[0].source_path)

        self._fingerprint = new_fp

    # ✅ The methods your app calls:
    def all_posts(self) -> List[Post]:
        self._load()
        return list(self._posts)

    def by_slug(self, slug: str) -> Optional[Post]:
        self._load()
        for p in self._posts:
            if p.slug == slug:
                return p
        return None
