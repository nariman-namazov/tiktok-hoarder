import json, boto3, requests, subprocess, os, http.cookiejar
from threading import Thread
from glob import glob

"""
1. Using cookies, go to your feed and get a list of all authors.
2. Iterate through the dictionary and create several {author: [video_id, video_id1,...]} dictionaries.
3. Iterate through the dictionaries and push each video to Telegram.
"""

# Converting duration from ffmpeg's output into seconds Telegram will comprehend.
def time(time):
    chunks = time.split("\n")[0].split(":")
    seconds = int(chunks[0]) * 60 * 60 + int(chunks[1]) * 60 + int(chunks[2])

    return int(seconds)

# Opening cookies.txt file and using the data from there. Has to be uploaded to S3 manually by someone.
# Pulling a file with TikTok cookies from the browser because TikTok authentication via passport/web/user/login/ is too complicated for my brain. :^)
def get_cookies(cookies_path):
    cookies = {}; cj = http.cookiejar.MozillaCookieJar(); cj.load(filename=cookies_path)
    for c in cj:
        cookies[str(c).split("Cookie ")[1].split("=")[0]] = str(c).split("Cookie ")[1].split("=")[1].split(" for")[0]

    return cookies

# Not used right now. Potential future functionality. Collecting IDs of all videos from a given account.
def collectVideoIds(username):
    res = requests.get(f"https://www.tiktok.com/@{username}", headers={"Content-Type": "application/json"})
    output = res.content.decode().replace('<script id="SIGI_STATE"', '\n<script id="SIGI_STATE"'); output = output.replace('</script>', '\n</script>')
    for line in output.split("\n"):
        if "SIGI_STATE" in line:
            target = line
            break
    target = target.replace('<script id="SIGI_STATE" type="application/json">', ""); target = target.replace('</script>', "")
    target = json.loads(target)

    return target["ItemList"]["user-post"]["list"]

# The multithreaded function.
def downloadVideo(username, video):
    cmd_str = f"/var/task/yt-dlp --config-locations /var/task/yt-dlp.conf https://www.tiktok.com/@{username}/video/{video}"
    _event = subprocess.run(cmd_str, shell=True, capture_output=True, text=True)
    try:
        print (f"All good: {_event.stdout}")
    except:
        print (f"All bad: {_event.stderr}")

def shipToTelegram(username, videos):
    files = {}; media = []
    # https://stackoverflow.com/questions/11968689/python-multithreading-wait-till-all-threads-finished
    threadz = [Thread(target=downloadVideo, args=[username, video]) for video in videos]
    [t.start() for t in threadz]
    [t.join() for t in threadz]

    if len(videos) > 1:
        print ("All {len(videos)} threads finished running.")
        # Request requirements with a single video are different from those of a request with several videos.
        for _file in glob(f"/tmp/{username}*.mp4"):
            thumb = _file.split(".mp4")[0] + "_thumb.jpg"
            # Do three things simultaneously: 1) create a thumbnail, 2) get video duration, and 3) get video resolution.
            cmd_str = f"""/var/task/ffmpeg -y -i {_file} -vf scale=w='min(320\, iw*3/2):h=-1' -vframes 1 {thumb} 2>&1 | grep -oP '(Duration: \K[0-9]+:[0-9]+:[0-9]+)|(Stream .*, \K[0-9]+x[0-9]+)' | head -2"""
            event = subprocess.run(cmd_str, shell=True, capture_output=True, text=True)
            duration = time(event.stdout); height = int(event.stdout.split("\n")[1].split("x")[1]); width = int(event.stdout.split("\n")[1].split("x")[0])
            files[_file] = open(_file, "rb"); files[thumb] = open(thumb, "rb")
            media.append({"type": "video", "media": f"attach://{_file}", "thumbnail": f"attach://{thumb}", "supports_streaming": True, "width": width, "height": height, "duration": duration})
        # https://stackoverflow.com/questions/58893142/how-to-send-telegram-mediagroup-with-caption-text
        media[0]["caption"] = f"Завантажено з допомогою tiktok-hoarder.\nhttps://www.tiktok.com/@{username}"
        payload = {
            "chat_id": CHAT_ID,
            "media": json.dumps(media),
            "disable_notification": True
        }
        msg = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMediaGroup", params=payload, files=files)
        if not msg.json()["ok"]:
            print (f"Caught an error uploading {media} to Telegram:", msg.json())
            if FEEDBACK_CHANNEL != "/dev/null":
                report = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", headers={"Content-Type": "application/json", "Cache-Control": "no-cache"}, json={"chat_id":FEEDBACK_CHANNEL, "is_personal": False, "text": f"Caught an error uploading {['https://www.tiktok.com/@' + username + '/video/' + _item + '; ' for _item in videos]} to Telegram:\n{msg.json()}"})
                if not report.json["ok"]:
                    print (f"Caught an error reporting another error to the feedback channel:\n{report.json()}")
    elif len(videos) != 0:
        thumb = "{username}-{videos[0]}_thumb.jpg"
        # Do three things simultaneously: 1) create a thumbnail, 2) get video duration, and 3) get video resolution.
        cmd_str = f"""/var/task/ffmpeg -y -i {username}-{videos[0]}.mp4 -vf scale=w='min(320\, iw*3/2):h=-1' -vframes 1 {thumb} 2>&1 | grep -oP '(Duration: \K[0-9]+:[0-9]+:[0-9]+)|(Stream .*, \K[0-9]+x[0-9]+)' | head -2"""
        event = subprocess.run(cmd_str, shell=True, capture_output=True, text=True)
        duration = time(event.stdout); height = int(event.stdout.split("\n")[1].split("x")[1]); width = int(event.stdout.split("\n")[1].split("x")[0])
        files = {"video": (f"{username}-{videos[0]}.mp4", open(f"/tmp/{username}-{videos[0]}.mp4", "rb"), "thumbnail": (f"{thumb}", open("{thumb}",   "rb")))}
        payload = {
            "chat_id": CHAT_ID,
            "caption": f"Завантажено з допомогою tiktok-hoarder.\nhttps://www.tiktok.com/@{username}",
            "is_personal": False,
            "disable_notification": True,
            "supports_streaming": True,
            "duration": duration,
            "height": height,
            "width": width
        }
        msg = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendVideo", data=payload, files=files)
        if not msg.json()["ok"]:
            print (f"Caught an error uploading {files} to Telegram:", msg.json())
            if FEEDBACK_CHANNEL != "/dev/null":
                report = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", headers={"Content-Type": "application/json", "Cache-Control": "no-cache"}, json={"chat_id": FEEDBACK_CHANNEL, "is_personal": False, "text": f"Caught an error uploading {'https://www.tiktok.com/@' + username + '/video/' + videos[0]} to Telegram:\n{msg.json()}"})
                if not report.json["ok"]:
                    print (f"Caught an error reporting another error to the feedback channel:\n{report.json()}")

