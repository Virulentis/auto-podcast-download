import requests
import os
import json
from dotenv import load_dotenv
from urllib.parse import quote_plus
import logging
import datetime
import re

def findAllAudioLinks():
    tag = ""
    if os.getenv("TAGS"):
        tag = f'?tag={quote_plus(os.getenv("TAGS"))}'
    url = f'{os.getenv("API_SITE")}{os.getenv("PROVIDER")}/user/{os.getenv("CREATOR_ID")}/posts{tag}'
    logger.info(f"Fetching posts from: {url}")
    try:
        response = requests.get(
            url,
            headers={
                "Accept": "text/css",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
        )
        if response.status_code != 200:
            logger.error(f"API request failed with status {response.status_code}")
            raise Exception(f"received {response.status_code} instead of 200")
        data = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error: {e}")
        raise

    return data


def findNewPosts():

    try:
        with open("seen_posts.json", "r") as f:
            seen_ids = set(json.load(f))
            logger.info(f"Loaded {len(seen_ids)} previously seen posts")
    except FileNotFoundError:
        seen_ids = set()
        logger.info("No previous seen_posts.json found, starting fresh")

    data = findAllAudioLinks()

    new_posts = [post for post in data if post["id"] not in seen_ids]

    logger.info(f"Found {len(new_posts)} new posts to process")
    return new_posts, seen_ids


def download_audio(url, filename):
    """Download a single audio file"""
    response = requests.get(url, stream=True)

    if response.status_code == 200:
        with open(filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"Downloaded: {filename}")
        return True
    else:
        print(f"Failed: {response.status_code}")
        return False


def download_new_posts():
    """Download all new audio posts"""
    new_posts, seen_ids = findNewPosts()
    
    successful_ids = []
    failed_posts = []

    os.makedirs(f"{os.getenv("DOWNLOAD_PATH")}podcasts_audio", exist_ok=True)

    for post in new_posts:
        if post.get("file"):

            path = post["file"]["path"]
            url = f"{os.getenv("DEFAULT_SITE")}/data{path}"

            filename = f"{post["title"]}-{post["file"]["name"]}"
            filename = re.sub(r"[/\\?%*:|\"<>\x7F\x00-\x1F]", "-", filename)
            filepath = os.path.join(f"{os.getenv("DOWNLOAD_PATH")}podcasts_audio", filename)

            if download_audio(url, filepath):
                logger.info(f"Downloaded {post['title']}")
                successful_ids.append(post["id"])
                print(successful_ids)
            else:
                failed_posts.append(
                    {
                        "id": post["id"],
                        "title": post["title"],
                        "url": url,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
        else:
            logger.info(f"post {post['title']} has no file attached")

        if successful_ids:
            seen_ids.update(successful_ids)
            with open("seen_posts.json", "w") as f:
                json.dump(list(seen_ids), f, indent=2)
            logger.info(f"Marked {len(successful_ids)} posts as seen")

        if failed_posts:
            logger.warning(f"⚠ {len(failed_posts)} downloads failed")
            try:
                existing_fails = []
                if os.path.exists('failed_downloads.json'):
                    with open('failed_downloads.json', 'r') as f:
                        existing_fails = json.load(f)
                
                existing_fails.extend(failed_posts)
                
                with open('failed_downloads.json', 'w') as f:
                    json.dump(existing_fails, f, indent=2)
                logger.info(f"Failed downloads logged to failed_downloads.json")
            except Exception as e:
                logger.error(f"Could not save failed downloads: {e}")
    
    logger.info(f"Download session complete: {len(successful_ids)} successful, {len(failed_posts)} failed")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("downloads.log"),
            logging.StreamHandler(),  # Also print to console
        ],
    )
    logger = logging.getLogger(__name__)
    load_dotenv()

    try:
        download_new_posts()
    except Exception as e:
        logger.critical(f"Script failed with error: {e}", exc_info=True)
