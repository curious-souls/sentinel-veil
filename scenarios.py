"""The demo scenarios. Audio (call) scenarios are planned for a later version."""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

SCENARIOS = {
    "1. Normal chat": {
        "kind": "message", "sender": "Saved contact: Rahul",
        "text": "Hey, are we still meeting at 6? Bring the notes from yesterday.",
        "sender_known": True, "banking_app_open": False, "remote_app_running": False,
        "expect": "ALLOW",
    },
    "2. Real bank OTP (must NOT be blocked)": {
        "kind": "message", "sender": "Verified sender: VM-HDFCBK",
        "text": "123456 is your OTP for login to HDFC NetBanking. Do not share it with anyone. -HDFC Bank",
        "sender_known": True, "banking_app_open": True, "remote_app_running": False,
        "expect": "ALLOW",
    },
    "3. Fake bank SMS": {
        "kind": "message", "sender": "Unknown number",
        "text": "Dear customer, your SBI account will be blocked today! Update KYC immediately: "
                "http://sbi-kyc-update.xyz and share the OTP you receive to avoid suspension.",
        "sender_known": False, "banking_app_open": False, "remote_app_running": False,
        "expect": "REJECT",
    },
    "4. Phishing page screenshot (image + OCR)": {
        "kind": "screen", "sender": "Page opened from a link",
        "image": os.path.join(ROOT, "assets", "fake_login.png"),
        "text": "",
        # Used ONLY if Tesseract is missing, and the app labels it. It is the text drawn on the image.
        "ocr_fallback": "SecureTrust Bank NetBanking\nYour account is LOCKED\n"
                        "Verify immediately. Session expires in 10 minutes.\n"
                        "Enter User ID, Password and the OTP sent to you:\nUser ID\nPassword\nOTP\nVERIFY NOW\n"
                        "http://securetrust-verify.xyz/login",
        "sender_known": False, "banking_app_open": False, "remote_app_running": False,
        "expect": "CHALLENGE",
    },
    "5. UPI 'sent by mistake' scam": {
        "kind": "message", "sender": "Unknown number",
        "text": "Sir I sent Rs 5000 to your number by mistake. Please accept the collect request "
                "on your UPI app and enter your PIN to return it.",
        "sender_known": False, "banking_app_open": True, "remote_app_running": False,
        "expect": "CHALLENGE or REJECT",
    },
    "6. Hinglish electricity scam": {
        "kind": "message", "sender": "Unknown number",
        "text": "Aapka bijli connection aaj raat 9 baje kat jayega. Turant is number par call karein "
                "aur apna OTP bataiye.",
        "sender_known": False, "banking_app_open": False, "remote_app_running": False,
        "expect": "CHALLENGE or REJECT",
    },
    "7. Delivery update with short link (gray area)": {
        "kind": "message", "sender": "Unknown number",
        "text": "Delivery update: your package arrives today between 2-6 pm. Track here: https://bit.ly/3xYzAbc",
        "sender_known": False, "banking_app_open": False, "remote_app_running": False,
        "expect": "DELAY",
    },
}


# ---------------------------------------------------------------------------
# Simulated live calls. The transcript streams in line by line, as if live
# speech-to-text were running. In a real product this audio would come from
# OS-level access (phone maker / OS vendor); here it is SIMULATED.
# ---------------------------------------------------------------------------
CALLS = {
    "8. Scam call: 'bank security desk' (simulated live call)": {
        "caller": "Unknown number", "sender_known": False,
        "lines": [
            "Hello sir, I am calling from the security department of your bank.",
            "We noticed a suspicious transaction, so your account may be blocked today.",
            "To stop it I need to verify you. Please open your UPI app right now.",
            "You will get a collect request. Accept it and enter your PIN to cancel the fraud.",
            "Also read me the OTP that just came on your phone, quickly, before the account is blocked.",
        ],
        "expect": "warning mid-call, payment app frozen",
    },
    "9. Genuine call: pharmacy delivery (simulated live call)": {
        "caller": "Unknown number", "sender_known": False,
        "lines": [
            "Hello, this is City Pharmacy. Your medicine order is ready for delivery.",
            "The delivery person will reach you in about twenty minutes.",
            "Please keep the exact amount ready, or pay by UPI when it arrives at your door.",
        ],
        "expect": "no warning, payment app opens normally",
    },
}