# Not used right now. Potential functionality. Pushing videos to S3.
def pushVideo(filename):
    S3.upload_file(f"{'/tmp/' + filename}", BUCKET, f"videos/{filename}")
    os.remove(f"{'/tmp/' + filename}")
    print (f"Successfully pushed and removed {filename}")

# Master function Lambda is configured to execute.
def lambda_handler(event, context):
    global S3, CHAT_ID, BUCKET, TOKEN, FEEDBACK_CHANNEL, GEOLOCK     # see CF template for the description of all but S3
    CHAT_ID = os.environ["chat_id"]; BUCKET = os.environ["bucket"]; TOKEN = os.environ["token"]; FEEDBACK_CHANNEL = os.environ["feedback"]; GEOLOCK = os.environ["geolock"]
    if "local_storage:" not in BUCKET:
        S3 = boto3.client("s3"); S3.download_file(BUCKET, "cookies.txt", "/tmp/cookies.txt")
        cookies = get_cookies("/tmp/cookies.txt")
    else:
        cookies = get_cookies(BUCKET.split(":")[1])


    # Getting videos from the personal feed.
    # Apparently, regardless of the query parameters TikTok will give you exactly 8 videos per GET request.
    res = requests.get(f"https://api19-va.tiktokv.com/aweme/v1/feed/?type=0&app_name=trill&min_cursor=-1&max_cursor=0&region={GEOLOCK}", cookies=cookies, headers={"Content-Type": "application/json"}).json()["aweme_list"]
    authors_and_videos = {}
    # This is how geolock is additionally enforced, apart from passing geolock parameters.
    if video["author"]["region"] != GEOLOCK:
        print (f"Skipping https://www.tiktok.com/@{video['author']['unique_id']}/video/{video['aweme_id']} because it came from {video['author']['region']} instead of {GEOLOCK}.")
        continue
    else:
        authors_and_videos.setdefault(video["author"]["unique_id"], []).append(video["aweme_id"])

    threadz = [Thread(target=shipToTelegram, args=[author, authors_and_videos[author]]) for author in authors_and_videos]
    [t.start() for t in threadz]
    [t.join() for t in threadz]

    removal_counter = 0
    for _object in glob(f"/tmp/*.mp4"):
        try:
            print (f"Removing {_object}"); os.remove(f"{_object}"); removal_counter += 1
        except Exception as e:
            print (f"Removed {removal_counter} in total and failed to remove {_object}. Reason:\n{e}")

    return {
        'statusCode': 200,
        'body': json.dumps(f"Pushed {removal_counter} videos this time.")
    }
