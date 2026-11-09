"""The PixelLab calls with the web stubbed out. Spends nothing and never touches the real token.

usage: python test_pixellab.py
"""
import base64
import io
import json
import urllib.error
import urllib.request

import common
import pixellab

SECRET = "Bearer not-a-real-token"


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def web(script, seen):
    """urlopen that plays back a list: a dict is a reply, an int is that HTTP error."""
    steps = iter(script)

    def urlopen(req, timeout=None):
        seen.append(req)
        step = next(steps)
        if isinstance(step, int):
            raise urllib.error.HTTPError(req.full_url, step, "no", {"Retry-After": "0"}, io.BytesIO(b"nope"))
        return Reply(json.dumps(step).encode())
    return urlopen


def stops(script, needs):
    urllib.request.urlopen = web(script, [])
    try:
        pixellab.inpaint(b"i", b"m", "d", 1, timeout=0.2)
    except common.CrewStop as e:
        assert needs in str(e) and SECRET not in str(e) and "not-a-real" not in str(e), (needs, e)
        return
    raise AssertionError(f"should have stopped: {needs}")


def main():
    real = urllib.request.urlopen
    pixellab._token = SECRET
    pixellab.POLL_SECONDS = 0
    pixellab.BUSY_SECONDS = 0
    picture = base64.b64encode(b"painted").decode()
    started = {"background_job_id": "j1", "usage": None}
    try:
        seen = []
        urllib.request.urlopen = web([started, {"status": "processing"}, {"status": "completed", "usage": {"type": "generations", "generations": 3},
                                                                          "last_response": {"image": {"base64": picture}}}], seen)
        png, usage = pixellab.inpaint(b"img", b"mask", "a head", 7)
        assert png == b"painted" and usage["generations"] == 3
        assert seen[0].full_url.endswith("/inpaint-image-pro-flash") and seen[0].get_header("Authorization") == SECRET
        body = json.loads(seen[0].data)
        assert body["image"]["base64"] == base64.b64encode(b"img").decode() and body["mask_image"]["base64"] == base64.b64encode(b"mask").decode()
        assert body["description"] == "a head" and body["seed"] == 7 and body["output_method"] == "Modify current layer"
        assert seen[1].full_url.endswith("/background-jobs/j1")
        print("Sends the image and mask, waits for the job, and returns the painting")

        urllib.request.urlopen = web([started, {"status": "completed", "usage": {"usd": 0.03}, "last_response": {"images": [{"base64": picture}]}}], [])
        assert pixellab.inpaint(b"i", b"m", "d", 1)[0] == b"painted"
        assert pixellab.spent() == {"calls": 2, "usd": 0.03, "generations": 3}, pixellab.spent()
        print("Finds the image in either reply shape, and adds up what the calls cost")

        urllib.request.urlopen = web([429, 429, started, {"status": "completed", "last_response": {"image": {"base64": picture}}}], [])
        assert pixellab.inpaint(b"i", b"m", "d", 1)[0] == b"painted"
        print("Too many jobs gets waited out")

        stops([429] * pixellab.BUSY_TRIES, "too busy")
        stops([402], "out of credits")
        stops([401], "token")
        stops([500], "HTTP 500")
        stops([started, {"status": "failed", "last_response": {"error": "bad"}}], "failed")
        stops([started, {"status": "completed", "last_response": {"nothing": 1}}], "no image")
        stops([started] + [{"status": "processing"}] * 100000, "did not finish")
        print("Out of credits, a failed job and a job that never finishes all stop the run, and the token is in none of the messages")

        urllib.request.urlopen = web([{"credits": {"usd": 1.5}, "subscription": {"generations": 37}}], [])
        assert pixellab.balance() == {"usd": 1.5, "generations": 37}
        print("Reads the balance")

        urllib.request.urlopen = web([{"credits": {"usd": 0}, "subscription": {"generations": 22}}], [])
        pixellab.check_room()
        urllib.request.urlopen = web([{"credits": {"usd": 0}, "subscription": {"generations": 4}}], [])
        try:
            pixellab.check_room()
            raise AssertionError("too few generations left should ask David")
        except common.NeedsDavid as e:
            assert "4 generations" in str(e), e
        urllib.request.urlopen = web([{"credits": {"usd": 2.0}, "subscription": {"generations": 0}}], [])
        pixellab.check_room()
        print("Asks David before a call that would run PixelLab dry; credits count as room")
    finally:
        urllib.request.urlopen = real
    print("all passed")


if __name__ == "__main__":
    main()
