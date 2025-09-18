from pathlib import Path
import io
from PIL import Image
import cv2
import numpy as np

label_shim = Path(f"{Path(__file__).parent}/stub/label.js").read_text()


async def extract(page):
    labels, size, title = await page.evaluate(label_shim)

    image_data = await page.screenshot()
    image = Image.open(io.BytesIO(image_data))

    return image, labels, title


import cv2
import numpy as np


def locate_browser(screen_image, dom_image, threshold=0.5, padding=0):
    try:
        # Convert PIL Image to OpenCV format
        needle = cv2.cvtColor(np.array(dom_image), cv2.COLOR_BGR2RGB)
        haystack = cv2.cvtColor(np.array(screen_image), cv2.COLOR_BGR2RGB)

        # Apply padding
        needle_padded = cv2.copyMakeBorder(
            needle,
            padding,
            padding,
            padding,
            padding,
            cv2.BORDER_CONSTANT,
            value=[0, 0, 0],
        )

        # Initialize KAZE detector
        kaze = cv2.KAZE_create()

        # Find the keypoints and descriptors with KAZE
        keypoints1, descriptors1 = kaze.detectAndCompute(needle_padded, None)
        keypoints2, descriptors2 = kaze.detectAndCompute(haystack, None)

        # Use BFMatcher with default parameters
        bf = cv2.BFMatcher()
        matches = bf.knnMatch(descriptors1, descriptors2, k=2)

        # Store all the good matches as per Lowe's ratio test
        good_matches = []
        for m, n in matches:
            if m.distance < 0.75 * n.distance:
                good_matches.append(m)

        has_match = (
            len(good_matches) >= 10
        )  # Consider a match if there are enough good matches

        if not has_match:
            return [0, 0, 0, 0], False

        src_pts = np.float32([keypoints1[m.queryIdx].pt for m in good_matches]).reshape(
            -1, 2
        )
        dst_pts = np.float32([keypoints2[m.trainIdx].pt for m in good_matches]).reshape(
            -1, 2
        )

        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        matches_mask = mask.ravel().tolist()

        h, w = needle_padded.shape[:2]
        pts = np.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(
            -1, 1, 2
        )
        dst = cv2.perspectiveTransform(pts, M)

        region = [
            int(min(dst[:, 0, 0])),
            int(min(dst[:, 0, 1])),
            int(max(dst[:, 0, 0])),
            int(max(dst[:, 0, 1])),
        ]

        return region, has_match
    except Exception as e:
        print("[webparse] Error:", e)
        return [0, 0, 0, 0], False


async def extract_locate(screenshot, page):
    image, entities, _ = await extract(page)
    # screenshot.save('testing.png')
    region, has_match = locate_browser(screenshot, image)
    print("has_match", has_match)

    x, y = region[0], region[1]
    x2, y2 = region[2], region[3]
    w, h = x2 - x, y2 - y
    for entity in entities:
        rect = entity["rect"]
        entity["mapped_rect"] = (
            x + rect[0] * w,
            y + rect[1] * h,
            x + rect[2] * w,
            y + rect[3] * h,
        )
        entity["shape"] = [
            entity["mapped_rect"][0],
            entity["mapped_rect"][1],
            entity["mapped_rect"][2] - entity["mapped_rect"][0],
            entity["mapped_rect"][3] - entity["mapped_rect"][1],
        ]

    return has_match, entities
