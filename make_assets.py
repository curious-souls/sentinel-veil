"""Generates the fake phishing-page screenshot used in the image scenario.
Everything on it is invented: the bank name and domain are not real."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fake_login.png")
os.makedirs(os.path.dirname(OUT), exist_ok=True)


def font(size, bold=False):
    names = ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for n in names:
        for base in ("/usr/share/fonts/truetype/dejavu/", ""):
            try:
                return ImageFont.truetype(base + n, size)
            except OSError:
                continue
    return ImageFont.load_default()


img = Image.new("RGB", (900, 640), "white")
d = ImageDraw.Draw(img)
d.rectangle([0, 0, 900, 70], fill=(20, 60, 140))
d.text((30, 18), "SecureTrust Bank NetBanking", fill="white", font=font(32, True))
d.text((30, 100), "Your account is LOCKED", fill=(180, 0, 0), font=font(36, True))
d.text((30, 160), "Verify immediately. Session expires in 10 minutes.", fill="black", font=font(26))
d.text((30, 215), "Enter User ID, Password and the OTP sent to you:", fill="black", font=font(26))
for i, label in enumerate(["User ID", "Password", "OTP"]):
    y = 280 + i * 80
    d.text((30, y), label, fill="black", font=font(24))
    d.rectangle([220, y - 6, 780, y + 40], outline="black", width=2)
d.rectangle([220, 530, 480, 585], fill=(20, 60, 140))
d.text((255, 543), "VERIFY NOW", fill="white", font=font(26, True))
d.text((30, 605), "http://securetrust-verify.xyz/login", fill=(90, 90, 90), font=font(20))
img.save(OUT)
print("wrote", OUT)
