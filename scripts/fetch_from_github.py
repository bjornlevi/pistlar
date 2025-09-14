#!/usr/bin/env python3
import argparse, os, requests, pathlib

GITHUB_API = "https://api.github.com"

def fetch_dir(repo, path, ref="master", token=None):
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}?ref={ref}"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code == 404 and ref == "master":
        # try common alt default branch
        url = f"{GITHUB_API}/repos/{repo}/contents/{path}?ref=main"
        r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_file(repo, path, ref="master", token=None):
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}?ref={ref}"
    headers = {"Accept": "application/vnd.github.raw"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code == 404 and ref == "master":
        url = f"{GITHUB_API}/repos/{repo}/contents/{path}?ref=main"
        r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.content

def main():
    ap = argparse.ArgumentParser(description="Fetch posts and assets from a GitHub repo into content/")
    ap.add_argument("--repo", required=True, help="e.g. bjornlevi/bjornlevi.github.io")
    ap.add_argument("--posts-path", dest="posts_path", default="_posts")
    ap.add_argument("--assets-path", dest="assets_path", default="assets/img/posts")
    ap.add_argument("--ref", default="master", help="branch or commit (default: master; will fallback to main if 404)")
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    ap.add_argument("--dest", default="content")
    args = ap.parse_args()

    posts_out = pathlib.Path(args.dest)/"posts"
    assets_out = pathlib.Path(args.dest)/"assets"/"img"/"posts"
    posts_out.mkdir(parents=True, exist_ok=True)
    assets_out.mkdir(parents=True, exist_ok=True)

    print(f"Fetching posts from {args.repo}:{args.posts_path} @ {args.ref}")
    for item in fetch_dir(args.repo, args.posts_path, args.ref, args.token):
        if item.get("type") != "file" or not item.get("name","").endswith(".md"):
            continue
        name = item["name"]
        print(" -", name)
        data = fetch_file(args.repo, f"{args.posts_path}/{name}", args.ref, args.token)
        (posts_out / name).write_bytes(data)

    print(f"Fetching assets from {args.repo}:{args.assets_path} @ {args.ref}")
    for item in fetch_dir(args.repo, args.assets_path, args.ref, args.token):
        if item.get("type") != "file":
            continue
        name = item["name"]
        print(" -", name)
        data = fetch_file(args.repo, f"{args.assets_path}/{name}", args.ref, args.token)
        (assets_out / name).write_bytes(data)

    print("Done.")

if __name__ == "__main__":
    main()